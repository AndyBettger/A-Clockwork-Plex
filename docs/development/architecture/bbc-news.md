# BBC News architecture

## Status

Checkpoint #92 is physically accepted on the commissioned 1280×720 appliance. The original feed/cache/API foundation, touchscreen News page, News Settings workspace, startup/idle integration, stale-cache behaviour and the later article-QR hand-off have all passed the Raspberry Pi physical gate.

The article hand-off was physically rechecked on 11 September 2026 after a live BBC Science specimen — **“El Niño likely to cause wetter and warmer-than-normal autumn”** — showed that BBC News RSS can legitimately point at a BBC Weather article. The accepted design therefore trusts syntactically valid absolute HTTPS destinations supplied by the already trusted BBC RSS item, using `<link>` first and a valid HTTPS `<guid>` fallback. Normal BBC News links opened the installed BBC News app on the owner's iPhone; the BBC Weather specimen opened Chrome. Kiosk Chromium remained inside A Clockwork Plex throughout.

The bounded post-#92 **configurable sections** follow-up on `feature/news-custom-feeds` / PR #12 has now completed physical acceptance. Repeated commissioned-appliance passes through 14 September 2026 proved repeat installation, the enlarged catalogue, order/default behaviour, custom-feed rendering, touch reordering, the custom-only News feeds manager and empty state, local QR hand-off, non-BBC rejection, friendly ordinary-page URL entry, final validation-control presentation, changed-source/cache isolation and portable Backup/Reset/Restore ownership. After the first BBC-page helper build exposed a browser-runtime MutationObserver loop that could starve the Settings page, the bounded observer/idempotent-decoration fix restored normal Settings behaviour. The commissioned appliance subsequently added **Sussex, Surrey and Hampshire & The Isle of Wight** from ordinary BBC News page URLs, with each input converted locally to the canonical `feeds.bbci.co.uk` RSS source and QR hand-off working from the resulting sections. A later **Kent → Essex** same-record source replacement physically proved that cached Kent stories were not presented under the Essex replacement source. The final read-only portability gate then confirmed a fresh schema-v2 export carries the configured logical News model, Reset Preview proposes exactly the News fields that differ from defaults, and Restore Preview reports no changes against the unchanged live appliance.

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

ACP still does **not** become a general-purpose RSS reader. A stored/fetched custom source is accepted only when `_safe_bbc_feed_url()` proves all of the following:

- scheme is HTTPS;
- hostname is exactly `feeds.bbci.co.uk`;
- no username/password is embedded;
- port is absent or 443;
- no query string or fragment is present;
- path is `/news/rss.xml` or a `/news/.../rss.xml` path;
- path contains no doubled, current-directory or parent-directory traversal segments.

This intentionally allows BBC-owned topic and local feeds such as `/news/topics/.../rss.xml` and `/news/england/sussex/rss.xml` while rejecting arbitrary internet hosts, BBC Sport feeds, HTTP sources and URL tricks intended to escape the News source boundary.

`fetch_bbc_rss()` uses the same validator before any request. Its redirect handler also validates each redirect target **before urllib follows it**, and the final response URL is validated again. A custom-feed feature therefore cannot be used as an SSRF/open-fetch primitive by entering a BBC-looking URL that redirects elsewhere.

Friendly page entry does not widen that network boundary. `settings-news-feed-discovery.js` may accept an ordinary HTTPS BBC News page on the exact `bbc.co.uk`/`bbc.com` hosts when its path begins `/news` and consists only of bounded safe path segments. It transforms that path locally into the corresponding `https://feeds.bbci.co.uk/.../rss.xml` candidate and dispatches it through the existing **Check feed and add** path. The server never receives the BBC page URL and never fetches or scrapes BBC page HTML. If the derived RSS address does not actually exist, the normal preflight fails and nothing becomes usable.

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

`feed_order` is the logical ordered list of built-in and custom section ids. Built-in sections have canonical names and fixed source URLs in the finished Settings UI. The `feed_labels` field remains tolerated internally on this in-flight branch so development backups/configurations created before the simplification do not become invalid, but new built-in renames are no longer exposed or needed by normal appliance use. A custom feed stores its own editable display label and canonical RSS URL as part of the bounded logical record:

```json
{
  "id": "custom-…",
  "label": "Display name",
  "url": "https://feeds.bbci.co.uk/news/.../rss.xml"
}
```

