from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from app.news_feed import _suggest_feed_label


class NewsCustomFeedLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.news_template = Path("app/templates/news.html").read_text(encoding="utf-8")
        self.placement = Path("app/static/js/settings-news-placement.js").read_text(encoding="utf-8")
        self.css = Path("app/static/css/news-custom-feeds.css").read_text(encoding="utf-8")
        self.scrollbar_js = Path("app/static/js/news-category-scrollbar.js").read_text(encoding="utf-8")
        self.news_feed = Path("app/news_feed.py").read_text(encoding="utf-8")
        self.touch_helper = Path("app/static/js/settings-touch-reorder.js").read_text(encoding="utf-8")
        self.feed_order = Path("app/static/js/settings-news-feed-order.js").read_text(encoding="utf-8")
        self.clock_drag = Path("app/static/js/settings-clock-card-drag.js").read_text(encoding="utf-8")
        self.touch_css = Path("app/static/css/settings-touch-reorder.css").read_text(encoding="utf-8")

    def test_feed_editor_is_reparented_into_news_before_settings_navigation_binds(self):
        self.assertIn("feedRow.dataset.settingsSubpageTarget = 'news:feeds';", self.placement)
        self.assertIn("feedSubpage.dataset.settingsSubpage = 'news:feeds';", self.placement)
        self.assertIn("back.dataset.settingsBack = 'news';", self.placement)
        self.assertIn("back.textContent = '‹ News';", self.placement)
        self.assertIn("newsOverview.appendChild(feedRow);", self.placement)
        self.assertIn("newsPanel.appendChild(feedSubpage);", self.placement)
        self.assertLess(
            self.base.index("settings-news.js"),
            self.base.index("settings-news-placement.js"),
        )
        self.assertLess(
            self.base.index("settings-news-placement.js"),
            self.base.index("{% block scripts %}"),
        )

    def test_feed_editor_cards_have_deliberate_vertical_spacing(self):
        self.assertIn("editorList?.classList.add('news-feed-editor-list');", self.placement)
        self.assertIn(".news-feed-editor-list {", self.css)
        self.assertIn("gap: clamp(12px, 1.8vmin, 18px);", self.css)
        self.assertIn(".news-feed-editor-list > .settings-card", self.css)

    def test_news_category_rail_reuses_the_story_custom_scrollbar(self):
        self.assertIn('class="news-category-scroll"', self.news_template)
        self.assertIn('id="news-category-list"', self.news_template)
        self.assertIn(
            'class="news-story-scrollbar news-category-scrollbar"',
            self.news_template,
        )
        self.assertIn('data-news-category-scrollbar', self.news_template)
        self.assertIn('data-news-category-scrollbar-thumb', self.news_template)
        self.assertIn('aria-controls="news-category-list"', self.news_template)
        self.assertIn("js/news-category-scrollbar.js", self.news_template)

        self.assertIn(".news-category-scroll {", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 8px;", self.css)
        self.assertIn("overflow-y: auto;", self.css)
        self.assertIn("overscroll-behavior: contain;", self.css)
        self.assertIn("touch-action: pan-y;", self.css)
        self.assertIn("scrollbar-width: none;", self.css)
        self.assertIn(".news-category-list::-webkit-scrollbar", self.css)
        self.assertIn("display: none;", self.css)

        self.assertIn("const trackInset = 1;", self.scrollbar_js)
        self.assertIn("Math.max(42, proportionalHeight)", self.scrollbar_js)
        self.assertIn("scrollMount.addEventListener('scroll', update", self.scrollbar_js)
        self.assertIn("scrollbar.classList.add('is-dragging');", self.scrollbar_js)
        self.assertIn("MutationObserver", self.scrollbar_js)

    def test_news_followup_clients_have_valid_javascript_syntax(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for JavaScript syntax regression checks")
        for source in (
            "app/static/js/settings-news-placement.js",
            "app/static/js/news-category-scrollbar.js",
            "app/static/js/settings-touch-reorder.js",
            "app/static/js/settings-news-feed-order.js",
            "app/static/js/settings-clock-card-drag.js",
        ):
            completed = subprocess.run(
                [node, "--check", source],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"JavaScript syntax check failed for {source}:\n{completed.stderr}",
            )

    def test_feed_help_uses_a_complete_rss_example_not_the_bare_feed_host(self):
        self.assertIn("const feedHelp = feedSubpage.querySelector", self.placement)
        self.assertIn(
            "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
            self.placement,
        )
        self.assertIn("Only HTTPS BBC News feeds are accepted.", self.placement)
        self.assertNotIn("add another BBC News RSS feed from <code>feeds.bbci.co.uk</code>", self.placement)

    def test_feed_check_help_matches_the_automatic_settings_workflow(self):
        self.assertIn("refreshCustomFeedHelp", self.placement)
        self.assertIn("copy.includes('pass Check feed before Save Changes')", self.placement)
        self.assertIn("then press Check feed", self.placement)
        self.assertIn("before this custom feed can be used", self.placement)

    def test_feed_label_prefers_specific_title_then_specific_description(self):
        self.assertEqual(_suggest_feed_label("BBC News - Space", "Space stories"), "Space")
        self.assertEqual(_suggest_feed_label("BBC News", "BBC News - Europe"), "Europe")
        self.assertEqual(_suggest_feed_label("BBC News", "BBC News"), "Custom BBC feed")
        self.assertIn('feed.get("feed_description")', self.news_feed)

    def test_touch_ordering_loads_in_the_required_settings_sequence(self):
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

    def test_touch_helper_uses_pointer_events_keyboard_fallback_and_auto_scroll(self):
        self.assertIn("pointerdown", self.touch_helper)
        self.assertIn("pointermove", self.touch_helper)
        self.assertIn("setPointerCapture", self.touch_helper)
        self.assertIn("autoScroll", self.touch_helper)
        self.assertIn("ArrowUp", self.touch_helper)
        self.assertIn("ArrowDown", self.touch_helper)
        self.assertIn("touch-action: none", self.touch_css)

    def test_news_feed_order_is_compact_and_separate_from_feed_editor(self):
        self.assertIn("news:feed-order", self.feed_order)
        self.assertIn("Drag the grip to arrange the News menu", self.feed_order)
        self.assertIn("news-feed-order-row", self.feed_order)
        self.assertIn("news-feed-enabled-button", self.feed_order)
        self.assertIn("textButton(card, 'Move up')", self.feed_order)
        self.assertIn("up.hidden = true", self.feed_order)
        self.assertIn("enabled.hidden = true", self.feed_order)
        self.assertIn("scrollIntoView", self.feed_order)
        self.assertIn("news-add-feed-button", self.touch_css)
        self.assertIn("grid-template-columns: 44px minmax(0, 1fr) auto", self.touch_css)

    def test_clock_weather_cards_gain_touch_drag_order_without_replacing_state_owner(self):
        self.assertIn("Choose cards below, then drag the grip", self.clock_drag)
        self.assertIn("clock-card-order-button", self.clock_drag)
        self.assertIn("button.hidden = true", self.clock_drag)
        self.assertIn("ACPClockCards.applyStoredIds(ids)", self.clock_drag)
        self.assertIn("acp:clock-cards-changed", self.clock_drag)
        self.assertIn("clock-card-drag-row", self.touch_css)


if __name__ == "__main__":
    unittest.main()
