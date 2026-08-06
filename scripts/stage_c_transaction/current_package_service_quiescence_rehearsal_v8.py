#!/usr/bin/python3
from __future__ import annotations

"""Guarded current-package service-quiescence and exact-restoration rehearsal.

Stage C22 repeats the accepted Stage C21 package/snapshot/validation prefix,
briefly stops only the three captured-active application services, proves the
DAC and fixed loopback endpoints are released, restores the exact accepted
appliance state and removes the transaction. It has no installation,
activation, route, mixer, approval or audio interface.
"""

import argparse
import json
import os
import platform
from datetime import datetime
from pathlib import Path

from .authoritative_snapshot_rehearsal import (
    _validate_owned_root,
    append_event,
    append_result,
    jsonable,
    require_pass,
    require_receipt,
    write_parent_states,
)
from .candidate_validation_rehearsal import write_blocked_operations
from .current_package_candidate_rehearsal_parent_contract_v8 import (
    apply_target_proved_parent_contract_v8,
)
from .current_package_candidate_rehearsal_v7 import (
    EVIDENCE_PREFIX as STAGE_C21_EVIDENCE_PREFIX,
    EXPECTED_CHECKS as STAGE_C21_EXPECTED_CHECKS,
    prove_approval_operations_blocked,
    validate_baseline_root,
    validate_candidate_manifest_v7,
    validate_package_root,
    write_approval_operations,
)
from .current_package_contract_v7 import (
    ACCEPTED_PACKAGE_FINGERPRINT,
    CurrentPackageContractErrorV7,
    validate_accepted_baseline_evidence_v7,
    validate_current_package_v7,
    validate_prepare_only_report_against_accepted_v7,
    validate_snapshot_payloads_against_accepted_v7,
)
from .current_package_service_quiescence_adapter_v8 import (
    CurrentPackageServiceQuiescenceAdapterV8,
    apply_current_service_identity_contract_v8,
)
from .package_review import sha256
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ProductionAdapterBlocked,
    ServiceActiveState,
    ServiceUnit,
    TransactionAction,
)
from .production_adapter_lifecycle_v2 import TransactionLifecycleOperation
from .production_adapter_lifecycle_v3 import (
    ProductionAdapterV3,
    RestoredRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v7 import ProductionAdapterV7
from .production_plan import _validate_evidence_manifest
from .production_prepare_only_inspector_v7 import ProductionPrepareOnlyInspectorV7
from .read_only_host_adapter import ReadOnlyHostProductionAdapter
from .sandbox_transaction import _assert_regular_tree, _read_tsv, tree_fingerprint
from .service_quiescence_rehearsal import (
    _expect_blocked,
    prove_blocked_operations,
    write_identity,
)
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c22-current-package-service-quiescence."
STAGE_C21_EVIDENCE_MANIFEST_SHA256 = (
    "a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff"
)
EXPECTED_CHECKS = (
    "root-scope",
    "package-replay",
    "baseline-replay",
    "stage-c21-evidence-replay",
    "pre-lock-live-baseline",
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
    "approval-operation-boundary",
    "pre-mutation-boundary",
    "service-quiescence",
    "dac-release",
    "pre-install-boundary",
    "application-service-restoration",
    "dashboard-health",
    "exact-restoration-boundary",
    "pre-mutation-abort-refusal",
    "candidate-evidence-copy",
    "restored-transaction-close-v3",
    "exact-transaction-cleanup",
    "production-lock-released",
    "post-lock-live-baseline",
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repeat the accepted current-package transaction prefix, briefly "
            "quiesce and exactly restore the application services, then close "
            "without installation or activation."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--stage-c21-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args(argv)


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C22 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C22 evidence root must be empty")
    return root


def _rows_by_key(path: Path, key: str, value: str) -> dict[str, str]:
    return {
        row.get(key, ""): row.get(value, "")
        for row in _read_tsv(path)
    }


def validate_stage_c21_evidence(
    raw: Path,
    invoking_uid: int,
    package_root: Path,
    baseline_root: Path,
) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=STAGE_C21_EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="accepted Stage C21 evidence",
    )
    _validate_evidence_manifest(root, "Stage C21")
    manifest = root / "evidence-manifest.tsv"
    if sha256(manifest) != STAGE_C21_EVIDENCE_MANIFEST_SHA256:
        raise SystemExit("Stage C21 accepted evidence-manifest digest changed")

    results = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in results) != STAGE_C21_EXPECTED_CHECKS:
        raise SystemExit("Stage C21 evidence check order changed")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C21 evidence contains a non-PASS result")

    binding = _rows_by_key(root / "input-binding.tsv", "item", "value")
    if Path(binding.get("package_root", "")).resolve() != package_root.resolve():
        raise SystemExit("Stage C21 evidence is not bound to the supplied package root")
    if Path(binding.get("baseline_root", "")).resolve() != baseline_root.resolve():
        raise SystemExit("Stage C21 evidence is not bound to the supplied baseline root")
    if binding.get("package_fingerprint") != ACCEPTED_PACKAGE_FINGERPRINT:
        raise SystemExit("Stage C21 evidence package fingerprint changed")

    identity = _rows_by_key(root / "identity.tsv", "item", "value")
    if (
        identity.get("mutation_started") != "false"
        or identity.get("committed") != "false"
        or identity.get("reusable_after_abort") != "false"
        or identity.get("approval_operations_exposed") != "false"
    ):
        raise SystemExit("Stage C21 identity is not the accepted pre-mutation abort")

    blocked = _read_tsv(root / "blocked-operations.tsv")
    if len(blocked) != 18 or any(row.get("state") != "blocked" for row in blocked):
        raise SystemExit("Stage C21 ordinary blocked-operation evidence changed")
    approvals = _read_tsv(root / "approval-operations.tsv")
    if len(approvals) != 4 or any(row.get("state") != "blocked" for row in approvals):
        raise SystemExit("Stage C21 approval boundary evidence changed")

    report = (root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "Final transaction state: aborted-before-mutation and removed",
        "Approval operations exposed by rehearsal: 0",
        "No installation or activation interface exists in this rehearsal.",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C21 report contract is missing: {marker}")
    for name in ("candidate-review-copy", "transaction-rehearsal-copy"):
        if not (root / name).is_dir():
            raise SystemExit(f"Stage C21 review evidence is missing: {name}")
    return root


def write_input_binding(
    output: Path,
    package_root: Path,
    baseline_root: Path,
    stage_c21_root: Path,
) -> None:
    output.write_text(
        "item\tvalue\n"
        f"package_root\t{package_root}\n"
        f"package_fingerprint\t{ACCEPTED_PACKAGE_FINGERPRINT}\n"
        f"baseline_root\t{baseline_root}\n"
        f"stage_c21_root\t{stage_c21_root}\n"
        f"stage_c21_manifest_sha256\t{STAGE_C21_EVIDENCE_MANIFEST_SHA256}\n"
        "package_files\t28\n"
        "package_payload_files\t27\n",
        encoding="utf-8",
    )


def write_report(
    output: Path,
    evidence_root: Path,
    transaction,
    ordinary_blocked: int,
    approval_blocked: int,
    restored_services: tuple[ServiceUnit, ...],
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C22 current-package service rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Current package files: 28
Current package payload files: 27
Ordinary blocked operations: {ordinary_blocked}
Approval operations exposed by rehearsal: 0
Approval operations blocked: {approval_blocked}
Final transaction state: service-rehearsal-restored-and-closed
Restored application services: {','.join(unit.value for unit in restored_services)}

Proved:
- exact accepted current package, baseline and Stage C21 evidence replay
- fresh accepted live state immediately before production-lock acquisition
- one real canonical lock and one fresh authoritative transaction
- exact filesystem, service, mixer, loopback and DAC snapshots
- all 28 package files staged and validated only inside the transaction
- every later installation, route, mixer, audio, commit and rollback operation blocked
- all four production approval operations blocked and absent
- only captured-active Plexamp, Shairport Sync and dashboard services stopped
- physical DAC and fixed loopback endpoints released
- managed-file installation remained blocked after DAC release
- exact captured service state, dashboard health and DAC ownership restored
- pre-mutation abort refused after mutation; typed restored closure removed the transaction
- production lock released only after exact restored transaction closure
- full accepted live baseline re-observed after lock release

Not proved or authorised:
- managed-file installation or systemd daemon reload
- split-bus route selection, mixer mutation or Stage C service startup
- approval publication, removal or promotion
- CamillaDSP startup, music probe, alarm probe or physical EQ evaluation
- transaction commit, automatic rollback after file mutation, activation or reboot persistence

No installation or activation interface exists in this rehearsal.
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Stage C22 rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )

    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = validate_package_root(args.package_root, invoking_uid)
    baseline_root = validate_baseline_root(args.baseline_root, invoking_uid)
    stage_c21_root = validate_stage_c21_evidence(
        args.stage_c21_root,
        invoking_uid,
        package_root,
        baseline_root,
    )
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    package = validate_current_package_v7(package_root)
    validate_accepted_baseline_evidence_v7(baseline_root, package)
    inputs = {
        "package": tree_fingerprint(package_root),
        "baseline": tree_fingerprint(baseline_root),
        "stage-c21": tree_fingerprint(stage_c21_root),
    }

    pre_live = ProductionPrepareOnlyInspectorV7(
        ReadOnlyHostProductionAdapter(), package
    ).inspect()
    validate_prepare_only_report_against_accepted_v7(pre_live, package)

    apply_target_proved_parent_contract_v8()
    apply_current_service_identity_contract_v8()

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
        append_result(results, "root-scope", f"root writes constrained to {evidence_root}, the canonical lock and one disposable authoritative transaction")
        append_result(results, "package-replay", "accepted 28-file current package and 27-payload fingerprint replayed")
        append_result(results, "baseline-replay", "accepted baseline report and manifest hashes replayed exactly")
        append_result(results, "stage-c21-evidence-replay", "accepted 32-check Stage C21 evidence manifest replayed exactly")
        append_result(results, "pre-lock-live-baseline", "fresh fixed read-only observation matches the accepted appliance state")
        write_input_binding(evidence_root / "input-binding.tsv", package_root, baseline_root, stage_c21_root)

        with CurrentPackageServiceQuiescenceAdapterV8(
            package_root, invoking_user, evidence_root
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV3):
                raise SystemExit("Stage C22 adapter does not conform to ProductionAdapterV3")
            if isinstance(adapter, ProductionAdapterV7):
                raise SystemExit("Stage C22 adapter unexpectedly exposes approval-capable v7")
            append_result(results, "protocol-conformance", "current-package validation plus typed restored-rehearsal closure; no approval methods")

            host_result = adapter.inspect_host_contract()
            require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(results, "pre-lock-host-contract", "fixed current appliance contract re-observed")
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
            write_identity(evidence_root / "identity.tsv", transaction, lease.lease_id, invoking_user, mutation_started=False, restored=False)
            write_parent_states(evidence_root / "parent-state.tsv", adapter.parent_states)

            filesystem_result = adapter.capture_filesystem_state(transaction.transaction)
            filesystem = require_pass(filesystem_result, AdapterOperation.CAPTURE_FILESYSTEM_STATE)
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot identity is not authoritative")
            append_result(results, "filesystem-snapshot", "current ALSA and all 28 package destinations captured exactly")

            service_result = adapter.capture_service_state(transaction.transaction)
            services = require_pass(service_result, AdapterOperation.CAPTURE_SERVICE_STATE)
            mixer_result = adapter.capture_mixer_state(transaction.transaction)
            mixer = require_pass(mixer_result, AdapterOperation.CAPTURE_MIXER_STATE)
            loopback_result = adapter.capture_loopback_state(transaction.transaction)
            loopback = require_pass(loopback_result, AdapterOperation.CAPTURE_LOOPBACK_STATE)
            dac_result = adapter.capture_dac_state(transaction.transaction)
            dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
            validate_snapshot_payloads_against_accepted_v7(services, mixer, loopback, dac)
            append_result(results, "service-snapshot", "exact accepted six-service state captured under the lock")
            append_result(results, "mixer-snapshot", "exact accepted four-control mixer values captured under the lock")
            append_result(results, "loopback-snapshot", "exact accepted loaded snd_aloop contract captured under the lock")
            append_result(results, "dac-snapshot", "exact DAC geometry and Plexamp owner contract captured under the lock")
            append_result(results, "snapshot-integrity", "all five authoritative domains match the accepted baseline")

            stage_result = adapter.stage_candidate_files(transaction.transaction, package)
            if stage_result.status is not AdapterStatus.PASS:
                raise SystemExit(f"candidate staging failed: {stage_result.detail}")
            append_result(results, "candidate-staging", "28 files atomically staged only inside the transaction candidate root")
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained by the adapter")
            validate_candidate_manifest_v7(package_root, adapter.candidate_root)
            append_result(results, "candidate-manifest-binding", "all staged paths, modes, owners and digests match package v2")

            validation_results = []
            for operation, call, check, detail in (
                (AdapterOperation.VALIDATE_CANDIDATE_ALSA, adapter.validate_candidate_alsa, "candidate-alsa-validation", "both staged routes parsed privately; no PCM opened"),
                (AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, adapter.validate_candidate_sudoers, "candidate-sudoers-validation", "only status and validate-runtime accepted by visudo"),
                (AdapterOperation.VALIDATE_CANDIDATE_UNITS, adapter.validate_candidate_units, "candidate-unit-validation", "current readiness units, launcher and runtime package verified"),
                (AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, adapter.validate_candidate_camilladsp, "candidate-camilladsp-validation", "digest-pinned binary accepted staged config without audio"),
            ):
                result = call(transaction.transaction)
                if result.operation is not operation or result.status is not AdapterStatus.PASS:
                    raise SystemExit(f"{operation.value} failed: {result.detail}")
                validation_results.append(result)
                append_result(results, check, detail)

            blocked = prove_blocked_operations(adapter, transaction=transaction.transaction, services=services, mixer=mixer, snapshot=transaction.snapshot)
            write_blocked_operations(evidence_root / "blocked-operations.tsv", blocked)
            append_result(results, "blocked-operation-boundary", f"all {len(blocked)} later ordinary operations refused exactly")
            approval_blocked = prove_approval_operations_blocked(adapter, transaction.transaction)
            write_approval_operations(evidence_root / "approval-operations.tsv", approval_blocked)
            append_result(results, "approval-operation-boundary", "all four approval operations blocked and absent from the adapter")
            append_result(results, "pre-mutation-boundary", "no service, DAC, install, route, mixer, approval or audio mutation began")

            stop_result = adapter.stop_captured_application_services(transaction.transaction, services)
            require_receipt(stop_result, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES)
            append_result(results, "service-quiescence", "only captured-active Plexamp, Shairport Sync and dashboard services stopped")
            append_event(events, 20, "application-services-stopped", ",".join(unit.value for unit in adapter.stopped_services))

            release_dac_result = adapter.verify_dac_released(transaction.transaction)
            require_receipt(release_dac_result, AdapterOperation.VERIFY_DAC_RELEASED)
            append_result(results, "dac-release", "physical DAC and fixed loopback endpoints have no owners")

            critical_rows: list[tuple[str, str]] = []
            _expect_blocked(critical_rows, AdapterOperation.INSTALL_MANAGED_FILES, lambda: adapter.install_managed_files(transaction.transaction))
            append_result(results, "pre-install-boundary", "managed-file installation remained blocked after DAC release")

            restore_result = adapter.restore_captured_application_services(transaction.transaction, services)
            require_receipt(restore_result, AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES)
            append_result(results, "application-service-restoration", "captured application service state restored exactly")
            append_event(events, 30, "application-services-restored", ",".join(unit.value for unit in (ServiceUnit.PLEXAMP, ServiceUnit.SHAIRPORT_SYNC, ServiceUnit.DASHBOARD)))

            dashboard_result = adapter.verify_dashboard_health(transaction.transaction)
            require_receipt(dashboard_result, AdapterOperation.VERIFY_DASHBOARD_HEALTH)
            append_result(results, "dashboard-health", "stable route, mixer, loopback, bounded DAC readiness and dashboard HTTP health verified")
            append_result(results, "exact-restoration-boundary", "service quiescence ended with the accepted direct appliance state restored")

            abort_result = adapter.abort_uncommitted_transaction(transaction.transaction)
            if abort_result.operation is not TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION or abort_result.status is not AdapterStatus.FAIL:
                raise SystemExit("pre-mutation abort did not refuse after service mutation")
            append_result(results, "pre-mutation-abort-refusal", "v2 pre-mutation abort refused after the service mutation boundary")

            typed = (host_result, lock_result, acquire_result, create_result, filesystem_result, service_result, mixer_result, loopback_result, dac_result, stage_result, *validation_results, stop_result, release_dac_result, restore_result, dashboard_result)
            (evidence_root / "typed-operations.json").write_text(
                json.dumps({
                    "transaction": transaction.transaction.value,
                    "snapshot": transaction.snapshot.value,
                    "lease": lease.lease_id,
                    "package_sha256": package.sha256,
                    "mutation_started": True,
                    "restored": True,
                    "committed": False,
                    "approval_operations_exposed": False,
                    "operations": [jsonable(result) for result in typed],
                }, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            premature = adapter.release_production_lock()
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit("production lock release did not refuse the open transaction")
            close_result = adapter.close_restored_rehearsal_transaction(transaction.transaction)
            if close_result.operation is not RestoredRehearsalLifecycleOperation.CLOSE_RESTORED_REHEARSAL_TRANSACTION or close_result.status is not AdapterStatus.PASS or close_result.payload is None:
                raise SystemExit(f"restored-rehearsal closure failed: {close_result.detail}")
            candidate_copy = evidence_root / "candidate-review-copy"
            if not candidate_copy.is_dir():
                raise SystemExit("candidate review evidence copy is missing")
            append_result(results, "candidate-evidence-copy", f"validated candidate and service rehearsal retained non-authoritatively at {candidate_copy}")
            append_result(results, "restored-transaction-close-v3", "typed v3 closure accepted only the adapter-generated restored transaction")
            if adapter.transaction_path is not None or Path(close_result.payload.audit_evidence) != evidence_root or not close_result.payload.transaction_path_absent or not close_result.payload.parents_restored:
                raise SystemExit("restored closure did not finish exact transaction cleanup")
            append_result(results, "exact-transaction-cleanup", "candidate, validation root and authoritative transaction removed; parent state restored")
            append_event(events, 40, "restored-transaction-closed", transaction.transaction.value)

            write_identity(evidence_root / "identity.tsv", transaction, lease.lease_id, invoking_user, mutation_started=True, restored=True)
            release_result = adapter.release_production_lock()
            require_receipt(release_result, AdapterOperation.RELEASE_PRODUCTION_LOCK)
            append_result(results, "production-lock-released", "exact production lock removed only after restored transaction closure")
            append_event(events, 50, "production-lock-released", lease.lease_id)
            write_report(evidence_root / "report.txt", evidence_root, transaction, len(blocked), len(approval_blocked), close_result.payload.restored_services)

        post_live = ProductionPrepareOnlyInspectorV7(
            ReadOnlyHostProductionAdapter(), package
        ).inspect()
        validate_prepare_only_report_against_accepted_v7(post_live, package)
        append_result(results, "post-lock-live-baseline", "full accepted lock, approval, service, mixer, loopback and DAC state restored")

        for label, root in (("package", package_root), ("baseline", baseline_root), ("stage-c21", stage_c21_root)):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(f"{label} input changed during Stage C22")
        append_result(results, "input-integrity", "package, baseline and Stage C21 evidence trees remained unchanged")
        _assert_regular_tree(evidence_root, "Stage C22 current-package service evidence")
        write_evidence_manifest(evidence_root)
        append_result(results, "evidence-integrity", "complete checksummed evidence tree contains no symlink or special object")
        append_result(results, "activation-interface", "absent; services restored and transaction closed without installation")
        write_evidence_manifest(evidence_root)
        observed = tuple(line.split("\t", 1)[0] for line in results.read_text(encoding="utf-8").splitlines()[1:])
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C22 result order: {observed}")
        completed = True
    except (CurrentPackageContractErrorV7, ProductionAdapterBlocked) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C22 current-package service rehearsal did not complete")
    print(
        f"""A Clockwork Plex Stage C22 current-package service rehearsal passed.

  Directory:           {evidence_root}
  Results:             {evidence_root / 'results.tsv'}
  Identity:            {evidence_root / 'identity.tsv'}
  Input binding:       {evidence_root / 'input-binding.tsv'}
  Service actions:     {evidence_root / 'service-actions.tsv'}
  Restoration timing:  {evidence_root / 'restoration-readiness.tsv'}
  Candidate copy:      {evidence_root / 'candidate-review-copy'}
  Transaction copy:    {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:   {evidence_root / 'evidence-manifest.tsv'}
  Report:              {evidence_root / 'report.txt'}

The accepted current package was staged and validated inside one fresh
transaction. The three captured-active application services were briefly
quiesced, the DAC release was proved, the exact accepted appliance state was
restored, and the transaction and production lock were removed. Installation,
approval, route mutation, CamillaDSP startup and audio remain blocked.""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
