#!/usr/bin/python3
from __future__ import annotations

"""Stage C15 root-owned authoritative snapshot and pre-mutation abort rehearsal."""

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

from .authoritative_snapshot_rehearsal_adapter import (
    PERMITTED_OPERATIONS,
    AbortTransactionResult,
    AuthoritativeSnapshotRehearsalAdapter,
    package_tree_fingerprint,
)
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    AuthoritativeTransaction,
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
from .production_lock_rehearsal import EXPECTED_CHECKS as STAGE_C14_CHECKS
from .production_plan import _validate_evidence_manifest
from .read_only_host_adapter import APPLICATION_SERVICE_UNITS, STAGE_C_SERVICE_UNITS
from .sandbox_transaction import _assert_regular_tree, _read_tsv, tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c15-authoritative-snapshot."
EXPECTED_CHECKS = (
    "root-scope",
    "input-replay",
    "protocol-conformance",
    "pre-lock-host-contract",
    "pre-lock-boundary",
    "production-lock-acquired",
    "transaction-parent-boundary",
    "authoritative-transaction-created",
    "transaction-identity-binding",
    "filesystem-snapshot",
    "service-snapshot",
    "mixer-snapshot",
    "loopback-snapshot",
    "dac-snapshot",
    "snapshot-integrity",
    "blocked-operation-boundary",
    "pre-mutation-abort",
    "transaction-evidence-copy",
    "exact-transaction-cleanup",
    "production-lock-released",
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage C15 authoritative snapshot transaction rehearsal. "
            "The transaction is aborted and removed before any mutation."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c14-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def _validate_owned_root(
    path: Path,
    *,
    prefix: str,
    invoking_uid: int,
    label: str,
) -> Path:
    raw = path.expanduser()
    if not raw.is_absolute():
        raise SystemExit(f"{label} must be an absolute path")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} does not exist: {raw}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"{label} must be a real directory")
    resolved = raw.resolve()
    if resolved.parent != Path("/var/tmp") or not resolved.name.startswith(prefix):
        raise SystemExit(f"unexpected {label} path: {resolved}")
    if info.st_uid != invoking_uid:
        raise SystemExit(f"{label} must remain owned by the invoking user")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit(f"{label} must retain mode 0700")
    _assert_regular_tree(resolved, label)
    return resolved


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C15 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C15 evidence root must be empty")
    return root


