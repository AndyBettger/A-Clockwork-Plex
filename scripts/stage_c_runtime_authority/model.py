#!/usr/bin/python3
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


SHA256_RE = re.compile(r"[0-9a-f]{64}")
TOKEN_RE = re.compile(r"[A-Za-z0-9_.:@+-]{1,160}")
EXPECTED_MANAGED_UNITS = (
    "a-clockwork-plex-audio-route.service",
    "a-clockwork-plex-camilladsp.service",
    "a-clockwork-plex-audio-failback.service",
)


class RuntimeAuthorityError(RuntimeError):
    """A fail-closed runtime-authority contract violation."""


class ApprovalPhase(str, Enum):
    TEMPORARY = "temporary-transaction-bound"
    COMMITTED = "committed-boot-eligible"


class RuntimeMode(str, Enum):
    OFFLINE = "offline"
    SPLIT_BUS_ACTIVE = "split-bus-active"
    DIRECT_FAILBACK = "direct-failback"


class RuntimeAction(str, Enum):
    ACCEPT_INSTALL_HANDOFF = "accept-install-transaction-handoff"
    PUBLISH_TEMPORARY_APPROVAL = "publish-temporary-activation-approval"
    PROMOTE_COMMITTED_APPROVAL = "promote-committed-activation-approval"
    ACQUIRE_PRODUCTION_LOCK = "acquire-production-lock"
    VALIDATE_COMMITTED_STATE = "validate-committed-stage-c-state"
    SELECT_SPLIT_BUS_ROUTE = "select-split-bus-route"
    START_CAMILLADSP = "start-camilladsp"
    VERIFY_SPLIT_BUS_HEALTH = "verify-split-bus-health"
    PUBLISH_SPLIT_BUS_ACTIVE = "publish-split-bus-active"
    STOP_CAMILLADSP = "stop-camilladsp"
    SELECT_DIRECT_FAILBACK_ROUTE = "select-direct-failback-route"
    PUBLISH_DIRECT_FAILBACK = "publish-direct-failback"
    RELEASE_PRODUCTION_LOCK = "release-production-lock"


def _require_token(label: str, value: str) -> str:
    if not TOKEN_RE.fullmatch(value):
        raise RuntimeAuthorityError(f"invalid {label}: {value!r}")
    return value


def _require_sha256(label: str, value: str) -> str:
    if not SHA256_RE.fullmatch(value):
        raise RuntimeAuthorityError(f"invalid {label}: {value!r}")
    return value


