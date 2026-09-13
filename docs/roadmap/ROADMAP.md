# A Clockwork Plex Roadmap

**Last updated:** 13 September 2026  
**Active integration branch:** `develop`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This began as the EQ/audio-installer roadmap. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide live roadmap.

## Roadmap authority and history

This file is the single live implementation/release/future-product roadmap. Detailed engineering chronology belongs in the development/history documents rather than turning the roadmap into a commit diary.

Specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and Plexamp Home completeness;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and physical/product gate;
- [`../development/architecture/bbc-news.md`](../development/architecture/bbc-news.md) — #92 BBC News, article QR hand-off and the active configurable-sections follow-up;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- feature branches do not merge merely because CI is green: relevant Raspberry Pi/touchscreen behaviour must pass its physical acceptance gate first.
- the next release version is intentionally not assigned until its real scope is clear.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from the post-v0.4.0 baseline.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established the feature-branch → `develop` → accepted release model.

### #85 High-resolution audio feasibility audit — COMPLETE; IMPLEMENTATION QUEUED

The current managed EQ and Direct/fallback profiles still use a fixed **S16_LE / 44100 Hz** shared music path. High-resolution implementation remains the next major product feature, but the bounded BBC News configurable-sections follow-up has deliberately been pulled forward and must close its physical gate first.

Before any production audio mutation, use `scripts/audio/preflight-eq.sh` as the **read-only bedroom-Pi validation gate**. The accepted production SD remains protected; **a separate spare SD is the disposable acceptance target** for destructive route/lifecycle experiments.

Accepted constraints:

- AirPlay compatibility must remain truthful to the received source format;
- scheduled-alarm takeover, Maximum Alarm Volume and recovery are non-negotiable;
- bypass/native/bit-perfect claims must be based on measured ALSA/DAC state;
- appliance reliability outranks a bit-perfect badge.

### #86 Friendly forecast-location entry — COMPLETE

- [x] Read-only town/city/postcode lookup using Open-Meteo plus Postcodes.io fallback for full UK postcodes.
- [x] Friendly location stages exact forecast coordinates while retaining precise manual latitude/longitude fallback.
- [x] Physical Milland and `GU30 7JS` tests passed.

### #87 WU supplemental indoor expiry — COMPLETE

- [x] Stale Ecowitt indoor supplementation expires while WU outdoor observations remain live.
- [x] Weather removes expired indoor values; Clock retains paired geometry with placeholders.
- [x] Re-enabling Ecowitt restores indoor data without service restart.

### #88 Configuration ownership and backup-format audit — COMPLETE

- [x] Portable ACP settings are a normalised logical model rather than raw `config.json` bytes.
- [x] Credentials/auth/session, hardware identity/topology, raw ALSA, caches and machine identity are excluded.
- [x] Plexamp native/Home ownership and portability boundaries are classified and documented.

Detailed authority: [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md).

### #89 Configuration backup/export — COMPLETE

- [x] Schema-v1 compatibility export remains supported.
- [x] Schema-v2 export carries portable ACP state, broader classified Plexamp native settings and complete logical Home-v2 state without source machine identifiers.
- [x] Production bridge 1.5.0 activates the bounded native/Home-v2 portability transport with no extension permissions, background authority or production DevTools interface.
- [x] Commissioned-Pi export specimens and real-use backups passed structural/portability inspection.

### #90 Configuration import/restore — COMPLETE

- [x] Read-only Preview → choose target → Review → Confirm flow accepted at 1280×720.
- [x] Schema-v2 multi-owner transaction preserves stale protection, verification and reverse rollback across native Plexamp → Home → ACP server owners.
- [x] Commissioned-Pi Reset/Restore round trips converged to zero supported differences.
- [x] Schema-v1 backups retain their accepted compatibility path.

#89/#90 and #93 are integrated into `develop`; the Settings/appliance-ownership engineering track is closed.

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] Plexamp Search keyboard/bridge physically accepted.
- [x] General Plexamp text fields physically accepted for Home title, Smart Playlist metadata, Home Screen section title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — CORE + ARTICLE QR COMPLETE; CONFIGURABLE SECTIONS FOLLOW-UP ACTIVE

#### Accepted core

- [x] BBC RSS feed/cache authority, link-free `/api/news` story model, last-good cache and stale/degraded presentation physically accepted.
- [x] Touch News page, category rail, synchronized scrollbar, local story detail, Settings workspace and Top Stories ticker physically accepted.
- [x] News as manual, Startup and Idle-return screen physically accepted, including a real reboot into News.
- [x] Real Wi-Fi-loss test retained cached stories/ticker and recovered normally.

