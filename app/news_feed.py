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

import qrcode
import qrcode.image.svg
from flask import Flask, Response, jsonify, request


CACHE_SCHEMA_VERSION = 4
DEFAULT_REFRESH_MINUTES = 15
DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_STALE_HOURS = 6
MAX_RESPONSE_BYTES = 1_500_000
MAX_ITEMS_PER_FEED = 40
MAX_CUSTOM_FEEDS = 12
MAX_FEED_LABEL_LENGTH = 80

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
        "label": "Science & Environment",
        "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    },
    "technology": {
        "label": "Technology",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    },
    "england": {
        "label": "England",
        "url": "https://feeds.bbci.co.uk/news/england/rss.xml",
    },
    "scotland": {
        "label": "Scotland",
        "url": "https://feeds.bbci.co.uk/news/scotland/rss.xml",
    },
    "wales": {
        "label": "Wales",
        "url": "https://feeds.bbci.co.uk/news/wales/rss.xml",
    },
    "northern_ireland": {
        "label": "Northern Ireland",
        "url": "https://feeds.bbci.co.uk/news/northern_ireland/rss.xml",
    },
    "business": {
        "label": "Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
    },
    "politics": {
        "label": "Politics",
        "url": "https://feeds.bbci.co.uk/news/politics/rss.xml",
    },
    "health": {
        "label": "Health",
        "url": "https://feeds.bbci.co.uk/news/health/rss.xml",
    },
    "education": {
        "label": "Education",
        "url": "https://feeds.bbci.co.uk/news/education/rss.xml",
    },
    "entertainment": {
        "label": "Entertainment & Arts",
        "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
    },
}
DEFAULT_ENABLED_CATEGORIES = ("top", "uk", "world", "science", "technology")
DEFAULT_FEED_ORDER = tuple(BBC_FEEDS)
TICKER_SPEEDS = {"slow", "normal", "fast"}
_SAFE_IMAGE_HOST_SUFFIXES = ("bbc.co.uk", "bbci.co.uk", "bbcimg.co.uk", "bbc.com")
_SAFE_FEED_HOST = "feeds.bbci.co.uk"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_STORY_ID_RE = re.compile(r"^[0-9a-f]{20}$")
_CATEGORY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_CUSTOM_FEED_ID_RE = re.compile(r"^custom-[a-z0-9][a-z0-9-]{0,47}$")

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


def _safe_article_url(value: Any) -> str | None:
    """Return an absolute HTTPS destination supplied by a trusted RSS item.

    The News service itself fetches only validated BBC feeds. Article
    destinations are therefore treated as feed-owned data rather than browser
    input: preserve the exact HTTPS URL the feed supplied, while rejecting
    malformed, relative, credential-bearing or non-HTTPS values.
    """

    text = str(value or "").strip()
    if not text or _CONTROL_RE.search(text) or any(character.isspace() for character in text):
        return None
    try:
        parsed = urlparse(text)
        _ = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https" or not parsed.netloc or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return text


def _safe_bbc_feed_url(value: Any) -> str | None:
    """Return a canonical BBC News RSS URL or None.

    User-configurable sources remain deliberately BBC-only. This keeps the
    fetcher from becoming an arbitrary URL/SSRF endpoint while still allowing
    additional BBC News section feeds.
    """

    text = str(value or "").strip()
    if not text or _CONTROL_RE.search(text) or any(character.isspace() for character in text):
        return None
    try:
        parsed = urlparse(text)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https":
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host != _SAFE_FEED_HOST or port not in (None, 443):
        return None
    if parsed.query or parsed.fragment or parsed.params:
        return None
    path = parsed.path or ""
    if path != "/news/rss.xml" and not (path.startswith("/news/") and path.endswith("/rss.xml")):
        return None
    if "//" in path or "/../" in path or "/./" in path:
        return None
    return f"https://{_SAFE_FEED_HOST}{path}"


