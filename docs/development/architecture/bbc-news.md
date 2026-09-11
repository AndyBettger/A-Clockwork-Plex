# BBC News architecture

## Status

Checkpoint #92 is physically accepted on the commissioned 1280×720 appliance. The feed/cache/API foundation, touchscreen News page, News Settings workspace, startup/idle integration and stale-cache behaviour have all been exercised on the Raspberry Pi. The final acceptance pass completed across 31 August and 1 September 2026.

The post-#92 article hand-off enhancement on `feature/news-article-qr` passed its initial commissioned-appliance acceptance on 11 September 2026: the normal repeat `bash setup.sh` convergence completed successfully and its final appliance verifier reported `APPLIANCE_VERIFY=PASS` with **0 failures / 0 warnings**; the locally generated QR rendered and scanned from the Touch Display 2; and the owner's iPhone handed the ordinary BBC HTTPS article link directly to the installed BBC News app rather than Safari. A later live BBC Science feed specimen — **“El Niño likely to cause wetter and warmer-than-normal autumn”** — exposed that the first implementation was too narrow because BBC legitimately supplied a `/weather/articles/...` destination rather than `/news/...`. The branch now trusts absolute HTTPS destinations supplied by the fixed BBC RSS feeds, with `<link>` first and a valid HTTPS `<guid>` fallback. A focused physical recheck of that Weather specimen remains before PR #11 integration.

## Feed authority

A Clockwork Plex uses a fixed allow-list of public BBC News RSS feeds only:

- Top Stories
- UK
- World
- Science & Environment
- Technology

The appliance does not accept arbitrary feed URLs and does not scrape BBC News article HTML.

`app/news_feed.py` is the single network/cache authority. It fetches feeds in a background worker, normalises them into bounded plain-text records, writes the last-good state atomically to `bbc-news-cache.json`, and preserves cached content when a later fetch fails.

The commissioned appliance live gate on 31 August 2026 returned all five categories as ready with fresh last-success state and a running worker. A recursive check of the public payload found no `url`, `link` or `guid` keys.

The article-QR follow-up increments the private cache schema because the cache can retain one additional internal field: the trusted RSS article HTTPS destination. The trusted-destination refinement advances the schema again so previously rejected non-`/news/` BBC destinations are rebuilt from RSS immediately rather than waiting for an old cached `null` hand-off to age out. The public API projection deliberately strips this private field before JSON is returned.

## Public story model

The public `/api/news` story model exposes only:

- opaque story id;
- title/headline;
- plain-text summary;
- published timestamp;
- category.

Article URLs and GUID values remain absent from `/api/news`. The browser therefore still cannot turn a headline into arbitrary outbound kiosk navigation.

The touchscreen detail panel shows the same feed-owned title, category, published timestamp and summary. It has no article anchor, no external-navigation action and no full-article scraping. Full BBC article bodies remain outside the supported RSS boundary unless BBC provides a suitable authorised/public syndication source in future.

## Article QR hand-off

The QR enhancement deliberately keeps article navigation off the kiosk.

The trust boundary is the RSS source, not a hard-coded article-path catalogue. ACP itself fetches only its configured fixed BBC RSS feeds. For each RSS item, the hand-off destination is selected as follows:

1. use `<link>` when it is a syntactically valid absolute HTTPS URL;
2. otherwise use `<guid>` only when the GUID itself is a syntactically valid absolute HTTPS URL;
3. otherwise retain no hand-off destination and show the ordinary local detail dialog without a QR.

The accepted URL is preserved exactly as supplied by the feed, including any query string or fragment, rather than ACP guessing which BBC URL components are disposable. Relative URLs, non-HTTPS URLs, embedded username/password components, malformed ports, whitespace/control-character values and otherwise malformed destinations are rejected. There is deliberately no `/news/` path restriction: the live El Niño specimen demonstrated that a BBC News RSS feed can legitimately syndicate a BBC Weather article such as `https://www.bbc.co.uk/weather/articles/...`.

