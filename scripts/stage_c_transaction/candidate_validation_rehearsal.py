#!/usr/bin/python3
from __future__ import annotations

"""Stage C16 root-owned candidate staging and validation rehearsal."""

import argparse
import json
import os
import platform
import stat
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .authoritative_snapshot_rehearsal import (
    _validate_owned_root,
    append_event,
    append_result,
    jsonable,
    require_pass,
    require_receipt,
    validate_service_snapshot,
    write_parent_states,
)
from .authoritative_snapshot_rehearsal_adapter import package_tree_fingerprint
from .candidate_validation_rehearsal_adapter import (
    BLOCKED_V2_COUNT,
    PERMITTED_V1_OPERATIONS,
    CandidateValidationRehearsalAdapter,
)
from .package_review import EXPECTED_PACKAGE_FILES, parse_manifest, sha256
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ProductionAdapterBlocked,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import (
    ProductionAdapterV2,
    TransactionLifecycleOperation,
)
from .production_plan import _validate_evidence_manifest
from .sandbox_transaction import _assert_regular_tree, _read_tsv, tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest
from .authoritative_snapshot_rehearsal import EXPECTED_CHECKS as STAGE_C15_CHECKS


REQUIRED_CONFIRMATION = "STAGE-C16-CANDIDATE-STAGE-VALIDATE-ABORT"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c16-candidate-validation."
EXPECTED_CHECKS = (
    "root-scope",
    "input-replay",
    "protocol-conformance",
    "pre-lock-host-contract",
    "pre-lock-boundary",
    "production-lock-acquired",
    "authoritative-transaction-created",
    "transaction-identity-binding",
    "filesystem-snapshot",
    "service-snapshot",
    "mixer-snapshot",
    "loopback-snapshot",
    "dac-snapshot",
    "snapshot-integrity",
    "candidate-staging",
    "candidate-manifest-binding",
    "candidate-alsa-validation",
    "candidate-sudoers-validation",
    "candidate-unit-validation",
    "candidate-camilladsp-validation",
    "blocked-operation-boundary",
    "pre-mutation-boundary",
    "candidate-evidence-copy",
    "transaction-abort-v2",
    "exact-transaction-cleanup",
    "production-lock-released",
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage C16 transaction-private candidate staging and validation, "
            "then abort before any service or audio mutation."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c15-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C16 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C16 evidence root must be empty")
    return root


def validate_stage_c15(root: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        root,
        prefix="a-clockwork-plex-stage-c15-authoritative-snapshot.",
        invoking_uid=invoking_uid,
        label="Stage C15 evidence",
    )
    _validate_evidence_manifest(root, "Stage C15")
    rows = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in rows) != STAGE_C15_CHECKS:
        raise SystemExit("Stage C15 evidence does not contain the exact twenty-three checks")
    if any(row.get("result") != "PASS" for row in rows):
        raise SystemExit("Stage C15 evidence contains a non-PASS result")
    blocked = _read_tsv(root / "blocked-operations.tsv")
    if len(blocked) != 23 or any(row.get("state") != "blocked" for row in blocked):
        raise SystemExit("Stage C15 blocked-operation evidence changed")
    identity = {row.get("item", ""): row.get("value", "") for row in _read_tsv(root / "identity.tsv")}
    if identity.get("committed") != "false" or identity.get("reusable_after_abort") != "false":
        raise SystemExit("Stage C15 transaction identity is not a disposable aborted snapshot")
    if not (root / "transaction-rehearsal-copy").is_dir():
        raise SystemExit("Stage C15 transaction review copy is missing")
    report = (root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "Final transaction state: aborted-before-mutation and removed",
        "candidate staging or validation",
        "Persistent Stage C activation remains blocked.",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C15 report contract is missing: {marker}")
    return root


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
                f"blocked identity mismatch: expected {operation.value}, found {exc.operation.value}"
            ) from exc
        rows.append((operation.value, "blocked"))
        return
    raise SystemExit(f"operation unexpectedly became executable: {operation.value}")


