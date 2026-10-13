#!/usr/bin/env python3
"""Guarded C3 hot-CSS test using *only* the separately verified ARM64 candidate.

--plan: READ-ONLY; validates pinned ZIP, stock singleton, accepted C2 layouts,
        one private C3 hot-CSS resource, user service manager and inactive trials.
--start: VOLUNTARY 180s disruptive keyboard test after a successful --plan;
         arms an INDEPENDENT 240s restore timer before touching the stock OSK.
--worker and --restore: internal trial/rescue user-service functions.

The original C2 controller, all C2 palettes and keyboard files, ACP settings,
global GTK, apt/dpkg, audio, Headless and NFC remain entirely unchanged.
A CSS palette change is made separately with stage-squeekboard-hot-css.py
while C3 is running; it must not restart/blur the real keyboard.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time

EXPECTED_VENDOR_SHA256 = "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338"
EXPECTED_CANDIDATE_SHA256 = "fdd1da08861bbc45331e66a70996953ed6ebfb52915a0a5abeb21c585f40bfd5"
TRIAL_SECONDS = 180
ROLLBACK_SECONDS = 240
TRIAL_UNIT = "acp-squeekboard-c3-trial"
ROLLBACK_UNIT = "acp-squeekboard-c3-restore"
ROOT = Path.home() / ".cache" / "a-clockwork-plex" / "osk-c3-hot-css-trials"
C2_TRIAL_UNIT = "acp-squeekboard-overlay-trial"
C2_ROLLBACK_UNIT = "acp-squeekboard-overlay-restore"
CANDIDATE_FILENAME = "squeekboard-c3-hot-css-arm64"


class TrialError(Exception):
    pass


def load_inspector():
    path = Path(__file__).resolve().with_name("inspect-squeekboard-hot-css-artifact.py")
    spec = importlib.util.spec_from_file_location("acp_c3_hot_css_checker", path)
    if not spec or not spec.loader:
        raise TrialError("ABI checker is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_theme_validator():
    path = Path(__file__).resolve().with_name("validate-squeekboard-uk-theme-stage.py")
    spec = importlib.util.spec_from_file_location("acp_c2_uk_stage_check", path)
    if not spec or not spec.loader:
        raise TrialError("UK/ACP stage validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def load_compact_number_stage():
    path = Path(__file__).resolve().with_name("stage-squeekboard-compact-number.py")
    spec = importlib.util.spec_from_file_location("acp_c2_compact_number", path)
    if not spec or not spec.loader:
        raise TrialError("Compact-number stage inspector is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verified_compact_keyboard_dir() -> str:
    """Validate the *new* private layout before any OSK is interrupted.

    The original accepted GB layout is never edited or replaced. Restoration
    deliberately does not depend on this new stage continuing to exist.
    """
    compact = load_compact_number_stage()
    try:
        expected, _width, _side = compact.expected_layouts(compact.input_layouts())
        compact.verify(expected)
    except (compact.CompactError, OSError, ValueError) as exc:
        raise TrialError("Compact numeric layout verification failed: " + str(exc)) from exc
    return str(compact.ROOT / "keyboards")



def load_c3_stage():
    path = Path(__file__).resolve().with_name("stage-squeekboard-hot-css.py")
    spec = importlib.util.spec_from_file_location("acp_c3_verified_hot_css_stage", path)
    if not spec or not spec.loader:
        raise TrialError("C3 CSS stage helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_style_environment() -> dict[str, str]:
    """All C3-only overrides are explicit and checked BEFORE stock is stopped.

    Do not include these in the independent stock rescue service environment.
    The only live CSS output is a copy in the C3 stage, not the accepted C2 CSS.
    """
    checker = load_theme_validator()
    try:
        checker.validate()  # all seven GB keymaps and 23 ACP theme samples
        gen = checker.generator()
        root = gen.DEST
        if root.is_symlink() or not root.is_dir():
            raise TrialError("Accepted C2 UK theme root missing/unsafe")
        compact_keyboard = verified_compact_keyboard_dir()
        c3 = load_c3_stage()
        selected = c3.inspect(c3.palettes())
        if selected != c3.DEFAULT_PALETTE:
            raise TrialError("C3 trial must initially show Classic Dark")
        values = c3.resource_environment()
        if set(values) != {"G_RESOURCE_OVERLAYS", "ACP_SQUEEKBOARD_CSS_DIR"}:
            raise TrialError("C3 CSS overlay environment is not candidate-only")
        if values["ACP_SQUEEKBOARD_CSS_DIR"] != str(c3.ROOT):
            raise TrialError("Unexpected C3 CSS stage path")
        if values["G_RESOURCE_OVERLAYS"] != (
            c3.RESOURCE_PREFIX + "=" + str(c3.ROOT)
        ):
            raise TrialError("Unexpected C3 GResource overlay")
        return {
            "SQUEEKBOARD_KEYBOARDSDIR": compact_keyboard,
            "XDG_CONFIG_HOME": str(root / "themes" / "classic_dark"),
            **values,
        }
    except (checker.CheckError, c3.CSSStageError, OSError, ValueError, RuntimeError) as exc:
        raise TrialError("C3 accepted-theme preflight failed: " + str(exc)) from exc



def run(*args: str, check: bool = False, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check, timeout=timeout)


def session_environment() -> dict[str, str]:
    runtime = Path("/run/user") / str(os.getuid())
    socket = runtime / "wayland-0"
    bus = runtime / "bus"
    if not socket.is_socket() or not bus.is_socket():
        raise TrialError("Expected labwc Wayland or user D-Bus socket is absent; stop here")
    return {
        "XDG_RUNTIME_DIR": str(runtime),
        "WAYLAND_DISPLAY": "wayland-0",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(bus),
        "XDG_SESSION_TYPE": "wayland",
        "HOME": str(Path.home()),
    }


def vendor_pids() -> list[int]:
    scan = run("pgrep", "-u", str(os.getuid()), "-x", "squeekboard")
    if scan.returncode not in (0, 1):
        raise TrialError("Could not query keyboard processes")
    found: list[int] = []
    for value in scan.stdout.splitlines():
        if not value.isdigit():
            raise TrialError("Invalid keyboard PID listing")
        pid = int(value)
        try:
            exe = Path(os.readlink("/proc/" + str(pid) + "/exe"))
        except OSError:
            continue
        if exe != Path("/usr/bin/squeekboard"):
            raise TrialError(f"Unexpected squeekboard instance at PID {pid}: {exe}")
        found.append(pid)
    return found


def candidate_pids(path: Path) -> list[int]:
    """Enumerate only this trial's exact ELF; never target other processes."""
    expected = str(path)
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            link = os.readlink(entry / "exe")
        except (OSError, PermissionError):
            continue
        if link in (expected, expected + " (deleted)"):
            found.append(int(entry.name))
    return found


