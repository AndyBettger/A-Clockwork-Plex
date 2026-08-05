#!/usr/bin/python3
from __future__ import annotations

"""Stage C15 authoritative snapshot transaction rehearsal adapter.

The adapter extends Stage C14 with creation of one disposable authoritative
transaction and exact pre-mutation snapshot. It cannot stage or mutate the
audio appliance. The uncommitted transaction must be explicitly aborted before
the production lock can be released.
"""

import hashlib
import os
import platform
import secrets
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self

from .host_review import (
    capture_mixer_states,
    capture_module_and_dac,
    capture_service_states,
    validate_service_boundary,
)
from .package_review import (
    EXPECTED_PACKAGE_FILES,
    ManifestEntry,
    parse_manifest,
    validate_stage_c1_evidence,
)
from .privileged_snapshot import write_rollback_ledger
from .production_adapter_contract import (
    AUTHORITATIVE_TRANSACTION_ROOT,
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    AuthoritativeTransaction,
    DacSnapshot,
    FilesystemSnapshot,
    LoopbackSnapshot,
    MixerSnapshot,
    PackageFingerprint,
    ServiceSnapshot,
    SnapshotIdentity,
    TransactionAction,
    TransactionIdentity,
)
from .production_lock_rehearsal_adapter import (
    PERMITTED_OPERATIONS as LOCK_OPERATIONS,
    ProductionLockRehearsalAdapter,
)
from .read_only_host_adapter import (
    ObservationFailure,
    _fail,
    _observe_dac_snapshot,
    _observe_loopback_snapshot,
    _observe_mixer_snapshot,
    _observe_service_snapshot,
)
from .sandbox_transaction import tree_fingerprint
from .snapshot_core import collect_filesystem_snapshot, write_evidence_manifest


TRANSACTION_ROOT = Path(AUTHORITATIVE_TRANSACTION_ROOT)
TRANSACTION_PREFIX = "stage-c15-install-"
SNAPSHOT_PREFIX = "stage-c15-snapshot-"
PARENT_CONTRACT = (
    (Path("/var/lib/a-clockwork-plex"), 0o750),
    (Path("/var/lib/a-clockwork-plex/split-bus"), 0o750),
    (TRANSACTION_ROOT, 0o700),
)
PERMITTED_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.ACQUIRE_PRODUCTION_LOCK,
    AdapterOperation.RELEASE_PRODUCTION_LOCK,
    AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
    AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
)

if set(PERMITTED_OPERATIONS) != set(LOCK_OPERATIONS).union(
    {
        AdapterOperation.CREATE_AUTHORITATIVE_TRANSACTION,
        AdapterOperation.CAPTURE_FILESYSTEM_STATE,
    }
):
    raise RuntimeError("Stage C15 permitted-operation boundary is inconsistent")


class AuthoritativeSnapshotFailure(RuntimeError):
    """The Stage C15 transaction or snapshot boundary could not be proved."""


@dataclass(frozen=True)
class PathState:
    path: str
    exists: bool
    device: int | None
    inode: int | None
    mode: int | None
    uid: int | None
    gid: int | None


@dataclass(frozen=True)
class AbortTransactionReceipt:
    transaction: TransactionIdentity
    state: str
    evidence_copy: str
    transaction_path_absent: bool
    parents_restored: bool

    def __post_init__(self) -> None:
        if self.state != "aborted-before-mutation":
            raise ValueError("abort receipt must describe a pre-mutation abort")
        if not self.transaction_path_absent or not self.parents_restored:
            raise ValueError("abort receipt requires exact cleanup")
        if not self.evidence_copy:
            raise ValueError("abort receipt requires a retained evidence copy")


@dataclass(frozen=True)
class AbortTransactionResult:
    status: AdapterStatus
    detail: str
    payload: AbortTransactionReceipt | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("abort result detail must not be empty")
        if self.status is not AdapterStatus.PASS and self.payload is not None:
            raise ValueError("failed abort result must not carry a receipt")


