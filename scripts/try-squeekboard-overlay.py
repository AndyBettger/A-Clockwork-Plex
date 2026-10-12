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


def prepare(archive: Path, *, modify: bool) -> tuple[int, dict[str, str], Path | None]:
    pid, env = check_baseline()
    load_inspector().inspect(archive)
    if unit_active(TRIAL_UNIT + ".service") or unit_active(ROLLBACK_UNIT + ".timer"):
        raise TrialError("A trial or rescue timer is already running; refusing to overlap")
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
    # Recovery must not depend on the experimental candidate still existing.
    state = read_state(state_path, require_candidate=False)
    # Timer and worker can both attempt restore; lock prevents duplicate OSKs.
    with (state_path.parent / "restore.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if stop_trial:
            run("systemctl", "--user", "stop", TRIAL_UNIT + ".service", timeout=12)
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
            if len(vendor_pids()) == 1:
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
        environment = dict(os.environ, **state["env"])
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
    args = parser.parse_args()
    try:
        if args.plan:
            prepare(args.plan, modify=False)
            print("PLAN PASS: stock OSK and verified artifact present; user timer manager available.")
            print(f"Test: {TRIAL_SECONDS}s; separate systemd rescue timer: {ROLLBACK_SECONDS}s.")
            print("No keyboard/process/configuration changes made.")
        elif args.start:
            start(args.start)
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
