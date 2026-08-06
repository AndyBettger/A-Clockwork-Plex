#!/usr/bin/python3
from __future__ import annotations

"""Guarded Stage C21 current-package pre-mutation transaction rehearsal.

The root-only guarded mode acquires the canonical production lock, creates one
fresh authoritative transaction, captures the five rollback domains, stages and
validates the accepted 28-file package only beneath that transaction, retains
review evidence, aborts exactly and releases the lock. It stops before service,
DAC, installation, route, approval or audio mutation.
"""

import argparse
import json
import os
import platform
import stat
from datetime import datetime
from pathlib import Path
from typing import Callable

from stage_c_activation_package.core import EXPECTED_FILES

from .authoritative_snapshot_rehearsal import (
    _validate_owned_root,
    append_event,
    append_result,
    jsonable,
    require_pass,
    require_receipt,
    write_parent_states,
)
from .candidate_validation_rehearsal import (
    prove_blocked_operations,
    write_blocked_operations,
)
from .candidate_validation_rehearsal_adapter import (
    BLOCKED_V2_COUNT,
    PERMITTED_V1_OPERATIONS,
)
from .current_package_candidate_rehearsal_adapter_v7 import (
    CurrentPackageCandidateValidationAdapterV7,
)
from .current_package_contract_v7 import (
    ACCEPTED_PACKAGE_FINGERPRINT,
    BASELINE_PREFIX,
    CurrentPackageContractErrorV7,
    parse_current_package_manifest_v7,
    validate_accepted_baseline_evidence_v7,
    validate_current_package_v7,
    validate_prepare_only_report_against_accepted_v7,
    validate_snapshot_payloads_against_accepted_v7,
)
from .package_review import sha256
from .privileged_snapshot import invoking_identity
from .production_adapter_contract import (
    AdapterOperation,
    AdapterStatus,
    PackageFingerprint,
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
from .production_adapter_lifecycle_v7 import (
    ActivationApprovalLifecycleOperation,
    BlockedProductionAdapterV7,
    ProductionActivationApprovalAdapterBlocked,
    ProductionAdapterV7,
)
from .production_prepare_only_evidence_v7 import (
    production_prepare_only_report_payload_v7,
)
from .production_prepare_only_inspector_v7 import ProductionPrepareOnlyInspectorV7
from .read_only_host_adapter import ReadOnlyHostProductionAdapter
from .sandbox_transaction import _assert_regular_tree, tree_fingerprint
from .snapshot_core import chown_evidence_tree, write_evidence_manifest


REQUIRED_CONFIRMATION = "STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT"
PACKAGE_PREFIX = "a-clockwork-plex-stage-c21-activation-package-v2."
EVIDENCE_PREFIX = "a-clockwork-plex-stage-c21-current-package-preparation."
EXPECTED_CHECKS = (
    "root-scope",
    "package-replay",
    "baseline-replay",
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
    "candidate-evidence-copy",
    "transaction-abort-v2",
    "exact-transaction-cleanup",
    "production-lock-released",
    "input-integrity",
    "evidence-integrity",
    "activation-interface",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage and validate the accepted current Stage C21 package inside "
            "one authoritative transaction, then abort before mutation."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args(argv)


def validate_evidence_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=EVIDENCE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C21 current-package evidence root",
    )
    if any(root.iterdir()):
        raise SystemExit("Stage C21 current-package evidence root must be empty")
    return root


def validate_package_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=PACKAGE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C21 current package",
    )
    package = validate_current_package_v7(root)
    if package.sha256 != ACCEPTED_PACKAGE_FINGERPRINT:
        raise SystemExit("Stage C21 current package fingerprint changed")
    return root


def validate_baseline_root(raw: Path, invoking_uid: int) -> Path:
    root = _validate_owned_root(
        raw,
        prefix=BASELINE_PREFIX,
        invoking_uid=invoking_uid,
        label="Stage C21 accepted baseline",
    )
    validate_accepted_baseline_evidence_v7(
        root,
        PackageFingerprint(ACCEPTED_PACKAGE_FINGERPRINT),
    )
    return root