#### Accepted article QR hand-off

- [x] Article hand-off retains the absolute HTTPS destination supplied by the trusted BBC RSS item, using `<link>` first and a valid HTTPS `<guid>` fallback.
- [x] QR SVG is generated locally; the kiosk exposes no article anchor and no arbitrary URL-to-QR input.
- [x] Initial full automated gate passed in **Tests #4732**; trusted-RSS destination/GUID refinement passed **Tests #4749**.
- [x] Commissioned 1280×720 + iPhone acceptance passed on 11 September 2026: normal BBC News destinations opened the installed BBC News app, the live BBC Weather destination from the Science feed gained a QR and opened correctly in Chrome, and kiosk Chromium remained in ACP.

#### Configurable sections follow-up — SOFTWARE IMPLEMENTED; PHYSICAL GATE PARTIALLY PASSED

Active branch: `feature/news-custom-feeds`  
Draft PR: **#12 — Add configurable BBC News feeds**

- [x] Preserve the original five sections — Top Stories, UK, World, Science & Environment and Technology — as the out-of-box enabled set.
- [x] Expand the friendly built-in catalogue with England, Scotland, Wales, Northern Ireland, Business, Politics, Health, Education and Entertainment & Arts.
- [x] Allow sections to be enabled/disabled, reordered and renamed; the default News section must remain enabled.
- [x] Add **News → News feeds** for bounded custom BBC News RSS sources; the first physical pass established that this belongs with ordinary News configuration rather than under Advanced.
- [x] Custom source boundary is exact HTTPS `feeds.bbci.co.uk/news/.../rss.xml`; arbitrary hosts, HTTP, credentials, non-News paths and redirect escapes are rejected.
- [x] New/changed custom feeds use a read-only **Check feed** preflight before normal Settings Save; the server parses the candidate, derives a sensible title and deterministic stable id, and returns no source URL in the validation response.
- [x] A changed source cannot reuse cached content belonging to the previous URL as if it came from the replacement source.
- [x] `/api/news` remains source-URL/article-link/GUID free; the accepted phone-owned QR boundary remains unchanged.
- [x] Top Stories remains the independent ticker source even if another section is active/default or Top Stories is hidden from the rail.
- [x] `feed_order`, `feed_labels` and `custom_feeds` now join the portable News Backup/Restore/Reset model; downloaded RSS/cache state remains excluded.
- [x] **Tests #4753** passed the first complete implementation gate on `58e47e800ff13ed98f0834a7f429d958b7927ac0`.
- [x] **Tests #4765** passed compile, JavaScript/page/shell and full regression CI on commissioned-test head `2ea286211cb8712553dce3e131598c06b2d6aa4c`.
- [x] Commissioned-Pi repeat `bash setup.sh` on that head passed with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings**.
- [x] First 1280×720 functional pass proved the enlarged catalogue plus Business enable → **Business Test** rename → reorder → default selection → saved News rendering, with the Top Stories ticker still independent.
- [x] Physical findings were folded back into the branch: the section rail gained a bounded touch-scroll region, feed-editor cards gained explicit vertical separation, and the feed editor moved into Settings → News.
- [x] **Tests #4774** passed compile, JavaScript/page wiring/shell and the full regression suite on the first post-physical-follow-up implementation/catalogue head `bc2f5b7c7a4e49bec9376fa49e1c73b279051e8a`.
- [x] Commissioned-Pi repeat `bash setup.sh` on follow-up head `8106ab5e91bcc4498cd1fca41959ed231c9e8815` again passed with `APPLIANCE_VERIFY=PASS`, **0 failures / 0 warnings** and preserved the existing commissioned News configuration.
- [x] Second 1280×720 pass confirmed that the enlarged News rail now scrolls, **News feeds** is correctly owned by Settings → News, and feed-editor cards have useful visual separation.
- [x] That second pass identified two final presentation-copy refinements: match the rail scrollbar to the existing story-list scrollbar and stop presenting the bare `feeds.bbci.co.uk` host as though it were a useful browser destination. Both are implemented with a full RSS example URL and dedicated regression coverage; **Tests #4779** passed compile, JavaScript/page wiring/shell and the full regression suite on `f783688ddb77b921514d52830ab0bd8188412083`.
- [ ] Commissioned 1280×720 recheck confirms the matched rail scrollbar and revised full-feed guidance, then completes custom BBC feed Check/Add, mixed rail rendering, custom-feed story QR, non-BBC rejection, cache-source correctness and touch/layout usability.
- [ ] Portable Backup/Reset/Restore ownership receives a bounded physical/read-only acceptance check appropriate to the commissioned appliance.