def orphan_trial_keyboard_pids() -> list[int]:
    """Refuse a second keyboard even if old user units/timers are inactive.

    A stalled C2 or C3 candidate might outlive its systemd trial service.
    Only inspect /proc metadata for own-user processes; never kill any here.
    """
    trial_roots = (
        Path.home() / ".cache/a-clockwork-plex/osk-overlay-trials",
        ROOT,
    )
    candidates = {"squeekboard-overlay-arm64", CANDIDATE_FILENAME}
    found: list[int] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            exe = os.readlink(proc / "exe").removesuffix(" (deleted)")
            path = Path(exe)
        except (OSError, PermissionError, ValueError):
            continue
        if path.name in candidates and any(path.is_relative_to(r) for r in trial_roots):
            found.append(int(proc.name))
    return sorted(found)


def check_baseline() -> tuple[int, dict[str, str]]:
    if os.geteuid() == 0 or platform.machine().lower() != "aarch64":
        raise TrialError("Use ordinary user on the commissioned ARM64 Pi (never sudo)")
    original = Path("/usr/bin/squeekboard")
    inspector = load_inspector()
    if inspector.hashlib.sha256(original.read_bytes()).hexdigest() != EXPECTED_VENDOR_SHA256:
        raise TrialError("Original keyboard hash does not match accepted baseline")
    env = session_environment()
    if run("systemctl", "--user", "show-environment").returncode != 0:
        raise TrialError("User systemd manager is not accessible")
    pids = vendor_pids()
    if len(pids) != 1:
        raise TrialError(f"Expected one stock Squeekboard; found {pids}")
    return pids[0], env


