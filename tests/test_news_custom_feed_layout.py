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


if __name__ == "__main__":
    unittest.main()
