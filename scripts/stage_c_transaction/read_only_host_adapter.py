#!/usr/bin/python3
from __future__ import annotations

"""Stage C13 typed read-only real-host observation adapter.

Exactly six host-observation methods are implemented. Every other method is
inherited from BlockedProductionAdapter and remains fail-closed.
"""

import os
import platform
import re
import secrets
import stat
from pathlib import Path
from subprocess import CompletedProcess

from .host_review import (
    APPROVAL_MARKER,
    CURRENT_ALSA,
    EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    _dac_owner_rows,
    run as host_run,
    running_camilladsp_pids,
)
from .package_review import sha256
from .privileged_snapshot_entry import EXPECTED_HW_PARAMS, parse_hw_params
from .production_adapter_contract import (
    AdapterOperation,
    AdapterResult,
    AdapterStatus,
    BlockedProductionAdapter,
    DAC_CONTRACT,
    DacOwner,
    DacSnapshot,
    HostContractSnapshot,
    LOOPBACK_CONTRACT,
    LoopbackSnapshot,
    MixerControl,
    MixerSnapshot,
    PRODUCTION_LOCK_PATH,
    ProductionLockObservation,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceState,
    ServiceUnit,
    TransactionIdentity,
)


OBSERVATION_PREFIX = "stage-c13-observation-"
PERMITTED_OPERATIONS = (
    AdapterOperation.INSPECT_HOST_CONTRACT,
    AdapterOperation.INSPECT_PRODUCTION_LOCK,
    AdapterOperation.CAPTURE_SERVICE_STATE,
    AdapterOperation.CAPTURE_MIXER_STATE,
    AdapterOperation.CAPTURE_LOOPBACK_STATE,
    AdapterOperation.CAPTURE_DAC_STATE,
)

ALSA_CONTROL_MAP = (
    ("A Clockwork Plexamp", "plexamp_output"),
    ("A Clockwork AirPlay", "airplay_output"),
    ("A Clockwork Master", "music_master"),
    ("A Clockwork Alarm", "maximum_alarm_volume"),
)

APPLICATION_SERVICE_UNITS = (
    ServiceUnit.PLEXAMP,
    ServiceUnit.SHAIRPORT_SYNC,
    ServiceUnit.DASHBOARD,
)
STAGE_C_SERVICE_UNITS = (
    ServiceUnit.ROUTE_AUTHORITY,
    ServiceUnit.CAMILLADSP,
    ServiceUnit.AUDIO_FAILBACK,
)

MODULE_PARAMETER_ROOT = Path("/sys/module/snd_aloop/parameters")
DAC_HW_PARAMS = Path("/proc/asound/Pro/pcm0p/sub0/hw_params")
DAC_CARD_ALIAS = Path("/proc/asound/Pro")


class ObservationFailure(RuntimeError):
    """A fixed read-only observation could not be validated."""


def _clean(value: str) -> str:
    return value.strip().replace("\t", " ")


def _pass(operation: AdapterOperation, detail: str, payload):
    return AdapterResult(
        operation=operation,
        status=AdapterStatus.PASS,
        detail=detail,
        payload=payload,
    )


def _fail(operation: AdapterOperation, detail: str):
    return AdapterResult(
        operation=operation,
        status=AdapterStatus.FAIL,
        detail=detail,
    )


