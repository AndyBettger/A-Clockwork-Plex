from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from flask import Flask, jsonify


CACHE_SCHEMA_VERSION = 1
DEFAULT_REFRESH_MINUTES = 15
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_STALE_HOURS = 6
MAX_RESPONSE_BYTES = 1_500_000
MAX_ITEMS_PER_FEED = 40

BBC_FEEDS: dict[str, dict[str, str]] = {
    "top": {
        "label": "Top Stories",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
    },
    "uk": {
        "label": "UK",
        "url": "https://feeds.bbci.co.uk/news/uk/rss.xml",
    },
    "world": {
        "label": "World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    "science": {
        "label": "Science",
        "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    },
    "technology": {
        "label": "Technology",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    },
}
DEFAULT_ENABLED_CATEGORIES = tuple(BBC_FEEDS)
TICKER_SPEEDS = {"slow", "normal", "fast"}
_SAFE_IMAGE_HOST_SUFFIXES = ("bbc.co.uk", "bbci.co.uk", "bbcimg.co.uk", "bbc.com")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

FetchBytes = Callable[[str, float], bytes]
ConfigProvider = Callable[[], dict[str, Any]]
NowProvider = Callable[[], datetime]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag.casefold() in {"br", "p", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"p", "div", "li"}:
            self.parts.append(" ")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _boolean(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return fallback


def _plain_text(value: Any, *, maximum: int) -> str:
    text = str(value or "")
    parser = _TextExtractor()
    try:
        parser.feed(text)
        parser.close()
        text = " ".join(parser.parts)
    except Exception:
        pass
    text = _CONTROL_RE.sub("", text)
    return " ".join(text.split())[:maximum]


def _local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1].casefold()


def _child(element: ET.Element, name: str) -> ET.Element | None:
    wanted = name.casefold()
    return next((item for item in list(element) if _local_name(item.tag) == wanted), None)


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    wanted = name.casefold()
    return [item for item in list(element) if _local_name(item.tag) == wanted]


def _child_text(element: ET.Element, name: str) -> str:
    item = _child(element, name)
    if item is None:
        return ""
    return "".join(item.itertext()).strip()


def _published_iso(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec="seconds")


def _safe_image_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host:
        return None
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in _SAFE_IMAGE_HOST_SUFFIXES):
        return None
    return text


def _feed_ttl(value: Any) -> int | None:
    try:
        ttl = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if ttl <= 0:
        return None
    return max(5, min(120, ttl))


def _enabled_categories(value: Any, *, strict: bool = False) -> list[str]:
    if not isinstance(value, list):
        if strict:
            raise ValueError("News categories must be an ordered list.")
        return list(DEFAULT_ENABLED_CATEGORIES)
    categories: list[str] = []
    for raw in value:
        category = str(raw).strip().casefold()
        if category not in BBC_FEEDS:
            if strict:
                raise ValueError(f"Unknown BBC News category: {category or 'empty'}")
            continue
        if category not in categories:
            categories.append(category)
    if not categories:
        if strict:
            raise ValueError("At least one BBC News category must remain enabled.")
        return list(DEFAULT_ENABLED_CATEGORIES)
    return categories


def public_news_config(config: dict[str, Any]) -> dict[str, Any]:
    news = _object(config.get("news"))
    enabled = _enabled_categories(news.get("enabled_categories"))
    default_category = str(news.get("default_category") or "top").strip().casefold()
    if default_category not in enabled:
        default_category = enabled[0]
    ticker = _object(news.get("ticker"))
    speed = str(ticker.get("speed") or "normal").strip().casefold()
    if speed not in TICKER_SPEEDS:
        speed = "normal"
    return {
        "enabled_categories": enabled,
        "default_category": default_category,
        "show_summaries": _boolean(news.get("show_summaries"), True),
        "ticker": {
            "enabled": _boolean(ticker.get("enabled"), True),
            "speed": speed,
        },
    }


