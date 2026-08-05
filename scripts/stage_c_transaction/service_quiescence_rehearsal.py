#!/usr/bin/python3
from __future__ import annotations

"""Stage C17 root-owned service-quiescence and exact-restoration rehearsal."""

import argparse
import json
import os
import platform
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
from .candidate_validation_rehearsal import (
    EXPECTED_CHECKS as STAGE_C16_CHECKS,
    validate_candidate_manifest,
    write_blocked_operations,
)
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    ProductionAdapterBlocked,
    ServiceActiveState,
    ServiceSnapshot,
    ServiceUnit,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v2 import (
    TransactionLifecycleOperation,
)
from .production_adapter_lifecycle_v3 import (
    ProductionAdapterV3,
    RestoredRehearsalLifecycleOperation,
)
from .production_plan import _validate_evidence_manifest
from .sandbox_transaction import _read_tsv, tree_fingerprint
from .service_quiescence_rehearsal_adapter import (
    BLOCKED_V3_COUNT,
    PERMITTED_V1_OPERATIONS,
    ServiceQuiescenceRehearsalAdapter,
)
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C17-SERVICE-QUIESCE-RESTORE"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c17-service-quiescence."
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
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage C17 candidate validation, briefly stop only captured-active "
            "application services, prove DAC release, restore exact application "
            "state and close the restored rehearsal transaction."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c16-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C17 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C17 evidence root must be empty")
    return root


def validate_stage_c16(root: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        root,
        prefix="a-clockwork-plex-stage-c16-candidate-validation.",
        invoking_uid=invoking_uid,
        label="Stage C16 evidence",
    )
    _validate_evidence_manifest(root, "Stage C16")
    rows = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in rows) != STAGE_C16_CHECKS:
        raise SystemExit(
            "Stage C16 evidence does not contain the exact twenty-nine checks"
        )
    if any(row.get("result") != "PASS" for row in rows):
        raise SystemExit("Stage C16 evidence contains a non-PASS result")
    blocked = _read_tsv(root / "blocked-operations.tsv")
    if len(blocked) != 18 or any(
        row.get("state") != "blocked" for row in blocked
    ):
        raise SystemExit("Stage C16 blocked-operation evidence changed")
    identity = {
        row.get("item", ""): row.get("value", "")
        for row in _read_tsv(root / "identity.tsv")
    }
    if (
        identity.get("mutation_started") != "false"
        or identity.get("committed") != "false"
        or identity.get("reusable_after_abort") != "false"
    ):
        raise SystemExit(
            "Stage C16 transaction identity is not a pre-mutation aborted rehearsal"
        )
    for name in ("candidate-review-copy", "transaction-rehearsal-copy"):
        if not (root / name).is_dir():
            raise SystemExit(f"Stage C16 review evidence is missing: {name}")
    report = (root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "Final transaction state: aborted-before-mutation and removed",
        "service stop or DAC release",
        "Persistent Stage C activation remains blocked.",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C16 report contract is missing: {marker}")
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
                f"blocked identity mismatch: expected {operation.value}, "
                f"found {exc.operation.value}"
            ) from exc
        rows.append((operation.value, "blocked"))
        return
    raise SystemExit(
        f"operation unexpectedly became executable: {operation.value}"
    )