def _observe_host_contract() -> HostContractSnapshot:
    if platform.machine() != "aarch64":
        raise ObservationFailure(f"expected aarch64; found {platform.machine()}")
    try:
        info = CURRENT_ALSA.lstat()
    except OSError as exc:
        raise ObservationFailure(f"current ALSA route is unavailable: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ObservationFailure("current ALSA route is not a regular file")
    if stat.S_IMODE(info.st_mode) != 0o644 or info.st_uid != 0 or info.st_gid != 0:
        raise ObservationFailure("current ALSA route owner or mode changed")
    observed_sha = sha256(CURRENT_ALSA)
    if observed_sha != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise ObservationFailure(
            "current ALSA route is not the physically validated pre-Stage-C graph"
        )
    if APPROVAL_MARKER.exists():
        raise ObservationFailure("unexpected Stage C activation marker already exists")
    pids = running_camilladsp_pids()
    if pids:
        raise ObservationFailure(f"unexpected running CamillaDSP process: {pids}")
    return HostContractSnapshot(
        service_units=tuple(ServiceUnit),
        mixer_controls=tuple(MixerControl),
        loopback=LOOPBACK_CONTRACT,
        dac=DAC_CONTRACT,
    )


def _observe_production_lock() -> ProductionLockObservation:
    lock = Path(PRODUCTION_LOCK_PATH)
    parent = lock.parent
    try:
        parent_info = parent.lstat()
    except OSError as exc:
        raise ObservationFailure(f"cannot inspect production lock parent: {exc}") from exc
    if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
        raise ObservationFailure("production lock parent is not a real directory")
    if parent_info.st_uid != 0 or parent_info.st_gid != 0:
        raise ObservationFailure("production lock parent is not root-owned")
    try:
        info = lock.lstat()
    except FileNotFoundError:
        return ProductionLockObservation(
            path=PRODUCTION_LOCK_PATH,
            exists=False,
            held_by_caller=False,
            owner_uid=None,
            owner_gid=None,
            mode=None,
        )
    except OSError as exc:
        raise ObservationFailure(f"cannot inspect production lock: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ObservationFailure("production lock path is not a regular file")
    return ProductionLockObservation(
        path=PRODUCTION_LOCK_PATH,
        exists=True,
        held_by_caller=False,
        owner_uid=info.st_uid,
        owner_gid=info.st_gid,
        mode=stat.S_IMODE(info.st_mode),
    )


def _service_load(value: str) -> ServiceLoadState:
    try:
        return ServiceLoadState(value)
    except ValueError as exc:
        raise ObservationFailure(f"unsupported service load state: {value}") from exc


def _service_active(value: str) -> ServiceActiveState:
    normalised = "inactive" if value in {"unknown", "deactivating"} else value
    try:
        return ServiceActiveState(normalised)
    except ValueError as exc:
        raise ObservationFailure(f"unsupported service active state: {value}") from exc


def _service_enabled(value: str) -> ServiceEnableState:
    try:
        return ServiceEnableState(value)
    except ValueError as exc:
        raise ObservationFailure(f"unsupported service enable state: {value}") from exc


def _observe_service_snapshot() -> ServiceSnapshot:
    states: list[ServiceState] = []
    for unit in ServiceUnit:
        show = host_run(
            ["systemctl", "show", unit.value, "--property=LoadState", "--value"]
        )
        active = host_run(["systemctl", "is-active", unit.value])
        enabled = host_run(["systemctl", "is-enabled", unit.value])
        load_value = _clean(show.stdout) or "not-found"
        active_value = _clean(active.stdout) or "inactive"
        enabled_value = _clean(enabled.stdout) or (
            "not-found" if load_value == "not-found" else "disabled"
        )
        states.append(
            ServiceState(
                unit=unit,
                load=_service_load(load_value),
                active=_service_active(active_value),
                enabled=_service_enabled(enabled_value),
            )
        )
    return ServiceSnapshot(tuple(states))


def _first_percent(result: CompletedProcess[str], control: str) -> int:
    if result.returncode != 0:
        raise ObservationFailure(f"could not read mixer control: {control}")
    match = re.search(r"\[(\d+)%\]", result.stdout)
    if match is None:
        raise ObservationFailure(f"could not parse mixer percentage: {control}")
    return int(match.group(1))


def _observe_mixer_snapshot() -> MixerSnapshot:
    values: dict[str, int] = {}
    for control, field_name in ALSA_CONTROL_MAP:
        result = host_run(["amixer", "-c", "Pro", "sget", control])
        values[field_name] = _first_percent(result, control)
    return MixerSnapshot(**values)


def _first_module_parameter(name: str) -> str:
    path = MODULE_PARAMETER_ROOT / name
    try:
        return path.read_text(encoding="utf-8").strip().split(",", 1)[0]
    except OSError as exc:
        raise ObservationFailure(f"cannot read snd_aloop {name}: {exc}") from exc


def _observe_loopback_snapshot() -> LoopbackSnapshot:
    expected = {
        "index": str(LOOPBACK_CONTRACT.card_index),
        "id": LOOPBACK_CONTRACT.card_id,
        "pcm_substreams": str(LOOPBACK_CONTRACT.pcm_substreams),
        "pcm_notify": str(LOOPBACK_CONTRACT.pcm_notify),
        "enable": "Y",
    }
    observed = {name: _first_module_parameter(name) for name in expected}
    mismatches = {
        name: (expected[name], observed[name])
        for name in expected
        if observed[name] != expected[name]
    }
    if mismatches:
        raise ObservationFailure(f"snd_aloop contract mismatch: {mismatches}")
    return LoopbackSnapshot(contract=LOOPBACK_CONTRACT, loaded=True)


def _physical_dac_device() -> Path:
    try:
        target = os.readlink(DAC_CARD_ALIAS)
    except OSError as exc:
        raise ObservationFailure(f"cannot resolve ALSA card alias Pro: {exc}") from exc
    match = re.fullmatch(r"card(\d+)", Path(target).name)
    if match is None:
        raise ObservationFailure(f"unexpected ALSA card alias target: {target}")
    device = Path(f"/dev/snd/pcmC{match.group(1)}D0p")
    if not device.exists():
        raise ObservationFailure(f"physical DAC playback device is missing: {device}")
    return device


def _parse_dac_owners(device: Path, fuser_stdout: str) -> tuple[DacOwner, ...]:
    rows = _dac_owner_rows(device, fuser_stdout)
    values: dict[str, str] = {}
    for row in rows:
        key, value = row.split("\t", 1)
        values[key] = value
    count = int(values.get("dac.owner_count", "0"))
    owners: list[DacOwner] = []
    for position in range(1, count + 1):
        prefix = f"dac.owner.{position}"
        fds = values.get(f"{prefix}.fds", "unavailable")
        access = ",".join(
            item.split(":", 1)[1] if ":" in item else item
            for item in fds.split(",")
        )
        owners.append(
            DacOwner(
                pid=int(values[f"{prefix}.pid"]),
                user=values[f"{prefix}.user"],
                command=values[f"{prefix}.command"],
                access=access or "unavailable",
            )
        )
    return tuple(owners)


def _observe_dac_snapshot() -> DacSnapshot:
    try:
        raw = DAC_HW_PARAMS.read_text(encoding="utf-8")
    except OSError as exc:
        raise ObservationFailure(f"cannot read physical DAC hw_params: {exc}") from exc
    observed = parse_hw_params(raw)
    mismatches = {
        key: (expected, observed.get(key, "<missing>"))
        for key, expected in EXPECTED_HW_PARAMS.items()
        if observed.get(key) != expected
    }
    if mismatches:
        raise ObservationFailure(f"physical DAC contract mismatch: {mismatches}")
    device = _physical_dac_device()
    fuser = host_run(["fuser", str(device)])
    if fuser.returncode not in (0, 1):
        raise ObservationFailure(
            f"could not inspect DAC owners: {_clean(fuser.stderr) or fuser.returncode}"
        )
    owners = _parse_dac_owners(device, fuser.stdout)
    return DacSnapshot(
        contract=DAC_CONTRACT,
        owners=owners,
        released=not owners,
    )


class ReadOnlyHostProductionAdapter(BlockedProductionAdapter):
    """Six-operation real-host observer; all other operations remain blocked."""

    def __init__(self) -> None:
        self._observation_transaction = TransactionIdentity(
            f"{OBSERVATION_PREFIX}{secrets.token_hex(12)}"
        )

    @property
    def observation_transaction(self) -> TransactionIdentity:
        return self._observation_transaction

    @staticmethod
    def _success(operation: AdapterOperation, payload):
        return _pass(
            operation,
            "fixed read-only host observation completed",
            payload,
        )

    def _require_observation_identity(
        self,
        operation: AdapterOperation,
        transaction: TransactionIdentity,
    ) -> AdapterResult[None] | None:
        if transaction == self._observation_transaction:
            return None
        return _fail(operation, "rejected non-adapter observation identity")

    def inspect_host_contract(self) -> AdapterResult[HostContractSnapshot]:
        operation = AdapterOperation.INSPECT_HOST_CONTRACT
        try:
            payload = _observe_host_contract()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)

    def inspect_production_lock(self) -> AdapterResult[ProductionLockObservation]:
        operation = AdapterOperation.INSPECT_PRODUCTION_LOCK
        try:
            payload = _observe_production_lock()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)

    def capture_service_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[ServiceSnapshot]:
        operation = AdapterOperation.CAPTURE_SERVICE_STATE
        invalid = self._require_observation_identity(operation, transaction)
        if invalid is not None:
            return invalid
        try:
            payload = _observe_service_snapshot()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)

    def capture_mixer_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[MixerSnapshot]:
        operation = AdapterOperation.CAPTURE_MIXER_STATE
        invalid = self._require_observation_identity(operation, transaction)
        if invalid is not None:
            return invalid
        try:
            payload = _observe_mixer_snapshot()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)

    def capture_loopback_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[LoopbackSnapshot]:
        operation = AdapterOperation.CAPTURE_LOOPBACK_STATE
        invalid = self._require_observation_identity(operation, transaction)
        if invalid is not None:
            return invalid
        try:
            payload = _observe_loopback_snapshot()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)

    def capture_dac_state(
        self, transaction: TransactionIdentity
    ) -> AdapterResult[DacSnapshot]:
        operation = AdapterOperation.CAPTURE_DAC_STATE
        invalid = self._require_observation_identity(operation, transaction)
        if invalid is not None:
            return invalid
        try:
            payload = _observe_dac_snapshot()
        except ObservationFailure as exc:
            return _fail(operation, str(exc))
        return self._success(operation, payload)
