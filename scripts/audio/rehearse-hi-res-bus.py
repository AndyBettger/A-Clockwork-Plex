#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

sys.dont_write_bytecode = True

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
PROFILE_ROOT: Final = REPO_ROOT / "installer" / "profiles" / "eq-split-bus"
PROFILE_ROUTE: Final = PROFILE_ROOT / "split-bus.conf"
PROFILE_DEFAULTS: Final = PROFILE_ROOT / "a-clockwork-plex-split-bus.defaults"
VERIFY_AUDIO: Final = REPO_ROOT / "scripts" / "audio" / "verify-audio.sh"

INSTALLED_ROUTE: Final = Path("/etc/a-clockwork-plex/audio-routes/split-bus.conf")
INSTALLED_DEFAULTS: Final = Path("/etc/default/a-clockwork-plex-split-bus")
ROUTE_HELPER: Final = Path("/usr/local/bin/a-clockwork-plex-audio-route")
CAMILLADSP_CONFIG: Final = Path("/etc/a-clockwork-plex/camilladsp-split-bus.yml")

STATE_ROOT: Final = Path("/var/lib/a-clockwork-plex/hi-res-rehearsal")
STATE_PATH: Final = STATE_ROOT / "state.json"
BACKUP_ROUTE: Final = STATE_ROOT / "split-bus.conf.before"
BACKUP_DEFAULTS: Final = STATE_ROOT / "split-bus.defaults.before"

CANDIDATE_FORMAT: Final = "S32_LE"
ALLOWED_RATES: Final = (96000, 192000)
EXPECTED_BASELINE_RATE: Final = 44100
EXPECTED_BASELINE_FORMAT: Final = "S16_LE"
TIMING_PROFILES: Final = ("unchanged", "time-scaled")
BASELINE_GEOMETRY: Final = {
    "period_size": 1024,
    "buffer_size": 8192,
    "chunksize": 1024,
    "target_level": 2048,
}
TIME_SCALED_GEOMETRY: Final = {
    96000: {
        "period_size": 2048,
        "buffer_size": 16384,
        "chunksize": 2048,
        "target_level": 4096,
    },
    192000: {
        "period_size": 4096,
        "buffer_size": 32768,
        "chunksize": 4096,
        "target_level": 8192,
    },
}

HW_PARAMS: Final = (
    ("Plexamp -> ACP loopback", Path("/proc/asound/card7/pcm0p/sub0/hw_params")),
    ("CamillaDSP capture", Path("/proc/asound/card7/pcm1c/sub0/hw_params")),
    ("Physical DAC", Path("/proc/asound/Pro/pcm0p/sub0/hw_params")),
)