def validate_stage_c14(root: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        root,
        prefix="a-clockwork-plex-stage-c14-production-lock.",
        invoking_uid=invoking_uid,
        label="Stage C14 evidence",
    )
    _validate_evidence_manifest(root, "Stage C14")
    results = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in results) != STAGE_C14_CHECKS:
        raise SystemExit("Stage C14 evidence does not contain the exact fourteen checks")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C14 evidence contains a non-PASS result")
    lease_rows = _read_tsv(root / "lease.tsv")
    lease = {row.get("item", ""): row.get("value", "") for row in lease_rows}
    expected = {
        "path": "/run/lock/a-clockwork-plex-audio-route.lock",
        "held": "true",
        "mode": "600",
        "owner_uid": "0",
        "owner_gid": "0",
        "contention_proved": "true",
        "production_authoritative": "false",
        "transaction_created": "false",
    }
    for key, value in expected.items():
        if lease.get(key) != value:
            raise SystemExit(f"Stage C14 lease contract changed: {key}")
    blocked = _read_tsv(root / "blocked-operations.tsv")
    if len(blocked) != 25 or any(row.get("state") != "blocked" for row in blocked):
        raise SystemExit("Stage C14 blocked-operation evidence changed")
    report = (root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "the production lock path was absent after unlock and close",
        "no authoritative transaction root was created",
        "Persistent Stage C activation remains blocked.",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C14 report contract is missing: {marker}")
    return root


def append_result(path: Path, check: str, detail: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def append_event(path: Path, order: int, event: str, detail: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{order}\t{time.monotonic_ns()}\t"
            f"{datetime.now().astimezone().isoformat(timespec='microseconds')}\t"
            f"{event}\t{detail}\n"
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


def require_abort(result: AbortTransactionResult):
    if result.status is not AdapterStatus.PASS or result.payload is None:
        raise SystemExit(f"pre-mutation abort failed: {result.detail}")
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


def validate_service_snapshot(snapshot: ServiceSnapshot) -> None:
    by_unit = {service.unit: service for service in snapshot.services}
    for unit in APPLICATION_SERVICE_UNITS:
        state = by_unit[unit]
        if (
            state.load is not ServiceLoadState.LOADED
            or state.active is not ServiceActiveState.ACTIVE
            or state.enabled is not ServiceEnableState.ENABLED
        ):
            raise SystemExit(f"application service boundary changed: {unit.value}")
    for unit in STAGE_C_SERVICE_UNITS:
        state = by_unit[unit]
        if (
            state.load is not ServiceLoadState.NOT_FOUND
            or state.enabled is not ServiceEnableState.NOT_FOUND
        ):
            raise SystemExit(f"unexpected existing Stage C service: {unit.value}")


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
    adapter: AuthoritativeSnapshotRehearsalAdapter,
    *,
    transaction: TransactionIdentity,
    package: PackageFingerprint,
    services: ServiceSnapshot,
    mixer,
    snapshot: SnapshotIdentity,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    _expect_blocked(rows, AdapterOperation.STAGE_CANDIDATE_FILES, lambda: adapter.stage_candidate_files(transaction, package))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_ALSA, lambda: adapter.validate_candidate_alsa(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, lambda: adapter.validate_candidate_sudoers(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_UNITS, lambda: adapter.validate_candidate_units(transaction))
    _expect_blocked(rows, AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, lambda: adapter.validate_candidate_camilladsp(transaction))
    _expect_blocked(rows, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES, lambda: adapter.stop_captured_application_services(transaction, services))
    _expect_blocked(rows, AdapterOperation.VERIFY_DAC_RELEASED, lambda: adapter.verify_dac_released(transaction))
    _expect_blocked(rows, AdapterOperation.INSTALL_MANAGED_FILES, lambda: adapter.install_managed_files(transaction))
    _expect_blocked(rows, AdapterOperation.RELOAD_SYSTEMD, lambda: adapter.reload_systemd(transaction))
    _expect_blocked(rows, AdapterOperation.SELECT_SPLIT_BUS_ROUTE, lambda: adapter.select_split_bus_route(transaction))
    _expect_blocked(rows, AdapterOperation.START_MANAGED_STAGE_C_SERVICES, lambda: adapter.start_managed_stage_c_services(transaction))
    _expect_blocked(rows, AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES, lambda: adapter.stop_managed_stage_c_services(transaction))
    _expect_blocked(rows, AdapterOperation.VERIFY_SPLIT_BUS_HEALTH, lambda: adapter.verify_split_bus_health(transaction))
    _expect_blocked(rows, AdapterOperation.RUN_FINITE_MUSIC_PROBE, lambda: adapter.run_finite_music_probe(transaction))
    _expect_blocked(rows, AdapterOperation.RUN_FINITE_ALARM_PROBE, lambda: adapter.run_finite_alarm_probe(transaction))
    _expect_blocked(rows, AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES, lambda: adapter.restore_captured_application_services(transaction, services))
    _expect_blocked(rows, AdapterOperation.VERIFY_DASHBOARD_HEALTH, lambda: adapter.verify_dashboard_health(transaction))
    _expect_blocked(rows, AdapterOperation.WRITE_COMMIT_MANIFEST, lambda: adapter.write_commit_manifest(transaction))
    _expect_blocked(rows, AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE, lambda: adapter.select_direct_failback_route(transaction))
    _expect_blocked(rows, AdapterOperation.RESTORE_EXACT_SNAPSHOT, lambda: adapter.restore_exact_snapshot(transaction, snapshot))
    _expect_blocked(rows, AdapterOperation.RESTORE_MIXER_STATE, lambda: adapter.restore_mixer_state(transaction, mixer))
    _expect_blocked(rows, AdapterOperation.RESTORE_SERVICE_STATE, lambda: adapter.restore_service_state(transaction, services))
    _expect_blocked(rows, AdapterOperation.VERIFY_EXACT_ROLLBACK, lambda: adapter.verify_exact_rollback(transaction, snapshot))
    expected = set(AdapterOperation).difference(PERMITTED_OPERATIONS)
    observed = {AdapterOperation(operation) for operation, state in rows if state == "blocked"}
    if observed != expected or len(rows) != len(expected):
        raise SystemExit(
            f"blocked-operation coverage changed: expected={len(expected)} observed={len(rows)}"
        )
    return rows


def write_blocked_operations(output: Path, rows: list[tuple[str, str]]) -> None:
    output.write_text(
        "operation\tstate\n"
        + "".join(f"{operation}\t{state}\n" for operation, state in rows),
        encoding="utf-8",
    )


def write_identity(
    output: Path,
    *,
    transaction: AuthoritativeTransaction,
    lease_id: str,
    invoking_user: str,
) -> None:
    output.write_text(
        "item\tvalue\n"
        f"transaction\t{transaction.transaction.value}\n"
        f"snapshot\t{transaction.snapshot.value}\n"
        f"action\t{transaction.action.value}\n"
        f"package_sha256\t{transaction.package.sha256}\n"
        f"lease_id\t{lease_id}\n"
        f"host\t{platform.node()}\n"
        f"architecture\t{platform.machine()}\n"
        f"invoking_user\t{invoking_user}\n"
        "caller_supplied\tfalse\n"
        "production_authoritative_during_capture\ttrue\n"
        "committed\tfalse\n"
        "reusable_after_abort\tfalse\n",
        encoding="utf-8",
    )


def write_parent_states(output: Path, states) -> None:
    output.write_text(
        "path\texists\tdevice\tinode\tmode\tuid\tgid\n"
        + "".join(
            f"{state.path}\t{str(state.exists).lower()}\t"
            f"{state.device if state.device is not None else '-'}\t"
            f"{state.inode if state.inode is not None else '-'}\t"
            f"{state.mode:o}" if state.mode is not None else f"{state.path}\t{str(state.exists).lower()}\t-\t-\t-"
            for state in ()
        ),
        encoding="utf-8",
    )
    rows = ["path\texists\tdevice\tinode\tmode\tuid\tgid"]
    for state in states:
        rows.append(
            "\t".join(
                (
                    state.path,
                    str(state.exists).lower(),
                    str(state.device) if state.device is not None else "-",
                    str(state.inode) if state.inode is not None else "-",
                    f"{state.mode:o}" if state.mode is not None else "-",
                    str(state.uid) if state.uid is not None else "-",
                    str(state.gid) if state.gid is not None else "-",
                )
            )
        )
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_report(
    output: Path,
    *,
    evidence_root: Path,
    transaction: AuthoritativeTransaction,
    blocked_count: int,
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C15 authoritative snapshot transaction rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Core typed operations: {len(PERMITTED_OPERATIONS)}
Blocked core operations: {blocked_count}
Final transaction state: aborted-before-mutation and removed

Proved:
- exact Stage C1 package and physical Stage C14 evidence replay
- real production lock held before transaction identity generation
- fresh adapter-generated install transaction and snapshot identities
- exact root-owned mode-0700 transaction directory under the fixed production root
- exact filesystem, service, mixer, loopback and DAC snapshot while locked
- all package staging and audio mutation operations remained blocked
- lock release refused until explicit typed pre-mutation abort completed
- complete transaction copied as non-authoritative review evidence
- exact transaction and rehearsal-created parent cleanup while still locked
- production lock released only after transaction cleanup

Not proved:
- candidate staging or validation
- service stop or DAC release
- managed-file installation or daemon reload
- split-bus route or managed-service startup
- finite music or alarm probes
- dashboard health or installation commit
- post-mutation exact rollback
- runtime failback, explicit uninstall or reboot persistence

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Stage C15 rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_owned_root(
        args.package_root,
        prefix="a-clockwork-plex-stage-c1-review-",
        invoking_uid=invoking_uid,
        label="Stage C1 package",
    )
    stage_c14_root = validate_stage_c14(args.stage_c14_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    input_fingerprints = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c14": tree_fingerprint(stage_c14_root),
    }
    package = package_tree_fingerprint(package_root)

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
        append_result(results, "root-scope", f"root writes constrained to {evidence_root}, the fixed lock and disposable transaction")
        append_result(results, "input-replay", "Stage C1 package and physical Stage C14 evidence replayed")

        with AuthoritativeSnapshotRehearsalAdapter(package_root, invoking_user) as adapter:
            if not isinstance(adapter, ProductionAdapter):
                raise SystemExit("Stage C15 adapter does not conform to ProductionAdapter")
            append_result(results, "protocol-conformance", "adapter exposes ten core operations plus explicit typed pre-mutation abort")

            host_result = adapter.inspect_host_contract()
            require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(results, "pre-lock-host-contract", "stable aarch64 route and fixed host contract verified")

            lock_pre_result = adapter.inspect_production_lock()
            lock_pre = require_pass(lock_pre_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
            if lock_pre.exists or lock_pre.held_by_caller:
                raise SystemExit("production lock must begin absent")
            append_result(results, "pre-lock-boundary", f"{lock_pre.path} absent and unopened")
            append_event(events, 10, "pre-lock-boundary", "fixed lock path absent")

            acquire_result = adapter.acquire_production_lock()
            lease = require_pass(acquire_result, AdapterOperation.ACQUIRE_PRODUCTION_LOCK)
            append_result(results, "production-lock-acquired", f"adapter-generated lease {lease.lease_id}")
            append_event(events, 20, "production-lock-acquired", f"lease={lease.lease_id}")

            create_result = adapter.create_authoritative_transaction(
                TransactionAction.INSTALL,
                package,
            )
            transaction = require_pass(
                create_result,
                AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            )
            write_parent_states(evidence_root / "parent-state.tsv", adapter.parent_states)
            append_result(results, "transaction-parent-boundary", "pre-existing parent metadata captured; missing parents created with fixed modes")
            append_result(results, "authoritative-transaction-created", f"fresh transaction {transaction.transaction.value}")
            append_event(events, 30, "authoritative-transaction-created", transaction.transaction.value)
            if (
                adapter.authoritative_transaction != transaction
                or transaction.package != package
                or transaction.action is not TransactionAction.INSTALL
            ):
                raise SystemExit("authoritative transaction identity binding failed")
            append_result(results, "transaction-identity-binding", "transaction, snapshot, package, action and held lease are adapter-bound")
            write_identity(
                evidence_root / "identity.tsv",
                transaction=transaction,
                lease_id=lease.lease_id,
                invoking_user=invoking_user,
            )

            filesystem_result = adapter.capture_filesystem_state(transaction.transaction)
            filesystem = require_pass(filesystem_result, AdapterOperation.CAPTURE_FILESYSTEM_STATE)
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot identity is not authoritative")
            append_result(results, "filesystem-snapshot", "current ALSA and all managed file/directory states captured exactly")

            service_result = adapter.capture_service_state(transaction.transaction)
            services = require_pass(service_result, AdapterOperation.CAPTURE_SERVICE_STATE)
            validate_service_snapshot(services)
            append_result(results, "service-snapshot", "exact six-service state captured")

            mixer_result = adapter.capture_mixer_state(transaction.transaction)
            mixer = require_pass(mixer_result, AdapterOperation.CAPTURE_MIXER_STATE)
            append_result(results, "mixer-snapshot", "exact four-control mixer state captured")

            loopback_result = adapter.capture_loopback_state(transaction.transaction)
            loopback = require_pass(loopback_result, AdapterOperation.CAPTURE_LOOPBACK_STATE)
            if not loopback.loaded:
                raise SystemExit("authoritative loopback snapshot is not loaded")
            append_result(results, "loopback-snapshot", "exact snd_aloop state captured")

            dac_result = adapter.capture_dac_state(transaction.transaction)
            dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
            if dac.released or not dac.owners:
                raise SystemExit("authoritative DAC snapshot lacks the live owner")
            append_result(results, "dac-snapshot", f"exact DAC format and {len(dac.owners)} structured owner(s) captured")
            append_result(results, "snapshot-integrity", "all five authoritative snapshot domains completed under one identity")

            typed_results = (
                host_result,
                lock_pre_result,
                acquire_result,
                create_result,
                filesystem_result,
                service_result,
                mixer_result,
                loopback_result,
                dac_result,
            )
            (evidence_root / "typed-observations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "production_authoritative_during_capture": True,
                        "committed": False,
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
                transaction=transaction.transaction,
                package=package,
                services=services,
                mixer=mixer,
                snapshot=transaction.snapshot,
            )
            write_blocked_operations(evidence_root / "blocked-operations.tsv", blocked)
            append_result(results, "blocked-operation-boundary", f"all {len(blocked)} staging and mutation operations refused exactly")

            premature_release = adapter.release_production_lock()
            if premature_release.status is not AdapterStatus.FAIL:
                raise SystemExit("production lock release did not refuse the open transaction")
            append_result(results, "pre-mutation-abort", "release refused until the explicit uncommitted transaction abort")

            evidence_copy = evidence_root / "transaction-rehearsal-copy"
            abort_result = adapter.abort_uncommitted_transaction(evidence_copy)
            abort = require_abort(abort_result)
            append_result(results, "transaction-evidence-copy", f"complete non-authoritative copy retained at {abort.evidence_copy}")
            append_result(results, "exact-transaction-cleanup", "transaction path absent and all pre-existing parent metadata restored")
            append_event(events, 40, "transaction-aborted", transaction.transaction.value)

            release_result = adapter.release_production_lock()
            require_receipt(release_result, AdapterOperation.RELEASE_PRODUCTION_LOCK)
            append_result(results, "production-lock-released", "exact production lock removed only after transaction cleanup")
            append_event(events, 50, "production-lock-released", lease.lease_id)

            write_report(
                evidence_root / "report.txt",
                evidence_root=evidence_root,
                transaction=transaction,
                blocked_count=len(blocked),
            )

        for label, root in (("stage-c1", package_root), ("stage-c14", stage_c14_root)):
            if tree_fingerprint(root) != input_fingerprints[label]:
                raise SystemExit(f"{label} input changed during Stage C15")
        append_result(results, "input-integrity", "Stage C1 and Stage C14 input trees remained unchanged")

        write_evidence_manifest(evidence_root)
        append_result(results, "evidence-integrity", "complete checksummed evidence tree contains no symlink or special object")
        append_result(results, "activation-interface", "absent; transaction aborted before staging or any audio mutation")
        write_evidence_manifest(evidence_root)

        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C15 result order: {observed}")
        completed = True
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C15 authoritative snapshot rehearsal did not complete")

    print(
        f"""
A Clockwork Plex Stage C15 authoritative snapshot rehearsal passed.

  Directory:          {evidence_root}
  Results:            {evidence_root / 'results.tsv'}
  Identity:           {evidence_root / 'identity.tsv'}
  Parent state:       {evidence_root / 'parent-state.tsv'}
  Typed observations: {evidence_root / 'typed-observations.json'}
  Blocked operations: {evidence_root / 'blocked-operations.tsv'}
  Transaction copy:   {evidence_root / 'transaction-rehearsal-copy'}
  Lock events:        {evidence_root / 'lock-events.tsv'}
  Evidence manifest:  {evidence_root / 'evidence-manifest.tsv'}
  Report:             {evidence_root / 'report.txt'}

The authoritative rehearsal transaction was aborted before mutation and removed.
The production lock was released. Persistent Stage C activation remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
