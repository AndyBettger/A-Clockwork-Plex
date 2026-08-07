#!/usr/bin/python3
from __future__ import annotations

import sys

sys.dont_write_bytecode = True
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent
INSTALLED_ROOT = Path('/usr/local/lib/a-clockwork-plex/audio-eq')
for root in (INSTALLED_ROOT, SOURCE_ROOT):
    if root.is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

from audio_eq_camilladsp import *  # noqa: F401,F403


if __name__ == '__main__':
    raise SystemExit(main())