def unit_active(name: str) -> bool:
    return run("systemctl", "--user", "is-active", "--quiet", name).returncode == 0


def verify_candidate(path: Path) -> None:
    import hashlib
    if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_CANDIDATE_SHA256:
        raise TrialError("Candidate executable missing or hash mismatch")


def prepare(archive: Path, *, modify: bool) -> tuple[int, dict[str, str], Path | None]:
    # Baseline identity and source/candidate hashes must all be checked before
    # creating trial files, arming rescue, or terminating the vendor keyboard.
    pid, env = check_baseline()
    load_inspector().inspect(archive)  # checks exact C3 ZIP + Pi ABI
    for unit in (TRIAL_UNIT + ".service", ROLLBACK_UNIT + ".timer",
                 C2_TRIAL_UNIT + ".service", C2_ROLLBACK_UNIT + ".timer"):
        if unit_active(unit):
            raise TrialError("Existing C2/C3 keyboard trial/rescue active: " + unit)
    if orphan_trial_keyboard_pids():
        raise TrialError("Orphan C2/C3 trial keyboard process detected; refusing overlap")
    trial_env = candidate_style_environment()
    if not modify:
        return pid, env, None
    if ROOT.is_symlink():
        raise TrialError("C3 trial root symlink refused")
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (ROOT.is_symlink() or ROOT.stat().st_uid != os.getuid()
            or (ROOT.stat().st_mode & 0o777) != 0o700):
        raise TrialError("C3 trial root owner/path/mode changed")
    location = Path(tempfile.mkdtemp(prefix="trial-", dir=ROOT))
    location.chmod(0o700)
    inspector = load_inspector()
    data = inspector.checked_archive(archive)[CANDIDATE_FILENAME]
    candidate = location / CANDIDATE_FILENAME
    candidate.write_bytes(data)
    candidate.chmod(0o700)
    verify_candidate(candidate)
    state = {
        "schema": 3,
        "stock_pid": pid,
        "candidate": str(candidate),
        "env": env,
        "trial_env": trial_env,
        "stock_unit": "acp-squeekboard-c3-stock-" +
                      location.name.replace("trial-", ""),
        "created_at": time.time(),
    }
    (location / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )
    (location / "state.json").chmod(0o600)
    return pid, env, location / "state.json"