def submitted_news_config(config: dict[str, Any], payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("News settings must be a JSON object.")
    news = _object(config.get("news"))
    enabled = _enabled_categories(payload.get("enabled_categories"), strict=True)
    default_category = str(payload.get("default_category") or news.get("default_category") or "top").strip().casefold()
    if default_category not in BBC_FEEDS:
        raise ValueError("Default BBC News category is unsupported.")
    if default_category not in enabled:
        raise ValueError("Default BBC News category must also be enabled.")
    ticker_payload = payload.get("ticker")
    if not isinstance(ticker_payload, dict):
        raise ValueError("News ticker settings must be a JSON object.")
    speed = str(ticker_payload.get("speed") or "normal").strip().casefold()
    if speed not in TICKER_SPEEDS:
        raise ValueError("News ticker speed must be slow, normal or fast.")

    updated = deepcopy(config)
    updated["news"] = {
        "enabled_categories": enabled,
        "default_category": default_category,
        "show_summaries": _boolean(payload.get("show_summaries"), True),
        "ticker": {
            "enabled": _boolean(ticker_payload.get("enabled"), True),
            "speed": speed,
        },
    }
    return updated


def fetch_bbc_rss(url: str, timeout: float) -> bytes:
    allowed_urls = {entry["url"] for entry in BBC_FEEDS.values()}
    if url not in allowed_urls:
        raise ValueError("BBC News feed URL is not in the appliance allow-list.")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9",
            "User-Agent": "A-Clockwork-Plex/1 bbc-news",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"BBC News returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach BBC News: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read BBC News response: {exc}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise RuntimeError("BBC News feed exceeded the appliance response-size limit.")
    return payload


def parse_bbc_rss(payload: bytes | str, category: str) -> dict[str, Any]:
    if category not in BBC_FEEDS:
        raise ValueError("Unsupported BBC News category.")
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("BBC News feed exceeded the appliance response-size limit.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"BBC News returned malformed XML: {exc}") from exc
    channel = _child(root, "channel")
    if channel is None:
        raise ValueError("BBC News RSS did not contain a channel.")

    stories: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _children(channel, "item"):
        title = _plain_text(_child_text(item, "title"), maximum=240)
        if not title:
            continue
        summary = _plain_text(_child_text(item, "description"), maximum=1600)
        published_at = _published_iso(_child_text(item, "pubDate"))
        identity_source = (
            _child_text(item, "guid")
            or _child_text(item, "link")
            or f"{title}|{published_at or ''}"
        )
        story_id = hashlib.sha256(identity_source.encode("utf-8", errors="replace")).hexdigest()[:20]
        if story_id in seen:
            continue
        seen.add(story_id)
        stories.append(
            {
                "id": story_id,
                "title": title,
                "summary": summary,
                "published_at": published_at,
                "category": category,
            }
        )
        if len(stories) >= MAX_ITEMS_PER_FEED:
            break

    image = _child(channel, "image")
    image_url = _safe_image_url(_child_text(image, "url")) if image is not None else None
    return {
        "category": category,
        "category_label": BBC_FEEDS[category]["label"],
        "source": "BBC News",
        "feed_title": _plain_text(_child_text(channel, "title"), maximum=120) or "BBC News",
        "feed_description": _plain_text(_child_text(channel, "description"), maximum=400),
        "feed_image_url": image_url,
        "last_build_at": _published_iso(_child_text(channel, "lastBuildDate")),
        "ttl_minutes": _feed_ttl(_child_text(channel, "ttl")),
        "items": stories,
    }


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _empty_cache() -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "status": "empty",
        "last_attempt_at": None,
        "expires_at": None,
        "categories": {},
    }


class BBCNewsFeedService:
    """Own BBC RSS fetching, safe normalisation and last-good disk caching."""

    def __init__(
        self,
        load_config: ConfigProvider,
        cache_path: Path,
        *,
        fetcher: FetchBytes = fetch_bbc_rss,
        now_provider: NowProvider = _now,
    ) -> None:
        self._load_config = load_config
        self._cache_path = Path(cache_path)
        self._fetcher = fetcher
        self._now = now_provider
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        if not self._cache_path.exists():
            return _empty_cache()
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_cache()
        if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            return _empty_cache()
        cache = _empty_cache()
        cache.update(payload)
        if not isinstance(cache.get("categories"), dict):
            cache["categories"] = {}
        return cache

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._cache, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._cache_path)

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._worker_loop, name="bbc-news", daemon=True)
        self._worker.start()

    def shutdown(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=max(0.1, timeout))

    def wake(self) -> None:
        self._wake_event.set()

    def worker_status(self) -> dict[str, Any]:
        worker = self._worker
        return {"running": bool(worker and worker.is_alive())}

    def _due(self, now: datetime) -> bool:
        expires_at = _parse_iso(self._cache.get("expires_at"))
        return expires_at is None or now >= expires_at

    @staticmethod
    def _required_categories(settings: dict[str, Any]) -> list[str]:
        required = list(settings["enabled_categories"])
        if settings["ticker"]["enabled"] and "top" not in required:
            required.append("top")
        return required

    def refresh(self, *, force: bool = False) -> dict[str, Any]:
        settings = public_news_config(self._load_config())
        now = self._now()
        if not force and not self._due(now):
            return self.snapshot()

        required = self._required_categories(settings)
        successes = 0
        failures = 0
        with self._lock:
            self._cache["last_attempt_at"] = _iso(now)

        for category in required:
            with self._lock:
                previous = deepcopy(_object(_object(self._cache.get("categories")).get(category)))
            try:
                payload = self._fetcher(BBC_FEEDS[category]["url"], float(DEFAULT_TIMEOUT_SECONDS))
                feed = parse_bbc_rss(payload, category)
            except Exception as exc:
                failures += 1
                state = previous
                state.update(
                    {
                        "status": "stale" if state.get("feed") else "error",
                        "last_attempt_at": _iso(now),
                        "last_error": str(exc),
                    }
                )
            else:
                successes += 1
                state = {
                    "status": "ready",
                    "last_attempt_at": _iso(now),
                    "last_success_at": _iso(now),
                    "last_error": None,
                    "feed": feed,
                }
            with self._lock:
                self._cache.setdefault("categories", {})[category] = state

        with self._lock:
            available = any(
                _object(_object(self._cache.get("categories")).get(category)).get("feed")
                for category in required
            )
            self._cache.update(
                {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "status": (
                        "ready"
                        if failures == 0 and successes == len(required)
                        else "degraded"
                        if available
                        else "error"
                    ),
                    "last_attempt_at": _iso(now),
                    "expires_at": _iso(now + timedelta(minutes=DEFAULT_REFRESH_MINUTES)),
                }
            )
            self._save_cache()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        settings = public_news_config(self._load_config())
        required = self._required_categories(settings)
        now = self._now()
        with self._lock:
            stored = deepcopy(self._cache)

        output_categories: dict[str, Any] = {}
        stale_cutoff = now - timedelta(hours=DEFAULT_STALE_HOURS)
        for category in settings["enabled_categories"]:
            state = deepcopy(_object(_object(stored.get("categories")).get(category)))
            last_success = _parse_iso(state.get("last_success_at"))
            stale = bool(state.get("feed") and (last_success is None or last_success <= stale_cutoff))
            if stale:
                state["status"] = "stale"
            state["stale"] = stale
            state["label"] = BBC_FEEDS[category]["label"]
            output_categories[category] = state

        top_state = _object(_object(stored.get("categories")).get("top"))
        top_feed = _object(top_state.get("feed"))
        ticker_items = []
        if settings["ticker"]["enabled"]:
            for item in top_feed.get("items", []) if isinstance(top_feed.get("items"), list) else []:
                if not isinstance(item, dict):
                    continue
                ticker_items.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "published_at": item.get("published_at"),
                        "category": "top",
                    }
                )

        required_states = [
            _object(_object(stored.get("categories")).get(category)) for category in required
        ]
        has_required_data = any(state.get("feed") for state in required_states)
        any_stale = any(
            state.get("feed")
            and (
                (success := _parse_iso(state.get("last_success_at"))) is None
                or success <= stale_cutoff
            )
            for state in required_states
        )
        status = str(stored.get("status") or "empty")
        if any_stale and has_required_data:
            status = "stale" if all(state.get("feed") for state in required_states) else "degraded"

        return {
            "ok": True,
            "schema_version": CACHE_SCHEMA_VERSION,
            "source": "BBC News",
            "status": status,
            "stale": any_stale,
            "last_attempt_at": stored.get("last_attempt_at"),
            "refresh_due": self._due(now),
            "worker": self.worker_status(),
            "settings": settings,
            "category_catalogue": [
                {"id": category, "label": details["label"]}
                for category, details in BBC_FEEDS.items()
            ],
            "categories": output_categories,
            "ticker": {
                "enabled": settings["ticker"]["enabled"],
                "speed": settings["ticker"]["speed"],
                "source_category": "top",
                "items": ticker_items,
            },
        }

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.refresh()
            except Exception:
                pass
            self._wake_event.wait(60)
            self._wake_event.clear()


def register_news_api(app: Flask, service: BBCNewsFeedService) -> None:
    if "api_news" in app.view_functions:
        return

    @app.get("/api/news")
    def api_news():
        return jsonify(service.snapshot())