def utc_timestamp(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise RuntimeAuthorityError("timestamp must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_timestamp(label: str, value: str) -> str:
    if not value.endswith("Z"):
        raise RuntimeAuthorityError(f"invalid {label}: {value!r}")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RuntimeAuthorityError(f"invalid {label}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeAuthorityError(f"invalid {label}: {value!r}")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if canonical != value:
        raise RuntimeAuthorityError(f"non-canonical {label}: {value!r}")
    return value


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class HardwareContract:
    package_fingerprint: str
    split_route_sha256: str
    direct_route_sha256: str
    camilladsp_config_sha256: str
    camilladsp_binary_version: str
    camilladsp_binary_sha256: str
    loopback_index: int
    loopback_id: str
    loopback_pcm_substreams: int
    loopback_pcm_notify: int
    dac_card: str
    dac_device: int
    sample_rate: int
    sample_format: str
    period_size: int
    buffer_size: int

    def __post_init__(self) -> None:
        for label, value in (
            ("package fingerprint", self.package_fingerprint),
            ("split route digest", self.split_route_sha256),
            ("direct route digest", self.direct_route_sha256),
            ("CamillaDSP config digest", self.camilladsp_config_sha256),
            ("CamillaDSP binary digest", self.camilladsp_binary_sha256),
        ):
            _require_sha256(label, value)
        _require_token("CamillaDSP version", self.camilladsp_binary_version)
        _require_token("loopback id", self.loopback_id)
        _require_token("DAC card", self.dac_card)
        _require_token("sample format", self.sample_format)
        for label, value, minimum in (
            ("loopback index", self.loopback_index, 0),
            ("loopback substreams", self.loopback_pcm_substreams, 1),
            ("loopback notify", self.loopback_pcm_notify, 0),
            ("DAC device", self.dac_device, 0),
            ("sample rate", self.sample_rate, 1),
            ("period size", self.period_size, 1),
            ("buffer size", self.buffer_size, 1),
        ):
            if value < minimum:
                raise RuntimeAuthorityError(f"invalid {label}: {value}")
        if self.buffer_size < self.period_size:
            raise RuntimeAuthorityError("buffer size must be at least one period")

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_fingerprint": self.package_fingerprint,
            "split_route_sha256": self.split_route_sha256,
            "direct_route_sha256": self.direct_route_sha256,
            "camilladsp_config_sha256": self.camilladsp_config_sha256,
            "camilladsp_binary_version": self.camilladsp_binary_version,
            "camilladsp_binary_sha256": self.camilladsp_binary_sha256,
            "loopback_index": self.loopback_index,
            "loopback_id": self.loopback_id,
            "loopback_pcm_substreams": self.loopback_pcm_substreams,
            "loopback_pcm_notify": self.loopback_pcm_notify,
            "dac_card": self.dac_card,
            "dac_device": self.dac_device,
            "sample_rate": self.sample_rate,
            "sample_format": self.sample_format,
            "period_size": self.period_size,
            "buffer_size": self.buffer_size,
        }


@dataclass(frozen=True)
class UnitObservation:
    name: str
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str

    def __post_init__(self) -> None:
        _require_token("unit name", self.name)
        for label, value in (
            ("load state", self.load_state),
            ("active state", self.active_state),
            ("sub state", self.sub_state),
            ("unit-file state", self.unit_file_state),
        ):
            if value:
                _require_token(label, value)

    @property
    def is_loaded_inactive(self) -> bool:
        return (
            self.load_state == "loaded"
            and self.active_state == "inactive"
            and self.sub_state == "dead"
            and self.unit_file_state in {"disabled", "static"}
        )


@dataclass(frozen=True)
class ActivationApprovalRecord:
    schema_version: int
    phase: ApprovalPhase
    transaction_id: str
    lock_lease_id: str
    package_fingerprint: str
    commit_manifest_sha256: str | None
    active_route_sha256: str
    direct_route_sha256: str
    camilladsp_config_sha256: str
    camilladsp_binary_version: str
    camilladsp_binary_sha256: str
    loopback_index: int
    loopback_id: str
    loopback_pcm_substreams: int
    loopback_pcm_notify: int
    dac_card: str
    dac_device: int
    sample_rate: int
    sample_format: str
    period_size: int
    buffer_size: int
    created_at: str
    committed_at: str | None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise RuntimeAuthorityError(f"unsupported approval schema: {self.schema_version}")
        _require_token("transaction id", self.transaction_id)
        _require_token("lock lease id", self.lock_lease_id)
        for label, value in (
            ("package fingerprint", self.package_fingerprint),
            ("active route digest", self.active_route_sha256),
            ("direct route digest", self.direct_route_sha256),
            ("CamillaDSP config digest", self.camilladsp_config_sha256),
            ("CamillaDSP binary digest", self.camilladsp_binary_sha256),
        ):
            _require_sha256(label, value)
        _require_token("CamillaDSP version", self.camilladsp_binary_version)
        _require_token("loopback id", self.loopback_id)
        _require_token("DAC card", self.dac_card)
        _require_token("sample format", self.sample_format)
        _require_timestamp("creation timestamp", self.created_at)
        if self.phase is ApprovalPhase.TEMPORARY:
            if self.commit_manifest_sha256 is not None or self.committed_at is not None:
                raise RuntimeAuthorityError("temporary approval must not contain commit fields")
        elif self.phase is ApprovalPhase.COMMITTED:
            if self.commit_manifest_sha256 is None or self.committed_at is None:
                raise RuntimeAuthorityError("committed approval requires commit fields")
            _require_sha256("commit manifest digest", self.commit_manifest_sha256)
            _require_timestamp("commit timestamp", self.committed_at)
        else:  # pragma: no cover - Enum construction prevents this
            raise RuntimeAuthorityError(f"unsupported approval phase: {self.phase}")
        HardwareContract(
            package_fingerprint=self.package_fingerprint,
            split_route_sha256=self.active_route_sha256,
            direct_route_sha256=self.direct_route_sha256,
            camilladsp_config_sha256=self.camilladsp_config_sha256,
            camilladsp_binary_version=self.camilladsp_binary_version,
            camilladsp_binary_sha256=self.camilladsp_binary_sha256,
            loopback_index=self.loopback_index,
            loopback_id=self.loopback_id,
            loopback_pcm_substreams=self.loopback_pcm_substreams,
            loopback_pcm_notify=self.loopback_pcm_notify,
            dac_card=self.dac_card,
            dac_device=self.dac_device,
            sample_rate=self.sample_rate,
            sample_format=self.sample_format,
            period_size=self.period_size,
            buffer_size=self.buffer_size,
        )

    @classmethod
    def temporary(cls, *, transaction_id: str, lock_lease_id: str, contract: HardwareContract, created_at: str) -> "ActivationApprovalRecord":
        return cls(
            schema_version=1,
            phase=ApprovalPhase.TEMPORARY,
            transaction_id=transaction_id,
            lock_lease_id=lock_lease_id,
            package_fingerprint=contract.package_fingerprint,
            commit_manifest_sha256=None,
            active_route_sha256=contract.split_route_sha256,
            direct_route_sha256=contract.direct_route_sha256,
            camilladsp_config_sha256=contract.camilladsp_config_sha256,
            camilladsp_binary_version=contract.camilladsp_binary_version,
            camilladsp_binary_sha256=contract.camilladsp_binary_sha256,
            loopback_index=contract.loopback_index,
            loopback_id=contract.loopback_id,
            loopback_pcm_substreams=contract.loopback_pcm_substreams,
            loopback_pcm_notify=contract.loopback_pcm_notify,
            dac_card=contract.dac_card,
            dac_device=contract.dac_device,
            sample_rate=contract.sample_rate,
            sample_format=contract.sample_format,
            period_size=contract.period_size,
            buffer_size=contract.buffer_size,
            created_at=created_at,
            committed_at=None,
        )

    def promote(self, *, commit_manifest_sha256: str, committed_at: str) -> "ActivationApprovalRecord":
        if self.phase is not ApprovalPhase.TEMPORARY:
            raise RuntimeAuthorityError("only a temporary approval can be promoted")
        _require_sha256("commit manifest digest", commit_manifest_sha256)
        return replace(self, phase=ApprovalPhase.COMMITTED, commit_manifest_sha256=commit_manifest_sha256, committed_at=committed_at)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase": self.phase.value,
            "transaction_id": self.transaction_id,
            "lock_lease_id": self.lock_lease_id,
            "package_fingerprint": self.package_fingerprint,
            "commit_manifest_sha256": self.commit_manifest_sha256,
            "active_route_sha256": self.active_route_sha256,
            "direct_route_sha256": self.direct_route_sha256,
            "camilladsp_config_sha256": self.camilladsp_config_sha256,
            "camilladsp_binary_version": self.camilladsp_binary_version,
            "camilladsp_binary_sha256": self.camilladsp_binary_sha256,
            "loopback_index": self.loopback_index,
            "loopback_id": self.loopback_id,
            "loopback_pcm_substreams": self.loopback_pcm_substreams,
            "loopback_pcm_notify": self.loopback_pcm_notify,
            "dac_card": self.dac_card,
            "dac_device": self.dac_device,
            "sample_rate": self.sample_rate,
            "sample_format": self.sample_format,
            "period_size": self.period_size,
            "buffer_size": self.buffer_size,
            "created_at": self.created_at,
            "committed_at": self.committed_at,
        }

    @property
    def record_sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.as_dict())).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActivationApprovalRecord":
        expected = set(cls.__dataclass_fields__)
        if set(payload) != expected:
            missing = sorted(expected - set(payload))
            extra = sorted(set(payload) - expected)
            raise RuntimeAuthorityError(f"approval fields mismatch: missing={missing} extra={extra}")
        try:
            return cls(
                schema_version=int(payload["schema_version"]),
                phase=ApprovalPhase(str(payload["phase"])),
                transaction_id=str(payload["transaction_id"]),
                lock_lease_id=str(payload["lock_lease_id"]),
                package_fingerprint=str(payload["package_fingerprint"]),
                commit_manifest_sha256=None if payload["commit_manifest_sha256"] is None else str(payload["commit_manifest_sha256"]),
                active_route_sha256=str(payload["active_route_sha256"]),
                direct_route_sha256=str(payload["direct_route_sha256"]),
                camilladsp_config_sha256=str(payload["camilladsp_config_sha256"]),
                camilladsp_binary_version=str(payload["camilladsp_binary_version"]),
                camilladsp_binary_sha256=str(payload["camilladsp_binary_sha256"]),
                loopback_index=int(payload["loopback_index"]),
                loopback_id=str(payload["loopback_id"]),
                loopback_pcm_substreams=int(payload["loopback_pcm_substreams"]),
                loopback_pcm_notify=int(payload["loopback_pcm_notify"]),
                dac_card=str(payload["dac_card"]),
                dac_device=int(payload["dac_device"]),
                sample_rate=int(payload["sample_rate"]),
                sample_format=str(payload["sample_format"]),
                period_size=int(payload["period_size"]),
                buffer_size=int(payload["buffer_size"]),
                created_at=str(payload["created_at"]),
                committed_at=None if payload["committed_at"] is None else str(payload["committed_at"]),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeAuthorityError(f"invalid approval payload: {exc}") from exc


@dataclass(frozen=True)
class InstallHandoffObservation:
    transaction_id: str
    lock_lease_id: str
    production_lock_held: bool
    candidate_validated: bool
    package_fingerprint: str
    active_route_sha256: str
    installed_file_count: int
    managed_units: tuple[UnitObservation, ...]
    dac_released: bool
    loopback_playback_released: bool


@dataclass(frozen=True)
class CommitObservation:
    transaction_id: str
    lock_lease_id: str
    production_lock_held: bool
    install_committed: bool
    split_bus_healthy: bool
    active_route_sha256: str
    commit_manifest_sha256: str


@dataclass(frozen=True)
class BootObservation:
    package_fingerprint: str
    split_route_sha256: str
    direct_route_sha256: str
    camilladsp_config_sha256: str
    camilladsp_binary_version: str
    camilladsp_binary_sha256: str
    loopback_index: int
    loopback_id: str
    loopback_pcm_substreams: int
    loopback_pcm_notify: int
    dac_card: str
    dac_device: int
    sample_rate: int
    sample_format: str
    period_size: int
    buffer_size: int
    managed_files_valid: bool
    split_route_valid: bool
    direct_route_valid: bool
    loopback_valid: bool
    dac_valid: bool
    camilladsp_start_succeeded: bool
    split_bus_health_valid: bool


@dataclass(frozen=True)
class RuntimeDecision:
    mode: RuntimeMode
    reason: str
    actions: tuple[RuntimeAction, ...]

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise RuntimeAuthorityError("runtime decision reason must not be empty")
        if not self.actions:
            raise RuntimeAuthorityError("runtime decision must contain actions")
