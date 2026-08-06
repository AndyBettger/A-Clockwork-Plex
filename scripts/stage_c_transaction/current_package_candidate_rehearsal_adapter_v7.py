#!/usr/bin/python3
from __future__ import annotations

"""Stage C21 current-package transaction-private validation adapter.

This is a narrow package-bound subclass of the physically proved Stage C16
adapter. Production-lock ownership, transaction identity, read-only host
observations, five-domain capture and exact pre-mutation abort remain inherited.
Only the current package contract, parent modes, file count, staging receipt and
unit/runtime validation differ.
"""

import json
import os
import secrets
import stat
from pathlib import Path

from stage_c_activation_package.core import (
    EXPECTED_FILES,
    RUNTIME_MODULES,
    package_fingerprint,
)
from stage_c_activation_package.runtime_templates import PACKAGE_PHASE

from .authoritative_snapshot_rehearsal_adapter import (
    AuthoritativeSnapshotFailure,
    AuthoritativeTransaction,
    PARENT_CONTRACT,
    PathState,
    TRANSACTION_ROOT,
    _assert_regular_tree,
    _atomic_text,
    _path_state,
    _remove_regular_tree,
)
from .candidate_validation_rehearsal_adapter import (
    CANDIDATE_ROOT_NAME,
    CandidateValidationFailure,
    CandidateValidationRehearsalAdapter,
    _atomic_copy,
)
from .current_package_contract_v7 import (
    ACCEPTED_PACKAGE_FINGERPRINT,
    EXPECTED_PAYLOAD_FILES,
    PACKAGE_CONTRACT_DESTINATION,
    CurrentPackageContractErrorV7,
    parse_current_package_manifest_v7,
    validate_current_package_v7,
)
from .package_review import sha256
from .privileged_snapshot import write_rollback_ledger
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    FilesystemSnapshot,
    PackageFingerprint,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_lock_rehearsal_adapter import ProductionLockRehearsalAdapter
from .read_only_host_adapter import _fail
from .sandbox_transaction import tree_fingerprint
from .snapshot_core import collect_filesystem_snapshot, write_evidence_manifest


CURRENT_TRANSACTION_PREFIX = "stage-c21-prepare-install-"
CURRENT_SNAPSHOT_PREFIX = "stage-c21-prepare-snapshot-"
CURRENT_PACKAGE_FINGERPRINT_LABEL = "stage-c21-package-v2"
CURRENT_PARENT_CONTRACT = (
    (Path("/var/lib/a-clockwork-plex"), 0o750),
    (Path("/var/lib/a-clockwork-plex/split-bus"), 0o755),
    (TRANSACTION_ROOT, 0o700),
)

if CURRENT_PARENT_CONTRACT[0] != PARENT_CONTRACT[0] or CURRENT_PARENT_CONTRACT[2] != PARENT_CONTRACT[2]:
    raise RuntimeError("current package changed the inherited outer transaction contract")


