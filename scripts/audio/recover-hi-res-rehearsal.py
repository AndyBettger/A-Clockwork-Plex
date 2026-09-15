#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

STATE_ROOT: Final = Path("/var/lib/a-clockwork-plex/hi-res-rehearsal")
STATE_PATH: Final = STATE_ROOT / "state.json"
BACKUP_ROUTE: Final = STATE_ROOT / "split-bus.conf.before"
BACKUP_DEFAULTS: Final = STATE_ROOT / "split-bus.defaults.before"

EXPECTED_SCHEMA: Final = 1
EXPECTED_FORMAT: Final = "S32_LE"
EXPECTED_RATES: Final = (96000, 192000)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_if_readable(path: Path) -> str | None:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        return sha256(path)
    except OSError:
        return None


def read_regular(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Required regular file is unavailable: {path}")
    return path.read_text(encoding="utf-8")


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file() or STATE_PATH.is_symlink():
        raise RuntimeError(f"No valid rehearsal state exists at {STATE_PATH}.")
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Rehearsal state cannot be read as valid JSON.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != EXPECTED_SCHEMA:
        raise RuntimeError("Unsupported rehearsal state schema.")
    if payload.get("candidate_format") != EXPECTED_FORMAT:
        raise RuntimeError("Rehearsal state does not describe the expected S32_LE candidate.")
    if payload.get("candidate_rate") not in EXPECTED_RATES:
        raise RuntimeError("Rehearsal state contains an unsupported candidate rate.")
    for key in (
        "original_route_sha256",
        "original_defaults_sha256",
        "candidate_route_sha256",
        "candidate_defaults_sha256",
    ):
        value = payload.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise RuntimeError(f"Rehearsal state is missing a valid {key} value.")
    return payload


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.recovery.", dir=path.parent)
    candidate = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(candidate, mode)
        os.replace(candidate, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        candidate.unlink(missing_ok=True)


def recovery_contract(state: dict[str, Any]) -> dict[str, Any]:
    profile_route_hash = sha256(PROFILE_ROUTE)
    profile_defaults_hash = sha256(PROFILE_DEFAULTS)
    backup_route_hash = hash_if_readable(BACKUP_ROUTE)
    backup_defaults_hash = hash_if_readable(BACKUP_DEFAULTS)
    installed_route_hash = hash_if_readable(INSTALLED_ROUTE)
    installed_defaults_hash = hash_if_readable(INSTALLED_DEFAULTS)

    originals_match_repository = (
        state["original_route_sha256"] == profile_route_hash
        and state["original_defaults_sha256"] == profile_defaults_hash
    )
    installed_route_known = installed_route_hash in {
        state["candidate_route_sha256"],
        state["original_route_sha256"],
    }
    installed_defaults_known = installed_defaults_hash in {
        state["candidate_defaults_sha256"],
        state["original_defaults_sha256"],
    }

    return {
        "candidate_format": state["candidate_format"],
        "candidate_rate": state["candidate_rate"],
        "recorded_original_route_sha256": state["original_route_sha256"],
        "recorded_original_defaults_sha256": state["original_defaults_sha256"],
        "recorded_candidate_route_sha256": state["candidate_route_sha256"],
        "recorded_candidate_defaults_sha256": state["candidate_defaults_sha256"],
        "repository_route_sha256": profile_route_hash,
        "repository_defaults_sha256": profile_defaults_hash,
        "saved_backup_route_sha256": backup_route_hash,
        "saved_backup_defaults_sha256": backup_defaults_hash,
        "installed_route_sha256": installed_route_hash,
        "installed_defaults_sha256": installed_defaults_hash,
        "saved_backup_route_ok": backup_route_hash == state["original_route_sha256"],
        "saved_backup_defaults_ok": backup_defaults_hash == state["original_defaults_sha256"],
        "originals_match_repository": originals_match_repository,
        "installed_route_known": installed_route_known,
        "installed_defaults_known": installed_defaults_known,
        "recovery_permitted": (
            originals_match_repository
            and installed_route_known
            and installed_defaults_known
        ),
    }


def print_report(report: dict[str, Any]) -> None:
    print("A Clockwork Plex — hi-res rehearsal recovery audit")
    print("READ-ONLY unless --apply is supplied")
    print()
    for key in (
        "candidate_format",
        "candidate_rate",
        "recorded_original_route_sha256",
        "repository_route_sha256",
        "saved_backup_route_sha256",
        "installed_route_sha256",
        "recorded_original_defaults_sha256",
        "repository_defaults_sha256",
        "saved_backup_defaults_sha256",
        "installed_defaults_sha256",
        "saved_backup_route_ok",
        "saved_backup_defaults_ok",
        "originals_match_repository",
        "installed_route_known",
        "installed_defaults_known",
        "recovery_permitted",
    ):
        print(f"{key}={report.get(key)}")
    print()
    if report["recovery_permitted"]:
        print(
            "RECOVERY_READY: the state-recorded accepted baseline matches the exact "
            "feature-branch profile, and the installed files are known rehearsal/baseline content."
        )
        if not report["saved_backup_route_ok"] or not report["saved_backup_defaults_ok"]:
            print(
                "The saved backup copy is damaged or unreadable, so recovery will reconstruct "
                "only from the checksum-matching repository baseline."
            )
    else:
        print(
            "RECOVERY_REFUSED: do not overwrite audio files. The recorded state cannot be "
            "safely reconciled with the repository baseline/current installed files."
        )


def require_root() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Recovery mutation requires root; re-run with sudo and --apply.")


def verify_audio() -> None:
    result = run(["bash", str(VERIFY_AUDIO)])
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError("Managed audio verification failed after rehearsal recovery.")


def activate_baseline() -> None:
    result = run([str(ROUTE_HELPER), "activate-split-bus"])
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError("Managed split-bus activation failed after restoring baseline files.")


def archive_rehearsal_state() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = STATE_ROOT.with_name(f"{STATE_ROOT.name}.recovered-{stamp}")
    if archive.exists():
        raise RuntimeError(f"Recovery archive path already exists: {archive}")
    os.replace(STATE_ROOT, archive)
    directory_fd = os.open(archive.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return archive


def apply_recovery(state: dict[str, Any], report: dict[str, Any]) -> None:
    require_root()
    if not report["recovery_permitted"]:
        raise RuntimeError("Checksum-gated recovery contract is not satisfied; refusing mutation.")

    baseline_route = read_regular(PROFILE_ROUTE)
    baseline_defaults = read_regular(PROFILE_DEFAULTS)
    if hashlib.sha256(baseline_route.encode("utf-8")).hexdigest() != state["original_route_sha256"]:
        raise RuntimeError("Repository route changed after the recovery audit; refusing mutation.")
    if hashlib.sha256(baseline_defaults.encode("utf-8")).hexdigest() != state["original_defaults_sha256"]:
        raise RuntimeError("Repository defaults changed after the recovery audit; refusing mutation.")

    evidence_route = STATE_ROOT / "installed-route-at-recovery.txt"
    evidence_defaults = STATE_ROOT / "installed-defaults-at-recovery.txt"
    atomic_write(evidence_route, read_regular(INSTALLED_ROUTE), 0o600)
    atomic_write(evidence_defaults, read_regular(INSTALLED_DEFAULTS), 0o600)

    atomic_write(INSTALLED_ROUTE, baseline_route, 0o644)
    atomic_write(INSTALLED_DEFAULTS, baseline_defaults, 0o644)

    if sha256(INSTALLED_ROUTE) != state["original_route_sha256"]:
        raise RuntimeError("Restored split-route hash does not match the recorded accepted baseline.")
    if sha256(INSTALLED_DEFAULTS) != state["original_defaults_sha256"]:
        raise RuntimeError("Restored defaults hash does not match the recorded accepted baseline.")

    try:
        activate_baseline()
        verify_audio()
    except Exception as exc:
        raise RuntimeError(
            "Accepted baseline files were restored, but route activation/verification failed. "
            f"Recovery evidence remains at {STATE_ROOT}: {exc}"
        ) from exc

    archive = archive_rehearsal_state()
    print()
    print("HI_RES_REHEARSAL_RECOVERY=PASS")
    print("format=S16_LE")
    print("rate=44100")
    print(f"recovery_evidence={archive}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Checksum-gated recovery for a hi-res managed-bus rehearsal whose saved backup "
            "copy cannot pass the normal restore guard. Default mode is read-only."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="restore the exact repository baseline only if every checksum/known-state gate passes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        state = load_state()
        report = recovery_contract(state)
        print_report(report)
        if args.apply:
            apply_recovery(state, report)
        return 0 if report["recovery_permitted"] else 1
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