This broader destination trust does **not** make the appliance a generic URL-to-QR service. The browser still asks only for:

```text
/api/news/story/<opaque-story-id>/qr.svg
```

`BBCNewsFeedService.article_url_for()` resolves that id against the private in-memory/cache state and revalidates the stored HTTPS destination. The route accepts no URL argument and `/api/news` still exposes no article URL or GUID.

QR SVG is generated locally with the Python `qrcode` package using a normal four-module quiet-zone border and medium error correction. No Google Charts, QR SaaS, redirector or other third party receives the selected article URL.

The QR contains the ordinary HTTPS address supplied by the BBC RSS item rather than an undocumented BBC custom URL scheme. That keeps the hand-off standards-based: iOS can pass a supported Universal Link to an installed BBC app when the app/site association permits it, otherwise the same address opens normally in the browser. Initial physical acceptance on the owner's iPhone confirmed that a BBC News article URL was claimed directly by the installed BBC News app.

The detail panel does not reveal an empty QR placeholder. It requests the local SVG only when a story is opened and shows the hand-off panel only after that image has loaded successfully. Missing/rejected links therefore leave the pre-existing title/summary dialog intact.

## News screen ownership

`app/news_ui.py` registers `/news` as a normal A Clockwork Plex screen and adds `news` to the existing dashboard/screen-projection mode sets. It deliberately reuses the established manual-screen lease authority rather than adding a parallel navigation owner.

News is manually leasable so an active background audio session does not immediately replace the page while the user is reading it. Following the physical follow-up, News is also a supported **Startup screen** and **Idle return screen** destination through the existing dashboard, unified-Settings, startup-bootstrap and screen-projection authorities. The commissioned appliance physically proved idle return to News and a real reboot/startup into News.

The normal main navigation includes News alongside Clock, Weather, Plexamp, AirPlay and Settings.

## Touchscreen presentation

`app/templates/news.html`, `app/static/css/news.css` and `app/static/js/news.js` own the News presentation:

- Settings-style category rail on the left;
- Top Stories, UK, World, Science and Technology choices filtered by the saved enabled-category model;
- scrollable headline cards showing category, published time, title and optional feed summary;
- local feed-detail modal on story tap;
- optional locally generated article QR hand-off panel inside that modal;
- explicit ready/degraded/stale/source-time state;
- theme-aware BBC feed-time pill;
- Weather-style synchronized vertical scroll rail/thumb while normal touch scrolling remains on the story list;
- Top Stories ticker fixed to the bottom of the News surface when enabled;
- ticker-off removes the whole strip and returns its height to the category/story area;
- theme-variable styling and 1280×720-first geometry.

All story title/summary rendering uses DOM `textContent`; RSS markup is already reduced to plain text server-side. The browser performs no BBC article fetches. The QR image request is looped back to the appliance itself; the phone, not Chromium, follows the encoded RSS address after scanning.

Real BBC feeds can contain repeated entries and older/promotional records further down the source order. The raw cached feed is preserved unchanged apart from bounded normalisation/private article-link metadata. Presentation performs semantic de-duplication by normalised title and preserves the BBC feed order. The main list shows at most the leading 24 unique entries and the ticker at most the leading 12 unique Top Stories; this keeps the touchscreen/ticker focused without rewriting source data.

## BBC branding

The parser accepts a feed-supplied image URL only when it is HTTPS and on an allowed BBC hostname. The News client revalidates the hostname before assigning the image source and falls back to plain `BBC NEWS` text on absence or image failure.

The RSS/content cache is stored locally. The small feed-supplied BBC logo image itself is **not** currently copied into ACP's disk cache; it is requested directly from the validated BBC image URL when the News page is displayed. This distinction is intentional and documented rather than implying offline logo caching that does not exist.

## Ticker

