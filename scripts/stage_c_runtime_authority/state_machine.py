#!/usr/bin/python3
from __future__ import annotations

from .model import (
    EXPECTED_MANAGED_UNITS,
    ActivationApprovalRecord,
    ApprovalPhase,
    BootObservation,
    CommitObservation,
    HardwareContract,
    InstallHandoffObservation,
    RuntimeAction,
    RuntimeAuthorityError,
    RuntimeDecision,
    RuntimeMode,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeAuthorityError(message)


def accept_install_handoff(
    observation: InstallHandoffObservation,
    contract: HardwareContract,
    *,
    created_at: str,
) -> tuple[ActivationApprovalRecord, RuntimeDecision]:
    _require(observation.production_lock_held, "install hand-off requires the already-held production lock")
    _require(observation.candidate_validated, "install hand-off requires a validated candidate")
    _require(observation.package_fingerprint == contract.package_fingerprint, "package fingerprint mismatch")
    _require(observation.active_route_sha256 == contract.split_route_sha256, "split-bus route is not selected")
    _require(observation.installed_file_count == 12, "install hand-off requires exactly twelve managed files")
    _require(observation.dac_released, "physical DAC must remain released during install hand-off")
    _require(observation.loopback_playback_released, "loopback playback endpoints must remain released during install hand-off")
    names = tuple(unit.name for unit in observation.managed_units)
    _require(names == EXPECTED_MANAGED_UNITS, "managed unit set or order mismatch")
    _require(all(unit.is_loaded_inactive for unit in observation.managed_units), "managed units must be loaded and inactive")
    record = ActivationApprovalRecord.temporary(
        transaction_id=observation.transaction_id,
        lock_lease_id=observation.lock_lease_id,
        contract=contract,
        created_at=created_at,
    )
    return record, RuntimeDecision(
        mode=RuntimeMode.OFFLINE,
        reason="transaction-selected split-bus route accepted; managed services remain stopped",
        actions=(RuntimeAction.ACCEPT_INSTALL_HANDOFF, RuntimeAction.PUBLISH_TEMPORARY_APPROVAL),
    )


def promote_committed_approval(
    temporary: ActivationApprovalRecord,
    observation: CommitObservation,
    *,
    committed_at: str,
) -> tuple[ActivationApprovalRecord, RuntimeDecision]:
    _require(temporary.phase is ApprovalPhase.TEMPORARY, "approval is not temporary")
    _require(observation.production_lock_held, "approval promotion requires the held production lock")
    _require(observation.install_committed, "install transaction has not committed")
    _require(observation.split_bus_healthy, "split-bus health has not passed")
    _require(observation.transaction_id == temporary.transaction_id, "commit transaction identity mismatch")
    _require(observation.lock_lease_id == temporary.lock_lease_id, "commit lock lease identity mismatch")
    _require(observation.active_route_sha256 == temporary.active_route_sha256, "committed route digest mismatch")
    committed = temporary.promote(
        commit_manifest_sha256=observation.commit_manifest_sha256,
        committed_at=committed_at,
    )
    return committed, RuntimeDecision(
        mode=RuntimeMode.SPLIT_BUS_ACTIVE,
        reason="healthy split-bus installation committed and made boot-eligible",
        actions=(RuntimeAction.PROMOTE_COMMITTED_APPROVAL,),
    )


def _direct_contract_matches(record: ActivationApprovalRecord, observation: BootObservation) -> bool:
    comparisons = (
        (record.package_fingerprint, observation.package_fingerprint),
        (record.direct_route_sha256, observation.direct_route_sha256),
        (record.dac_card, observation.dac_card),
        (record.dac_device, observation.dac_device),
        (record.sample_rate, observation.sample_rate),
        (record.sample_format, observation.sample_format),
        (record.period_size, observation.period_size),
        (record.buffer_size, observation.buffer_size),
    )
    return all(expected == observed for expected, observed in comparisons)


def _split_contract_matches(record: ActivationApprovalRecord, observation: BootObservation) -> bool:
    comparisons = (
        (record.active_route_sha256, observation.split_route_sha256),
        (record.camilladsp_config_sha256, observation.camilladsp_config_sha256),
        (record.camilladsp_binary_version, observation.camilladsp_binary_version),
        (record.camilladsp_binary_sha256, observation.camilladsp_binary_sha256),
        (record.loopback_index, observation.loopback_index),
        (record.loopback_id, observation.loopback_id),
        (record.loopback_pcm_substreams, observation.loopback_pcm_substreams),
        (record.loopback_pcm_notify, observation.loopback_pcm_notify),
    )
    return _direct_contract_matches(record, observation) and all(
        expected == observed for expected, observed in comparisons
    )


def decide_boot(record: ActivationApprovalRecord, observation: BootObservation) -> RuntimeDecision:
    _require(record.phase is ApprovalPhase.COMMITTED, "ordinary boot requires a committed approval")
    _require(
        _direct_contract_matches(record, observation),
        "committed approval does not match the direct-failback runtime contract",
    )
    _require(observation.managed_files_valid, "managed files do not match the committed manifest")
    _require(observation.direct_route_valid, "direct alarm-bypass failback route is invalid")
    _require(observation.dac_valid, "physical DAC contract is invalid")

    prefix = (RuntimeAction.ACQUIRE_PRODUCTION_LOCK, RuntimeAction.VALIDATE_COMMITTED_STATE)
    suffix = (RuntimeAction.RELEASE_PRODUCTION_LOCK,)
    split_preflight = (
        _split_contract_matches(record, observation)
        and observation.split_route_valid
        and observation.loopback_valid
    )
    split_runtime = observation.camilladsp_start_succeeded and observation.split_bus_health_valid
    if split_preflight and split_runtime:
        return RuntimeDecision(
            mode=RuntimeMode.SPLIT_BUS_ACTIVE,
            reason="committed split-bus route and CamillaDSP passed strict boot health",
            actions=prefix + (
                RuntimeAction.SELECT_SPLIT_BUS_ROUTE,
                RuntimeAction.START_CAMILLADSP,
                RuntimeAction.VERIFY_SPLIT_BUS_HEALTH,
                RuntimeAction.PUBLISH_SPLIT_BUS_ACTIVE,
            ) + suffix,
        )

    reason = "split-bus candidate or loopback validation failed" if not split_preflight else "CamillaDSP startup or strict split-bus health failed"
    return RuntimeDecision(
        mode=RuntimeMode.DIRECT_FAILBACK,
        reason=reason,
        actions=prefix + (
            RuntimeAction.STOP_CAMILLADSP,
            RuntimeAction.SELECT_DIRECT_FAILBACK_ROUTE,
            RuntimeAction.PUBLISH_DIRECT_FAILBACK,
        ) + suffix,
    )


def fixed_runtime_action_vocabulary() -> tuple[str, ...]:
    """Return the immutable action values without accepting caller-supplied dispatch."""
    return tuple(action.value for action in RuntimeAction)
