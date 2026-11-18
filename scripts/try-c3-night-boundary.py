#!/usr/bin/env python3
"""Guard a single attended C3 schedule-boundary experiment.

--plan: read-only eligibility/time window check.
--arm: verify the original 22:00-07:00 schedule, arm an INDEPENDENT
       7-minute user-systemd restore timer, and only then temporarily change
       the two night schedule clock fields via revisioned ACP settings API.
--restore: user-timer/manual rollback through the SAME revisioned settings API.

Never launches or controls a keyboard, changes night styling, creates a CSS
writer, or touches global GTK, alarms, audio, Headless or NFC.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = 'http://127.0.0.1:8088'
UK = ZoneInfo('Europe/London')
BASELINE = ('22:00', '07:00')
RESTORE_SECONDS = 420
TIMER = 'acp-c3-schedule-boundary-restore'
STATE_DIR = Path.home() / '.cache/a-clockwork-plex/c3-schedule-boundary'
STATE = STATE_DIR / 'state.json'
ALLOWED_FIELDS = frozenset({'schema', 'baseline', 'temporary', 'created_at'})


class BoundaryError(Exception):
    pass


def read_api(endpoint: str) -> dict:
    with urlopen(API + endpoint, timeout=8) as response:
        value = json.load(response)
    if not isinstance(value, dict) or value.get('ok') is not True:
        raise BoundaryError('ACP API did not supply an affirmative response')
    return value


def submit_times(snapshot: dict, pair: tuple[str, str]) -> None:
    if type(snapshot.get('revision')) is not str or not isinstance(snapshot.get('settings'), dict):
        raise BoundaryError('Versioned Settings snapshot is unavailable')
    settings = json.loads(json.dumps(snapshot['settings']))
    if not isinstance(settings.get('display'), dict):
        raise BoundaryError('Settings display domain is unavailable')
    settings['display']['night_dim_start'], settings['display']['night_dim_end'] = pair
    data = json.dumps({'revision': snapshot['revision'], 'settings': settings},
                      separators=(',', ':')).encode('utf-8')
    request = Request(API + '/api/settings', data=data,
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=12) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise BoundaryError(f'ACP rejected settings transaction (HTTP {exc.code}); nothing else should be edited') from exc
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise BoundaryError('ACP did not confirm the settings transaction')


def displayed_times(snapshot: dict) -> tuple[str, str]:
    try:
        d = snapshot['settings']['display']
        values = (d['night_dim_start'], d['night_dim_end'])
        if not all(isinstance(x, str) and len(x) == 5 for x in values):
            raise ValueError('invalid clock')
        return values
    except (TypeError, KeyError, ValueError) as exc:
        raise BoundaryError('Night schedule fields absent or invalid') from exc


def validate_baseline(snapshot: dict) -> None:
    d = snapshot.get('settings', {}).get('display', {})
    if (displayed_times(snapshot) != BASELINE
        or d.get('night_dim_enabled') is not True
        or d.get('daytime_theme') != 'classic_dark'
        or d.get('night_dim_style') != 'classic'
        or d.get('night_dim_active_style') != 'same'):
        raise BoundaryError('Current schedule/theme differs from user-accepted baseline; refusing changes')


def window(now: datetime) -> tuple[datetime, datetime]:
    now = now.astimezone(UK)
    if not (7 <= now.hour < 21) or (now.hour == 7 and now.minute < 15) or (now.hour == 20 and now.minute > 40):
        raise BoundaryError('Test only in safe daytime window 07:15-20:40 UK local, away from real schedule')
    start = now.replace(second=0, microsecond=0) + timedelta(minutes=4)
    end = start + timedelta(minutes=1)
    if end.hour >= 22 or end.date() != now.date():
        raise BoundaryError('Temporary schedule would approach real night boundary')
    return start, end


def timer_active() -> bool:
    return subprocess.run(('systemctl', '--user', 'is-active', '--quiet', TIMER + '.timer'),
                          check=False, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=8).returncode == 0


def check_remote_safety() -> dict:
    alarm = read_api('/api/alarms/active')
    if alarm.get('active') is not None or alarm.get('screen_required') is not False or alarm.get('snoozed_until') is not None:
        raise BoundaryError('An alarm is active/requested/snoozed; refusing schedule trial')
    sync = read_api('/api/osk/c3/theme-sync/status')
    if sync.get('enabled') is not False:
        raise BoundaryError('C3 theme-sync trial is already enabled')
    return read_api('/api/settings')


def save_state(start: str, end: str) -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATE_DIR.is_symlink() or STATE_DIR.stat().st_uid != os.getuid() or stat.S_IMODE(STATE_DIR.stat().st_mode) != 0o700:
        raise BoundaryError('Unsafe schedule-guard directory')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(STATE, flags, 0o600)
    except FileExistsError as exc:
        raise BoundaryError('An older schedule guard is still present; inspect/restore it before starting another') from exc
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'schema': 1, 'baseline': list(BASELINE),
                   'temporary': [start, end], 'created_at': time.time()}, f)
        f.flush()
        os.fsync(f.fileno())


def load_state() -> dict | None:
    if not STATE.exists() and not STATE.is_symlink():
        return None
    if STATE.is_symlink():
        raise BoundaryError('Refusing symlinked schedule guard state')
    s = STATE.stat()
    if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1:
        raise BoundaryError('Schedule-guard state permissions/ownership invalid')
    data = json.loads(STATE.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or set(data) != ALLOWED_FIELDS
        or data['schema'] != 1 or data['baseline'] != list(BASELINE)
        or not isinstance(data['temporary'], list) or len(data['temporary']) != 2):
        raise BoundaryError('Schedule-guard state content invalid')
    return data


def restore() -> None:
    state = load_state()
    if state is None:
        print('No outstanding C3 schedule-guard state; nothing to restore.')
        return
    target = tuple(state['temporary'])
    for attempt in range(6):
        try:
            current = read_api('/api/settings')
            times = displayed_times(current)
            if times == BASELINE:
                print('C3 night schedule already restored: 22:00-07:00.')
                STATE.unlink()
                return
            if times != target:
                raise BoundaryError(f'Schedule changed to {times!r} by another party; refusing to overwrite it')
            submit_times(current, BASELINE)
            if displayed_times(read_api('/api/settings')) != BASELINE:
                raise BoundaryError('Restore response was not persisted')
            STATE.unlink()
            print('C3 night schedule RESTORED to 22:00-07:00 via revisioned ACP Settings.')
            return
        except (OSError, URLError, BoundaryError) as exc:
            if attempt == 5:
                raise BoundaryError('Automatic schedule restore FAILED: ' + str(exc) +
                                    '; manually restore 22:00-07:00 in ACP Settings') from exc
            time.sleep(5)


def arm(now: datetime) -> None:
    if os.geteuid() == 0:
        raise BoundaryError('Run as the Pi desktop user, never sudo/root')
    if load_state() is not None or timer_active():
        raise BoundaryError('Another schedule guard/restore is already armed')
    settings = check_remote_safety()
    validate_baseline(settings)
    start, end = window(now)
    save_state(start.strftime('%H:%M'), end.strftime('%H:%M'))
    script = str(Path(__file__).resolve())
    command = ('systemd-run', '--user', '--collect', '--unit=' + TIMER,
               '--on-active=' + str(RESTORE_SECONDS) + 's', sys.executable, script, '--restore')
    try:
        run = subprocess.run(command, text=True, capture_output=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BoundaryError('Could not arm schedule restore; original schedule remains unchanged') from exc
    if run.returncode != 0 or not timer_active():
        raise BoundaryError('Independent schedule restore timer not armed; original schedule remains unchanged')
    try:
        submit_times(settings, (start.strftime('%H:%M'), end.strftime('%H:%M')))
        current = read_api('/api/settings')
        if displayed_times(current) != (start.strftime('%H:%M'), end.strftime('%H:%M')):
            raise BoundaryError('Temporary start/end not confirmed persisted')
    except Exception:
        print('Temporary schedule was not confirmed; attempting immediate restore.', file=sys.stderr)
        restore()
        raise
    print('GUARDED C3 NIGHT SCHEDULE ARMED via revisioned Settings API')
    print('Temporary night START:', start.strftime('%H:%M'), 'BST/GMT local')
    print('Temporary night END:  ', end.strftime('%H:%M'), 'BST/GMT local')
    print('Suggested C3 trial start:', (start - timedelta(seconds=45)).strftime('%H:%M:%S'), 'local.')
    print('Independent schedule restoration: 7 minutes after arm (not the keyboard rescue).')
    print('To restore schedule early: python3 scripts/try-c3-night-boundary.py --restore')
    print('Hard-refresh ACP Settings now to load the temporary schedule BEFORE Plexamp takes focus.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan', action='store_true')
    group.add_argument('--arm', action='store_true')
    group.add_argument('--restore', action='store_true', help='Also used by independent restore timer')
    args = parser.parse_args()
    try:
        if args.restore:
            restore()
        elif args.plan:
            if os.geteuid() == 0:
                raise BoundaryError('Run as the Pi desktop user, never root')
            if load_state() is not None or timer_active():
                raise BoundaryError('A C3 schedule guard/timer is already present')
            validate_baseline(check_remote_safety())
            start, end = window(datetime.now(UK))
            print('READ-ONLY C3 NIGHT SCHEDULE PLAN: PASS')
            print('Original: 22:00-07:00; test:', start.strftime('%H:%M'), '-', end.strftime('%H:%M'))
            print('Guard: independent 7-minute restore armed BEFORE modifying ACP Settings')
            print('C3 keyboard trial remains separate, 180s with independent 240s stock rescue')
            print('No settings, keyboard, CSS, services or timers changed.')
        else:
            arm(datetime.now(UK))
        return 0
    except (BoundaryError, OSError, URLError, ValueError,
            subprocess.TimeoutExpired) as exc:
        print('C3 schedule boundary guard: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
