#!/usr/bin/python3
from __future__ import annotations

"""One guarded persistent Stage C EQ installation transaction."""

import argparse
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.model import ApprovalPhase

from . import current_package_candidate_rehearsal_adapter_v7 as current_v7
from .activation_commit_executor_v7 import (
    ActivationExecutionContextV7,
    ActivationExecutionOutcomeV7,
    execute_activation_commit_v7,
)
from .authoritative_snapshot_rehearsal import (
    _validate_owned_root,
    append_event,
    append_result,
    jsonable,
    require_pass,
    require_receipt,
    write_parent_states,
)
from .current_package_candidate_rehearsal_parent_contract_v8 import (
    apply_target_proved_parent_contract_v8,
)
from .current_package_candidate_rehearsal_v7 import (
    validate_baseline_root,
    validate_candidate_manifest_v7,
    validate_package_root,
)
from .current_package_contract_v7 import (
    ACCEPTED_PACKAGE_FINGERPRINT,
    validate_accepted_baseline_evidence_v7,
    validate_current_package_v7,
    validate_prepare_only_report_against_accepted_v7,
    validate_snapshot_payloads_against_accepted_v7,
)
from .current_package_managed_file_rollback_rehearsal_v9 import (
    validate_stage_c22_evidence,
)
from .current_package_route_selection_rollback_adapter_v13 import (
    apply_current_route_identity_contract_v13,
)
from .current_package_route_selection_rollback_rehearsal_v13 import (
    EXPECTED_CHECKS as C25_EXPECTED_CHECKS,
)
from .current_package_service_quiescence_rehearsal_v8 import (
    validate_stage_c21_evidence,
)
from .current_package_systemd_reload_rollback_rehearsal_v10 import (
    validate_stage_c23_evidence,
    write_input_binding,
)
from .current_package_systemd_reload_rollback_rehearsal_v12 import (
    emit_pre_live_diagnostics_v12,
)
from .current_package_terminal_install_adapter_v16 import (
    ACTIVE_ROUTE,
    COMMITTED_INSTALL_ROOT,
    CurrentPackageTerminalInstallAdapterV16,
    RUNTIME_HELPER,
    SPLIT_ROUTE,
)
from .package_review import sha256
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    TransactionAction,
)
from .production_prepare_only_inspector_v7 import ProductionPrepareOnlyInspectorV7
from .read_only_host_adapter import ReadOnlyHostProductionAdapter
from .sandbox_transaction import tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "INSTALL-AND-ENABLE-STAGE-C-EQ"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c-terminal-install."
C25_PREFIX = "a-clockwork-plex-stage-c25-current-package-route-rollback."
TERMINAL_TRANSACTION_PREFIX = "stage-c-terminal-eq-install-"
TERMINAL_SNAPSHOT_PREFIX = "stage-c-terminal-eq-snapshot-"

