#!/usr/bin/python3
from __future__ import annotations

"""Read-only Stage C21 production baseline inspector.

This module observes the fixed pre-install appliance boundary and returns one
frozen in-memory report. It has no CLI, evidence writer, lock acquisition,
approval mutation, service/process/audio command or activation capability.
"""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from enum import Enum
from typing import Any

from scripts.stage_c_runtime_authority.model import (
    ActivationApprovalRecord,
    ApprovalPhase,
    RuntimeAuthorityError,
    canonical_json_bytes,
)

from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    DacSnapshot,
    HostContractSnapshot,
    LoopbackSnapshot,
    MixerSnapshot,
    PackageFingerprint,
    ProductionLockObservation,
    ServiceSnapshot,
)
from .read_only_host_adapter import ReadOnlyHostProductionAdapter


PRODUCTION_APPROVAL_DIRECTORY = "/var/lib/a-clockwork-plex/split-bus"
PRODUCTION_APPROVAL_PATH = (
    "/var/lib/a-clockwork-plex/split-bus/activation-approved"
)
APPROVAL_DIRECTORY_PARTS = ("var", "lib", "a-clockwork-plex", "split-bus")
APPROVAL_NAME = "activation-approved"
APPROVAL_MODE = 0o600
STATE_DIRECTORY_MODE = 0o755
MAX_APPROVAL_BYTES = 64 * 1024
ROOT_UID = 0
ROOT_GID = 0


class ProductionApprovalBaselineStateV7(str, Enum):
    ABSENT = "absent"
    VALID_TEMPORARY_UNBOUND = "valid-temporary-unbound"
    VALID_COMMITTED = "valid-committed"
    MISMATCHED = "mismatched"
    OBSERVATION_FAILURE = "observation-failure"


class ProductionPrepareOnlyDispositionV7(str, Enum):
    BASELINE_READY = "baseline-ready"
    EXISTING_APPROVAL_REQUIRES_REVIEW = "existing-approval-requires-review"
    PRODUCTION_LOCK_PRESENT = "production-lock-present"
    HOST_OBSERVATION_FAILED = "host-observation-failed"
    APPROVAL_OBSERVATION_UNAVAILABLE = "approval-observation-unavailable"


