#!/usr/bin/python3
from __future__ import annotations

"""Stage C14 root-owned production-lock-only rehearsal."""

import argparse
import json
import os
import platform
import stat
import time
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
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
from .production_lock_rehearsal_adapter import (
    PERMITTED_OPERATIONS,
    ProductionLockRehearsalAdapter,
)
from .read_only_host_adapter import (
    APPLICATION_SERVICE_UNITS,
    STAGE_C_SERVICE_UNITS,
)
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C14-PRODUCTION-LOCK-ONLY"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c14-production-lock."
EXPECTED_CHECKS = (
    "root-scope",
    "protocol-conformance",
    "pre-lock-host-contract",
    "pre-lock-boundary",
    "production-lock-acquired",
    "lock-file-contract",
    "lock-contention",
    "held-lock-observation",
    "read-only-host-observations",
    "blocked-operation-boundary",
    "production-lock-released",
    "exact-lock-cleanup",
    "evidence-integrity",
    "activation-interface",
)
TRANSACTION_ROOT = Path(AUTHORITATIVE_TRANSACTION_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage C14 production-lock-only rehearsal. No production "
            "transaction or audio mutation operation is implemented."
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


def append_event(path: Path, order: int, event: str, detail: str) -> None:
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"{order}\t{time.monotonic_ns()}\t"
        + f"{datetime.now().astimezone().isoformat(timespec='microseconds')}\t"
        + f"{event}\t{detail}\n",
        encoding="utf-8",
    )


def require_pass(result: AdapterResult[Any], operation: AdapterOperation) -> Any:
    if result.operation is not operation:
        raise SystemExit(
            f"adapter returned {result.operation.value} for {operation.value}"
        )
    if result.status is not AdapterStatus.PASS or result.payload is None:
        raise SystemExit(f"{operation.value} failed: {result.detail}")
    return result.payload


def require_receipt(result: AdapterResult[None], operation: AdapterOperation) -> None:
    if result.operation is not operation or result.status is not AdapterStatus.PASS:
        raise SystemExit(f"{operation.value} failed: {result.detail}")
    if result.payload is not None:
        raise SystemExit(f"{operation.value} unexpectedly returned a payload")


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
                f"application service boundary changed: {unit.value} "
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
                f"unexpected existing Stage C service: {unit.value} "
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
                f"blocked identity mismatch: expected {operation.value}, "
                f"found {exc.operation.value}"
            ) from exc
        rows.append((operation.value, "blocked"))
        return
    raise SystemExit(f"operation unexpectedly became executable: {operation.value}")


