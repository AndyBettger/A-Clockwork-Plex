#!/usr/bin/python3
from __future__ import annotations

"""Stage C13 root-owned typed read-only host-adapter rehearsal."""

import argparse
import json
import os
import platform
import stat
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    PackageFingerprint,
    ProductionAdapter,
    ProductionAdapterBlocked,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .read_only_host_adapter import (
    APPLICATION_SERVICE_UNITS,
    PERMITTED_OPERATIONS,
    STAGE_C_SERVICE_UNITS,
    ReadOnlyHostProductionAdapter,
)
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C13-TYPED-READ-ONLY-HOST-ADAPTER"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c13-read-only-adapter."
EXPECTED_CHECKS = (
    "root-scope",
    "observation-identity",
    "protocol-conformance",
    "host-contract",
    "production-lock-boundary",
    "service-snapshot",
    "mixer-snapshot",
    "loopback-snapshot",
    "dac-snapshot",
    "blocked-operation-boundary",
    "evidence-integrity",
    "activation-interface",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage C13 typed read-only real-host adapter rehearsal. "
            "No production operation is implemented."
        )
    )
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    if not raw.is_absolute() or raw.parent != Path("/var/tmp"):
        raise SystemExit("--evidence-root must be directly beneath /var/tmp.")
    if not raw.name.startswith(EVIDENCE_PREFIX):
        raise SystemExit(f"--evidence-root name must start with {EVIDENCE_PREFIX}")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit("--evidence-root must already exist and be empty.") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("--evidence-root must be a real directory.")
    if info.st_uid != invoking_uid:
        raise SystemExit("--evidence-root must be owned by the invoking user.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("--evidence-root must have mode 0700.")
    if any(raw.iterdir()):
        raise SystemExit("--evidence-root must be empty.")
    return raw.resolve()


def append_result(path: Path, check: str, detail: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def require_pass(result: AdapterResult[Any], operation: AdapterOperation) -> Any:
    if result.operation is not operation:
        raise SystemExit(
            f"Adapter returned {result.operation.value} for {operation.value}."
        )
    if result.status is not AdapterStatus.PASS or result.payload is None:
        raise SystemExit(f"{operation.value} failed: {result.detail}")
    return result.payload


def jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value


def write_identity(
    output: Path,
    *,
    transaction: TransactionIdentity,
    invoking_user: str,
) -> None:
    rows = (
        ("identity", transaction.value),
        ("host", platform.node()),
        ("architecture", platform.machine()),
        ("invoking_user", invoking_user),
        ("generated", datetime.now().astimezone().isoformat(timespec="microseconds")),
        ("caller_supplied", "false"),
        ("production_authoritative", "false"),
        ("persistent", "false"),
    )
    output.write_text(
        "item\tvalue\n" + "".join(f"{item}\t{value}\n" for item, value in rows),
        encoding="utf-8",
    )


def validate_service_snapshot(snapshot: ServiceSnapshot) -> None:
    by_unit = {service.unit: service for service in snapshot.services}
    for unit in APPLICATION_SERVICE_UNITS:
        state = by_unit[unit]
        if (
            state.load is not ServiceLoadState.LOADED
            or state.active is not ServiceActiveState.ACTIVE
            or state.enabled is not ServiceEnableState.ENABLED
        ):
            raise SystemExit(
                f"Application service boundary changed: {unit.value} "
                f"load={state.load.value} active={state.active.value} "
                f"enabled={state.enabled.value}"
            )
    for unit in STAGE_C_SERVICE_UNITS:
        state = by_unit[unit]
        if (
            state.load is not ServiceLoadState.NOT_FOUND
            or state.enabled is not ServiceEnableState.NOT_FOUND
        ):
            raise SystemExit(
                f"Unexpected existing Stage C service: {unit.value} "
                f"load={state.load.value} enabled={state.enabled.value}"
            )


def _expect_blocked(
    rows: list[tuple[str, str]],
    operation: AdapterOperation,
    call: Callable[[], object],
) -> None:
    try:
        call()
    except ProductionAdapterBlocked as exc:
        if exc.operation is not operation:
            raise SystemExit(
                f"Blocked operation identity mismatch: expected {operation.value}, "
                f"found {exc.operation.value}"
            ) from exc
        rows.append((operation.value, "blocked"))
        return
    raise SystemExit(f"Operation unexpectedly became executable: {operation.value}")


def prove_blocked_operations(
    adapter: ReadOnlyHostProductionAdapter,
    *,
    transaction: TransactionIdentity,
    services: ServiceSnapshot,
    mixer,
) -> list[tuple[str, str]]:
    package = PackageFingerprint("0" * 64)
    snapshot = SnapshotIdentity("stage-c13-non-authoritative-snapshot")
    rows: list[tuple[str, str]] = []

    _expect_blocked(
        rows,
        AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
        lambda: adapter.acquire_production_lock(),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RELEASE_PRODUCTION_LOCK,
        lambda: adapter.release_production_lock(),
    )
    _expect_blocked(
        rows,
        AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
        lambda: adapter.create_authoritative_transaction(
            TransactionAction.INSTALL,
            package,
        ),
    )
    _expect_blocked(
        rows,
        AdapterOperation.CAPTURE_FILESYSTEM_STATE,
        lambda: adapter.capture_filesystem_state(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.STAGE_CANDIDATE_FILES,
        lambda: adapter.stage_candidate_files(transaction, package),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VALIDATE_CANDIDATE_ALSA,
        lambda: adapter.validate_candidate_alsa(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
        lambda: adapter.validate_candidate_sudoers(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VALIDATE_CANDIDATE_UNITS,
        lambda: adapter.validate_candidate_units(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
        lambda: adapter.validate_candidate_camilladsp(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
        lambda: adapter.stop_captured_application_services(transaction, services),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VERIFY_DAC_RELEASED,
        lambda: adapter.verify_dac_released(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.INSTALL_MANAGED_FILES,
        lambda: adapter.install_managed_files(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RELOAD_SYSTEMD,
        lambda: adapter.reload_systemd(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
        lambda: adapter.select_split_bus_route(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
        lambda: adapter.start_managed_stage_c_services(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
        lambda: adapter.stop_managed_stage_c_services(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
        lambda: adapter.verify_split_bus_health(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RUN_FINITE_MUSIC_PROBE,
        lambda: adapter.run_finite_music_probe(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RUN_FINITE_ALARM_PROBE,
        lambda: adapter.run_finite_alarm_probe(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
        lambda: adapter.restore_captured_application_services(transaction, services),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VERIFY_DASHBOARD_HEALTH,
        lambda: adapter.verify_dashboard_health(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.WRITE_COMMIT_MANIFEST,
        lambda: adapter.write_commit_manifest(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
        lambda: adapter.select_direct_failback_route(transaction),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RESTORE_EXACT_SNAPSHOT,
        lambda: adapter.restore_exact_snapshot(transaction, snapshot),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RESTORE_MIXER_STATE,
        lambda: adapter.restore_mixer_state(transaction, mixer),
    )
    _expect_blocked(
        rows,
        AdapterOperation.RESTORE_SERVICE_STATE,
        lambda: adapter.restore_service_state(transaction, services),
    )
    _expect_blocked(
        rows,
        AdapterOperation.VERIFY_EXACT_ROLLBACK,
        lambda: adapter.verify_exact_rollback(transaction, snapshot),
    )

    expected = set(AdapterOperation).difference(PERMITTED_OPERATIONS)
    observed = {
        AdapterOperation(operation)
        for operation, state in rows
        if state == "blocked"
    }
    if observed != expected or len(rows) != len(expected):
        raise SystemExit(
            f"Blocked operation coverage changed: expected={len(expected)} "
            f"observed={len(rows)}"
        )
    return rows


def write_blocked_operations(output: Path, rows: list[tuple[str, str]]) -> None:
    output.write_text(
        "operation\tstate\n"
        + "".join(f"{operation}\t{state}\n" for operation, state in rows),
        encoding="utf-8",
    )


def write_report(output: Path, *, evidence_root: Path, owner_count: int) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C13 typed read-only host-adapter rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Typed real-host operations: {len(PERMITTED_OPERATIONS)}
Blocked operations: {len(AdapterOperation) - len(PERMITTED_OPERATIONS)}
Structured DAC owners: {owner_count}

Proved:
- six fixed typed observations were obtained from the real host
- the observation identity was generated by the adapter and was non-authoritative
- the production route-lock path was inspected with lstat and remained absent
- current route, service, mixer, loopback and DAC boundaries matched the reviewed host
- all other adapter operations remained blocked with exact identities
- evidence was written only beneath the fresh Stage C13 directory

Not proved:
- production-lock acquisition or contention
- production transaction or activation-time filesystem snapshot
- package validation or installation
- service, mixer, module, PCM, DAC or route mutation
- split-bus startup, failback, rollback, uninstall or reboot persistence

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Read-only host-adapter rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)

    os.chown(evidence_root, 0, 0)
    evidence_root.chmod(0o700)
    completed = False
    try:
        results_path = evidence_root / "results.tsv"
        results_path.write_text("check\tresult\tdetail\n", encoding="utf-8")
        append_result(
            results_path,
            "root-scope",
            f"root writes constrained to {evidence_root}",
        )

        adapter = ReadOnlyHostProductionAdapter()
        transaction = adapter.observation_transaction
        substituted = adapter.capture_service_state(
            TransactionIdentity("stage-c13-substituted-observation")
        )
        if (
            substituted.operation is not AdapterOperation.CAPTURE_SERVICE_STATE
            or substituted.status is not AdapterStatus.FAIL
            or substituted.payload is not None
        ):
            raise SystemExit("Substituted observation identity was not rejected.")
        write_identity(
            evidence_root / "identity.tsv",
            transaction=transaction,
            invoking_user=invoking_user,
        )
        append_result(
            results_path,
            "observation-identity",
            "fresh adapter-generated identity; substituted identity rejected before host access",
        )

        if not isinstance(adapter, ProductionAdapter):
            raise SystemExit("Read-only adapter does not conform to ProductionAdapter.")
        append_result(
            results_path,
            "protocol-conformance",
            "adapter conforms while overriding exactly six operations",
        )

        host_result = adapter.inspect_host_contract()
        require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
        append_result(
            results_path,
            "host-contract",
            "aarch64, exact stable route and fixed typed contract verified",
        )

        lock_result = adapter.inspect_production_lock()
        lock = require_pass(lock_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
        if lock.exists or lock.held_by_caller:
            raise SystemExit("Production route lock must remain absent in Stage C13.")
        append_result(
            results_path,
            "production-lock-boundary",
            f"{lock.path} absent and not opened",
        )

        service_result = adapter.capture_service_state(transaction)
        services = require_pass(
            service_result,
            AdapterOperation.CAPTURE_SERVICE_STATE,
        )
        validate_service_snapshot(services)
        append_result(
            results_path,
            "service-snapshot",
            "three application services active/enabled; three Stage C services absent",
        )

        mixer_result = adapter.capture_mixer_state(transaction)
        mixer = require_pass(mixer_result, AdapterOperation.CAPTURE_MIXER_STATE)
        append_result(
            results_path,
            "mixer-snapshot",
            "four fixed ALSA controls returned typed percentages",
        )

        loopback_result = adapter.capture_loopback_state(transaction)
        loopback = require_pass(
            loopback_result,
            AdapterOperation.CAPTURE_LOOPBACK_STATE,
        )
        if not loopback.loaded:
            raise SystemExit("Expected snd_aloop to remain loaded.")
        append_result(
            results_path,
            "loopback-snapshot",
            "snd_aloop exact index, id, substreams, notify and enable state verified",
        )

        dac_result = adapter.capture_dac_state(transaction)
        dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
        if dac.released or not dac.owners:
            raise SystemExit("Expected the active appliance DAC owner to be visible.")
        if not any(
            owner.command == "node" and "read-write" in owner.access
            for owner in dac.owners
        ):
            raise SystemExit("Expected structured read-write Node DAC owner evidence.")
        append_result(
            results_path,
            "dac-snapshot",
            f"exact DAC format and {len(dac.owners)} structured owner(s) captured",
        )

        typed_results = (
            host_result,
            lock_result,
            service_result,
            mixer_result,
            loopback_result,
            dac_result,
        )
        (evidence_root / "typed-observations.json").write_text(
            json.dumps(
                {
                    "identity": transaction.value,
                    "production_authoritative": False,
                    "operations": [jsonable(result) for result in typed_results],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        blocked = prove_blocked_operations(
            adapter,
            transaction=transaction,
            services=services,
            mixer=mixer,
        )
        write_blocked_operations(
            evidence_root / "blocked-operations.tsv",
            blocked,
        )
        append_result(
            results_path,
            "blocked-operation-boundary",
            f"all {len(blocked)} non-observation operations refused exactly",
        )

        write_report(
            evidence_root / "report.txt",
            evidence_root=evidence_root,
            owner_count=len(dac.owners),
        )
        write_evidence_manifest(evidence_root)
        append_result(
            results_path,
            "evidence-integrity",
            "complete checksummed evidence tree contains no symlink or special object",
        )
        append_result(
            results_path,
            "activation-interface",
            "absent; no production lock, transaction, install, activation or rollback action",
        )
        write_evidence_manifest(evidence_root)

        observed_checks = tuple(
            line.split("\t", 1)[0]
            for line in results_path.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed_checks != EXPECTED_CHECKS:
            raise SystemExit(
                f"Unexpected Stage C13 result order: {observed_checks}"
            )
        completed = True
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C13 read-only host-adapter rehearsal did not complete.")

    print(
        f"""
A Clockwork Plex Stage C13 typed read-only host-adapter rehearsal passed.

  Directory:          {evidence_root}
  Results:            {evidence_root / 'results.tsv'}
  Identity:           {evidence_root / 'identity.tsv'}
  Typed observations: {evidence_root / 'typed-observations.json'}
  Blocked operations: {evidence_root / 'blocked-operations.tsv'}
  Evidence manifest:  {evidence_root / 'evidence-manifest.tsv'}
  Report:             {evidence_root / 'report.txt'}

No production path was written or changed. The real production lock was not opened.
Persistent Stage C activation remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
