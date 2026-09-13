# BBC News architecture

## Status

Checkpoint #92 is physically accepted on the commissioned 1280×720 appliance. The original feed/cache/API foundation, touchscreen News page, News Settings workspace, startup/idle integration, stale-cache behaviour and the later article-QR hand-off have all passed the Raspberry Pi physical gate.

The article hand-off was physically rechecked on 11 September 2026 after a live BBC Science specimen — **“El Niño likely to cause wetter and warmer-than-normal autumn”** — showed that BBC News RSS can legitimately point at a BBC Weather article. The accepted design therefore trusts syntactically valid absolute HTTPS destinations supplied by the already trusted BBC RSS item, using `<link>` first and a valid HTTPS `<guid>` fallback. Normal BBC News links opened the installed BBC News app on the owner's iPhone; the BBC Weather specimen opened Chrome. Kiosk Chromium remained inside A Clockwork Plex throughout.

A bounded post-#92 **configurable sections** follow-up is now active on `feature/news-custom-feeds` / draft PR #12. Software implementation is complete, and the first commissioned-appliance pass on 13 September 2026 proved repeat installation plus the enlarged built-in catalogue, rename/reorder/default transaction and saved News rendering. That pass also exposed two bounded presentation follow-ups — the News section rail needed its own touch-scroll region and the feed-editor cards needed more vertical separation — and established the product preference that **News feeds belongs inside Settings → News rather than Advanced**. Those follow-ups are implemented and passed the complete automated gate in **Tests #4774**; the commissioned 1280×720 physical recheck and remaining custom-feed/portability gates are still open. PR #12 must remain draft until those gates pass.

## Feed authority

`app/news_feed.py` is the single BBC News network/cache authority. It fetches feeds in a background worker, normalises them into bounded plain-text records, writes last-good state atomically to `bbc-news-cache.json`, and preserves cached content when a later fetch fails.

The original five feeds remain the out-of-box enabled set:

- Top Stories;
- UK;
- World;
- Science & Environment;
- Technology.

The configurable-sections follow-up expands the curated built-in catalogue with:

- England;
- Scotland;
- Wales;
- Northern Ireland;
- Business;
- Politics;
- Health;
- Education;
- Entertainment & Arts.

Those additional feeds are available to the owner but are **not enabled by default**, so an upgraded appliance preserves the accepted five-section starting experience unless the owner deliberately changes it.

### Custom BBC feed boundary

ACP still does **not** become a general-purpose RSS reader. An advanced custom source is accepted only when `_safe_bbc_feed_url()` proves all of the following:

- scheme is HTTPS;
- hostname is exactly `feeds.bbci.co.uk`;
- no username/password is embedded;
- port is absent or 443;
- no query string or fragment is present;
- path is `/news/rss.xml` or a `/news/.../rss.xml` path;
- path contains no doubled, current-directory or parent-directory traversal segments.

This intentionally allows BBC-owned topic feeds such as `/news/topics/.../rss.xml` while rejecting arbitrary internet hosts, BBC Sport feeds, HTTP sources and URL tricks intended to escape the News source boundary.

`fetch_bbc_rss()` uses the same validator before any request. Its redirect handler also validates each redirect target **before urllib follows it**, and the final response URL is validated again. A custom-feed feature therefore cannot be used as an SSRF/open-fetch primitive by entering a BBC-looking URL that redirects elsewhere.

The appliance still does not scrape BBC article HTML.

## Configurable feed model

The revisioned `news` Settings domain now owns:

```text
enabled_categories
default_category
feed_order
feed_labels
custom_feeds
show_summaries
ticker.enabled
ticker.speed
```

`feed_order` is the logical ordered list of built-in and custom section ids. Built-in renames are stored separately in `feed_labels`, so ACP never has to mutate the curated catalogue itself. A custom feed is stored as a bounded logical record:

```json
{
  "id": "custom-…",
  "label": "Display name",
  "url": "https://feeds.bbci.co.uk/news/.../rss.xml"
}
```

