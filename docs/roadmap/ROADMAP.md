# A Clockwork Plex Roadmap

**Last updated:** 7 September 2026  
**Active integration branch:** `develop`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This began as the EQ/audio-installer roadmap. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation/release/future-product roadmap. Detailed engineering chronology belongs in the development/history documents rather than burying the useful current plan.

Specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and Home completeness;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and current physical/product gate;
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
- [x] Plexamp Home order and per-hub hidden families physically classified without treating the Chromium profile as a backup unit.

### #89 Configuration backup/export — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

- [x] Schema-v1 backup/export physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer, the exact eight typed Headless preferences and logical Home order/hidden choices.
- [x] Credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state excluded.
- [x] Physical final export captured **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.
- [x] Fresh disposable-profile #93 testing independently confirmed the existing logical persistence families: `order` and `hidden` are durable browser-profile-local Local Storage owners.
- [x] Fresh disposable-profile #93 testing independently confirmed built-in presentation persistence: **Recent Plays → Carousel** creates a durable `viewSettings` record; the companion `editing` record is transient and disappears on reload.
- [ ] Per-section Home presentation `viewSettings` are **not currently in schema-v1 backup**. Physical restore testing on 5 September confirmed this is the principal known portability gap.
- [ ] Define a validated logical presentation model after the custom-section/title family is classified.

### #90 Configuration import/restore — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

- [x] Read-only parse/validate/Preview with paths/counts rather than values.
- [x] Stale-protected ACP Settings/EQ/mixer restore with reverse rollback.
- [x] Exact-version eight-value Plexamp Headless restore through the narrow restricted owner.
- [x] Target-context-aware Home order/hidden restore with exact raw rollback.
- [x] Guided **Preview → choose ACP / Plexamp / both → Review → Confirm & restore** presentation physically accepted at 1280×720.
- [x] Final combined physical restore converged back to zero differences for the supported schema-v1 scope.
- [x] Fresh-profile #93 evidence independently confirms the existing browser-local `order`, `hidden` and `viewSettings` persistence families rather than exposing alternate owners.
- [ ] Extend the portable Home model to validated per-section presentation.
- [ ] Revalidate complete logical Home restore after the custom-section/title family is causally classified.

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

### #93 Reset-to-defaults workflow — TRANSACTION ACCEPTED; FULL HOME REBUILD INVESTIGATION OPEN

PR #9 remains **Draft and unmerged**. The complete multi-owner transaction has passed physically. The remaining product question is whether the already accepted presentation-only Home Reset should expand into a separately proven full Home-customisation reset which clears only proven Home-owned persistence and lets Plexamp rebuild its own effective Home.

#### Physically accepted foundations

- [x] ACP Reset transaction generated from version-controlled defaults through production normalisers.
- [x] ACP stale-preview, verification and rollback semantics physically accepted.
- [x] Final 1280×720 Preview/Review/Ready/Confirm presentation physically accepted.
- [x] Same-appliance Plexamp commissioning owner restores captured player name + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Plexamp native owner calls the real `global.app.rootStore.settings.resetToDefaults()` authority.
- [x] Plexamp live music-player volume resets to **100%** with verification and exact rollback.
- [x] `equalizerPresets` is excluded from native changed-set/fingerprinting as physically proven runtime-normalised state while remaining rollback-covered.
- [x] ACP EQ returns to 0/0/0 dB; Music Master, Plexamp trim, AirPlay trim, Maximum Alarm Volume and AirPlay session-start volume all use the accepted 100% baseline.
- [x] Full multi-owner Confirm crosses the corrected ACP-only browser/server stale-token boundary and completes successfully.

#### Accepted production Home Reset boundary

The current production owner deliberately preserves structure and resets only presentation:

- [x] preserve Home section order;
- [x] preserve hidden/visible choices;
- [x] preserve custom-added sections;
- [x] preserve validated custom section titles;
- [x] reset only current-context per-section `viewSettings` presentation data to Plexamp's own per-section defaults;
- [x] leave `order`, `hidden`, `editing`, custom-hub, auth and cache records untouched.

The bounded presentation family is:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

Physical acceptance proved this presentation-only owner works on the commissioned appliance while preserving order and visibility.

#### Full Home-customisation persistence investigation

A genuinely fresh disposable Chromium profile established that Plexamp can build a complete effective Home from account/library/runtime context with no Home edits. The pre-login 0-hub state is unresolved context, not a factory target; after login/library selection Plexamp populated the effective Home itself.

Causal disposable-profile evidence now closes three durable owners:

```text
9224 order tracer        Mixes for you moved to third
                          order=1, hidden=0

9225 hidden tracer       Recent Plays hidden
                          hidden=1, order=0

9226 presentation tracer Recent Plays → Carousel
                          viewSettings=1 after page refresh and full Chromium restart
                          editing=0 after reload

9227 editor-only control Open/close Home editor, change nothing
                          all Home families remain zero
```

Specific conclusions:

- [x] **Order:** moving Mixes for you survives page refresh and full Chromium restart; an explicit browser-local `...:<section>:order` key is present only on the order tracer.
- [x] **Hidden/visible:** hiding Recent Plays creates exactly one `hidden` record, survives page refresh and full Chromium restart, and leaves order at default.
- [x] **Presentation:** changing Recent Plays to Carousel from an all-zero profile creates `viewSettings=1` plus transient `editing=1`; after normal reload `editing` disappears while `viewSettings=1` and the Carousel remain. A full Chromium process exit/relaunch preserves the Carousel with exactly `viewSettings=1`, `editing=0`.
- [x] **Editor-only control:** entering and leaving the editor without changing anything creates no Home record at all.
- [x] No Local Storage values were read by the family diagnostics; Session Storage/IndexedDB were ruled out in the earlier browser-storage inventory.

Therefore Home **order**, **hidden/visible** and built-in **presentation** persistence are all closed as bounded browser-profile-local Local Storage owners. `editing` is transient edit bookkeeping, not a durable presentation owner.

The preferred full-Home design remains “let Plexamp rebuild itself”:

1. preserve Plex authentication/session, selected library, commissioned player name/output and unrelated browser/cache state;
2. classify the complete bounded browser-profile-local Home persistence authority;
3. do **not** construct, copy or directly mutate the transient runtime hub array;
4. capture exact rollback state for narrowly proven Home-owned records;
5. clear only those records;
6. trigger the narrowest proven Plexamp Home reload/re-fetch mechanism;
7. let Plexamp regenerate its own effective Home;
8. verify rebuilt logical Home plus continued login/library state;
9. rollback if a later transaction participant fails.

#### Next physical investigation

- [x] order persistence + full-process durability;
- [x] hidden/visible persistence + full-process durability;
- [x] built-in presentation persistence + full-process durability;
- [x] editor-only control;
- [ ] classify **custom-added section persistence** on a fresh isolated profile;
- [ ] classify **custom section title persistence** one change at a time;
- [ ] define exact full-Reset semantics for custom-added sections/titles from that evidence;
- [ ] only then build a disposable-only reversible scrub/rebuild experiment across the complete classified Home-owned family set;
- [ ] decide whether full Home structure joins #93 or remains a tightly scoped follow-up.

#### Automated evidence

- [x] Tests #4575 passed on `07fec02c85a6871cc3a74160b7cd029ff7736f2c`.
- [x] Tests #4586 passed on `1468d7e58a44664d67b7237f16633a3afce93f4b`.
- [x] Tests #4601 passed on `379a49af5d77de2a3def470ada946fd8246d2664`.
- [x] Tests #4619 passed on `7f5c756de22805fdafcfee0a3e6d7f0c260aedbc`.
- [x] Tests #4620 passed on `f5f0f4e460a12d50666932c75801fb4c692d229d`.
- [x] Tests #4621 passed on `9cdcf1abfc81bf4a9bc050ae4ea85ca1087eaf29`.

#### Remaining gate before #93 can close

- [ ] Classify custom-added section/title persistence one variable at a time.
- [ ] Complete the reversible scrub/rebuild experiment only after the complete Home-owned persistence surface is bounded.
- [ ] Decide from that evidence whether full Home structure joins #93 or remains a follow-up; presentation-only Reset itself is already physically accepted.
- [ ] Pull/reboot the eventual final accepted production head so Chromium reloads the packaged bridge.
- [ ] Fresh production Preview must no longer report `equalizerPresets` as a native Reset difference.
- [ ] If the commissioned Pi ever contains the short-lived 10% AirPlay start value, Reset should offer the accepted return to **100%** and verify both AirPlay session-start and persistent AirPlay trim at 100%.
- [ ] Keep the Home `viewSettings` Backup/Restore completeness follow-up open until implemented or explicitly deferred.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**Do not begin high-resolution-audio implementation until the Settings/appliance-ownership track is deliberately closed or the remaining Home follow-ups are explicitly deferred.**

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — #88 core COMPLETE; #89/#90 Home-presentation portability follow-up OPEN; #93 transaction accepted with full Home rebuild investigation OPEN
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