#!/usr/bin/python3
from __future__ import annotations

"""Disposable exact Stage C21 temporary approval remover.

The remover borrows an already-bound C20-shaped owner and the existing no-follow
approval-root descriptor. It may unlink only the fixed public temporary approval
and fsync that directory. It cannot create, write, replace, promote, acquire or
release the owner-held lock, run commands, manage services or access audio.
"""

import hashlib
import os
import stat
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .approval_record_plan_v7 import (
    ApprovalObservedStateV7,
    ApprovalRecordClassificationV7,
    CommittedApprovalRecordPlanV7,
    TemporaryApprovalRecordPlanV7,
    classify_approval_record_v7,
)
from .disposable_approval_root_v7 import (
    APPROVAL_MODE,
    APPROVAL_NAME,
    MAX_APPROVAL_BYTES,
    DisposableApprovalFileObservationV7,
    DisposableApprovalRootFailure,
    DisposableApprovalRootV7,
)
from .disposable_c20_lock_owner_v7 import DisposableC20LockOwnerV7
from .production_adapter_contract import AdapterStatus


FaultHook = Callable[[str], None]


def _noop_fault_hook(_point: str) -> None:
    return None


class DisposableTemporaryRemovalDispositionV7(str, Enum):
    TEMPORARY_REMOVED = "temporary-removed"
    TEMPORARY_RETAINED_RECOVERY = "temporary-retained-recovery"
    MANUAL_RECONCILIATION = "manual-reconciliation"


@dataclass(frozen=True)
class OpenTemporaryApprovalProofV7:
    descriptor: int
    device: int
    inode: int
    raw_content: bytes

    def __post_init__(self) -> None:
        if self.descriptor < 0 or self.device <= 0 or self.inode <= 0:
            raise ValueError("open temporary approval proof requires exact identity")
        if not self.raw_content or len(self.raw_content) > MAX_APPROVAL_BYTES:
            raise ValueError("open temporary approval proof requires bounded bytes")


@dataclass(frozen=True)
class DisposableTemporaryApprovalRemovalResultV7:
    status: AdapterStatus
    disposition: DisposableTemporaryRemovalDispositionV7
    observed_state: ApprovalObservedStateV7
    detail: str
    temporary_encoded_sha256: str
    reconciled_after_exception: bool
    reviewed_recovery_permitted: bool
    manual_reconciliation_required: bool
    owner_lock_remains_held: bool
    approval_absent: bool

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("temporary removal result requires detail")
        if (
            len(self.temporary_encoded_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.temporary_encoded_sha256
            )
        ):
            raise ValueError("temporary removal result requires a SHA-256")
        if self.disposition is DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED:
            if (
                self.status is not AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.ABSENT
                or self.reviewed_recovery_permitted
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or not self.approval_absent
            ):
                raise ValueError("removed temporary result is inconsistent")
        elif self.disposition is DisposableTemporaryRemovalDispositionV7.TEMPORARY_RETAINED_RECOVERY:
            if (
                self.status is AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.EXACT_TEMPORARY
                or self.reconciled_after_exception
                or not self.reviewed_recovery_permitted
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or self.approval_absent
            ):
                raise ValueError("retained temporary recovery result is inconsistent")
        elif self.disposition is DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION:
            if (
                self.status is AdapterStatus.PASS
                or self.reviewed_recovery_permitted
                or not self.manual_reconciliation_required
                or self.reconciled_after_exception
            ):
                raise ValueError("manual temporary removal result is inconsistent")


def _result(
    *,
    owner: DisposableC20LockOwnerV7,
    temporary: TemporaryApprovalRecordPlanV7,
    status: AdapterStatus,
    disposition: DisposableTemporaryRemovalDispositionV7,
    observed_state: ApprovalObservedStateV7,
    detail: str,
    reconciled_after_exception: bool = False,
    approval_absent: bool,
) -> DisposableTemporaryApprovalRemovalResultV7:
    return DisposableTemporaryApprovalRemovalResultV7(
        status=status,
        disposition=disposition,
        observed_state=observed_state,
        detail=detail,
        temporary_encoded_sha256=temporary.encoded_sha256,
        reconciled_after_exception=reconciled_after_exception,
        reviewed_recovery_permitted=(
            disposition
            is DisposableTemporaryRemovalDispositionV7.TEMPORARY_RETAINED_RECOVERY
        ),
        manual_reconciliation_required=(
            disposition
            is DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION
        ),
        owner_lock_remains_held=owner.lock_held,
        approval_absent=approval_absent,
    )