Custom ids are stable configuration identifiers rather than display labels. The default section must be enabled, at least one section must remain enabled, duplicate custom ids are rejected and a custom URL may not duplicate a curated built-in source.

The News page receives the enabled order and a link-free `{id, label}` catalogue. It does not need the underlying source URL in order to render the section rail.

## Candidate feed validation

New or edited custom sources have a deliberate read-only preflight before the Settings transaction can save them.

The Settings UI calls:

```text
POST /api/news/feed/validate
```

with only the candidate URL. The endpoint:

1. applies the exact BBC feed-source validator described above;
2. performs a bounded read of that BBC RSS source;
3. parses it through the normal RSS parser without changing cache or configuration;
4. derives a friendly suggested title from the feed title;
5. derives a deterministic `custom-<hash>` logical id from the canonical feed URL;
6. returns only safe validation metadata (`label`, suggested id and story count).

The validation response does **not** echo the source URL. A non-BBC URL is rejected before the network fetcher is called.

The browser marks a custom row as checked only for the exact URL that passed this preflight. Editing the URL clears that state. `Save Changes` refuses to collect the News domain while any custom source is new/changed and unchecked. This gives normal interactive configuration an explicit “does this really look like a BBC News RSS feed?” gate without moving network fetching into the unified Settings commit itself.

Portable Restore is intentionally different: it restores an already validated logical ACP configuration through the normal server validator and does not require BBC connectivity during the Restore transaction. The News worker checks/fetches the restored source afterwards using the same source boundary. This preserves offline/cache-first Restore semantics.

## Cache ownership

The configurable-source work advances the private cache schema to version 4.

Each cached category state privately remembers the source `feed_url` that produced it. If a configured source changes, a last-good feed belonging to the old URL is not presented as if it came from the replacement source. A newly required section is also considered immediately due when it has no matching cached data, rather than waiting for the global refresh timer.

Source URLs are runtime/private cache metadata. Public snapshots strip `feed_url` before JSON projection.

Downloaded RSS/cache state remains generated runtime state and is excluded from portable Backup/Restore.

## Public story model

The public `/api/news` story model remains deliberately small:

- opaque story id;
- title/headline;
- plain-text summary;
- published timestamp;
- category id.

Article URLs and GUID values are absent. The configurable-feed source URLs, rename map and custom-feed records are also absent from the kiosk News API. `/api/news` exposes only the presentation settings the News screen actually needs plus the link-free category catalogue.

This preserves the original security boundary: the touchscreen browser cannot turn feed metadata into arbitrary outbound kiosk navigation.

## Article QR hand-off

The QR enhancement deliberately keeps article navigation off the kiosk.

For each RSS item ACP chooses the hand-off destination as follows:

1. use `<link>` when it is a syntactically valid absolute HTTPS URL;
2. otherwise use `<guid>` only when the GUID itself is a syntactically valid absolute HTTPS URL;
3. otherwise retain no hand-off destination and show the ordinary local detail dialog without a QR.

The destination is preserved exactly as supplied by the trusted RSS item, including any query string or fragment. Relative URLs, non-HTTPS URLs, embedded username/password components, malformed ports, whitespace/control-character values and otherwise malformed destinations are rejected.

This destination trust remains distinct from feed-source trust. ACP may display QR hand-offs to an HTTPS destination syndicated by a trusted BBC feed (including the physically proven BBC Weather case), while the **feed itself** may only be fetched from the strict `feeds.bbci.co.uk/news/.../rss.xml` boundary.

The browser asks only for:

```text
/api/news/story/<opaque-story-id>/qr.svg
```

`BBCNewsFeedService.article_url_for()` resolves that id against private cache state and revalidates the stored HTTPS destination. The route accepts no URL argument, and `/api/news` still exposes no article URL or GUID.

QR SVG is generated locally with the Python `qrcode` package. No QR SaaS, redirector or third party receives the selected article URL.

The QR contains the ordinary HTTPS address. iOS may pass a supported Universal Link to an installed BBC app; otherwise it opens in the browser. Physical acceptance on the owner's iPhone has proved both outcomes depending on URL ownership. ACP itself does not decide which app receives the scanned HTTPS link.