LOG_PATTERN: Final = re.compile(
    r"Media: Found an item|Mixer: Initializing audio pipeline|"
    r"BASS: Device 9 opened|BASS: Creating a mixer|"
    r"BASS: Created a gapless source stream"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_regular(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Required regular file is unavailable: {path}")
    return path.read_text(encoding="utf-8")


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    candidate = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(candidate, mode)
        os.replace(candidate, path)
        fsync_directory(path.parent)
    finally:
        candidate.unlink(missing_ok=True)


def run(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if check and result.returncode:
        detail = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        )
        raise RuntimeError(detail or f"Command failed: {' '.join(command)}")
    return result


def require_root() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Mutation requires root. Re-run this action with sudo.")


def read_route_status() -> dict[str, Any]:
    result = run([str(ROUTE_HELPER), "status"], check=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Audio route helper returned invalid JSON status.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Audio route helper returned an invalid status payload.")
    return payload


def verify_audio(label: str) -> None:
    result = run(["bash", str(VERIFY_AUDIO)])
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"Managed audio verification failed {label}.")


def ensure_no_existing_rehearsal() -> None:
    if STATE_ROOT.exists():
        raise RuntimeError(
            "A rehearsal state already exists. Do not start another candidate. "
            "Use --snapshot and --restore; if restore refuses, use "
            "scripts/audio/recover-hi-res-rehearsal.py."
        )


def ensure_accepted_baseline() -> None:
    expected_route = read_regular(PROFILE_ROUTE)
    expected_defaults = read_regular(PROFILE_DEFAULTS)
    installed_route = read_regular(INSTALLED_ROUTE)
    installed_defaults = read_regular(INSTALLED_DEFAULTS)
    if installed_route != expected_route:
        raise RuntimeError(
            "Installed split-bus route does not match the feature-branch accepted baseline; "
            "refusing rehearsal."
        )
    if installed_defaults != expected_defaults:
        raise RuntimeError(
            "Installed split-bus defaults do not match the feature-branch accepted baseline; "
            "refusing rehearsal."
        )
    status = read_route_status()
    if not (
        status.get("mode") == "split-bus-active"
        and status.get("selected_mode") == "split-bus-selected"
        and status.get("active_matches_split") is True
    ):
        raise RuntimeError(
            "Managed route is not the healthy accepted split bus; refusing rehearsal."
        )
    verify_audio("before hi-res rehearsal")


def replace_exact_once(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} marker, found {count}.")
    return content.replace(old, new, 1)


def candidate_geometry(rate: int, timing_profile: str) -> dict[str, int]:
    if timing_profile == "unchanged":
        return dict(BASELINE_GEOMETRY)
    if timing_profile == "time-scaled":
        geometry = TIME_SCALED_GEOMETRY.get(rate)
        if geometry is None:
            raise RuntimeError(f"No time-scaled geometry exists for rate {rate}.")
        return dict(geometry)
    raise RuntimeError(f"Unsupported timing profile: {timing_profile}")


def render_candidate(rate: int, timing_profile: str = "unchanged") -> tuple[str, str]:
    geometry = candidate_geometry(rate, timing_profile)
    route = read_regular(PROFILE_ROUTE)
    defaults = read_regular(PROFILE_DEFAULTS)
    route = replace_exact_once(
        route,
        f"        format {EXPECTED_BASELINE_FORMAT}\n",
        f"        format {CANDIDATE_FORMAT}\n",
        "split-route format",
    )
    route = replace_exact_once(
        route,
        f"        rate {EXPECTED_BASELINE_RATE}\n",
        f"        rate {rate}\n",
        "split-route rate",
    )
    defaults = replace_exact_once(
        defaults,
        f"SAMPLE_RATE={EXPECTED_BASELINE_RATE}\n",
        f"SAMPLE_RATE={rate}\n",
        "defaults sample rate",
    )
    defaults = replace_exact_once(
        defaults,
        f"FORMAT={EXPECTED_BASELINE_FORMAT}\n",
        f"FORMAT={CANDIDATE_FORMAT}\n",
        "defaults format",
    )
    if timing_profile == "time-scaled":
        route = replace_exact_once(
            route,
            f"        period_size {BASELINE_GEOMETRY['period_size']}\n",
            f"        period_size {geometry['period_size']}\n",
            "split-route period size",
        )
        route = replace_exact_once(
            route,
            f"        buffer_size {BASELINE_GEOMETRY['buffer_size']}\n",
            f"        buffer_size {geometry['buffer_size']}\n",
            "split-route buffer size",
        )
        for key, label in (
            ("PERIOD_SIZE", "period_size"),
            ("BUFFER_SIZE", "buffer_size"),
            ("CHUNKSIZE", "chunksize"),
            ("TARGET_LEVEL", "target_level"),
        ):
            defaults = replace_exact_once(
                defaults,
                f"{key}={BASELINE_GEOMETRY[label]}\n",
                f"{key}={geometry[label]}\n",
                f"defaults {label}",
            )
    return route, defaults


def write_state(
    rate: int,
    timing_profile: str,
    geometry: dict[str, int],
    candidate_route: str,
    candidate_defaults: str,
) -> None:
    ensure_no_existing_rehearsal()
    original_route = read_regular(INSTALLED_ROUTE)
    original_defaults = read_regular(INSTALLED_DEFAULTS)

    STATE_ROOT.mkdir(parents=True, mode=0o755)
    os.chmod(STATE_ROOT, 0o755)
    fsync_directory(STATE_ROOT.parent)

    # Backups are written atomically and fsynced before any candidate mutation.
    # This deliberately avoids shutil.copy2 here: the first physical rehearsal
    # rebooted after apply and both copy2-created backup files came back as
    # zero-length files while state.json and the candidate files persisted.
    atomic_write(BACKUP_ROUTE, original_route, 0o600)
    atomic_write(BACKUP_DEFAULTS, original_defaults, 0o600)

    original_route_hash = sha256_text(original_route)
    original_defaults_hash = sha256_text(original_defaults)
    if sha256(BACKUP_ROUTE) != original_route_hash:
        raise RuntimeError("Durable split-route backup verification failed.")
    if sha256(BACKUP_DEFAULTS) != original_defaults_hash:
        raise RuntimeError("Durable defaults backup verification failed.")

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_format": CANDIDATE_FORMAT,
        "candidate_rate": rate,
        "candidate_timing_profile": timing_profile,
        "candidate_period_size": geometry["period_size"],
        "candidate_buffer_size": geometry["buffer_size"],
        "candidate_chunksize": geometry["chunksize"],
        "candidate_target_level": geometry["target_level"],
        "original_route_sha256": original_route_hash,
        "original_defaults_sha256": original_defaults_hash,
        "candidate_route_sha256": sha256_text(candidate_route),
        "candidate_defaults_sha256": sha256_text(candidate_defaults),
        "durable_backups": True,
    }
    atomic_write(
        STATE_PATH,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        0o644,
    )
    load_state()


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file() or STATE_PATH.is_symlink():
        raise RuntimeError(f"No active rehearsal state exists at {STATE_PATH}.")
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Rehearsal state is invalid JSON; refusing automatic restore."
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("Unsupported rehearsal state; refusing automatic restore.")

    for path in (BACKUP_ROUTE, BACKUP_DEFAULTS):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Rehearsal backup is incomplete: {path}")
    if sha256(BACKUP_ROUTE) != payload.get("original_route_sha256"):
        raise RuntimeError("Rehearsal split-route backup checksum mismatch.")
    if sha256(BACKUP_DEFAULTS) != payload.get("original_defaults_sha256"):
        raise RuntimeError("Rehearsal defaults backup checksum mismatch.")
    return payload


def activate_split_bus() -> dict[str, Any]:
    result = run([str(ROUTE_HELPER), "activate-split-bus"])
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError("Managed split-bus activation failed.")
    status = read_route_status()
    if not (
        status.get("mode") == "split-bus-active"
        and status.get("selected_mode") == "split-bus-selected"
        and status.get("active_matches_split") is True
    ):
        raise RuntimeError("Split-bus activation returned an unexpected route state.")
    return status


def restore_original_files() -> dict[str, Any]:
    state = load_state()
    atomic_write(
        INSTALLED_ROUTE,
        BACKUP_ROUTE.read_text(encoding="utf-8"),
        0o644,
    )
    atomic_write(
        INSTALLED_DEFAULTS,
        BACKUP_DEFAULTS.read_text(encoding="utf-8"),
        0o644,
    )
    if sha256(INSTALLED_ROUTE) != state["original_route_sha256"]:
        raise RuntimeError(
            "Restored split-bus route checksum does not match the saved baseline."
        )
    if sha256(INSTALLED_DEFAULTS) != state["original_defaults_sha256"]:
        raise RuntimeError(
            "Restored defaults checksum does not match the saved baseline."
        )
    return state


def cleanup_state() -> None:
    shutil.rmtree(STATE_ROOT)
    fsync_directory(STATE_ROOT.parent)


def validate_candidate_files(state: dict[str, Any]) -> None:
    if sha256(INSTALLED_ROUTE) != state.get("candidate_route_sha256"):
        raise RuntimeError("Installed route does not match the rehearsed candidate.")
    if sha256(INSTALLED_DEFAULTS) != state.get("candidate_defaults_sha256"):
        raise RuntimeError("Installed defaults do not match the rehearsed candidate.")


def apply(rate: int, timing_profile: str) -> None:
    require_root()
    ensure_no_existing_rehearsal()
    ensure_accepted_baseline()
    geometry = candidate_geometry(rate, timing_profile)
    candidate_route, candidate_defaults = render_candidate(rate, timing_profile)
    write_state(rate, timing_profile, geometry, candidate_route, candidate_defaults)
    try:
        atomic_write(INSTALLED_ROUTE, candidate_route, 0o644)
        atomic_write(INSTALLED_DEFAULTS, candidate_defaults, 0o644)
        state = load_state()
        validate_candidate_files(state)
        activate_split_bus()
        camilla = read_regular(CAMILLADSP_CONFIG)
        for marker in (
            f"samplerate: {rate}",
            f"chunksize: {geometry['chunksize']}",
            f"target_level: {geometry['target_level']}",
            f"format: {CANDIDATE_FORMAT}",
        ):
            if marker not in camilla:
                raise RuntimeError(
                    f"Candidate CamillaDSP config is missing {marker!r}."
                )
    except Exception as exc:
        print(f"Candidate activation failed: {exc}", file=sys.stderr)
        try:
            restore_original_files()
            activate_split_bus()
            verify_audio("after failed rehearsal restoration")
            cleanup_state()
            print(
                "Accepted S16_LE / 44100 graph restored after failed candidate activation."
            )
        except Exception as restore_exc:
            raise RuntimeError(
                "Candidate activation failed and automatic baseline restoration was "
                f"incomplete. Rehearsal backup is retained at {STATE_ROOT}: {restore_exc}"
            ) from exc
        raise RuntimeError(
            "Candidate activation failed; accepted baseline was restored."
        ) from exc

    print()
    print("HI_RES_REHEARSAL_ACTIVE")
    print(f"candidate_format={CANDIDATE_FORMAT}")
    print(f"candidate_rate={rate}")
    print(f"candidate_timing_profile={timing_profile}")
    print(f"candidate_period_size={geometry['period_size']}")
    print(f"candidate_buffer_size={geometry['buffer_size']}")
    print(f"candidate_chunksize={geometry['chunksize']}")
    print(f"candidate_target_level={geometry['target_level']}")
    print(f"state={STATE_PATH}")
    print("The candidate remains active until --restore is run.")
    print(
        "The recovery files have been atomically written, fsynced and checksum-verified."
    )
    print("Play the matching Plex source, then run --snapshot before restoring.")
    print("If anything behaves unexpectedly, restore immediately.")


def restore() -> None:
    require_root()
    state = load_state()
    print(
        "Restoring accepted baseline from rehearsal state: "
        f"{state.get('candidate_format')} / {state.get('candidate_rate')}"
    )
    restore_original_files()
    try:
        activate_split_bus()
        verify_audio("after hi-res rehearsal restoration")
    except Exception as exc:
        raise RuntimeError(
            "Baseline files were restored but managed split-bus reactivation/verification "
            f"failed. Rehearsal backup is retained at {STATE_ROOT}: {exc}"
        ) from exc
    cleanup_state()
    print("HI_RES_REHEARSAL_RESTORED")
    print(f"format={EXPECTED_BASELINE_FORMAT}")
    print(f"rate={EXPECTED_BASELINE_RATE}")


def print_hw_params() -> None:
    for label, path in HW_PARAMS:
        print()
        print(f"===== {label} =====")
        try:
            print(path.read_text(encoding="utf-8").strip())
        except OSError as exc:
            print(f"unavailable: {path} ({exc})")


def print_recent_plexamp_log() -> None:
    log = Path.home() / ".cache" / "Plexamp" / "log" / "Plexamp.log"
    print()
    print("===== Plexamp negotiation =====")
    if not log.is_file():
        print(f"unavailable: {log}")
        return
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-1200:]
    except OSError as exc:
        print(f"unavailable: {log} ({exc})")
        return
    matches = [line for line in lines if LOG_PATTERN.search(line)]
    for line in matches[-20:]:
        print(line)