def validate_candidate_manifest_v7(
    package_root: Path,
    candidate_root: Path,
) -> None:
    entries = parse_current_package_manifest_v7(package_root)
    files = [entry for entry in entries if entry.kind == "file"]
    if len(files) != EXPECTED_FILES:
        raise SystemExit("Stage C21 current manifest file count changed")
    for entry in entries:
        candidate = candidate_root / entry.destination.lstrip("/")
        try:
            info = candidate.lstat()
        except OSError as exc:
            raise SystemExit(
                f"staged current-package object is unavailable: "
                f"{entry.destination}: {exc}"
            ) from exc
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"staged candidate is a symlink: {entry.destination}")
        if stat.S_IMODE(info.st_mode) != int(entry.mode, 8):
            raise SystemExit(
                f"staged mode differs from current manifest: {entry.destination}"
            )
        if info.st_uid != 0 or info.st_gid != 0:
            raise SystemExit(
                f"staged owner differs from root:root: {entry.destination}"
            )
        if entry.kind == "directory":
            if not stat.S_ISDIR(info.st_mode):
                raise SystemExit(
                    f"staged manifest directory is not a directory: "
                    f"{entry.destination}"
                )
        elif (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or sha256(candidate) != entry.digest
        ):
            raise SystemExit(
                f"staged file differs from current manifest: {entry.destination}"
            )


def _approval_calls(
    gate: BlockedProductionAdapterV7,
    transaction: TransactionIdentity,
) -> tuple[
    tuple[
        ActivationApprovalLifecycleOperation,
        str,
        Callable[[], object],
    ],
    ...,
]:
    return (
        (
            ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
            "bind_production_lock_lease",
            lambda: gate.bind_production_lock_lease(transaction),
        ),
        (
            ActivationApprovalLifecycleOperation.
            PUBLISH_TEMPORARY_ACTIVATION_APPROVAL,
            "publish_temporary_activation_approval",
            lambda: gate.publish_temporary_activation_approval(transaction),
        ),
        (
            ActivationApprovalLifecycleOperation.
            REMOVE_TEMPORARY_ACTIVATION_APPROVAL,
            "remove_temporary_activation_approval",
            lambda: gate.remove_temporary_activation_approval(transaction),
        ),
        (
            ActivationApprovalLifecycleOperation.
            PROMOTE_COMMITTED_ACTIVATION_APPROVAL,
            "promote_committed_activation_approval",
            lambda: gate.promote_committed_activation_approval(transaction),
        ),
    )


def prove_approval_operations_blocked(
    adapter: CurrentPackageCandidateValidationAdapterV7,
    transaction: TransactionIdentity,
) -> list[tuple[str, str, str]]:
    if isinstance(adapter, ProductionAdapterV7):
        raise SystemExit(
            "current-package preparation unexpectedly exposes the v7 approval interface"
        )
    gate = BlockedProductionAdapterV7()
    rows: list[tuple[str, str, str]] = []
    for operation, method_name, call in _approval_calls(gate, transaction):
        if hasattr(adapter, method_name):
            raise SystemExit(
                f"current-package adapter unexpectedly exposes: {method_name}"
            )
        try:
            call()
        except ProductionActivationApprovalAdapterBlocked as exc:
            if exc.operation is not operation:
                raise SystemExit(
                    f"approval blocked identity mismatch: expected "
                    f"{operation.value}, found {exc.operation.value}"
                ) from exc
            rows.append((operation.value, "blocked", "not-exposed-by-rehearsal"))
            continue
        raise SystemExit(
            f"approval operation unexpectedly became executable: {operation.value}"
        )
    if len(rows) != 4:
        raise SystemExit("Stage C21 approval boundary must contain four blocked operations")
    return rows


def write_approval_operations(
    output: Path,
    rows: list[tuple[str, str, str]],
) -> None:
    output.write_text(
        "operation\tstate\trehearsal-interface\n"
        + "".join(
            f"{operation}\t{state}\t{interface}\n"
            for operation, state, interface in rows
        ),
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
        "caller_supplied_identity\tfalse\n"
        "candidate_production_authoritative\tfalse\n"
        "approval_operations_exposed\tfalse\n"
        "mutation_started\tfalse\n"
        "committed\tfalse\n"
        "reusable_after_abort\tfalse\n",
        encoding="utf-8",
    )


