from __future__ import annotations

import unittest
from pathlib import Path


class BackupRestoreLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-backup-restore.css").read_text(encoding="utf-8")

    def test_restore_preview_long_paths_wrap_inside_grid_columns(self) -> None:
        self.assertIn('.settings-restore-detail-grid > *', self.css)
        self.assertIn('min-width: 0;', self.css)
        self.assertIn('.settings-restore-detail-grid li', self.css)
        self.assertIn('max-width: 100%;', self.css)
        self.assertIn('overflow-wrap: anywhere;', self.css)
        self.assertIn('word-break: break-word;', self.css)

    def test_restore_layout_stylesheet_cache_buster_tracks_overflow_fix(self) -> None:
        self.assertIn(
            "20260831-home-restore-feedback-v2-20260910-overflow-v1",
            self.base,
        )


if __name__ == "__main__":
    unittest.main()