@dataclass(frozen=True)
class ProductionApprovalBaselineObservationV7:
    state: ProductionApprovalBaselineStateV7
    detail: str
    approval_path: str = PRODUCTION_APPROVAL_PATH
    raw_sha256: str | None = None
    device: int | None = None
    inode: int | None = None
    mode: int | None = None
    owner_uid: int | None = None
    owner_gid: int | None = None
    link_count: int | None = None
    size: int | None = None
    phase: ApprovalPhase | None = None
    transaction_id: str | None = None
    lock_lease_id: str | None = None
    package_fingerprint: str | None = None
    record_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("production approval observation requires detail")
        if self.approval_path != PRODUCTION_APPROVAL_PATH:
            raise ValueError("production approval observation uses the wrong path")

        metadata = (
            self.device,
            self.inode,
            self.mode,
            self.owner_uid,
            self.owner_gid,
            self.link_count,
            self.size,
        )
        record_identity = (
            self.phase,
            self.transaction_id,
            self.lock_lease_id,
            self.package_fingerprint,
            self.record_sha256,
        )

        if self.state is ProductionApprovalBaselineStateV7.ABSENT:
            if self.raw_sha256 is not None or any(
                value is not None for value in metadata + record_identity
            ):
                raise ValueError("absent approval observation cannot carry identity")
            return

        if self.state is ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE:
            if self.raw_sha256 is not None or any(
                value is not None for value in metadata + record_identity
            ):
                raise ValueError("failed approval observation cannot claim identity")
            return

        if any(value is None for value in metadata):
            raise ValueError("present approval observation requires exact metadata")
        assert self.device is not None and self.inode is not None
        assert self.owner_uid is not None and self.owner_gid is not None
        assert self.link_count is not None and self.size is not None
        if self.device <= 0 or self.inode <= 0:
            raise ValueError("present approval observation requires positive identity")
        if self.owner_uid < 0 or self.owner_gid < 0:
            raise ValueError("present approval observation requires a valid owner")
        if self.link_count <= 0 or self.size < 0:
            raise ValueError("present approval observation metadata is invalid")
        if self.raw_sha256 is not None and not _is_sha256(self.raw_sha256):
            raise ValueError("approval raw digest must be a lowercase SHA-256")

        valid_states = {
            ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND,
            ProductionApprovalBaselineStateV7.VALID_COMMITTED,
        }
        if self.state in valid_states:
            if self.raw_sha256 is None or any(
                value is None for value in record_identity
            ):
                raise ValueError("valid approval observation requires record identity")
            if (
                self.owner_uid != ROOT_UID
                or self.owner_gid != ROOT_GID
                or self.mode != APPROVAL_MODE
                or self.link_count != 1
                or not 0 < self.size <= MAX_APPROVAL_BYTES
            ):
                raise ValueError("valid approval observation metadata changed")
            assert self.package_fingerprint is not None
            assert self.record_sha256 is not None
            if not _is_sha256(self.package_fingerprint) or not _is_sha256(
                self.record_sha256
            ):
                raise ValueError("valid approval record digests are invalid")
            expected_phase = (
                ApprovalPhase.TEMPORARY
                if self.state
                is ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND
                else ApprovalPhase.COMMITTED
            )
            if self.phase is not expected_phase:
                raise ValueError("valid approval state and phase differ")
        elif self.state is ProductionApprovalBaselineStateV7.MISMATCHED:
            if any(value is not None for value in record_identity):
                raise ValueError("mismatched approval cannot claim record authority")
        else:  # pragma: no cover - exhaustive Enum guard
            raise ValueError("unsupported production approval baseline state")

    @property
    def present(self) -> bool:
        return self.state in {
            ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND,
            ProductionApprovalBaselineStateV7.VALID_COMMITTED,
            ProductionApprovalBaselineStateV7.MISMATCHED,
        }

    @property
    def canonical_record(self) -> bool:
        return self.state in {
            ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND,
            ProductionApprovalBaselineStateV7.VALID_COMMITTED,
        }


