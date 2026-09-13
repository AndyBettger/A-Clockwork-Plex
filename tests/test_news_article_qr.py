from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

from app.configuration_backup import portable_settings
from app.news_feed import (
    BBC_FEEDS,
    DEFAULT_ENABLED_CATEGORIES,
    BBCNewsFeedService,
    _safe_article_url,
    _safe_bbc_feed_url,
    parse_bbc_rss,
    public_news_config,
    register_news_api,
    render_article_qr_svg,
    submitted_news_config,
)


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <description>BBC News test feed</description>
    <lastBuildDate>Thu, 10 Sep 2026 21:00:00 GMT</lastBuildDate>
    <item>
      <title>QR handoff test story</title>
      <description>A safe feed summary.</description>
      <pubDate>Thu, 10 Sep 2026 20:30:00 GMT</pubDate>
      <guid>https://www.bbc.co.uk/news/articles/c1234567890</guid>
      <link>https://www.bbc.co.uk/news/articles/c1234567890?at_medium=RSS&amp;at_campaign=rss#tracking</link>
    </item>
  </channel>
</rss>
"""

WEATHER_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <description>BBC News test feed</description>
    <item>
      <title>El Ni\xc3\xb1o likely to cause wetter and warmer-than-normal autumn</title>
      <description>A warmer and wetter-than-normal autumn is in store for the UK.</description>
      <pubDate>Fri, 11 Sep 2026 06:43:00 GMT</pubDate>
      <guid>https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo</guid>
      <link>https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo</link>
    </item>
  </channel>
</rss>
"""

GUID_FALLBACK_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <description>BBC News test feed</description>
    <item>
      <title>GUID fallback story</title>
      <description>Feed item with no usable HTTPS link.</description>
      <pubDate>Fri, 11 Sep 2026 07:00:00 GMT</pubDate>
      <guid>https://www.bbc.co.uk/news/articles/cguidfallback?source=rss</guid>
      <link>http://www.bbc.co.uk/news/articles/cguidfallback</link>
    </item>
  </channel>
</rss>
"""


def _config() -> dict:
    return {
        "news": {
            "enabled_categories": ["top"],
            "default_category": "top",
            "show_summaries": True,
            "ticker": {"enabled": False, "speed": "normal"},
        }
    }


def _rss(title: str) -> bytes:
    slug = title.lower().replace(" ", "-")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <description>BBC News test feed</description>
    <lastBuildDate>Sat, 12 Sep 2026 20:00:00 GMT</lastBuildDate>
    <item>
      <title>{title}</title>
      <description>Safe test summary.</description>
      <pubDate>Sat, 12 Sep 2026 19:30:00 GMT</pubDate>
      <guid>https://www.bbc.co.uk/news/articles/{slug}</guid>
      <link>https://www.bbc.co.uk/news/articles/{slug}</link>
    </item>
  </channel>
</rss>
""".encode("utf-8")


class NewsArticleQrTests(unittest.TestCase):
    def test_article_url_accepts_absolute_https_and_preserves_feed_destination(self) -> None:
        self.assertEqual(
            _safe_article_url(
                "https://www.bbc.co.uk/news/articles/c123?at_medium=RSS#fragment"
            ),
            "https://www.bbc.co.uk/news/articles/c123?at_medium=RSS#fragment",
        )
        self.assertEqual(
            _safe_article_url("https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo"),
            "https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo",
        )
        self.assertEqual(
            _safe_article_url("https://example.com/article?id=123"),
            "https://example.com/article?id=123",
        )
        self.assertIsNone(_safe_article_url("http://www.bbc.co.uk/news/articles/c123"))
        self.assertIsNone(_safe_article_url("/news/articles/c123"))
        self.assertIsNone(_safe_article_url("https://user@www.bbc.co.uk/news/articles/c123"))
        self.assertIsNone(_safe_article_url("https://www.bbc.co.uk:bad/news/articles/c123"))
        self.assertIsNone(_safe_article_url("https://www.bbc.co.uk/news/articles/c123 bad"))

    def test_public_snapshot_remains_link_free_but_private_lookup_keeps_exact_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = BBCNewsFeedService(
                _config,
                Path(directory) / "bbc-news-cache.json",
                fetcher=lambda _url, _timeout: RSS,
                now_provider=lambda: datetime(2026, 9, 10, 21, 5, tzinfo=timezone.utc),
            )
            snapshot = service.refresh(force=True)

            story = snapshot["categories"]["top"]["feed"]["items"][0]
            self.assertEqual(
                set(story),
                {"id", "title", "summary", "published_at", "category"},
            )
            self.assertNotIn("article_url", story)
            self.assertEqual(
                service.article_url_for(story["id"]),
                "https://www.bbc.co.uk/news/articles/c1234567890?at_medium=RSS&at_campaign=rss#tracking",
            )

    def test_bbc_weather_story_link_is_retained_for_qr_handoff(self) -> None:
        parsed = parse_bbc_rss(WEATHER_RSS, "science")
        self.assertEqual(len(parsed["items"]), 1)
        self.assertEqual(
            parsed["items"][0]["article_url"],
            "https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo",
        )

    def test_guid_is_used_when_link_is_not_usable_https(self) -> None:
        parsed = parse_bbc_rss(GUID_FALLBACK_RSS, "top")
        self.assertEqual(len(parsed["items"]), 1)
        self.assertEqual(
            parsed["items"][0]["article_url"],
            "https://www.bbc.co.uk/news/articles/cguidfallback?source=rss",
        )

    def test_qr_endpoint_is_local_story_id_only_and_returns_svg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = BBCNewsFeedService(
                _config,
                Path(directory) / "bbc-news-cache.json",
                fetcher=lambda _url, _timeout: RSS,
                now_provider=lambda: datetime(2026, 9, 10, 21, 5, tzinfo=timezone.utc),
            )
            snapshot = service.refresh(force=True)
            story_id = snapshot["categories"]["top"]["feed"]["items"][0]["id"]

            app = Flask(__name__)
            register_news_api(app, service)
            client = app.test_client()

            response = client.get(f"/api/news/story/{story_id}/qr.svg")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/svg+xml")
            self.assertIn(b"<svg", response.data)
            self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

            missing = client.get("/api/news/story/00000000000000000000/qr.svg")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.get_json()["ok"], False)

    def test_qr_renderer_accepts_https_feed_destinations_and_rejects_non_https(self) -> None:
        self.assertIn(
            b"<svg",
            render_article_qr_svg("https://www.bbc.co.uk/weather/articles/cqxv4wj8jxwo"),
        )
        self.assertIn(
            b"<svg",
            render_article_qr_svg("https://example.com/article?id=123"),
        )
        with self.assertRaises(ValueError):
            render_article_qr_svg("http://example.com/article")


