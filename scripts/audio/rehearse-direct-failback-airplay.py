#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

sys.dont_write_bytecode = True

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
PROFILE_DIRECT: Final = (
    REPO_ROOT / "installer" / "profiles" / "eq-split-bus" / "direct-alarm-bypass.conf"
)
VERIFY_AUDIO: Final = REPO_ROOT / "scripts" / "audio" / "verify-audio.sh"

INSTALLED_DIRECT: Final = Path(
    "/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf"
)
ROUTE_HELPER: Final = Path("/usr/local/bin/a-clockwork-plex-audio-route")
STATE_ROOT: Final = Path("/var/lib/a-clockwork-plex/direct-airplay-rehearsal")
STATE_PATH: Final = STATE_ROOT / "state.json"
BACKUP_DIRECT: Final = STATE_ROOT / "direct-alarm-bypass.conf.before"
HI_RES_STATE_ROOT: Final = Path("/var/lib/a-clockwork-plex/hi-res-rehearsal")

AIRPLAY_PREFIX: Final = """pcm.acp_airplay {
    type plug
    slave.pcm "acp_airplay_volume"
"""
AIRPLAY_LIVE_PREFIX: Final = """pcm.acp_airplay_live_volume {
    type softvol
    slave.pcm "acp_airplay_volume"
    control {
        name "A Clockwork AirPlay Live"
        card "Pro"
    }
    min_dB -51.0
    max_dB 0.0
    resolution 256
}

pcm.acp_airplay {
    type plug
    slave.pcm "acp_airplay_live_volume"
"""


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
            "A Direct/AirPlay rehearsal state already exists. Use --snapshot or --restore."
        )
    if HI_RES_STATE_ROOT.exists():
        raise RuntimeError(
            "A hi-res rehearsal is active. Restore it before starting Direct/AirPlay rehearsal."
        )


def ensure_accepted_baseline() -> None:
    expected_direct = read_regular(PROFILE_DIRECT)
    installed_direct = read_regular(INSTALLED_DIRECT)
    if installed_direct != expected_direct:
        raise RuntimeError(
            "Installed Direct/failback route does not match the feature-branch accepted "
            "baseline; refusing rehearsal."
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
    verify_audio("before Direct/AirPlay rehearsal")


def render_candidate() -> str:
    direct = read_regular(PROFILE_DIRECT)
    if "pcm.acp_airplay_live_volume" in direct:
        raise RuntimeError(
            "Accepted Direct route already contains AirPlay Live; rehearsal is obsolete."
        )
    count = direct.count(AIRPLAY_PREFIX)
    if count != 1:
        raise RuntimeError(f"Expected exactly one Direct AirPlay route marker, found {count}.")
    candidate = direct.replace(AIRPLAY_PREFIX, AIRPLAY_LIVE_PREFIX, 1)
    if "format S16_LE" not in candidate or "rate 44100" not in candidate:
        raise RuntimeError("Direct candidate lost the accepted S16_LE / 44100 contract.")
    return candidate


def write_state(candidate: str) -> None:
    ensure_no_existing_rehearsal()
    original = read_regular(INSTALLED_DIRECT)
    STATE_ROOT.mkdir(parents=True, mode=0o755)
    os.chmod(STATE_ROOT, 0o755)
    fsync_directory(STATE_ROOT.parent)

    atomic_write(BACKUP_DIRECT, original, 0o600)
    original_hash = sha256_text(original)
    if sha256(BACKUP_DIRECT) != original_hash:
        raise RuntimeError("Durable Direct-route backup verification failed.")

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "original_direct_sha256": original_hash,
        "candidate_direct_sha256": sha256_text(candidate),
        "candidate_change": "receiver-owned AirPlay Live softvol only",
        "candidate_format": "S16_LE",
        "candidate_rate": 44100,
        "durable_backup": True,
    }
    atomic_write(
        STATE_PATH,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        0o644,
    )
    load_state()


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file() or STATE_PATH.is_symlink():
        raise RuntimeError(f"No active Direct/AirPlay rehearsal exists at {STATE_PATH}.")
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Direct/AirPlay rehearsal state is invalid JSON; refusing automatic restore."
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("Unsupported Direct/AirPlay rehearsal state.")
    if not BACKUP_DIRECT.is_file() or BACKUP_DIRECT.is_symlink():
        raise RuntimeError("Direct/AirPlay rehearsal backup is incomplete.")
    if sha256(BACKUP_DIRECT) != payload.get("original_direct_sha256"):
        raise RuntimeError("Direct/AirPlay rehearsal backup checksum mismatch.")
    return payload


