#!/usr/bin/python3
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import ActivationApprovalRecord, ApprovalPhase, BootObservation, RuntimeAuthorityError


class PreparedRoute(str, Enum):
    SPLIT_PENDING = "split-bus-pending-health"
    DIRECT_READY = "direct-failback-ready"


class SupervisorMode(str, Enum):
    SPLIT_ACTIVE = "split-bus-active"
    DIRECT_FAILBACK = "direct-failback"


class SupervisorAction(str, Enum):
    ACQUIRE_PRODUCTION_LOCK = "acquire-production-lock"
    VALIDATE_COMMITTED_STATE = "validate-committed-stage-c-state"
    SELECT_SPLIT_BUS_ROUTE = "select-split-bus-route"
    PUBLISH_SPLIT_PENDING = "publish-split-bus-pending-health"
    START_CAMILLADSP_CHILD = "start-camilladsp-child"
    VERIFY_SPLIT_BUS_HEALTH = "verify-split-bus-health"
    PUBLISH_SPLIT_ACTIVE = "publish-split-bus-active"
    STOP_CAMILLADSP_CHILD = "stop-camilladsp-child"
    SELECT_DIRECT_FAILBACK_ROUTE = "select-direct-failback-route"
    PUBLISH_DIRECT_FAILBACK = "publish-direct-failback"
    NOTIFY_SYSTEMD_READY = "notify-systemd-ready"
    RELEASE_PRODUCTION_LOCK = "release-production-lock"
    REMAIN_RUNTIME_SUPERVISOR = "remain-runtime-supervisor"


@dataclass(frozen=True)
class BootPreparationDecision:
    prepared_route: PreparedRoute
    reason: str
    actions: tuple[SupervisorAction, ...]

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.actions:
            raise RuntimeAuthorityError("boot preparation decision is incomplete")


@dataclass(frozen=True)
class SupervisorStartupObservation:
    prepared_route: PreparedRoute
    production_lock_held: bool
    camilladsp_child_started: bool
    split_bus_health_valid: bool


@dataclass(frozen=True)
class SupervisorDecision:
    mode: SupervisorMode
    reason: str
    systemd_ready: bool
    actions: tuple[SupervisorAction, ...]

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.actions:
            raise RuntimeAuthorityError("supervisor decision is incomplete")
        if not self.systemd_ready:
            raise RuntimeAuthorityError("accepted supervisor decisions must release the application-service gate")
        if self.actions[-2:] != (
            SupervisorAction.NOTIFY_SYSTEMD_READY,
            SupervisorAction.REMAIN_RUNTIME_SUPERVISOR,
        ):
            raise RuntimeAuthorityError("supervisor must notify readiness before entering its runtime loop")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeAuthorityError(message)


def _direct_contract_matches(record: ActivationApprovalRecord, observation: BootObservation) -> bool:
    return all(
        expected == observed
        for expected, observed in (
            (record.package_fingerprint, observation.package_fingerprint),
            (record.direct_route_sha256, observation.direct_route_sha256),
            (record.dac_card, observation.dac_card),
            (record.dac_device, observation.dac_device),
            (record.sample_rate, observation.sample_rate),
            (record.sample_format, observation.sample_format),
            (record.period_size, observation.period_size),
            (record.buffer_size, observation.buffer_size),
        )
    )


def _split_contract_matches(record: ActivationApprovalRecord, observation: BootObservation) -> bool:
    return _direct_contract_matches(record, observation) and all(
        expected == observed
        for expected, observed in (
            (record.active_route_sha256, observation.split_route_sha256),
            (record.camilladsp_config_sha256, observation.camilladsp_config_sha256),
            (record.camilladsp_binary_version, observation.camilladsp_binary_version),
            (record.camilladsp_binary_sha256, observation.camilladsp_binary_sha256),
            (record.loopback_index, observation.loopback_index),
            (record.loopback_id, observation.loopback_id),
            (record.loopback_pcm_substreams, observation.loopback_pcm_substreams),
            (record.loopback_pcm_notify, observation.loopback_pcm_notify),
        )
    )


