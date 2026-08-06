#!/usr/bin/python3
from __future__ import annotations

"""Stage C24 current-package systemd reload and exact rollback rehearsal."""

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
from .current_package_managed_file_rollback_adapter_v9 import (
    CURRENT_PACKAGE_FILE_COUNT_V9,
    CURRENT_PACKAGE_PAYLOAD_COUNT_V9,
    CurrentPackageExactRollbackLifecycleOperationV9,
)
from .current_package_managed_file_rollback_rehearsal_v9 import (
    validate_stage_c22_evidence,
)
from .current_package_service_quiescence_rehearsal_v8 import (
    validate_stage_c21_evidence,
)
from .current_package_systemd_reload_rollback_adapter_v10 import (
    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10,
    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10,
    CurrentPackageSystemdReloadLifecycleOperationV10,
    CurrentPackageSystemdReloadRollbackAdapterV10,
    apply_current_systemd_reload_identity_contract_v10,
)
from .managed_file_rollback_rehearsal import _expect_blocked
from .package_review import sha256
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ProductionAdapterBlocked,
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
from .snapshot_core import chown_evidence_tree, write_evidence_manifest
from .stage_c23_evidence_identity import (
    ACCEPTED_STAGE_C23_MANIFEST_ROWS,
    ACCEPTED_STAGE_C23_MANIFEST_SHA256,
    ACCEPTED_STAGE_C23_ROOT,
    validate_blocked_boundaries as validate_stage_c23_blocked_boundaries,
    validate_identity as validate_stage_c23_identity,
    validate_input_binding as validate_stage_c23_input_binding,
    validate_report as validate_stage_c23_report,
    validate_results as validate_stage_c23_results,
)
from .systemd_reload_rollback_rehearsal import (
    prove_blocked_operations as prove_c24_blocked_operations,
)


REQUIRED_CONFIRMATION = (
    "STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK"
)
EVIDENCE_PREFIX = (
    "a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback."
)
STAGE_C23_MANIFEST_ENTRIES = 143
EXPECTED_CHECKS = (
    "root-scope",
    "package-replay",
    "baseline-replay",
    "stage-c21-evidence-replay",
    "stage-c22-evidence-replay",
    "stage-c23-evidence-replay",
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
    "managed-file-installation",
    "installed-manifest-binding",
    "post-install-route-boundary",
    "systemd-candidate-reload",
    "systemd-candidate-unit-visibility",
    "exact-filesystem-rollback",
    "pre-manager-rollback-service-refusal",
    "systemd-manager-rollback",
    "systemd-rollback-unit-absence",
    "application-service-restoration",
    "dashboard-health",
    "exact-rollback-verification",
    "exact-restoration-boundary",
    "pre-mutation-abort-refusal",
    "service-only-closure-refusal",
    "c23-closure-refusal",
    "candidate-evidence-copy",
    "exact-rollback-close-c24",
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
            "Install and validate the accepted 28-file current package while "
            "the application services and DAC are quiesced, reload systemd "
            "once to prove the three candidate units are loaded but inactive, "
            "restore the exact filesystem, reload systemd again to prove the "
            "units are forgotten, and restore the accepted appliance state."
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
        label="Stage C24 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C24 evidence root must be empty")
    return root


def _rows_by_key(path: Path, key: str, value: str) -> dict[str, str]:
    return {row.get(key, ""): row.get(value, "") for row in _read_tsv(path)}