class CurrentPackageCandidateValidationAdapterV7(
    CandidateValidationRehearsalAdapter
):
    """Stage C16 mechanics bound to the accepted 28-file Stage C21 package."""

    def __init__(
        self,
        package_root: Path,
        invoking_user: str,
        evidence_root: Path,
    ) -> None:
        # CandidateValidationRehearsalAdapter.__init__ is intentionally not
        # called because it is immutably bound to the historical Stage C1
        # 12-file package validator. The inherited owner fields are initialised
        # with the same shapes and the current fixed package contract.
        ProductionLockRehearsalAdapter.__init__(self)
        self._package_root = package_root.resolve()
        self._package = validate_current_package_v7(self._package_root)
        self._entries = list(parse_current_package_manifest_v7(self._package_root))
        self._invoking_user = invoking_user
        self._transaction: AuthoritativeTransaction | None = None
        self._transaction_path: Path | None = None
        self._transaction_device: int | None = None
        self._transaction_inode: int | None = None
        self._parent_states: tuple[PathState, ...] = ()
        self._created_parents: tuple[Path, ...] = ()
        self._filesystem_captured = False
        self._service_captured = False
        self._mixer_captured = False
        self._loopback_captured = False
        self._dac_captured = False

        self._evidence_root = evidence_root.resolve()
        self._candidate_root: Path | None = None
        self._candidate_device: int | None = None
        self._candidate_inode: int | None = None
        self._validation_root: Path | None = None
        self._candidate_staged = False
        self._alsa_validated = False
        self._sudoers_validated = False
        self._units_validated = False
        self._camilladsp_validated = False
        self._candidate_review_copy: Path | None = None

    def _create_parent_contract(self) -> None:
        states = tuple(_path_state(path) for path, _mode in CURRENT_PARENT_CONTRACT)
        created: list[Path] = []
        try:
            for (path, mode), state in zip(
                CURRENT_PARENT_CONTRACT,
                states,
                strict=True,
            ):
                if state.exists:
                    if (
                        state.uid != 0
                        or state.gid != 0
                        or state.mode != mode
                    ):
                        raise AuthoritativeSnapshotFailure(
                            "existing current-package transaction parent differs "
                            f"from root:root {mode:o}: {path}"
                        )
                    continue
                path.mkdir(mode=mode, exist_ok=False)
                os.chown(path, 0, 0)
                path.chmod(mode)
                created.append(path)
        except BaseException:
            for path in reversed(created):
                try:
                    path.rmdir()
                except OSError:
                    pass
            raise
        self._parent_states = states
        self._created_parents = tuple(created)

    def create_authoritative_transaction(
        self,
        action: TransactionAction,
        package: PackageFingerprint,
    ) -> AdapterResult[AuthoritativeTransaction]:
        operation = AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION
        if not self.lock_held:
            return _fail(operation, "transaction creation requires the held production lock")
        if self._transaction is not None:
            return _fail(operation, "an authoritative transaction already exists")
        if action is not TransactionAction.INSTALL:
            return _fail(operation, "current-package preparation accepts only install")
        try:
            replayed = validate_current_package_v7(self._package_root)
        except CurrentPackageContractErrorV7 as exc:
            return _fail(operation, str(exc))
        if package != self._package or replayed != self._package:
            return _fail(operation, "accepted current-package fingerprint mismatch")
        lease = self.lease
        if lease is None:
            return _fail(operation, "production-lock lease is unavailable")

        try:
            self._create_parent_contract()
            token = secrets.token_hex(12)
            identity = TransactionIdentity(f"{CURRENT_TRANSACTION_PREFIX}{token}")
            snapshot = SnapshotIdentity(f"{CURRENT_SNAPSHOT_PREFIX}{token}")
            path = TRANSACTION_ROOT / identity.value
            path.mkdir(mode=0o700, exist_ok=False)
            os.chown(path, 0, 0)
            path.chmod(0o700)
            info = path.lstat()
            transaction = AuthoritativeTransaction(
                transaction=identity,
                snapshot=snapshot,
                action=action,
                package=package,
            )
            _atomic_text(
                path / "transaction.tsv",
                "item\tvalue\n"
                f"transaction\t{identity.value}\n"
                f"snapshot\t{snapshot.value}\n"
                f"action\t{action.value}\n"
                f"package_sha256\t{package.sha256}\n"
                f"invoking_user\t{self._invoking_user}\n"
                f"root_pid\t{os.getpid()}\n"
                f"lease_id\t{lease.lease_id}\n"
                "package_contract\tstage-c21-current-v2\n"
                "production_authoritative\ttrue\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                path / "state.tsv",
                "item\tvalue\n"
                "state\tsnapshot-open\n"
                "mutation_started\tfalse\n"
                "committed\tfalse\n",
            )
            _atomic_text(
                path / "package-fingerprint.tsv",
                "item\tsha256\n"
                f"{CURRENT_PACKAGE_FINGERPRINT_LABEL}\t{package.sha256}\n",
            )
        except (OSError, AuthoritativeSnapshotFailure, ValueError) as exc:
            return _fail(operation, str(exc))

        self._transaction = transaction
        self._transaction_path = path
        self._transaction_device = info.st_dev
        self._transaction_inode = info.st_ino
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="fresh current-package authoritative transaction created under the held lock",
            payload=transaction,
            evidence=(
                ("path", str(path)),
                ("inode", str(info.st_ino)),
                ("mode", "700"),
                ("owner", "0:0"),
                ("package_fingerprint", package.sha256),
                ("committed", "false"),
            ),
        )

    def capture_filesystem_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[FilesystemSnapshot]:
        operation = AdapterOperation.CAPTURE_FILESYSTEM_STATE
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if self._filesystem_captured:
            return _fail(operation, "filesystem snapshot was already captured")
        assert self._transaction is not None
        assert self._transaction_path is not None
        snapshot_root = self._transaction_path / "snapshot"
        try:
            snapshot_root.mkdir(mode=0o700, exist_ok=False)
            os.chown(snapshot_root, 0, 0)
            snapshot_root.chmod(0o700)
            summary = collect_filesystem_snapshot(
                self._entries,
                Path("/"),
                snapshot_root,
            )
            if (
                summary.conflicts != 0
                or summary.managed_present != 0
                or summary.managed_absent != EXPECTED_FILES
            ):
                raise AuthoritativeSnapshotFailure(
                    "current managed destination boundary changed: "
                    f"absent={summary.managed_absent} "
                    f"present={summary.managed_present} "
                    f"conflicts={summary.conflicts}"
                )
            _atomic_text(
                snapshot_root / "package-fingerprint.tsv",
                "item\tsha256\n"
                f"{CURRENT_PACKAGE_FINGERPRINT_LABEL}\t{self._package.sha256}\n",
            )
            write_rollback_ledger(
                self._entries,
                snapshot_root / "rollback-ledger.tsv",
                self._transaction_path,
            )
            write_evidence_manifest(snapshot_root)
        except (OSError, SystemExit, AuthoritativeSnapshotFailure) as exc:
            return _fail(operation, str(exc))

        self._filesystem_captured = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact current-package activation-time filesystem state captured",
            payload=FilesystemSnapshot(
                identity=self._transaction.snapshot,
                managed_entries=len(self._entries) + 1,
                exact=True,
            ),
            evidence=(
                ("managed_absent", str(summary.managed_absent)),
                ("managed_present", str(summary.managed_present)),
                ("conflicts", str(summary.conflicts)),
            ),
        )

    def stage_candidate_files(
        self,
        transaction: TransactionIdentity,
        package: PackageFingerprint,
    ) -> AdapterResult[None]:
        operation = AdapterOperation.STAGE_CANDIDATE_FILES
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if not self._snapshot_complete():
            return _fail(operation, "candidate staging requires all five snapshot domains")
        if package != self.package:
            return _fail(operation, "candidate package fingerprint is not transaction-bound")
        if self._candidate_root is not None:
            return _fail(operation, "candidate files were already staged")
        assert self.transaction_path is not None
        candidate = self.transaction_path / CANDIDATE_ROOT_NAME
        try:
            candidate.mkdir(mode=0o700, exist_ok=False)
            os.chown(candidate, 0, 0)
            candidate.chmod(0o700)
            for entry in sorted(
                (item for item in self._entries if item.kind == "directory"),
                key=lambda item: len(Path(item.destination).parts),
            ):
                destination = candidate / entry.destination.lstrip("/")
                destination.mkdir(parents=True, exist_ok=True)
                os.chown(destination, 0, 0)
                destination.chmod(int(entry.mode, 8))
            for entry in (item for item in self._entries if item.kind == "file"):
                source = self._package_root / "rootfs" / entry.destination.lstrip("/")
                destination = candidate / entry.destination.lstrip("/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                _atomic_copy(source, destination, int(entry.mode, 8))
                if sha256(destination) != entry.digest:
                    raise CandidateValidationFailure(
                        f"staged digest differs from manifest: {entry.destination}"
                    )
            _assert_regular_tree(candidate)
            files = [path for path in candidate.rglob("*") if path.is_file()]
            if len(files) != EXPECTED_FILES:
                raise CandidateValidationFailure(
                    f"staged file count mismatch: expected {EXPECTED_FILES}, found {len(files)}"
                )
            staged_rows = tree_fingerprint(candidate)
            (self.transaction_path / "candidate-tree.tsv").write_text(
                "path\ttype\tmode\tsha256\n"
                + "".join(
                    f"{relative}\t{kind}\t{mode}\t{value}\n"
                    for relative, kind, mode, value in staged_rows
                ),
                encoding="utf-8",
            )
            info = candidate.lstat()
        except (
            OSError,
            SystemExit,
            CandidateValidationFailure,
            AuthoritativeSnapshotFailure,
        ) as exc:
            if candidate.exists():
                try:
                    _remove_regular_tree(candidate)
                except (OSError, AuthoritativeSnapshotFailure):
                    pass
            return _fail(operation, str(exc))
        self._candidate_root = candidate
        self._candidate_device = info.st_dev
        self._candidate_inode = info.st_ino
        self._candidate_staged = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="28 current-package files staged atomically inside the authoritative transaction",
            evidence=(
                ("candidate_root", str(candidate)),
                ("file_count", str(EXPECTED_FILES)),
                ("package_fingerprint", package.sha256),
                ("production_destination_writes", "0"),
            ),
        )

    def _fixed_paths(self) -> dict[str, Path]:
        paths = super()._fixed_paths()
        assert self._candidate_root is not None
        runtime_parent = self._candidate_root / "usr/local/lib/a-clockwork-plex/runtime-authority"
        runtime_package = runtime_parent / "stage_c_runtime_authority"
        paths.update(
            {
                "runtime_parent": runtime_parent,
                "runtime_package": runtime_package,
                "package_entry": runtime_package / "package_entry.py",
                "package_contract": self._candidate_root
                / PACKAGE_CONTRACT_DESTINATION.lstrip("/"),
            }
        )
        return paths

    @staticmethod
    def _unit_contract(paths: dict[str, Path]) -> None:
        route = paths["route_unit"].read_text(encoding="utf-8")
        camilla = paths["camilla_unit"].read_text(encoding="utf-8")
        failback = paths["failback_unit"].read_text(encoding="utf-8")
        combined = "\n".join((route, camilla, failback))
        required = (
            "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-prepare",
            "Type=notify",
            "NotifyAccess=main",
            "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route supervise",
            "Before=plexamp.service shairport-sync.service a-clockwork-plex.service",
            "OnFailure=a-clockwork-plex-audio-failback.service",
            "ExecStart=/usr/local/bin/a-clockwork-plex-audio-route emergency-direct-failback",
        )
        for marker in required:
            if marker not in combined:
                raise CandidateValidationFailure(
                    f"staged current unit contract omitted: {marker}"
                )
        approval = (
            "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved"
        )
        if sum(text.count(approval) for text in (route, camilla, failback)) != 3:
            raise CandidateValidationFailure(
                "all three current units must retain the approval gate"
            )

        launcher = paths["route_helper"].read_text(encoding="utf-8")
        compile(launcher, str(paths["route_helper"]), "exec")
        if (
            "stage_c_runtime_authority.package_entry" not in launcher
            or "raise SystemExit(main())" not in launcher
        ):
            raise CandidateValidationFailure(
                "staged current route launcher is not package-entry bound"
            )

        runtime_package = paths["runtime_package"]
        expected_runtime = set(RUNTIME_MODULES)
        observed_runtime = {
            path.name for path in runtime_package.iterdir() if path.is_file()
        }
        if observed_runtime != expected_runtime:
            raise CandidateValidationFailure(
                "staged runtime-authority module inventory changed"
            )
        if (runtime_package / "recording_runtime_adapter.py").exists():
            raise CandidateValidationFailure(
                "staged package contains the disposable recording adapter"
            )
        for module_name in RUNTIME_MODULES:
            source_path = runtime_package / module_name
            source = source_path.read_text(encoding="utf-8")
            compile(source, str(source_path), "exec")

        entry = paths["package_entry"].read_text(encoding="utf-8")
        for action in (
            "status",
            "validate-runtime",
            "accept-install-handoff",
            "promote-committed-approval",
            "boot-prepare",
            "supervise",
            "emergency-direct-failback",
        ):
            if action not in entry:
                raise CandidateValidationFailure(
                    f"staged package entry omitted fixed action: {action}"
                )
        for guard in (
            "INSTALLED_PACKAGE_ROOT",
            PACKAGE_PHASE,
            'contract.get("host_mutation_available") is not True',
            "transaction-only approval operation is not exposed through the service helper",
            "runtime mutation requires root",
        ):
            if guard not in entry:
                raise CandidateValidationFailure(
                    f"staged package entry omitted guard: {guard}"
                )

        try:
            contract = json.loads(
                paths["package_contract"].read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CandidateValidationFailure(
                f"staged package contract is invalid: {exc}"
            ) from exc
        if (
            contract.get("schema_version") != 1
            or contract.get("package_phase") != PACKAGE_PHASE
            or contract.get("host_mutation_available") is not True
        ):
            raise CandidateValidationFailure(
                "staged package contract authority fields changed"
            )
        rows = contract.get("files")
        if not isinstance(rows, list) or len(rows) != EXPECTED_PAYLOAD_FILES:
            raise CandidateValidationFailure(
                "staged package contract payload inventory changed"
            )
        canonical_rows: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
                raise CandidateValidationFailure(
                    "staged package contract row shape changed"
                )
            candidate = paths["runtime_parent"].parents[3] / row["path"].lstrip("/")
            if not candidate.is_file() or candidate.is_symlink():
                raise CandidateValidationFailure(
                    f"staged package payload is unavailable: {row['path']}"
                )
            if sha256(candidate) != row["sha256"]:
                raise CandidateValidationFailure(
                    f"staged package payload digest changed: {row['path']}"
                )
            canonical_rows.append(
                {"path": row["path"], "sha256": row["sha256"]}
            )
        if package_fingerprint(canonical_rows) != ACCEPTED_PACKAGE_FINGERPRINT:
            raise CandidateValidationFailure(
                "staged package fingerprint differs from the accepted target package"
            )
        if contract.get("package_fingerprint") != ACCEPTED_PACKAGE_FINGERPRINT:
            raise CandidateValidationFailure(
                "staged package contract fingerprint changed"
            )

    def validate_candidate_sudoers(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        result = super().validate_candidate_sudoers(transaction)
        if result.status is not AdapterStatus.PASS:
            return result
        lines = tuple(
            line
            for line in self._fixed_paths()["sudoers"].read_text(
                encoding="utf-8"
            ).splitlines()
            if line and not line.startswith("#")
        )
        expected = (
            "andy ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route status",
            "andy ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route validate-runtime",
        )
        if lines != expected:
            self._sudoers_validated = False
            return _fail(
                AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
                "staged current sudoers exposes more than two read-only actions",
            )
        return AdapterResult(
            operation=AdapterOperation.VALIDATE_CANDIDATE_SUDOERS,
            status=AdapterStatus.PASS,
            detail="staged current sudoers exposes only status and validate-runtime",
            evidence=(("approval_operations_exposed", "0"),),
        )

    def validate_candidate_units(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None]:
        result = super().validate_candidate_units(transaction)
        if result.status is not AdapterStatus.PASS:
            return result
        return AdapterResult(
            operation=AdapterOperation.VALIDATE_CANDIDATE_UNITS,
            status=AdapterStatus.PASS,
            detail="current units, launcher, 15 runtime modules and package contract passed private validation",
            evidence=result.evidence
            + (
                ("runtime_modules", str(len(RUNTIME_MODULES))),
                ("python_candidates", str(len(RUNTIME_MODULES) + 1)),
                ("package_fingerprint", ACCEPTED_PACKAGE_FINGERPRINT),
                ("service_manager_contacted", "false"),
            ),
        )