Detailed authority and the physical checklist: [`../development/architecture/bbc-news.md`](../development/architecture/bbc-news.md).

### #93 Reset-to-defaults workflow — COMPLETE

- [x] Full ACP + Plexamp native + bounded Home + commissioning transaction physically accepted.
- [x] Reset uses version-controlled ACP defaults through production normalisers; EQ/mixer/audio baselines are verified.
- [x] Plexamp login/library/identity and managed output survive Reset correctly.
- [x] Full Home customisation ownership (`order`, `hidden`, `viewSettings`, `customHubs`) was classified through disposable-profile evidence and a reversible scrub/rebuild/rollback proof.
- [x] Commissioned-Pi Preview → Review → Confirm and fresh post-reset zero-change Preview passed.
- [x] #93 merged to `develop` via PR #9; #89/#90 completeness then merged via PR #10.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — COMPLETE through #93, including schema-v2 Backup/Restore
3. **Touchscreen Plexamp text entry** — COMPLETE #91
4. **BBC News** — core + article QR COMPLETE; configurable-sections follow-up **ACTIVE**
5. **High-resolution Plexamp audio / mixer-EQ path** — NEXT after #92 follow-up physical closure
6. **Astronomy**
7. **Appliance resilience**
8. **Events calendar**

This priority list is authoritative.

## Future product backlog

### High-resolution Plexamp audio / mixer-EQ path

Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

- [ ] Physical capability audit with known 16/44.1, 24/48, 24/96 and 24/192 Plex files.
- [ ] Choose a managed high-resolution bus by measured CPU/stability/latency.
- [ ] Remove the managed 16/44.1 bottleneck while preserving trims → Music Master → reserve → EQ → limiter → alarm join.
- [ ] Define truthful EQ-active high-resolution and native-bypass behaviour.
- [ ] Investigate source-rate-native Direct Plexamp across 44.1/48/88.2/96/176.4/192 kHz.
- [ ] Define deliberate resampling policy for Plexamp and AirPlay sources.
- [ ] Expose source, processing and final DAC format/rate separately in diagnostics.
- [ ] Regression/physical acceptance: route/fallback, EQ active/bypass, alarm takeover, AirPlay both directions and recovery.

### Astronomy

- [ ] Deterministic local/offline calculation authority with reference fixtures and tolerances.
- [ ] Observer/location model reusing existing coordinates/timezone where sensible.
- [ ] Overview/Tonight: Julian Date, sidereal time, Sun/Moon headline state and useful events.
- [ ] Sun: rise/transit/set, twilight classes, day length, RA/Dec and altitude/azimuth.
- [ ] Moon: rise/transit/set, phase/age/illumination, principal phases, distance/angular diameter, RA/Dec and altitude/azimuth.
- [ ] Planets Mercury–Neptune: rise/transit/set and useful position/magnitude/elongation data where reliable.
- [ ] Touch-first 1280×720 navigation plus night presentation.
- [ ] Validate circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Appliance resilience

Detailed design/security constraints: [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md).

- [ ] Investigate intermittent read-only root-filesystem/SD behaviour observed during commissioned-Pi testing.
- [ ] Reduce avoidable appliance writes where this does not weaken rollback/history/recovery.
- [ ] Design kiosk-safe Wi-Fi recovery with a bounded temporary NetworkManager-backed recovery AP and local QR/captive-portal-style setup.
- [ ] Keep Wi-Fi credentials out of query strings, argv, logs, browser history and persistent recovery pages.
- [ ] Define recovery timeout/rollback so failed reconfiguration cannot strand the appliance indefinitely.
- [ ] Add truthful health/status for storage, network and critical appliance services without automatic mutation.

### Events calendar

- [ ] Define source/credential ownership before implementation.
- [ ] Build a cache-first, touch-friendly upcoming-events model.
- [ ] Reuse global date/time formatting and existing screen/idle ownership.
- [ ] Design stale/offline behaviour.
- [ ] Keep external event links/navigation out of the kiosk unless explicitly designed and safely owned.

## Release gate for the next version

Before promoting the next development cycle to `main`:

- all included feature branches must be merged into `develop` only after automated and relevant physical acceptance;
- the clean-room installer/runbook must still pass on supported hardware;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and this live roadmap must describe the actual shipped state;
- the accepted production appliance must not be used as the disposable target for destructive audio/storage experiments;
- release version/tag/name is assigned only after final scope and acceptance are known.
