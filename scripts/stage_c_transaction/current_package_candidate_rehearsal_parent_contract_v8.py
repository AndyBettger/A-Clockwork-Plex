#!/usr/bin/python3
from __future__ import annotations

"""Target-proved parent-mode correction for the Stage C21 rehearsal.

The first real Pi run proved that the established appliance root
``/var/lib/a-clockwork-plex`` is root:root 0755, while the historical Stage C15
adapter contract expected 0750.  This compatibility entrypoint changes only
that obsolete inherited mode expectation before delegating to the unchanged
Stage C21 v7 stage/validate/abort rehearsal.

No filesystem permission is changed by this module.  Any owner, path or other
mode drift continues to fail closed in the existing adapter.
"""

from pathlib import Path

from . import current_package_candidate_rehearsal_adapter_v7 as adapter_v7
from . import current_package_candidate_rehearsal_v7 as rehearsal_v7


LEGACY_CURRENT_PARENT_CONTRACT_V7 = (
    (Path("/var/lib/a-clockwork-plex"), 0o750),
    (Path("/var/lib/a-clockwork-plex/split-bus"), 0o755),
    (Path("/var/lib/a-clockwork-plex/split-bus/transactions"), 0o700),
)

TARGET_PROVED_PARENT_CONTRACT_V8 = (
    (Path("/var/lib/a-clockwork-plex"), 0o755),
    (Path("/var/lib/a-clockwork-plex/split-bus"), 0o755),
    (Path("/var/lib/a-clockwork-plex/split-bus/transactions"), 0o700),
)


def apply_target_proved_parent_contract_v8() -> None:
    """Apply only the reviewed 0755 outer-parent correction."""

    if adapter_v7.CURRENT_PARENT_CONTRACT != LEGACY_CURRENT_PARENT_CONTRACT_V7:
        raise SystemExit(
            "Stage C21 v7 parent contract changed; refusing to apply the v8 "
            "target-proved compatibility correction"
        )

    inherited_paths = tuple(path for path, _mode in adapter_v7.PARENT_CONTRACT)
    corrected_paths = tuple(
        path for path, _mode in TARGET_PROVED_PARENT_CONTRACT_V8
    )
    if inherited_paths != corrected_paths:
        raise SystemExit(
            "Stage C21 inherited transaction paths changed; refusing the v8 "
            "parent-mode correction"
        )

    adapter_v7.CURRENT_PARENT_CONTRACT = TARGET_PROVED_PARENT_CONTRACT_V8


def main(argv: list[str] | None = None) -> int:
    apply_target_proved_parent_contract_v8()
    return rehearsal_v7.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