def snapshot() -> None:
    print("A Clockwork Plex — hi-res managed-bus rehearsal snapshot")
    if STATE_PATH.is_file():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        print(f"candidate_format={state.get('candidate_format', 'unknown')}")
        print(f"candidate_rate={state.get('candidate_rate', 'unknown')}")
        print(f"candidate_timing_profile={state.get('candidate_timing_profile', 'unchanged')}")
        print(f"candidate_period_size={state.get('candidate_period_size', 'unknown')}")
        print(f"candidate_buffer_size={state.get('candidate_buffer_size', 'unknown')}")
        print(f"candidate_chunksize={state.get('candidate_chunksize', 'unknown')}")
        print(f"candidate_target_level={state.get('candidate_target_level', 'unknown')}")
        print(f"durable_backups={state.get('durable_backups', False)}")
    else:
        print("candidate_state=none")
    try:
        status = read_route_status()
        print(f"route_mode={status.get('mode')}")
        print(f"selected_mode={status.get('selected_mode')}")
        print(f"active_matches_split={status.get('active_matches_split')}")
    except RuntimeError as exc:
        print(f"route_status_error={exc}")

    print_recent_plexamp_log()
    print_hw_params()
    print()
    print("===== CamillaDSP CPU =====")
    result = run(
        ["ps", "-C", "camilladsp", "-o", "pid=,pcpu=,pmem=,etimes=,args="]
    )
    print((result.stdout or result.stderr).strip() or "unavailable")


