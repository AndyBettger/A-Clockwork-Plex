#!/usr/bin/python3
from __future__ import annotations

"""Target-proved compatibility corrections for the Stage C21 rehearsal.

The first real Pi run proved that the established appliance root
``/var/lib/a-clockwork-plex`` is root:root 0755, while the historical Stage C15
adapter contract expected 0750. A later real run proved that the shared
regular-tree helper now requires an explicit evidence label, while the Stage C21
v7 rehearsal still called its earlier one-argument interface.

This compatibility entrypoint changes only those two reviewed bindings before
delegating to the otherwise unchanged Stage C21 v7 stage/validate/abort
rehearsal. It changes no filesystem permission and exposes no additional
production operation.
"""

import inspect
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

EVIDENCE_TREE_LABEL_V8 = "Stage C21 current-package evidence"
EVIDENCE_TREE_PARAMETERS_V8 = ("root", "label")
_EVIDENCE_TREE_WRAPPER_MARKER_V8 = "_stage_c21_evidence_label_v8"


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


def apply_evidence_tree_label_contract_v8() -> None:
    """Bind the current two-argument tree checker to the fixed evidence label."""

    checker = rehearsal_v7._assert_regular_tree
    if getattr(checker, _EVIDENCE_TREE_WRAPPER_MARKER_V8, False):
        return

    parameters = tuple(inspect.signature(checker).parameters)
    if parameters != EVIDENCE_TREE_PARAMETERS_V8:
        raise SystemExit(
            "Stage C21 regular-tree helper signature changed; refusing the v8 "
            "evidence-label compatibility correction"
        )

    def assert_current_package_evidence_tree(root: Path) -> None:
        checker(root, EVIDENCE_TREE_LABEL_V8)

    setattr(
        assert_current_package_evidence_tree,
        _EVIDENCE_TREE_WRAPPER_MARKER_V8,
        True,
    )
    rehearsal_v7._assert_regular_tree = assert_current_package_evidence_tree


def main(argv: list[str] | None = None) -> int:
    apply_target_proved_parent_contract_v8()
    apply_evidence_tree_label_contract_v8()
    return rehearsal_v7.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
