#!/usr/bin/python3
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_SCRIPTS = SCRIPT_DIR.parent
if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))

from stage_c_transaction.privileged_snapshot import main

EXPECTED_HW_PARAMS = {
    "access": "MMAP_INTERLEAVED",
    "format": "S16_LE",
    "subformat": "STD",
    "channels": "2",
    "rate": "44100",
    "period_size": "1024",
    "buffer_size": "8192",
}


def first_module_parameter(name: str) -> str:
    path = Path("/sys/module/snd_aloop/parameters") / name
    try:
        return path.read_text(encoding="utf-8").strip().split(",", 1)[0]
    except OSError as exc:
        raise SystemExit(f"Cannot read snd_aloop {name}: {exc}") from exc


def parse_hw_params(text: str) -> dict[str, str]:
    observed: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "rate":
            match = re.match(r"^(\d+)(?:\s|$)", value)
            if match:
                value = match.group(1)
        observed[key] = value
    return observed


def validate_physical_capture_boundary() -> None:
    enable = first_module_parameter("enable")
    if enable != "Y":
        raise SystemExit(f"Unexpected snd_aloop enable state: {enable}")

    device = Path("/dev/snd/pcmC2D0p")
    if not device.exists():
        raise SystemExit(f"Expected physical DAC playback device is missing: {device}")

    hw_params_path = Path("/proc/asound/Pro/pcm0p/sub0/hw_params")
    try:
        raw = hw_params_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Cannot read physical DAC hw_params: {exc}") from exc
    observed = parse_hw_params(raw)
    mismatches = {
        key: (expected, observed.get(key, "<missing>"))
        for key, expected in EXPECTED_HW_PARAMS.items()
        if observed.get(key) != expected
    }
    if mismatches:
        detail = ", ".join(
            f"{key} expected={expected} observed={actual}"
            for key, (expected, actual) in sorted(mismatches.items())
        )
        raise SystemExit(f"Physical DAC hw_params differ from the validated boundary: {detail}")


if __name__ == "__main__":
    validate_physical_capture_boundary()
    raise SystemExit(main())