def validate_stage_c23_evidence(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix="a-clockwork-plex-stage-c23-current-package-managed-file-rollback.",
        invoking_uid=invoking_uid,
        label="accepted Stage C23 evidence",
    )
    if root != ACCEPTED_STAGE_C23_ROOT:
        raise SystemExit("Stage C24 accepts only the exact retained Stage C23 root")
    _assert_regular_tree(root, "accepted Stage C23 evidence")
    _validate_evidence_manifest(root, "Stage C23")
    manifest = root / "evidence-manifest.tsv"
    if sha256(manifest) != ACCEPTED_STAGE_C23_MANIFEST_SHA256:
        raise SystemExit("Stage C23 accepted evidence-manifest digest changed")
    rows = sum(1 for _ in manifest.open("r", encoding="utf-8"))
    entries = len(_read_tsv(manifest))
    if (
        rows != ACCEPTED_STAGE_C23_MANIFEST_ROWS
        or entries != STAGE_C23_MANIFEST_ENTRIES
    ):
        raise SystemExit("Stage C23 accepted manifest shape changed")
    validate_stage_c23_results(_read_tsv(root / "results.tsv"))
    validate_stage_c23_input_binding(
        _rows_by_key(root / "input-binding.tsv", "item", "value")
    )
    validate_stage_c23_identity(
        _rows_by_key(root / "identity.tsv", "item", "value")
    )
    validate_stage_c23_blocked_boundaries(root)
    validate_stage_c23_report((root / "report.txt").read_text(encoding="utf-8"))
    return root


def write_input_binding(
    output: Path,
    package_root: Path,
    baseline_root: Path,
    stage_c21_root: Path,
    stage_c22_root: Path,
    stage_c23_root: Path,
) -> None:
    output.write_text(
        "item\tvalue\n"
        f"package_root\t{package_root}\n"
        f"package_fingerprint\t{ACCEPTED_PACKAGE_FINGERPRINT}\n"
        f"baseline_root\t{baseline_root}\n"
        f"stage_c21_root\t{stage_c21_root}\n"
        f"stage_c22_root\t{stage_c22_root}\n"
        f"stage_c23_root\t{stage_c23_root}\n"
        f"stage_c23_manifest_sha256\t{ACCEPTED_STAGE_C23_MANIFEST_SHA256}\n"
        f"stage_c23_manifest_rows\t{ACCEPTED_STAGE_C23_MANIFEST_ROWS}\n"
        f"stage_c23_manifest_entries\t{STAGE_C23_MANIFEST_ENTRIES}\n"
        f"package_files\t{CURRENT_PACKAGE_FILE_COUNT_V9}\n"
        f"package_payload_files\t{CURRENT_PACKAGE_PAYLOAD_COUNT_V9}\n",
        encoding="utf-8",
    )


def write_identity(
    output: Path,
    transaction,
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
        "mutation_started\ttrue\n"
        "managed_files_installed\ttrue\n"
        "filesystem_restored\ttrue\n"
        "systemd_reloaded\ttrue\n"
        "systemd_manager_restored\ttrue\n"
        "services_restored\ttrue\n"
        "daemon_reload_count\t2\n"
        "route_selected\tfalse\n"
        "committed\tfalse\n"
        "reusable_for_activation\tfalse\n"
        "reusable_for_rollback\tfalse\n",
        encoding="utf-8",
    )


