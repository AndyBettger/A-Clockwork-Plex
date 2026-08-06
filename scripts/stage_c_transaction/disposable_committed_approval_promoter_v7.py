#!/usr/bin/python3
from __future__ import annotations

"""Disposable one-way Stage C21 committed approval promoter.

The promoter requires an already-bound disposable C20 owner and the existing
no-follow approval-root authority. It may create one private committed candidate,
exchange that candidate once with the fixed public temporary approval, remove
only the parked exact temporary inode and fsync the held approval directory.

There is deliberately no reverse-exchange path. Once exact committed bytes are
public, every automatic action is forward recovery.
"""

import ctypes
import hashlib
import os
import secrets
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


PRIVATE_PREFIX = ".activation-approved.stage-c21-commit-"
RENAME_EXCHANGE = 2
FaultHook = Callable[[str], None]


def _noop_fault_hook(_point: str) -> None:
    return None


def _rename_exchange(dir_fd: int, private_name: str) -> None:
    if dir_fd < 0:
        raise ValueError("committed exchange requires a live directory descriptor")
    if not private_name.startswith(PRIVATE_PREFIX) or "/" in private_name:
        raise ValueError("committed exchange private name is invalid")
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise DisposableApprovalRootFailure("renameat2 is unavailable") from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        dir_fd,
        os.fsencode(private_name),
        dir_fd,
        os.fsencode(APPROVAL_NAME),
        RENAME_EXCHANGE,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), f"{private_name}<->{APPROVAL_NAME}")