class DisposableTemporaryApprovalRemoverV7:
    """Exact public-name remover with descriptor-pinned reconciliation."""

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
            raise TypeError("temporary remover requires DisposableC20LockOwnerV7")
        if not isinstance(approval_root, DisposableApprovalRootV7):
            raise TypeError("temporary remover requires DisposableApprovalRootV7")
        if approval_root.owner is not owner or approval_root.path.parent.parent.parent.parent != owner.root:
            raise ValueError("temporary remover authorities use different roots")
        if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
            raise TypeError("temporary remover requires TemporaryApprovalRecordPlanV7")
        if not isinstance(committed, CommittedApprovalRecordPlanV7):
            raise TypeError("temporary remover requires CommittedApprovalRecordPlanV7")
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

    def _observe_and_classify(
        self,
    ) -> tuple[
        ApprovalRecordClassificationV7,
        DisposableApprovalFileObservationV7 | None,
    ]:
        observed = self._approval_root.observe_public()
        if observed.status is not AdapterStatus.PASS or observed.payload is None:
            return (
                classify_approval_record_v7(
                    self._temporary,
                    self._committed,
                    observed_raw=None,
                    observation_error=observed.detail,
                ),
                None,
            )
        raw = observed.payload.raw_content if observed.payload.present else None
        return (
            classify_approval_record_v7(
                self._temporary,
                self._committed,
                observed_raw=raw,
            ),
            observed.payload,
        )

    def _manual_result(
        self,
        state: ApprovalObservedStateV7,
        detail: str,
        *,
        approval_absent: bool,
    ) -> DisposableTemporaryApprovalRemovalResultV7:
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            status=AdapterStatus.FAIL,
            disposition=DisposableTemporaryRemovalDispositionV7.MANUAL_RECONCILIATION,
            observed_state=state,
            detail=detail,
            approval_absent=approval_absent,
        )

    def _open_exact_temporary(self) -> OpenTemporaryApprovalProofV7:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        file_fd: int | None = None
        try:
            self._fault_hook("before-public-open")
            file_fd = os.open(
                APPROVAL_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=dir_fd,
            )
            self._fault_hook("after-public-open")
            descriptor = os.fstat(file_fd)
            path_info = os.stat(
                APPROVAL_NAME,
                dir_fd=dir_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(descriptor.st_mode)
                or stat.S_ISLNK(path_info.st_mode)
                or not stat.S_ISREG(path_info.st_mode)
                or descriptor.st_dev != path_info.st_dev
                or descriptor.st_ino != path_info.st_ino
                or descriptor.st_uid != os.geteuid()
                or descriptor.st_gid != os.getegid()
                or path_info.st_uid != os.geteuid()
                or path_info.st_gid != os.getegid()
                or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
                or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
            ):
                raise DisposableApprovalRootFailure(
                    "public temporary approval metadata or identity mismatch"
                )
            if descriptor.st_size < 0 or descriptor.st_size > MAX_APPROVAL_BYTES:
                raise DisposableApprovalRootFailure(
                    "public temporary approval exceeds the bounded size"
                )
            raw = os.pread(file_fd, MAX_APPROVAL_BYTES + 1, 0)
            self._fault_hook("after-public-read")
            after = os.fstat(file_fd)
            after_path = os.stat(
                APPROVAL_NAME,
                dir_fd=dir_fd,
                follow_symlinks=False,
            )
            if (
                len(raw) != descriptor.st_size
                or (after.st_dev, after.st_ino, after.st_size)
                != (descriptor.st_dev, descriptor.st_ino, descriptor.st_size)
                or (after_path.st_dev, after_path.st_ino)
                != (descriptor.st_dev, descriptor.st_ino)
            ):
                raise DisposableApprovalRootFailure(
                    "public temporary approval changed during exact observation"
                )
            if (
                raw != self._temporary.encoded_bytes
                or hashlib.sha256(raw).hexdigest() != self._temporary.encoded_sha256
                or classify_approval_record_v7(
                    self._temporary,
                    self._committed,
                    observed_raw=raw,
                ).state
                is not ApprovalObservedStateV7.EXACT_TEMPORARY
            ):
                raise DisposableApprovalRootFailure(
                    "public approval is not the exact canonical temporary plan"
                )
            proof = OpenTemporaryApprovalProofV7(
                descriptor=file_fd,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
                raw_content=raw,
            )
            file_fd = None
            return proof
        finally:
            if file_fd is not None:
                os.close(file_fd)

    def _verify_open_proof(
        self,
        proof: OpenTemporaryApprovalProofV7,
        *,
        require_unlinked: bool,
    ) -> None:
        descriptor = os.fstat(proof.descriptor)
        if (
            not stat.S_ISREG(descriptor.st_mode)
            or (descriptor.st_dev, descriptor.st_ino) != (proof.device, proof.inode)
            or descriptor.st_uid != os.geteuid()
            or descriptor.st_gid != os.getegid()
            or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
            or descriptor.st_size != len(self._temporary.encoded_bytes)
        ):
            raise DisposableApprovalRootFailure(
                "open temporary approval descriptor identity changed"
            )
        raw = os.pread(proof.descriptor, MAX_APPROVAL_BYTES + 1, 0)
        after = os.fstat(proof.descriptor)
        if (
            raw != proof.raw_content
            or raw != self._temporary.encoded_bytes
            or hashlib.sha256(raw).hexdigest() != self._temporary.encoded_sha256
            or (after.st_dev, after.st_ino, after.st_size)
            != (descriptor.st_dev, descriptor.st_ino, descriptor.st_size)
        ):
            raise DisposableApprovalRootFailure(
                "open temporary approval descriptor bytes changed"
            )
        if require_unlinked and after.st_nlink != 0:
            raise DisposableApprovalRootFailure(
                "removed temporary approval inode still has a namespace link"
            )

    def _recheck_public_identity(self, proof: OpenTemporaryApprovalProofV7) -> None:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        self._fault_hook("before-final-name-recheck")
        path_info = os.stat(
            APPROVAL_NAME,
            dir_fd=dir_fd,
            follow_symlinks=False,
        )
        if (
            stat.S_ISLNK(path_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or (path_info.st_dev, path_info.st_ino) != (proof.device, proof.inode)
            or path_info.st_uid != os.geteuid()
            or path_info.st_gid != os.getegid()
            or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
        ):
            raise DisposableApprovalRootFailure(
                "public temporary approval name was substituted before unlink"
            )

    def _reconcile_exception(
        self,
        exc: BaseException,
        proof: OpenTemporaryApprovalProofV7 | None,
    ) -> DisposableTemporaryApprovalRemovalResultV7:
        try:
            owner_ok, owner_detail = self._verify_owner()
            classification, observation = self._observe_and_classify()
            if not owner_ok:
                return self._manual_result(
                    classification.state,
                    f"removal raised {type(exc).__name__}: {exc}; owner authority unavailable: {owner_detail}",
                    approval_absent=(
                        classification.state is ApprovalObservedStateV7.ABSENT
                    ),
                )
            if classification.state is ApprovalObservedStateV7.ABSENT:
                if proof is None:
                    return self._manual_result(
                        classification.state,
                        f"removal raised {type(exc).__name__}: {exc}; public approval is absent but no exact temporary descriptor was captured",
                        approval_absent=True,
                    )
                self._verify_open_proof(proof, require_unlinked=True)
                dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
                os.fsync(dir_fd)
                repeated, _repeated_observation = self._observe_and_classify()
                if repeated.state is not ApprovalObservedStateV7.ABSENT:
                    return self._manual_result(
                        repeated.state,
                        f"removal raised {type(exc).__name__}: {exc}; recovery absence did not remain stable",
                        approval_absent=False,
                    )
                owner_ok, owner_detail = self._verify_owner()
                if not owner_ok:
                    return self._manual_result(
                        repeated.state,
                        f"removal raised {type(exc).__name__}: {exc}; recovery lost owner authority: {owner_detail}",
                        approval_absent=True,
                    )
                return _result(
                    owner=self._owner,
                    temporary=self._temporary,
                    status=AdapterStatus.PASS,
                    disposition=DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED,
                    observed_state=ApprovalObservedStateV7.ABSENT,
                    detail=(
                        f"removal raised {type(exc).__name__}: {exc}; exact temporary inode was absent and directory durability was reconciled"
                    ),
                    reconciled_after_exception=True,
                    approval_absent=True,
                )
            if classification.state is ApprovalObservedStateV7.EXACT_TEMPORARY:
                if proof is not None:
                    if (
                        observation is None
                        or not observation.present
                        or (observation.device, observation.inode)
                        != (proof.device, proof.inode)
                    ):
                        return self._manual_result(
                            classification.state,
                            f"removal raised {type(exc).__name__}: {exc}; exact temporary bytes are now attached to a different inode",
                            approval_absent=False,
                        )
                    self._verify_open_proof(proof, require_unlinked=False)
                return _result(
                    owner=self._owner,
                    temporary=self._temporary,
                    status=AdapterStatus.FAIL,
                    disposition=(
                        DisposableTemporaryRemovalDispositionV7.TEMPORARY_RETAINED_RECOVERY
                    ),
                    observed_state=classification.state,
                    detail=(
                        f"removal raised {type(exc).__name__}: {exc}; exact temporary approval remains and may be retried only by a separately reviewed recovery invocation"
                    ),
                    approval_absent=False,
                )
            return self._manual_result(
                classification.state,
                f"removal raised {type(exc).__name__}: {exc}; observed approval is not removable temporary state",
                approval_absent=False,
            )
        except BaseException as reconciliation_exc:
            state = ApprovalObservedStateV7.OBSERVATION_FAILURE
            try:
                classification, _observation = self._observe_and_classify()
                state = classification.state
            except BaseException:
                pass
            return self._manual_result(
                state,
                f"removal raised {type(exc).__name__}: {exc}; exact reconciliation failed: {reconciliation_exc}",
                approval_absent=(state is ApprovalObservedStateV7.ABSENT),
            )

    def remove(self) -> DisposableTemporaryApprovalRemovalResultV7:
        owner_ok, owner_detail = self._verify_owner()
        if not owner_ok:
            return self._manual_result(
                ApprovalObservedStateV7.OBSERVATION_FAILURE,
                f"cannot establish pre-removal owner authority: {owner_detail}",
                approval_absent=False,
            )
        classification, _observation = self._observe_and_classify()
        if classification.state is not ApprovalObservedStateV7.EXACT_TEMPORARY:
            return self._manual_result(
                classification.state,
                "pre-existing approval is not the exact planned temporary rollback record",
                approval_absent=(classification.state is ApprovalObservedStateV7.ABSENT),
            )

        proof: OpenTemporaryApprovalProofV7 | None = None
        try:
            proof = self._open_exact_temporary()
            self._verify_open_proof(proof, require_unlinked=False)
            self._recheck_public_identity(proof)
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            os.unlink(APPROVAL_NAME, dir_fd=dir_fd)
            self._fault_hook("after-public-unlink")
            self._verify_open_proof(proof, require_unlinked=True)
            self._fault_hook("after-unlinked-descriptor-verification")
            self._fault_hook("before-removal-directory-fsync")
            os.fsync(dir_fd)
            self._fault_hook("after-removal-directory-fsync")
            self._fault_hook("before-absence-observation")
            final, _final_observation = self._observe_and_classify()
            self._fault_hook("after-absence-observation")
            if final.state is not ApprovalObservedStateV7.ABSENT:
                raise DisposableApprovalRootFailure(
                    "public temporary approval remains after exact unlink"
                )
            self._fault_hook("before-final-owner-verification")
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                raise DisposableApprovalRootFailure(owner_detail)
            self._fault_hook("after-final-owner-verification")
        except BaseException as exc:
            result = self._reconcile_exception(exc, proof)
            if proof is not None:
                try:
                    os.close(proof.descriptor)
                except OSError:
                    pass
            return result

        assert proof is not None
        os.close(proof.descriptor)
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            status=AdapterStatus.PASS,
            disposition=DisposableTemporaryRemovalDispositionV7.TEMPORARY_REMOVED,
            observed_state=ApprovalObservedStateV7.ABSENT,
            detail="exact canonical temporary approval inode removed and directory durability verified",
            approval_absent=True,
        )
