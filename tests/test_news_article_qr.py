from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

from app.news_feed import (
    BBCNewsFeedService,
    _safe_article_url,
    parse_bbc_rss,
    register_news_api,
    render_article_qr_svg,
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


if __name__ == "__main__":
    unittest.main()