def print_plan(rate: int | None, timing_profile: str) -> None:
    requested = rate if rate is not None else 96000
    geometry = candidate_geometry(requested, timing_profile)
    route, defaults = render_candidate(requested, timing_profile)
    print("A Clockwork Plex — guarded hi-res managed-bus rehearsal")
    print()
    print("Default mode: plan only; no files, services, routes or PCMs are changed.")
    print(f"Candidate format: {CANDIDATE_FORMAT}")
    print(f"Candidate rate:   {requested}")
    print(f"Timing profile:   {timing_profile}")
    print(
        "Timing geometry:  "
        f"period={geometry['period_size']}, buffer={geometry['buffer_size']}, "
        f"chunk={geometry['chunksize']}, target={geometry['target_level']}"
    )
    print(f"Allowed rates:    {', '.join(str(value) for value in ALLOWED_RATES)}")
    print()
    print("An --apply run will:")
    print("  1. refuse if any earlier rehearsal state still exists;")
    print("  2. require the exact accepted S16_LE / 44100 branch baseline and verify it;")
    print(
        "  3. atomically write, fsync and checksum-verify exact route/default backups "
        "before mutation;"
    )
    print("  4. stage S32_LE at the selected fixed managed-bus rate;")
    print("  5. use the existing managed route helper to quiesce/restart the graph safely;")
    print("  6. leave the candidate active for a deliberate playback snapshot;")
    print("  7. require an explicit --restore to return to the accepted baseline;")
    print("  8. retain the backup if restoration cannot be fully verified.")
    print()
    print(f"Candidate route SHA-256:    {sha256_text(route)}")
    print(f"Candidate defaults SHA-256: {sha256_text(defaults)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarded reversible S32_LE/96-or-192 kHz managed-bus rehearsal."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="activate a guarded candidate bus"
    )
    mode.add_argument(
        "--restore", action="store_true", help="restore the saved accepted baseline"
    )
    mode.add_argument(
        "--snapshot",
        action="store_true",
        help="capture current read-only audio evidence",
    )
    parser.add_argument(
        "--rate",
        type=int,
        choices=ALLOWED_RATES,
        help="candidate fixed bus rate for plan/apply (96000 or 192000)",
    )
    parser.add_argument(
        "--timing-profile",
        choices=TIMING_PROFILES,
        default="unchanged",
        help=(
            "frame geometry: unchanged preserves the original 44.1 kHz frame counts; "
            "time-scaled uses power-of-two high-rate values with approximately the "
            "accepted graph's timing headroom"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.apply:
            if args.rate is None:
                raise RuntimeError("--apply requires --rate 96000 or --rate 192000.")
            apply(args.rate, args.timing_profile)
        elif args.restore:
            if args.rate is not None:
                raise RuntimeError("--restore does not accept --rate.")
            restore()
        elif args.snapshot:
            if args.rate is not None:
                raise RuntimeError("--snapshot does not accept --rate.")
            snapshot()
        else:
            print_plan(args.rate, args.timing_profile)
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