The detail panel shows its QR hand-off only after the local SVG loads successfully. Missing/rejected destinations therefore leave the existing title/summary dialog intact rather than showing a broken QR placeholder.

## News screen ownership

`app/news_ui.py` registers `/news` as a normal A Clockwork Plex screen and reuses the established dashboard/screen-projection authority rather than creating a parallel navigation owner.

News is manually leasable so background audio does not immediately replace a page the owner is reading. News is also a supported **Startup screen** and **Idle return screen**. The commissioned appliance has physically proved both idle return to News and a real reboot/startup into News.

The normal navigation includes News alongside Clock, Weather, Plexamp, AirPlay and Settings.

## Touchscreen presentation

`app/templates/news.html`, `app/static/css/news.css`, `app/static/css/news-custom-feeds.css` and `app/static/js/news.js` own the 1280×720-first News presentation:

- Settings-style section rail on the left, driven by the saved enabled order and display labels;
- the section rail has its own bounded vertical touch-scroll region when enabled sections exceed the available height;
- scrollable headline cards showing section, published time, title and optional feed summary;
- local detail modal on story tap;
- optional locally generated article QR hand-off panel;
- ready/degraded/stale/source-time state;
- Weather-style synchronized vertical scrollbar while normal touch scrolling remains available;
- Top Stories ticker fixed to the bottom when enabled;
- ticker-off returns that height to the section/story area;
- theme-variable presentation.

All story title/summary rendering uses DOM `textContent`; RSS markup is reduced to plain text server-side. The browser performs no BBC article fetches. The QR image request is loopback to ACP; the phone follows the encoded RSS destination after scanning.

Real feeds may contain repeated or promotional entries. The cache keeps bounded normalised source order while presentation de-duplicates by normalised title. The main list shows at most the leading 24 unique entries and the ticker at most the leading 12 unique Top Stories.

## BBC branding

The parser accepts a feed-supplied image URL only when it is HTTPS and on an allowed BBC image hostname. The News client revalidates that hostname before assigning the image source and falls back to plain `BBC NEWS` text if the image is absent or fails.

RSS/content is cached locally. The small feed-supplied logo itself is not copied into ACP's disk cache; it is requested from the validated BBC image URL when the News page is displayed.

## Ticker

The ticker remains deliberately independent of section customisation. It is always derived from the cached **Top Stories** feed and has no second network source.

Top Stories therefore remains a fetch dependency whenever the ticker is enabled, even if the owner hides Top Stories from the News section rail or chooses another default section. Custom feeds cannot replace the ticker source in this follow-up.

## Settings ownership

`app/static/js/settings-news.js` registers the `news` domain with the existing `ACPUnifiedSettings` transaction owner. It has no separate save path.

The News workspace owns enabled sections, default section, summaries, ticker presentation and the **News feeds** subpage for section rename/order plus the bounded custom BBC RSS editor. The initial software build placed that editor under Advanced; the first commissioned 1280×720 pass established that this is ordinary News configuration, so the feature branch now presents it within Settings → News before the shared Settings navigation binds.

The feed editor list uses deliberate vertical card spacing at 1280×720 so adjacent feed records retain a clear visual boundary.

After a custom source has passed its explicit preflight, `Save Changes` still performs the existing single revisioned Settings transaction. Saving Settings does not wait for the normal background News refresh; it wakes the News worker after the validated configuration commit.

The full logical News configuration is portable ACP state. Portable Backup now carries:

- enabled ids;
- default id;
- feed order;
- built-in display-name overrides;
- custom BBC feed logical records;
- summary setting;
- ticker setting/speed.

Restore compares and reapplies those fields through the normal News Settings validator. Reset derives its News target from version-controlled `config.example.json`, returning the appliance to the original five enabled sections, curated default ordering, no renames and no custom feeds.

RSS downloads/cache/private article hand-off metadata are excluded from Backup/Restore/Reset portability.

## Failure boundary