def prove_blocked_operations(
    adapter: ServiceQuiescenceRehearsalAdapter,
    *,
    transaction: TransactionIdentity,
    services: ServiceSnapshot,
    mixer,
    snapshot: SnapshotIdentity,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
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
    expected = set(AdapterOperation).difference(PERMITTED_V1_OPERATIONS)
    observed = {
        AdapterOperation(operation)
        for operation, state in rows
        if state == "blocked"
    }
    if observed != expected or len(rows) != BLOCKED_V3_COUNT:
        raise SystemExit(
            "blocked-operation coverage changed: "
            f"expected={BLOCKED_V3_COUNT} observed={len(rows)}"
        )
    return rows


def write_identity(
    output: Path,
    transaction,
    lease_id: str,
    invoking_user: str,
    *,
    mutation_started: bool,
    restored: bool,
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
        "candidate_production_authoritative\tfalse\n"
        f"mutation_started\t{str(mutation_started).lower()}\n"
        f"restored\t{str(restored).lower()}\n"
        "committed\tfalse\n"
        "reusable_for_activation\tfalse\n"
        "reusable_for_rollback\tfalse\n",
        encoding="utf-8",
    )


def write_report(
    output: Path,
    evidence_root: Path,
    transaction,
    blocked_count: int,
    restored_services: tuple[ServiceUnit, ...],
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C17 service-quiescence and restoration rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
V3 permitted operations: 21
V3 blocked operations: {blocked_count}
Final transaction state: rehearsal-restored-and-closed
Restored application services: {','.join(unit.value for unit in restored_services)}

Proved:
- exact Stage C1 package and successful physical Stage C16 evidence replay
- real production lock and fresh authoritative five-domain snapshot
- transaction-private staging and all four candidate validation domains
- only captured-active Plexamp, Shairport Sync and dashboard services stopped
- physical DAC and fixed loopback endpoints released
- managed installation, route, mixer, unit and audio operations remained blocked
- exact captured application service state restored without enablement changes
- stable direct ALSA route, mixer, loopback and physical DAC ownership restored
- dashboard root returned healthy HTTP after restart
- pre-mutation abort refused after the mutation boundary
- v3 restored-rehearsal closure retained non-authoritative evidence and removed
  the exact transaction before production-lock release

Not proved:
- production managed-file installation or systemd daemon reload
- active split-bus route selection or managed Stage C service startup
- CamillaDSP runtime health or finite music/alarm probes
- installation commit or automatic exact rollback after file mutation
- runtime direct failback, explicit uninstall or reboot persistence

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Stage C17 rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_owned_root(
        args.package_root,
        prefix="a-clockwork-plex-stage-c1-review-",
        invoking_uid=invoking_uid,
        label="Stage C1 package",
    )
    stage_c16_root = validate_stage_c16(args.stage_c16_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    inputs = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c16": tree_fingerprint(stage_c16_root),
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
        append_result(
            results,
            "root-scope",
            (
                f"root writes constrained to {evidence_root}, the fixed lock "
                "and disposable transaction"
            ),
        )
        append_result(
            results,
            "input-replay",
            "Stage C1 package and successful physical Stage C16 evidence replayed",
        )

        with ServiceQuiescenceRehearsalAdapter(
            package_root,
            invoking_user,
            evidence_root,
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV3):
                raise SystemExit(
                    "Stage C17 adapter does not conform to ProductionAdapterV3"
                )
            append_result(
                results,
                "protocol-conformance",
                (
                    "adapter exposes nineteen v1 operations, v2 pre-mutation "
                    "abort and v3 restored-rehearsal closure"
                ),
            )

            host_result = adapter.inspect_host_contract()
            require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(
                results,
                "pre-lock-host-contract",
                "stable aarch64 direct route and fixed host contract verified",
            )
            lock_result = adapter.inspect_production_lock()
            lock = require_pass(
                lock_result,
                AdapterOperation.INSPECT_PRODUCTION_LOCK,
            )
            if lock.exists or lock.held_by_caller:
                raise SystemExit("production lock must begin absent")
            append_result(
                results,
                "pre-lock-boundary",
                f"{lock.path} absent and unopened",
            )

            acquire_result = adapter.acquire_production_lock()
            lease = require_pass(
                acquire_result,
                AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-acquired",
                f"adapter-generated lease {lease.lease_id}",
            )
            append_event(
                events,
                10,
                "production-lock-acquired",
                lease.lease_id,
            )

            create_result = adapter.create_authoritative_transaction(
                TransactionAction.INSTALL,
                package,
            )
            transaction = require_pass(
                create_result,
                AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
            )
            append_result(
                results,
                "authoritative-transaction-created",
                f"fresh transaction {transaction.transaction.value}",
            )
            if adapter.authoritative_transaction != transaction:
                raise SystemExit(
                    "authoritative transaction identity binding failed"
                )
            append_result(
                results,
                "transaction-identity-binding",
                (
                    "transaction, snapshot, package, action and held lease "
                    "are adapter-bound"
                ),
            )
            write_identity(
                evidence_root / "identity.tsv",
                transaction,
                lease.lease_id,
                invoking_user,
                mutation_started=False,
                restored=False,
            )
            write_parent_states(
                evidence_root / "parent-state.tsv",
                adapter.parent_states,
            )

            filesystem_result = adapter.capture_filesystem_state(
                transaction.transaction
            )
            filesystem = require_pass(
                filesystem_result,
                AdapterOperation.CAPTURE_FILESYSTEM_STATE,
            )
            if (
                filesystem.identity != transaction.snapshot
                or not filesystem.exact
            ):
                raise SystemExit(
                    "filesystem snapshot identity is not authoritative"
                )
            append_result(
                results,
                "filesystem-snapshot",
                "current ALSA and all managed destination states captured exactly",
            )

            service_result = adapter.capture_service_state(
                transaction.transaction
            )
            services = require_pass(
                service_result,
                AdapterOperation.CAPTURE_SERVICE_STATE,
            )
            validate_service_snapshot(services)
            active_apps = tuple(
                state.unit
                for state in services.services
                if state.unit
                in {
                    ServiceUnit.PLEXAMP,
                    ServiceUnit.SHAIRPORT_SYNC,
                    ServiceUnit.DASHBOARD,
                }
                and state.active is ServiceActiveState.ACTIVE
            )
            if set(active_apps) != {
                ServiceUnit.PLEXAMP,
                ServiceUnit.SHAIRPORT_SYNC,
                ServiceUnit.DASHBOARD,
            }:
                raise SystemExit(
                    "Stage C17 requires all three application services active"
                )
            append_result(
                results,
                "service-snapshot",
                "exact six-service state captured; all three application services active",
            )

            mixer_result = adapter.capture_mixer_state(
                transaction.transaction
            )
            mixer = require_pass(
                mixer_result,
                AdapterOperation.CAPTURE_MIXER_STATE,
            )
            append_result(
                results,
                "mixer-snapshot",
                "exact four-control mixer state captured",
            )
            loopback_result = adapter.capture_loopback_state(
                transaction.transaction
            )
            loopback = require_pass(
                loopback_result,
                AdapterOperation.CAPTURE_LOOPBACK_STATE,
            )
            if not loopback.loaded:
                raise SystemExit(
                    "authoritative loopback snapshot is not loaded"
                )
            append_result(
                results,
                "loopback-snapshot",
                "exact snd_aloop state captured",
            )
            dac_result = adapter.capture_dac_state(
                transaction.transaction
            )
            dac = require_pass(
                dac_result,
                AdapterOperation.CAPTURE_DAC_STATE,
            )
            if dac.released or not dac.owners:
                raise SystemExit(
                    "authoritative DAC snapshot lacks the live owner"
                )
            append_result(
                results,
                "dac-snapshot",
                (
                    f"exact DAC format and {len(dac.owners)} "
                    "structured owner(s) captured"
                ),
            )
            append_result(
                results,
                "snapshot-integrity",
                "all five authoritative snapshot domains completed under one identity",
            )

            stage_result = adapter.stage_candidate_files(
                transaction.transaction,
                package,
            )
            if stage_result.status is not AdapterStatus.PASS:
                raise SystemExit(
                    f"candidate staging failed: {stage_result.detail}"
                )
            append_result(
                results,
                "candidate-staging",
                "twelve files atomically staged only inside the transaction candidate root",
            )
            if adapter.candidate_root is None:
                raise SystemExit(
                    "candidate root was not retained by the adapter"
                )
            validate_candidate_manifest(
                package_root,
                adapter.candidate_root,
            )
            append_result(
                results,
                "candidate-manifest-binding",
                (
                    "all staged paths, modes, owners and digests match "
                    "the Stage C1 manifest"
                ),
            )

            validation_results = []
            for operation, call, check, detail in (
                (
                    AdapterOperation.VALIDATE_CANDIDATE_ALSA,
                    adapter.validate_candidate_alsa,
                    "candidate-alsa-validation",
                    "both staged routes parsed privately; no PCM opened",
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
                    adapter.validate_candidate_sudoers,
                    "candidate-sudoers-validation",
                    "staged restricted rules accepted by visudo",
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
                    adapter.validate_candidate_units,
                    "candidate-unit-validation",
                    (
                        "three staged units and inert helper passed "
                        "private verification"
                    ),
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
                    adapter.validate_candidate_camilladsp,
                    "candidate-camilladsp-validation",
                    (
                        "digest-pinned binary accepted staged config "
                        "without audio"
                    ),
                ),
            ):
                result = call(transaction.transaction)
                if (
                    result.operation is not operation
                    or result.status is not AdapterStatus.PASS
                ):
                    raise SystemExit(
                        f"{operation.value} failed: {result.detail}"
                    )
                validation_results.append(result)
                append_result(results, check, detail)

            blocked = prove_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
                snapshot=transaction.snapshot,
            )
            write_blocked_operations(
                evidence_root / "blocked-operations.tsv",
                blocked,
            )
            append_result(
                results,
                "blocked-operation-boundary",
                (
                    f"all {len(blocked)} install, route, audio, commit and "
                    "rollback operations refused exactly"
                ),
            )

            stop_result = adapter.stop_captured_application_services(
                transaction.transaction,
                services,
            )
            require_receipt(
                stop_result,
                AdapterOperation.STOP_CAPTURED_APPLICATION_SERVICES,
            )
            append_result(
                results,
                "service-quiescence",
                (
                    "only captured-active Plexamp, Shairport Sync and "
                    "dashboard services stopped"
                ),
            )
            append_event(
                events,
                20,
                "application-services-stopped",
                ",".join(unit.value for unit in adapter.stopped_services),
            )

            release_dac_result = adapter.verify_dac_released(
                transaction.transaction
            )
            require_receipt(
                release_dac_result,
                AdapterOperation.VERIFY_DAC_RELEASED,
            )
            append_result(
                results,
                "dac-release",
                (
                    "physical DAC and fixed loopback endpoints have no owners"
                ),
            )

            critical_rows: list[tuple[str, str]] = []
            _expect_blocked(
                critical_rows,
                AdapterOperation.INSTALL_MANAGED_FILES,
                lambda: adapter.install_managed_files(
                    transaction.transaction
                ),
            )
            append_result(
                results,
                "pre-install-boundary",
                (
                    "managed-file installation remained blocked after "
                    "DAC release"
                ),
            )

            restore_result = adapter.restore_captured_application_services(
                transaction.transaction,
                services,
            )
            require_receipt(
                restore_result,
                AdapterOperation.RESTORE_CAPTURED_APPLICATION_SERVICES,
            )
            append_result(
                results,
                "application-service-restoration",
                "captured application service state restored exactly",
            )
            append_event(
                events,
                30,
                "application-services-restored",
                ",".join(unit.value for unit in active_apps),
            )

            dashboard_result = adapter.verify_dashboard_health(
                transaction.transaction
            )
            require_receipt(
                dashboard_result,
                AdapterOperation.VERIFY_DASHBOARD_HEALTH,
            )
            append_result(
                results,
                "dashboard-health",
                (
                    "stable route, mixer, loopback, DAC ownership and "
                    "dashboard HTTP health verified"
                ),
            )
            append_result(
                results,
                "exact-restoration-boundary",
                (
                    "service quiescence ended with the accepted direct "
                    "appliance state restored"
                ),
            )

            abort_result = adapter.abort_uncommitted_transaction(
                transaction.transaction
            )
            if (
                abort_result.operation
                is not TransactionLifecycleOperation.
                ABORT_UNCOMMITTED_TRANSACTION
                or abort_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit(
                    "pre-mutation abort did not refuse after mutation"
                )
            append_result(
                results,
                "pre-mutation-abort-refusal",
                (
                    "v2 pre-mutation abort refused after the service "
                    "mutation boundary"
                ),
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
                stop_result,
                release_dac_result,
                restore_result,
                dashboard_result,
            )
            (evidence_root / "typed-operations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "mutation_started": True,
                        "restored": True,
                        "committed": False,
                        "operations": [
                            jsonable(result) for result in typed
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            premature = adapter.release_production_lock()
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit(
                    "production lock release did not refuse the open transaction"
                )
            close_result = adapter.close_restored_rehearsal_transaction(
                transaction.transaction
            )
            if (
                close_result.operation
                is not RestoredRehearsalLifecycleOperation.
                CLOSE_RESTORED_REHEARSAL_TRANSACTION
                or close_result.status is not AdapterStatus.PASS
                or close_result.payload is None
            ):
                raise SystemExit(
                    "v3 restored-rehearsal closure failed: "
                    f"{close_result.detail}"
                )
            if (
                adapter.candidate_review_copy is not None
                and not adapter.candidate_review_copy.is_dir()
            ):
                raise SystemExit(
                    "candidate review evidence path became invalid"
                )
            candidate_copy = evidence_root / "candidate-review-copy"
            if not candidate_copy.is_dir():
                raise SystemExit(
                    "candidate review evidence copy is missing"
                )
            append_result(
                results,
                "candidate-evidence-copy",
                (
                    "validated candidate and service rehearsal retained "
                    f"non-authoritatively at {candidate_copy}"
                ),
            )
            append_result(
                results,
                "restored-transaction-close-v3",
                (
                    "typed v3 closure accepted only the adapter-generated "
                    "restored transaction"
                ),
            )
            if (
                adapter.transaction_path is not None
                or Path(close_result.payload.audit_evidence)
                != evidence_root
                or not close_result.payload.transaction_path_absent
                or not close_result.payload.parents_restored
            ):
                raise SystemExit(
                    "v3 closure did not finish exact transaction cleanup"
                )
            append_result(
                results,
                "exact-transaction-cleanup",
                (
                    "candidate, validation root and authoritative transaction "
                    "removed; parent state restored"
                ),
            )
            append_event(
                events,
                40,
                "restored-transaction-closed",
                transaction.transaction.value,
            )

            write_identity(
                evidence_root / "identity.tsv",
                transaction,
                lease.lease_id,
                invoking_user,
                mutation_started=True,
                restored=True,
            )
            release_result = adapter.release_production_lock()
            require_receipt(
                release_result,
                AdapterOperation.RELEASE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-released",
                (
                    "exact production lock removed only after restored "
                    "transaction closure"
                ),
            )
            append_event(
                events,
                50,
                "production-lock-released",
                lease.lease_id,
            )
            write_report(
                evidence_root / "report.txt",
                evidence_root,
                transaction,
                len(blocked),
                close_result.payload.restored_services,
            )

        for label, root in (
            ("stage-c1", package_root),
            ("stage-c16", stage_c16_root),
        ):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(
                    f"{label} input changed during Stage C17"
                )
        append_result(
            results,
            "input-integrity",
            "Stage C1 and Stage C16 input trees remained unchanged",
        )
        write_evidence_manifest(evidence_root)
        append_result(
            results,
            "evidence-integrity",
            (
                "complete checksummed evidence tree contains no symlink "
                "or special object"
            ),
        )
        append_result(
            results,
            "activation-interface",
            (
                "absent; services restored and transaction closed before "
                "installation or route mutation"
            ),
        )
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(
                encoding="utf-8"
            ).splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(
                f"unexpected Stage C17 result order: {observed}"
            )
        completed = True
    finally:
        chown_evidence_tree(
            evidence_root,
            invoking_uid,
            invoking_gid,
        )
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit(
            "Stage C17 service-quiescence rehearsal did not complete"
        )
    print(
        f"""
A Clockwork Plex Stage C17 service-quiescence rehearsal passed.

  Directory:          {evidence_root}
  Results:            {evidence_root / 'results.tsv'}
  Identity:           {evidence_root / 'identity.tsv'}
  Service actions:    {evidence_root / 'service-actions.tsv'}
  Typed operations:   {evidence_root / 'typed-operations.json'}
  Blocked operations: {evidence_root / 'blocked-operations.tsv'}
  Candidate copy:     {evidence_root / 'candidate-review-copy'}
  Transaction copy:   {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:  {evidence_root / 'evidence-manifest.tsv'}
  Report:             {evidence_root / 'report.txt'}

The three captured-active application services were briefly stopped, the DAC was
proved released, and the exact captured application state was restored. No file,
route, mixer, managed Stage C service or audio-probe mutation was available.
The restored transaction was closed and the production lock released. Persistent
Stage C activation remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
