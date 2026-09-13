# BBC News architecture

## Status

Checkpoint #92 is physically accepted on the commissioned 1280×720 appliance. The original feed/cache/API foundation, touchscreen News page, News Settings workspace, startup/idle integration, stale-cache behaviour and the later article-QR hand-off have all passed the Raspberry Pi physical gate.

The article hand-off was physically rechecked on 11 September 2026 after a live BBC Science specimen — **“El Niño likely to cause wetter and warmer-than-normal autumn”** — showed that BBC News RSS can legitimately point at a BBC Weather article. The accepted design therefore trusts syntactically valid absolute HTTPS destinations supplied by the already trusted BBC RSS item, using `<link>` first and a valid HTTPS `<guid>` fallback. Normal BBC News links opened the installed BBC News app on the owner's iPhone; the BBC Weather specimen opened Chrome. Kiosk Chromium remained inside A Clockwork Plex throughout.

A bounded post-#92 **configurable sections** follow-up is active on `feature/news-custom-feeds` / draft PR #12. Software implementation is complete and repeated commissioned-appliance passes on 13 September 2026 have proved repeat installation, the enlarged catalogue, rename/reorder/default behaviour, saved News rendering, the News-owned custom-feed editor, the shared custom category scrollbar and a live Europe custom feed. The Europe source passed **Check feed**, was automatically named **Europe** from its RSS description, was enabled alongside built-in sections and rendered real Europe stories while the ticker remained tied to Top Stories. The final physical presentation pass requested a more compact ordering workflow: the large feed-editor cards are now add/edit ownership only, while a dedicated **News → Feed order** page exposes compact drag-to-reorder rows and Enabled/Disabled controls. The same touch-reorder helper now also enhances Weather → Clock weather cards. **Tests #4801** passed the complete automated gate on implementation head `92cb656452fb546f20f078d6ee76f0e72b31fc6b`. Commissioned-screen confirmation of those touch-order interactions and the remaining custom-feed/portability checks are still open, so PR #12 remains draft.

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

The revisioned `news` Settings domain owns:

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

New or edited custom sources have a deliberate read-only preflight before they can become usable through the normal Settings transaction.

The Settings UI calls:

```text
POST /api/news/feed/validate
```

with only the candidate URL. The endpoint:

1. applies the exact BBC feed-source validator described above;
2. performs a bounded read of that BBC RSS source;
3. parses it through the normal RSS parser without changing cache or configuration;
4. derives a friendly suggested label from the feed metadata;
5. derives a deterministic `custom-<hash>` logical id from the canonical feed URL;
6. returns only safe validation metadata (`label`, suggested id and story count).

BBC feed metadata is not completely uniform. `_suggest_feed_label()` therefore prefers a useful channel title, strips the normal `BBC News - ` / dash-prefixed branding when present, ignores a generic `BBC News` title, and then applies the same rule to the channel description. The physically accepted Europe feed is the motivating specimen: title `BBC News` plus description `BBC News - Europe` yields the display label **Europe**.

The validation response does **not** echo the source URL. A non-BBC URL is rejected before the network fetcher is called.

The browser marks a custom row as checked only for the exact URL that passed this preflight. Editing the URL clears that state, so an unchecked new/changed source cannot be accepted into the usable News configuration. Field help describes **Check feed** itself rather than referring to a separate save step. This gives normal interactive configuration an explicit “does this really look like a BBC News RSS feed?” gate without moving network fetching into the unified Settings transaction itself.

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

`app/templates/news.html`, `app/static/css/news.css`, `app/static/css/news-custom-feeds.css`, `app/static/js/news.js` and `app/static/js/news-category-scrollbar.js` own the 1280×720-first News presentation:

- Settings-style section rail on the left, driven by the saved enabled order and display labels;
- the section rail has its own bounded vertical touch-scroll region when enabled sections exceed the available height;
- the section rail hides Chromium's native scrollbar completely and uses the same ACP custom track/thumb presentation as the story-list scrollbar; this has now been physically accepted at 1280×720;
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

Top Stories therefore remains a fetch dependency whenever the ticker is enabled, even if the owner hides Top Stories from the News section rail or chooses another default section. Custom feeds cannot replace the ticker source in this follow-up. The commissioned Europe test physically reconfirmed that a custom section can be active while the ticker continues to show Top Stories.

## Settings ownership

`app/static/js/settings-news.js` registers the `news` domain with the existing `ACPUnifiedSettings` transaction owner. It has no separate save path.

The News workspace owns enabled sections, default section, summaries, ticker presentation, feed order and the bounded custom BBC RSS editor. The first software build placed News feeds under Advanced; physical testing established that it is ordinary News configuration, so the feature branch reparents it into Settings → News before the shared Settings navigation binds.

The physical 1280×720 passes then separated two different jobs that had become crowded together:

- **News feeds** owns feed display-name editing plus custom source Add / Check feed / Remove. Its large editor cards no longer expose order arrows or an Enabled control. The Add BBC feed control uses a normal compact Settings-button footprint, and creating a feed scrolls/highlights the new editor so its location is immediately obvious.
- **Feed order** owns the compact menu-order/enablement view. Each row has an explicit touch grip, label/source summary and Enabled/Disabled button. Pointer drag reorders vertically, auto-scroll assists long-distance moves near the viewport edge, and Arrow Up/Down on the grip provides a keyboard fallback. It delegates changes back to the existing News `feedState` owner, so there is still only one logical order and one unified Settings transaction.

`app/static/js/settings-touch-reorder.js` is the shared touch-order interaction helper. It is deliberately handle-based rather than making the entire row draggable so ordinary vertical touchscreen scrolling remains available outside the grip. The same helper enhances **Weather → Clock weather cards** through `settings-clock-card-drag.js`: visible up/down arrows are replaced by a grip, while `ACPClockCards.applyStoredIds()` remains the actual weather-card state owner and a single `acp:clock-cards-changed` event marks the Weather domain dirty after a committed drag.

A new or edited custom News source remains unusable until its exact URL has passed **Check feed**; after the preflight succeeds it rejoins the existing single revisioned Settings owner rather than creating a separate custom-feed save mechanism. The News worker is woken after the validated configuration commit rather than making the user wait for the normal refresh interval.

The full logical News configuration is portable ACP state. Portable Backup carries:

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

Commissioned passes on 13 September 2026 have established:

- [x] repeat `bash setup.sh` converged with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings** and preserved commissioned News configuration;
- [x] the enlarged curated catalogue rendered in Settings at 1280×720;
- [x] Business could be enabled, renamed to **Business Test**, moved in the saved order and selected as the default section;
- [x] the News page then opened the renamed Business feed with the saved rail order and correct Business stories;
- [x] the enlarged category rail became touch-scrollable and its ACP custom scrollbar now visually matches the story-list scrollbar without Chromium arrow buttons;
- [x] **News feeds** moved into Settings → News and its feed cards gained usable vertical separation;
- [x] the real candidate `https://feeds.bbci.co.uk/news/world/europe/rss.xml` passed **Check feed** and automatically derived **Europe** from title `BBC News` plus description `BBC News - Europe`;
- [x] Europe could be enabled and real Europe stories rendered as part of the mixed built-in/custom rail;
- [x] the Top Stories ticker remained visibly independent while Europe was active;
- [x] the corrected Check-feed field guidance matched the visible interaction;
- [ ] the new compact **News → Feed order** drag/enablement page still needs physical confirmation;
- [ ] the normal-sized Add BBC feed button and automatic scroll/highlight of a newly created feed editor still need physical confirmation;
- [ ] Weather → Clock weather cards drag ordering still needs physical confirmation.

Before draft PR #12 may leave draft, the commissioned appliance must still prove:

- Feed order drag remains comfortable on the touchscreen, including a long-distance move/auto-scroll, ordinary page scrolling outside the grip and correct saved News-rail order;
- its Enabled/Disabled control obeys the existing at-least-one-enabled/default-section rules;
- adding a new source makes the new editor immediately obvious without changing menu order unexpectedly;
- Clock weather-card drag commits the intended order and preserves the normal Weather/Clock presentation;
- a story delivered by the added Europe feed retains the accepted local QR hand-off behaviour when the RSS item supplies a usable HTTPS destination;
- an unchecked/non-BBC source is rejected;
- changing a custom source cannot make cache from the old source appear under the new source;
- portable Backup contains the logical order/labels/custom feed records and Reset/Restore Preview ownership remains truthful;
- News Settings, touch keyboard and unified update/discard interaction remain usable without 1280×720 overflow.

Automated evidence:

- **Tests #4753** passed the first complete implementation gate on `58e47e800ff13ed98f0834a7f429d958b7927ac0`;
- **Tests #4765** passed compile, JavaScript/page wiring/shell checks and the full regression suite on physical-test head `2ea286211cb8712553dce3e131598c06b2d6aa4c`;
- **Tests #4774** passed compile, JavaScript/page wiring/shell checks and the full regression suite on first post-physical-follow-up implementation/catalogue head `bc2f5b7c7a4e49bec9376fa49e1c73b279051e8a`;
- **Tests #4779/#4780** passed the full-feed guidance and first scrollbar-refinement heads;
- **Tests #4788** passed compile, existing JavaScript/page/shell checks and the full regression suite on `01817c5ced6dbcb7c686b52e2db851ce6905d00c`;
- **Tests #4801** passed Python compilation, JavaScript/page/shell checks and the full regression suite on `92cb656452fb546f20f078d6ee76f0e72b31fc6b`; its dedicated News regression directly syntax-checks the shared touch-reorder helper, News Feed-order client and Clock-card drag enhancer as well as the News placement/scrollbar clients.

Until the remaining gate passes, configurable sections are **software implemented / partial physical-acceptance stage**, not fully accepted product behaviour.
