#!/usr/bin/python3
from __future__ import annotations

"""Disposable implementation of the four Stage C21 v7 approval operations.

This adapter exists only for failure-injected sandbox proof. It subclasses the
blocked v7 adapter and overrides exactly the four new approval-lifecycle
methods. Every v1 through v6 production operation remains blocked.

All filesystem activity is confined beneath one caller-supplied, empty, real
0700 laboratory root. No production path, service, ALSA endpoint or process is
available through this module.
"""

import errno
import fcntl
import os
import secrets
import stat
from pathlib import Path
from typing import Callable

from stage_c_runtime_authority.approval_store import ApprovalStore
from stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
    utc_timestamp,
)

from .production_adapter_contract import (
    AdapterStatus,
    PackageFingerprint,
    TransactionIdentity,
)
from .production_adapter_lifecycle_v7 import (
    ACTIVATION_APPROVAL_PATH,
    COMMITTED_APPROVAL_PHASE,
    PRODUCTION_LOCK_PATH,
    TEMPORARY_APPROVAL_PHASE,
    ActivationApprovalAdapterResult,
    ActivationApprovalLifecycleOperation,
    ActivationApprovalRemovalReceipt,
    BlockedProductionAdapterV7,
    CommittedActivationApprovalReceipt,
    ProductionLockLeaseBindingReceipt,
    TemporaryActivationApprovalReceipt,
)


FaultHook = Callable[[str], None]
TimestampFactory = Callable[[], str]
LOCK_MODE = 0o600
DIRECTORY_MODE = 0o700
LOCK_RELATIVE = Path("run/lock/a-clockwork-plex-audio-route.lock")
STATE_RELATIVE = Path("var/lib/a-clockwork-plex/split-bus")


def _noop_fault_hook(_point: str) -> None:
    return None


