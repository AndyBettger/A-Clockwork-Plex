# BBC News architecture

## Status

Checkpoint #92 foundation is under development. The first slice owns feed fetching, safe RSS normalisation, last-good caching, a read-only API and the user-owned News preference model. Touch presentation follows after the backend gate is green.

## Feed authority

A Clockwork Plex uses a fixed allow-list of public BBC News RSS feeds only:

- Top Stories
- UK
- World
- Science & Environment
- Technology

The appliance does not accept arbitrary feed URLs and does not scrape BBC News article HTML.

`app/news_feed.py` is the single network/cache authority. It fetches feeds in a background worker, normalises them into bounded plain-text records, writes the last-good state atomically to `bbc-news-cache.json`, and preserves cached content when a later fetch fails.

## Public story model

The public `/api/news` story model exposes only:

- opaque story id;
- title/headline;
- plain-text summary;
- published timestamp;
- category.

Article URLs and GUID values are not exposed. The bridge therefore cannot accidentally turn a headline into outbound kiosk navigation. A later touchscreen detail view may show the full feed summary, but full BBC article bodies remain outside the supported RSS boundary unless BBC provides a suitable authorised/public syndication source.

## Ticker

The ticker is derived from the same cached Top Stories feed. It has no independent network source and exposes only the story id, title, published timestamp and `top` category. Top Stories is fetched for the ticker even when the user hides Top Stories from the News category rail.

The ticker is general BBC News, not labelled as a breaking-news wire.

## Settings ownership

User-owned News preferences are part of the revisioned unified Settings model:

- enabled categories;
- default category;
- show summaries;
- ticker enabled;
- ticker speed (`slow`, `normal`, `fast`).

At least one category must remain enabled and the default category must be one of the enabled categories. Refresh cadence, request timeout, stale threshold and cache policy remain appliance-owned rather than user-facing tuning knobs.

News preference changes are committed inside the existing one-write Settings transaction and then wake the News background worker. Saving Settings never waits for a BBC network request.

## Failure boundary

BBC/network/XML failure must never affect the rest of the appliance. A failed category keeps its previous successful feed when available and records an explicit degraded/stale/error state. The News page will label stale data rather than replacing it with invented content.

## Planned touchscreen presentation

The agreed presentation direction is:

- Settings-style left category rail;
- BBC feed-supplied branding at the top-left where safely available, with text fallback;
- main scrolling headline/summary pane;
- tap-to-open ACP detail presentation using feed content only;
- no outbound article navigation;
- Top Stories ticker fixed to the News surface initially;
- 1280×720 physical acceptance before promotion.
