from __future__ import annotations

import json
import os
import sys
from typing import Any

from .model import load_settings
from .runtime import EqController


def emit(payload: dict[str, Any], code: int = 0, *, stderr: bool = False) -> int:
    print(json.dumps(payload, sort_keys=True), file=sys.stderr if stderr else sys.stdout)
    return code


def main() -> int:
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'status'
    controller = EqController(load_settings())
    try:
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
