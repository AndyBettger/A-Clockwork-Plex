#!/usr/bin/python3
from __future__ import annotations

"""Stage C20 root-owned split-bus route-selection exact-rollback rehearsal."""

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
    validate_candidate_manifest,
    write_blocked_operations,
)
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
    RestoredRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v4 import (
    ExactRollbackRehearsalLifecycleOperation,
)
from .production_adapter_lifecycle_v5 import (
    SystemdReloadRollbackLifecycleOperation,
)
from .production_adapter_lifecycle_v6 import (
    ProductionAdapterV6,
    RouteSelectionRollbackLifecycleOperation,
)
from .production_plan import _validate_evidence_manifest
from .route_selection_rollback_rehearsal_adapter import (
    BLOCKED_V6_COUNT,
    PERMITTED_V1_OPERATIONS,
    RouteSelectionRollbackRehearsalAdapter,
)
from .sandbox_transaction import _read_tsv, tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest
from .systemd_reload_rollback_rehearsal import (
    EXPECTED_CHECKS as STAGE_C19_CHECKS,
)


REQUIRED_CONFIRMATION = "STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK"
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c20-route-selection-rollback."
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
    "route-selection-gate",
    "service-quiescence",
    "dac-release",
    "managed-file-installation",
    "installed-manifest-binding",
    "systemd-candidate-reload",
    "managed-unit-visibility",
    "split-bus-route-selection",
    "selected-route-binding",
    "post-route-boundary",
    "active-route-restoration",
    "exact-filesystem-rollback",
    "systemd-manager-restoration",
    "managed-unit-forgetting",
    "application-service-restoration",
    "dashboard-health",
    "exact-rollback-verification",
    "exact-restoration-boundary",
    "pre-mutation-abort-refusal",
    "service-only-closure-refusal",
    "file-only-closure-refusal",
    "systemd-only-closure-refusal",
    "candidate-evidence-copy",
    "route-rollback-close-v6",
    "exact-transaction-cleanup",
    "production-lock-released",
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage C20: repeat the accepted C19 prefix, select the reviewed "
            "split-bus ALSA route by atomic inode exchange while services remain "
            "quiesced, prove all later operations remain blocked, restore the "
            "original active-route inode, then restore files, manager and services."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c19-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C20 evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C20 evidence root must be empty")
    return root