def write_report(
    output: Path,
    evidence_root: Path,
    transaction,
    ordinary_blocked: int,
    approval_blocked: int,
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C24 current-package systemd-reload exact-rollback rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Current package files installed and removed: 28
Current package payload files: 27
Accepted Stage C23 manifest: {ACCEPTED_STAGE_C23_MANIFEST_SHA256}
Accepted Stage C23 manifest entries: {STAGE_C23_MANIFEST_ENTRIES}
Ordinary blocked operations: {ordinary_blocked}
Approval operations exposed by rehearsal: 0
Approval operations blocked: {approval_blocked}
Final transaction state: current-package-systemd-reload-rolled-back-and-closed
Systemd reload count: 2
Systemd manager restored: true
Route selected: false
CamillaDSP started: false
Committed: false

Proved:
- exact package, baseline, Stage C21, Stage C22 and immutable Stage C23 evidence replay
- one canonical lock and one fresh authoritative five-domain snapshot
- all 28 current-package files privately staged and validated
- captured-active Plexamp, Shairport Sync and dashboard services quiesced
- physical DAC and fixed loopback endpoints released
- all 28 managed files atomically installed with inode-ledger coverage
- first fixed daemon reload exposed exactly three loaded, inactive managed units
- route selection, managed services, probes, commit and approvals stayed blocked
- exact installed inodes and only transaction-created directories were removed
- application services could not restart while manager rollback remained pending
- second fixed daemon reload forgot all three managed units
- exact services, dashboard, route, mixer, loopback and DAC state restored
- exact-rollback transaction closed and removed before lock release
- full accepted live baseline re-observed after lock release

Not proved or authorised:
- split-bus or direct-failback route selection
- CamillaDSP managed-service startup or runtime health
- music or alarm probes
- mixer mutation
- approval publication or promotion
- installation commit, activation, reboot persistence or merge

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(f"Stage C24 requires --confirm {REQUIRED_CONFIRMATION}")

    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = validate_package_root(args.package_root, invoking_uid)
    baseline_root = validate_baseline_root(args.baseline_root, invoking_uid)
    stage_c21_root = validate_stage_c21_evidence(
        args.stage_c21_root, invoking_uid, package_root, baseline_root
    )
    stage_c22_root = validate_stage_c22_evidence(args.stage_c22_root, invoking_uid)
    stage_c23_root = validate_stage_c23_evidence(args.stage_c23_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    package = validate_current_package_v7(package_root)
    validate_accepted_baseline_evidence_v7(baseline_root, package)
    inputs = {
        "package": tree_fingerprint(package_root),
        "baseline": tree_fingerprint(baseline_root),
        "stage-c21": tree_fingerprint(stage_c21_root),
        "stage-c22": tree_fingerprint(stage_c22_root),
        "stage-c23": tree_fingerprint(stage_c23_root),
    }

    pre_live = ProductionPrepareOnlyInspectorV7(
        ReadOnlyHostProductionAdapter(), package
    ).inspect()
    validate_prepare_only_report_against_accepted_v7(pre_live, package)

    apply_target_proved_parent_contract_v8()
    apply_current_systemd_reload_identity_contract_v10()

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
        append_result(
            results,
            "root-scope",
            (
                f"root writes constrained to {evidence_root}, the canonical "
                "lock, one disposable transaction and 28 fixed destinations"
            ),
        )
        append_result(results, "package-replay", "accepted 28-file current package and 27-payload fingerprint replayed")
        append_result(results, "baseline-replay", "accepted baseline report and manifest hashes replayed exactly")
        append_result(results, "stage-c21-evidence-replay", "accepted 32-check Stage C21 evidence replayed exactly")
        append_result(results, "stage-c22-evidence-replay", "accepted 41-check Stage C22 evidence replayed exactly")
        append_result(results, "stage-c23-evidence-replay", "accepted 47-check Stage C23 evidence replayed at immutable 144-row/143-entry identity")
        append_result(results, "pre-lock-live-baseline", "fresh fixed read-only observation matches the accepted appliance state")
        write_input_binding(
            evidence_root / "input-binding.tsv",
            package_root,
            baseline_root,
            stage_c21_root,
            stage_c22_root,
            stage_c23_root,
        )

        with CurrentPackageSystemdReloadRollbackAdapterV10(
            package_root, invoking_user, evidence_root
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV3):
                raise SystemExit("Stage C24 adapter does not conform to ProductionAdapterV3")
            if isinstance(adapter, ProductionAdapterV7):
                raise SystemExit("Stage C24 adapter unexpectedly exposes approval-capable v7")
            append_result(
                results,
                "protocol-conformance",
                "current-package validation, reversible service/file mutation, exactly two daemon reloads and one typed C24 closure; no approval methods",
            )

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

            create_result = adapter.create_authoritative_transaction(
                TransactionAction.INSTALL, package
            )
            transaction = require_pass(
                create_result, AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION
            )
            if (
                not transaction.transaction.value.startswith(
                    CURRENT_SYSTEMD_TRANSACTION_PREFIX_V10
                )
                or not transaction.snapshot.value.startswith(
                    CURRENT_SYSTEMD_SNAPSHOT_PREFIX_V10
                )
            ):
                raise SystemExit("Stage C24 transaction identity prefix changed")
            append_result(results, "authoritative-transaction-created", f"fresh transaction {transaction.transaction.value}")
            if adapter.authoritative_transaction != transaction:
                raise SystemExit("authoritative transaction identity binding failed")
            append_result(results, "transaction-identity-binding", "transaction, snapshot, package, action and held lease are adapter-bound")
            write_parent_states(evidence_root / "parent-state.tsv", adapter.parent_states)

            filesystem_result = adapter.capture_filesystem_state(transaction.transaction)
            filesystem = require_pass(filesystem_result, AdapterOperation.CAPTURE_FILESYSTEM_STATE)
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot identity is not authoritative")
            append_result(results, "filesystem-snapshot", "current ALSA and all current-package destination states captured exactly")

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
            require_receipt(stage_result, AdapterOperation.STAGE_CANDIDATE_FILES)
            append_result(results, "candidate-staging", "28 files atomically staged only inside the transaction candidate root")
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained by the adapter")
            validate_candidate_manifest_v7(package_root, adapter.candidate_root)
            append_result(results, "candidate-manifest-binding", "all staged paths, modes, owners and digests match package v2")

            validation_results = []
            for operation, call, check, detail in (
                (AdapterOperation.VALIDATE_CANDIDATE_ALSA, adapter.validate_candidate_alsa, "candidate-alsa-validation", "both staged routes parsed privately; no PCM opened"),
                (AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, adapter.validate_candidate_sudoers, "candidate-sudoers-validation", "restricted installed helper rules accepted by visudo"),
                (AdapterOperation.VALIDATE_CANDIDATE_UNITS, adapter.validate_candidate_units, "candidate-unit-validation", "current readiness units, launcher and runtime package verified"),
                (AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, adapter.validate_candidate_camilladsp, "candidate-camilladsp-validation", "digest-pinned binary accepted staged config without audio"),
            ):
                result = call(transaction.transaction)
                require_receipt(result, operation)
                validation_results.append(result)
                append_result(results, check, detail)

            blocked = prove_c24_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
            )
            write_blocked_operations(evidence_root / "blocked-operations.tsv", blocked)
            append_result(results, "blocked-operation-boundary", f"all {len(blocked)} route, managed-service, probe, commit and direct-restore operations refused exactly")
            approval_blocked = prove_approval_operations_blocked(
                adapter, transaction.transaction
            )
            write_approval_operations(evidence_root / "approval-operations.tsv", approval_blocked)
            append_result(results, "approval-operation-boundary", "all four approval operations blocked and absent from the adapter")

            pre_reload = adapter.reload_systemd(transaction.transaction)
            if pre_reload.status is not AdapterStatus.FAIL or adapter.systemd_reload_count != 0:
                raise SystemExit("systemd reload did not refuse before service/file mutation")
            append_result(results, "pre-mutation-boundary", "daemon reload refused before quiescence and installation; no service, DAC, file, route, mixer, approval or audio mutation began")

            stop_result = adapter.stop_captured_application_services(
                transaction.transaction, services
            )
            require_receipt(stop_result, AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES)
            append_result(results, "service-quiescence", "only captured-active Plexamp, Shairport Sync and dashboard services stopped")
            append_event(events, 20, "application-services-stopped", ",".join(unit.value for unit in adapter.stopped_services))

            release_dac_result = adapter.verify_dac_released(transaction.transaction)
            require_receipt(release_dac_result, AdapterOperation.VERIFY_DAC_RELEASED)
            append_result(results, "dac-release", "physical DAC and fixed loopback endpoints have no owners")

            install_result = adapter.install_managed_files(transaction.transaction)
            require_receipt(install_result, AdapterOperation.INSTALL_MANAGED_FILES)
            install_evidence = dict(install_result.evidence)
            if (
                install_evidence.get("installed_file_count") != "28"
                or install_evidence.get("payload_file_count") != "27"
            ):
                raise SystemExit("Stage C24 installed-file receipt changed")
            append_result(results, "managed-file-installation", "all 28 current-package files atomically installed while services and DAC remained quiesced")
            append_result(results, "installed-manifest-binding", "installed types, inodes, modes, owners and digests matched the transaction candidate")
            append_event(events, 30, "managed-files-installed", "file_count=28")

            route_rows: list[tuple[str, str]] = []
            _expect_blocked(
                route_rows,
                AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
                lambda: adapter.select_split_bus_route(transaction.transaction),
            )
            if len(route_rows) != 1:
                raise SystemExit("post-install route boundary was not exact")
            append_result(results, "post-install-route-boundary", "active split-bus route selection remained blocked after all 28 files existed")

            candidate_reload_result = adapter.reload_systemd(transaction.transaction)
            require_receipt(candidate_reload_result, AdapterOperation.RELOAD_SYSTEMD)
            if (
                adapter.systemd_reload_count != 1
                or not adapter.systemd_candidate_visible
                or adapter.systemd_manager_restored
            ):
                raise SystemExit("first systemd reload state was not exact")
            append_result(results, "systemd-candidate-reload", "first fixed daemon reload completed with all candidate files installed")
            append_result(results, "systemd-candidate-unit-visibility", "exactly three managed units are loaded, inactive, dead and not enabled")
            append_event(events, 35, "systemd-candidate-visible", "managed_units=3")

            post_reload_blocked = prove_c24_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
            )
            write_blocked_operations(
                evidence_root / "post-reload-blocked-operations.tsv",
                post_reload_blocked,
            )

            rollback_result = adapter.restore_exact_snapshot(
                transaction.transaction, transaction.snapshot
            )
            require_receipt(rollback_result, AdapterOperation.RESTORE_EXACT_SNAPSHOT)
            append_result(results, "exact-filesystem-rollback", "all installed inodes and transaction-created directories restored while application services remained stopped")
            append_event(events, 40, "managed-files-rolled-back", "filesystem_restored=true")

            premature_restore = adapter.restore_captured_application_services(
                transaction.transaction, services
            )
            if premature_restore.status is not AdapterStatus.FAIL:
                raise SystemExit("application services restarted before manager rollback")
            append_result(results, "pre-manager-rollback-service-refusal", "application-service restoration refused while the systemd manager still knew the removed units")

            manager_reload_result = adapter.reload_systemd(transaction.transaction)
            require_receipt(manager_reload_result, AdapterOperation.RELOAD_SYSTEMD)
            if (
                adapter.systemd_reload_count != 2
                or not adapter.systemd_manager_restored
            ):
                raise SystemExit("second systemd reload state was not exact")
            append_result(results, "systemd-manager-rollback", "second fixed daemon reload completed only after exact filesystem rollback")
            append_result(results, "systemd-rollback-unit-absence", "all three managed units are not-found, inactive and dead")
            append_event(events, 45, "systemd-manager-restored", "managed_units_not_found=3")

            restore_result = adapter.restore_captured_application_services(
                transaction.transaction, services
            )
            require_receipt(restore_result, AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES)
            append_result(results, "application-service-restoration", "captured application service state restored only after manager rollback")
            append_event(events, 50, "application-services-restored", "plexamp,shairport,dashboard")

            dashboard_result = adapter.verify_dashboard_health(transaction.transaction)
            require_receipt(dashboard_result, AdapterOperation.VERIFY_DASHBOARD_HEALTH)
            append_result(results, "dashboard-health", "stable direct route, mixer, loopback, bounded DAC readiness and dashboard HTTP health verified")

            verify_result = adapter.verify_exact_rollback(
                transaction.transaction, transaction.snapshot
            )
            require_receipt(verify_result, AdapterOperation.VERIFY_EXACT_ROLLBACK)
            append_result(results, "exact-rollback-verification", "zero filesystem, systemd-manager, service, route, mixer, loopback or DAC mismatch remained")
            append_result(results, "exact-restoration-boundary", "two-reload rehearsal ended with the accepted direct appliance state restored")

            abort_result = adapter.abort_uncommitted_transaction(transaction.transaction)
            if (
                abort_result.operation
                is not TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
                or abort_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("pre-mutation abort did not refuse after mutation")
            append_result(results, "pre-mutation-abort-refusal", "v2 pre-mutation abort refused after service, file and manager mutation")

            service_close_result = adapter.close_restored_rehearsal_transaction(
                transaction.transaction
            )
            if (
                service_close_result.operation
                is not RestoredRehearsalLifecycleOperation.CLOSE_RESTORED_REHEARSAL_TRANSACTION
                or service_close_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("service-only closure did not refuse")
            append_result(results, "service-only-closure-refusal", "service-only closure refused the 28-file and systemd-manager mutation history")

            c23_close_result = adapter.close_current_package_exact_rollback_rehearsal(
                transaction.transaction
            )
            if (
                c23_close_result.operation
                is not CurrentPackageExactRollbackLifecycleOperationV9.CLOSE_CURRENT_PACKAGE_EXACT_ROLLBACK_REHEARSAL
                or c23_close_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("C23 file-only closure did not refuse")
            append_result(results, "c23-closure-refusal", "C23 file-only closure refused after systemd-manager mutation")

            premature = adapter.release_production_lock()
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit("production lock release did not refuse the open transaction")

            close_result = (
                adapter.close_current_package_systemd_reload_rollback_rehearsal(
                    transaction.transaction
                )
            )
            if (
                close_result.operation
                is not CurrentPackageSystemdReloadLifecycleOperationV10.CLOSE_CURRENT_PACKAGE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL
                or close_result.status is not AdapterStatus.PASS
                or close_result.payload is None
            ):
                raise SystemExit(f"Stage C24 closure failed: {close_result.detail}")
            candidate_copy = evidence_root / "candidate-review-copy"
            transaction_copy = evidence_root / "transaction-rehearsal-copy"
            if not candidate_copy.is_dir() or not transaction_copy.is_dir():
                raise SystemExit("Stage C24 audit evidence copies are missing")
            append_result(results, "candidate-evidence-copy", f"validated candidate and two-reload transaction retained non-authoritatively at {evidence_root}")
            append_result(results, "exact-rollback-close-c24", "typed C24 closure accepted only the adapter-generated 28-file, two-reload exact-rollback transaction")
            if (
                adapter.transaction_path is not None
                or not close_result.payload.transaction_path_absent
                or not close_result.payload.parents_restored
                or close_result.payload.installed_file_count != 28
                or close_result.payload.payload_file_count != 27
                or close_result.payload.daemon_reload_count != 2
                or Path(close_result.payload.audit_evidence) != evidence_root
            ):
                raise SystemExit("Stage C24 closure did not finish exact transaction cleanup")
            append_result(results, "exact-transaction-cleanup", "candidate, validation root and authoritative transaction removed; parent state restored")
            append_event(events, 60, "systemd-rollback-transaction-closed", transaction.transaction.value)

            write_identity(
                evidence_root / "identity.tsv",
                transaction,
                lease.lease_id,
                invoking_user,
            )
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
                pre_reload,
                stop_result,
                release_dac_result,
                install_result,
                candidate_reload_result,
                rollback_result,
                premature_restore,
                manager_reload_result,
                restore_result,
                dashboard_result,
                verify_result,
                abort_result,
                service_close_result,
                c23_close_result,
                close_result,
            )
            (evidence_root / "typed-operations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "stage_c23_manifest_sha256": ACCEPTED_STAGE_C23_MANIFEST_SHA256,
                        "stage_c23_manifest_entries": STAGE_C23_MANIFEST_ENTRIES,
                        "mutation_started": True,
                        "managed_files_installed": True,
                        "installed_file_count": 28,
                        "payload_file_count": 27,
                        "systemd_reloaded": True,
                        "filesystem_restored": True,
                        "systemd_manager_restored": True,
                        "services_restored": True,
                        "daemon_reload_count": 2,
                        "route_selected": False,
                        "approval_operations_exposed": False,
                        "committed": False,
                        "operations": [jsonable(result) for result in typed],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            release_result = adapter.release_production_lock()
            require_receipt(release_result, AdapterOperation.RELEASE_PRODUCTION_LOCK)
            append_result(results, "production-lock-released", "canonical production lock removed only after exact C24 closure")
            append_event(events, 70, "production-lock-released", lease.lease_id)
            write_report(
                evidence_root / "report.txt",
                evidence_root,
                transaction,
                len(blocked),
                len(approval_blocked),
            )

        post_live = ProductionPrepareOnlyInspectorV7(
            ReadOnlyHostProductionAdapter(), package
        ).inspect()
        validate_prepare_only_report_against_accepted_v7(post_live, package)
        append_result(results, "post-lock-live-baseline", "full accepted lock, approval, service, mixer, loopback and DAC state restored")

        for label, root in (
            ("package", package_root),
            ("baseline", baseline_root),
            ("stage-c21", stage_c21_root),
            ("stage-c22", stage_c22_root),
            ("stage-c23", stage_c23_root),
        ):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(f"{label} input changed during Stage C24")
        append_result(results, "input-integrity", "package, baseline, Stage C21, Stage C22 and Stage C23 evidence trees remained unchanged")
        _assert_regular_tree(evidence_root, "Stage C24 current-package systemd evidence")
        write_evidence_manifest(evidence_root)
        append_result(results, "evidence-integrity", "complete checksummed evidence tree contains no symlink or special object")
        append_result(results, "activation-interface", "absent; both daemon reloads and exact rollback completed before any route selection, managed service startup, probe, approval or commit")
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C24 result order: {observed}")
        completed = True
    except (CurrentPackageContractErrorV7, ProductionAdapterBlocked) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C24 current-package systemd rollback rehearsal did not complete")
    print(
        f"""A Clockwork Plex Stage C24 current-package systemd-reload exact-rollback rehearsal passed.

  Directory:           {evidence_root}
  Results:             {evidence_root / 'results.tsv'}
  Identity:            {evidence_root / 'identity.tsv'}
  Input binding:       {evidence_root / 'input-binding.tsv'}
  Service actions:     {evidence_root / 'service-actions.tsv'}
  File actions:        {evidence_root / 'managed-file-actions.tsv'}
  Systemd actions:     {evidence_root / 'systemd-reload-actions.tsv'}
  Unit observations:   {evidence_root / 'systemd-unit-observations.tsv'}
  Restoration timing: {evidence_root / 'restoration-readiness.tsv'}
  Candidate copy:      {evidence_root / 'candidate-review-copy'}
  Transaction copy:    {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:   {evidence_root / 'evidence-manifest.tsv'}
  Report:              {evidence_root / 'report.txt'}

All 28 accepted current-package files were installed while the application
services and DAC were quiesced. Systemd reloaded and saw exactly three inactive
managed units. The files were removed through the authoritative inode ledger,
systemd reloaded a second time and forgot all three units, then the exact
application and audio state was restored. Route selection, CamillaDSP startup,
probes, approvals, commit and activation remained blocked.""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
