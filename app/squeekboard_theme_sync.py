"""Opt-in C3 trial/dev ACP keyboard palette bridge; never owns the stock OSK.

The browser reports the CURRENT ACPDisplayDimming.status() result. We resolve
the 23 allowed styles on the Python side, and write only the previously staged
private C3 style.css while an explicitly opted-in C3 trial or dev session is alive.
The original OSK, C2 resources, system GTK and trial recovery are never touched.
"""
from __future__ import annotations

import fcntl
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ALLOWED_HOSTS = frozenset(("localhost", "127.0.0.1", "::1"))
MAX_BODY = 384


class SyncError(ValueError):
    pass


def load_script(filename: str):
    """Load only hardcoded repository scripts, never a path from HTTP."""
    allowed = {
        "try-squeekboard-hot-css.py": "acp_sync_c3_trial",
        "try-squeekboard-c3-dev.py": "acp_sync_c3_dev",
        "stage-squeekboard-hot-css.py": "acp_sync_c3_stage",
        "plan-squeekboard-acp-theme.py": "acp_sync_palette_planner",
    }
    if filename not in allowed:
        raise SyncError("Unknown C3 helper")
    key = allowed[filename]
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, SCRIPTS / filename)
    if not spec or not spec.loader:
        raise SyncError("C3 trial helper unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module  # Required for the read-only planner dataclass.
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(key, None)
        raise
    return module


def local_browser_request(req, *, mutation: bool) -> bool:
    """Never expose trial controls to the LAN, a reverse proxy, or other origin."""
    try:
        peer = ipaddress.ip_address(req.remote_addr)
    except (ValueError, TypeError):
        return False
    # The kiosk uses a loopback URL. Never trust a reverse proxy on localhost
    # as proof that an external browser is local.
    host = req.host.lower()
    valid_host = (host in ALLOWED_HOSTS
                  or (host.rsplit(":", 1)[0] in ("localhost", "127.0.0.1")
                      and host.rsplit(":", 1)[-1].isdigit())
                  or host == "[::1]"
                  or (host.startswith("[::1]:") and host[6:].isdigit()))
    if not peer.is_loopback or not valid_host:
        return False
    if any(req.headers.get(header) for header in ("X-Forwarded-Host",
                                                   "X-Forwarded-For",
                                                   "X-Forwarded-Proto", "Forwarded")):
        return False
    if mutation:
        if req.headers.get("Origin") != req.scheme + "://" + req.host:
            return False
        if req.headers.get("Sec-Fetch-Site") not in (None, "same-origin"):
            return False
        if (req.mimetype != "application/json" or req.content_length is None
                or req.content_length > MAX_BODY):
            return False
    return True


def validated_payload(raw: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(raw, dict) or set(raw) != {"daytimeTheme", "night"}:
        raise SyncError("Expected exactly daytimeTheme and night")
    daytime = raw["daytimeTheme"]
    night = raw["night"]
    if not isinstance(daytime, str) or len(daytime) > 32:
        raise SyncError("Invalid daytime theme")
    if not isinstance(night, dict) or set(night) != {"active", "interacting", "effectiveStyle"}:
        raise SyncError("Unexpected night state fields")
    if type(night["active"]) is not bool or type(night["interacting"]) is not bool:
        raise SyncError("Night flags must be booleans")
    if not isinstance(night["effectiveStyle"], str) or night["effectiveStyle"] not in ("classic", "astronomy"):
        raise SyncError("Unsupported effective night style")
    planner = load_script("plan-squeekboard-acp-theme.py")
    # Planner already has the agreed Classic Dark fallback for unknown themes.
    decision = planner.select_palette(daytime, night)
    return decision.palette, night



def user_unit_active(name: str) -> bool:
    """Query the Pi user's systemd manager even from ACP's *system* service.

    systemd User=andy does not guarantee XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS
    are inherited. Pin these for this one read-only child; NEVER change the
    process-wide environment or start/stop any unit.
    """
    allowed = frozenset((
        "acp-squeekboard-c3-trial.service",
        "acp-squeekboard-c3-dev.service",
        "acp-squeekboard-c3-restore.timer",
        "acp-squeekboard-overlay-trial.service",
        "acp-squeekboard-overlay-restore.timer",
    ))
    if name not in allowed or os.geteuid() == 0:
        return False
    runtime = Path("/run/user") / str(os.getuid())
    if not (runtime / "bus").is_socket():
        return False
    env = os.environ.copy()
    env.update({
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
        "HOME": str(Path.home()),
    })
    try:
        check = subprocess.run(
            ("systemctl", "--user", "is-active", "--quiet", name),
            env=env, capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return check.returncode == 0


def opted_in_trial():
    """Read-only positive proof of ONE still-running, opted-in C3 trial."""
    if os.geteuid() == 0:
        return None
    try:
        trial = load_script("try-squeekboard-hot-css.py")
        # Dev mode has no artificial 180s expiry. It remains opt-in and
        # needs one exact, live, hash-verified C3 instance with NO stock OSK.
        # The dashboard system service must query user-systemd with its own
        # explicit DBus environment (not the SSH/session environment).
        if user_unit_active("acp-squeekboard-c3-dev.service"):
            dev = load_script("try-squeekboard-c3-dev.py")
            return dev.active_state(trial=trial, unit_check=user_unit_active)
        if (not user_unit_active(trial.TRIAL_UNIT + ".service")
                or not user_unit_active(trial.ROLLBACK_UNIT + ".timer")
                or user_unit_active(trial.C2_TRIAL_UNIT + ".service")
                or user_unit_active(trial.C2_ROLLBACK_UNIT + ".timer")):
            return None
        active = []
        for path in trial.ROOT.glob("trial-*/state.json"):
            if path.is_symlink() or not path.is_file():
                continue
            meta = path.stat()
            if (meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600
                    or meta.st_nlink != 1):
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("theme_sync") is not True:
                continue
            state = trial.read_state(path)  # Checks exact candidate ELF + recovery env.
            created = state.get("created_at")
            if not isinstance(created, (int, float)) or not 0 <= time.time() - created < 220:
                continue
            candidate = Path(state["candidate"])
            if len(trial.candidate_pids(candidate)) != 1 or trial.vendor_pids():
                continue
            active.append(path)
        if len(active) != 1:
            return None
        return active[0]
    except Exception:
        # This is an opt-in safety gate: a failed hash, missing state,
        # user-bus problem or unexpected validation error must fail CLOSED.
        return None


def status() -> dict[str, Any]:
    return {"enabled": opted_in_trial() is not None}


def apply(payload: Any) -> dict[str, Any]:
    palette, _night = validated_payload(payload)
    state_path = opted_in_trial()
    if state_path is None:
        return {"enabled": False, "changed": False, "reason": "no opted-in live C3 trial"}
    stage = load_script("stage-squeekboard-hot-css.py")
    lock = state_path.parent / "theme-sync.lock"
    # Lock is confined to the already validated private trial folder, NEVER C3
    # CSS root (which accepts exactly README.txt and style.css).
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        meta = os.fstat(fd)
        if (meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_nlink != 1 or not stat.S_ISREG(meta.st_mode)):
            raise SyncError("Unsafe trial sync lock")
        fcntl.flock(fd, fcntl.LOCK_EX)
        # Close the race with parallel browser requests or a just-ended trial.
        if opted_in_trial() != state_path:
            return {"enabled": False, "changed": False, "reason": "C3 trial ended"}
        styles = stage.palettes()
        if palette not in styles:
            raise SyncError("Palette outside validated C3 inventory")
        before, changed = stage.select(styles, palette)
        return {"enabled": True, "palette": palette, "previous": before, "changed": changed}
    finally:
        os.close(fd)