def validate_stage_c19(root: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        root,
        prefix="a-clockwork-plex-stage-c19-systemd-reload-rollback.",
        invoking_uid=invoking_uid,
        label="Stage C19 evidence",
    )
    _validate_evidence_manifest(root, "Stage C19")
    rows = _read_tsv(root / "results.tsv")
    if tuple(row.get("check", "") for row in rows) != STAGE_C19_CHECKS:
        raise SystemExit(
            "Stage C19 evidence does not contain the exact forty-five checks"
        )
    if any(row.get("result") != "PASS" for row in rows):
        raise SystemExit("Stage C19 evidence contains a non-PASS result")
    for name in (
        "blocked-operations.tsv",
        "post-reload-blocked-operations.tsv",
    ):
        blocked = _read_tsv(root / name)
        if len(blocked) != 10 or any(
            row.get("state") != "blocked" for row in blocked
        ):
            raise SystemExit(f"Stage C19 blocked-operation evidence changed: {name}")
    identity = {
        row.get("item", ""): row.get("value", "")
        for row in _read_tsv(root / "identity.tsv")
    }
    required_identity = {
        "mutation_started": "true",
        "managed_files_installed": "true",
        "systemd_reloaded": "true",
        "filesystem_restored": "true",
        "systemd_manager_restored": "true",
        "services_restored": "true",
        "daemon_reload_count": "2",
        "route_selected": "false",
        "committed": "false",
        "reusable_for_activation": "false",
        "reusable_for_rollback": "false",
    }
    for key, expected in required_identity.items():
        if identity.get(key) != expected:
            raise SystemExit(f"Stage C19 identity contract changed: {key}")
    for name in (
        "candidate-review-copy",
        "transaction-rehearsal-copy",
    ):
        path = root / name
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(f"Stage C19 review evidence is missing: {name}")
    for name in (
        "managed-file-actions.tsv",
        "service-actions.tsv",
        "systemd-reload-actions.tsv",
        "systemd-unit-observations.tsv",
        "restoration-readiness.tsv",
    ):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"Stage C19 audit evidence is missing: {name}")
    report = (root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "Final transaction state: systemd-reload-rolled-back-and-closed",
        "Installed file count: 12",
        "Daemon reload count: 2",
        "Systemd manager restored: true",
        "Route selected: false",
        "Persistent Stage C activation remains blocked.",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C19 report contract is missing: {marker}")
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
    adapter: RouteSelectionRollbackRehearsalAdapter,
    *,
    transaction,
    services,
    mixer,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for operation, call in (
        (
            AdapterOperation.START_MANAGED_STAGE_C_SERVICES,
            lambda: adapter.start_managed_stage_c_services(transaction),
        ),
        (
            AdapterOperation.STOP_MANAGED_STAGE_C_SERVICES,
            lambda: adapter.stop_managed_stage_c_services(transaction),
        ),
        (
            AdapterOperation.VERIFY_SPLIT_BUS_HEALTH,
            lambda: adapter.verify_split_bus_health(transaction),
        ),
        (
            AdapterOperation.RUN_FINITE_MUSIC_PROBE,
            lambda: adapter.run_finite_music_probe(transaction),
        ),
        (
            AdapterOperation.RUN_FINITE_ALARM_PROBE,
            lambda: adapter.run_finite_alarm_probe(transaction),
        ),
        (
            AdapterOperation.WRITE_COMMIT_MANIFEST,
            lambda: adapter.write_commit_manifest(transaction),
        ),
        (
            AdapterOperation.SELECT_DIRECT_FAILBACK_ROUTE,
            lambda: adapter.select_direct_failback_route(transaction),
        ),
        (
            AdapterOperation.RESTORE_MIXER_STATE,
            lambda: adapter.restore_mixer_state(transaction, mixer),
        ),
        (
            AdapterOperation.RESTORE_SERVICE_STATE,
            lambda: adapter.restore_service_state(transaction, services),
        ),
    ):
        _expect_blocked(rows, operation, call)
    expected = set(AdapterOperation).difference(PERMITTED_V1_OPERATIONS)
    observed = {
        AdapterOperation(operation)
        for operation, state in rows
        if state == "blocked"
    }
    if observed != expected or len(rows) != BLOCKED_V6_COUNT:
        raise SystemExit(
            "blocked-operation coverage changed: "
            f"expected={BLOCKED_V6_COUNT} observed={len(rows)}"
        )
    return rows


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
        "systemd_reloaded\ttrue\n"
        "split_bus_route_selected\ttrue\n"
        "active_route_restored\ttrue\n"
        "route_selection_count\t1\n"
        "filesystem_restored\ttrue\n"
        "systemd_manager_restored\ttrue\n"
        "services_restored\ttrue\n"
        "daemon_reload_count\t2\n"
        "route_selected\tfalse\n"
        "managed_stage_c_services_started\tfalse\n"
        "audio_probe_opened\tfalse\n"
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
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C20 split-bus route-selection exact-rollback rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
V6 permitted operations: 29
V6 blocked operations: {blocked_count}
Final transaction state: split-bus-route-rolled-back-and-closed
Installed file count: 12
Systemd reloaded: true
Daemon reload count: 2
Split-bus route selected: true
Route selection count: 1
Active route restored: true
Systemd manager restored: true
Managed Stage C services started: false
Audio probe opened: false
Route selected at completion: false
Committed: false

Proved:
- successful physical Stage C19 evidence and exact Stage C1 package replay
- real production lock and fresh authoritative five-domain snapshot
- transaction-private staging and all four candidate validation domains
- split-bus route selection refused before its exact prerequisites
- only captured-active Plexamp, Shairport Sync and dashboard services stopped
- physical DAC and fixed loopback endpoints released
- twelve managed files atomically installed and verified
- first fixed daemon reload exposed exactly three loaded inactive managed units
- reviewed split-bus route selected by one atomic inode exchange
- selected active route matched the transaction candidate inode and digest
- managed Stage C startup, health, probes, direct failback and commit stayed blocked
- original active-route inode atomically restored before managed-file rollback
- exact managed-file and created-directory rollback while services stayed stopped
- second fixed daemon reload removed all three managed units from manager state
- exact captured application-service state restored only after all rollback domains
- bounded dashboard and strict DAC runtime readiness
- zero filesystem, route, service, mixer, loopback or DAC rollback mismatch
- v2, v3, v4 and v5 lifecycle closures refused after route mutation
- typed v6 closure removed the transaction before lock release

Not proved:
- managed route-authority or CamillaDSP service startup
- split-bus runtime health with a live source
- finite music or alarm probes
- direct-failback route selection
- automatic CamillaDSP failure handling
- installation commit
- runtime failback, explicit uninstall or reboot persistence

Persistent Stage C activation remains blocked.
""",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            f"Stage C20 rehearsal requires --confirm {REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_owned_root(
        args.package_root,
        prefix="a-clockwork-plex-stage-c1-review-",
        invoking_uid=invoking_uid,
        label="Stage C1 package",
    )
    stage_c19_root = validate_stage_c19(args.stage_c19_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    inputs = {
        "stage-c1": tree_fingerprint(package_root),
        "stage-c19": tree_fingerprint(stage_c19_root),
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
                f"root writes constrained to {evidence_root}, the fixed lock, "
                "authoritative transaction, twelve manifest destinations and "
                "one private active-route exchange name"
            ),
        )
        append_result(
            results,
            "input-replay",
            "Stage C1 package and successful physical Stage C19 evidence replayed",
        )

        with RouteSelectionRollbackRehearsalAdapter(
            package_root,
            invoking_user,
            evidence_root,
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV6):
                raise SystemExit(
                    "Stage C20 adapter does not conform to ProductionAdapterV6"
                )
            append_result(
                results,
                "protocol-conformance",
                (
                    "adapter exposes twenty-four v1 operations plus v2, v3, "
                    "v4, v5 and v6 lifecycle methods"
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
            append_event(events, 10, "production-lock-acquired", lease.lease_id)

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
                raise SystemExit("authoritative transaction identity binding failed")
            append_result(
                results,
                "transaction-identity-binding",
                (
                    "transaction, snapshot, package, action and held lease "
                    "are adapter-bound"
                ),
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
            if filesystem.identity != transaction.snapshot or not filesystem.exact:
                raise SystemExit("filesystem snapshot identity is not authoritative")
            append_result(
                results,
                "filesystem-snapshot",
                "current active ALSA inode and all managed destination states captured exactly",
            )

            service_result = adapter.capture_service_state(transaction.transaction)
            services = require_pass(
                service_result,
                AdapterOperation.CAPTURE_SERVICE_STATE,
            )
            validate_service_snapshot(services)
            active_apps = {
                state.unit
                for state in services.services
                if state.unit
                in {
                    ServiceUnit.PLEXAMP,
                    ServiceUnit.SHAIRPORT_SYNC,
                    ServiceUnit.DASHBOARD,
                }
                and state.active is ServiceActiveState.ACTIVE
            }
            if active_apps != {
                ServiceUnit.PLEXAMP,
                ServiceUnit.SHAIRPORT_SYNC,
                ServiceUnit.DASHBOARD,
            }:
                raise SystemExit("Stage C20 requires all three application services active")
            append_result(
                results,
                "service-snapshot",
                "exact six-service state captured; all three application services active",
            )

            mixer_result = adapter.capture_mixer_state(transaction.transaction)
            mixer = require_pass(
                mixer_result,
                AdapterOperation.CAPTURE_MIXER_STATE,
            )
            append_result(
                results,
                "mixer-snapshot",
                "exact four-control mixer state captured",
            )
            loopback_result = adapter.capture_loopback_state(transaction.transaction)
            loopback = require_pass(
                loopback_result,
                AdapterOperation.CAPTURE_LOOPBACK_STATE,
            )
            if not loopback.loaded:
                raise SystemExit("authoritative loopback snapshot is not loaded")
            append_result(
                results,
                "loopback-snapshot",
                "exact snd_aloop state captured",
            )
            dac_result = adapter.capture_dac_state(transaction.transaction)
            dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
            if dac.released or not dac.owners:
                raise SystemExit("authoritative DAC snapshot lacks the live owner")
            append_result(
                results,
                "dac-snapshot",
                f"exact DAC format and {len(dac.owners)} structured owner(s) captured",
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
            require_receipt(stage_result, AdapterOperation.STAGE_CANDIDATE_FILES)
            append_result(
                results,
                "candidate-staging",
                "twelve files atomically staged only inside the transaction candidate root",
            )
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained by the adapter")
            validate_candidate_manifest(package_root, adapter.candidate_root)
            append_result(
                results,
                "candidate-manifest-binding",
                "all staged paths, modes, owners and digests match the Stage C1 manifest",
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
                    "three staged units and inert helper passed private verification",
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
                    adapter.validate_candidate_camilladsp,
                    "candidate-camilladsp-validation",
                    "digest-pinned binary accepted staged config without audio",
                ),
            ):
                result = call(transaction.transaction)
                require_receipt(result, operation)
                validation_results.append(result)
                append_result(results, check, detail)

            blocked = prove_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
            )
            write_blocked_operations(
                evidence_root / "blocked-operations.tsv",
                blocked,
            )
            append_result(
                results,
                "blocked-operation-boundary",
                f"all {len(blocked)} managed-service, audio, direct-route, commit and later restore operations refused exactly",
            )

            early_route_result = adapter.select_split_bus_route(
                transaction.transaction
            )
            if (
                early_route_result.operation
                is not AdapterOperation.SELECT_SPLIT_BUS_ROUTE
                or early_route_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("split-bus route selection did not refuse before reload")
            append_result(
                results,
                "route-selection-gate",
                "split-bus route selection refused before service quiescence, installation and candidate reload",
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
                "only captured-active Plexamp, Shairport Sync and dashboard services stopped",
            )
            append_event(
                events,
                20,
                "application-services-stopped",
                "dashboard,shairport,plexamp",
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
                "physical DAC and fixed loopback endpoints have no owners",
            )

            install_result = adapter.install_managed_files(transaction.transaction)
            require_receipt(
                install_result,
                AdapterOperation.INSTALL_MANAGED_FILES,
            )
            append_result(
                results,
                "managed-file-installation",
                "twelve managed files atomically installed while services and DAC remained quiesced",
            )
            append_result(
                results,
                "installed-manifest-binding",
                "all installed types, inodes, modes, owners and digests matched the transaction candidate",
            )
            append_event(events, 30, "managed-files-installed", "file_count=12")

            candidate_reload_result = adapter.reload_systemd(
                transaction.transaction
            )
            require_receipt(
                candidate_reload_result,
                AdapterOperation.RELOAD_SYSTEMD,
            )
            if (
                adapter.systemd_reload_count != 1
                or not adapter.systemd_candidate_visible
                or adapter.systemd_manager_restored
            ):
                raise SystemExit("first systemd reload state was not exact")
            append_result(
                results,
                "systemd-candidate-reload",
                "first fixed daemon reload completed with the candidate files installed",
            )
            append_result(
                results,
                "managed-unit-visibility",
                "three managed units are loaded, inactive, dead and not enabled",
            )
            append_event(events, 35, "systemd-candidate-visible", "managed_units=3")

            route_result = adapter.select_split_bus_route(
                transaction.transaction
            )
            require_receipt(
                route_result,
                AdapterOperation.SELECT_SPLIT_BUS_ROUTE,
            )
            if (
                not adapter.route_selected_once
                or adapter.route_restored
                or adapter.route_selection_count != 1
            ):
                raise SystemExit("split-bus route selection state was not exact")
            route_evidence = dict(route_result.evidence)
            if (
                not route_evidence.get("original_inode")
                or not route_evidence.get("selected_inode")
                or not route_evidence.get("original_sha256")
                or not route_evidence.get("selected_sha256")
            ):
                raise SystemExit("route selection evidence lacks exact identities")
            append_result(
                results,
                "split-bus-route-selection",
                "reviewed split-bus route selected by one atomic inode exchange while all services remained stopped",
            )
            append_result(
                results,
                "selected-route-binding",
                "active route inode and SHA-256 match the installed transaction candidate; original inode remains parked",
            )
            append_event(
                events,
                38,
                "split-bus-route-selected",
                f"selected_inode={route_evidence['selected_inode']}",
            )

            post_route_blocked = prove_blocked_operations(
                adapter,
                transaction=transaction.transaction,
                services=services,
                mixer=mixer,
            )
            write_blocked_operations(
                evidence_root / "post-route-blocked-operations.tsv",
                post_route_blocked,
            )
            append_result(
                results,
                "post-route-boundary",
                "all nine managed-service, audio, direct-failback, commit and later restore operations remained blocked after route selection",
            )

            rollback_result = adapter.restore_exact_snapshot(
                transaction.transaction,
                transaction.snapshot,
            )
            require_receipt(
                rollback_result,
                AdapterOperation.RESTORE_EXACT_SNAPSHOT,
            )
            if not adapter.route_restored:
                raise SystemExit("original active route was not restored")
            append_result(
                results,
                "active-route-restoration",
                "original active-route inode atomically restored and exact candidate inode removed",
            )
            append_result(
                results,
                "exact-filesystem-rollback",
                "all installed files and transaction-created directories restored after active-route rollback",
            )
            append_event(
                events,
                40,
                "route-and-managed-files-rolled-back",
                "route_restored=true filesystem_restored=true",
            )

            manager_reload_result = adapter.reload_systemd(
                transaction.transaction
            )
            require_receipt(
                manager_reload_result,
                AdapterOperation.RELOAD_SYSTEMD,
            )
            if (
                adapter.systemd_reload_count != 2
                or not adapter.systemd_manager_restored
            ):
                raise SystemExit("second systemd reload state was not exact")
            append_result(
                results,
                "systemd-manager-restoration",
                "second fixed daemon reload completed after route and filesystem rollback",
            )
            append_result(
                results,
                "managed-unit-forgetting",
                "all three managed units are not-found, inactive and dead",
            )
            append_event(events, 45, "systemd-manager-restored", "managed_units_not_found=3")

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
                "captured application service state restored only after route, file and manager rollback",
            )
            append_event(
                events,
                50,
                "application-services-restored",
                "plexamp,shairport,dashboard",
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
                "stable direct route, mixer, loopback, DAC readiness and dashboard HTTP health verified",
            )

            verify_result = adapter.verify_exact_rollback(
                transaction.transaction,
                transaction.snapshot,
            )
            require_receipt(
                verify_result,
                AdapterOperation.VERIFY_EXACT_ROLLBACK,
            )
            append_result(
                results,
                "exact-rollback-verification",
                "zero filesystem, route, service, mixer, loopback or DAC mismatch remained",
            )
            append_result(
                results,
                "exact-restoration-boundary",
                "route-selection rehearsal ended with the accepted direct appliance state restored",
            )

            abort_result = adapter.abort_uncommitted_transaction(
                transaction.transaction
            )
            if (
                abort_result.operation
                is not TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
                or abort_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("v2 pre-mutation abort did not refuse after mutation")
            append_result(
                results,
                "pre-mutation-abort-refusal",
                "v2 pre-mutation abort refused after service, file, manager and route mutation",
            )

            service_close_result = adapter.close_restored_rehearsal_transaction(
                transaction.transaction
            )
            if (
                service_close_result.operation
                is not RestoredRehearsalLifecycleOperation.CLOSE_RESTORED_REHEARSAL_TRANSACTION
                or service_close_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("v3 service-only closure did not refuse")
            append_result(
                results,
                "service-only-closure-refusal",
                "v3 service-only closure refused the managed-file, manager and route mutation history",
            )

            file_close_result = adapter.close_exact_rollback_rehearsal_transaction(
                transaction.transaction
            )
            if (
                file_close_result.operation
                is not ExactRollbackRehearsalLifecycleOperation.CLOSE_EXACT_ROLLBACK_REHEARSAL_TRANSACTION
                or file_close_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("v4 file-only closure did not refuse")
            append_result(
                results,
                "file-only-closure-refusal",
                "v4 file-only closure refused after systemd-manager and route mutation",
            )

            systemd_close_result = (
                adapter.close_systemd_reload_rollback_rehearsal_transaction(
                    transaction.transaction
                )
            )
            if (
                systemd_close_result.operation
                is not SystemdReloadRollbackLifecycleOperation.
                CLOSE_SYSTEMD_RELOAD_ROLLBACK_REHEARSAL_TRANSACTION
                or systemd_close_result.status is not AdapterStatus.FAIL
            ):
                raise SystemExit("v5 systemd-only closure did not refuse")
            append_result(
                results,
                "systemd-only-closure-refusal",
                "v5 systemd-only closure refused the active-route mutation history",
            )

            premature = adapter.release_production_lock()
            if premature.status is not AdapterStatus.FAIL:
                raise SystemExit("production lock release did not refuse the open transaction")

            close_result = (
                adapter.close_route_selection_rollback_rehearsal_transaction(
                    transaction.transaction
                )
            )
            if (
                close_result.operation
                is not RouteSelectionRollbackLifecycleOperation.
                CLOSE_ROUTE_SELECTION_ROLLBACK_REHEARSAL_TRANSACTION
                or close_result.status is not AdapterStatus.PASS
                or close_result.payload is None
            ):
                raise SystemExit(
                    f"v6 route-selection rollback closure failed: {close_result.detail}"
                )
            candidate_copy = evidence_root / "candidate-review-copy"
            if candidate_copy.is_symlink() or not candidate_copy.is_dir():
                raise SystemExit("candidate review evidence copy is missing")
            append_result(
                results,
                "candidate-evidence-copy",
                f"validated candidate and route-selection rehearsal retained non-authoritatively at {candidate_copy}",
            )
            append_result(
                results,
                "route-rollback-close-v6",
                "typed v6 closure accepted only the adapter-generated route-selection rollback transaction",
            )
            if (
                adapter.transaction_path is not None
                or not close_result.payload.transaction_path_absent
                or not close_result.payload.parents_restored
                or close_result.payload.installed_file_count != 12
                or close_result.payload.daemon_reload_count != 2
                or close_result.payload.route_selection_count != 1
                or not close_result.payload.active_route_restored
                or Path(close_result.payload.audit_evidence) != evidence_root
            ):
                raise SystemExit("v6 closure did not finish exact transaction cleanup")
            append_result(
                results,
                "exact-transaction-cleanup",
                "candidate, validation root and authoritative transaction removed; parent state restored",
            )
            append_event(
                events,
                60,
                "route-rollback-transaction-closed",
                transaction.transaction.value,
            )

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
                early_route_result,
                stop_result,
                release_dac_result,
                install_result,
                candidate_reload_result,
                route_result,
                rollback_result,
                manager_reload_result,
                restore_result,
                dashboard_result,
                verify_result,
                abort_result,
                service_close_result,
                file_close_result,
                systemd_close_result,
                close_result,
            )
            (evidence_root / "typed-operations.json").write_text(
                json.dumps(
                    {
                        "transaction": transaction.transaction.value,
                        "snapshot": transaction.snapshot.value,
                        "lease": lease.lease_id,
                        "package_sha256": package.sha256,
                        "mutation_started": True,
                        "managed_files_installed": True,
                        "systemd_reloaded": True,
                        "split_bus_route_selected": True,
                        "active_route_restored": True,
                        "route_selection_count": 1,
                        "filesystem_restored": True,
                        "systemd_manager_restored": True,
                        "services_restored": True,
                        "daemon_reload_count": 2,
                        "route_selected": False,
                        "managed_stage_c_services_started": False,
                        "audio_probe_opened": False,
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
            require_receipt(
                release_result,
                AdapterOperation.RELEASE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-released",
                "exact production lock removed only after v6 route-selection rollback closure",
            )
            append_event(events, 70, "production-lock-released", lease.lease_id)
            write_report(
                evidence_root / "report.txt",
                evidence_root,
                transaction,
                len(blocked),
            )

        for label, root in (
            ("stage-c1", package_root),
            ("stage-c19", stage_c19_root),
        ):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(f"{label} input changed during Stage C20")
        append_result(
            results,
            "input-integrity",
            "Stage C1 and Stage C19 input trees remained unchanged",
        )
        write_evidence_manifest(evidence_root)
        append_result(
            results,
            "evidence-integrity",
            "complete checksummed evidence tree contains no symlink or special object",
        )
        append_result(
            results,
            "activation-interface",
            "absent; route rollback completed before managed-service startup, audio probe or commit",
        )
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C20 result order: {observed}")
        completed = True
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C20 route-selection rollback rehearsal did not complete")
    print(
        f"""
A Clockwork Plex Stage C20 split-bus route-selection exact-rollback rehearsal passed.

  Directory:             {evidence_root}
  Results:               {evidence_root / 'results.tsv'}
  Identity:              {evidence_root / 'identity.tsv'}
  Service actions:       {evidence_root / 'service-actions.tsv'}
  File actions:          {evidence_root / 'managed-file-actions.tsv'}
  Systemd actions:       {evidence_root / 'systemd-reload-actions.tsv'}
  Unit observations:     {evidence_root / 'systemd-unit-observations.tsv'}
  Route actions:         {evidence_root / 'route-selection-actions.tsv'}
  Readiness:             {evidence_root / 'restoration-readiness.tsv'}
  Typed operations:      {evidence_root / 'typed-operations.json'}
  Blocked operations:    {evidence_root / 'blocked-operations.tsv'}
  Post-route blocked:    {evidence_root / 'post-route-blocked-operations.tsv'}
  Candidate copy:        {evidence_root / 'candidate-review-copy'}
  Transaction copy:      {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:     {evidence_root / 'evidence-manifest.tsv'}
  Report:                {evidence_root / 'report.txt'}

The reviewed split-bus route was selected once by atomic inode exchange while all
application services and audio endpoints remained quiesced. Every later service,
audio, direct-failback and commit operation remained blocked. The original active
route inode was exchanged back before managed-file and systemd-manager rollback,
then the exact direct appliance state was restored. Persistent Stage C activation
remains blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
