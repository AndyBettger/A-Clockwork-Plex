from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "app" / "static" / "css" / "settings-backup-restore.css"


class SettingsRestorePhysicalFollowupTests(unittest.TestCase):
    def test_preview_action_has_separation_from_status(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn(
            '.settings-action-row:has([data-action="preview-configuration-restore"])',
            style,
        )
        self.assertIn("margin-bottom: 12px", style)

    def test_review_button_and_status_are_grouped_into_one_card(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn(
            '[data-configuration-restore-apply-zone]:not([hidden])::before',
            style,
        )
        self.assertIn('content: "Review restore"', style)
        self.assertIn("grid-template-columns: auto minmax(0, 1fr)", style)
        self.assertIn("[data-action=\"review-selected-restore\"]", style)
        self.assertIn("[data-configuration-restore-review-status]:not([hidden])", style)

    def test_final_confirmation_is_hard_hidden_until_review_completes(self):
        style = STYLE.read_text(encoding="utf-8")
        selector = (
            '[data-settings-subpage="advanced:backup"] '
            '[data-configuration-restore-confirm][hidden]'
        )
        self.assertIn(selector, style)
        self.assertIn("display: none !important", style)

    def test_persisted_restore_result_is_promoted_after_reload(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn(
            '.settings-card:has(> [data-configuration-restore-result-status]:not([hidden]))',
            style,
        )
        self.assertIn("flex-direction: column", style)
        self.assertIn("order: -2", style)
        self.assertIn("order: -1", style)


if __name__ == "__main__":
    unittest.main()
