#!/usr/bin/python3
from __future__ import annotations

"""Single current-package file/reload/route exact-rollback rehearsal.

This consolidates the remaining rollback-only filesystem, systemd-manager and
active-route proof into one physical interruption.  Managed Stage C services,
CamillaDSP, probes, approval publication and commit remain unavailable here;
the next physical operation after this checkpoint is the guarded terminal
install, not another one-operation rehearsal.
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
from .current_package_route_selection_rollback_adapter_v13 import (
    CURRENT_ROUTE_SNAPSHOT_PREFIX_V13,
    CURRENT_ROUTE_TRANSACTION_PREFIX_V13,
    CurrentPackageRouteRollbackLifecycleOperationV13,
    CurrentPackageRouteSelectionRollbackAdapterV13,
    apply_current_route_identity_contract_v13,
)
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CurrentPackageSystemdReloadLifecycleOperationV10,
)
from .current_package_systemd_reload_rollback_rehearsal_v10 import (
    STAGE_C23_MANIFEST_ENTRIES,
    validate_stage_c23_evidence,
    write_input_binding,
)
from .current_package_managed_file_rollback_rehearsal_v9 import (
    validate_stage_c22_evidence,
)
from .current_package_service_quiescence_rehearsal_v8 import (
    validate_stage_c21_evidence,
)
from .current_package_systemd_reload_rollback_rehearsal_v12 import (
    emit_pre_live_diagnostics_v12,
)
from .managed_file_rollback_rehearsal import _expect_blocked
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ProductionAdapterBlocked,
    TransactionAction,
)
from .production_adapter_lifecycle_v3 import ProductionAdapterV3
from .production_adapter_lifecycle_v7 import ProductionAdapterV7
from .production_prepare_only_inspector_v7 import ProductionPrepareOnlyInspectorV7
from .read_only_host_adapter import ReadOnlyHostProductionAdapter
from .sandbox_transaction import _assert_regular_tree, tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C25-CURRENT-PACKAGE-ROUTE-EXACT-ROLLBACK"
EVIDENCE_PREFIX = (
    "a-clockwork-plex-stage-c25-current-package-route-rollback."
)
EXPECTED_CHECKS = (
    "root-scope",
    "input-replay",
    "pre-lock-live-baseline",
    "protocol-conformance",
    "production-lock-acquired",
    "authoritative-transaction-created",
    "snapshot-complete",
    "candidate-validated",
    "pre-route-boundary",
    "service-quiescence",
    "dac-release",
    "managed-file-installation",
    "systemd-candidate-reload",
    "split-bus-route-selection",
    "runtime-activation-boundary",
    "active-route-and-filesystem-rollback",
    "pre-manager-rollback-service-refusal",
    "systemd-manager-rollback",
    "application-service-restoration",
    "dashboard-health",
    "exact-rollback-verification",
    "prior-closure-refusal",
    "route-rollback-close",
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
            "Install and validate the accepted 28-file package, perform one "
            "bounded daemon reload, atomically select the split-bus route, "
            "then restore the exact route/filesystem/systemd/service baseline."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--stage-c21-root", required=True, type=Path)
    parser.add_argument("--stage-c22-root", required=True, type=Path)
    parser.add_argument("--stage-c23-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args(argv)


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="integrated current-package route evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("integrated route evidence root must be empty")
    return root


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
        "managed_files_installed\ttrue\n"
        "systemd_reloaded\ttrue\n"
        "split_bus_route_selected\ttrue\n"
        "active_route_restored\ttrue\n"
        "filesystem_restored\ttrue\n"
        "systemd_manager_restored\ttrue\n"
        "services_restored\ttrue\n"
        "daemon_reload_attempts\t2\n"
        "route_selection_count\t1\n"
        "managed_stage_c_services_started\tfalse\n"
        "audio_probe_opened\tfalse\n"
        "approval_published\tfalse\n"
        "committed\tfalse\n"
        "reusable_for_activation\tfalse\n",
        encoding="utf-8",
    )


def write_report(output: Path, evidence_root: Path, transaction) -> None:
    output.write_text(
        f"""A Clockwork Plex integrated current-package route rollback rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Accepted package fingerprint: {ACCEPTED_PACKAGE_FINGERPRINT}
