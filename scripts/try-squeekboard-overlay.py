#!/usr/bin/env python3
"""Bounded, user-scoped test of Squeekboard OVERLAY on the commissioned Pi.

--plan: verifies vendor keyboard and artifact, changes nothing.
--start: arms an independent systemd-user rollback timer BEFORE stopping stock OSK.
--worker / --restore: internal transient-unit entry points.
Does not install packages, write system config or affect ACP/Headless/audio.
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
EXPECTED_CANDIDATE_SHA256 = "11e1c8ef40674503cb9a0b82a96086d8bbca319c99943b9061bc5629118166a6"
TRIAL_SECONDS = 180
ROLLBACK_SECONDS = 240
TRIAL_UNIT = "acp-squeekboard-overlay-trial"
ROLLBACK_UNIT = "acp-squeekboard-overlay-restore"
ROOT = Path.home() / ".cache" / "a-clockwork-plex" / "osk-overlay-trials"


class TrialError(Exception):
    pass


def load_inspector():
    path = Path(__file__).resolve().with_name("inspect-squeekboard-overlay-artifact.py")
    spec = importlib.util.spec_from_file_location("acp_overlay_checker", path)
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


def load_resource_probe():
    path = Path(__file__).resolve().with_name("probe-squeekboard-resource-overlay.py")
    spec = importlib.util.spec_from_file_location("acp_c2_resource_probe", path)
    if not spec or not spec.loader:
        raise TrialError("GLib resource overlay inspector is unavailable")
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


def verified_resource_override(theme: str) -> str:
    """Prove all private CSS bytes before the trial's timer/stock handover.

    This is a *candidate-only* environment override, never a stock OSK change.
    No resource files are created or modified by the trial controller.
    """
    probe = load_resource_probe()
    try:
        expected = probe.samples()
        if theme not in expected:
            raise TrialError("Unknown ACP Squeekboard resource palette")
        probe.verify_stage(expected)
        return probe.trial_override(theme)
    except (probe.OverlayError, OSError, ValueError) as exc:
        raise TrialError("GLib resource overlay stage verification failed: " + str(exc)) from exc


def candidate_style_environment(
    theme: str, *, resource_overlay: bool = False,
    compact_number: bool = False,
) -> dict[str, str]:
    """Verify pinned layouts and theme; pass overrides ONLY to candidate ELF.

    The stock-restoration unit receives the original desktop environment and
    must never receive XDG, GB-keymap or G_RESOURCE_OVERLAYS trial overrides.
    """
    if compact_number and not resource_overlay:
        raise TrialError("Compact numeric layout requires resource-overlay theme")
    checker = load_theme_validator()
    gen = checker.generator()
    if theme not in gen.styles():
        raise TrialError("Unknown ACP Squeekboard theme: " + theme)
    try:
        checker.validate()
    except checker.CheckError as exc:
        raise TrialError("UK/theme stage verification failed: " + str(exc)) from exc
    root = gen.DEST.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise TrialError("Unsafe Stage C2 root")
    result = {
        "SQUEEKBOARD_KEYBOARDSDIR": str(root / "keyboards"),
        "XDG_CONFIG_HOME": str(root / "themes" / theme),
    }
    if resource_overlay:
        result["G_RESOURCE_OVERLAYS"] = verified_resource_override(theme)
    if compact_number:
        result["SQUEEKBOARD_KEYBOARDSDIR"] = verified_compact_keyboard_dir()
    return result


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
    module = load_inspector()
    if not path.is_file() or module.hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_CANDIDATE_SHA256:
        raise TrialError("Candidate executable missing or hash mismatch")


def prepare(
    archive: Path, *, modify: bool, uk_theme: str | None = None,
    resource_overlay: bool = False, compact_number: bool = False,
) -> tuple[int, dict[str, str], Path | None]:
    if resource_overlay and not uk_theme:
        raise TrialError("Resource overlay requires --uk-theme")
    if compact_number and (not resource_overlay or not uk_theme):
        raise TrialError("Compact number requires both --uk-theme and --resource-overlay")
    pid, env = check_baseline()
    load_inspector().inspect(archive)
    if unit_active(TRIAL_UNIT + ".service") or unit_active(ROLLBACK_UNIT + ".timer"):
        raise TrialError("A trial or rescue timer is already running; refusing to overlap")
    if compact_number:
        trial_env = candidate_style_environment(
            uk_theme, resource_overlay=True, compact_number=True,
        )
    elif resource_overlay:
        trial_env = candidate_style_environment(uk_theme, resource_overlay=True)
    else:
        trial_env = candidate_style_environment(uk_theme) if uk_theme else {}
    if not modify:
        return pid, env, None
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    location = Path(tempfile.mkdtemp(prefix="trial-", dir=ROOT))
    location.chmod(0o700)
    inspector = load_inspector()
    data = inspector.checked_files(archive)["squeekboard-overlay-arm64"]
    candidate = location / "squeekboard-overlay-arm64"
    candidate.write_bytes(data)
    candidate.chmod(0o700)
    verify_candidate(candidate)
    state = {
        "schema": 1,
        "stock_pid": pid,
        "candidate": str(candidate),
        "env": env,
        "trial_env": trial_env,
        "stock_unit": "acp-squeekboard-stock-" + location.name.replace("trial-", ""),
        "created_at": time.time(),
    }
    (location / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (location / "state.json").chmod(0o600)
    return pid, env, location / "state.json"


def read_state(path: Path, *, require_candidate: bool = True) -> dict:
    path = path.resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.name != "state.json":
        raise TrialError("Unexpected trial state location")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != 1 or not isinstance(value.get("env"), dict):
        raise TrialError("Invalid trial state")
    overrides = value.get("trial_env", {})
    old_keys = {"SQUEEKBOARD_KEYBOARDSDIR", "XDG_CONFIG_HOME"}
    new_keys = old_keys | {"G_RESOURCE_OVERLAYS"}
    if not isinstance(overrides, dict) or set(overrides) not in (
        set(), old_keys, new_keys
    ):
        raise TrialError("Invalid candidate-only keyboard theme environment")
    if overrides:
        checker = load_theme_validator()
        gen = checker.generator()
        root = gen.DEST.resolve()
        keyboard = str(root / "keyboards")
        # State validation must work for both pre-C2 accepted layouts and the
        # new compact alternative. No reading or verifying the optional compact
        # files here: the independent stock restoration must always be possible.
        compact = load_compact_number_stage()
        compact_keyboard = str(compact.ROOT / "keyboards")
        palettes = {str(root / "themes" / name) for name in gen.styles()}
        selected_keyboard = overrides.get("SQUEEKBOARD_KEYBOARDSDIR")
        if selected_keyboard not in (keyboard, compact_keyboard) or (
            overrides.get("XDG_CONFIG_HOME") not in palettes
        ):
            raise TrialError("Candidate keyboard paths are outside the pinned stage")
        if selected_keyboard == compact_keyboard and "G_RESOURCE_OVERLAYS" not in overrides:
            raise TrialError("Compact layout must retain the candidate-only CSS resource")
        if "G_RESOURCE_OVERLAYS" in overrides:
            # The independent rescue must remain possible even when test CSS
            # disappears; validate only a fixed allowlisted string here, never
            # read private files from the rescue/restore path.
            probe = load_resource_probe()
            allowed = {
                probe.RESOURCE_PREFIX + "=" + str(probe.ROOT / "palettes" / name)
                for name in gen.styles()
            }
            if overrides["G_RESOURCE_OVERLAYS"] not in allowed:
                raise TrialError("Candidate resource overlay is outside the pinned stage")
            selected = overrides["XDG_CONFIG_HOME"]
            selected_name = Path(selected).name
            if overrides["G_RESOURCE_OVERLAYS"] != (
                probe.RESOURCE_PREFIX + "=" +
                str(probe.ROOT / "palettes" / selected_name)
            ):
                raise TrialError("Resource overlay and GTK palette differ")
    candidate = Path(value.get("candidate", ""))
    if candidate != path.parent / "squeekboard-overlay-arm64":
        raise TrialError("Candidate must be in same isolated trial folder")
    if require_candidate:
        verify_candidate(candidate)
    if value.get("stock_unit") != "acp-squeekboard-stock-" + path.parent.name.replace("trial-", ""):
        raise TrialError("Unexpected stock restore service name")
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
        print(f"Overlay candidate PID {candidate_process.pid}; {TRIAL_SECONDS}s trial window.", flush=True)
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


def start(
    archive: Path, *, uk_theme: str | None = None,
    resource_overlay: bool = False, compact_number: bool = False,
) -> None:
    _, env, state_path = prepare(
        archive, modify=True, uk_theme=uk_theme,
        resource_overlay=resource_overlay, compact_number=compact_number,
    )
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
    print("Trial service requested. Independent backup restore timer is ARMED.", flush=True)
    print(f"Automatic end: {TRIAL_SECONDS}s; independent rescue: {ROLLBACK_SECONDS}s.", flush=True)
    print(f"Log: journalctl --user -u {TRIAL_UNIT}.service -n 60 --no-pager", flush=True)
    print(f"Early restore: systemctl --user start {ROLLBACK_UNIT}.service", flush=True)
    print("DO NOT kill services, edit autostart, or run two keyboards at once.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", type=Path, metavar="ZIP")
    group.add_argument("--start", type=Path, metavar="ZIP")
    group.add_argument("--worker", type=Path, metavar="STATE", help=argparse.SUPPRESS)
    group.add_argument("--restore", type=Path, metavar="STATE", help=argparse.SUPPRESS)
    parser.add_argument(
        "--uk-theme", metavar="PALETTE",
        help="Use verified private British YAML and this ACP palette ONLY in experimental OSK",
    )
    parser.add_argument(
        "--resource-overlay", action="store_true",
        help="Opt-in verified private GResource CSS ONLY for experimental OSK; "
             "requires --uk-theme and --plan/--start",
    )
    parser.add_argument(
        "--compact-number", action="store_true",
        help="Use separately staged compact numeric GB layout ONLY in experimental OSK; "
             "requires --uk-theme, --resource-overlay, and --plan/--start",
    )
    args = parser.parse_args()
    try:
        if args.uk_theme and not (args.plan or args.start):
            raise TrialError("--uk-theme is only allowed with --plan or --start")
        if args.resource_overlay and (not args.uk_theme or not (args.plan or args.start)):
            raise TrialError("--resource-overlay requires --uk-theme and --plan/--start")
        if args.compact_number and (
            not args.resource_overlay or not args.uk_theme or not (args.plan or args.start)
        ):
            raise TrialError("--compact-number requires --uk-theme, --resource-overlay and --plan/--start")
        if args.plan:
            prepare(
                args.plan, modify=False, uk_theme=args.uk_theme,
                resource_overlay=args.resource_overlay,
                compact_number=args.compact_number,
            )
            print("PLAN PASS: stock OSK and verified artifact present; user timer manager available.")
            print(f"Test: {TRIAL_SECONDS}s; separate systemd rescue timer: {ROLLBACK_SECONDS}s.")
            print("No keyboard/process/configuration changes made.")
            if args.uk_theme:
                print("UK keyboards and ACP palette verified: " + args.uk_theme)
                print("Only the experimental OSK would receive override paths.")
            if args.resource_overlay:
                print("PRIVATE GLib resource CSS: VERIFIED (candidate only; no system or stock changes).")
            if args.compact_number:
                print("COMPACT NUMERIC PRIVATE STAGE: VERIFIED (candidate only; accepted v1 untouched).")
        elif args.start:
            start(
                args.start, uk_theme=args.uk_theme,
                resource_overlay=args.resource_overlay,
                compact_number=args.compact_number,
            )
        elif args.worker:
            worker(args.worker)
        else:
            restore_stock(args.restore, stop_trial=True)
        return 0
    except (TrialError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print("ACP keyboard overlay trial: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