@dataclass(frozen=True)
class ProductionPrepareOnlyReportV7:
    status: AdapterStatus
    disposition: ProductionPrepareOnlyDispositionV7
    detail: str
    candidate_package: PackageFingerprint
    host_contract: AdapterResult[HostContractSnapshot]
    production_lock: AdapterResult[ProductionLockObservation]
    services: AdapterResult[ServiceSnapshot]
    mixer: AdapterResult[MixerSnapshot]
    loopback: AdapterResult[LoopbackSnapshot]
    dac: AdapterResult[DacSnapshot]
    approval: ProductionApprovalBaselineObservationV7
    production_mutation_authorised: bool = False
    activation_authorised: bool = False
    pi_execution_authorised: bool = False
    review_bundle_persisted: bool = False
    production_lock_acquired: bool = False
    transaction_created: bool = False

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("prepare-only report requires detail")
        if not isinstance(self.candidate_package, PackageFingerprint):
            raise TypeError("prepare-only report requires PackageFingerprint")
        for value in (
            self.production_mutation_authorised,
            self.activation_authorised,
            self.pi_execution_authorised,
            self.review_bundle_persisted,
            self.production_lock_acquired,
            self.transaction_created,
        ):
            if value:
                raise ValueError("prepare-only report cannot grant authority")

        expected = (
            (self.host_contract, AdapterOperation.INSPECT_HOST_CONTRACT, HostContractSnapshot),
            (self.production_lock, AdapterOperation.INSPECT_PRODUCTION_LOCK, ProductionLockObservation),
            (self.services, AdapterOperation.CAPTURE_SERVICE_STATE, ServiceSnapshot),
            (self.mixer, AdapterOperation.CAPTURE_MIXER_STATE, MixerSnapshot),
            (self.loopback, AdapterOperation.CAPTURE_LOOPBACK_STATE, LoopbackSnapshot),
            (self.dac, AdapterOperation.CAPTURE_DAC_STATE, DacSnapshot),
        )
        for result, operation, payload_type in expected:
            if not isinstance(result, AdapterResult) or result.operation is not operation:
                raise ValueError("prepare-only report operation identity changed")
            if result.status is AdapterStatus.PASS and not isinstance(
                result.payload, payload_type
            ):
                raise ValueError("successful prepare-only observation has wrong payload")

        lock_present = bool(
            self.production_lock.status is AdapterStatus.PASS
            and self.production_lock.payload is not None
            and self.production_lock.payload.exists
        )
        other_results = (
            self.host_contract,
            self.services,
            self.mixer,
            self.loopback,
            self.dac,
        )
        other_failed = any(
            result.status is not AdapterStatus.PASS for result in other_results
        )

        if self.disposition is ProductionPrepareOnlyDispositionV7.BASELINE_READY:
            if (
                self.status is not AdapterStatus.PASS
                or self.approval.state is not ProductionApprovalBaselineStateV7.ABSENT
                or self.production_lock.status is not AdapterStatus.PASS
                or lock_present
                or other_failed
            ):
                raise ValueError("baseline-ready report is inconsistent")
        elif self.disposition is ProductionPrepareOnlyDispositionV7.APPROVAL_OBSERVATION_UNAVAILABLE:
            if (
                self.status is AdapterStatus.PASS
                or self.approval.state
                is not ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE
            ):
                raise ValueError("approval-unavailable report is inconsistent")
        elif self.disposition is ProductionPrepareOnlyDispositionV7.EXISTING_APPROVAL_REQUIRES_REVIEW:
            if self.status is AdapterStatus.PASS or not self.approval.present:
                raise ValueError("existing-approval report is inconsistent")
        elif self.disposition is ProductionPrepareOnlyDispositionV7.PRODUCTION_LOCK_PRESENT:
            if (
                self.status is AdapterStatus.PASS
                or self.approval.state is not ProductionApprovalBaselineStateV7.ABSENT
                or not lock_present
            ):
                raise ValueError("production-lock-present report is inconsistent")
        elif self.disposition is ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED:
            if (
                self.status is AdapterStatus.PASS
                or self.approval.state is not ProductionApprovalBaselineStateV7.ABSENT
                or not (
                    self.production_lock.status is not AdapterStatus.PASS
                    or (not lock_present and other_failed)
                )
            ):
                raise ValueError("host-observation-failed report is inconsistent")
        else:  # pragma: no cover - exhaustive Enum guard
            raise ValueError("unsupported prepare-only disposition")

    @property
    def ready_for_human_review(self) -> bool:
        return self.disposition is ProductionPrepareOnlyDispositionV7.BASELINE_READY


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _record_field_types_are_exact(payload: dict[str, Any]) -> bool:
    integer_fields = {
        "schema_version",
        "loopback_index",
        "loopback_pcm_substreams",
        "loopback_pcm_notify",
        "dac_device",
        "sample_rate",
        "period_size",
        "buffer_size",
    }
    nullable_string_fields = {"commit_manifest_sha256", "committed_at"}
    expected_fields = set(ActivationApprovalRecord.__dataclass_fields__)
    if set(payload) != expected_fields:
        return False
    for key, value in payload.items():
        if key in integer_fields:
            if isinstance(value, bool) or not isinstance(value, int):
                return False
        elif key in nullable_string_fields:
            if value is not None and not isinstance(value, str):
                return False
        elif not isinstance(value, str):
            return False
    return True