def _write_all_at(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while view:
        written = os.pwrite(fd, view, offset)
        if written <= 0:
            raise OSError("short disposable committed approval write")
        offset += written
        view = view[written:]


class DisposableCommittedPromotionDispositionV7(str, Enum):
    COMMITTED_PROMOTED = "committed-promoted"
    TEMPORARY_RETAINED_RECOVERY = "temporary-retained-recovery"
    COMMITTED_FORWARD_RECOVERY_REQUIRED = "committed-forward-recovery-required"
    MANUAL_RECONCILIATION = "manual-reconciliation"


@dataclass(frozen=True)
class OpenApprovalProofV7:
    descriptor: int
    device: int
    inode: int
    raw_content: bytes

    def __post_init__(self) -> None:
        if self.descriptor < 0 or self.device <= 0 or self.inode <= 0:
            raise ValueError("open approval proof requires exact identity")
        if not self.raw_content or len(self.raw_content) > MAX_APPROVAL_BYTES:
            raise ValueError("open approval proof requires bounded bytes")


@dataclass(frozen=True)
class DisposableCommittedApprovalPromotionResultV7:
    status: AdapterStatus
    disposition: DisposableCommittedPromotionDispositionV7
    observed_state: ApprovalObservedStateV7
    detail: str
    temporary_encoded_sha256: str
    committed_encoded_sha256: str
    reconciled_after_exception: bool
    reviewed_retry_permitted: bool
    forward_recovery_required: bool
    manual_reconciliation_required: bool
    owner_lock_remains_held: bool
    private_name_absent: bool
    public_temporary_identity_proved: bool
    public_committed_identity_proved: bool

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("committed promotion result requires detail")
        for value in (
            self.temporary_encoded_sha256,
            self.committed_encoded_sha256,
        ):
            if len(value) != 64 or any(
                character not in "0123456789abcdef" for character in value
            ):
                raise ValueError("committed promotion result requires SHA-256 values")
        if self.public_temporary_identity_proved and self.public_committed_identity_proved:
            raise ValueError("public approval cannot prove both temporary and committed identity")
        if self.disposition is DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED:
            if (
                self.status is not AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.EXACT_COMMITTED
                or self.reviewed_retry_permitted
                or self.forward_recovery_required
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or not self.private_name_absent
                or self.public_temporary_identity_proved
                or not self.public_committed_identity_proved
            ):
                raise ValueError("promoted committed result is inconsistent")
        elif (
            self.disposition
            is DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY
        ):
            if (
                self.status is AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.EXACT_TEMPORARY
                or self.reconciled_after_exception
                or not self.reviewed_retry_permitted
                or self.forward_recovery_required
                or self.manual_reconciliation_required
                or not self.owner_lock_remains_held
                or not self.private_name_absent
                or not self.public_temporary_identity_proved
                or self.public_committed_identity_proved
            ):
                raise ValueError("retained temporary recovery result is inconsistent")
        elif (
            self.disposition
            is DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED
        ):
            if (
                self.status is AdapterStatus.PASS
                or self.observed_state is not ApprovalObservedStateV7.EXACT_COMMITTED
                or self.reconciled_after_exception
                or self.reviewed_retry_permitted
                or not self.forward_recovery_required
                or not self.manual_reconciliation_required
                or self.public_temporary_identity_proved
            ):
                raise ValueError("committed forward-recovery result is inconsistent")
        elif self.disposition is DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION:
            if (
                self.status is AdapterStatus.PASS
                or self.reconciled_after_exception
                or self.reviewed_retry_permitted
                or self.forward_recovery_required
                or not self.manual_reconciliation_required
            ):
                raise ValueError("manual committed promotion result is inconsistent")


def _result(
    *,
    owner: DisposableC20LockOwnerV7,
    temporary: TemporaryApprovalRecordPlanV7,
    committed: CommittedApprovalRecordPlanV7,
    status: AdapterStatus,
    disposition: DisposableCommittedPromotionDispositionV7,
    observed_state: ApprovalObservedStateV7,
    detail: str,
    reconciled_after_exception: bool = False,
    private_name_absent: bool,
    public_temporary_identity_proved: bool = False,
    public_committed_identity_proved: bool = False,
) -> DisposableCommittedApprovalPromotionResultV7:
    return DisposableCommittedApprovalPromotionResultV7(
        status=status,
        disposition=disposition,
        observed_state=observed_state,
        detail=detail,
        temporary_encoded_sha256=temporary.encoded_sha256,
        committed_encoded_sha256=committed.encoded_sha256,
        reconciled_after_exception=reconciled_after_exception,
        reviewed_retry_permitted=(
            disposition
            is DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY
        ),
        forward_recovery_required=(
            disposition
            is DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED
        ),
        manual_reconciliation_required=(
            disposition
            in {
                DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED,
                DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            }
        ),
        owner_lock_remains_held=owner.lock_held,
        private_name_absent=private_name_absent,
        public_temporary_identity_proved=public_temporary_identity_proved,
        public_committed_identity_proved=public_committed_identity_proved,
    )


class DisposableCommittedApprovalPromoterV7:
    """One-shot atomic exchange with irreversible committed-state recovery."""

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
            raise TypeError("committed promoter requires DisposableC20LockOwnerV7")
        if not isinstance(approval_root, DisposableApprovalRootV7):
            raise TypeError("committed promoter requires DisposableApprovalRootV7")
        if (
            approval_root.owner is not owner
            or approval_root.path.parent.parent.parent.parent != owner.root
        ):
            raise ValueError("committed promoter authorities use different roots")
        if not isinstance(temporary, TemporaryApprovalRecordPlanV7):
            raise TypeError("committed promoter requires TemporaryApprovalRecordPlanV7")
        if not isinstance(committed, CommittedApprovalRecordPlanV7):
            raise TypeError("committed promoter requires CommittedApprovalRecordPlanV7")
        if temporary.binding_sha256 != committed.binding_sha256:
            raise ValueError("temporary and committed plans use different bindings")
        if temporary.record_sha256 != committed.temporary_record_sha256:
            raise ValueError("committed plan does not derive from the temporary plan")
        if temporary.record.lock_lease_id != owner.lease_id:
            raise ValueError("temporary approval lease differs from disposable owner")
        if committed.record.lock_lease_id != owner.lease_id:
            raise ValueError("committed approval lease differs from disposable owner")
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
            return False, "disposable owner lease differs from the approval plans"
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

    def _verify_open_proof(
        self,
        proof: OpenApprovalProofV7,
        *,
        expected_bytes: bytes,
        expected_sha256: str,
        expected_links: int | None,
    ) -> None:
        descriptor = os.fstat(proof.descriptor)
        if (
            not stat.S_ISREG(descriptor.st_mode)
            or (descriptor.st_dev, descriptor.st_ino) != (proof.device, proof.inode)
            or descriptor.st_uid != os.geteuid()
            or descriptor.st_gid != os.getegid()
            or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
            or descriptor.st_size != len(expected_bytes)
        ):
            raise DisposableApprovalRootFailure("open approval descriptor identity changed")
        raw = os.pread(proof.descriptor, MAX_APPROVAL_BYTES + 1, 0)
        after = os.fstat(proof.descriptor)
        if (
            raw != proof.raw_content
            or raw != expected_bytes
            or hashlib.sha256(raw).hexdigest() != expected_sha256
            or (after.st_dev, after.st_ino, after.st_size)
            != (descriptor.st_dev, descriptor.st_ino, descriptor.st_size)
        ):
            raise DisposableApprovalRootFailure("open approval descriptor bytes changed")
        if expected_links is not None and after.st_nlink != expected_links:
            raise DisposableApprovalRootFailure(
                f"open approval descriptor has {after.st_nlink} links, expected {expected_links}"
            )

    def _recheck_name(
        self,
        name: str,
        proof: OpenApprovalProofV7,
    ) -> None:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        path_info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        if (
            stat.S_ISLNK(path_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or (path_info.st_dev, path_info.st_ino) != (proof.device, proof.inode)
            or path_info.st_uid != os.geteuid()
            or path_info.st_gid != os.getegid()
            or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
        ):
            raise DisposableApprovalRootFailure(
                f"approval name was substituted or changed: {name}"
            )

    def _name_absent(self, name: str | None) -> bool:
        if name is None:
            return True
        try:
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            return True
        except BaseException:
            return False
        return False

    def _open_public_temporary(self) -> OpenApprovalProofV7:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        file_fd: int | None = None
        try:
            self._fault_hook("before-public-temporary-open")
            file_fd = os.open(
                APPROVAL_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=dir_fd,
            )
            self._fault_hook("after-public-temporary-open")
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
                or (descriptor.st_dev, descriptor.st_ino)
                != (path_info.st_dev, path_info.st_ino)
                or descriptor.st_uid != os.geteuid()
                or descriptor.st_gid != os.getegid()
                or path_info.st_uid != os.geteuid()
                or path_info.st_gid != os.getegid()
                or stat.S_IMODE(descriptor.st_mode) != APPROVAL_MODE
                or stat.S_IMODE(path_info.st_mode) != APPROVAL_MODE
                or descriptor.st_size < 0
                or descriptor.st_size > MAX_APPROVAL_BYTES
            ):
                raise DisposableApprovalRootFailure(
                    "public temporary approval metadata or identity mismatch"
                )
            raw = os.pread(file_fd, MAX_APPROVAL_BYTES + 1, 0)
            self._fault_hook("after-public-temporary-read")
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
                or raw != self._temporary.encoded_bytes
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
            proof = OpenApprovalProofV7(
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

    def _create_committed_candidate(
        self,
    ) -> tuple[str, OpenApprovalProofV7]:
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        private_name = f"{PRIVATE_PREFIX}{secrets.token_hex(12)}"
        candidate_fd: int | None = None
        try:
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
            descriptor = os.fstat(candidate_fd)
            proof = OpenApprovalProofV7(
                descriptor=candidate_fd,
                device=descriptor.st_dev,
                inode=descriptor.st_ino,
                raw_content=self._committed.encoded_bytes,
            )
            self._fault_hook("after-candidate-create")
            _write_all_at(candidate_fd, self._committed.encoded_bytes)
            self._fault_hook("after-candidate-write")
            os.ftruncate(candidate_fd, len(self._committed.encoded_bytes))
            self._fault_hook("after-candidate-truncate")
            os.fsync(candidate_fd)
            self._fault_hook("after-candidate-fsync")
            self._verify_open_proof(
                proof,
                expected_bytes=self._committed.encoded_bytes,
                expected_sha256=self._committed.encoded_sha256,
                expected_links=1,
            )
            self._recheck_name(private_name, proof)
            if classify_approval_record_v7(
                self._temporary,
                self._committed,
                observed_raw=os.pread(candidate_fd, MAX_APPROVAL_BYTES + 1, 0),
            ).state is not ApprovalObservedStateV7.EXACT_COMMITTED:
                raise DisposableApprovalRootFailure(
                    "private candidate is not the exact committed plan"
                )
            candidate_fd = None
            return private_name, proof
        finally:
            if candidate_fd is not None:
                os.close(candidate_fd)

    def _public_identity_matches(
        self,
        observation: DisposableApprovalFileObservationV7 | None,
        proof: OpenApprovalProofV7 | None,
    ) -> bool:
        return bool(
            observation is not None
            and observation.present
            and proof is not None
            and (observation.device, observation.inode) == (proof.device, proof.inode)
        )

    def _unlink_private_exact(
        self,
        private_name: str,
        proof: OpenApprovalProofV7,
        *,
        expected_bytes: bytes,
        expected_sha256: str,
    ) -> None:
        self._verify_open_proof(
            proof,
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            expected_links=1,
        )
        self._recheck_name(private_name, proof)
        dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
        os.unlink(private_name, dir_fd=dir_fd)
        self._verify_open_proof(
            proof,
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            expected_links=0,
        )

    def _manual_result(
        self,
        state: ApprovalObservedStateV7,
        detail: str,
        *,
        private_name: str | None,
        public_temporary_identity_proved: bool = False,
        public_committed_identity_proved: bool = False,
    ) -> DisposableCommittedApprovalPromotionResultV7:
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            committed=self._committed,
            status=AdapterStatus.FAIL,
            disposition=DisposableCommittedPromotionDispositionV7.MANUAL_RECONCILIATION,
            observed_state=state,
            detail=detail,
            private_name_absent=self._name_absent(private_name),
            public_temporary_identity_proved=public_temporary_identity_proved,
            public_committed_identity_proved=public_committed_identity_proved,
        )

    def _forward_result(
        self,
        detail: str,
        *,
        private_name: str | None,
        public_committed_identity_proved: bool,
    ) -> DisposableCommittedApprovalPromotionResultV7:
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            committed=self._committed,
            status=AdapterStatus.FAIL,
            disposition=(
                DisposableCommittedPromotionDispositionV7.COMMITTED_FORWARD_RECOVERY_REQUIRED
            ),
            observed_state=ApprovalObservedStateV7.EXACT_COMMITTED,
            detail=detail,
            private_name_absent=self._name_absent(private_name),
            public_committed_identity_proved=public_committed_identity_proved,
        )

    def _reconcile_committed(
        self,
        exc: BaseException,
        temporary_proof: OpenApprovalProofV7 | None,
        candidate_proof: OpenApprovalProofV7 | None,
        private_name: str | None,
        observation: DisposableApprovalFileObservationV7 | None,
    ) -> DisposableCommittedApprovalPromotionResultV7:
        if not self._public_identity_matches(observation, candidate_proof):
            return self._forward_result(
                f"promotion raised {type(exc).__name__}: {exc}; exact committed bytes are public but not on the tracked candidate inode",
                private_name=private_name,
                public_committed_identity_proved=False,
            )
        assert candidate_proof is not None
        try:
            self._verify_open_proof(
                candidate_proof,
                expected_bytes=self._committed.encoded_bytes,
                expected_sha256=self._committed.encoded_sha256,
                expected_links=1,
            )
            self._recheck_name(APPROVAL_NAME, candidate_proof)
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            os.fsync(dir_fd)
            if private_name is None or temporary_proof is None:
                raise DisposableApprovalRootFailure(
                    "committed state lacks the tracked parked temporary identity"
                )
            if self._name_absent(private_name):
                self._verify_open_proof(
                    temporary_proof,
                    expected_bytes=self._temporary.encoded_bytes,
                    expected_sha256=self._temporary.encoded_sha256,
                    expected_links=0,
                )
            else:
                self._unlink_private_exact(
                    private_name,
                    temporary_proof,
                    expected_bytes=self._temporary.encoded_bytes,
                    expected_sha256=self._temporary.encoded_sha256,
                )
            os.fsync(dir_fd)
            repeated, repeated_observation = self._observe_and_classify()
            if (
                repeated.state is not ApprovalObservedStateV7.EXACT_COMMITTED
                or not self._public_identity_matches(
                    repeated_observation,
                    candidate_proof,
                )
                or not self._name_absent(private_name)
            ):
                raise DisposableApprovalRootFailure(
                    "committed forward recovery did not reach stable exact state"
                )
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                raise DisposableApprovalRootFailure(owner_detail)
        except BaseException as recovery_exc:
            return self._forward_result(
                f"promotion raised {type(exc).__name__}: {exc}; committed forward recovery remains required: {recovery_exc}",
                private_name=private_name,
                public_committed_identity_proved=True,
            )
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            committed=self._committed,
            status=AdapterStatus.PASS,
            disposition=DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED,
            observed_state=ApprovalObservedStateV7.EXACT_COMMITTED,
            detail=(
                f"promotion raised {type(exc).__name__}: {exc}; exact committed state was reconciled forward without reverse exchange"
            ),
            reconciled_after_exception=True,
            private_name_absent=True,
            public_committed_identity_proved=True,
        )

    def _reconcile_temporary(
        self,
        exc: BaseException,
        temporary_proof: OpenApprovalProofV7 | None,
        candidate_proof: OpenApprovalProofV7 | None,
        private_name: str | None,
        observation: DisposableApprovalFileObservationV7 | None,
    ) -> DisposableCommittedApprovalPromotionResultV7:
        if not self._public_identity_matches(observation, temporary_proof):
            return self._manual_result(
                ApprovalObservedStateV7.EXACT_TEMPORARY,
                f"promotion raised {type(exc).__name__}: {exc}; exact temporary bytes are attached to a different inode",
                private_name=private_name,
            )
        assert temporary_proof is not None
        try:
            self._verify_open_proof(
                temporary_proof,
                expected_bytes=self._temporary.encoded_bytes,
                expected_sha256=self._temporary.encoded_sha256,
                expected_links=1,
            )
            self._recheck_name(APPROVAL_NAME, temporary_proof)
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            if private_name is not None and candidate_proof is not None:
                if self._name_absent(private_name):
                    self._verify_open_proof(
                        candidate_proof,
                        expected_bytes=self._committed.encoded_bytes,
                        expected_sha256=self._committed.encoded_sha256,
                        expected_links=0,
                    )
                else:
                    self._unlink_private_exact(
                        private_name,
                        candidate_proof,
                        expected_bytes=self._committed.encoded_bytes,
                        expected_sha256=self._committed.encoded_sha256,
                    )
            os.fsync(dir_fd)
            repeated, repeated_observation = self._observe_and_classify()
            if (
                repeated.state is not ApprovalObservedStateV7.EXACT_TEMPORARY
                or not self._public_identity_matches(
                    repeated_observation,
                    temporary_proof,
                )
                or not self._name_absent(private_name)
            ):
                raise DisposableApprovalRootFailure(
                    "temporary recovery did not retain stable exact state"
                )
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                raise DisposableApprovalRootFailure(owner_detail)
        except BaseException as recovery_exc:
            return self._manual_result(
                ApprovalObservedStateV7.EXACT_TEMPORARY,
                f"promotion raised {type(exc).__name__}: {exc}; exact temporary cleanup failed: {recovery_exc}",
                private_name=private_name,
                public_temporary_identity_proved=True,
            )
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            committed=self._committed,
            status=AdapterStatus.FAIL,
            disposition=(
                DisposableCommittedPromotionDispositionV7.TEMPORARY_RETAINED_RECOVERY
            ),
            observed_state=ApprovalObservedStateV7.EXACT_TEMPORARY,
            detail=(
                f"promotion raised {type(exc).__name__}: {exc}; exact original temporary approval remains and a separately reviewed retry is permitted"
            ),
            private_name_absent=True,
            public_temporary_identity_proved=True,
        )

    def _reconcile_exception(
        self,
        exc: BaseException,
        temporary_proof: OpenApprovalProofV7 | None,
        candidate_proof: OpenApprovalProofV7 | None,
        private_name: str | None,
    ) -> DisposableCommittedApprovalPromotionResultV7:
        try:
            owner_ok, owner_detail = self._verify_owner()
            classification, observation = self._observe_and_classify()
            if classification.state is ApprovalObservedStateV7.EXACT_COMMITTED:
                if not owner_ok:
                    return self._forward_result(
                        f"promotion raised {type(exc).__name__}: {exc}; committed bytes are public but owner authority is unavailable: {owner_detail}",
                        private_name=private_name,
                        public_committed_identity_proved=self._public_identity_matches(
                            observation,
                            candidate_proof,
                        ),
                    )
                return self._reconcile_committed(
                    exc,
                    temporary_proof,
                    candidate_proof,
                    private_name,
                    observation,
                )
            if not owner_ok:
                return self._manual_result(
                    classification.state,
                    f"promotion raised {type(exc).__name__}: {exc}; owner authority unavailable: {owner_detail}",
                    private_name=private_name,
                )
            if classification.state is ApprovalObservedStateV7.EXACT_TEMPORARY:
                return self._reconcile_temporary(
                    exc,
                    temporary_proof,
                    candidate_proof,
                    private_name,
                    observation,
                )
            return self._manual_result(
                classification.state,
                f"promotion raised {type(exc).__name__}: {exc}; observed approval cannot be reconciled automatically",
                private_name=private_name,
            )
        except BaseException as reconciliation_exc:
            state = ApprovalObservedStateV7.OBSERVATION_FAILURE
            observation = None
            try:
                classification, observation = self._observe_and_classify()
                state = classification.state
            except BaseException:
                pass
            if state is ApprovalObservedStateV7.EXACT_COMMITTED:
                return self._forward_result(
                    f"promotion raised {type(exc).__name__}: {exc}; committed reconciliation failed: {reconciliation_exc}",
                    private_name=private_name,
                    public_committed_identity_proved=self._public_identity_matches(
                        observation,
                        candidate_proof,
                    ),
                )
            return self._manual_result(
                state,
                f"promotion raised {type(exc).__name__}: {exc}; exact reconciliation failed: {reconciliation_exc}",
                private_name=private_name,
            )

    def promote(self) -> DisposableCommittedApprovalPromotionResultV7:
        owner_ok, owner_detail = self._verify_owner()
        if not owner_ok:
            return self._manual_result(
                ApprovalObservedStateV7.OBSERVATION_FAILURE,
                f"cannot establish pre-promotion owner authority: {owner_detail}",
                private_name=None,
            )
        classification, _observation = self._observe_and_classify()
        if classification.state is not ApprovalObservedStateV7.EXACT_TEMPORARY:
            return self._manual_result(
                classification.state,
                "pre-existing approval is not the exact planned temporary record",
                private_name=None,
            )

        temporary_proof: OpenApprovalProofV7 | None = None
        candidate_proof: OpenApprovalProofV7 | None = None
        private_name: str | None = None
        try:
            temporary_proof = self._open_public_temporary()
            self._verify_open_proof(
                temporary_proof,
                expected_bytes=self._temporary.encoded_bytes,
                expected_sha256=self._temporary.encoded_sha256,
                expected_links=1,
            )
            private_name, candidate_proof = self._create_committed_candidate()
            self._verify_open_proof(
                candidate_proof,
                expected_bytes=self._committed.encoded_bytes,
                expected_sha256=self._committed.encoded_sha256,
                expected_links=1,
            )
            self._fault_hook("before-final-exchange-name-recheck")
            self._recheck_name(APPROVAL_NAME, temporary_proof)
            self._recheck_name(private_name, candidate_proof)
            dir_fd = self._approval_root._borrow_directory_descriptor_for_publisher()
            _rename_exchange(dir_fd, private_name)
            self._fault_hook("after-exchange")

            self._verify_open_proof(
                candidate_proof,
                expected_bytes=self._committed.encoded_bytes,
                expected_sha256=self._committed.encoded_sha256,
                expected_links=1,
            )
            self._verify_open_proof(
                temporary_proof,
                expected_bytes=self._temporary.encoded_bytes,
                expected_sha256=self._temporary.encoded_sha256,
                expected_links=1,
            )
            self._recheck_name(APPROVAL_NAME, candidate_proof)
            self._recheck_name(private_name, temporary_proof)

            self._fault_hook("before-exchange-directory-fsync")
            os.fsync(dir_fd)
            self._fault_hook("after-exchange-directory-fsync")
            self._fault_hook("before-committed-observation")
            committed_classification, committed_observation = self._observe_and_classify()
            self._fault_hook("after-committed-observation")
            if (
                committed_classification.state
                is not ApprovalObservedStateV7.EXACT_COMMITTED
                or not self._public_identity_matches(
                    committed_observation,
                    candidate_proof,
                )
            ):
                raise DisposableApprovalRootFailure(
                    "public approval is not the tracked exact committed candidate"
                )

            self._fault_hook("before-parked-temporary-unlink")
            self._recheck_name(private_name, temporary_proof)
            os.unlink(private_name, dir_fd=dir_fd)
            self._fault_hook("after-parked-temporary-unlink")
            self._verify_open_proof(
                temporary_proof,
                expected_bytes=self._temporary.encoded_bytes,
                expected_sha256=self._temporary.encoded_sha256,
                expected_links=0,
            )

            self._fault_hook("before-cleanup-directory-fsync")
            os.fsync(dir_fd)
            self._fault_hook("after-cleanup-directory-fsync")
            self._fault_hook("before-final-committed-observation")
            final, final_observation = self._observe_and_classify()
            self._fault_hook("after-final-committed-observation")
            if (
                final.state is not ApprovalObservedStateV7.EXACT_COMMITTED
                or not self._public_identity_matches(final_observation, candidate_proof)
                or not self._name_absent(private_name)
            ):
                raise DisposableApprovalRootFailure(
                    "final public approval is not stable exact committed state"
                )
            self._fault_hook("before-final-owner-verification")
            owner_ok, owner_detail = self._verify_owner()
            if not owner_ok:
                raise DisposableApprovalRootFailure(owner_detail)
            self._fault_hook("after-final-owner-verification")
        except BaseException as exc:
            result = self._reconcile_exception(
                exc,
                temporary_proof,
                candidate_proof,
                private_name,
            )
            for proof in (candidate_proof, temporary_proof):
                if proof is not None:
                    try:
                        os.close(proof.descriptor)
                    except OSError:
                        pass
            return result

        assert temporary_proof is not None and candidate_proof is not None
        os.close(candidate_proof.descriptor)
        os.close(temporary_proof.descriptor)
        return _result(
            owner=self._owner,
            temporary=self._temporary,
            committed=self._committed,
            status=AdapterStatus.PASS,
            disposition=DisposableCommittedPromotionDispositionV7.COMMITTED_PROMOTED,
            observed_state=ApprovalObservedStateV7.EXACT_COMMITTED,
            detail="exact temporary approval atomically promoted and parked temporary inode durably removed",
            private_name_absent=True,
            public_committed_identity_proved=True,
        )
