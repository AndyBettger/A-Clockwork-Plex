#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Final

DEFAULTS: Final = Path("/etc/default/a-clockwork-plex-split-bus")
CAMILLA_CONFIG: Final = Path("/etc/a-clockwork-plex/camilladsp-split-bus.yml")
SHAIRPORT_CONFIG: Final = Path("/etc/shairport-sync.conf")
REHEARSAL_STATE: Final = Path("/var/lib/a-clockwork-plex/hi-res-rehearsal/state.json")

HW_PARAMS: Final = (
    ("ACP dmix / loopback playback", Path("/proc/asound/card7/pcm0p/sub0/hw_params")),
    ("CamillaDSP loopback capture", Path("/proc/asound/card7/pcm1c/sub0/hw_params")),
    ("Physical DAC playback", Path("/proc/asound/Pro/pcm0p/sub0/hw_params")),
)

SAFE_SHAIRPORT_KEYS: Final = (
    "output_backend",
    "output_device",
    "output_rate",
    "output_format",
    "audio_backend_latency_offset_in_seconds",
    "audio_backend_buffer_desired_length_in_seconds",
    "drift_tolerance_in_seconds",
    "resync_threshold_in_seconds",
    "disable_synchronization",
    "use_precision_timing",
    "stuffing",
)

JOURNAL_PATTERN: Final = re.compile(
    r"underrun|overrun|xrun|buffer|sync|resync|drift|stuff|late|missing|packet|"
    r"alsa|rate|capture|playback|resampl|error|warn|fail|stall|flush",
    re.IGNORECASE,
)
IPV4_PATTERN: Final = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
MAC_PATTERN: Final = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def yaml_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", text)
    return match.group(1).strip().strip('"').strip("'") if match else None


def as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def milliseconds(frames: int | None, rate: int | None) -> float | None:
    if frames is None or rate is None or rate <= 0:
        return None
    return frames * 1000.0 / rate


def show_duration(label: str, frames: int | None, rate: int | None) -> None:
    duration = milliseconds(frames, rate)
    if frames is None or duration is None:
        print(f"{label}=unknown")
        return
    print(f"{label}_frames={frames}")
    print(f"{label}_ms={duration:.3f}")


def read_camilla() -> tuple[str, dict[str, str | None]]:
    try:
        text = CAMILLA_CONFIG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", {}
    keys = (
        "samplerate",
        "capture_samplerate",
        "chunksize",
        "queuelimit",
        "target_level",
        "adjust_period",
        "enable_rate_adjust",
        "resampler",
    )
    return text, {key: yaml_scalar(text, key) for key in keys}


def show_timing_geometry() -> None:
    defaults = read_key_values(DEFAULTS)
    _camilla_text, camilla = read_camilla()

    rate = as_int(camilla.get("samplerate")) or as_int(defaults.get("SAMPLE_RATE"))
    period = as_int(defaults.get("PERIOD_SIZE"))
    buffer_size = as_int(defaults.get("BUFFER_SIZE"))
    chunk = as_int(camilla.get("chunksize")) or as_int(defaults.get("CHUNKSIZE"))
    queue_limit = as_int(camilla.get("queuelimit"))
    if queue_limit is None:
        queue_limit = 4
    target = as_int(camilla.get("target_level")) or as_int(defaults.get("TARGET_LEVEL"))

    print(f"processing_rate={rate if rate is not None else 'unknown'}")
    print(f"format={defaults.get('FORMAT', 'unknown')}")
    show_duration("alsa_period", period, rate)
    show_duration("alsa_buffer", buffer_size, rate)
    show_duration("camilla_chunk", chunk, rate)
    show_duration("camilla_target_level", target, rate)

    if chunk is not None and rate is not None:
        per_queue = chunk * queue_limit
        combined = 2 * per_queue
        print(f"camilla_queuelimit={queue_limit}")
        show_duration("camilla_one_queue_limit", per_queue, rate)
        show_duration("camilla_two_queue_total_limit", combined, rate)

    if rate and rate != 44100:
        print("--- same frame counts at accepted 44100 Hz baseline ---")
        show_duration("baseline_alsa_period", period, 44100)
        show_duration("baseline_alsa_buffer", buffer_size, 44100)
        show_duration("baseline_camilla_chunk", chunk, 44100)
        show_duration("baseline_camilla_target_level", target, 44100)


