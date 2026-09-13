from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


class SettingsTouchReorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.helper = Path("app/static/js/settings-touch-reorder.js").read_text(encoding="utf-8")
        self.news = Path("app/static/js/settings-news-feed-order.js").read_text(encoding="utf-8")
        self.clock = Path("app/static/js/settings-clock-card-drag.js").read_text(encoding="utf-8")
        self.css = Path("app/static/css/settings-touch-reorder.css").read_text(encoding="utf-8")

    def test_shared_touch_reorder_loads_before_news_and_clock_enhancements(self):
        self.assertIn("settings-touch-reorder.css", self.base)
        self.assertIn("settings-touch-reorder.js", self.base)
        self.assertIn("settings-news-feed-order.js", self.base)
        self.assertIn("settings-clock-card-drag.js", self.base)
        self.assertLess(
            self.base.index("settings-touch-reorder.js"),
            self.base.index("settings-news-feed-order.js"),
        )
        self.assertLess(
            self.base.index("{% block scripts %}"),
            self.base.index("settings-clock-card-drag.js"),
        )

    def test_touch_helper_uses_pointer_events_and_scroll_assistance(self):
        self.assertIn("pointerdown", self.helper)
        self.assertIn("pointermove", self.helper)
        self.assertIn("setPointerCapture", self.helper)
        self.assertIn("autoScroll", self.helper)
        self.assertIn("ArrowUp", self.helper)
        self.assertIn("ArrowDown", self.helper)
        self.assertIn("touch-action: none", self.css)

    def test_news_feed_order_is_compact_and_separate_from_feed_editor(self):
        self.assertIn("news:feed-order", self.news)
        self.assertIn("Drag the grip to arrange the News menu", self.news)
        self.assertIn("news-feed-order-row", self.news)
        self.assertIn("news-feed-enabled-button", self.news)
        self.assertIn("textButton(card, 'Move up')", self.news)
        self.assertIn("up.hidden = true", self.news)
        self.assertIn("enabled.hidden = true", self.news)
        self.assertIn("scrollIntoView", self.news)
        self.assertIn("news-add-feed-button", self.css)
        self.assertIn("grid-template-columns: 44px minmax(0, 1fr) auto", self.css)

    def test_clock_weather_cards_use_drag_order_with_one_change_event(self):
        self.assertIn("Choose cards below, then drag the grip", self.clock)
        self.assertIn("clock-card-order-button", self.clock)
        self.assertIn("button.hidden = true", self.clock)
        self.assertIn("ACPClockCards.applyStoredIds(ids)", self.clock)
        self.assertIn("acp:clock-cards-changed", self.clock)
        self.assertIn("clock-card-drag-row", self.css)

    def test_new_javascript_is_syntax_valid(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        for path in (
            "app/static/js/settings-touch-reorder.js",
            "app/static/js/settings-news-feed-order.js",
            "app/static/js/settings-clock-card-drag.js",
        ):
            completed = subprocess.run(
                [node, "--check", path],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