def emit_command(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def activate_direct_candidate() -> dict[str, Any]:
    result = run([str(ROUTE_HELPER), "activate-direct-failback"])
    emit_command(result)
    if result.returncode:
        raise RuntimeError("Managed Direct/failback activation failed.")
    status = read_route_status()
    if not (
        status.get("mode") == "direct-failback"
        and status.get("selected_mode") == "direct-failback"
        and status.get("active_matches_direct_failback") is True
    ):
        raise RuntimeError("Direct candidate activation returned an unexpected route state.")
    return status


def activate_split_bus() -> dict[str, Any]:
    result = run([str(ROUTE_HELPER), "activate-split-bus"])
    emit_command(result)
    if result.returncode:
        raise RuntimeError("Managed split-bus restoration failed.")
    status = read_route_status()
    if not (
        status.get("mode") == "split-bus-active"
        and status.get("selected_mode") == "split-bus-selected"
        and status.get("active_matches_split") is True
    ):
        raise RuntimeError("Split-bus restoration returned an unexpected route state.")
    return status


def restore_original_direct() -> dict[str, Any]:
    state = load_state()
    atomic_write(
        INSTALLED_DIRECT,
        BACKUP_DIRECT.read_text(encoding="utf-8"),
        0o644,
    )
    if sha256(INSTALLED_DIRECT) != state["original_direct_sha256"]:
        raise RuntimeError("Restored Direct route checksum does not match saved baseline.")
    return state


def cleanup_state() -> None:
    shutil.rmtree(STATE_ROOT)
    fsync_directory(STATE_ROOT.parent)


def apply() -> None:
    require_root()
    ensure_no_existing_rehearsal()
    ensure_accepted_baseline()
    candidate = render_candidate()
    write_state(candidate)
    try:
        atomic_write(INSTALLED_DIRECT, candidate, 0o644)
        state = load_state()
        if sha256(INSTALLED_DIRECT) != state["candidate_direct_sha256"]:
            raise RuntimeError("Installed Direct route does not match the candidate.")
        status = activate_direct_candidate()
    except Exception as exc:
        print(f"Candidate activation failed: {exc}", file=sys.stderr)
        try:
            restore_original_direct()
            activate_split_bus()
            verify_audio("after failed Direct/AirPlay rehearsal restoration")
            cleanup_state()
            print("Accepted split-bus baseline restored after failed candidate activation.")
        except Exception as restore_exc:
            raise RuntimeError(
                "Candidate activation failed and automatic restoration was incomplete. "
                f"Rehearsal backup is retained at {STATE_ROOT}: {restore_exc}"
            ) from exc
        raise RuntimeError(
            "Direct/AirPlay candidate activation failed; accepted baseline was restored."
        ) from exc

    print()
    print("DIRECT_AIRPLAY_REHEARSAL_ACTIVE")
    print("candidate_format=S16_LE")
    print("candidate_rate=44100")
    print("candidate_change=receiver-owned AirPlay Live softvol only")
    print(f"active_matches_direct_failback={status.get('active_matches_direct_failback')}")
    print(f"state={STATE_PATH}")
    print("CamillaDSP is intentionally bypassed in this Direct/failback rehearsal.")
    print("Test AirPlay Live/Trim/Music Master plus alarm takeover before --restore.")
    print("The candidate remains active until --restore is run.")


def restore() -> None:
    require_root()
    state = load_state()
    print(
        "Restoring accepted Direct route and managed split bus from rehearsal state: "
        f"{state.get('candidate_format')} / {state.get('candidate_rate')}"
    )
    restore_original_direct()
    try:
        activate_split_bus()
        verify_audio("after Direct/AirPlay rehearsal restoration")
    except Exception as exc:
        raise RuntimeError(
            "The accepted Direct route was restored, but split-bus reactivation/verification "
            f"failed. Rehearsal backup is retained at {STATE_ROOT}: {exc}"
        ) from exc
    cleanup_state()
    print("DIRECT_AIRPLAY_REHEARSAL_RESTORED")
    print("route=split-bus-active")


def snapshot() -> None:
    print("A Clockwork Plex — Direct/failback AirPlay parity rehearsal snapshot")
    if STATE_PATH.is_file():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        print(f"candidate_change={state.get('candidate_change', 'unknown')}")
        print(f"candidate_format={state.get('candidate_format', 'unknown')}")
        print(f"candidate_rate={state.get('candidate_rate', 'unknown')}")
        print(f"durable_backup={state.get('durable_backup', False)}")
    else:
        print("candidate_state=none")
    try:
        status = read_route_status()
        print(f"route_mode={status.get('mode')}")
        print(f"selected_mode={status.get('selected_mode')}")
        print(
            "active_matches_direct_failback="
            f"{status.get('active_matches_direct_failback')}"
        )
        print(
            "camilladsp_active="
            f"{status.get('services', {}).get('camilladsp', {}).get('active')}"
        )
    except RuntimeError as exc:
        print(f"route_status_error={exc}")

    print("\n===== physical DAC =====")
    path = Path("/proc/asound/Pro/pcm0p/sub0/hw_params")
    try:
        print(path.read_text(encoding="utf-8").strip())
    except OSError as exc:
        print(f"unavailable: {path} ({exc})")

    print("\n===== AirPlay Live control =====")
    result = run(["amixer", "-c", "Pro", "get", "A Clockwork AirPlay Live"])
    print((result.stdout or result.stderr).strip() or "unavailable")


def print_plan() -> None:
    candidate = render_candidate()
    print("A Clockwork Plex — guarded Direct/failback AirPlay parity rehearsal")
    print()
    print("Default mode: plan only; no files, services, routes or PCMs are changed.")
    print("Candidate: accepted S16_LE / 44100 Direct alarm-safe route")
    print("Delta:     add receiver-owned A Clockwork AirPlay Live softvol only")
    print()
    print("An --apply run will:")
    print("  1. require the exact healthy accepted split-bus baseline;")
    print("  2. atomically back up and checksum the installed pinned Direct route;")
    print("  3. stage the one-delta Direct candidate;")
    print("  4. use the existing route helper to quiesce apps and enter Direct/failback;")
    print("  5. leave the candidate active for AirPlay and alarm physical testing;")
    print("  6. require --restore to put back the exact pinned Direct route and split bus.")
    print()
    print(f"Accepted Direct SHA-256:  {sha256(PROFILE_DIRECT)}")
    print(f"Candidate Direct SHA-256: {sha256_text(candidate)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarded reversible Direct/failback receiver-owned AirPlay rehearsal."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="activate the Direct candidate")
    mode.add_argument("--restore", action="store_true", help="restore accepted split bus")
    mode.add_argument("--snapshot", action="store_true", help="capture read-only evidence")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.apply:
            apply()
        elif args.restore:
            restore()
        elif args.snapshot:
            snapshot()
        else:
            print_plan()
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