def show_rehearsal_state() -> None:
    try:
        payload = json.loads(REHEARSAL_STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("candidate_state=none")
        return
    except (OSError, json.JSONDecodeError) as exc:
        print(f"candidate_state=unreadable ({exc})")
        return
    print(f"candidate_format={payload.get('candidate_format', 'unknown')}")
    print(f"candidate_rate={payload.get('candidate_rate', 'unknown')}")
    print(f"durable_backups={payload.get('durable_backups', False)}")


def show_file(label: str, path: Path) -> None:
    print(f"\n===== {label} =====")
    try:
        print(path.read_text(encoding="utf-8", errors="replace").strip())
    except OSError as exc:
        print(f"unavailable: {path} ({exc})")


def show_shairport_config() -> None:
    print("\n===== Shairport timing/output configuration clues =====")
    try:
        text = SHAIRPORT_CONFIG.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"unavailable: {SHAIRPORT_CONFIG} ({exc})")
        return

    found = False
    for key in SAFE_SHAIRPORT_KEYS:
        match = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*([^;\n]+)\s*;",
            text,
        )
        if match:
            print(f"{key}={match.group(1).strip()}")
            found = True
    if not found:
        print("no selected timing/output keys found")


def redact(line: str) -> str:
    line = IPV4_PATTERN.sub("<ip>", line)
    return MAC_PATTERN.sub("<mac>", line)


def show_journal(unit: str, minutes: int) -> None:
    print(f"\n===== {unit} relevant journal ({minutes} min) =====")
    if not shutil_which("journalctl"):
        print("journalctl unavailable")
        return
    result = run(
        [
            "journalctl",
            "-u",
            unit,
            "--since",
            f"{minutes} minutes ago",
            "--no-pager",
            "-n",
            "500",
            "-o",
            "short-iso",
        ]
    )
    if result.returncode and not result.stdout.strip():
        detail = result.stderr.strip() or f"journalctl exit {result.returncode}"
        print(f"unavailable: {detail}")
        return
    matches = [redact(line) for line in result.stdout.splitlines() if JOURNAL_PATTERN.search(line)]
    if not matches:
        print("no matching timing/buffer/error lines")
        return
    for line in matches[-120:]:
        print(line)


def shutil_which(command: str) -> str | None:
    # Local tiny equivalent avoids adding another import merely for one lookup.
    result = run(["/usr/bin/env", "sh", "-c", f"command -v {command}"])
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def show_service(unit: str) -> None:
    result = run(["systemctl", "is-active", unit])
    state = result.stdout.strip() or result.stderr.strip() or "unknown"
    print(f"{unit}={state}")


def show_versions() -> None:
    print("\n===== versions and service state =====")
    if shutil_which("shairport-sync"):
        result = run(["shairport-sync", "-V"])
        print(f"shairport_sync_version={(result.stdout or result.stderr).strip() or 'unknown'}")
    else:
        print("shairport_sync_version=unavailable")
    show_service("shairport-sync.service")
    show_service("a-clockwork-plex-camilladsp.service")
    result = run(["ps", "-C", "camilladsp", "-o", "pid=,pcpu=,pmem=,etimes=,args="])
    print("camilladsp_process=" + ((result.stdout or result.stderr).strip() or "unavailable"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only AirPlay/high-resolution timing snapshot. Run while the guarded "
            "192 kHz rehearsal is active and AirPlay is audibly misbehaving."
        )
    )
    parser.add_argument(
        "--journal-minutes",
        type=int,
        default=10,
        choices=range(1, 61),
        metavar="1-60",
        help="journal window to inspect (default: 10 minutes)",
    )
    parser.add_argument(
        "--no-journal",
        action="store_true",
        help="skip journal inspection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("A Clockwork Plex — read-only AirPlay hi-res timing snapshot")
    print("No PCM is opened and no service, route, mixer or configuration is changed.")

    print("\n===== rehearsal state =====")
    show_rehearsal_state()

    print("\n===== configured timing geometry =====")
    show_timing_geometry()

    for label, path in HW_PARAMS:
        show_file(label, path)

    show_shairport_config()

    _text, camilla = read_camilla()
    print("\n===== CamillaDSP rate-adjust configuration =====")
    if camilla:
        for key, value in camilla.items():
            print(f"{key}={value if value is not None else 'unset'}")
    else:
        print(f"unavailable: {CAMILLA_CONFIG}")

    show_versions()

    if not args.no_journal:
        show_journal("shairport-sync.service", args.journal_minutes)
        show_journal("a-clockwork-plex-camilladsp.service", args.journal_minutes)

    print("\n===== snapshot result =====")
    print("READ_ONLY_AIRPLAY_HI_RES_SNAPSHOT_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