def prepare_boot(record: ActivationApprovalRecord, observation: BootObservation) -> BootPreparationDecision:
    _require(record.phase is ApprovalPhase.COMMITTED, "ordinary boot requires a committed approval")
    _require(_direct_contract_matches(record, observation), "committed direct-failback contract mismatch")
    _require(observation.managed_files_valid, "managed files do not match the committed manifest")
    _require(observation.direct_route_valid, "direct alarm-bypass route is invalid")
    _require(observation.dac_valid, "physical DAC contract is invalid")

    prefix = (
        SupervisorAction.ACQUIRE_PRODUCTION_LOCK,
        SupervisorAction.VALIDATE_COMMITTED_STATE,
    )
    suffix = (SupervisorAction.RELEASE_PRODUCTION_LOCK,)
    split_preflight = (
        _split_contract_matches(record, observation)
        and observation.split_route_valid
        and observation.loopback_valid
    )
    if split_preflight:
        return BootPreparationDecision(
            prepared_route=PreparedRoute.SPLIT_PENDING,
            reason="committed split-bus candidate passed preflight and awaits supervised runtime health",
            actions=prefix
            + (
                SupervisorAction.SELECT_SPLIT_BUS_ROUTE,
                SupervisorAction.PUBLISH_SPLIT_PENDING,
            )
            + suffix,
        )
    return BootPreparationDecision(
        prepared_route=PreparedRoute.DIRECT_READY,
        reason="split-bus preflight failed; alarm-safe direct route prepared before applications",
        actions=prefix
        + (
            SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE,
            SupervisorAction.PUBLISH_DIRECT_FAILBACK,
        )
        + suffix,
    )


def start_supervisor(observation: SupervisorStartupObservation) -> SupervisorDecision:
    _require(observation.production_lock_held, "supervisor startup requires the production lock")
    common_tail = (
        SupervisorAction.RELEASE_PRODUCTION_LOCK,
        SupervisorAction.NOTIFY_SYSTEMD_READY,
        SupervisorAction.REMAIN_RUNTIME_SUPERVISOR,
    )
    if observation.prepared_route is PreparedRoute.DIRECT_READY:
        return SupervisorDecision(
            mode=SupervisorMode.DIRECT_FAILBACK,
            reason="direct alarm-safe route was already prepared",
            systemd_ready=True,
            actions=(SupervisorAction.VALIDATE_COMMITTED_STATE,) + common_tail,
        )
    if observation.camilladsp_child_started and observation.split_bus_health_valid:
        return SupervisorDecision(
            mode=SupervisorMode.SPLIT_ACTIVE,
            reason="CamillaDSP child and strict split-bus health passed",
            systemd_ready=True,
            actions=(
                SupervisorAction.VALIDATE_COMMITTED_STATE,
                SupervisorAction.START_CAMILLADSP_CHILD,
                SupervisorAction.VERIFY_SPLIT_BUS_HEALTH,
                SupervisorAction.PUBLISH_SPLIT_ACTIVE,
            )
            + common_tail,
        )
    return SupervisorDecision(
        mode=SupervisorMode.DIRECT_FAILBACK,
        reason="CamillaDSP startup or split-bus health failed; direct route completed before readiness",
        systemd_ready=True,
        actions=(
            SupervisorAction.VALIDATE_COMMITTED_STATE,
            SupervisorAction.START_CAMILLADSP_CHILD,
            SupervisorAction.VERIFY_SPLIT_BUS_HEALTH,
            SupervisorAction.STOP_CAMILLADSP_CHILD,
            SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE,
            SupervisorAction.PUBLISH_DIRECT_FAILBACK,
        )
        + common_tail,
    )


def child_failure_failback(*, production_lock_held: bool) -> SupervisorDecision:
    _require(production_lock_held, "runtime child-failure handling requires the production lock")
    return SupervisorDecision(
        mode=SupervisorMode.DIRECT_FAILBACK,
        reason="CamillaDSP child exited after readiness; supervisor completed direct failback",
        systemd_ready=True,
        actions=(
            SupervisorAction.STOP_CAMILLADSP_CHILD,
            SupervisorAction.SELECT_DIRECT_FAILBACK_ROUTE,
            SupervisorAction.PUBLISH_DIRECT_FAILBACK,
            SupervisorAction.RELEASE_PRODUCTION_LOCK,
            SupervisorAction.NOTIFY_SYSTEMD_READY,
            SupervisorAction.REMAIN_RUNTIME_SUPERVISOR,
        ),
    )