A friendly BBC page URL is only an input convenience; after Check feed and add the stored source remains the canonical RSS URL. Custom ids are stable configuration identifiers rather than display labels. The default section must be enabled, at least one section must remain enabled, duplicate custom ids are rejected and a custom URL may not duplicate a curated built-in source.

The News page receives the enabled order and a link-free `{id, label}` catalogue. It does not need the underlying source URL in order to render the section rail.

## Candidate feed validation

New or edited custom sources have a deliberate read-only preflight before they can become usable through the normal Settings transaction.

For direct RSS entry the Settings UI calls:

```text
POST /api/news/feed/validate
```

with only the candidate RSS URL. If the owner instead pastes an ordinary BBC News section page, the browser first validates that it is HTTPS on an exact BBC News host with a safe `/news/...` path, converts that path to the corresponding `feeds.bbci.co.uk` RSS candidate, and then makes the same request. There is no separate HTML-discovery fetch.

The endpoint:

1. applies the exact BBC feed-source validator described above;
2. performs a bounded read of that BBC RSS source;
3. parses it through the normal RSS parser without changing cache or configuration;
4. derives a friendly suggested label from the feed metadata;
5. derives a deterministic `custom-<hash>` logical id from the canonical feed URL;
6. returns only safe validation metadata (`label`, suggested id and story count).

BBC feed metadata is not completely uniform. `_suggest_feed_label()` therefore prefers a useful channel title, strips the normal `BBC News - ` / dash-prefixed branding when present, ignores a generic `BBC News` title, and then applies the same rule to the channel description. The physically accepted Europe feed is the motivating specimen: title `BBC News` plus description `BBC News - Europe` yields the display label **Europe**.

The validation response does **not** echo the source URL. A non-BBC RSS URL is rejected before the network fetcher is called; a non-BBC ordinary page URL cannot be converted by the client and therefore reaches the same rejection boundary rather than becoming an arbitrary page fetch.

The browser marks a custom row as checked only for the exact canonical RSS URL that passed this preflight. Editing the URL clears that state, so an unchecked new/changed source cannot be accepted into the usable News configuration. Check progress, success and failure are presented beside the relevant custom feed's own action row rather than only in the page-level intro card, with explicit spacing so the result does not visually collide with the button row. The visible action is labelled **Check feed and add** because a successful preflight converts/stages the custom feed into the existing unified Settings transaction; there is still no independent save mechanism. This gives normal interactive configuration an explicit “does this really look like a BBC News RSS feed?” gate without moving network fetching into the unified Settings transaction itself.

Portable Restore is intentionally different: it restores an already validated logical ACP configuration through the normal server validator and does not require BBC connectivity during the Restore transaction. The News worker checks/fetches the restored source afterwards using the same source boundary. This preserves offline/cache-first Restore semantics.

## Cache ownership

The configurable-source work advances the private cache schema to version 4.

Each cached category state privately remembers the source `feed_url` that produced it. If a configured source changes, a last-good feed belonging to the old URL is not presented as if it came from the replacement source. A newly required section is also considered immediately due when it has no matching cached data, rather than waiting for the global refresh timer.

This source-ownership rule is physically accepted on the commissioned appliance. A temporary custom feed named **Cache Test** first fetched Kent stories; the same custom feed record was then changed to the Essex source. Essex content populated normally and no stale Kent headlines were presented under the replacement source. The temporary feed was removed after the proof.

Source URLs are runtime/private cache metadata. Public snapshots strip `feed_url` before JSON projection.

Downloaded RSS/cache state remains generated runtime state and is excluded from portable Backup/Restore.

## Public story model

The public `/api/news` story model remains deliberately small:

- opaque story id;
- title/headline;
- plain-text summary;
- published timestamp;
- category id.

Article URLs and GUID values are absent. The configurable-feed source URLs, compatibility rename map and custom-feed records are also absent from the kiosk News API. `/api/news` exposes only the presentation settings the News screen actually needs plus the link-free category catalogue.

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

The physical 1280×720 passes then separated the jobs cleanly:

- **News feeds** is a custom-source manager only. Built-in editor cards remain in the DOM as hidden implementation/state-owner records so the pre-existing News transaction and Feed-order adapter can continue to share one model, but CSS removes them completely from this page. Built-in BBC names and URLs are therefore not user-editable. Custom cards retain Display name, a **BBC News page or RSS URL** field, **Check feed and add** and Remove. An ordinary BBC News section page is converted locally to its canonical RSS candidate before the preflight; the field then contains the RSS URL that is actually validated/stored. Check status/errors are shown beneath that card's action row with deliberate vertical separation. The Add BBC feed control uses a normal compact Settings-button footprint; after creation the `.settings-detail` scroller moves directly to/highlights the new custom editor. When no custom sources exist the page shows a friendly empty-state message rather than a blank list.
- **Feed order** owns the compact menu-order/enablement view for both built-in and custom feeds. Each row has an explicit touch grip, label/source summary and Enabled/Disabled button. Pointer drag reorders vertically, auto-scroll assists long-distance moves near the viewport edge, and Arrow Up/Down on the grip provides a keyboard fallback. It delegates changes back to the existing News `feedState` owner, so there is still only one logical order and one unified Settings transaction.
- **Sections** retains the quick checkbox/default-section view and does not edit feed identities.

`app/static/js/settings-touch-reorder.js` is the shared touch-order interaction helper. It is deliberately handle-based rather than making the entire row draggable so ordinary vertical touchscreen scrolling remains available outside the grip. The visual grip is drawn as a fixed CSS 2×3 dot matrix instead of relying on the Braille `⠿` glyph's font metrics, keeping the mark geometrically centred inside the touch target across Chromium/font combinations. The same helper enhances **Weather → Clock weather cards** through `settings-clock-card-drag.js`: visible up/down arrows are replaced by a grip, while `ACPClockCards.applyStoredIds()` remains the actual weather-card state owner and a single `acp:clock-cards-changed` event marks the Weather domain dirty after a committed drag.

A new or edited custom News source remains unusable until its exact canonical RSS URL has passed **Check feed and add**; after the preflight succeeds it rejoins the existing single revisioned Settings owner rather than creating a separate custom-feed save mechanism. The News worker is woken after the validated configuration commit rather than making the user wait for the normal refresh interval.

The full logical News configuration is portable ACP state. Portable Backup carries:

- enabled ids;
- default id;
- feed order;
- custom BBC feed logical records, including their editable display names and canonical RSS URLs;
- the compatibility built-in-label map if present in a development-era configuration, although the finished UI no longer creates such overrides;
- summary setting;
- ticker setting/speed.

Restore compares and reapplies those fields through the normal News Settings validator. Reset derives its News target from version-controlled `config.example.json`, returning the appliance to the original five enabled sections, curated default ordering, canonical built-in names and no custom feeds.

RSS downloads/cache/private article hand-off metadata are excluded from Backup/Restore/Reset portability.

## Failure boundary

BBC/network/XML failure must never affect the rest of the appliance. A failed active section keeps its previous successful feed only when that cache belongs to the same configured source, and records an explicit degraded/stale/error state. The News page labels stale data rather than inventing content.

A failed custom-feed preflight does not change configuration or cache. A friendly page URL that derives to a nonexistent RSS endpoint therefore fails safely at the same gate. A missing/rejected article link or QR-generation failure does not prevent the story summary dialog from opening and does not affect the feed worker.

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

### Configurable-sections follow-up — physically accepted

Commissioned passes through 14 September 2026 established:

- [x] repeat `bash setup.sh` converged with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings** and preserved commissioned News configuration;
- [x] the enlarged curated catalogue rendered in Settings at 1280×720;
- [x] Business could be enabled, temporarily renamed to **Business Test**, moved in the saved order and selected as the default section; it was later returned to canonical **Business** before built-in renaming was removed from the finished UI;
- [x] the News page opened the selected Business feed with the saved rail order and correct Business stories;
- [x] the enlarged category rail became touch-scrollable and its ACP custom scrollbar now visually matches the story-list scrollbar without Chromium arrow buttons;
- [x] **News feeds** moved into Settings → News and its feed cards gained usable vertical separation;
- [x] the real candidate `https://feeds.bbci.co.uk/news/world/europe/rss.xml` passed the feed preflight and automatically derived **Europe** from title `BBC News` plus description `BBC News - Europe`;
- [x] Europe could be enabled and real Europe stories rendered as part of the mixed built-in/custom rail;
- [x] the Top Stories ticker remained visibly independent while Europe was active;
- [x] the corrected feed-check field guidance matched the visible interaction;
- [x] the compact **News → Feed order** page works physically for long-distance drag, including edge auto-scroll;
- [x] Feed order Enabled/Disabled changes correctly enable and disable optional News sections;
- [x] Weather → Clock weather cards drag ordering physically changes the configured card order;
- [x] the normal-sized Add BBC feed button is visually accepted;
- [x] Add BBC feed now scrolls/highlights the newly created custom editor on the commissioned screen;
- [x] the CSS-drawn 2×3 grips are visually centred on both News Feed order and Clock weather cards;
- [x] duplicate Enabled/Move controls are absent from News feeds;
- [x] the final custom-only News feeds page hides all built-in editors and shows its friendly empty state when Europe is removed;
- [x] Europe story QR hand-off works from the custom feed;
- [x] an arbitrary non-BBC custom source is rejected before it can become usable;
- [x] the MutationObserver runtime-loop fix restored normal Settings loading/navigation;
- [x] ordinary BBC page URLs physically added **Sussex, Surrey and Hampshire & The Isle of Wight**, converting to the corresponding canonical RSS URLs;
- [x] QR hand-off works from those three newly added local custom sections;
- [x] non-BBC rejection feedback is now physically visible beside the relevant custom-feed controls;
- [x] **Check feed and add** plus validation-message spacing are physically comfortable at 1280×720;
- [x] source replacement is cache-safe: a **Cache Test** custom feed changed in-place from Kent to Essex populated Essex content without showing stale Kent stories under the new source;
- [x] a fresh backup made at 01:03 on 14 September was **schema-v2** and contained the live logical News configuration: Business default, the saved enabled/order model, and the Europe, Sussex, Hampshire & Isle of Wight and Surrey custom-feed records with canonical `feeds.bbci.co.uk` RSS URLs;
- [x] Reset **Preview** remained read-only and reported `settings.news · 4`, with exactly `a_clockwork_plex.settings.news.custom_feeds`, `.default_category`, `.enabled_categories` and `.feed_order` among the technical changed paths;
- [x] Restore **Preview** of that just-created backup correctly reported **No changes** against the unchanged live appliance, proving the exported News state is recognised by the existing portable transaction without applying anything.

The portable-ownership gate is therefore closed. No destructive Reset or Restore confirmation was required on the commissioned appliance; the broader #89/#90/#93 destructive round-trip had already been physically accepted separately. Generated RSS/cache/private article state remains outside the portable model by design.

Automated evidence:

- **Tests #4753** passed the first complete implementation gate on `58e47e800ff13ed98f0834a7f429d958b7927ac0`;
- **Tests #4765** passed compile, JavaScript/page wiring/shell checks and the full regression suite on physical-test head `2ea286211cb8712553dce3e131598c06b2d6aa4c`;
- **Tests #4774** passed compile, JavaScript/page wiring/shell and the full regression suite on first post-physical-follow-up implementation/catalogue head `bc2f5b7c7a4e49bec9376fa49e1c73b279051e8a`;
- **Tests #4779/#4780** passed the full-feed guidance and first scrollbar-refinement heads;
- **Tests #4788** passed compile, existing JavaScript/page/shell checks and the full regression suite on `01817c5ced6dbcb7c686b52e2db851ce6905d00c`;
- **Tests #4801** passed Python compilation, JavaScript/page/shell checks and the full regression suite on `92cb656452fb546f20f078d6ee76f0e72b31fc6b`; its dedicated News regression directly syntax-checks the shared touch-reorder helper, News Feed-order client and Clock-card drag enhancer as well as the News placement/scrollbar clients;
- **Tests #4807** passed Python compilation, JavaScript/page/shell checks and the full regression suite on `e5828a7205394019f4fb6d24e1c8ef46547beec3`, covering explicit new-editor scrolling, centred dot-matrix grip styling and editor-only hidden-control enforcement;
- **Tests #4824** passed the full automated gate on custom-only News feed manager implementation head `90a4eee0f66c63bf7e3f5ba6272279ac177e2aa0`, including regression coverage that built-in editor cards are hidden while Feed order still uses the shared underlying records;
- **Tests #4834** passed Python compilation, JavaScript/page/shell checks and the full regression suite on `81fd4798d7954baf46e17cbd8f28f22868f6bd67`, including syntax/contract coverage for friendly BBC page URL conversion and local feed-validation feedback;
- **Tests #4839** passed compile, JavaScript/page/shell checks and the full regression suite on the bounded-MutationObserver runtime-fix head `708296f0d3d84c0218541c79ad436ec8e93062d6`;
- **Tests #4844** passed Python compilation, JavaScript/page/shell checks and the full regression suite on final validation-control polish head `a0466bf605515078961e7110f81f9942cd473094`;
- **Tests #4852** passed the full automated gate on the final pre-acceptance documentation head `dc348dc029241241d42e60de5d7e347ed50a4625`.

Configurable sections are now **software implemented and physically accepted product behaviour**.
