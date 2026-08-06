#!/usr/bin/python3
from __future__ import annotations

"""Disposable no-replace Stage C21 temporary approval publisher.

The publisher requires an already-bound disposable C20 lock owner and one
separate no-follow approval-root authority. It may create one tracked private
candidate, hard-link it to the fixed public name without replacement, fsync the
namespace and remove only its private name.

It contains no production path, committed promotion, command, service, process,
audio endpoint or generic dispatch boundary.
"""

import hashlib
import os
import secrets
import stat
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .approval_authority_binding_v7 import ApprovalPublicationKnowledgeV7
from .approval_record_plan_v7 import (
    ApprovalObservedStateV7,
    CommittedApprovalRecordPlanV7,
    IndeterminateResolutionActionV7,
    TemporaryApprovalRecordPlanV7,
    classify_approval_record_v7,
    resolve_indeterminate_approval_v7,
)
from .disposable_approval_root_v7 import (
    APPROVAL_MODE,
    APPROVAL_NAME,
    MAX_APPROVAL_BYTES,
    DisposableApprovalRootFailure,
    DisposableApprovalRootV7,
)
from .disposable_c20_lock_owner_v7 import DisposableC20LockOwnerV7
from .production_adapter_contract import AdapterStatus


PRIVATE_PREFIX = ".activation-approved.stage-c21-"
FaultHook = Callable[[str], None]


def _noop_fault_hook(_point: str) -> None:
    return None


class DisposableTemporaryPublicationDispositionV7(str, Enum):
    TEMPORARY_PUBLISHED = "temporary-published"
    APPROVAL_ABSENT_ROLLBACK = "approval-absent-rollback"
    MANUAL_RECONCILIATION = "manual-reconciliation"


@dataclass(frozen=True)
class TrackedPrivateCandidateV7:
    name: str
    device: int
    inode: int

    def __post_init__(self) -> None:
        if not self.name.startswith(PRIVATE_PREFIX):
            raise ValueError("tracked temporary candidate uses the wrong private prefix")
        if "/" in self.name or self.device <= 0 or self.inode <= 0:
            raise ValueError("tracked temporary candidate identity is invalid")


@dataclass(frozen=True)
class PrivateCandidateObservationV7:
    present: bool
    raw_content: bytes | None = None
    device: int | None = None
    inode: int | None = None

    def __post_init__(self) -> None:
        if self.present:
            if (
                self.raw_content is None
                or self.device is None
                or self.inode is None
                or self.device <= 0
                or self.inode <= 0
            ):
                raise ValueError("present private candidate requires exact identity")
        elif any(
            value is not None
            for value in (self.raw_content, self.device, self.inode)
        ):
            raise ValueError("absent private candidate cannot carry identity")


@dataclass(frozen=True)
class DisposableTemporaryApprovalPublicationResultV7:
    status: AdapterStatus
    disposition: DisposableTemporaryPublicationDispositionV7
    observed_state: ApprovalObservedStateV7
    detail: str
    temporary_encoded_sha256: str
    reconciled_after_exception: bool
    ordinary_rollback_permitted: bool
    manual_reconciliation_required: bool
    owner_lock_remains_held: bool
    private_name_absent: bool

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("temporary publication result requires detail")
        if (
            len(self.temporary_encoded_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.temporary_encoded_sha256
            )
        ):
            raise ValueError("temporary publication result requires a SHA-256")
        if self.disposition is DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED:
            if (
                self.status is not AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.EXACT_TEMPORARY
                or self.ordinary_rollback_permitted
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or not self.private_name_absent
            ):
                raise ValueError("published temporary result is inconsistent")
        elif self.disposition is DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK:
            if (
                self.status is AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.ABSENT
                or not self.ordinary_rollback_permitted
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or not self.private_name_absent
                or self.reconciled_after_exception
            ):
                raise ValueError("approval-absent rollback result is inconsistent")
        elif self.disposition is DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION:
            if (
                self.status is AdapterStatus.PASS
                or self.ordinary_rollback_permitted
                or not self.manual_reconciliation_required
                or self.reconciled_after_exception
            ):
                raise ValueError("manual reconciliation result is inconsistent")