BBC/network/XML failure must never affect the rest of the appliance. A failed active section keeps its previous successful feed only when that cache belongs to the same configured source, and records an explicit degraded/stale/error state. The News page labels stale data rather than inventing content.

A failed custom-feed preflight does not change configuration or cache. A missing/rejected article link or QR-generation failure does not prevent the story summary dialog from opening and does not affect the feed worker.

The previously accepted real Wi-Fi interruption proved the cache-first boundary: cached stories and ticker remained visible with stale/cached status and normal fresh updates resumed after connectivity returned.

## Physical acceptance

### Accepted #92 core

Physical acceptance at 1280×720 confirms:

- original five-section rail and switching;
- touch scrolling/custom vertical scrollbar/local detail modal;
- BBC branding/fallback and source-time/status pills;
- News Settings Sections and Presentation pages;
- enablement/default constraints;
- summary visibility;
- ticker on/off and Slow/Normal/Fast speeds;
- manual News navigation/lease behaviour;
- News as Startup and Idle return, including real reboot;
- cache/stale behaviour during real Wi-Fi loss;
- normal navigation to the rest of the appliance.

### Accepted article QR follow-up

Physical acceptance confirms:

- repeat `bash setup.sh` convergence with `APPLIANCE_VERIFY=PASS`, 0 failures / 0 warnings;
- article detail/QR geometry at 1280×720;
- QR scanning from the Touch Display 2;
- normal BBC News article URLs opening in the installed BBC News app on the owner's iPhone;
- the live BBC Weather destination from the Science feed receiving a QR and opening correctly in Chrome;
- kiosk Chromium remaining in ACP;
- no article anchor or arbitrary URL-to-QR input in the kiosk.

### Configurable-sections follow-up — physical gate open

First commissioned pass on 13 September 2026, head `2ea286211cb8712553dce3e131598c06b2d6aa4c`:

- [x] `bash setup.sh` converged with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings**;
- [x] the enlarged curated catalogue rendered in Settings at 1280×720;
- [x] Business could be enabled, renamed to **Business Test**, moved in the saved order and selected as the default section;
- [x] the News page then opened the renamed Business feed with the saved rail order and correct Business stories;
- [x] the Top Stories ticker remained visibly independent while Business Test was active;
- [ ] the larger enabled rail was not fully reachable because the category list itself did not scroll;
- [ ] feed-editor cards were visually too tightly packed and the editor's initial Advanced placement was rejected in favour of Settings → News.

The branch now contains bounded follow-up styling/placement for those two open presentation findings. Before draft PR #12 may leave draft, the commissioned appliance must still prove:

- the News-owned **News feeds** subpage, feed-card spacing and touch-scrollable section rail at 1280×720;
- a real BBC-owned News RSS URL can be added using the touch keyboard;
- **Check feed** validates that source, derives a sensible label/stable id and blocks an unchecked or non-BBC source;
- a mixed built-in + custom configuration renders stories in the saved rail order;
- the Top Stories ticker remains Top Stories regardless of active/default/custom section;
- a story delivered by the added BBC feed retains the accepted local QR hand-off behaviour when the RSS item supplies a usable HTTPS destination;
- changing a custom source cannot make cache from the old source appear under the new source;
- portable Backup contains the logical order/labels/custom feed records and Reset/Restore Preview ownership remains truthful;
- News Settings, touch keyboard and Save/Discard interaction remain usable without 1280×720 overflow.

Automated evidence:

- **Tests #4753** passed the first complete implementation gate on `58e47e800ff13ed98f0834a7f429d958b7927ac0`;
- **Tests #4765** passed compile, JavaScript/page wiring/shell checks and the full regression suite on physical-test head `2ea286211cb8712553dce3e131598c06b2d6aa4c`;
- **Tests #4774** passed compile, JavaScript/page wiring/shell checks and the full regression suite on post-physical-follow-up implementation/catalogue head `bc2f5b7c7a4e49bec9376fa49e1c73b279051e8a`.

Until the remaining gate passes, configurable sections are **software implemented / partial physical-acceptance stage**, not fully accepted product behaviour.