def _require_sha256(label: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeAuthorityError(f"{label} must be a lowercase SHA-256 digest")


def _write_all_at(fd: int, payload: bytes, offset: int = 0) -> None:
    view = memoryview(payload)
    position = offset
    while view:
        written = os.pwrite(fd, view, position)
        if written <= 0:
            raise RuntimeAuthorityError("short disposable lock write")
        position += written
        view = view[written:]


class DisposableActivationApprovalLifecycleAdapter(BlockedProductionAdapterV7):
    """Real-file v7 rehearsal confined to an empty disposable root."""

    def __init__(
        self,
        root: Path,
        *,
        transaction: TransactionIdentity,
        package: PackageFingerprint,
        temporary_approval: ActivationApprovalRecord,
        fault_hook: FaultHook | None = None,
        timestamp_factory: TimestampFactory = utc_timestamp,
    ) -> None:
        self._root = self._validate_fresh_root(root)
        self._transaction = transaction
        self._package = package
        self._temporary = self._validate_temporary_approval(temporary_approval)
        self._fault_hook = fault_hook or _noop_fault_hook
        self._timestamp_factory = timestamp_factory
        self._commit_manifest_sha256: str | None = None
        self._lease_bound = False
        self._closed = False

        self._lock_path = self._root / LOCK_RELATIVE
        self._state_root = self._root / STATE_RELATIVE
        self._create_private_directory(self._lock_path.parent)
        self._create_private_directory(self._state_root)
        self._store = ApprovalStore(self._state_root, fault_hook=self._fault_hook)

        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        self._lock_fd = os.open(self._lock_path, flags, LOCK_MODE)
        try:
            os.fchmod(self._lock_fd, LOCK_MODE)
            os.fchown(self._lock_fd, os.geteuid(), os.getegid())
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fsync(self._lock_fd)
            descriptor = os.fstat(self._lock_fd)
            path_info = self._lock_path.lstat()
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or descriptor.st_dev != path_info.st_dev
                or descriptor.st_ino != path_info.st_ino
            ):
                raise RuntimeAuthorityError("disposable lock descriptor identity mismatch")
            self._lock_identity = (descriptor.st_dev, descriptor.st_ino)
            self._prove_second_descriptor_contended()
        except BaseException:
            try:
                descriptor = os.fstat(self._lock_fd)
                path_info = self._lock_path.lstat()
                if (
                    stat.S_ISREG(path_info.st_mode)
                    and descriptor.st_dev == path_info.st_dev
                    and descriptor.st_ino == path_info.st_ino
                ):
                    self._lock_path.unlink()
            except OSError:
                pass
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(self._lock_fd)
            raise

    @staticmethod
    def _validate_fresh_root(root: Path) -> Path:
        if not isinstance(root, Path) or not root.is_absolute():
            raise RuntimeAuthorityError("disposable approval root must be an absolute Path")
        try:
            info = root.lstat()
        except FileNotFoundError as exc:
            raise RuntimeAuthorityError("disposable approval root must already exist") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeAuthorityError("disposable approval root must be a real directory")
        if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
            raise RuntimeAuthorityError("disposable approval root owner mismatch")
        if stat.S_IMODE(info.st_mode) != DIRECTORY_MODE:
            raise RuntimeAuthorityError("disposable approval root must have mode 0700")
        if any(root.iterdir()):
            raise RuntimeAuthorityError("disposable approval root must be empty")
        resolved = root.resolve(strict=True)
        if resolved != root:
            raise RuntimeAuthorityError("disposable approval root must not traverse a symlink")
        return resolved

    def _validate_temporary_approval(
        self,
        record: ActivationApprovalRecord,
    ) -> ActivationApprovalRecord:
        if record.phase is not ApprovalPhase.TEMPORARY:
            raise RuntimeAuthorityError("disposable adapter requires a temporary approval")
        if record.transaction_id != self._transaction.value:
            raise RuntimeAuthorityError("temporary approval transaction identity mismatch")
        if record.package_fingerprint != self._package.sha256:
            raise RuntimeAuthorityError("temporary approval package fingerprint mismatch")
        if not record.lock_lease_id:
            raise RuntimeAuthorityError("temporary approval has no lock lease identity")
        if record.commit_manifest_sha256 is not None or record.committed_at is not None:
            raise RuntimeAuthorityError("temporary approval invents committed state")
        return record

    def _create_private_directory(self, path: Path) -> None:
        relative = path.relative_to(self._root)
        current = self._root
        for part in relative.parts:
            current = current / part
            try:
                current.mkdir(mode=DIRECTORY_MODE)
            except FileExistsError:
                pass
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise RuntimeAuthorityError(
                    f"disposable approval ancestor is not a real directory: {current}"
                )
            if info.st_uid != os.geteuid() or info.st_gid != os.getegid():
                raise RuntimeAuthorityError(
                    f"disposable approval ancestor owner mismatch: {current}"
                )
            if stat.S_IMODE(info.st_mode) != DIRECTORY_MODE:
                raise RuntimeAuthorityError(
                    f"disposable approval ancestor mode mismatch: {current}"
                )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def state_root(self) -> Path:
        return self._state_root

    @property
    def lease_bound(self) -> bool:
        return self._lease_bound

    @property
    def closed(self) -> bool:
        return self._closed

    def _require_transaction(self, transaction: TransactionIdentity) -> None:
        if transaction != self._transaction:
            raise RuntimeAuthorityError("disposable approval transaction identity mismatch")

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeAuthorityError("disposable approval adapter is closed")

    def _lock_content(self) -> bytes:
        descriptor = os.fstat(self._lock_fd)
        if descriptor.st_size > 512:
            raise RuntimeAuthorityError("disposable lock content is too large")
        return os.pread(self._lock_fd, 512, 0)

    def _verify_exact_lock(self, *, require_bound: bool) -> os.stat_result:
        self._require_open()
        descriptor = os.fstat(self._lock_fd)
        path_info = self._lock_path.lstat()
        if (
            not stat.S_ISREG(descriptor.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or stat.S_ISLNK(path_info.st_mode)
            or (descriptor.st_dev, descriptor.st_ino) != self._lock_identity
            or (path_info.st_dev, path_info.st_ino) != self._lock_identity
        ):
            raise RuntimeAuthorityError("disposable lock pathname was substituted")
        if descriptor.st_uid != os.geteuid() or descriptor.st_gid != os.getegid():
            raise RuntimeAuthorityError("disposable lock owner changed")
        if stat.S_IMODE(descriptor.st_mode) != LOCK_MODE:
            raise RuntimeAuthorityError("disposable lock mode changed")
        self._prove_second_descriptor_contended()
        content = self._lock_content()
        if require_bound:
            expected = (self._temporary.lock_lease_id + "\n").encode("ascii")
            if content != expected:
                raise RuntimeAuthorityError("bound disposable lock lease content changed")
        elif content not in (b"", (self._temporary.lock_lease_id + "\n").encode("ascii")):
            raise RuntimeAuthorityError("disposable lock contains an unexpected lease")
        return descriptor

    def _prove_second_descriptor_contended(self) -> None:
        second = os.open(
            self._lock_path,
            os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            try:
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise RuntimeAuthorityError(
                        f"disposable lock contention proof failed: {exc}"
                    ) from exc
            else:
                fcntl.flock(second, fcntl.LOCK_UN)
                raise RuntimeAuthorityError("disposable lock is not held")
        finally:
            os.close(second)

    def _approval_or_none(self) -> ActivationApprovalRecord | None:
        try:
            return self._store.read()
        except RuntimeAuthorityError as exc:
            if str(exc) == "activation approval is absent":
                return None
            raise

    def _require_bound_lock(self) -> os.stat_result:
        if not self._lease_bound:
            raise RuntimeAuthorityError("disposable approval operation requires a bound lock lease")
        return self._verify_exact_lock(require_bound=True)

    def bind_production_lock_lease(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        self._require_transaction(transaction)
        descriptor = self._verify_exact_lock(require_bound=False)
        expected = (self._temporary.lock_lease_id + "\n").encode("ascii")
        current = self._lock_content()
        reconciled = current == expected
        if current == b"":
            os.ftruncate(self._lock_fd, 0)
            _write_all_at(self._lock_fd, expected)
            os.ftruncate(self._lock_fd, len(expected))
            os.fsync(self._lock_fd)
        elif not reconciled:
            raise RuntimeAuthorityError("disposable lock contains a different lease")
        descriptor = self._verify_exact_lock(require_bound=True)
        self._lease_bound = True
        receipt = ProductionLockLeaseBindingReceipt(
            transaction=self._transaction,
            lock_path=PRODUCTION_LOCK_PATH,
            lease_id=self._temporary.lock_lease_id,
            lock_device=descriptor.st_dev,
            lock_inode=descriptor.st_ino,
            transaction_owns_lock=True,
            canonical_content_written=True,
            exact_inode_verified=True,
            external_observer_ready=True,
        )
        return ActivationApprovalAdapterResult(
            operation=ActivationApprovalLifecycleOperation.BIND_PRODUCTION_LOCK_LEASE,
            status=AdapterStatus.PASS,
            detail=(
                "existing canonical disposable lock lease reconciled"
                if reconciled
                else "canonical disposable lock lease written and verified"
            ),
            payload=receipt,
        )

    def publish_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        self._require_transaction(transaction)
        self._require_bound_lock()
        existing = self._approval_or_none()
        reconciled = existing == self._temporary
        if existing is not None and not reconciled:
            raise RuntimeAuthorityError(
                "existing disposable activation approval differs from expected temporary record"
            )
        if existing is None:
            try:
                self._store.publish_new(self._temporary, lock_held=True)
            except BaseException:
                observed = self._approval_or_none()
                if observed != self._temporary:
                    raise
                reconciled = True
        if self._store.read() != self._temporary:
            raise RuntimeAuthorityError("temporary approval publication did not verify exactly")
        receipt = TemporaryActivationApprovalReceipt(
            transaction=self._transaction,
            approval_path=ACTIVATION_APPROVAL_PATH,
            phase=TEMPORARY_APPROVAL_PHASE,
            package=self._package,
            lock_lease_id=self._temporary.lock_lease_id,
            record_sha256=self._temporary.record_sha256,
            active_route_sha256=self._temporary.active_route_sha256,
            boot_eligible=False,
            atomically_published=True,
            exact_record_verified=True,
        )
        return ActivationApprovalAdapterResult(
            operation=ActivationApprovalLifecycleOperation.
            PUBLISH_TEMPORARY_ACTIVATION_APPROVAL,
            status=AdapterStatus.PASS,
            detail=(
                "interrupted temporary approval publication reconciled exactly"
                if reconciled
                else "temporary activation approval atomically published and verified"
            ),
            payload=receipt,
        )

    def remove_temporary_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        self._require_transaction(transaction)
        self._require_bound_lock()
        observed = self._approval_or_none()
        if observed is None:
            raise RuntimeAuthorityError(
                "temporary approval is already absent before rollback removal"
            )
        if observed != self._temporary:
            raise RuntimeAuthorityError(
                "activation approval differs from the exact temporary rollback record"
            )
        reconciled = False
        self._fault_hook("before-temporary-removal")
        try:
            self._store.remove_exact(self._temporary, lock_held=True)
            self._fault_hook("after-temporary-removal")
        except BaseException:
            if self._approval_or_none() is not None:
                raise
            reconciled = True
        if self._approval_or_none() is not None:
            raise RuntimeAuthorityError("temporary approval remains after rollback removal")
        receipt = ActivationApprovalRemovalReceipt(
            transaction=self._transaction,
            approval_path=ACTIVATION_APPROVAL_PATH,
            expected_record_sha256=self._temporary.record_sha256,
            exact_record_removed=True,
            approval_absent=True,
            rollback_owned=True,
        )
        return ActivationApprovalAdapterResult(
            operation=ActivationApprovalLifecycleOperation.
            REMOVE_TEMPORARY_ACTIVATION_APPROVAL,
            status=AdapterStatus.PASS,
            detail=(
                "interrupted temporary approval removal reconciled as exact absence"
                if reconciled
                else "exact temporary activation approval removed for rollback"
            ),
            payload=receipt,
        )

    def record_commit_manifest_for_rehearsal(
        self,
        transaction: TransactionIdentity,
        commit_manifest_sha256: str,
    ) -> None:
        self._require_transaction(transaction)
        self._require_bound_lock()
        _require_sha256("disposable commit manifest", commit_manifest_sha256)
        if (
            self._commit_manifest_sha256 is not None
            and self._commit_manifest_sha256 != commit_manifest_sha256
        ):
            raise RuntimeAuthorityError(
                "disposable commit manifest identity cannot be replaced"
            )
        self._commit_manifest_sha256 = commit_manifest_sha256

    def promote_committed_activation_approval(
        self,
        transaction: TransactionIdentity,
    ) -> ActivationApprovalAdapterResult:
        self._require_transaction(transaction)
        self._require_bound_lock()
        if self._commit_manifest_sha256 is None:
            raise RuntimeAuthorityError(
                "committed approval promotion requires a recorded commit manifest"
            )
        observed = self._approval_or_none()
        if observed != self._temporary:
            raise RuntimeAuthorityError(
                "committed promotion requires the exact temporary approval"
            )
        committed_at = self._timestamp_factory()
        committed = self._temporary.promote(
            commit_manifest_sha256=self._commit_manifest_sha256,
            committed_at=committed_at,
        )
        reconciled = False
        try:
            self._store.replace_exact(
                self._temporary,
                committed,
                lock_held=True,
            )
        except BaseException:
            current = self._approval_or_none()
            if current == committed:
                reconciled = True
            else:
                raise
        if self._store.read() != committed:
            raise RuntimeAuthorityError("committed approval promotion did not verify exactly")
        receipt = CommittedActivationApprovalReceipt(
            transaction=self._transaction,
            approval_path=ACTIVATION_APPROVAL_PATH,
            phase=COMMITTED_APPROVAL_PHASE,
            package=self._package,
            lock_lease_id=committed.lock_lease_id,
            temporary_record_sha256=self._temporary.record_sha256,
            committed_record_sha256=committed.record_sha256,
            commit_manifest_sha256=self._commit_manifest_sha256,
            boot_eligible=True,
            atomically_promoted=True,
            exact_record_verified=True,
        )
        return ActivationApprovalAdapterResult(
            operation=ActivationApprovalLifecycleOperation.
            PROMOTE_COMMITTED_ACTIVATION_APPROVAL,
            status=AdapterStatus.PASS,
            detail=(
                "interrupted committed approval promotion reconciled exactly"
                if reconciled
                else "temporary approval atomically promoted to committed state"
            ),
            payload=receipt,
        )

    def close_disposable_transaction(self) -> None:
        self._require_open()
        current = self._approval_or_none()
        if current is not None and current.phase is ApprovalPhase.TEMPORARY:
            raise RuntimeAuthorityError(
                "refusing to release disposable lock while temporary approval exists"
            )
        self._verify_exact_lock(require_bound=self._lease_bound)
        descriptor = os.fstat(self._lock_fd)
        path_info = self._lock_path.lstat()
        if (
            (descriptor.st_dev, descriptor.st_ino) != self._lock_identity
            or (path_info.st_dev, path_info.st_ino) != self._lock_identity
        ):
            raise RuntimeAuthorityError(
                "refusing to close a substituted disposable transaction lock"
            )
        self._lock_path.unlink()
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._closed = True


def create_disposable_root(parent: Path) -> Path:
    """Create one fresh 0700 rehearsal root without touching production paths."""

    if not parent.is_absolute():
        raise RuntimeAuthorityError("disposable parent must be absolute")
    info = parent.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RuntimeAuthorityError("disposable parent must be a real directory")
    root = parent / f"a-clockwork-plex-stage-c21-approval.{secrets.token_hex(6)}"
    root.mkdir(mode=DIRECTORY_MODE)
    return root