def _result(
    *,
    owner: DisposableC20LockOwnerV7,
    temporary: TemporaryApprovalRecordPlanV7,
    status: AdapterStatus,
    disposition: DisposableTemporaryPublicationDispositionV7,
    observed_state: ApprovalObservedStateV7,
    detail: str,
    reconciled_after_exception: bool = False,
    private_name_absent: bool,
) -> DisposableTemporaryApprovalPublicationResultV7:
    return DisposableTemporaryApprovalPublicationResultV7(
        status=status,
        disposition=disposition,
        observed_state=observed_state,
        detail=detail,
        temporary_encoded_sha256=temporary.encoded_sha256,
        reconciled_after_exception=reconciled_after_exception,
        ordinary_rollback_permitted=(
            disposition
            is DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK
        ),
        manual_reconciliation_required=(
            disposition
            is DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION
        ),
        owner_lock_remains_held=owner.lock_held,
        private_name_absent=private_name_absent,
    )


def _write_all_at(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while view:
        written = os.pwrite(fd, view, offset)
        if written <= 0:
            raise OSError("short disposable temporary approval write")
        offset += written
        view = view[written:]


class DisposableTemporaryApprovalPublisherV7:
    """One-shot temporary publisher with exact post-exception reconciliation."""

    def __init__(
        self,
        owner: DisposableC20LockOwnerV7,
        approval_root: DisposableApprovalRootV7,
        temporary: TemporaryApprovalRecordPlanV7,
        committed: CommittedApprovalRecordPlanV7,
        *,
        fault_hook: FaultHook | None = None,
    ) -> None:
        if not isinstance(owner, DisposableC20LockOwnerV7):
            raise TypeError("temporary publisher requires DisposableC20LockOwnerV7")
        if not isinstance(approval_root, DisposableApprovalRootV7):
            raise TypeError("temporary publisher requires DisposableApprovalRootV7")
        if approval_root.owner is not owner or approval_root.path.parent.parent.parent.parent != owner.root:
            raise ValueError("temporary publisher authorities use different roots")
        if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
            raise TypeError("temporary publisher requires TemporaryApprovalRecordPlanV7")
        if not isinstance(committed, CommittedApprovalRecordPlanV7):
            raise TypeError("temporary publisher requires CommittedApprovalRecordPlanV7")
        if temporary.binding_sha256 != committed.binding_sha256:
            raise ValueError("temporary and committed plans use different bindings")
        if temporary.record_sha256 != committed.temporary_record_sha256:
            raise ValueError("committed plan does not derive from the temporary plan")
        if temporary.record.lock_lease_id != owner.lease_id:
            raise ValueError("temporary approval lease differs from disposable owner")
        self._owner = owner
        self._approval_root = approval_root
        self._temporary = temporary
        self._committed = committed
        self._fault_hook = fault_hook or _noop_fault_hook

    def _verify_owner(self) -> tuple[bool, str]:
        observed = self._owner.observe()
        if observed.status is not AdapterStatus.PASS or observed.payload is None:
            return False, observed.detail
        if observed.payload.raw_content != self._owner.canonical_lease_bytes:
            return False, "disposable owner lock does not contain the exact canonical lease"
        if observed.payload.lease_id != self._temporary.record.lock_lease_id:
            return False, "disposable owner lease differs from the temporary plan"
        return True, "exact disposable owner authority and canonical lease verified"

    def _classify_public(self):
        observed = self._approval_root.observe_public()
        if observed.status is not AdapterStatus.PASS or observed.payload is None:
            return classify_approval_record_v7(
                self._temporary,
                self._committed,
                observed_raw=None,
                observation_error=observed.detail,
            )
        raw = observed.payload.raw_content if observed.payload.present else None
        return classify_approval_record_v7(
            self._temporary,
            self._committed,
            observed_raw=raw,
        )

    def _observe_private(
        self,
        tracked: TrackedPrivateCandidateV7,
    ) -> PrivateCandidateObservationV7:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        file_fd: int | None = None
        try:
            try:
                file_fd = os.open(
                    tracked.name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=dir_fd,
                )
            except FileNotFoundError:
                return PrivateCandidateObservationV7(present=False)
            descriptor = os.fstat(file_fd)
            path_info = os.stat(
                tracked.name,
                dir_fd=dir_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or not stat.S_ISREG(path_info.st_mode)
                or descriptor.st_dev != path_info.st_dev
                or descriptor.st_ino != path_info.st_ino
                or (descriptor.st_dev, descriptor.st_ino)
                != (tracked.device, tracked.inode)
                or descriptor.st_uid != os.geteuid()
                or descriptor.st_gid != os.getegid()
                or path_info.st_uid != os.geteuid()
                or path_info.st_gid != os.getegid()
                or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
                or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
            ):
                raise DisposableApprovalRootFailure(
                    "tracked temporary private candidate was substituted"
                )
            if descriptor.st_size < 0 or descriptor.st_size > MAX_APPROVAL_BYTES:
                raise DisposableApprovalRootFailure(
                    "tracked temporary private candidate is too large"
                )
            raw = os.pread(file_fd, MAX_APPROVAL_BYTES + 1, 0)
            after = os.fstat(file_fd)
            if (
                len(raw) != descriptor.st_size
                or (after.st_dev, after.st_ino, after.st_size)
                != (descriptor.st_dev, descriptor.st_ino, descriptor.st_size)
            ):
                raise DisposableApprovalRootFailure(
                    "tracked temporary private candidate changed during observation"
                )
            return PrivateCandidateObservationV7(
                present=True,
                raw_content=raw,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
            )
        finally:
            if file_fd is not None:
                os.close(file_fd)

    def _private_absent(self, tracked: TrackedPrivateCandidateV7 | None) -> bool:
        if tracked is None:
            return True
        try:
            return not self._observe_private(tracked).present
        except (OSError, DisposableApprovalRootFailure):
            return False

    def _remove_private_exact(
        self,
        tracked: TrackedPrivateCandidateV7 | None,
        *,
        require_public_alias: bool,
    ) -> None:
        if tracked is None:
            return
        observed = self._observe_private(tracked)
        if not observed.present:
            return
        if require_public_alias:
            public = self._approval_root.observe_public()
            if (
                public.status is not AdapterStatus.PASS
                or public.payload is None
                or not public.payload.present
                or public.payload.raw_content != self._temporary.encoded_bytes
                or (public.payload.device, public.payload.inode)
                != (tracked.device, tracked.inode)
            ):
                raise DisposableApprovalRootFailure(
                    "public temporary approval is not the tracked private alias"
                )
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        self._fault_hook("before-private-unlink")
        os.unlink(tracked.name, dir_fd=dir_fd)
        self._fault_hook("after-private-unlink")
        os.fsync(dir_fd)
        self._fault_hook("after-cleanup-directory-fsync")
        if self._observe_private(tracked).present:
            raise DisposableApprovalRootFailure(
                "tracked temporary private name remains after unlink"
            )

    def _manual_result(
        self,
        state: ApprovalObservedStateV7,
        detail: str,
        tracked: TrackedPrivateCandidateV7 | None,
    ) -> DisposableTemporaryApprovalPublicationResultV7:
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            status=AdapterStatus.FAIL,
            disposition=(
                DisposableTemporaryPublicationDispositionV7.MANUAL_RECONCILIATION
            ),
            observed_state=state,
            detail=detail,
            private_name_absent=self._private_absent(tracked),
        )

    def _reconcile_exception(
        self,
        exc: BaseException,
        tracked: TrackedPrivateCandidateV7 | None,
    ) -> DisposableTemporaryApprovalPublicationResultV7:
        owner_ok, owner_detail = self._verify_owner()
        classification = self._classify_public()
        if not owner_ok:
            return self._manual_result(
                classification.state,
                f"publication raised {type(exc).__name__}: {exc}; owner authority unavailable: {owner_detail}",
                tracked,
            )
        resolution = resolve_indeterminate_approval_v7(
            ApprovalPublicationKnowledgeV7.TEMPORARY_PUBLICATION_INDETERMINATE,
            classification,
        )
        try:
            if resolution.action is IndeterminateResolutionActionV7.EXACT_ROLLBACK_APPROVAL_ABSENT:
                self._remove_private_exact(tracked, require_public_alias=False)
                owner_ok, owner_detail = self._verify_owner()
                if not owner_ok:
                    raise DisposableApprovalRootFailure(owner_detail)
                return _result(
                    owner=self._owner,
                    temporary=self._temporary,
                    status=AdapterStatus.FAIL,
                    disposition=(
                        DisposableTemporaryPublicationDispositionV7.APPROVAL_ABSENT_ROLLBACK
                    ),
                    observed_state=classification.state,
                    detail=(
                        f"publication raised {type(exc).__name__}: {exc}; public approval remained absent and the exact tracked private candidate was removed"
                    ),
                    private_name_absent=True,
                )
            if resolution.action is IndeterminateResolutionActionV7.CONTINUE_TEMPORARY_INSTALL:
                self._remove_private_exact(tracked, require_public_alias=True)
                owner_ok, owner_detail = self._verify_owner()
                if not owner_ok:
                    raise DisposableApprovalRootFailure(owner_detail)
                return _result(
                    owner=self._owner,
                    temporary=self._temporary,
                    status=AdapterStatus.PASS,
                    disposition=(
                        DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED
                    ),
                    observed_state=classification.state,
                    detail=(
                        f"publication raised {type(exc).__name__}: {exc}; exact temporary approval was observed and reconciled without retry"
                    ),
                    reconciled_after_exception=True,
                    private_name_absent=True,
                )
        except (OSError, DisposableApprovalRootFailure) as cleanup_exc:
            return self._manual_result(
                classification.state,
                f"publication raised {type(exc).__name__}: {exc}; exact reconciliation failed: {cleanup_exc}",
                tracked,
            )
        return self._manual_result(
            classification.state,
            f"publication raised {type(exc).__name__}: {exc}; {resolution.detail}",
            tracked,
        )

    def publish(self) -> DisposableTemporaryApprovalPublicationResultV7:
        tracked: TrackedPrivateCandidateV7 | None = None
        owner_ok, owner_detail = self._verify_owner()
        if not owner_ok:
            return self._manual_result(
                ApprovalObservedStateV7.OBSERVATION_FAILURE,
                f"cannot establish pre-publication owner authority: {owner_detail}",
                tracked,
            )
        classification = self._classify_public()
        if classification.state is ApprovalObservedStateV7.EXACT_TEMPORARY:
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                return self._manual_result(
                    classification.state,
                    f"idempotent temporary observation lost owner authority: {owner_detail}",
                    tracked,
                )
            return _result(
                owner=self._owner,
                temporary=self._temporary,
                status=AdapterStatus.PASS,
                disposition=(
                    DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED
                ),
                observed_state=classification.state,
                detail="exact temporary approval was already published; no mutation was required",
                private_name_absent=True,
            )
        if classification.state is not ApprovalObservedStateV7.ABSENT:
            return self._manual_result(
                classification.state,
                "pre-existing approval is not the exact planned temporary record",
                tracked,
            )

        candidate_fd: int | None = None
        try:
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            private_name = f"{PRIVATE_PREFIX}{secrets.token_hex(12)}"
            self._fault_hook("before-candidate-create")
            candidate_fd = os.open(
                private_name,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                APPROVAL_MODE,
                dir_fd=dir_fd,
            )
            os.fchmod(candidate_fd, APPROVAL_MODE)
            os.fchown(candidate_fd, os.geteuid(), os.getegid())
            descriptor = os.fstat(candidate_fd)
            tracked = TrackedPrivateCandidateV7(
                name=private_name,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
            )
            self._fault_hook("after-candidate-create")
            _write_all_at(candidate_fd, self._temporary.encoded_bytes)
            self._fault_hook("after-candidate-write")
            os.ftruncate(candidate_fd, len(self._temporary.encoded_bytes))
            self._fault_hook("after-candidate-exact-truncate")
            os.fsync(candidate_fd)
            self._fault_hook("after-candidate-fsync")
            candidate = self._observe_private(tracked)
            if (
                not candidate.present
                or candidate.raw_content != self._temporary.encoded_bytes
                or hashlib.sha256(candidate.raw_content).hexdigest()
                != self._temporary.encoded_sha256
            ):
                raise DisposableApprovalRootFailure(
                    "private temporary candidate differs from the exact plan"
                )
            os.close(candidate_fd)
            candidate_fd = None

            self._fault_hook("before-public-link")
            os.link(
                tracked.name,
                APPROVAL_NAME,
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
                follow_symlinks=False,
            )
            self._fault_hook("after-public-link")
            os.fsync(dir_fd)
            self._fault_hook("after-publication-directory-fsync")
            public = self._approval_root.observe_public()
            if (
                public.status is not AdapterStatus.PASS
                or public.payload is None
                or not public.payload.present
                or public.payload.raw_content != self._temporary.encoded_bytes
                or (public.payload.device, public.payload.inode)
                != (tracked.device, tracked.inode)
            ):
                raise DisposableApprovalRootFailure(
                    "public temporary approval differs from the tracked candidate"
                )
            self._remove_private_exact(tracked, require_public_alias=True)
            final = self._classify_public()
            if final.state is not ApprovalObservedStateV7.EXACT_TEMPORARY:
                raise DisposableApprovalRootFailure(
                    "final public approval is not the exact temporary plan"
                )
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                raise DisposableApprovalRootFailure(owner_detail)
        except BaseException as exc:
            if candidate_fd is not None:
                try:
                    os.close(candidate_fd)
                except OSError:
                    pass
            return self._reconcile_exception(exc, tracked)

        return _result(
            owner=self._owner,
            temporary=self._temporary,
            status=AdapterStatus.PASS,
            disposition=(
                DisposableTemporaryPublicationDispositionV7.TEMPORARY_PUBLISHED
            ),
            observed_state=ApprovalObservedStateV7.EXACT_TEMPORARY,
            detail="exact temporary approval published without replacement and durably cleaned",
            private_name_absent=True,
        )