def prove_blocked_operations(
    adapter: CandidateValidationRehearsalAdapter,
    *,
    transaction: TransactionIdentity,
    services: ServiceSnapshot,
    mixer,
    snapshot: SnapshotIdentity,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
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
    expected = set(AdapterOperation).difference(PERMITTED_V1_OPERATIONS)
    observed = {AdapterOperation(operation) for operation, state in rows if state == "blocked"}
    if observed != expected or len(rows) != BLOCKED_V2_COUNT:
        raise SystemExit(
            f"blocked-operation coverage changed: expected={BLOCKED_V2_COUNT} observed={len(rows)}"
        )
    return rows


def write_blocked_operations(output: Path, rows: list[tuple[str, str]]) -> None:
    output.write_text(
        "operation\tstate\n"
        + "".join(f"{operation}\t{state}\n" for operation, state in rows),
        encoding="utf-8",
    )


def validate_candidate_manifest(package_root: Path, candidate_root: Path) -> None:
    entries = parse_manifest(package_root)
    files = [entry for entry in entries if entry.kind == "file"]
    if len(files) != EXPECTED_PACKAGE_FILES:
        raise SystemExit("Stage C16 manifest file count changed")
    for entry in entries:
        candidate = candidate_root / entry.destination.lstrip("/")
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"staged candidate is a symlink: {entry.destination}")
        if stat.S_IMODE(info.st_mode) != int(entry.mode, 8):
            raise SystemExit(f"staged mode differs from manifest: {entry.destination}")
        if info.st_uid != 0 or info.st_gid != 0:
            raise SystemExit(f"staged owner differs from root:root: {entry.destination}")
        if entry.kind == "directory":
            if not stat.S_ISDIR(info.st_mode):
                raise SystemExit(f"staged manifest directory is not a directory: {entry.destination}")
        elif not stat.S_ISREG(info.st_mode) or sha256(candidate) != entry.digest:
            raise SystemExit(f"staged file differs from manifest: {entry.destination}")


def write_identity(output: Path, transaction, lease_id: str, invoking_user: str) -> None:
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
        "candidate_production_authoritative\tfalse\n"
        "mutation_started\tfalse\n"
        "committed\tfalse\n"
        "reusable_after_abort\tfalse\n",
        encoding="utf-8",
    )


def write_report(output: Path, evidence_root: Path, transaction, blocked_count: int) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C16 candidate staging and validation rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
V2 permitted operations: 16
V2 blocked operations: {blocked_count}
Final transaction state: aborted-before-mutation and removed

Proved:
- exact Stage C1 package and physical Stage C15 evidence replay
- real production lock and fresh authoritative five-domain snapshot
- twelve manifest files staged only below the transaction-private candidate root
- staged candidate mode, owner and digest binding
- isolated parsing of split and direct ALSA candidates without opening a PCM
- staged sudoers validation with visudo
- staged unit, ordering, approval-gate and inert-helper validation
- digest-pinned CamillaDSP configuration validation without opening audio
- every service, installation, route, audio, commit and recovery operation remained blocked
- candidate and validation evidence retained non-authoritatively
- v2 explicit abort removed candidate and transaction before lock release