def _present_observation(
    *,
    state: ProductionApprovalBaselineStateV7,
    detail: str,
    raw_sha256: str | None,
    file_info: os.stat_result,
    record: ActivationApprovalRecord | None = None,
) -> ProductionApprovalBaselineObservationV7:
    return ProductionApprovalBaselineObservationV7(
        state=state,
        detail=detail,
        raw_sha256=raw_sha256,
        device=file_info.st_dev,
        inode=file_info.st_ino,
        mode=stat.S_IMODE(file_info.st_mode),
        owner_uid=file_info.st_uid,
        owner_gid=file_info.st_gid,
        link_count=file_info.st_nlink,
        size=file_info.st_size,
        phase=record.phase if record is not None else None,
        transaction_id=record.transaction_id if record is not None else None,
        lock_lease_id=record.lock_lease_id if record is not None else None,
        package_fingerprint=(
            record.package_fingerprint if record is not None else None
        ),
        record_sha256=record.record_sha256 if record is not None else None,
    )


def classify_production_approval_bytes_v7(
    raw: bytes,
    *,
    file_info: os.stat_result,
) -> ProductionApprovalBaselineObservationV7:
    """Classify already descriptor-pinned bytes without granting path authority."""

    raw_sha256 = hashlib.sha256(raw).hexdigest()
    mode = stat.S_IMODE(file_info.st_mode)
    if (
        not stat.S_ISREG(file_info.st_mode)
        or file_info.st_uid != ROOT_UID
        or file_info.st_gid != ROOT_GID
        or mode != APPROVAL_MODE
        or file_info.st_nlink != 1
        or not 0 < file_info.st_size <= MAX_APPROVAL_BYTES
        or len(raw) != file_info.st_size
    ):
        return _present_observation(
            state=ProductionApprovalBaselineStateV7.MISMATCHED,
            detail="production approval metadata does not match the fixed contract",
            raw_sha256=raw_sha256,
            file_info=file_info,
        )

    try:
        decoded = raw.decode("utf-8")
        envelope = json.loads(decoded, object_pairs_hook=_strict_json_object)
        if not isinstance(envelope, dict) or set(envelope) != {
            "record",
            "record_sha256",
        }:
            raise ValueError("approval envelope fields differ")
        payload = envelope["record"]
        embedded_sha = envelope["record_sha256"]
        if not isinstance(payload, dict) or not isinstance(embedded_sha, str):
            raise ValueError("approval envelope types differ")
        if not _record_field_types_are_exact(payload):
            raise ValueError("approval record field types differ")
        record = ActivationApprovalRecord.from_dict(payload)
        if embedded_sha != record.record_sha256:
            raise ValueError("approval record checksum differs")
        canonical = canonical_json_bytes(
            {
                "record": record.as_dict(),
                "record_sha256": record.record_sha256,
            }
        ) + b"\n"
        if raw != canonical:
            raise ValueError("approval bytes are not canonical")
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeAuthorityError, ValueError) as exc:
        return _present_observation(
            state=ProductionApprovalBaselineStateV7.MISMATCHED,
            detail=f"production approval record mismatch: {exc}",
            raw_sha256=raw_sha256,
            file_info=file_info,
        )

    state = (
        ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND
        if record.phase is ApprovalPhase.TEMPORARY
        else ProductionApprovalBaselineStateV7.VALID_COMMITTED
    )
    return _present_observation(
        state=state,
        detail=(
            "canonical temporary approval observed without held transaction authority"
            if state
            is ProductionApprovalBaselineStateV7.VALID_TEMPORARY_UNBOUND
            else "canonical committed approval observed for separate human review"
        ),
        raw_sha256=raw_sha256,
        file_info=file_info,
        record=record,
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _approval_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_uid,
        left.st_gid,
        left.st_nlink,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_uid,
        right.st_gid,
        right.st_nlink,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _validate_directory(
    descriptor: int,
    path_info: os.stat_result,
    *,
    private_state_directory: bool,
) -> None:
    descriptor_info = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(descriptor_info.st_mode)
        or stat.S_ISLNK(path_info.st_mode)
        or not stat.S_ISDIR(path_info.st_mode)
        or descriptor_info.st_dev != path_info.st_dev
        or descriptor_info.st_ino != path_info.st_ino
        or descriptor_info.st_uid != ROOT_UID
        or descriptor_info.st_gid != ROOT_GID
        or path_info.st_uid != ROOT_UID
        or path_info.st_gid != ROOT_GID
    ):
        raise OSError("production approval ancestor identity or owner mismatch")
    descriptor_mode = stat.S_IMODE(descriptor_info.st_mode)
    path_mode = stat.S_IMODE(path_info.st_mode)
    if private_state_directory:
        if descriptor_mode != STATE_DIRECTORY_MODE or path_mode != STATE_DIRECTORY_MODE:
            raise OSError("production Stage C state directory mode differs from 0755")
    elif descriptor_mode & 0o022 or path_mode & 0o022:
        raise OSError("production approval system ancestor is group/world writable")