def write_input_binding(
    output: Path,
    package_root: Path,
    baseline_root: Path,
) -> None:
    output.write_text(
        "item\tvalue\n"
        f"package_root\t{package_root}\n"
        f"package_fingerprint\t{ACCEPTED_PACKAGE_FINGERPRINT}\n"
        f"baseline_root\t{baseline_root}\n"
        "baseline_disposition\tbaseline-ready\n"
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
) -> None:
    output.write_text(
        f"""A Clockwork Plex Stage C21 current-package transaction preparation
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Host: {platform.node()}
Architecture: {platform.machine()}
Evidence root: {evidence_root}
Transaction identity: {transaction.transaction.value}
Snapshot identity: {transaction.snapshot.value}
Package fingerprint: {transaction.package.sha256}
Current package files: 28
Current package payload files: 27
Ordinary permitted operations: {len(PERMITTED_V1_OPERATIONS) + 1}
Ordinary blocked operations: {ordinary_blocked}
Approval operations exposed by rehearsal: 0
Approval operations blocked: {approval_blocked}
Final transaction state: aborted-before-mutation and removed

Proved:
- exact current Stage C21 package v2 and accepted Pi baseline replay
- fresh fixed read-only baseline observation immediately before lock acquisition
- real canonical production lock and one fresh authoritative transaction
- exact current filesystem, six-service, four-control mixer, loopback and DAC snapshot
- all 28 package files staged only below the transaction-private candidate root
- staged path, mode, root ownership, single-link and digest binding
- exact package-contract replay with the accepted 27-payload fingerprint
- isolated parsing of split and direct ALSA candidates without opening a PCM
- staged sudoers validation exposing only status and validate-runtime
- staged current readiness units, launcher and fifteen runtime modules validated privately
- digest-pinned CamillaDSP configuration validation without opening audio
- every later service, installation, route, audio, commit and recovery operation blocked
- all four production approval operations blocked and absent from the rehearsal adapter
- candidate, validation and transaction evidence retained non-authoritatively
- explicit typed abort removed the transaction before production-lock release

Not proved or authorised:
- service stop, DAC release, module mutation or mixer write
- production installation, systemd reload or route selection
- approval publication, removal or promotion
- CamillaDSP startup or any music/alarm audio probe
- commit, activation, physical EQ rehearsal, uninstall or reboot persistence

No installation or activation interface exists in this rehearsal.
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(
            "Stage C21 current-package rehearsal requires --confirm "
            f"{REQUIRED_CONFIRMATION}"
        )
    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = validate_package_root(args.package_root, invoking_uid)
    baseline_root = validate_baseline_root(args.baseline_root, invoking_uid)
    evidence_root = validate_evidence_root(args.evidence_root, invoking_uid)
    package = validate_current_package_v7(package_root)
    validate_accepted_baseline_evidence_v7(baseline_root, package)
    inputs = {
        "package": tree_fingerprint(package_root),
        "baseline": tree_fingerprint(baseline_root),
    }

    live_report = ProductionPrepareOnlyInspectorV7(
        ReadOnlyHostProductionAdapter(),
        package,
    ).inspect()
    validate_prepare_only_report_against_accepted_v7(live_report, package)

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
                "lock and one disposable authoritative transaction"
            ),
        )
        append_result(
            results,
            "package-replay",
            "accepted 28-file current package and 27-payload fingerprint replayed",
        )
        append_result(
            results,
            "baseline-replay",
            "accepted baseline report and manifest hashes replayed exactly",
        )
        append_result(
            results,
            "pre-lock-live-baseline",
            "fresh fixed read-only observation matches the accepted appliance state",
        )
        write_input_binding(
            evidence_root / "input-binding.tsv",
            package_root,
            baseline_root,
        )
        (evidence_root / "pre-lock-report.json").write_text(
            json.dumps(
                production_prepare_only_report_payload_v7(live_report),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with CurrentPackageCandidateValidationAdapterV7(
            package_root,
            invoking_user,
            evidence_root,
        ) as adapter:
            if not isinstance(adapter, ProductionAdapterV2):
                raise SystemExit(
                    "current-package adapter does not conform to ProductionAdapterV2"
                )
            if isinstance(adapter, ProductionAdapterV7):
                raise SystemExit(
                    "current-package adapter unexpectedly conforms to approval-capable v7"
                )
            append_result(
                results,
                "protocol-conformance",
                "fifteen ordinary operations plus typed v2 abort; no v7 approval methods",
            )

            host_result = adapter.inspect_host_contract()
            require_pass(host_result, AdapterOperation.INSPECT_HOST_CONTRACT)
            append_result(
                results,
                "pre-lock-host-contract",
                "fixed host contract re-observed through the transaction owner",
            )
            lock_result = adapter.inspect_production_lock()
            lock = require_pass(lock_result, AdapterOperation.INSPECT_PRODUCTION_LOCK)
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
                "transaction, snapshot, package, action and held lease are adapter-bound",
            )
            write_identity(
                evidence_root / "identity.tsv",
                transaction,
                lease.lease_id,
                invoking_user,
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
                "current ALSA and all 28 package destinations captured exactly",
            )

            service_result = adapter.capture_service_state(transaction.transaction)
            services = require_pass(
                service_result,
                AdapterOperation.CAPTURE_SERVICE_STATE,
            )
            mixer_result = adapter.capture_mixer_state(transaction.transaction)
            mixer = require_pass(
                mixer_result,
                AdapterOperation.CAPTURE_MIXER_STATE,
            )
            loopback_result = adapter.capture_loopback_state(transaction.transaction)
            loopback = require_pass(
                loopback_result,
                AdapterOperation.CAPTURE_LOOPBACK_STATE,
            )
            dac_result = adapter.capture_dac_state(transaction.transaction)
            dac = require_pass(dac_result, AdapterOperation.CAPTURE_DAC_STATE)
            validate_snapshot_payloads_against_accepted_v7(
                services,
                mixer,
                loopback,
                dac,
            )
            append_result(
                results,
                "service-snapshot",
                "exact accepted six-service state captured under the lock",
            )
            append_result(
                results,
                "mixer-snapshot",
                "exact accepted four-control mixer values captured under the lock",
            )
            append_result(
                results,
                "loopback-snapshot",
                "exact accepted loaded snd_aloop contract captured under the lock",
            )
            append_result(
                results,
                "dac-snapshot",
                "exact DAC geometry and Plexamp owner contract captured under the lock",
            )
            append_result(
                results,
                "snapshot-integrity",
                "all five authoritative domains match the accepted baseline",
            )

            stage_result = adapter.stage_candidate_files(
                transaction.transaction,
                package,
            )
            if stage_result.status is not AdapterStatus.PASS:
                raise SystemExit(f"candidate staging failed: {stage_result.detail}")
            append_result(
                results,
                "candidate-staging",
                "28 files atomically staged only inside the transaction candidate root",
            )
            if adapter.candidate_root is None:
                raise SystemExit("candidate root was not retained by the adapter")
            validate_candidate_manifest_v7(package_root, adapter.candidate_root)
            append_result(
                results,
                "candidate-manifest-binding",
                "all staged paths, modes, owners and digests match package v2",
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
                    "only status and validate-runtime accepted by visudo",
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_UNITS,
                    adapter.validate_candidate_units,
                    "candidate-unit-validation",
                    "current readiness units, launcher and runtime package verified",
                ),
                (
                    AdapterOperation.VALIDATE_CANDIDATE_CAMILLADSP,
                    adapter.validate_candidate_camilladsp,
                    "candidate-camilladsp-validation",
                    "digest-pinned binary accepted staged config without audio",
                ),
            ):
                result = call(transaction.transaction)
                if (
                    result.operation is not operation
                    or result.status is not AdapterStatus.PASS
                ):
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
            if len(blocked) != BLOCKED_V2_COUNT:
                raise SystemExit("ordinary blocked-operation count changed")
            write_blocked_operations(
                evidence_root / "blocked-operations.tsv",
                blocked,
            )
            append_result(
                results,
                "blocked-operation-boundary",
                f"all {len(blocked)} later ordinary operations refused exactly",
            )

            approval_blocked = prove_approval_operations_blocked(
                adapter,
                transaction.transaction,
            )
            write_approval_operations(
                evidence_root / "approval-operations.tsv",
                approval_blocked,
            )
            append_result(
                results,
                "approval-operation-boundary",
                "all four approval operations blocked and absent from the adapter",
            )
            append_result(
                results,
                "pre-mutation-boundary",
                "no service, DAC, install, route, mixer, approval or audio mutation began",
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
                        "approval_operations_exposed": False,
                        "operations": [jsonable(result) for result in typed],
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
            abort_result = adapter.abort_uncommitted_transaction(
                transaction.transaction
            )
            if (
                abort_result.operation
                is not TransactionLifecycleOperation.ABORT_UNCOMMITTED_TRANSACTION
                or abort_result.status is not AdapterStatus.PASS
                or abort_result.payload is None
            ):
                raise SystemExit(f"v2 transaction abort failed: {abort_result.detail}")
            if (
                adapter.candidate_review_copy is None
                or not adapter.candidate_review_copy.is_dir()
            ):
                raise SystemExit("candidate review evidence copy is missing")
            append_result(
                results,
                "candidate-evidence-copy",
                (
                    "validated candidate and private validation retained at "
                    f"{adapter.candidate_review_copy}"
                ),
            )
            append_result(
                results,
                "transaction-abort-v2",
                "typed abort accepted only the adapter-generated transaction identity",
            )
            if (
                adapter.transaction_path is not None
                or Path(abort_result.payload.audit_evidence) != evidence_root
            ):
                raise SystemExit("transaction abort did not finish exact cleanup")
            append_result(
                results,
                "exact-transaction-cleanup",
                "candidate, validation and authoritative transaction removed exactly",
            )
            append_event(
                events,
                20,
                "transaction-aborted",
                transaction.transaction.value,
            )

            release_result = adapter.release_production_lock()
            require_receipt(
                release_result,
                AdapterOperation.RELEASE_PRODUCTION_LOCK,
            )
            append_result(
                results,
                "production-lock-released",
                "exact production lock removed only after transaction abort",
            )
            append_event(events, 30, "production-lock-released", lease.lease_id)
            write_report(
                evidence_root / "report.txt",
                evidence_root,
                transaction,
                len(blocked),
                len(approval_blocked),
            )

        for label, root in (
            ("package", package_root),
            ("baseline", baseline_root),
        ):
            if tree_fingerprint(root) != inputs[label]:
                raise SystemExit(f"{label} input changed during Stage C21 preparation")
        append_result(
            results,
            "input-integrity",
            "current package and accepted baseline trees remained unchanged",
        )
        _assert_regular_tree(evidence_root)
        write_evidence_manifest(evidence_root)
        append_result(
            results,
            "evidence-integrity",
            "complete checksummed evidence tree contains no symlink or special object",
        )
        append_result(
            results,
            "activation-interface",
            "absent; transaction aborted before the first appliance mutation",
        )
        write_evidence_manifest(evidence_root)
        observed = tuple(
            line.split("\t", 1)[0]
            for line in results.read_text(encoding="utf-8").splitlines()[1:]
        )
        if observed != EXPECTED_CHECKS:
            raise SystemExit(f"unexpected Stage C21 result order: {observed}")
        completed = True
    except CurrentPackageContractErrorV7 as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        chown_evidence_tree(evidence_root, invoking_uid, invoking_gid)
        evidence_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C21 current-package rehearsal did not complete")
    print(
        f"""
A Clockwork Plex Stage C21 current-package transaction preparation passed.

  Directory:           {evidence_root}
  Results:             {evidence_root / 'results.tsv'}
  Identity:            {evidence_root / 'identity.tsv'}
  Input binding:       {evidence_root / 'input-binding.tsv'}
  Typed operations:    {evidence_root / 'typed-operations.json'}
  Blocked operations:  {evidence_root / 'blocked-operations.tsv'}
  Approval operations: {evidence_root / 'approval-operations.tsv'}
  Candidate copy:      {evidence_root / 'candidate-review-copy'}
  Transaction copy:    {evidence_root / 'transaction-rehearsal-copy'}
  Evidence manifest:   {evidence_root / 'evidence-manifest.tsv'}
  Report:              {evidence_root / 'report.txt'}

The accepted current package was staged and validated only inside one
fresh authoritative transaction. The transaction was aborted before service,
DAC, installation, route, approval or audio mutation, then the canonical
production lock was released. Installation and activation remain blocked.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