Accepted Stage C23 manifest entries: {STAGE_C23_MANIFEST_ENTRIES}
Final transaction state: current-package-route-rolled-back-and-closed
Managed files installed and removed: 28
Daemon reload attempts: 2
Route selections: 1
Managed Stage C services started: false
Audio probes opened: false
Approval published: false
Committed: false

This is the final rollback-only checkpoint.  It combines the current-package
managed-file, systemd-manager and active-route boundaries in one physical run.
The next physical operation is the guarded terminal install/enable transaction,
not a new one-operation rehearsal.

Proved:
- exact retained package, baseline and C21-C23 evidence replay
- one held canonical production lock and one authoritative five-domain snapshot
- all 28 fixed managed files privately staged, validated and installed
- one bounded daemon reload exposed the three inactive managed units
- one atomic inode exchange selected the reviewed split-bus ALSA route
- managed runtime, probes, approval and commit remained blocked
- exact original active-route inode restored before managed-file rollback
- second and final daemon reload forgot all three removed units
- captured application services, dashboard and full audio baseline restored
- transaction removed before production lock release

Not performed:
- managed Stage C service startup
- CamillaDSP child startup or health publication
- finite music or alarm probes
- approval publication or committed promotion
- persistent activation, reboot verification, PR readiness or merge
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(f"integrated route rehearsal requires --confirm {REQUIRED_CONFIRMATION}")

    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = validate_package_root(args.package_root, invoking_uid)
    baseline_root = validate_baseline_root(args.baseline_root, invoking_uid)
    stage_c21_root = validate_stage_c21_evidence(
        args.stage_c21_root,
        invoking_uid,
        package_root,
        baseline_root,
    )
    stage_c22_root = validate_stage_c22_evidence(args.stage_c22_root, invoking_uid)
    stage_c23_root = validate_stage_c23_evidence(args.stage_c23_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    package = validate_current_package_v7(package_root)
    validate_accepted_baseline_evidence_v7(baseline_root, package)

    input_roots = {
        "package": package_root,
        "baseline": baseline_root,
        "stage-c21": stage_c21_root,
        "stage-c22": stage_c22_root,
        "stage-c23": stage_c23_root,
    }
    input_fingerprints = {
        label: tree_fingerprint(root) for label, root in input_roots.items()
    }

    pre_live = ProductionPrepareOnlyInspectorV7(
        ReadOnlyHostProductionAdapter(),
        package,
    ).inspect()
    emit_pre_live_diagnostics_v12(pre_live)
    validate_prepare_only_report_against_accepted_v7(pre_live, package)

    apply_target_proved_parent_contract_v8()
    apply_current_route_identity_contract_v13()

    os.chown(evidence_root, 0, 0)
    evidence_root.chmod(0o700)
    completed = False
    results = evidence_root / "results.tsv"
    events = evidence_root / "lock-events.tsv"
    try:
        results.write_text("check\tresult\tdetail\n", encoding="utf-8")
        events.write_text(
            "order\tmonotonic_ns\twall_time\tevent\tdetail\n",
            encoding="utf-8",
        )
        append_result(
            results,
            "root-scope",
            (
                f"writes constrained to {evidence_root}, the canonical lock, "
                "one authoritative transaction and 28 fixed destinations"
            ),
        )
        append_result(
            results,
            "input-replay",
            "accepted current package, baseline and immutable C21-C23 evidence replayed",
        )
        append_result(
            results,
            "pre-lock-live-baseline",
            "all six fixed read-only appliance observations are baseline-ready",
        )
        write_input_binding(
            evidence_root / "input-binding.tsv",
            package_root,
            baseline_root,
            stage_c21_root,
            stage_c22_root,
            stage_c23_root,
        )

        with CurrentPackageRouteSelectionRollbackAdapterV13(
            package_root,
            invoking_user,
            evidence_root,
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV3):
                raise SystemExit("integrated route adapter lost ProductionAdapterV3")
            if isinstance(adapter, ProductionAdapterV7):
                raise SystemExit("rollback-only route adapter exposes approval-capable v7")
            append_result(
                results,
                "protocol-conformance",
                (
                    "current 28-file owner, hard two-attempt reload budget and "
                    "one exact route exchange; approval operations absent"
                ),
            )

            require_pass(
                adapter.inspect_host_contract(),
                AdapterOperation.INSPECT_HOST_CONTRACT,
            )
            observed_lock = require_pass(
                adapter.inspect_production_lock(),
                AdapterOperation.INSPECT_PRODUCTION_LOCK,
            )
            if observed_lock.exists or observed_lock.held_by_caller:
                raise SystemExit("production lock must begin absent")
            lease = require_pass(
                adapter.acquire_production_lock(),
                AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-acquired",
                f"adapter-generated lease {lease.lease_id}",
            )
            append_event(events, 10, "production-lock-acquired", lease.lease_id)

            transaction = require_pass(
                adapter.create_authoritative_transaction(
                    TransactionAction.INSTALL,
                    package,
                ),
                AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            )
            if (
                not transaction.transaction.value.startswith(
                    CURRENT_ROUTE_TRANSACTION_PREFIX_V13
                )
                or not transaction.snapshot.value.startswith(
                    CURRENT_ROUTE_SNAPSHOT_PREFIX_V13
                )
            ):
                raise SystemExit("integrated route transaction prefix changed")
            append_result(
                results,
                "authoritative-transaction-created",
                transaction.transaction.value,
            )
            write_parent_states(
                evidence_root / "parent-state.tsv",
                adapter.parent_states,
            )

            filesystem = require_pass(
                adapter.capture_filesystem_state(transaction.transaction),
                AdapterOperation.CAPTURE_FILESYSTEM_STATE,
            )
            services = require_pass(
                adapter.capture_service_state(transaction.transaction),
                AdapterOperation.CAPTURE_SERVICE_STATE,
            )
            mixer = require_pass(
                adapter.capture_mixer_state(transaction.transaction),
                AdapterOperation.CAPTURE_MIXER_STATE,
            )
            loopback = require_pass(
                adapter.capture_loopback_state(transaction.transaction),
                AdapterOperation.CAPTURE_LOOPBACK_STATE,
            )
            dac = require_pass(
                adapter.capture_dac_state(transaction.transaction),
                AdapterOperation.CAPTURE_DAC_STATE,
            )
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot is not authoritative")
            validate_snapshot_payloads_against_accepted_v7(
                services,
                mixer,
                loopback,
                dac,
            )
            append_result(
                results,
                "snapshot-complete",
                "filesystem, service, mixer, loopback and DAC domains captured exactly",
            )

            require_receipt(
                adapter.stage_candidate_files(transaction.transaction, package),
                AdapterOperation.STAGE_CANDIDATE_FILES,
            )
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained")
            validate_candidate_manifest_v7(package_root, adapter.candidate_root)
            for operation, call in (
                (AdapterOperation.VALIDATE_CANDIDATE_ALSA, adapter.validate_candidate_alsa),
                (AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, adapter.validate_candidate_sudoers),
                (AdapterOperation.VALIDATE_CANDIDATE_UNITS, adapter.validate_candidate_units),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
                    adapter.validate_candidate_camilladsp,
                ),
            ):
                require_receipt(call(transaction.transaction), operation)
            append_result(
                results,
                "candidate-validated",
                "all 28 staged paths and four private validation domains passed",
            )

            pre_route = adapter.select_split_bus_route(transaction.transaction)
            if pre_route.status is not AdapterStatus.FAIL:
                raise SystemExit("route selection did not refuse before installation/reload")
            append_result(
                results,
                "pre-route-boundary",
                "route exchange refused before quiescence, installation and first reload",
            )

            require_receipt(
                adapter.stop_captured_application_services(
                    transaction.transaction,
                    services,
                ),
                AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            )
            append_result(
                results,
                "service-quiescence",
                "captured-active Plexamp, AirPlay and dashboard services stopped",
            )
            append_event(events, 20, "application-services-stopped", "3")

            require_receipt(
                adapter.verify_dac_released(transaction.transaction),
                AdapterOperation.VERIFY_DAC_RELEASED,
            )
            append_result(
                results,
                "dac-release",
                "physical DAC and fixed loopback endpoints are unowned",
            )

            install_result = adapter.install_managed_files(transaction.transaction)
            require_receipt(install_result, AdapterOperation.INSTALL_MANAGED_FILES)
            if dict(install_result.evidence).get("installed_file_count") != "28":
                raise SystemExit("integrated route install count changed")
            append_result(
                results,
                "managed-file-installation",
                "all 28 managed files installed with exact inode-ledger ownership",
            )
            append_event(events, 30, "managed-files-installed", "28")

            require_receipt(
                adapter.reload_systemd(transaction.transaction),
                AdapterOperation.RELOAD_SYSTEMD,
            )
            if (
                adapter.systemd_reload_count != 1
                or adapter.systemd_reload_attempt_count != 1
                or not adapter.systemd_candidate_visible
            ):
                raise SystemExit("first daemon reload state is not exact")
            append_result(
                results,
                "systemd-candidate-reload",
                "first reload exposed exactly three loaded inactive managed units",
            )

            route_result = adapter.select_split_bus_route(transaction.transaction)
            require_receipt(route_result, AdapterOperation.SELECT_SPLIT_BUS_ROUTE)
            if (
                adapter.route_selection_count != 1
                or not adapter.route_selected_once
                or adapter.route_restored
            ):
                raise SystemExit("split-bus route selection state is not exact")
            append_result(
                results,
                "split-bus-route-selection",
                "one atomic inode exchange selected the reviewed split-bus route",
            )
            append_event(events, 40, "split-bus-route-selected", "count=1")

            blocked_rows: list[tuple[str, str]] = []
            for operation, call in (
                (
                    AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
                    lambda: adapter.start_managed_stage_c_services(
                        transaction.transaction
                    ),
                ),
                (
                    AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
                    lambda: adapter.verify_split_bus_health(transaction.transaction),
                ),
                (
                    AdapterOperation.RUN_FINITE_MUSIC_PROBE,
                    lambda: adapter.run_finite_music_probe(transaction.transaction),
                ),
                (
                    AdapterOperation.RUN_FINITE_ALARM_PROBE,
                    lambda: adapter.run_finite_alarm_probe(transaction.transaction),
                ),
                (
                    AdapterOperation.WRITE_COMMIT_MANIFEST,
                    lambda: adapter.write_commit_manifest(transaction.transaction),
                ),
            ):
                _expect_blocked(blocked_rows, operation, call)
            write_blocked_operations(
                evidence_root / "runtime-activation-blocked.tsv",
                blocked_rows,
            )
            approval_rows = prove_approval_operations_blocked(
                adapter,
                transaction.transaction,
            )
            write_approval_operations(
                evidence_root / "approval-operations.tsv",
                approval_rows,
            )
            append_result(
                results,
                "runtime-activation-boundary",
                "managed runtime, health, probes, commit and all four approvals remained blocked",
            )

            rollback_result = adapter.restore_exact_snapshot(
                transaction.transaction,
                transaction.snapshot,
            )
            require_receipt(
                rollback_result,
                AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            )
            if not adapter.route_restored or not adapter.filesystem_restored:
                raise SystemExit("route/filesystem rollback did not complete exactly")
            append_result(
                results,
                "active-route-and-filesystem-rollback",
                "original route inode restored before all installed files were removed",
            )
            append_event(events, 50, "route-and-files-restored", "true")

            premature = adapter.restore_captured_application_services(
                transaction.transaction,
                services,
            )
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit("services restarted before manager rollback")
            append_result(
                results,
                "pre-manager-rollback-service-refusal",
                "application services remained blocked while removed units were cached",
            )

            require_receipt(
                adapter.reload_systemd(transaction.transaction),
                AdapterOperation.RELOAD_SYSTEMD,
            )
            if (
                adapter.systemd_reload_count != 2
                or adapter.systemd_reload_attempt_count != 2
                or not adapter.systemd_manager_restored
            ):
                raise SystemExit("second daemon reload state is not exact")
            append_result(
                results,
                "systemd-manager-rollback",
                "second and final reload forgot all three removed managed units",
            )
            append_event(events, 60, "systemd-manager-restored", "true")

            require_receipt(
                adapter.restore_captured_application_services(
                    transaction.transaction,
                    services,
                ),
                AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            )
            append_result(
                results,
                "application-service-restoration",
                "captured application service state restored after route and manager rollback",
            )

            require_receipt(
                adapter.verify_dashboard_health(transaction.transaction),
                AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            )
            append_result(
                results,
                "dashboard-health",
                "dashboard HTTP and accepted direct audio baseline are healthy",
            )

            require_receipt(
                adapter.verify_exact_rollback(
                    transaction.transaction,
                    transaction.snapshot,
                ),
                AdapterOperation.VERIFY_EXACT_ROLLBACK,
            )
            append_result(
                results,
                "exact-rollback-verification",
                "zero route, file, systemd, service, mixer, loopback or DAC mismatch remains",
            )

            old_close = adapter.close_current_package_systemd_reload_rollback_rehearsal(
                transaction.transaction
            )
            if (
                old_close.operation
                is not CurrentPackageSystemdReloadLifecycleOperationV10.
                CLOSE_CURRENT_PACKAGE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL
                or old_close.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("C24 systemd-only closure did not refuse route history")
            append_result(
                results,
                "prior-closure-refusal",
                "C24 systemd-only closure refused after route mutation",
            )

            close_result = adapter.close_current_package_route_rollback_rehearsal(
                transaction.transaction
            )
            if (
                close_result.operation
                is not CurrentPackageRouteRollbackLifecycleOperationV13.
                CLOSE_CURRENT_PACKAGE_ROUTE_ROLLBACK_REHEARSAL
                or close_result.status is not AdapterStatus.PASS
                or close_result.payload is None
            ):
                raise SystemExit(f"integrated route closure failed: {close_result.detail}")
            append_result(
                results,
                "route-rollback-close",
                "typed closure accepted exactly one route exchange and complete rollback",
            )
            if (
                adapter.transaction_path is not None
                or not close_result.payload.transaction_path_absent
                or close_result.payload.daemon_reload_count != 2
                or close_result.payload.route_selection_count != 1
            ):
                raise SystemExit("integrated route transaction cleanup is incomplete")
            append_result(
                results,
                "exact-transaction-cleanup",
                "authoritative transaction removed and fixed parent state restored",
            )

            write_identity(
                evidence_root / "identity.tsv",
                transaction,
                lease.lease_id,
                invoking_user,
            )
            (evidence_root / "typed-operations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "managed_files_installed": True,
                        "daemon_reload_attempts": 2,
                        "route_selection_count": 1,
                        "active_route_restored": True,
                        "filesystem_restored": True,
                        "systemd_manager_restored": True,
                        "services_restored": True,
                        "managed_stage_c_services_started": False,
                        "audio_probe_opened": False,
                        "approval_published": False,
                        "committed": False,
                        "close_result": jsonable(close_result),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            require_receipt(
                adapter.release_production_lock(),
                AdapterOperation.RELEASE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-released",
                "canonical lock released only after exact transaction closure",
            )
            append_event(events, 70, "production-lock-released", lease.lease_id)

        post_live = ProductionPrepareOnlyInspectorV7(
            ReadOnlyHostProductionAdapter(),
            package,
        ).inspect()
        emit_pre_live_diagnostics_v12(post_live)
        validate_prepare_only_report_against_accepted_v7(post_live, package)
        append_result(
            results,
            "post-lock-live-baseline",
            "all six fixed read-only observations returned to baseline-ready",
        )

        for label, root in input_roots.items():
            if tree_fingerprint(root) != input_fingerprints[label]:
                raise SystemExit(f"{label} input changed during integrated route rehearsal")
        append_result(
            results,
            "input-integrity",
            "package, baseline and C21-C23 evidence trees remained unchanged",
        )

        write_report(evidence_root / "report.txt", evidence_root, transaction)
        _assert_regular_tree(evidence_root, "integrated route evidence")
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS[:-2]:
            raise SystemExit(f"unexpected pre-seal result order: {observed}")
        append_result(
            results,
            "evidence-integrity",
            "fixed evidence tree sealed with deterministic manifest",
        )
        append_result(
            results,
            "activation-interface",
            "absent; the next operation is the separately coded terminal installer",
        )
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected integrated route result order: {observed}")
        completed = True
    except (CurrentPackageContractErrorV7, ProductionAdapterBlocked) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("integrated current-package route rehearsal did not complete")

    print(
        f"""A Clockwork Plex integrated current-package route rollback passed.

  Directory:         {evidence_root}
  Results:           {evidence_root / 'results.tsv'}
  Identity:          {evidence_root / 'identity.tsv'}
  Route actions:     {evidence_root / 'route-selection-actions.tsv'}
  File actions:      {evidence_root / 'managed-file-actions.tsv'}
  Systemd actions:   {evidence_root / 'systemd-reload-actions.tsv'}
  Transaction copy:  {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest: {evidence_root / 'evidence-manifest.tsv'}
  Report:            {evidence_root / 'report.txt'}

All 28 files, both daemon reloads and one atomic split-bus route selection were
exercised in one physical run, then the exact direct baseline was restored.
No managed Stage C service, probe, approval or commit operation was exposed.
This is the final rollback-only physical checkpoint before guarded install."""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