def prove_blocked_operations(
    adapter: ProductionLockRehearsalAdapter,
    *,
    transaction: TransactionIdentity,
    services: ServiceSnapshot,
    mixer,
) -> list[tuple[str, str]]:
    package = PackageFingerprint("0" * 64)
    snapshot = SnapshotIdentity("stage-c14-non-authoritative-snapshot")
    rows: list[tuple[str, str]] = []

    _expect_blocked(
        rows,
        AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
        lambda: adapter.create_authoritative_transaction(TransactionAction.INSTALL, package),
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
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_ALSA, lambda: adapter.validate_candidate_alsa(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, lambda: adapter.validate_candidate_sudoers(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_UNITS, lambda: adapter.validate_candidate_units(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, lambda: adapter.validate_candidate_camilladsp(transaction))
    _expect_blocked(
        rows,
        AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
        lambda: adapter.stop_captured_application_services(transaction, services),
    )
    _expect_blocked(rows, AdapterOperation.VERIFY_DAC_RELEASED, lambda: adapter.verify_dac_released(transaction))
    _expect_blocked(rows, AdapterOperation.INSTALL_MANAGED_FILES, lambda: adapter.install_managed_files(transaction))
    _expect_blocked(rows, AdapterOperation.RELOAD_SYSTEMD, lambda: adapter.reload_systemd(transaction))
    _expect_blocked(rows, AdapterOperation.SELECT_SPLIT_BUS_ROUTE, lambda: adapter.select_split_bus_route(transaction))
    _expect_blocked(rows, AdapterOperation.START_MANAGED_STAGE_C_SERVICES, lambda: adapter.start_managed_stage_c_services(transaction))
    _expect_blocked(rows, AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES, lambda: adapter.stop_managed_stage_c_services(transaction))
    _expect_blocked(rows, AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, lambda: adapter.verify_split_bus_health(transaction))
    _expect_blocked(rows, AdapterOperation.RUN_FINITE_MUSIC_PROBE, lambda: adapter.run_finite_music_probe(transaction))
    _expect_blocked(rows, AdapterOperation.RUN_FINITE_ALARM_PROBE, lambda: adapter.run_finite_alarm_probe(transaction))
    _expect_blocked(
        rows,
        AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
        lambda: adapter.restore_captured_application_services(transaction, services),
    )
    _expect_blocked(rows, AdapterOperation.VERIFY_DASHBOARD_HEALTH, lambda: adapter.verify_dashboard_health(transaction))
    _expect_blocked(rows, AdapterOperation.WRITE_COMMIT_MANIFEST, lambda: adapter.write_commit_manifest(transaction))
    _expect_blocked(rows, AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE, lambda: adapter.select_direct_failback_route(transaction))
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
            f"blocked-operation coverage changed: expected={len(expected)} "
            f"observed={len(rows)}"
        )
    return rows


def write_blocked_operations(output: Path, rows: list[tuple[str, str]]) -> None:
    output.write_text(
        "operation\tstate\n"
        + "".join(f"{operation}\t{state}\n" for operation, state in rows),
        encoding="utf-8",
    )


def write_lease(output: Path, lease, evidence) -> None:
    output.write_text(
        "item\tvalue\n"
        f"lease_id\t{lease.lease_id}\n"
        f"path\t{lease.path}\n"
        f"held\t{str(lease.held).lower()}\n"
        f"inode\t{evidence.inode}\n"
        f"mode\t{evidence.mode:o}\n"
        f"owner_uid\t{evidence.owner_uid}\n"
        f"owner_gid\t{evidence.owner_gid}\n"
        f"contention_proved\t{str(evidence.contention_proved).lower()}\n"
        "production_authoritative\tfalse\n"
        "transaction_created\tfalse\n",
        encoding="utf-8",
    )


def write_report(output: Path, *, evidence_root: Path, lease_id: str, inode: int) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C14 production-lock-only rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Lease identity: {lease_id}
Lock inode: {inode}
Typed operations: {len(PERMITTED_OPERATIONS)}
Blocked operations: {len(AdapterOperation) - len(PERMITTED_OPERATIONS)}

Proved:
- the exact production route-lock path began absent
- a root-owned mode-0600 regular lock file was created exclusively
- a non-blocking exclusive flock was acquired
- an independent descriptor could not acquire the held lock
- six typed real-host observations remained exact while the lock was held
- all remaining adapter operations stayed blocked with exact identities
- normal typed release unlinked the exact original inode while held
- the production lock path was absent after unlock and close
- no authoritative transaction root was created

Not proved:
- authoritative transaction creation
- activation-time filesystem snapshot
- package staging or validation
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
            f"production-lock rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, _invoking_user = invoking_identity()
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)

    try:
        transaction_root_pre = TRANSACTION_ROOT.lstat()
    except FileNotFoundError:
        transaction_root_pre = None
    if transaction_root_pre is not None:
        raise SystemExit(
            f"authoritative transaction root unexpectedly exists: {TRANSACTION_ROOT}"
        )

    os.chown(evidence_root, 0, 0)
    evidence_root.chmod(0o700)
    completed = False
    try:
        results = evidence_root / "results.tsv"
        results.write_text("check\tresult\tdetail\n", encoding="utf-8")
        events = evidence_root / "lock-events.tsv"
        events.write_text(
            "order\tmonotonic_ns\twall_time\tevent\tdetail\n",
            encoding="utf-8",
        )
        append_result(results, "root-scope", f"root writes constrained to {evidence_root} and the exact temporary lock path")

        with ProductionLockRehearsalAdapter() as adapter:
            if not isinstance(adapter, ProductionAdapter):
                raise SystemExit("Stage C14 adapter does not conform to ProductionAdapter")
            append_result(results, "protocol-conformance", "adapter exposes exactly eight typed operations")

            host_pre = adapter.inspect_host_contract()
            require_pass(host_pre, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(results, "pre-lock-host-contract", "stable aarch64 route and fixed host contract verified")

            lock_pre = adapter.inspect_production_lock()
            pre = require_pass(lock_pre, AdapterOperation.INSPECT_PRODUCTION_LOCK)
            if pre.exists or pre.held_by_caller:
                raise SystemExit("production lock must begin absent")
            append_result(results, "pre-lock-boundary", f"{pre.path} absent and unopened")
            append_event(events, 10, "pre-lock-boundary", "fixed path absent")

            acquire_result = adapter.acquire_production_lock()
            lease = require_pass(acquire_result, AdapterOperation.ACQUIRE_PRODUCTION_LOCK)
            evidence = adapter.held_lock_evidence
            if evidence is None or not adapter.lock_held:
                raise SystemExit("typed acquisition returned without held lock evidence")
            append_result(results, "production-lock-acquired", f"adapter-generated lease {lease.lease_id}")
            append_event(events, 20, "production-lock-acquired", f"lease={lease.lease_id} inode={evidence.inode}")

            write_lease(evidence_root / "lease.tsv", lease, evidence)
            append_result(results, "lock-file-contract", f"inode {evidence.inode}, mode 0600, owner 0:0")
            if not evidence.contention_proved:
                raise SystemExit("production lock contention was not proved")
            append_result(results, "lock-contention", "independent descriptor failed closed with the lock held")

            held_result = adapter.inspect_production_lock()
            held = require_pass(held_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
            if (
                not held.exists
                or not held.held_by_caller
                or held.mode != 0o600
                or held.owner_uid != 0
                or held.owner_gid != 0
            ):
                raise SystemExit("held production-lock observation is not exact")
            append_result(results, "held-lock-observation", "typed observation reports exact caller-held root:root mode-0600 lock")

            transaction = adapter.observation_transaction
            service_result = adapter.capture_service_state(transaction)
            services = require_pass(service_result, AdapterOperation.CAPTURE_SERVICE_STATE)
            validate_service_snapshot(services)
            mixer_result = adapter.capture_mixer_state(transaction)
            mixer = require_pass(mixer_result, AdapterOperation.CAPTURE_MIXER_STATE)
            loopback_result = adapter.capture_loopback_state(transaction)
            loopback = require_pass(loopback_result, AdapterOperation.CAPTURE_LOOPBACK_STATE)
            dac_result = adapter.capture_dac_state(transaction)
            dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
            if not loopback.loaded or dac.released or not dac.owners:
                raise SystemExit("held-lock read-only host observations changed")
            append_result(results, "read-only-host-observations", "service, mixer, loopback and DAC snapshots remained exact while locked")

            typed_results = (
                host_pre,
                lock_pre,
                acquire_result,
                held_result,
                service_result,
                mixer_result,
                loopback_result,
                dac_result,
            )
            (evidence_root / "typed-observations.json").write_text(
                json.dumps(
                    {
                        "observation_identity": transaction.value,
                        "lease_identity": lease.lease_id,
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
            write_blocked_operations(evidence_root / "blocked-operations.tsv", blocked)
            append_result(results, "blocked-operation-boundary", f"all {len(blocked)} transaction and audio operations refused exactly")

            release_result = adapter.release_production_lock()
            require_receipt(release_result, AdapterOperation.RELEASE_PRODUCTION_LOCK)
            append_result(results, "production-lock-released", "normal typed release unlinked, unlocked and closed the exact inode")
            append_event(events, 30, "production-lock-released", f"lease={lease.lease_id} inode={evidence.inode}")

            post_result = adapter.inspect_production_lock()
            post = require_pass(post_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
            if post.exists or post.held_by_caller or adapter.lock_held:
                raise SystemExit("production lock remained after typed release")
            try:
                TRANSACTION_ROOT.lstat()
            except FileNotFoundError:
                pass
            else:
                raise SystemExit("authoritative transaction root appeared during Stage C14")
            append_result(results, "exact-lock-cleanup", "lock path absent and no transaction root created")

            write_report(
                evidence_root / "report.txt",
                evidence_root=evidence_root,
                lease_id=lease.lease_id,
                inode=evidence.inode,
            )

        write_evidence_manifest(evidence_root)
        append_result(results, "evidence-integrity", "complete checksummed evidence tree contains no symlink or special object")
        append_result(results, "activation-interface", "absent; no production transaction, install, activation or rollback action")
        write_evidence_manifest(evidence_root)

        observed_checks = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed_checks != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C14 result order: {observed_checks}")
        completed = True
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C14 production-lock-only rehearsal did not complete")

    print(
        f"""
A Clockwork Plex Stage C14 production-lock-only rehearsal passed.

  Directory:          {evidence_root}
  Results:            {evidence_root / 'results.tsv'}
  Lease:              {evidence_root / 'lease.tsv'}
  Typed observations: {evidence_root / 'typed-observations.json'}
  Blocked operations: {evidence_root / 'blocked-operations.tsv'}
  Lock events:        {evidence_root / 'lock-events.tsv'}
  Evidence manifest:  {evidence_root / 'evidence-manifest.tsv'}
  Report:             {evidence_root / 'report.txt'}

The temporary production lock was released and removed. No transaction or
audio-appliance state was created or changed. Persistent Stage C activation
remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())