def package_tree_fingerprint(root: Path) -> PackageFingerprint:
    validate_stage_c1_evidence(root)
    digest = hashlib.sha256()
    for relative, kind, mode, value in tree_fingerprint(root):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(kind.encode("ascii"))
        digest.update(b"\0")
        digest.update(mode.encode("ascii"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return PackageFingerprint(digest.hexdigest())


def _path_state(path: Path) -> PathState:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return PathState(str(path), False, None, None, None, None, None)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise AuthoritativeSnapshotFailure(f"transaction parent is not a real directory: {path}")
    return PathState(
        str(path),
        True,
        info.st_dev,
        info.st_ino,
        stat.S_IMODE(info.st_mode),
        info.st_uid,
        info.st_gid,
    )


def _verify_state(expected: PathState) -> None:
    observed = _path_state(Path(expected.path))
    if observed != expected:
        raise AuthoritativeSnapshotFailure(
            f"transaction parent state changed: expected={expected} observed={observed}"
        )


def _atomic_text(path: Path, text: str, mode: int = 0o600) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{secrets.token_hex(6)}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, mode)
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, 0, 0)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _assert_regular_tree(root: Path) -> None:
    root_info = root.lstat()
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise AuthoritativeSnapshotFailure(f"transaction root is not a real directory: {root}")
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise AuthoritativeSnapshotFailure(f"transaction contains a symlink: {path}")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise AuthoritativeSnapshotFailure(f"transaction contains a special object: {path}")


def _remove_regular_tree(root: Path) -> None:
    _assert_regular_tree(root)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            path.rmdir()
        elif stat.S_ISREG(info.st_mode):
            path.unlink()
        else:
            raise AuthoritativeSnapshotFailure(f"refusing to remove special object: {path}")
    root.rmdir()