def observe_production_approval_baseline_v7(
) -> ProductionApprovalBaselineObservationV7:
    """Observe only the one fixed production approval path without mutation."""

    current_fd: int | None = None
    approval_fd: int | None = None
    try:
        current_fd = os.open("/", _directory_flags())
        root_path = os.stat("/", follow_symlinks=False)
        _validate_directory(
            current_fd,
            root_path,
            private_state_directory=False,
        )

        for index, part in enumerate(APPROVAL_DIRECTORY_PARTS):
            try:
                path_info = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            except FileNotFoundError:
                return ProductionApprovalBaselineObservationV7(
                    state=ProductionApprovalBaselineStateV7.ABSENT,
                    detail=f"fixed production approval ancestor is absent: {part}",
                )
            next_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            try:
                _validate_directory(
                    next_fd,
                    path_info,
                    private_state_directory=index >= 2,
                )
            except BaseException:
                os.close(next_fd)
                raise
            os.close(current_fd)
            current_fd = next_fd

        try:
            path_before = os.stat(
                APPROVAL_NAME,
                dir_fd=current_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return ProductionApprovalBaselineObservationV7(
                state=ProductionApprovalBaselineStateV7.ABSENT,
                detail="fixed production approval record is absent",
            )

        if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(
            path_before.st_mode
        ):
            return _present_observation(
                state=ProductionApprovalBaselineStateV7.MISMATCHED,
                detail="production approval public object is not a regular file",
                raw_sha256=None,
                file_info=path_before,
            )

        approval_fd = os.open(APPROVAL_NAME, _approval_flags(), dir_fd=current_fd)
        descriptor_before = os.fstat(approval_fd)
        if not _same_stat(descriptor_before, path_before):
            raise OSError("production approval descriptor/path identity changed before read")
        if descriptor_before.st_size > MAX_APPROVAL_BYTES:
            return _present_observation(
                state=ProductionApprovalBaselineStateV7.MISMATCHED,
                detail="production approval record exceeds the bounded size",
                raw_sha256=None,
                file_info=descriptor_before,
            )

        raw = os.pread(approval_fd, descriptor_before.st_size + 1, 0)
        descriptor_after = os.fstat(approval_fd)
        path_after = os.stat(
            APPROVAL_NAME,
            dir_fd=current_fd,
            follow_symlinks=False,
        )
        if (
            not _same_stat(descriptor_before, descriptor_after)
            or not _same_stat(descriptor_after, path_after)
            or len(raw) != descriptor_after.st_size
        ):
            raise OSError("production approval changed during bounded observation")
        return classify_production_approval_bytes_v7(
            raw,
            file_info=descriptor_after,
        )
    except BaseException as exc:
        return ProductionApprovalBaselineObservationV7(
            state=ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE,
            detail=f"fixed production approval observation failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if approval_fd is not None:
            os.close(approval_fd)
        if current_fd is not None:
            os.close(current_fd)


def _failed_observation(
    operation: AdapterOperation,
    exc: BaseException,
) -> AdapterResult[Any]:
    return AdapterResult(
        operation=operation,
        status=AdapterStatus.FAIL,
        detail=f"read-only production observation raised {type(exc).__name__}: {exc}",
    )


class ProductionPrepareOnlyInspectorV7:
    """Fixed baseline observer with no transaction or mutation authority."""

    __slots__ = ("_adapter", "_candidate_package")

    def __init__(
        self,
        adapter: ReadOnlyHostProductionAdapter,
        candidate_package: PackageFingerprint,
    ) -> None:
        if type(adapter) is not ReadOnlyHostProductionAdapter:
            raise TypeError("prepare-only inspector requires the exact read-only host adapter")
        if type(candidate_package) is not PackageFingerprint:
            raise TypeError("prepare-only inspector requires PackageFingerprint")
        self._adapter = adapter
        self._candidate_package = candidate_package

    def inspect(self) -> ProductionPrepareOnlyReportV7:
        try:
            host_contract = self._adapter.inspect_host_contract()
        except BaseException as exc:
            host_contract = _failed_observation(
                AdapterOperation.INSPECT_HOST_CONTRACT,
                exc,
            )
        try:
            production_lock = self._adapter.inspect_production_lock()
        except BaseException as exc:
            production_lock = _failed_observation(
                AdapterOperation.INSPECT_PRODUCTION_LOCK,
                exc,
            )
        try:
            services = self._adapter.capture_service_state(
                self._adapter.observation_transaction
            )
        except BaseException as exc:
            services = _failed_observation(
                AdapterOperation.CAPTURE_SERVICE_STATE,
                exc,
            )
        try:
            mixer = self._adapter.capture_mixer_state(
                self._adapter.observation_transaction
            )
        except BaseException as exc:
            mixer = _failed_observation(
                AdapterOperation.CAPTURE_MIXER_STATE,
                exc,
            )
        try:
            loopback = self._adapter.capture_loopback_state(
                self._adapter.observation_transaction
            )
        except BaseException as exc:
            loopback = _failed_observation(
                AdapterOperation.CAPTURE_LOOPBACK_STATE,
                exc,
            )
        try:
            dac = self._adapter.capture_dac_state(
                self._adapter.observation_transaction
            )
        except BaseException as exc:
            dac = _failed_observation(
                AdapterOperation.CAPTURE_DAC_STATE,
                exc,
            )
        approval = observe_production_approval_baseline_v7()

        lock_present = bool(
            production_lock.status is AdapterStatus.PASS
            and production_lock.payload is not None
            and production_lock.payload.exists
        )
        host_results = (host_contract, services, mixer, loopback, dac)

        if approval.state is ProductionApprovalBaselineStateV7.OBSERVATION_FAILURE:
            disposition = (
                ProductionPrepareOnlyDispositionV7.APPROVAL_OBSERVATION_UNAVAILABLE
            )
            detail = "production approval could not be observed safely"
        elif approval.present:
            disposition = (
                ProductionPrepareOnlyDispositionV7.EXISTING_APPROVAL_REQUIRES_REVIEW
            )
            detail = "existing production approval state requires separate review"
        elif production_lock.status is not AdapterStatus.PASS:
            disposition = ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED
            detail = "production lock observation failed"
        elif lock_present:
            disposition = ProductionPrepareOnlyDispositionV7.PRODUCTION_LOCK_PRESENT
            detail = "production lock is present; baseline first-install review is blocked"
        elif any(result.status is not AdapterStatus.PASS for result in host_results):
            disposition = ProductionPrepareOnlyDispositionV7.HOST_OBSERVATION_FAILED
            detail = "one or more fixed host observations failed"
        else:
            disposition = ProductionPrepareOnlyDispositionV7.BASELINE_READY
            detail = "fixed untouched-appliance baseline is ready for human review only"

        return ProductionPrepareOnlyReportV7(
            status=(
                AdapterStatus.PASS
                if disposition is ProductionPrepareOnlyDispositionV7.BASELINE_READY
                else AdapterStatus.FAIL
            ),
            disposition=disposition,
            detail=detail,
            candidate_package=self._candidate_package,
            host_contract=host_contract,
            production_lock=production_lock,
            services=services,
            mixer=mixer,
            loopback=loopback,
            dac=dac,
            approval=approval,
        )
