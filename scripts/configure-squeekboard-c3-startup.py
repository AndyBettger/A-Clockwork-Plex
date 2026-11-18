#!/usr/bin/env python3
"""Opt-in desktop-login startup for the C3 Squeekboard *development* session.

Writes only ~/.config/autostart/a-clockwork-plex-c3-dev.desktop.
Does not change stock Squeekboard, labwc, vendor packages, or the current OSK.
--enable takes effect NEXT login; --disable removes only our marked entry.
This is a prototype of the final installer's keyboard selection feature.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile

DESKTOP_NAME = 'a-clockwork-plex-c3-dev.desktop'
MARKER = 'X-ACP-C3-Managed=true'
HOOK_NAME = 'try-squeekboard-c3-dev.py'


class StartupError(Exception):
    pass


def target_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / '.config' / 'autostart' / DESKTOP_NAME


def desktop_text(script: Path, archive: Path) -> str:
    for item in (script, archive):
        path = str(item)
        if not item.is_absolute() or any(x in path for x in ('\n', '\r', '\t', ' ', '%', '"', "'")):
            raise StartupError('Startup paths must be absolute and contain no whitespace, percent or quotes')
    return (
        '[Desktop Entry]\n'
        'Type=Application\n'
        'Name=ACP Native Squeekboard C3 (development)\n'
        'Comment=Start the opt-in C3 keyboard after the stock labwc keyboard\n'
        f'Exec=/usr/bin/python3 {script} --startup {archive}\n'
        'Terminal=false\n'
        'X-GNOME-Autostart-enabled=true\n'
        f'{MARKER}\n'
    )


def managed(path: Path) -> bool:
    if path.is_symlink():
        raise StartupError('Autostart destination is a symlink; refusing changes')
    if not path.exists():
        return False
    st = path.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1):
        raise StartupError('Autostart destination is not a private user-owned file')
    return MARKER in path.read_text(encoding='utf-8').splitlines()


def plan(path: Path) -> None:
    print('C3 labwc/XDG desktop autostart:', path)
    print('Managed by ACP:', managed(path))
    print('Stock Raspberry Pi OS /usr/bin/sbtest and labwc startup remain unchanged.')
    print('This desktop entry starts after login and changes NO currently running keyboard.')


def enable(script: Path, archive: Path, dest: Path) -> None:
    if os.geteuid() == 0:
        raise StartupError('Use the normal Pi desktop user, not sudo/root')
    if not script.is_file() or script.is_symlink():
        raise StartupError('C3 development launcher is missing or symlinked')
    if not archive.is_file() or archive.is_symlink():
        raise StartupError('Pinned C3 ZIP must remain in place across reboots')
    new = desktop_text(script.resolve(), archive.resolve())
    existing = managed(dest)
    if dest.exists() and not existing:
        raise StartupError('Unmanaged autostart destination exists; refusing overwrite')
    if dest.parent.is_symlink():
        raise StartupError('Autostart directory is a symlink; refusing changes')
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if dest.parent.is_symlink() or dest.parent.stat().st_uid != os.getuid():
        raise StartupError('Autostart directory has unexpected ownership')
    if existing and dest.read_text(encoding='utf-8') == new:
        print('C3 development autostart already configured (no changes).')
        return
    # Write a complete entry atomically; no partial desktop file on interruption.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', prefix='.acp-c3-', suffix='.desktop',
            dir=dest.parent, delete=False,
        ) as f:
            temporary = Path(f.name)
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        temporary.chmod(0o600)
        temporary.replace(dest)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('C3 development keyboard will start at the NEXT graphical login.')
    print('Stock keyboard remains the fallback; existing keyboard session untouched.')
    print('Undo: python3 scripts/configure-squeekboard-c3-startup.py --disable')


def disable(dest: Path) -> None:
    if os.geteuid() == 0:
        raise StartupError('Use the normal Pi desktop user, not sudo/root')
    if not dest.exists() and not dest.is_symlink():
        print('No C3 development autostart entry to remove.')
        return
    if not managed(dest):
        raise StartupError('Refusing to delete an unrecognised desktop autostart entry')
    dest.unlink()
    print('C3 development autostart removed; next login uses stock keyboard.')
    print('Current C3 session is untouched; use try-squeekboard-c3-dev.py --stop separately.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--enable', metavar='PINNED_C3_ZIP', type=Path)
    modes.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    dest = target_path()
    try:
        if args.check:
            plan(dest)
        elif args.enable:
            enable(Path(__file__).with_name(HOOK_NAME), args.enable.expanduser(), dest)
        else:
            disable(dest)
        return 0
    except (StartupError, OSError, UnicodeError) as exc:
        print('C3 startup: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