def read_state(path: Path, *, require_candidate: bool = True) -> dict:
    if path.is_symlink() or path.name != "state.json":
        raise TrialError("C3 trial state path invalid")
    path = path.resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.parent.name.startswith("trial-"):
        raise TrialError("C3 trial state outside private root")
    if path.stat().st_uid != os.getuid() or (path.stat().st_mode & 0o777) != 0o600:
        raise TrialError("C3 trial state permissions/owner invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != 3 or not isinstance(value.get("env"), dict):
        raise TrialError("Unknown C3 state schema")
    if not isinstance(value.get("stock_pid"), int) or value["stock_pid"] <= 0:
        raise TrialError("Invalid stored stock keyboard PID")
    # Stock restoration is independent of the CSS stage, the currently
    # working Wayland socket, and the current session environment. Inspect
    # ONLY the exact stored allowlisted values; do not fail before trying to
    # relaunch vendor sbtest merely because the keyboard has vanished.
    runtime = Path("/run/user") / str(os.getuid())
    expected_stock_env = {
        "XDG_RUNTIME_DIR": str(runtime),
        "WAYLAND_DISPLAY": "wayland-0",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
        "XDG_SESSION_TYPE": "wayland",
        "HOME": str(Path.home()),
    }
    if value.get("env") != expected_stock_env:
        raise TrialError("Unexpected stored stock-only restore environment")
    # Recovery must succeed even if the separate CSS stage has disappeared.
    # Thus: compare ONLY fixed strings, never re-read staged CSS in --restore.
    style = load_c3_stage()
    layout = load_compact_number_stage()
    checker = load_theme_validator()
    values = {
        "SQUEEKBOARD_KEYBOARDSDIR": str(layout.ROOT / "keyboards"),
        "XDG_CONFIG_HOME": str(checker.generator().DEST / "themes" / "classic_dark"),
        "G_RESOURCE_OVERLAYS": style.RESOURCE_PREFIX + "=" + str(style.ROOT),
        "ACP_SQUEEKBOARD_CSS_DIR": str(style.ROOT),
    }
    if value.get("trial_env") != values:
        raise TrialError("Invalid C3 trial-only environment")
    candidate = Path(value.get("candidate", ""))
    if candidate != path.parent / CANDIDATE_FILENAME:
        raise TrialError("Candidate outside this trial directory")
    if require_candidate:
        verify_candidate(candidate)
    if value.get("stock_unit") != (
        "acp-squeekboard-c3-stock-" + path.parent.name.replace("trial-", "")
    ):
        raise TrialError("Unexpected stock rescue unit")
    return value



def unit_environment(env: dict[str, str]) -> list[str]:
    return ["--setenv=" + key + "=" + value for key, value in sorted(env.items())]


def restore_stock(state_path: Path, *, stop_trial: bool) -> None:
    # Never depend on the experimental binary still existing on disk.
    state = read_state(state_path, require_candidate=False)
    candidate = Path(state["candidate"])
    if stop_trial:
        # IMPORTANT: stop the worker OUTSIDE the restoration lock. If the
        # worker is in its own finally/restore path, taking the lock first
        # would deadlock systemctl stop against the worker waiting for it.
        stop = run("systemctl", "--user", "stop", TRIAL_UNIT + ".service", timeout=12)
        if stop.returncode != 0 and unit_active(TRIAL_UNIT + ".service"):
            raise TrialError("Trial service did not stop; preserving single-OSK safety")
    # Timer and worker can both attempt restoration. Serialize ONLY restore.
    with (state_path.parent / "restore.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        # systemd transient worker must use KillMode=control-group, so
        # stopping it terminates its experimental child too. Check instead
        # of assuming this. Never spawn stock while a candidate still exists.
        for _ in range(20):
            active = candidate_pids(candidate)
            if not active:
                break
            time.sleep(0.25)
        else:
            raise TrialError("Experimental keyboard still running; refusing to overlap with stock")
        pids = vendor_pids()
        if len(pids) > 1:
            raise TrialError("More than one vendor keyboard; refusing extra launch")
        if len(pids) == 1:
            print("Original Squeekboard is already running; nothing to restore.", flush=True)
            return
        print("Restoring vendor /usr/bin/sbtest in an independent user unit...", flush=True)
        command = [
            "systemd-run", "--user", "--collect", "--no-block",
            "--unit=" + state["stock_unit"],
            *unit_environment(state["env"]), "/usr/bin/sbtest",
        ]
        result = run(*command, timeout=12)
        if result.returncode != 0:
            raise TrialError("Could not start vendor OSK user service: " + result.stderr.strip())
        for _ in range(40):
            time.sleep(0.25)
            if len(vendor_pids()) == 1 and not candidate_pids(candidate):
                print("Original Squeekboard restored.", flush=True)
                return
        raise TrialError("Restore service launched but original keyboard not detected")


def worker(state_path: Path) -> None:
    state = read_state(state_path)
    if not unit_active(ROLLBACK_UNIT + ".timer"):
        raise TrialError("Independent restore timer not armed; refusing to stop keyboard")
    pids = vendor_pids()
    if pids != [state["stock_pid"]]:
        raise TrialError("Stock OSK identity changed; refusing to stop keyboard")
    candidate_process: subprocess.Popen | None = None
    try:
        os.kill(state["stock_pid"], signal.SIGTERM)
        for _ in range(40):
            if not vendor_pids():
                break
            time.sleep(0.25)
        else:
            raise TrialError("Original keyboard did not exit; refusing candidate launch")
        log = (state_path.parent / "candidate.log").open("ab")
        environment = dict(os.environ, **state["env"], **state.get("trial_env", {}))
        try:
            candidate_process = subprocess.Popen(
                [state["candidate"]], env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
            )
        finally:
            log.close()
        print(f"C3 hot-CSS candidate PID {candidate_process.pid}; {TRIAL_SECONDS}s trial window.", flush=True)
        until = time.monotonic() + TRIAL_SECONDS
        while time.monotonic() < until and candidate_process.poll() is None:
            time.sleep(0.5)
        print("Timed trial ending or candidate exited; restoring stock OSK.", flush=True)
    finally:
        if candidate_process is not None and candidate_process.poll() is None:
            candidate_process.terminate()
            try:
                candidate_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                candidate_process.kill()
                candidate_process.wait(timeout=3)
        restore_stock(state_path, stop_trial=False)


def start(archive: Path) -> None:
    _, env, state_path = prepare(archive, modify=True)
    assert state_path is not None
    script = str(Path(__file__).resolve())
    # Rescue timer is independent of trial service AND SSH.
    restore_command = [
        "systemd-run", "--user", "--collect", "--unit=" + ROLLBACK_UNIT,
        "--on-active=" + str(ROLLBACK_SECONDS) + "s",
        *unit_environment(env), sys.executable, script, "--restore", str(state_path),
    ]
    timer = run(*restore_command)
    if timer.returncode != 0 or not unit_active(ROLLBACK_UNIT + ".timer"):
        raise TrialError("Could not arm/verify independent rollback timer: " + timer.stderr.strip())
    trial_command = [
        "systemd-run", "--user", "--collect", "--no-block",
        "--unit=" + TRIAL_UNIT,
        "--property=KillMode=control-group",
        "--property=TimeoutStopSec=5s",
        *unit_environment(env), sys.executable, script, "--worker", str(state_path),
    ]
    started = run(*trial_command)
    if started.returncode != 0:
        print("Trial service did not start; stock OSK remains running.", file=sys.stderr)
        restore_stock(state_path, stop_trial=False)
        raise TrialError(started.stderr.strip())
    print("C3 trial requested. Independent stock OSK restore timer is ARMED.", flush=True)
    print(f"Automatic end: {TRIAL_SECONDS}s; independent rescue: {ROLLBACK_SECONDS}s.", flush=True)
    print(f"Log: journalctl --user -u {TRIAL_UNIT}.service -n 60 --no-pager", flush=True)
    print(f"Early restore: systemctl --user start {ROLLBACK_UNIT}.service", flush=True)
    print("DO NOT kill services, edit autostart, or run two keyboards at once.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", type=Path, metavar="C3_ZIP")
    group.add_argument("--start", type=Path, metavar="C3_ZIP")
    group.add_argument("--worker", type=Path, metavar="STATE", help=argparse.SUPPRESS)
    group.add_argument("--restore", type=Path, metavar="STATE", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.plan:
            prepare(args.plan, modify=False)
            print("C3 PLAN PASS: stock OSK and verified C3 artifact present.")
            print("UK compact keyboard, all 23 palettes and private Classic Dark CSS validated.")
            print(f"Window: {TRIAL_SECONDS}s; INDEPENDENT restore: {ROLLBACK_SECONDS}s.")
            print("No keyboard, service, system configuration or files changed.")
        elif args.start:
            start(args.start)
        elif args.worker:
            worker(args.worker)
        else:
            restore_stock(args.restore, stop_trial=True)
        return 0
    except (TrialError, OSError, subprocess.TimeoutExpired,
            json.JSONDecodeError, ValueError) as exc:
        print("ACP C3 hot-CSS keyboard trial: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
