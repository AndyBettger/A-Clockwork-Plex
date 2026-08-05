#!/usr/bin/python3
from __future__ import annotations

"""Stage C17 corrected physical entry point.

The accepted C17 orchestration remains unchanged. This explicit entry point
selects only the corrected post-restoration readiness adapter introduced after
the first physical run exposed the systemd-active versus ALSA-ready race.
"""

from . import service_quiescence_rehearsal as rehearsal
from .service_quiescence_rehearsal_adapter_v2 import (
    ServiceQuiescenceRehearsalAdapterV2,
)


def main() -> None:
    rehearsal.ServiceQuiescenceRehearsalAdapter = (
        ServiceQuiescenceRehearsalAdapterV2
    )
    rehearsal.main()


if __name__ == "__main__":
    main()