Not proved:
- service stop or DAC release
- production installation or systemd daemon reload
- active route selection or managed service startup
- finite music or alarm probes
- commit, post-mutation rollback, runtime failback, uninstall or reboot persistence

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(f"Stage C16 rehearsal requires --confirm {REQUIRED_CONFIRMATION}")
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_owned_root(
        args.package_root,
        prefix="a-clockwork-plex-stage-c1-review-",
        invoking_uid=invoking_uid,
        label="Stage C1 package",
    )
    stage_c15_root = validate_stage_c15(args.stage_c15_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    inputs = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c15": tree_fingerprint(stage_c15_root),
    }
    package = package_tree_fingerprint(package_root)

    os.chown(evidence_root, 0, 0)
    evidence_root.chmod(0o700)
    completed = False
    try:
        results = evidence_root / "results.tsv"
        results.write_text("check\tresult\tdetail\n", encoding="utf-8")
        events = evidence_root / "lock-events.tsv"
        events.write_text("order\tmonotonic_ns\twall_time\tevent\tdetail\n", encoding="utf-8")
        append_result(results, "root-scope", f"root writes constrained to {evidence_root}, the fixed lock and disposable transaction")
        append_result(results, "input-replay", "Stage C1 package and physical Stage C15 evidence replayed")

        with CandidateValidationRehearsalAdapter(package_root, invoking_user, evidence_root) as adapter:
            if not isinstance(adapter, ProductionAdapterV2):
                raise SystemExit("Stage C16 adapter does not conform to ProductionAdapterV2")
            append_result(results, "protocol-conformance", "adapter exposes fifteen v1 operations plus typed v2 abort")

            host_result = adapter.inspect_host_contract()
            require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(results, "pre-lock-host-contract", "stable aarch64 route and fixed host contract verified")
            lock_result = adapter.inspect_production_lock()
            lock = require_pass(lock_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
            if lock.exists or lock.held_by_caller:
                raise SystemExit("production lock must begin absent")
            append_result(results, "pre-lock-boundary", f"{lock.path} absent and unopened")

            acquire_result = adapter.acquire_production_lock()
            lease = require_pass(acquire_result, AdapterOperation.ACQUIRE_PRODUCTION_LOCK)
            append_result(results, "production-lock-acquired", f"adapter-generated lease {lease.lease_id}")
            append_event(events, 10, "production-lock-acquired", lease.lease_id)

            create_result = adapter.create_authoritative_transaction(TransactionAction.INSTALL, package)
            transaction = require_pass(create_result, AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION)
            append_result(results, "authoritative-transaction-created", f"fresh transaction {transaction.transaction.value}")
            if adapter.authoritative_transaction != transaction:
                raise SystemExit("authoritative transaction identity binding failed")
            append_result(results, "transaction-identity-binding", "transaction, snapshot, package, action and held lease are adapter-bound")
            write_identity(evidence_root / "identity.tsv", transaction, lease.lease_id, invoking_user)
            write_parent_states(evidence_root / "parent-state.tsv", adapter.parent_states)

            filesystem_result = adapter.capture_filesystem_state(transaction.transaction)
            filesystem = require_pass(filesystem_result, AdapterOperation.CAPTURE_FILESYSTEM_STATE)
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot identity is not authoritative")
            append_result(results, "filesystem-snapshot", "current ALSA and all managed destination states captured exactly")
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

            stage_result = adapter.stage_candidate_files(transaction.transaction, package)
            if stage_result.status is not AdapterStatus.PASS:
                raise SystemExit(f"candidate staging failed: {stage_result.detail}")
            append_result(results, "candidate-staging", "twelve files atomically staged only inside the transaction candidate root")
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained by the adapter")
            validate_candidate_manifest(package_root, adapter.candidate_root)
            append_result(results, "candidate-manifest-binding", "all staged paths, modes, owners and digests match the Stage C1 manifest")

            validation_results = []
            for operation, call, check, detail in (
                (AdapterOperation.VALIDATE_CANDIDATE_ALSA, adapter.validate_candidate_alsa, "candidate-alsa-validation", "both staged routes parsed privately; no PCM opened"),
                (AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, adapter.validate_candidate_sudoers, "candidate-sudoers-validation", "staged restricted rules accepted by visudo"),
                (AdapterOperation.VALIDATE_CANDIDATE_UNITS, adapter.validate_candidate_units, "candidate-unit-validation", "three staged units and inert helper passed private verification"),
                (AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, adapter.validate_candidate_camilladsp, "candidate-camilladsp-validation", "digest-pinned binary accepted staged config without audio"),
            ):
                result = call(transaction.transaction)
                if result.operation is not operation or result.status is not AdapterStatus.PASS:
                    raise SystemExit(f"{operation.value} failed: {result.detail}")
                validation_results.append(result)
                append_result(results, check, detail)

            blocked = prove_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
                snapshot=transaction.snapshot,
            )
            write_blocked_operations(evidence_root / "blocked-operations.tsv", blocked)
            append_result(results, "blocked-operation-boundary", f"all {len(blocked)} service, install, audio and recovery operations refused exactly")
            append_result(results, "pre-mutation-boundary", "first appliance mutation remained blocked; no service, mixer, route or audio state changed")

            typed = (
                host_result,
                lock_result,
                acquire_result,
                create_result,
                filesystem_result,
                service_result,
                mixer_result,
                loopback_result,
                dac_result,
                stage_result,
                *validation_results,
            )
            (evidence_root / "typed-operations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "mutation_started": False,
                        "committed": False,
                        "operations": [jsonable(result) for result in typed],
                    },
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )

            premature = adapter.release_production_lock()
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit("production lock release did not refuse the open transaction")
            abort_result = adapter.abort_uncommitted_transaction(transaction.transaction)
            if (
                abort_result.operation is not TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
                or abort_result.status is not AdapterStatus.PASS
                or abort_result.payload is None
            ):
                raise SystemExit(f"v2 transaction abort failed: {abort_result.detail}")
            if adapter.candidate_review_copy is None or not adapter.candidate_review_copy.is_dir():
                raise SystemExit("candidate review evidence copy is missing")
            append_result(results, "candidate-evidence-copy", f"validated candidate retained non-authoritatively at {adapter.candidate_review_copy}")
            append_result(results, "transaction-abort-v2", "typed abort accepted only the adapter-generated transaction identity")
            if adapter.transaction_path is not None or Path(abort_result.payload.audit_evidence) != evidence_root:
                raise SystemExit("transaction abort did not finish exact cleanup")
            append_result(results, "exact-transaction-cleanup", "candidate, validation root and authoritative transaction removed; parent state restored")
            append_event(events, 20, "transaction-aborted", transaction.transaction.value)

            release_result = adapter.release_production_lock()
            require_receipt(release_result, AdapterOperation.RELEASE_PRODUCTION_LOCK)
            append_result(results, "production-lock-released", "exact production lock removed only after v2 transaction abort")
            append_event(events, 30, "production-lock-released", lease.lease_id)
            write_report(evidence_root / "report.txt", evidence_root, transaction, len(blocked))

        for label, root in (("stage-c1", package_root), ("stage-c15", stage_c15_root)):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(f"{label} input changed during Stage C16")
        append_result(results, "input-integrity", "Stage C1 and Stage C15 input trees remained unchanged")
        write_evidence_manifest(evidence_root)
        append_result(results, "evidence-integrity", "complete checksummed evidence tree contains no symlink or special object")
        append_result(results, "activation-interface", "absent; validated transaction aborted before the first appliance mutation")
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C16 result order: {observed}")
        completed = True
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C16 candidate validation rehearsal did not complete")
    print(
        f"""
A Clockwork Plex Stage C16 candidate staging and validation rehearsal passed.

  Directory:          {evidence_root}
  Results:            {evidence_root / 'results.tsv'}
  Identity:           {evidence_root / 'identity.tsv'}
  Typed operations:   {evidence_root / 'typed-operations.json'}
  Blocked operations: {evidence_root / 'blocked-operations.tsv'}
  Candidate copy:     {evidence_root / 'candidate-review-copy'}
  Transaction copy:   {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:  {evidence_root / 'evidence-manifest.tsv'}
  Report:             {evidence_root / 'report.txt'}

The candidate was staged and validated only inside the authoritative transaction.
The transaction was aborted before service or audio mutation, and the production
lock was released. Persistent Stage C activation remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
