from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .model import load_settings
from .runtime import EqController


INSTALLED_LAUNCHER = Path('/usr/local/bin/a-clockwork-plex-audio-eq')
INSTALLED_CLI = Path(
    '/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/cli.py'
)


def emit(payload: dict[str, Any], code: int = 0, *, stderr: bool = False) -> int:
    print(json.dumps(payload, sort_keys=True), file=sys.stderr if stderr else sys.stdout)
    return code


def _delegate_status_if_needed(
    action: str,
    argument_count: int,
    *,
    effective_uid: int | None = None,
    module_path: Path | None = None,
    runner: Any = subprocess.run,
) -> int | None:
    """Run installed read-only status through the existing restricted sudo rule.

    The authoritative EQ JSON is intentionally root-owned mode 0600.  The
    dashboard already invokes the helper through sudo, but an interactive
    unprivileged invocation previously fell back to the default neutral state
    when that JSON could not be read.  Only the installed helper's exact
    ``status`` command is delegated; source-tree execution and mutations keep
    their existing privilege boundary.
    """
    uid = os.geteuid() if effective_uid is None else effective_uid
    current_module = Path(__file__).resolve() if module_path is None else Path(module_path).resolve()
    if action != 'status' or argument_count != 2 or uid == 0:
        return None
    if current_module != INSTALLED_CLI:
        return None
    result = runner(
        ['/usr/bin/sudo', '-n', str(INSTALLED_LAUNCHER), 'status'],
        check=False,
    )
    return int(result.returncode)


def main() -> int:
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'status'
    try:
        delegated = _delegate_status_if_needed(action, len(sys.argv))
        if delegated is not None:
            return delegated

        controller = EqController(load_settings())
        if action == 'status' and len(sys.argv) == 2:
            return emit(controller.status())
        if os.geteuid() != 0:
            raise RuntimeError('EQ mutation requires root through the restricted sudo rule.')
        with controller.locked():
            if action in {'set', 'live'} and len(sys.argv) == 4:
                return emit(controller.set_band(
                    sys.argv[2].strip().lower(),
                    sys.argv[3],
                    persist=action == 'set',
                ))
            if action == 'bypass' and len(sys.argv) == 3:
                value = sys.argv[2].strip().lower()
                if value not in {'on', 'off', 'true', 'false', '1', '0'}:
                    raise ValueError('Bypass must be on or off.')
                return emit(controller.set_bypass(value in {'on', 'true', '1'}))
            if action == 'neutral' and len(sys.argv) == 2:
                return emit(controller.neutral())
        raise ValueError(f'Unsupported EQ action: {action}')
    except (ValueError, RuntimeError, OSError) as exc:
        return emit({'ok': False, 'error': str(exc)}, 1, stderr=True)


if __name__ == '__main__':
    raise SystemExit(main())
