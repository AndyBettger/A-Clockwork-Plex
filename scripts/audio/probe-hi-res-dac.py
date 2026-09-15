#!/usr/bin/env python3
"""Guarded Raspberry Pi DAC Pro capability probe for hi-res development.

The probe deliberately quiesces the ACP applications and CamillaDSP so the
physical DAC can be opened exclusively, queries ALSA hardware-parameter
constraints, closes the PCM without starting a stream, then restores the exact
services that were active beforehand and re-runs the managed audio verifier.

No ALSA route, EQ setting, mixer value or appliance configuration is changed.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[2]
VERIFY: Final = ROOT / "scripts" / "audio" / "verify-audio.sh"
ROUTE_HELPER: Final = Path("/usr/local/bin/a-clockwork-plex-audio-route")
DAC_PCM: Final = "hw:CARD=Pro,DEV=0"
DAC_HW_PARAMS: Final = Path("/proc/asound/Pro/pcm0p/sub0/hw_params")
CAMILLADSP_SERVICE: Final = "a-clockwork-plex-camilladsp.service"
APP_STOP_ORDER: Final = (
    "a-clockwork-plex.service",
    "shairport-sync.service",
    "plexamp.service",
)
APP_START_ORDER: Final = (
    "plexamp.service",
    "shairport-sync.service",
    "a-clockwork-plex.service",
)
FORMATS: Final = ("S16_LE", "S24_LE", "S24_3LE", "S32_LE")
RATES: Final = (44100, 48000, 88200, 96000, 176400, 192000)

SND_PCM_STREAM_PLAYBACK: Final = 0
SND_PCM_NONBLOCK: Final = 0x00000001
SND_PCM_ACCESS_RW_INTERLEAVED: Final = 3


class ProbeError(RuntimeError):
    """Expected probe or restoration failure."""


def run(
    command: list[str],
    *,
    check: bool = False,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=capture,
    )


def sudo(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run(["sudo", *command], check=False, capture=True)
    if check and result.returncode != 0:
        detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise ProbeError(detail or f"sudo command failed: {' '.join(command)}")
    return result


def service_active(unit: str) -> bool:
    return run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


def service_main_pid(unit: str) -> int:
    result = run(["systemctl", "show", unit, "--property=MainPID", "--value"])
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def systemctl(action: str, unit: str) -> None:
    result = sudo(["systemctl", action, unit], check=False)
    if result.returncode != 0:
        detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise ProbeError(detail or f"systemctl {action} failed for {unit}")


def wait_dac_closed(timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            state = DAC_HW_PARAMS.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ProbeError(f"cannot read DAC hardware state: {DAC_HW_PARAMS}: {exc}") from exc
        if state == "closed":
            return
        time.sleep(0.1)
    raise ProbeError(f"physical DAC did not become idle: {DAC_HW_PARAMS}")


def wait_camilla(timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service_active(CAMILLADSP_SERVICE) and service_main_pid(CAMILLADSP_SERVICE) > 0:
            return
        time.sleep(0.1)
    raise ProbeError("CamillaDSP did not return to an active process state")


def verify_audio(label: str) -> None:
    result = run(["bash", str(VERIFY)], capture=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise ProbeError(f"managed audio verification failed {label}")


def route_status() -> dict[str, object]:
    result = run([str(ROUTE_HELPER), "status"])
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ProbeError(detail or "could not read managed route status")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("managed route status was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ProbeError("managed route status was not an object")
    return payload


def alsa_error(lib: ctypes.CDLL, code: int) -> str:
    raw = lib.snd_strerror(code)
    if not raw:
        return f"ALSA error {code}"
    return raw.decode("utf-8", errors="replace")


def query_capabilities() -> dict[str, dict[int, bool]]:
    library = ctypes.util.find_library("asound") or "libasound.so.2"
    try:
        lib = ctypes.CDLL(library)
    except OSError as exc:
        raise ProbeError(f"could not load ALSA library {library}: {exc}") from exc

    lib.snd_strerror.argtypes = [ctypes.c_int]
    lib.snd_strerror.restype = ctypes.c_char_p
    lib.snd_pcm_open.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.snd_pcm_open.restype = ctypes.c_int
    lib.snd_pcm_close.argtypes = [ctypes.c_void_p]
    lib.snd_pcm_close.restype = ctypes.c_int
    lib.snd_pcm_hw_params_malloc.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.snd_pcm_hw_params_malloc.restype = ctypes.c_int
    lib.snd_pcm_hw_params_free.argtypes = [ctypes.c_void_p]
    lib.snd_pcm_hw_params_free.restype = None
    lib.snd_pcm_hw_params_any.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.snd_pcm_hw_params_any.restype = ctypes.c_int
    lib.snd_pcm_hw_params_set_access.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
    lib.snd_pcm_hw_params_set_access.restype = ctypes.c_int
    lib.snd_pcm_hw_params_set_channels.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    lib.snd_pcm_hw_params_set_channels.restype = ctypes.c_int
    lib.snd_pcm_format_value.argtypes = [ctypes.c_char_p]
    lib.snd_pcm_format_value.restype = ctypes.c_int
    lib.snd_pcm_hw_params_set_format.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
    lib.snd_pcm_hw_params_set_format.restype = ctypes.c_int
    lib.snd_pcm_hw_params_test_rate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_int,
    ]
    lib.snd_pcm_hw_params_test_rate.restype = ctypes.c_int

    pcm = ctypes.c_void_p()
    rc = lib.snd_pcm_open(
        ctypes.byref(pcm),
        DAC_PCM.encode("ascii"),
        SND_PCM_STREAM_PLAYBACK,
        SND_PCM_NONBLOCK,
    )
    if rc < 0:
        raise ProbeError(f"could not open idle DAC {DAC_PCM}: {alsa_error(lib, rc)}")

    matrix: dict[str, dict[int, bool]] = {}
    try:
        for format_name in FORMATS:
            format_value = lib.snd_pcm_format_value(format_name.encode("ascii"))
            if format_value < 0:
                raise ProbeError(f"ALSA does not recognise format name {format_name}")
            row: dict[int, bool] = {}
            for rate in RATES:
                params = ctypes.c_void_p()
                rc = lib.snd_pcm_hw_params_malloc(ctypes.byref(params))
                if rc < 0:
                    raise ProbeError(f"could not allocate ALSA hw_params: {alsa_error(lib, rc)}")
                try:
                    rc = lib.snd_pcm_hw_params_any(pcm, params)
                    if rc < 0:
                        raise ProbeError(f"could not initialise ALSA hw_params: {alsa_error(lib, rc)}")
                    rc = lib.snd_pcm_hw_params_set_access(
                        pcm, params, SND_PCM_ACCESS_RW_INTERLEAVED
                    )
                    if rc < 0:
                        row[rate] = False
                        continue
                    rc = lib.snd_pcm_hw_params_set_channels(pcm, params, 2)
                    if rc < 0:
                        row[rate] = False
                        continue
                    rc = lib.snd_pcm_hw_params_set_format(pcm, params, format_value)
                    if rc < 0:
                        row[rate] = False
                        continue
                    rc = lib.snd_pcm_hw_params_test_rate(pcm, params, rate, 0)
                    row[rate] = rc == 0
                finally:
                    lib.snd_pcm_hw_params_free(params)
            matrix[format_name] = row
    finally:
        lib.snd_pcm_close(pcm)

    return matrix


def print_matrix(matrix: dict[str, dict[int, bool]]) -> None:
    print("\n===== physical DAC exact format/rate capability matrix =====")
    header = "format".ljust(10) + "".join(f"{rate:>9}" for rate in RATES)
    print(header)
    print("-" * len(header))
    for format_name in FORMATS:
        row = format_name.ljust(10)
        row += "".join(f"{'YES' if matrix[format_name][rate] else '-':>9}" for rate in RATES)
        print(row)
    print("\nYES means ALSA accepted that exact stereo RW_INTERLEAVED format/rate constraint.")
    print("The probe never applies snd_pcm_hw_params and never starts a playback stream.")


def recover_direct(reason: str) -> None:
    print(f"[A Clockwork Plex] WARNING: {reason}; selecting managed Direct failback.", file=sys.stderr)
    result = sudo([str(ROUTE_HELPER), "activate-direct-failback"], check=False)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode != 0:
        detail = result.stderr.strip() or "Direct failback command failed"
        raise ProbeError(detail)


def execute_probe() -> int:
    if os.geteuid() == 0:
        raise ProbeError("run this probe as the normal project user, not as root")
    if not VERIFY.is_file():
        raise ProbeError(f"missing verifier: {VERIFY}")
    if not ROUTE_HELPER.is_file():
        raise ProbeError(f"missing installed route helper: {ROUTE_HELPER}")

    sudo(["-v"])
    verify_audio("before capability probe")
    before = route_status()
    if before.get("mode") != "split-bus-active" or not before.get("active_matches_split"):
        raise ProbeError("capability probe requires the healthy managed split-bus baseline")

    snapshot = {
        CAMILLADSP_SERVICE: service_active(CAMILLADSP_SERVICE),
        **{unit: service_active(unit) for unit in APP_STOP_ORDER},
    }
    print("\n===== service snapshot =====")
    for unit, active in snapshot.items():
        print(f"{unit}: {'active' if active else 'inactive'}")

    probe_error: BaseException | None = None
    restoration_error: BaseException | None = None
    matrix: dict[str, dict[int, bool]] | None = None
    restored_to_split = False
    direct_recovery_used = False

    try:
        print("\n===== quiescing managed audio =====")
        for unit in APP_STOP_ORDER:
            if snapshot[unit]:
                print(f"stopping {unit}")
                systemctl("stop", unit)
        if snapshot[CAMILLADSP_SERVICE]:
            print(f"stopping {CAMILLADSP_SERVICE}")
            systemctl("stop", CAMILLADSP_SERVICE)
        wait_dac_closed()
        print("physical DAC is idle")
        matrix = query_capabilities()
        print_matrix(matrix)
    except BaseException as exc:  # restoration must also run for Ctrl+C
        probe_error = exc
    finally:
        print("\n===== restoring managed audio =====")
        try:
            if snapshot[CAMILLADSP_SERVICE]:
                print(f"starting {CAMILLADSP_SERVICE}")
                systemctl("start", CAMILLADSP_SERVICE)
                try:
                    wait_camilla()
                    restored_to_split = True
                except ProbeError as exc:
                    recover_direct(str(exc))
                    direct_recovery_used = True
            for unit in APP_START_ORDER:
                if snapshot[unit]:
                    print(f"starting {unit}")
                    systemctl("start", unit)
            if restored_to_split:
                verify_audio("after capability probe")
            after = route_status()
            print(
                "final_route="
                f"{after.get('mode')} selected={after.get('selected_mode')} "
                f"split={after.get('active_matches_split')} direct={after.get('active_matches_direct_failback')}"
            )
            if direct_recovery_used:
                raise ProbeError(
                    "CamillaDSP did not restore to the original split bus; managed Direct failback is active"
                )
            if after.get("mode") != "split-bus-active" or not after.get("active_matches_split"):
                raise ProbeError("final route does not match the original managed split-bus state")
        except BaseException as exc:
            restoration_error = exc

    if restoration_error is not None:
        raise ProbeError(f"audio restoration was incomplete: {restoration_error}") from restoration_error
    if probe_error is not None:
        if isinstance(probe_error, KeyboardInterrupt):
            raise ProbeError("capability probe interrupted after restoration") from probe_error
        raise ProbeError(f"capability probe failed after restoration: {probe_error}") from probe_error
    if matrix is None:
        raise ProbeError("capability probe produced no matrix")

    print("\nDAC_CAPABILITY_PROBE=PASS")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Temporarily quiesce ACP audio, query the physical DAC's exact ALSA "
            "format/rate constraints without starting playback, then restore audio."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the guarded stop/query/restore transaction",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.apply:
        print("DAC capability probe plan (no changes made):")
        print("  1. verify the current managed split-bus audio contract")
        print("  2. snapshot active dashboard/AirPlay/Plexamp/CamillaDSP services")
        print("  3. stop dashboard -> AirPlay -> Plexamp -> CamillaDSP")
        print("  4. wait for the physical DAC to report closed")
        print("  5. open the DAC non-blocking and query stereo RW_INTERLEAVED constraints")
        print("  6. test S16_LE/S24_LE/S24_3LE/S32_LE at 44.1–192 kHz")
        print("  7. close the PCM without applying hw_params or starting playback")
        print("  8. restore CamillaDSP -> Plexamp -> AirPlay -> dashboard and re-verify")
        print("Run again with --apply when ready. Audio will be interrupted briefly.")
        return 0
    try:
        return execute_probe()
    except (ProbeError, OSError) as exc:
        print(f"[A Clockwork Plex] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