class NewsCustomFeedTests(unittest.TestCase):
    def test_curated_catalogue_expands_without_enabling_new_sections_by_default(self) -> None:
        settings = public_news_config({"news": {}})
        self.assertEqual(settings["enabled_categories"], list(DEFAULT_ENABLED_CATEGORIES))
        self.assertEqual(settings["default_category"], "top")
        self.assertEqual(settings["feed_order"][:5], list(DEFAULT_ENABLED_CATEGORIES))
        self.assertEqual(
            set(settings["feed_order"]),
            {
                "top", "uk", "world", "science", "technology", "england", "scotland",
                "wales", "northern_ireland", "business", "politics", "health", "education",
                "entertainment",
            },
        )
        self.assertEqual(BBC_FEEDS["science"]["label"], "Science & Environment")

    def test_bbc_feed_url_boundary_accepts_news_rss_only(self) -> None:
        self.assertEqual(
            _safe_bbc_feed_url("https://feeds.bbci.co.uk/news/business/rss.xml"),
            "https://feeds.bbci.co.uk/news/business/rss.xml",
        )
        self.assertEqual(
            _safe_bbc_feed_url("https://feeds.bbci.co.uk/news/rss.xml"),
            "https://feeds.bbci.co.uk/news/rss.xml",
        )
        self.assertIsNone(_safe_bbc_feed_url("http://feeds.bbci.co.uk/news/business/rss.xml"))
        self.assertIsNone(_safe_bbc_feed_url("https://feeds.bbci.co.uk.evil.example/news/rss.xml"))
        self.assertIsNone(_safe_bbc_feed_url("https://user@feeds.bbci.co.uk/news/rss.xml"))
        self.assertIsNone(_safe_bbc_feed_url("https://feeds.bbci.co.uk/sport/rss.xml"))
        self.assertIsNone(_safe_bbc_feed_url("https://feeds.bbci.co.uk/news/business/rss.xml?x=1"))
        self.assertIsNone(_safe_bbc_feed_url("https://example.com/news/rss.xml"))

    def test_custom_feed_can_be_renamed_ordered_enabled_and_made_default(self) -> None:
        custom_url = "https://feeds.bbci.co.uk/news/topics/cp7r8vgl2lgt/rss.xml"
        payload = {
            "enabled_categories": ["custom-space", "business"],
            "default_category": "custom-space",
            "feed_order": ["custom-space", "business"],
            "feed_labels": {"business": "Money & Business"},
            "custom_feeds": [{"id": "custom-space", "label": "Space", "url": custom_url}],
            "show_summaries": False,
            "ticker": {"enabled": True, "speed": "slow"},
        }

        settings = public_news_config(submitted_news_config({"news": {}}, payload))

        self.assertEqual(settings["enabled_categories"][:2], ["custom-space", "business"])
        self.assertEqual(settings["default_category"], "custom-space")
        self.assertEqual(settings["feed_order"][:2], ["custom-space", "business"])
        self.assertEqual(settings["feed_labels"], {"business": "Money & Business"})
        self.assertEqual(
            settings["custom_feeds"],
            [{"id": "custom-space", "label": "Space", "url": custom_url}],
        )
        self.assertFalse(settings["show_summaries"])
        self.assertEqual(settings["ticker"]["speed"], "slow")

    def test_custom_feed_rejects_arbitrary_and_duplicate_sources(self) -> None:
        base = {
            "enabled_categories": ["top"],
            "default_category": "top",
            "feed_order": ["top"],
            "feed_labels": {},
            "show_summaries": True,
            "ticker": {"enabled": False, "speed": "normal"},
        }
        with self.assertRaisesRegex(ValueError, "feeds.bbci.co.uk"):
            submitted_news_config(
                {"news": {}},
                {**base, "custom_feeds": [{"id": "custom-evil", "label": "Not BBC", "url": "https://example.com/news/rss.xml"}]},
            )
        with self.assertRaisesRegex(ValueError, "already configured"):
            submitted_news_config(
                {"news": {}},
                {**base, "custom_feeds": [{"id": "custom-top-copy", "label": "Duplicate", "url": "https://feeds.bbci.co.uk/news/rss.xml"}]},
            )

    def test_custom_source_is_fetched_but_source_url_stays_out_of_news_api(self) -> None:
        custom_url = "https://feeds.bbci.co.uk/news/topics/cp7r8vgl2lgt/rss.xml"
        config = {
            "news": {
                "enabled_categories": ["custom-space"],
                "default_category": "custom-space",
                "feed_order": ["custom-space"],
                "feed_labels": {},
                "custom_feeds": [{"id": "custom-space", "label": "Space", "url": custom_url}],
                "show_summaries": True,
                "ticker": {"enabled": False, "speed": "normal"},
            }
        }
        requested: list[str] = []

        def fetcher(url: str, _timeout: float) -> bytes:
            requested.append(url)
            return _rss("Custom feed story")

        with tempfile.TemporaryDirectory() as directory:
            service = BBCNewsFeedService(
                lambda: config,
                Path(directory) / "bbc-news-cache.json",
                fetcher=fetcher,
                now_provider=lambda: datetime(2026, 9, 12, 20, 5, tzinfo=timezone.utc),
            )
            snapshot = service.refresh(force=True)

        self.assertEqual(requested, [custom_url])
        self.assertEqual(snapshot["settings"]["enabled_categories"], ["custom-space"])
        self.assertEqual(snapshot["category_catalogue"][0], {"id": "custom-space", "label": "Space"})
        self.assertEqual(snapshot["categories"]["custom-space"]["feed"]["items"][0]["title"], "Custom feed story")
        serialised = json.dumps(snapshot)
        self.assertNotIn(custom_url, serialised)
        self.assertNotIn("custom_feeds", snapshot["settings"])
        self.assertNotIn("feed_labels", snapshot["settings"])

    def test_ticker_remains_top_stories_when_other_feeds_are_enabled(self) -> None:
        config = {
            "news": {
                "enabled_categories": ["business"],
                "default_category": "business",
                "show_summaries": True,
                "ticker": {"enabled": True, "speed": "normal"},
            }
        }

        def fetcher(url: str, _timeout: float) -> bytes:
            if url == BBC_FEEDS["top"]["url"]:
                return _rss("Top ticker story")
            if url == BBC_FEEDS["business"]["url"]:
                return _rss("Business page story")
            raise AssertionError(f"unexpected feed {url}")

        with tempfile.TemporaryDirectory() as directory:
            service = BBCNewsFeedService(
                lambda: config,
                Path(directory) / "bbc-news-cache.json",
                fetcher=fetcher,
                now_provider=lambda: datetime(2026, 9, 12, 20, 5, tzinfo=timezone.utc),
            )
            snapshot = service.refresh(force=True)

        self.assertEqual(snapshot["ticker"]["source_category"], "top")
        self.assertEqual([item["title"] for item in snapshot["ticker"]["items"]], ["Top ticker story"])
        self.assertEqual(snapshot["categories"]["business"]["feed"]["items"][0]["title"], "Business page story")

    def test_portable_backup_keeps_logical_news_feed_configuration(self) -> None:
        news = {
            "enabled_categories": ["business", "custom-space"],
            "default_category": "custom-space",
            "feed_order": ["business", "custom-space", "top"],
            "feed_labels": {"business": "Money & Business"},
            "custom_feeds": [
                {
                    "id": "custom-space",
                    "label": "Space",
                    "url": "https://feeds.bbci.co.uk/news/topics/cp7r8vgl2lgt/rss.xml",
                }
            ],
            "show_summaries": True,
            "ticker": {"enabled": True, "speed": "normal"},
        }

        backup_settings = portable_settings({"news": news})

        self.assertEqual(backup_settings["news"], news)


if __name__ == "__main__":
    unittest.main()
