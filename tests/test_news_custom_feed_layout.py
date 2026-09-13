from __future__ import annotations

import unittest
from pathlib import Path


class NewsCustomFeedLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path("app/templates/base.html").read_text(encoding="utf-8")
        self.news_template = Path("app/templates/news.html").read_text(encoding="utf-8")
        self.placement = Path("app/static/js/settings-news-placement.js").read_text(encoding="utf-8")
        self.css = Path("app/static/css/news-custom-feeds.css").read_text(encoding="utf-8")

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

    def test_news_category_rail_is_touch_scrollable(self):
        self.assertIn(".news-category-list {", self.css)
        self.assertIn("flex: 1 1 auto;", self.css)
        self.assertIn("min-height: 0;", self.css)
        self.assertIn("overflow-y: auto;", self.css)
        self.assertIn("overscroll-behavior: contain;", self.css)
        self.assertIn("touch-action: pan-y;", self.css)
        self.assertIn(".news-category-list::-webkit-scrollbar-thumb", self.css)
        self.assertIn("css/news-custom-feeds.css", self.news_template)
        self.assertIn("css/news-custom-feeds.css", self.base)


if __name__ == "__main__":
    unittest.main()
