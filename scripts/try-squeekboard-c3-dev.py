#!/usr/bin/env python3
"""Opt-in persistent-for-this-login C3 keyboard development session.

No keyboard package install, desktop autostart changes, 180s deadline or
permanent enable. --start temporarily replaces the single stock Squeekboard
with the pinned C3 hot-CSS candidate in a supervised user-systemd service.
--stop returns to /usr/bin/sbtest, and candidate exit also restores stock.
Normal Pi login/reboot uses the original stock Squeekboard as before.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

UNIT = 'acp-squeekboard-c3-dev'
STATE_FILE = Path.home() / '.cache/a-clockwork-plex/osk-c3-hot-css-trials/dev-active.json'


class DevError(Exception):
    pass


def load_trial():
    path = Path(__file__).with_name('try-squeekboard-hot-css.py')
    spec = importlib.util.spec_from_file_location('acp_c3_dev_verified_trial', path)
    if not spec or not spec.loader:
        raise DevError('C3 verified trial helper unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pointer_state() -> Path | None:
    if not STATE_FILE.exists() and not STATE_FILE.is_symlink():
        return None
    if STATE_FILE.is_symlink():
        raise DevError('Refusing symlinked C3 development pointer')
    meta = STATE_FILE.stat()
    if (meta.st_uid != os.getuid() or not stat.S_ISREG(meta.st_mode)
            or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1):
        raise DevError('C3 development pointer owner or permissions changed')
    obj = json.loads(STATE_FILE.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or set(obj) != {'state'} or not isinstance(obj['state'], str):
        raise DevError('C3 development pointer has an invalid schema')
    return Path(obj['state'])


def active_state(trial=None, unit_check=None) -> Path | None:
    """Return exact opted-in candidate state; used read-only by theme bridge."""
    trial = trial or load_trial()
    checked = unit_check or trial.unit_active
    if not checked(UNIT + '.service'): 
        return None
    if any(checked(name) for name in (
        trial.TRIAL_UNIT + '.service', trial.ROLLBACK_UNIT + '.timer',
        trial.C2_TRIAL_UNIT + '.service', trial.C2_ROLLBACK_UNIT + '.timer'
    )):
        return None
    path = pointer_state()
    if path is None:
        return None
    state = trial.read_state(path)
    if (state.get('theme_sync') is not True
            or trial.vendor_pids()
            or len(trial.candidate_pids(Path(state['candidate']))) != 1):
        return None
    return path


def save_pointer(path: Path, trial) -> None:
    root = trial.ROOT
    if root.is_symlink() or root.stat().st_uid != os.getuid() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise DevError('C3 private trial root is unsafe')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(STATE_FILE, flags, 0o600)
    except FileExistsError as exc:
        raise DevError('Previous dev state exists: run --status or --stop first') from exc
    with os.fdopen(fd, 'w', encoding='utf-8') as target:
        json.dump({'state': str(path)}, target)
        target.flush()
        os.fsync(target.fileno())


def remove_pointer(path: Path) -> None:
    try:
        if pointer_state() == path:
            STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def start(archive: Path) -> None:
    trial = load_trial()
    if trial.unit_active(UNIT + '.service') or pointer_state() is not None:
        raise DevError('C3 dev session already running or awaiting cleanup; run --stop')
    # Reuse the exact known-good candidate hash, source/layout/CSS checks,
    # singleton checks and private candidate layout from the 180s trial.
    _stock_pid, env, path = trial.prepare(archive, modify=True, theme_sync=True)
    assert path is not None
    save_pointer(path, trial)
    command = [
        'systemd-run', '--user', '--collect', '--no-block',
        '--unit=' + UNIT,
        '--property=KillMode=mixed',
        '--property=TimeoutStopSec=25s',
        *trial.unit_environment(env),
        sys.executable, str(Path(__file__).resolve()), '--worker', str(path)
    ]
    try:
        result = trial.run(*command, timeout=15)
        if result.returncode != 0:
            raise DevError('Could not start C3 dev service: ' + result.stderr.strip())
    except Exception:
        remove_pointer(path)
        raise
    print('C3 DEVELOPMENT SESSION REQUESTED (no 180s timeout).')
    print('No autostart changes. Browser-owned palette sync enabled ONLY while dev candidate is alive.')
    print('Stop and restore stock: python3 scripts/try-squeekboard-c3-dev.py --stop')
    print('Status: python3 scripts/try-squeekboard-c3-dev.py --status')
    print('Logs: journalctl --user -u ' + UNIT + '.service -n 40 --no-pager')


def worker(path: Path) -> None:
    trial = load_trial()
    state = trial.read_state(path)
    if pointer_state() != path:
        raise DevError('C3 pointer/state disagreement')
    if not trial.unit_active(UNIT + '.service'):
        raise DevError('C3 development service not active')
    if trial.vendor_pids() != [state['stock_pid']]:
        raise DevError('Expected original stock singleton before C3 handover')

    shutting_down = False
    def request_stop(_signum, _frame):
        nonlocal shutting_down
        shutting_down = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    candidate = None
    try:
        os.kill(state['stock_pid'], signal.SIGTERM)
        for _ in range(40):
            if not trial.vendor_pids():
                break
            time.sleep(0.25)
        else:
            raise DevError('Vendor keyboard did not exit; refusing candidate overlap')
        if shutting_down:
            return  # finally restores vendor if stopped during initial handover
        with (path.parent / 'candidate.log').open('ab') as logfile:
            candidate = subprocess.Popen(
                [state['candidate']],
                env={**os.environ, **state['env'], **state['trial_env']},
                stdin=subprocess.DEVNULL, stdout=logfile, stderr=subprocess.STDOUT)
        print('C3 development candidate PID:', candidate.pid, flush=True)
        while not shutting_down and candidate.poll() is None:
            time.sleep(0.5)
        print('C3 session stopping/candidate exited, restoring vendor keyboard.', flush=True)
    finally:
        if candidate is not None and candidate.poll() is None:
            candidate.terminate()
            try:
                candidate.wait(timeout=5)
            except subprocess.TimeoutExpired:
                candidate.kill()
                candidate.wait(timeout=3)
        try:
            trial.restore_stock(path, stop_trial=False)
        finally:
            # Leave the pointer for manual --stop if stock restore failed.
            if len(trial.vendor_pids()) == 1:
                remove_pointer(path)


def stop() -> None:
    trial = load_trial()
    path = pointer_state()
    if trial.unit_active(UNIT + '.service'):
        result = trial.run('systemctl', '--user', 'stop', UNIT + '.service', timeout=35)
        if result.returncode != 0 or trial.unit_active(UNIT + '.service'):
            raise DevError('C3 service did not stop; check journal before restoring vendor')
    if path is None:
        print('No active C3 dev pointer. Original keyboard:', trial.vendor_pids())
        return
    trial.restore_stock(path, stop_trial=False)
    remove_pointer(path)
    print('C3 development session stopped. Vendor Squeekboard restored.')


def start_at_login(archive: Path, *, wait_seconds: int = 60) -> None:
    """Desktop-login entry: wait for distro OSK, then perform the same C3 handoff.

    Labwc starts the distro keyboard independently. The session-start hook
    never edits labwc's stock keyboard entry and never launches a second OSK.
    After a reboot the old transient-service pointer can remain on disk even
    though its user unit and old candidate have gone away.
    """
    trial = load_trial()
    if trial.unit_active(UNIT + '.service'):
        print('C3 session already active; login hook has nothing to do.')
        return
    deadline = time.monotonic() + max(0, wait_seconds)
    while True:
        if trial.unit_active(UNIT + '.service'):
            return
        stock = trial.vendor_pids()
        if len(stock) > 1:
            raise DevError('Multiple vendor OSKs detected; refusing login handover')
        if len(stock) == 1:
            if trial.orphan_trial_keyboard_pids():
                raise DevError('An experimental OSK is already running; refusing overlap')
            stale = pointer_state()
            if stale is not None:
                # The only permitted stale-state cleanup is a dead dev service
                # with exactly one working stock OSK and NO trial candidate.
                trial.read_state(stale, require_candidate=False)
                remove_pointer(stale)
                print('Cleared stale C3 dev pointer left by previous login.')
            start(archive)
            return
        if time.monotonic() >= deadline:
            raise DevError('Stock OSK did not become ready within startup window; leaving desktop unchanged')
        time.sleep(1)


def status() -> None:
    trial = load_trial()
    path = pointer_state()
    enabled = active_state(trial)
    print(json.dumps({
        'service_active': trial.unit_active(UNIT + '.service'),
        'theme_sync_eligible': enabled is not None,
        'vendor_pids': trial.vendor_pids(),
        'candidate_pids': trial.candidate_pids(Path(trial.read_state(path)['candidate'])) if path else [],
        'state_present': path is not None,
        'autostart_changed': False,
    }, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument('--plan', type=Path, metavar='C3_ZIP')
    commands.add_argument('--start', type=Path, metavar='C3_ZIP')
    commands.add_argument('--startup', type=Path, metavar='C3_ZIP', help='desktop-login handoff')
    commands.add_argument('--stop', action='store_true')
    commands.add_argument('--status', action='store_true')
    commands.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise DevError('Never run C3 keyboard session with sudo/root')
        if args.plan:
            trial = load_trial()
            if pointer_state() is not None or trial.unit_active(UNIT + '.service'):
                raise DevError('Dev session already active; use --status')
            trial.prepare(args.plan, modify=False, theme_sync=True)
            print('C3 DEV PLAN PASS: verified candidate, single stock keyboard, no conflicts.')
            print('No timeout; --stop returns to stock; stock labwc autostart unchanged.')
        elif args.start:
            start(args.start)
        elif args.startup:
            start_at_login(args.startup)
        elif args.stop:
            stop()
        elif args.status:
            status()
        else:
            worker(args.worker)
        return 0
    except (DevError, OSError, ValueError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print('C3 dev session: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
