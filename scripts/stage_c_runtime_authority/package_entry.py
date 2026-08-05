#!/usr/bin/python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .install_runtime_adapter import InstallLinuxRuntimeHostAdapter
from .install_runtime_executor import run_install_route_entry, run_install_supervisor_startup
from .linux_runtime_adapter import LinuxRuntimeHostAdapter
from .linux_runtime_filesystem import LinuxRuntimeFilesystem
from .model import ApprovalPhase, RuntimeAuthorityError
from .runtime_executor import (
    run_boot_preparation,
    run_runtime_child_failure,
    run_supervisor_startup,
)
from .supervisor_service import production_stop_event, supervise_lifetime


INSTALLED_PACKAGE_ROOT = Path(
    "/usr/local/lib/a-clockwork-plex/runtime-authority/stage_c_runtime_authority"
)
PACKAGE_CONTRACT = Path(
    "/usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json"
)
STATE_ROOT = Path("/var/lib/a-clockwork-plex/split-bus")
FIXED_ACTIONS = (
    "status",
    "validate-runtime",
    "boot-prepare",
    "supervise",
    "emergency-direct-failback",
    "accept-install-handoff",
    "promote-committed-approval",
)
TRANSACTION_ONLY_ACTIONS = {
    "accept-install-handoff",
    "promote-committed-approval",
}
MUTATING_ACTIONS = {
    "boot-prepare",
    "supervise",
    "emergency-direct-failback",
    *TRANSACTION_ONLY_ACTIONS,
}


def _json_default(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported result value: {type(value).__name__}")


def _print(payload: dict[str, Any], *, stream=None) -> None:
    print(
        json.dumps(payload, sort_keys=True, default=_json_default),
        file=stream or sys.stdout,
        flush=True,
    )


def _require_installed_image(*, mutation: bool) -> dict[str, Any]:
    actual = Path(__file__).resolve().parent
    if actual != INSTALLED_PACKAGE_ROOT:
        raise RuntimeAuthorityError(
            "runtime authority is not executing from the exact installed package location"
        )
    filesystem = LinuxRuntimeFilesystem()
    contract = filesystem._load_contract()
    if contract.get("package_phase") != "stage-c21-activation-capable-review-v2":
        raise RuntimeAuthorityError("runtime package phase is not activation-capable v2")
    if contract.get("host_mutation_available") is not True:
        raise RuntimeAuthorityError("runtime package contract keeps host mutation blocked")
    if not filesystem._contract_files_valid(contract):
        raise RuntimeAuthorityError("installed runtime package files do not match their contract")
    if mutation and os.geteuid() != 0:
        raise RuntimeAuthorityError("runtime mutation requires root")
    return contract


def validate_runtime() -> dict[str, Any]:
    contract = _require_installed_image(mutation=False)
    return {
        "ok": True,
        "package_phase": contract["package_phase"],
        "package_fingerprint": contract["package_fingerprint"],
        "checked_files": len(contract["files"]),
        "host_mutation_available": True,
    }


def status() -> dict[str, Any]:
    payload = validate_runtime()
    try:
        approval = ApprovalStore(STATE_ROOT).read()
    except (OSError, RuntimeAuthorityError) as exc:
        payload["approval"] = None
        payload["approval_status"] = str(exc)
    else:
        payload["approval"] = approval.as_dict()
        payload["approval_status"] = "valid"
    route_state = STATE_ROOT / "route-state.json"
    try:
        raw_state = json.loads(route_state.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload["route_state"] = None
        payload["route_state_status"] = str(exc)
    else:
        payload["route_state"] = raw_state
        payload["route_state_status"] = "present"
    return payload


def _approval_phase() -> ApprovalPhase:
    return ApprovalStore(STATE_ROOT).read().phase


def _boot_prepare() -> dict[str, Any]:
    phase = _approval_phase()
    if phase is ApprovalPhase.TEMPORARY:
        receipt = run_install_route_entry(InstallLinuxRuntimeHostAdapter())
        return {"ok": True, "path": "temporary-install", "receipt": asdict(receipt)}
    decision, receipt = run_boot_preparation(LinuxRuntimeHostAdapter())
    return {
        "ok": True,
        "path": "committed-boot",
        "decision": asdict(decision),
        "receipt": asdict(receipt),
    }


def _supervise() -> int:
    phase = _approval_phase()
    if phase is ApprovalPhase.TEMPORARY:
        startup_adapter = InstallLinuxRuntimeHostAdapter()
        decision, receipt = run_install_supervisor_startup(startup_adapter)
        startup_path = "temporary-install"
    else:
        startup_adapter = LinuxRuntimeHostAdapter()
        decision, receipt = run_supervisor_startup(startup_adapter)
        startup_path = "committed-boot"
    _print(
        {
            "ok": True,
            "path": startup_path,
            "decision": asdict(decision),
            "receipt": asdict(receipt),
        }
    )
    outcome = supervise_lifetime(
        startup_adapter,
        decision.mode,
        approval_reader=lambda: ApprovalStore(STATE_ROOT).read(),
        ordinary_adapter_factory=LinuxRuntimeHostAdapter,
        stop_event=production_stop_event(),
    )
    _print({"ok": outcome.exit_code == 0, "outcome": asdict(outcome)})
    return outcome.exit_code


def _emergency_direct_failback() -> dict[str, Any]:
    if _approval_phase() is ApprovalPhase.TEMPORARY:
        return {
            "ok": True,
            "deferred": True,
            "reason": "temporary install failure remains owned by exact transaction rollback",
        }
    decision, receipt = run_runtime_child_failure(LinuxRuntimeHostAdapter())
    return {
        "ok": True,
        "deferred": False,
        "decision": asdict(decision),
        "receipt": asdict(receipt),
    }


def main(argv: tuple[str, ...] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    action = arguments[0] if len(arguments) == 1 else ""
    try:
        if action not in FIXED_ACTIONS:
            raise RuntimeAuthorityError("unsupported fixed runtime action")
        _require_installed_image(mutation=action in MUTATING_ACTIONS)
        if action == "status":
            _print(status())
            return 0
        if action == "validate-runtime":
            _print(validate_runtime())
            return 0
        if action in TRANSACTION_ONLY_ACTIONS:
            raise RuntimeAuthorityError(
                "transaction-only approval operation is not exposed through the service helper"
            )
        if action == "boot-prepare":
            _print(_boot_prepare())
            return 0
        if action == "supervise":
            return _supervise()
        if action == "emergency-direct-failback":
            _print(_emergency_direct_failback())
            return 0
        raise RuntimeAuthorityError("unreachable fixed runtime action")
    except (OSError, ValueError, json.JSONDecodeError, RuntimeAuthorityError) as exc:
        _print({"ok": False, "action": action or None, "error": str(exc)}, stream=sys.stderr)
        return 78 if action in MUTATING_ACTIONS else 1


if __name__ == "__main__":
    raise SystemExit(main())