class _BBCFeedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects before urllib can leave the BBC News RSS boundary."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        if _safe_bbc_feed_url(newurl) is None:
            raise RuntimeError("BBC News redirected outside the approved RSS source boundary.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _public_story(item: Any) -> dict[str, Any] | None:
    """Project one cached story onto the intentionally link-free public API."""

    if not isinstance(item, dict):
        return None
    story_id = str(item.get("id") or "").strip().casefold()
    if not _STORY_ID_RE.fullmatch(story_id):
        return None
    return {
        "id": story_id,
        "title": item.get("title"),
        "summary": item.get("summary"),
        "published_at": item.get("published_at"),
        "category": item.get("category"),
    }


def _public_feed(feed: Any) -> dict[str, Any]:
    """Strip private QR hand-off data from a cached feed before JSON output."""

    source = _object(feed)
    public = {key: deepcopy(value) for key, value in source.items() if key != "items"}
    items: list[dict[str, Any]] = []
    for item in source.get("items", []) if isinstance(source.get("items"), list) else []:
        projected = _public_story(item)
        if projected is not None:
            items.append(projected)
    public["items"] = items
    return public


def render_article_qr_svg(value: Any) -> bytes:
    """Render a locally generated QR code for one trusted RSS HTTPS destination."""

    article_url = _safe_article_url(value)
    if article_url is None:
        raise ValueError("RSS article URL is not a valid absolute HTTPS destination.")
    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    code.add_data(article_url)
    code.make(fit=True)
    image = code.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
    return image.to_string()


def _feed_ttl(value: Any) -> int | None:
    try:
        ttl = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if ttl <= 0:
        return None
    return max(5, min(120, ttl))


def _custom_feed_id(value: Any, url: str, *, strict: bool) -> str | None:
    candidate = str(value or "").strip().casefold()
    if not candidate:
        candidate = f"custom-{hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]}"
    if not _CUSTOM_FEED_ID_RE.fullmatch(candidate):
        if strict:
            raise ValueError("Custom BBC News feed id is invalid.")
        return None
    return candidate


def _custom_feeds(value: Any, *, strict: bool = False) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        if strict:
            raise ValueError("Custom BBC News feeds must be a list.")
        return []

    output: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_urls = {entry["url"] for entry in BBC_FEEDS.values()}
    for raw in value:
        if not isinstance(raw, dict):
            if strict:
                raise ValueError("Each custom BBC News feed must be an object.")
            continue
        url = _safe_bbc_feed_url(raw.get("url"))
        if url is None:
            if strict:
                raise ValueError("Custom feeds must use a BBC News RSS URL on feeds.bbci.co.uk.")
            continue
        feed_id = _custom_feed_id(raw.get("id"), url, strict=strict)
        if feed_id is None:
            continue
        label = _plain_text(raw.get("label"), maximum=MAX_FEED_LABEL_LENGTH)
        if not label:
            if strict:
                raise ValueError("Custom BBC News feeds require a label.")
            continue
        if feed_id in BBC_FEEDS or feed_id in seen_ids:
            if strict:
                raise ValueError("Custom BBC News feed ids must be unique.")
            continue
        if url in seen_urls:
            if strict:
                raise ValueError("That BBC News RSS URL is already configured.")
            continue
        seen_ids.add(feed_id)
        seen_urls.add(url)
        output.append({"id": feed_id, "label": label, "url": url})
        if len(output) > MAX_CUSTOM_FEEDS:
            if strict:
                raise ValueError(f"No more than {MAX_CUSTOM_FEEDS} custom BBC News feeds may be configured.")
            return output[:MAX_CUSTOM_FEEDS]
    return output


def _feed_labels(value: Any, *, strict: bool = False) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        if strict:
            raise ValueError("BBC News feed labels must be an object.")
        return {}
    output: dict[str, str] = {}
    for raw_id, raw_label in value.items():
        feed_id = str(raw_id or "").strip().casefold()
        if feed_id not in BBC_FEEDS:
            if strict:
                raise ValueError(f"Unknown built-in BBC News feed label: {feed_id or 'empty'}")
            continue
        label = _plain_text(raw_label, maximum=MAX_FEED_LABEL_LENGTH)
        if not label:
            continue
        if label != BBC_FEEDS[feed_id]["label"]:
            output[feed_id] = label
    return output


def _feed_order(
    value: Any,
    custom: list[dict[str, str]],
    *,
    strict: bool = False,
) -> list[str]:
    valid = list(DEFAULT_FEED_ORDER) + [item["id"] for item in custom]
    valid_set = set(valid)
    ordered: list[str] = []
    if value is not None and not isinstance(value, list):
        if strict:
            raise ValueError("BBC News feed order must be a list.")
        value = []
    for raw in value or []:
        feed_id = str(raw or "").strip().casefold()
        if feed_id not in valid_set:
            if strict:
                raise ValueError(f"Unknown BBC News feed in order: {feed_id or 'empty'}")
            continue
        if feed_id not in ordered:
            ordered.append(feed_id)
    for feed_id in valid:
        if feed_id not in ordered:
            ordered.append(feed_id)
    return ordered


def _enabled_categories(
    value: Any,
    allowed_ids: set[str],
    *,
    strict: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        if strict:
            raise ValueError("News categories must be an ordered list.")
        return [feed_id for feed_id in DEFAULT_ENABLED_CATEGORIES if feed_id in allowed_ids]
    categories: list[str] = []
    for raw in value:
        category = str(raw).strip().casefold()
        if category not in allowed_ids:
            if strict:
                raise ValueError(f"Unknown BBC News category: {category or 'empty'}")
            continue
        if category not in categories:
            categories.append(category)
    if not categories:
        if strict:
            raise ValueError("At least one BBC News category must remain enabled.")
        return [feed_id for feed_id in DEFAULT_ENABLED_CATEGORIES if feed_id in allowed_ids]
    return categories


def public_news_config(config: dict[str, Any]) -> dict[str, Any]:
    news = _object(config.get("news"))
    custom = _custom_feeds(news.get("custom_feeds"))
    labels = _feed_labels(news.get("feed_labels"))
    order = _feed_order(news.get("feed_order"), custom)
    allowed = set(order)
    enabled_requested = _enabled_categories(news.get("enabled_categories"), allowed)
    enabled_set = set(enabled_requested)
    enabled = [feed_id for feed_id in order if feed_id in enabled_set]
    if not enabled:
        enabled = list(DEFAULT_ENABLED_CATEGORIES)

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
        "feed_order": order,
        "feed_labels": labels,
        "custom_feeds": custom,
        "show_summaries": _boolean(news.get("show_summaries"), True),
        "ticker": {
            "enabled": _boolean(ticker.get("enabled"), True),
            "speed": speed,
        },
    }


def _news_api_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Project Settings-owned News config onto the link-free kiosk API."""

    return {
        "enabled_categories": deepcopy(settings["enabled_categories"]),
        "default_category": settings["default_category"],
        "show_summaries": settings["show_summaries"],
        "ticker": deepcopy(settings["ticker"]),
    }


def submitted_news_config(config: dict[str, Any], payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("News settings must be a JSON object.")

    news = _object(config.get("news"))
    custom_source = payload.get("custom_feeds", news.get("custom_feeds", []))
    label_source = payload.get("feed_labels", news.get("feed_labels", {}))
    order_source = payload.get("feed_order", news.get("feed_order"))

    custom = _custom_feeds(custom_source, strict=True)
    labels = _feed_labels(label_source, strict=True)
    order = _feed_order(order_source, custom, strict=order_source is not None)
    allowed = set(order)

    enabled_raw = _enabled_categories(payload.get("enabled_categories"), allowed, strict=True)
    enabled_set = set(enabled_raw)
    enabled = [feed_id for feed_id in order if feed_id in enabled_set]

    default_category = str(
        payload.get("default_category") or news.get("default_category") or "top"
    ).strip().casefold()
    if default_category not in allowed:
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
        "feed_order": order,
        "feed_labels": labels,
        "custom_feeds": custom,
        "show_summaries": _boolean(payload.get("show_summaries"), True),
        "ticker": {
            "enabled": _boolean(ticker_payload.get("enabled"), True),
            "speed": speed,
        },
    }
    return updated


def _feed_definitions(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    labels = _object(settings.get("feed_labels"))
    custom_by_id = {
        item["id"]: item
        for item in settings.get("custom_feeds", [])
        if isinstance(item, dict) and item.get("id")
    }
    definitions: dict[str, dict[str, Any]] = {}
    for feed_id in settings.get("feed_order", []):
        if feed_id in BBC_FEEDS:
            entry = BBC_FEEDS[feed_id]
            definitions[feed_id] = {
                "id": feed_id,
                "label": str(labels.get(feed_id) or entry["label"]),
                "url": entry["url"],
                "built_in": True,
            }
            continue
        custom = custom_by_id.get(feed_id)
        if custom:
            definitions[feed_id] = {
                "id": feed_id,
                "label": custom["label"],
                "url": custom["url"],
                "built_in": False,
            }
    return definitions


def fetch_bbc_rss(url: str, timeout: float) -> bytes:
    safe_url = _safe_bbc_feed_url(url)
    if safe_url is None:
        raise ValueError("BBC News feed URL must be an approved feeds.bbci.co.uk News RSS source.")
    request_object = urllib.request.Request(
        safe_url,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9",
            "User-Agent": "A-Clockwork-Plex/1 bbc-news",
        },
    )
    opener = urllib.request.build_opener(_BBCFeedRedirectHandler())
    try:
        with opener.open(request_object, timeout=timeout) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else safe_url
            if _safe_bbc_feed_url(final_url) is None:
                raise RuntimeError("BBC News redirected outside the approved RSS source boundary.")
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


def parse_bbc_rss(
    payload: bytes | str,
    category: str,
    *,
    label: str | None = None,
) -> dict[str, Any]:
    category_id = str(category or "").strip().casefold()
    if not _CATEGORY_ID_RE.fullmatch(category_id):
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
        link = _child_text(item, "link")
        guid = _child_text(item, "guid")
        identity_source = guid or link or f"{title}|{published_at or ''}"
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
                "category": category_id,
                "article_url": _safe_article_url(link) or _safe_article_url(guid),
            }
        )
        if len(stories) >= MAX_ITEMS_PER_FEED:
            break

    image = _child(channel, "image")
    image_url = _safe_image_url(_child_text(image, "url")) if image is not None else None
    default_label = BBC_FEEDS.get(category_id, {}).get("label") or category_id
    display_label = _plain_text(label, maximum=MAX_FEED_LABEL_LENGTH) or default_label
    return {
        "category": category_id,
        "category_label": display_label,
        "source": "BBC News",
        "feed_title": _plain_text(_child_text(channel, "title"), maximum=120) or "BBC News",
        "feed_description": _plain_text(_child_text(channel, "description"), maximum=400),
        "feed_image_url": image_url,
        "last_build_at": _published_iso(_child_text(channel, "lastBuildDate")),
        "ttl_minutes": _feed_ttl(_child_text(channel, "ttl")),
        "items": stories,
    }


def _suggest_feed_label(title_value: Any, description_value: Any = None) -> str:
    """Derive a useful custom-feed label from BBC RSS channel metadata.

    BBC topic feeds are inconsistent: some put the section name in ``title``
    while others use the generic ``BBC News`` title and put the useful name in
    ``description`` (for example ``BBC News - Europe``). Prefer an informative
    title, then fall back to the description, stripping the common BBC News
    prefix in either case.
    """

    for value in (title_value, description_value):
        candidate = _plain_text(value, maximum=MAX_FEED_LABEL_LENGTH)
        for prefix in ("BBC News - ", "BBC News – ", "BBC News — "):
            if candidate.casefold().startswith(prefix.casefold()):
                candidate = candidate[len(prefix) :].strip()
                break
        if candidate and candidate.casefold() not in {"bbc", "bbc news"}:
            return candidate
    return "Custom BBC feed"


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

    def validate_feed(self, value: Any) -> dict[str, Any]:
        """Read and parse one candidate BBC News RSS URL without saving it."""

        safe_url = _safe_bbc_feed_url(value)
        if safe_url is None:
            raise ValueError(
                "Feed must be an HTTPS BBC News RSS URL on feeds.bbci.co.uk."
            )
        try:
            payload = self._fetcher(safe_url, float(DEFAULT_TIMEOUT_SECONDS))
            feed = parse_bbc_rss(payload, "custom-preview", label="Custom feed")
        except ValueError as exc:
            raise RuntimeError(f"BBC News RSS validation failed: {exc}") from exc
        suggested_id = _custom_feed_id(None, safe_url, strict=True)
        return {
            "ok": True,
            "label": _suggest_feed_label(
                feed.get("feed_title"),
                feed.get("feed_description"),
            ),
            "suggested_id": suggested_id,
            "story_count": len(feed.get("items", [])),
        }

    def _due(self, now: datetime) -> bool:
        expires_at = _parse_iso(self._cache.get("expires_at"))
        return expires_at is None or now >= expires_at

    @staticmethod
    def _required_categories(settings: dict[str, Any]) -> list[str]:
        required = list(settings["enabled_categories"])
        if settings["ticker"]["enabled"] and "top" not in required:
            required.append("top")
        return required

    def _missing_required_data(
        self,
        settings: dict[str, Any],
        definitions: dict[str, dict[str, Any]],
    ) -> bool:
        with self._lock:
            categories = deepcopy(_object(self._cache.get("categories")))
        for category in self._required_categories(settings):
            definition = definitions.get(category)
            state = _object(categories.get(category))
            if not definition:
                return True
            if state.get("feed_url") != definition["url"] or not state.get("feed"):
                return True
        return False

    def refresh(self, *, force: bool = False) -> dict[str, Any]:
        settings = public_news_config(self._load_config())
        definitions = _feed_definitions(settings)
        now = self._now()
        if (
            not force
            and not self._due(now)
            and not self._missing_required_data(settings, definitions)
        ):
            return self.snapshot()

        required = self._required_categories(settings)
        successes = 0
        failures = 0
        with self._lock:
            self._cache["last_attempt_at"] = _iso(now)

        for category in required:
            definition = definitions.get(category)
            with self._lock:
                previous = deepcopy(_object(_object(self._cache.get("categories")).get(category)))
            if not definition:
                failures += 1
                state = {
                    "status": "error",
                    "last_attempt_at": _iso(now),
                    "last_error": "BBC News feed configuration is unavailable.",
                }
                with self._lock:
                    self._cache.setdefault("categories", {})[category] = state
                continue

            if previous.get("feed_url") != definition["url"]:
                previous = {}
            try:
                payload = self._fetcher(definition["url"], float(DEFAULT_TIMEOUT_SECONDS))
                feed = parse_bbc_rss(payload, category, label=definition["label"])
            except Exception as exc:
                failures += 1
                state = previous
                state.update(
                    {
                        "feed_url": definition["url"],
                        "status": "stale" if state.get("feed") else "error",
                        "last_attempt_at": _iso(now),
                        "last_error": str(exc),
                    }
                )
            else:
                successes += 1
                state = {
                    "feed_url": definition["url"],
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
        definitions = _feed_definitions(settings)
        required = self._required_categories(settings)
        now = self._now()
        with self._lock:
            stored = deepcopy(self._cache)

        output_categories: dict[str, Any] = {}
        stale_cutoff = now - timedelta(hours=DEFAULT_STALE_HOURS)
        for category in settings["enabled_categories"]:
            definition = definitions.get(category)
            state = deepcopy(_object(_object(stored.get("categories")).get(category)))
            if not definition or state.get("feed_url") != definition["url"]:
                state = {}
            last_success = _parse_iso(state.get("last_success_at"))
            stale = bool(state.get("feed") and (last_success is None or last_success <= stale_cutoff))
            if stale:
                state["status"] = "stale"
            state["stale"] = stale
            state["label"] = definition["label"] if definition else category
            if state.get("feed"):
                state["feed"] = _public_feed(state.get("feed"))
                state["feed"]["category_label"] = state["label"]
            state.pop("feed_url", None)
            output_categories[category] = state

        top_definition = definitions.get("top")
        top_state = _object(_object(stored.get("categories")).get("top"))
        if not top_definition or top_state.get("feed_url") != top_definition["url"]:
            top_state = {}
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

        required_states: list[dict[str, Any]] = []
        for category in required:
            definition = definitions.get(category)
            state = _object(_object(stored.get("categories")).get(category))
            if not definition or state.get("feed_url") != definition["url"]:
                state = {}
            required_states.append(state)

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
            "settings": _news_api_settings(settings),
            "category_catalogue": [
                {"id": feed_id, "label": definition["label"]}
                for feed_id, definition in definitions.items()
            ],
            "categories": output_categories,
            "ticker": {
                "enabled": settings["ticker"]["enabled"],
                "speed": settings["ticker"]["speed"],
                "source_category": "top",
                "items": ticker_items,
            },
        }

    def article_url_for(self, story_id: Any) -> str | None:
        """Resolve one opaque public story id to its private trusted RSS URL."""

        candidate = str(story_id or "").strip().casefold()
        if not _STORY_ID_RE.fullmatch(candidate):
            return None
        with self._lock:
            categories = deepcopy(_object(self._cache.get("categories")))
        for state in categories.values():
            feed = _object(_object(state).get("feed"))
            items = feed.get("items", []) if isinstance(feed.get("items"), list) else []
            for item in items:
                if not isinstance(item, dict) or item.get("id") != candidate:
                    continue
                article_url = _safe_article_url(item.get("article_url"))
                if article_url is not None:
                    return article_url
        return None

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

    @app.post("/api/news/feed/validate")
    def api_news_feed_validate():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Feed validation requires a JSON object."}), 400
        try:
            result = service.validate_feed(payload.get("url"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/news/story/<story_id>/qr.svg")
    def api_news_story_qr(story_id: str):
        article_url = service.article_url_for(story_id)
        if article_url is None:
            return jsonify({"ok": False, "error": "No HTTPS article link is available for this story."}), 404
        try:
            svg = render_article_qr_svg(article_url)
        except ValueError:
            return jsonify({"ok": False, "error": "RSS article link was rejected."}), 404
        response = Response(svg, mimetype="image/svg+xml")
        response.headers["Cache-Control"] = "private, max-age=300"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