class AuthoritativeSnapshotRehearsalAdapter(ProductionLockRehearsalAdapter):
    """Ten core operations plus explicit typed pre-mutation abort lifecycle."""

    def __init__(self, package_root: Path, invoking_user: str) -> None:
        super().__init__()
        self._package_root = package_root.resolve()
        self._package = package_tree_fingerprint(self._package_root)
        self._entries: list[ManifestEntry] = parse_manifest(self._package_root)
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

    def __enter__(self) -> Self:
        return self

    @property
    def package(self) -> PackageFingerprint:
        return self._package

    @property
    def authoritative_transaction(self) -> AuthoritativeTransaction | None:
        return self._transaction

    @property
    def transaction_path(self) -> Path | None:
        return self._transaction_path

    @property
    def parent_states(self) -> tuple[PathState, ...]:
        return self._parent_states

    def _require_transaction(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | None:
        current = self._transaction
        path = self._transaction_path
        if not self.lock_held:
            return _fail(operation, "authoritative capture requires the held production lock")
        if current is None or path is None:
            return _fail(operation, "no authoritative transaction exists")
        if transaction != current.transaction:
            return _fail(operation, "rejected non-authoritative transaction identity")
        try:
            info = path.lstat()
        except OSError as exc:
            return _fail(operation, f"authoritative transaction path is unavailable: {exc}")
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_dev != self._transaction_device
            or info.st_ino != self._transaction_inode
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != 0
            or info.st_gid != 0
        ):
            return _fail(operation, "authoritative transaction path identity changed")
        return None

    def _create_parent_contract(self) -> None:
        states = tuple(_path_state(path) for path, _mode in PARENT_CONTRACT)
        created: list[Path] = []
        try:
            for (path, mode), state in zip(PARENT_CONTRACT, states, strict=True):
                if state.exists:
                    if state.uid != 0 or state.gid != 0:
                        raise AuthoritativeSnapshotFailure(
                            f"existing transaction parent is not root-owned: {path}"
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
            return _fail(operation, "Stage C15 accepts only the install action")
        if package != self._package or package_tree_fingerprint(self._package_root) != self._package:
            return _fail(operation, "Stage C1 package fingerprint mismatch")
        lease = self.lease
        if lease is None:
            return _fail(operation, "production-lock lease is unavailable")

        try:
            self._create_parent_contract()
            token = secrets.token_hex(12)
            identity = TransactionIdentity(f"{TRANSACTION_PREFIX}{token}")
            snapshot = SnapshotIdentity(f"{SNAPSHOT_PREFIX}{token}")
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
                f"host\t{platform.node()}\n"
                f"architecture\t{platform.machine()}\n"
                f"invoking_user\t{self._invoking_user}\n"
                f"root_pid\t{os.getpid()}\n"
                f"created\t{datetime.now().astimezone().isoformat(timespec='microseconds')}\n"
                f"lease_id\t{lease.lease_id}\n"
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
                f"stage-c1-tree\t{package.sha256}\n",
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
            detail="fresh authoritative transaction created under the held lock",
            payload=transaction,
            evidence=(
                ("path", str(path)),
                ("inode", str(info.st_ino)),
                ("mode", "700"),
                ("owner", "0:0"),
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
            summary = collect_filesystem_snapshot(self._entries, Path("/"), snapshot_root)
            if (
                summary.conflicts != 0
                or summary.managed_present != 0
                or summary.managed_absent != EXPECTED_PACKAGE_FILES
            ):
                raise AuthoritativeSnapshotFailure(
                    "managed destination boundary changed: "
                    f"absent={summary.managed_absent} "
                    f"present={summary.managed_present} conflicts={summary.conflicts}"
                )
            _atomic_text(
                snapshot_root / "package-fingerprint.tsv",
                "item\tsha256\n"
                f"stage-c1-tree\t{self._package.sha256}\n",
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
        payload = FilesystemSnapshot(
            identity=self._transaction.snapshot,
            managed_entries=len(self._entries) + 1,
            exact=True,
        )
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact activation-time filesystem state captured",
            payload=payload,
            evidence=(
                ("managed_absent", str(summary.managed_absent)),
                ("managed_present", str(summary.managed_present)),
                ("conflicts", str(summary.conflicts)),
            ),
        )

    def capture_service_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[ServiceSnapshot]:
        operation = AdapterOperation.CAPTURE_SERVICE_STATE
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if self._service_captured:
            return _fail(operation, "service snapshot was already captured")
        assert self._transaction_path is not None
        try:
            states = capture_service_states(self._transaction_path / "snapshot/service-state.tsv")
            validate_service_boundary(states)
            payload = _observe_service_snapshot()
        except (SystemExit, ObservationFailure, OSError) as exc:
            return _fail(operation, str(exc))
        self._service_captured = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact service snapshot captured under the authoritative identity",
            payload=payload,
        )

    def capture_mixer_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[MixerSnapshot]:
        operation = AdapterOperation.CAPTURE_MIXER_STATE
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if self._mixer_captured:
            return _fail(operation, "mixer snapshot was already captured")
        assert self._transaction_path is not None
        try:
            capture_mixer_states(
                self._transaction_path / "snapshot/mixer-state.tsv",
                self._transaction_path / "snapshot/mixer-raw",
            )
            payload = _observe_mixer_snapshot()
        except (SystemExit, ObservationFailure, OSError) as exc:
            return _fail(operation, str(exc))
        self._mixer_captured = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact mixer snapshot captured under the authoritative identity",
            payload=payload,
        )

    def capture_loopback_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[LoopbackSnapshot]:
        operation = AdapterOperation.CAPTURE_LOOPBACK_STATE
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if self._loopback_captured:
            return _fail(operation, "loopback snapshot was already captured")
        assert self._transaction_path is not None
        try:
            if not (self._transaction_path / "snapshot/module-dac-state.tsv").exists():
                capture_module_and_dac(
                    self._transaction_path / "snapshot/module-dac-state.tsv",
                    self._transaction_path / "snapshot",
                )
            payload = _observe_loopback_snapshot()
        except (SystemExit, ObservationFailure, OSError) as exc:
            return _fail(operation, str(exc))
        self._loopback_captured = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact loopback snapshot captured under the authoritative identity",
            payload=payload,
        )

    def capture_dac_state(
        self,
        transaction: TransactionIdentity,
    ) -> AdapterResult[DacSnapshot]:
        operation = AdapterOperation.CAPTURE_DAC_STATE
        invalid = self._require_transaction(operation, transaction)
        if invalid is not None:
            return invalid
        if self._dac_captured:
            return _fail(operation, "DAC snapshot was already captured")
        assert self._transaction_path is not None
        try:
            if not (self._transaction_path / "snapshot/module-dac-state.tsv").exists():
                capture_module_and_dac(
                    self._transaction_path / "snapshot/module-dac-state.tsv",
                    self._transaction_path / "snapshot",
                )
            payload = _observe_dac_snapshot()
        except (SystemExit, ObservationFailure, OSError) as exc:
            return _fail(operation, str(exc))
        self._dac_captured = True
        return AdapterResult(
            operation=operation,
            status=AdapterStatus.PASS,
            detail="exact DAC snapshot captured under the authoritative identity",
            payload=payload,
        )

    def release_production_lock(self) -> AdapterResult[None]:
        if self._transaction is not None or self._transaction_path is not None:
            return _fail(
                AdapterOperation.RELEASE_PRODUCTION_LOCK,
                "refusing to release production lock while an uncommitted transaction exists",
            )
        return super().release_production_lock()

    def abort_uncommitted_transaction(self, evidence_copy: Path) -> AbortTransactionResult:
        transaction = self._transaction
        path = self._transaction_path
        if not self.lock_held:
            return AbortTransactionResult(
                AdapterStatus.FAIL,
                "pre-mutation abort requires the held production lock",
            )
        if transaction is None or path is None:
            return AbortTransactionResult(
                AdapterStatus.FAIL,
                "no uncommitted authoritative transaction exists",
            )
        required = (
            self._filesystem_captured,
            self._service_captured,
            self._mixer_captured,
            self._loopback_captured,
            self._dac_captured,
        )
        if not all(required):
            return AbortTransactionResult(
                AdapterStatus.FAIL,
                "refusing abort evidence copy before the complete snapshot exists",
            )
        if evidence_copy.exists():
            return AbortTransactionResult(
                AdapterStatus.FAIL,
                "transaction evidence-copy destination already exists",
            )
        try:
            info = path.lstat()
            if (
                info.st_dev != self._transaction_device
                or info.st_ino != self._transaction_inode
                or stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
            ):
                raise AuthoritativeSnapshotFailure(
                    "refusing cleanup after transaction pathname substitution"
                )
            _assert_regular_tree(path)
            if any((path / name).exists() for name in ("candidate", "installed", "commit.tsv")):
                raise AuthoritativeSnapshotFailure(
                    "pre-mutation transaction unexpectedly contains later-phase state"
                )
            _atomic_text(
                path / "state.tsv",
                "item\tvalue\n"
                "state\taborted-before-mutation\n"
                "mutation_started\tfalse\n"
                "committed\tfalse\n",
            )
            write_evidence_manifest(path / "snapshot")
            write_evidence_manifest(path)
            shutil.copytree(path, evidence_copy, symlinks=False)
            _atomic_text(
                evidence_copy / "rehearsal-label.tsv",
                "item\tvalue\n"
                "rehearsal_copy\ttrue\n"
                "production_authoritative\tfalse\n"
                "reusable_for_activation\tfalse\n",
            )
            write_evidence_manifest(evidence_copy)
            _remove_regular_tree(path)
            for created in reversed(self._created_parents):
                created.rmdir()
            for state in self._parent_states:
                _verify_state(state)
        except (OSError, SystemExit, AuthoritativeSnapshotFailure) as exc:
            return AbortTransactionResult(AdapterStatus.FAIL, str(exc))

        self._transaction = None
        self._transaction_path = None
        self._transaction_device = None
        self._transaction_inode = None
        self._created_parents = ()
        receipt = AbortTransactionReceipt(
            transaction=transaction.transaction,
            state="aborted-before-mutation",
            evidence_copy=str(evidence_copy),
            transaction_path_absent=True,
            parents_restored=True,
        )
        return AbortTransactionResult(
            AdapterStatus.PASS,
            "uncommitted authoritative transaction copied as evidence and removed exactly",
            payload=receipt,
        )

    def _best_effort_cleanup(self) -> None:
        path = self._transaction_path
        if path is not None:
            try:
                if path.exists() and not path.is_symlink():
                    _remove_regular_tree(path)
            except (OSError, AuthoritativeSnapshotFailure):
                pass
            for created in reversed(self._created_parents):
                try:
                    created.rmdir()
                except OSError:
                    pass
            self._transaction = None
            self._transaction_path = None
            self._created_parents = ()
        super()._best_effort_cleanup()
