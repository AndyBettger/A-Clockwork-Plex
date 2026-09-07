# A Clockwork Plex Roadmap

**Last updated:** 7 September 2026  
**Active integration branch:** `develop`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This began as the EQ/audio-installer roadmap. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation/release/future-product roadmap. Detailed engineering chronology belongs in development/history documents rather than burying the useful current plan.

Specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and Home completeness;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and physical/product gate;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally not assigned until its real scope is clear.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from the post-v0.4.0 baseline.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established the feature-branch → `develop` → accepted release model.

### #85 High-resolution audio feasibility audit — COMPLETE; implementation queued

The current managed EQ and Direct/fallback profiles still use a fixed **S16_LE / 44100 Hz** shared music path. High-resolution implementation remains queued until the Settings/appliance-ownership track is deliberately closed or its remaining Home follow-ups are explicitly deferred.

Before production mutation, use `scripts/audio/preflight-eq.sh` as the **read-only bedroom-Pi validation gate**. The **accepted production SD remains protected**; **a separate spare SD is the disposable acceptance target** for destructive route/lifecycle experiments.

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

- [x] Portable ACP settings are a normalised logical model, never raw `config.json` bytes.
- [x] Credentials/auth/session, hardware identity/topology, raw ALSA, caches and machine identity are excluded.
- [x] Exact eight-value Plexamp Headless portable allow-list established: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `playerName` and `audioDeviceUuid` classified nonportable.
- [x] Plexamp Home browser-local persistence families physically classified without treating the Chromium profile as a backup unit.

### #89 Configuration backup/export — CORE COMPLETE; HOME PRESENTATION/CUSTOM MODEL FOLLOW-UP OPEN

- [x] Schema-v1 backup/export physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer, exact eight typed Headless preferences and logical Home order/hidden choices.
- [x] Credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state excluded.
- [x] Physical export captured **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.
- [x] Fresh-profile #93 evidence independently confirms durable `order`, `hidden`, `viewSettings`, custom-section and custom-title persistence.
- [ ] Per-section Home `viewSettings`, custom-section structure and custom-title semantics are **not currently portable in schema v1**.
- [ ] Define and implement a validated logical presentation/custom-section/title model; never export raw browser keys/values.

### #90 Configuration import/restore — CORE COMPLETE; HOME PRESENTATION/CUSTOM MODEL FOLLOW-UP OPEN

- [x] Read-only parse/validate/Preview with paths/counts rather than values.
- [x] Stale-protected ACP Settings/EQ/mixer restore with reverse rollback.
- [x] Exact-version eight-value Plexamp Headless restore through the restricted owner.
- [x] Target-context-aware Home order/hidden restore with exact raw rollback.
- [x] Guided **Preview → choose ACP / Plexamp / both → Review → Confirm & restore** presentation physically accepted at 1280×720.
- [x] Final combined physical restore converged to zero differences for the supported schema-v1 scope.
- [ ] Extend the portable Home model to validated presentation/custom-section/title semantics and physically revalidate complete logical Home restore.

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] Plexamp Search keyboard/bridge physically accepted.
- [x] General Plexamp text fields physically accepted for Home title, Smart Playlist name/description, Home Screen section title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — COMPLETE

- [x] BBC RSS-only feed/cache authority for Top Stories, UK, World, Science and Technology.
- [x] Public model strips article links/GUIDs; no outbound article navigation.
- [x] Last-good cache, stale/degraded presentation and Top Stories ticker physically accepted.
- [x] Settings, News page, touch scrolling, startup/idle-return and Wi-Fi-loss recovery physically accepted.

### #93 Reset-to-defaults workflow — FULL HOME ARCHITECTURE PROVEN; FINAL PRODUCTION ACCEPTANCE PENDING

PR #9 remains **Draft and unmerged**. The combined Reset transaction is physically accepted, the complete tested Home persistence surface is classified, and the disposable **9230 full-Home scrub → Plexamp rebuild → exact rollback** proof has passed. The branch now implements bounded full Home customisation Reset; the remaining gate is commissioned-Pi production acceptance on a final green head plus explicit owner approval.

#### Accepted transaction foundations

- [x] ACP Reset target generated from version-controlled defaults through production normalisers.
- [x] ACP stale-preview, verification and rollback semantics physically accepted.
- [x] 1280×720 Preview/Review/Ready/Confirm presentation physically accepted.
- [x] Same-appliance commissioning restores captured Plexamp player name + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Plexamp native owner calls real `global.app.rootStore.settings.resetToDefaults()`.
- [x] Plexamp live music-player volume resets to **100%** with verification and exact rollback.
- [x] `equalizerPresets` excluded from native changed-set/fingerprint as runtime-normalised catalogue state while remaining rollback-covered.
- [x] ACP EQ returns to 0/0/0 dB; Music Master, Plexamp trim, AirPlay trim, Maximum Alarm Volume and AirPlay session-start volume use the accepted **100%** baseline.
- [x] Full multi-owner Confirm crosses the corrected ACP-only browser/server stale-token boundary successfully.

#### Complete Home persistence classification — CLOSED

Preserved causal specimens:

```text
9224  order tracer
9225  hidden tracer
9226  built-in presentation tracer
9227  editor-only control
9228  durable custom-section tracer
9229  durable custom-title tracer
9230  mixed reversible full-Home tracer
```

Established durable families:

```text
order
hidden
viewSettings
customHubs
```

Established interpretation:

- [x] `order` is durable and browser-profile-local.
- [x] `hidden` is durable and browser-profile-local.
- [x] `viewSettings` owns durable built-in presentation.
- [x] `editing` is transient edit bookkeeping; editor entry/exit alone creates no Home state.
- [x] custom-added sections are coordinated `customHubs + order + viewSettings` bundles.
- [x] validated custom titles live inside the custom section `viewSettings` record.
- [x] Session Storage/IndexedDB were ruled out for the tested Home persistence cases.

The observed effective/default hub count is evidence, not a product invariant, and is never hard-coded.

#### 9230 full reversible proof — PASSED

9230 deliberately combined:

- custom Artist section **ACP Scrub Section**;
- moved **Mixes for you**;
- hidden **Recent Plays**;
- **Recently Added in Music** set to Carousel / Block / 180 px.

Settled bounded state:

```text
customHubs=1
order=1
hidden=1
viewSettings=2
editing=0
other=0
matching records=5
context_count=2
section_context_count=2
fingerprint=58ed4b28
```

Confirmed scrub:

- [x] exact five Home records captured to a no-overwrite mode-0600 disposable snapshot;
- [x] exactly those five classified records removed;
- [x] bounded Home state verified all-zero;
- [x] empty/customisation-free fingerprint `741638a5`;
- [x] after normal reload Plexamp rebuilt a populated default-looking Home itself;
- [x] custom section/order/hidden/presentation overrides disappeared;
- [x] Plex login remained intact;
- [x] correct library remained selected.

Confirmed rollback:

- [x] restored exactly five records into the empty bounded target;
- [x] original fingerprint **`58ed4b28`** returned exactly;
- [x] independent family probe returned the original `customHubs=1`, `order=1`, `hidden=1`, `viewSettings=2` inventory;
- [x] title matcher again found exactly one `ACP Scrub Section`;
- [x] after reload the custom section, moved order, hidden Recent Plays and Carousel/Block/180 px presentation all returned visually;
- [x] Plex login and correct library remained intact throughout.

This proves the intended production model: clear only bounded Home-owned customisation state and let Plexamp rebuild itself; do not synthesize runtime hubs or copy a clean Chromium profile.

#### Production full-Home semantics — IMPLEMENTED ON FEATURE BRANCH

The Home owner now:

- [x] recognises only bounded durable `order`, `hidden`, `viewSettings`, `customHubs` records;
- [x] fails closed on active `editing`, unknown/malformed families, stale targets and bounded-size/count violations;
- [x] snapshots exact raw Home records in memory before mutation;
- [x] removes records individually, never `localStorage.clear()`;
- [x] verifies the bounded Home target is empty after apply;
- [x] retains exact rollback through the later server participant;
- [x] refuses rollback into a non-empty bounded Home target;
- [x] finalises rollback state only after the complete transaction succeeds;
- [x] uses the existing post-success dashboard reload as Plexamp's Home rebuild trigger;
- [x] leaves auth/session/library/account/device identity and unrelated browser/cache state outside the Home owner;
- [x] uses no DevTools, remote-debug production interface, generic `eval`, raw profile copying or transient runtime-hub mutation.

The ordering is deliberate: Home must **not** reload immediately after clearing because that would discard the in-memory rollback token before the later server participant committed. The existing outer transaction already supplies the correct commit boundary.

#### Automated evidence

- [x] Tests #4623 passed on `8db7c9907675ec416681b0d72676594c4781f960`.
- [x] Tests #4625 passed on `136f6fc5e14b0734f0d9ff5ca8f4d02951418450`.
- [x] Tests #4631 passed on `9457a4413611e506bfab0cbf73cd4ef01a07184f`.
- [x] Tests #4632 passed on `1b0fccf26887b708417a24974df92d87ff093553`.
- [x] Tests #4633 passed on `54600624add3af758dd38d564daf1a4a7868d7eb`.
- [x] Tests #4638 passed on `96f06e09544fafed3475f3416ac28650b040c580`: widened full-Home production owner + five-record safety/rollback smoke + full suite green.
- [ ] Final production/docs head must also pass complete CI before the commissioned-Pi acceptance run.

#### Remaining #93 gate

- [x] Home persistence classification complete.
- [x] Full disposable scrub/rebuild/rollback proof complete.
- [x] Full bounded Home customisation joins #93 rather than becoming a separate Reset follow-up.
- [x] Production owner widened and extension/client cache versions advanced.
- [ ] Complete CI green on the final code/docs head.
- [ ] Pull/reboot that exact head on the commissioned Pi so Chromium loads the new packaged bridge.
- [ ] Run fresh production Preview/Review/Confirm and verify Home rebuild while login/library remain intact.
- [ ] Verify fresh Preview does not report `equalizerPresets`.
- [ ] If the commissioned Pi contains the short-lived 10% AirPlay start value, verify Reset restores both AirPlay session-start and persistent AirPlay trim to **100%**.
- [ ] Keep #89/#90 presentation/custom-section/title portable Backup/Restore follow-up open until implemented or deliberately deferred.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**Do not begin high-resolution-audio implementation until the Settings/appliance-ownership track is deliberately closed or the remaining Home follow-ups are explicitly deferred.**

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — #88 core COMPLETE; #89/#90 Home portability follow-up OPEN; #93 final production acceptance pending
3. **Touchscreen Plexamp text entry** — COMPLETE #91
4. **BBC News** — COMPLETE #92
5. **High-resolution Plexamp audio / mixer-EQ path**
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

- all included feature branches must be merged into `develop` only after automated and physical acceptance;
- the clean-room installer/runbook must still pass on supported hardware;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and this live roadmap must describe the actual shipped state;
- the accepted production appliance must not be used as the disposable target for destructive audio/storage experiments;
- release version/tag/name is assigned only after final scope and acceptance are known.