The ticker is derived from the same cached Top Stories feed. It has no independent network source and exposes only story id, title, published timestamp and `top` category. Top Stories remains a fetch dependency for the ticker even when the user hides Top Stories from the News category rail.

The ticker is general BBC News, not labelled as a breaking-news wire. Presentation maps the saved speed choices to bounded client-side motion rates and honours the browser reduced-motion preference. Slow/Normal/Fast were physically checked on the Touch Display 2 and accepted.

## Settings ownership

User-owned News preferences are part of the revisioned unified Settings model:

- enabled categories;
- default category;
- show summaries;
- ticker enabled;
- ticker speed (`slow`, `normal`, `fast`).

At least one category must remain enabled and the default category must be one of the enabled categories. Refresh cadence, request timeout, stale threshold and cache policy remain appliance-owned rather than user-facing tuning knobs.

`app/static/js/settings-news.js` contributes a News workspace to the existing Settings shell and registers the `news` domain with the established `ACPUnifiedSettings` transaction owner. It has no network/save path of its own. News preference changes are committed inside the existing one-write Settings transaction and then wake the News background worker. Saving Settings never waits for a BBC network request.

News preferences are included in portable configuration backup/restore; downloaded RSS/cache data, including private article-link metadata, is generated runtime state and is excluded.

## Failure boundary

BBC/network/XML failure must never affect the rest of the appliance. A failed category keeps its previous successful feed when available and records an explicit degraded/stale/error state. The News page labels stale data rather than replacing it with invented content.

QR generation is also optional presentation state. A missing/rejected article link or a QR-generation failure must not prevent the story summary dialog from opening and must not affect the News feed/cache worker.

A real commissioned-appliance connectivity interruption physically proved the main News failure boundary: while Wi-Fi was unavailable, the News page retained cached stories and ticker content, exposed the cached/stale state in the lower-left status pill, and retained the last BBC feed time. Normal fresh updates resumed after Wi-Fi reconnected.

The same incident also exposed a separate appliance-storage concern: the Pi root filesystem had previously remounted read-only, causing unrelated ACP state writes to fail. That storage-resilience investigation is intentionally tracked as future appliance work rather than attributed to BBC News.

## Physical acceptance

Checkpoint #92 physical acceptance at 1280×720 confirms:

- left-rail layout and category switching;
- touch scrolling, Weather-style custom vertical scrollbar and local detail modal;
- feed-supplied BBC logo/fallback presentation and source-time/status pills;
- News Settings overview plus Sections and Presentation subpages;
- category enablement/default-category constraints;
- summary visibility;
- ticker on/off, reclaimed layout height and Slow/Normal/Fast speeds;
- manual News navigation/lease behaviour;
- News as both Startup and Idle return destination, including a real reboot into News;
- cached/stale presentation during a real Wi-Fi interruption with stories/ticker retained;
- navigation back to the other dashboard surfaces without regression.

The initial article-QR follow-up acceptance on 11 September 2026 confirmed:

- normal repeat `bash setup.sh` convergence completed successfully on the commissioned appliance and the final verifier reported `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings**;
- the article detail/QR presentation rendered successfully at the production 1280×720 geometry;
- a QR scanned successfully from the Touch Display 2;
- the scanned BBC News HTTPS link was claimed by the installed BBC News app on the owner's iPhone rather than opening in Safari;
- kiosk Chromium retains no article anchor/navigation action; the outbound hand-off remains phone-owned.

A subsequent live feed check found a missing QR for **“El Niño likely to cause wetter and warmer-than-normal autumn”** because its BBC RSS `<link>` is a BBC Weather article outside `/news/`. The trusted-RSS destination refinement now covers that case and adds HTTPS-GUID fallback. The remaining focused gate is to pull the refined branch on the commissioned Pi, let the schema-3 cache rebuild, confirm that exact Weather story now gains a QR, scan it successfully, and verify ACP Chromium remains on the kiosk.

Checkpoint #92 itself remains complete. PR #11 stays Draft until this final QR-destination recheck passes.