EXPECTED_CHECKS = (
    "root-scope",
    "input-replay",
    "c25-final-checkpoint",
    "pre-lock-live-baseline",
    "production-lock-acquired",
    "authoritative-transaction-created",
    "snapshot-complete",
    "candidate-validated",
    "service-quiescence",
    "dac-release",
    "managed-file-installation",
    "systemd-candidate-reload",
    "split-bus-route-selection",
    "temporary-approval-and-runtime",
    "finite-lane-probes",
    "application-restoration",
    "terminal-commit-publication",
    "managed-boot-enablement",
    "production-lock-released",
    "post-commit-health",
    "input-integrity",
    "evidence-integrity",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install, verify, commit and enable the fixed Stage C split-bus EQ package."
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--stage-c21-root", required=True, type=Path)
    parser.add_argument("--stage-c22-root", required=True, type=Path)
    parser.add_argument("--stage-c23-root", required=True, type=Path)
    parser.add_argument("--stage-c25-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args(argv)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"empty TSV: {path}")
    headers = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) != len(headers):
            raise SystemExit(f"invalid TSV row: {path}")
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


def validate_c25_evidence(raw: Path, invoking_uid: int, package_sha256: str) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=C25_PREFIX,
        invoking_uid=invoking_uid,
        label="accepted final C25 rollback evidence",
    )
    results = _read_tsv(root / "results.tsv")
    observed = tuple(row.get("check", "") for row in results)
    if observed != C25_EXPECTED_CHECKS:
        raise SystemExit("C25 evidence check order changed")
    if any(row.get("result") != "PASS" for row in results):
        raise SystemExit("C25 evidence contains a non-PASS result")
    identity_rows = _read_tsv(root / "identity.tsv")
    identity = {row["item"]: row["value"] for row in identity_rows}
    expected = {
        "package_sha256": package_sha256,
        "managed_files_installed": "true",
        "systemd_reloaded": "true",
        "split_bus_route_selected": "true",
        "active_route_restored": "true",
        "filesystem_restored": "true",
        "systemd_manager_restored": "true",
        "services_restored": "true",
        "daemon_reload_attempts": "2",
        "route_selection_count": "1",
        "managed_stage_c_services_started": "false",
        "audio_probe_opened": "false",
        "approval_published": "false",
        "committed": "false",
        "reusable_for_activation": "false",
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise SystemExit(f"C25 evidence identity mismatch: {key}")
    report = (root / "report.txt").read_text(encoding="utf-8")
    if "Final transaction state: current-package-route-rolled-back-and-closed" not in report:
        raise SystemExit("C25 final transaction state is not accepted")
    if "This is the final rollback-only checkpoint" not in report:
        raise SystemExit("C25 final-checkpoint declaration is absent")
    manifest = root / "evidence-manifest.tsv"
    if not manifest.is_file() or manifest.is_symlink():
        raise SystemExit("C25 deterministic evidence manifest is unavailable")
    return root


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="terminal Stage C install evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("terminal install evidence root must be empty")
    return root


def apply_terminal_identity_contract() -> None:
    apply_current_route_identity_contract_v13()
    current = (
        current_v7.CURRENT_TRANSACTION_PREFIX,
        current_v7.CURRENT_SNAPSHOT_PREFIX,
    )
    c25 = (
        "stage-c25-current-package-route-rollback-install-",
        "stage-c25-current-package-route-rollback-snapshot-",
    )
    target = (TERMINAL_TRANSACTION_PREFIX, TERMINAL_SNAPSHOT_PREFIX)
    if current == target:
        return
    if current != c25:
        raise SystemExit("current-package transaction identity contract changed")
    current_v7.CURRENT_TRANSACTION_PREFIX = TERMINAL_TRANSACTION_PREFIX
    current_v7.CURRENT_SNAPSHOT_PREFIX = TERMINAL_SNAPSHOT_PREFIX


def write_execution(output: Path, execution) -> None:
    output.write_text(
        json.dumps(
            {
                "outcome": execution.outcome.value,
                "approval": execution.approval.value,
                "failure_operation": (
                    execution.failure_operation.value
                    if execution.failure_operation is not None
                    else None
                ),
                "rollback_failure_operation": (
                    execution.rollback_failure_operation.value
                    if execution.rollback_failure_operation is not None
                    else None
                ),
                "exact_rollback_verified": execution.exact_rollback_verified,
                "lock_held": execution.lock_held,
                "records": [jsonable(record) for record in execution.records],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_identity(output: Path, transaction, adapter) -> None:
    output.write_text(
        "item\tvalue\n"
        f"transaction\t{transaction.transaction.value}\n"
        f"snapshot\t{transaction.snapshot.value}\n"
        f"package_sha256\t{transaction.package.sha256}\n"
        f"host\t{platform.node()}\n"
        f"architecture\t{platform.machine()}\n"
        "managed_files_installed\ttrue\n"
        "systemd_reloaded\ttrue\n"
        "split_bus_route_selected\ttrue\n"
        "managed_stage_c_services_started\ttrue\n"
        "finite_music_probe\ttrue\n"
        "finite_alarm_probe\ttrue\n"
        "application_services_restored\ttrue\n"
        "approval_phase\tcommitted\n"
        "boot_eligible\ttrue\n"
        "managed_units_enabled\ttrue\n"
        "committed\ttrue\n"
        f"commit_manifest_sha256\t{adapter.commit_manifest_sha256}\n"
        f"committed_install_root\t{adapter.committed_install_root}\n"
        "reboot_verification\tpending\n"
        "pr_ready_or_merged\tfalse\n",
        encoding="utf-8",
    )


def write_report(output: Path, evidence_root: Path, transaction, adapter) -> None:
    output.write_text(
        f"""A Clockwork Plex guarded persistent Stage C EQ installation
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Commit manifest SHA-256: {adapter.commit_manifest_sha256}
Committed install root: {adapter.committed_install_root}
Final state: committed-stage-c-eq-install
Approval phase: committed
Boot eligible: true
Managed units enabled: true
Production lock released: true

Installed and verified:
- all 28 fixed managed files and the exact activation-capable runtime package
- persistent snd_aloop module loading and fixed index/options configuration
- one atomic split-bus active-route selection
- guarded route authority and Type=notify CamillaDSP supervisor
- finite music-lane and independent alarm-lane probes
- restored Plexamp, AirPlay and dashboard services under the managed EQ graph
- durable pre-EQ active-route inode and authoritative uninstall snapshot
- one boot-eligible committed approval as the sole terminal commit marker

Still pending:
- one controlled reboot and post-boot verification
- final release review
- explicit PR readiness or merge approval
""",
        encoding="utf-8",
    )


def _require_enabled(unit: str) -> None:
    result = os.popen(f"systemctl is-enabled {unit}").read().strip()
    if result != "enabled":
        raise SystemExit(f"managed unit is not enabled: {unit} ({result})")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(f"terminal install requires --confirm {REQUIRED_CONFIRMATION}")

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
    stage_c25_root = validate_c25_evidence(
        args.stage_c25_root,
        invoking_uid,
        package.sha256,
    )

    input_roots = {
        "package": package_root,
        "baseline": baseline_root,
        "stage-c21": stage_c21_root,
        "stage-c22": stage_c22_root,
        "stage-c23": stage_c23_root,
        "stage-c25": stage_c25_root,
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
    apply_terminal_identity_contract()

    os.chown(evidence_root, 0, 0)
    evidence_root.chmod(0o700)
    results = evidence_root / "results.tsv"
    events = evidence_root / "lock-events.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")
    events.write_text(
        "order\tmonotonic_ns\twall_time\tevent\tdetail\n",
        encoding="utf-8",
    )
    append_result(
        results,
        "root-scope",
        "fixed current package, canonical lock, one transaction, one active route and one committed-install root",
    )
    append_result(results, "input-replay", "accepted package and C21-C23 evidence replayed")
    append_result(results, "c25-final-checkpoint", "accepted 29-check C25 exact rollback evidence replayed")
    append_result(results, "pre-lock-live-baseline", "all six fixed live observations are baseline-ready")
    write_input_binding(
        evidence_root / "input-binding.tsv",
        package_root,
        baseline_root,
        stage_c21_root,
        stage_c22_root,
        stage_c23_root,
    )
    (evidence_root / "stage-c25-binding.tsv").write_text(
        "item\tvalue\n"
        f"path\t{stage_c25_root}\n"
        f"tree_fingerprint\t{input_fingerprints['stage-c25']}\n",
        encoding="utf-8",
    )

    adapter = CurrentPackageTerminalInstallAdapterV16(
        package_root,
        invoking_user,
        evidence_root,
        accepted_c25_evidence=stage_c25_root,
    )
    transaction = None
    execution = None
    prefix_complete = False
    try:
        require_pass(
            adapter.inspect_host_contract(),
            AdapterOperation.INSPECT_HOST_CONTRACT,
        )
        observed_lock = require_pass(
            adapter.inspect_production_lock(),
            AdapterOperation.INSPECT_PRODUCTION_LOCK,
        )
        if observed_lock.exists:
            raise SystemExit("production lock must begin absent")
        lease = require_pass(
            adapter.acquire_production_lock(),
            AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
        )
        append_result(results, "production-lock-acquired", lease.lease_id)
        append_event(events, 10, "production-lock-acquired", lease.lease_id)

        transaction = require_pass(
            adapter.create_authoritative_transaction(TransactionAction.INSTALL, package),
            AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
        )
        if not transaction.transaction.value.startswith(TERMINAL_TRANSACTION_PREFIX):
            raise SystemExit("terminal transaction prefix changed")
        append_result(
            results,
            "authoritative-transaction-created",
            transaction.transaction.value,
        )
        write_parent_states(evidence_root / "parent-state.tsv", adapter.parent_states)

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
            raise SystemExit("terminal filesystem snapshot is not authoritative")
        validate_snapshot_payloads_against_accepted_v7(services, mixer, loopback, dac)
        append_result(results, "snapshot-complete", "five authoritative domains captured exactly")

        require_receipt(
            adapter.stage_candidate_files(transaction.transaction, package),
            AdapterOperation.STAGE_CANDIDATE_FILES,
        )
        if adapter.candidate_root is None:
            raise SystemExit("candidate root is unavailable")
        validate_candidate_manifest_v7(package_root, adapter.candidate_root)
        for operation, call in (
            (AdapterOperation.VALIDATE_CANDIDATE_ALSA, adapter.validate_candidate_alsa),
            (AdapterOperation.VALIDATE_CANDIDATE_SUDOERS, adapter.validate_candidate_sudoers),
            (AdapterOperation.VALIDATE_CANDIDATE_UNITS, adapter.validate_candidate_units),
            (AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP, adapter.validate_candidate_camilladsp),
        ):
            require_receipt(call(transaction.transaction), operation)
        append_result(results, "candidate-validated", "all 28 files and four private validation domains passed")

        require_receipt(
            adapter.stop_captured_application_services(transaction.transaction, services),
            AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
        )
        append_result(results, "service-quiescence", "Plexamp, AirPlay and dashboard stopped")
        require_receipt(
            adapter.verify_dac_released(transaction.transaction),
            AdapterOperation.VERIFY_DAC_RELEASED,
        )
        append_result(results, "dac-release", "physical and loopback endpoints released")
        require_receipt(
            adapter.install_managed_files(transaction.transaction),
            AdapterOperation.INSTALL_MANAGED_FILES,
        )
        append_result(results, "managed-file-installation", "all 28 fixed files installed")
        require_receipt(
            adapter.reload_systemd(transaction.transaction),
            AdapterOperation.RELOAD_SYSTEMD,
        )
        if adapter.systemd_reload_attempt_count != 1:
            raise SystemExit("terminal install requires exactly one pre-commit daemon reload")
        append_result(results, "systemd-candidate-reload", "three managed units loaded inactive")
        require_receipt(
            adapter.select_split_bus_route(transaction.transaction),
            AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
        )
        append_result(results, "split-bus-route-selection", "reviewed split route selected once")
        prefix_complete = True

        execution = execute_activation_commit_v7(
            adapter,
            ActivationExecutionContextV7(
                transaction=transaction,
                services=services,
                mixer=mixer,
            ),
        )
        write_execution(evidence_root / "activation-execution.json", execution)

        if execution.outcome is ActivationExecutionOutcomeV7.COMMITTED:
            append_result(results, "temporary-approval-and-runtime", "temporary approval started route and CamillaDSP authorities")
            append_result(results, "finite-lane-probes", "music and independent alarm lanes opened and closed finitely")
            append_result(results, "application-restoration", "Plexamp, AirPlay and dashboard restored under split bus")
            append_result(results, "terminal-commit-publication", "durable snapshot and committed approval published atomically")
            append_result(results, "managed-boot-enablement", "route authority and CamillaDSP supervisor enabled")
            append_result(results, "production-lock-released", "terminal executor released the exact lock after commit")
        elif execution.outcome is ActivationExecutionOutcomeV7.EXACTLY_ROLLED_BACK:
            raise SystemExit(
                "terminal install failed before commit and completed exact rollback: "
                f"{execution.failure_operation.value if execution.failure_operation else 'unknown'}"
            )
        else:
            raise SystemExit(
                "terminal install retained authority for inspection: "
                f"{execution.outcome.value}"
            )

    except BaseException:
        if execution is None and adapter.lock_held:
            adapter.__exit__(*sys.exc_info())
        raise

    if not prefix_complete or transaction is None or execution is None:
        raise SystemExit("terminal install did not reach a final execution result")
    if not adapter.terminal_committed:
        raise SystemExit("terminal adapter did not retain committed state")

    approval = ApprovalStore(Path("/var/lib/a-clockwork-plex/split-bus")).read()
    if approval.phase is not ApprovalPhase.COMMITTED:
        raise SystemExit("installed approval is not committed")
    if approval.package_fingerprint != package.sha256:
        raise SystemExit("committed approval package fingerprint changed")
    if sha256(ACTIVE_ROUTE) != sha256(SPLIT_ROUTE):
        raise SystemExit("active route is not the installed split-bus route")
    if not COMMITTED_INSTALL_ROOT.is_dir() or COMMITTED_INSTALL_ROOT.is_symlink():
        raise SystemExit("committed install root is unavailable")
    for unit in (
        "a-clockwork-plex-audio-route.service",
        "a-clockwork-plex-camilladsp.service",
    ):
        _require_enabled(unit)
        active = os.popen(f"systemctl is-active {unit}").read().strip()
        if active != "active":
            raise SystemExit(f"managed unit is not active: {unit} ({active})")
    for unit in (
        "plexamp.service",
        "shairport-sync.service",
        "a-clockwork-plex.service",
    ):
        active = os.popen(f"systemctl is-active {unit}").read().strip()
        if active != "active":
            raise SystemExit(f"application unit is not active: {unit} ({active})")
    status = os.popen(f"{RUNTIME_HELPER} status").read()
    payload = json.loads(status)
    if payload.get("ok") is not True or payload.get("approval_status") != "valid":
        raise SystemExit("installed runtime status is not healthy")
    append_result(results, "post-commit-health", "committed approval, split route, managed runtime and applications are healthy")

    for label, root in input_roots.items():
        if tree_fingerprint(root) != input_fingerprints[label]:
            raise SystemExit(f"retained input changed during terminal install: {label}")
    append_result(results, "input-integrity", "package and all accepted evidence roots remained unchanged")

    write_identity(evidence_root / "identity.tsv", transaction, adapter)
    write_report(evidence_root / "report.txt", evidence_root, transaction, adapter)
    write_evidence_manifest(evidence_root)
    append_result(results, "evidence-integrity", "terminal evidence tree sealed with deterministic manifest")
    write_evidence_manifest(evidence_root)

    observed_checks = tuple(
        line.split("\t", 1)[0]
        for line in results.read_text(encoding="utf-8").splitlines()[1:]
    )
    if observed_checks != EXPECTED_CHECKS:
        raise SystemExit(f"terminal result order changed: {observed_checks}")

    chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
    evidence_root.chmod(0o700)
    print(
        f"""A Clockwork Plex persistent Stage C EQ installation committed.

  Evidence:          {evidence_root}
  Committed install: {adapter.committed_install_root}
  Manifest SHA-256:  {adapter.commit_manifest_sha256}
  Approval phase:    committed
  Managed runtime:   active and enabled
  Application audio: restored under split bus

The EQ installation is now persistent.  One controlled reboot and post-boot
verification remain before final release review.  PR #2 remains Draft and
unmerged.""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
