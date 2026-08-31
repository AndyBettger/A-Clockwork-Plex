# BBC News architecture

## Status

Checkpoint #92 is in progress. The feed/cache/API foundation passed automated gates and the commissioned appliance successfully fetched the current real BBC feeds on 31 August 2026. The touchscreen News page and News Settings workspace are implemented on the feature branch but remain subject to physical 1280×720 acceptance before #92 can close.

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

## Public story model

The public `/api/news` story model exposes only:

- opaque story id;
- title/headline;
- plain-text summary;
- published timestamp;
- category.

Article URLs and GUID values are not exposed. The browser cannot therefore turn a headline into outbound kiosk navigation without changing the backend contract first.

The touchscreen detail panel shows only the same feed-owned title, category, published timestamp and summary. It has no article anchor, no external-navigation action and no full-article scraping. Full BBC article bodies remain outside the supported RSS boundary unless BBC provides a suitable authorised/public syndication source in future.

## News screen ownership

`app/news_ui.py` registers `/news` as a normal A Clockwork Plex screen and adds `news` to the existing dashboard/screen-projection mode sets. It deliberately reuses the established manual-screen lease authority rather than adding a parallel navigation owner.

News is manually leasable so an active background audio session does not immediately replace the page while the user is reading it. It is deliberately **not** added to the startup/idle-return destination set at checkpoint #92; News is an information surface the user opens, not a new automatic appliance destination.

The normal main navigation includes News alongside Clock, Weather, Plexamp, AirPlay and Settings.

## Touchscreen presentation

`app/templates/news.html`, `app/static/css/news.css` and `app/static/js/news.js` own the News presentation:

- Settings-style category rail on the left;
- Top Stories, UK, World, Science and Technology choices filtered by the saved enabled-category model;
- scrollable headline cards showing category, published time, title and optional feed summary;
- local feed-detail modal on story tap;
- explicit ready/degraded/stale/update state;
- Top Stories ticker fixed to the bottom of the News surface;
- theme-variable styling and 1280×720-first geometry.

All story title/summary rendering uses DOM `textContent`; RSS markup is already reduced to plain text server-side. The browser performs no BBC article fetches.

Real BBC feeds can contain repeated entries and older/promotional records further down the source order. The raw cached feed is preserved unchanged. Presentation performs semantic de-duplication by normalised title plus published timestamp and preserves the BBC feed order. The main list shows at most the leading 24 unique entries and the ticker at most the leading 12 unique Top Stories; this keeps the touchscreen/ticker focused without rewriting source data.

## BBC branding

The parser accepts a feed-supplied image URL only when it is HTTPS and on an allowed BBC hostname. The News client revalidates the hostname before assigning the image source and falls back to plain `BBC NEWS` text on absence or image failure.

The RSS/content cache is stored locally. The small feed-supplied BBC logo image itself is **not** currently copied into ACP's disk cache; it is requested directly from the validated BBC image URL when the News page is displayed. This distinction is intentional and documented rather than implying offline logo caching that does not exist.

## Ticker

The ticker is derived from the same cached Top Stories feed. It has no independent network source and exposes only story id, title, published timestamp and `top` category. Top Stories remains a fetch dependency for the ticker even when the user hides Top Stories from the News category rail.

The ticker is general BBC News, not labelled as a breaking-news wire. Presentation maps the saved speed choices to bounded client-side motion rates and honours the browser reduced-motion preference. Slow/Normal/Fast remain subject to physical tuning on the Touch Display 2.

## Settings ownership

User-owned News preferences are part of the revisioned unified Settings model:

- enabled categories;
- default category;
- show summaries;
- ticker enabled;
- ticker speed (`slow`, `normal`, `fast`).

At least one category must remain enabled and the default category must be one of the enabled categories. Refresh cadence, request timeout, stale threshold and cache policy remain appliance-owned rather than user-facing tuning knobs.

`app/static/js/settings-news.js` contributes a News workspace to the existing Settings shell and registers the `news` domain with the established `ACPUnifiedSettings` transaction owner. It has no network/save path of its own. News preference changes are committed inside the existing one-write Settings transaction and then wake the News background worker. Saving Settings never waits for a BBC network request.

News preferences are included in portable configuration backup/restore; downloaded RSS/cache data is generated runtime state and is excluded.

## Failure boundary

BBC/network/XML failure must never affect the rest of the appliance. A failed category keeps its previous successful feed when available and records an explicit degraded/stale/error state. The News page labels stale data rather than replacing it with invented content.

## Remaining acceptance

The backend/live-feed boundary is proven. Checkpoint #92 still requires physical 1280×720 verification of:

- left-rail layout and category switching;
- touch scrolling and local detail modal;
- feed-supplied logo/fallback behaviour;
- News Settings save/discard and category constraints;
- summary visibility;
- ticker on/off and Slow/Normal/Fast feel;
- night/dimming/theme treatment;
- manual screen lease and idle-return behaviour;
- no regression to Clock, Weather, Plexamp, AirPlay or alarms.
