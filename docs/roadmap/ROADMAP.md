# A Clockwork Plex Roadmap

**Last updated:** 5 September 2026  
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
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership and current Home-presentation follow-up;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and current physical/product gate;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally not assigned until its real scope is clear.
- the old `feature/alarm-engine` branch was retired after v0.4.0.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from post-release v0.4.0 baseline.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established the feature-branch → `develop` → accepted release model.

### #85 High-resolution audio feasibility audit — COMPLETE; implementation queued

The current managed EQ and Direct/fallback profiles still use a fixed **S16_LE / 44100 Hz** shared music path. The Raspberry Pi DAC Pro can do more, but no production rate/format change was made by the feasibility audit.

Accepted constraints for later implementation:

- AirPlay compatibility must remain truthful to the received source format;
- scheduled-alarm takeover, Maximum Alarm Volume and recovery are non-negotiable;
- bypass/native/bit-perfect claims must be based on measured ALSA/DAC state, not labels;
- appliance reliability outranks a bit-perfect badge.

### #86 Friendly forecast-location entry — COMPLETE

- [x] Read-only town/city/postcode lookup using Open-Meteo plus Postcodes.io fallback for full UK postcodes.
- [x] Friendly location stages exact forecast coordinates while retaining precise manual latitude/longitude fallback.
- [x] Physical Milland and `GU30 7JS` tests passed.
- [x] Unsupported long-range condition cards are suppressed without corrupting Today/Tomorrow/date labelling.

### #87 WU supplemental indoor expiry — COMPLETE

- [x] Stale Ecowitt indoor supplementation expires while WU outdoor observations remain live.
- [x] Weather removes expired indoor values; Clock retains paired geometry with placeholders.
- [x] Re-enabling Ecowitt restores indoor data without service restart.

**Weather priority #1 for this cycle is complete.**

### #88 Configuration ownership and backup-format audit — COMPLETE

- [x] Portable ACP settings are a normalised logical model, never raw `config.json` bytes.
- [x] Credentials/auth/session, hardware identity/topology, raw ALSA, caches and machine identity are excluded.
- [x] Exact eight-value Plexamp Headless portable allow-list established: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `playerName` and `audioDeviceUuid` classified nonportable.
- [x] Plexamp Home order/per-hub-hidden browser families physically classified without treating the Chromium profile as a backup unit.

### #89 Configuration backup/export — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

- [x] **Configuration backup/export** schema-v1 path physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer and the exact eight typed Headless preferences.
- [x] Credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state excluded.
- [x] Permission-free loopback browser bridge adds validated logical Home **order/hidden** choices.
- [x] Physical final export captured **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.
- [ ] Per-section Home presentation `viewSettings` are **not currently in schema-v1 backup**. Physical restore testing on 5 September confirmed that a backup taken with the Home page looking as desired cannot restore those section-presentation choices because they were never exported.
- [ ] Reconcile the portable logical Home owner with #93's fresh-profile evidence that durable section order can persist outside the previously classified Local Storage `order` family.

### #90 Configuration import/restore — CORE COMPLETE; HOME PRESENTATION FOLLOW-UP OPEN

- [x] Read-only parse/validate/Preview with paths/counts rather than values.
- [x] Stale-protected ACP Settings/EQ/mixer restore with reverse rollback.
- [x] Exact-version eight-value Plexamp Headless restore through the narrow restricted owner.
- [x] Target-context-aware Home order/hidden restore with exact raw rollback.
- [x] Guided **Preview → choose ACP / Plexamp / both → Review → Confirm & restore** presentation physically accepted at 1280×720.
- [x] Final combined physical restore converged back to zero differences for the original supported scope.
- [ ] Extend the portable Home model to validated per-section presentation now that #93 has physically established the bounded `viewSettings` family and rollback semantics.
- [ ] Revalidate logical Home order restore against the newly discovered durable persistence authority once that authority is classified; the previously accepted Local Storage path remains real evidence but is no longer assumed to be exhaustive.

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] **Plexamp Search keyboard/bridge** physically accepted; results update during entry and Done dismisses cleanly.
- [x] General Plexamp text fields physically accepted for Home title, Smart Playlist name/description, Home Screen section title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — COMPLETE

- [x] BBC RSS-only feed/cache authority for Top Stories, UK, World, Science and Technology.
- [x] Public model strips article links/GUIDs; no outbound article navigation.
- [x] Last-good cache, stale/degraded presentation and Top Stories ticker physically accepted.
- [x] Settings, News page, touch scrolling, startup/idle-return and Wi-Fi-loss recovery physically accepted.

### #93 Reset-to-defaults workflow — TRANSACTION ACCEPTED; FULL HOME REBUILD INVESTIGATION OPEN

PR #9 remains **Draft and unmerged**. The complete multi-owner transaction has passed physically and the corrected AirPlay session-start baseline is 100%. The remaining product question is whether the already accepted presentation-only Home Reset is extended to a separately proven full Home-customisation reset which lets Plexamp rebuild its own effective Home.

#### Physically accepted foundations

- [x] ACP Reset transaction generated from version-controlled defaults through production normalisers.
- [x] ACP stale-preview, verification and rollback semantics physically accepted.
- [x] Final 1280×720 Preview/Review/Ready/Confirm presentation physically accepted.
- [x] Same-appliance Plexamp commissioning owner: captured player-name baseline + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Deliberate player rename + **Follows system output** produced exactly two differences and Reset restored both without exposing name/UUID values.
- [x] Full multi-owner Confirm now crosses the corrected ACP-only browser/server stale-token boundary and completes successfully.

#### Native Plexamp settings owner

- [x] Disposable Chromium testing proved Plexamp **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings.
- [x] Read-only bundle inspection established `global.app.rootStore.settings` as the real Plexamp 4.13.2 settings authority.
- [x] Native owner calls Plexamp's real `settings.resetToDefaults()`; no webpack scanning, `eval`, generic page execution, remote debugging or arbitrary DOM automation.
- [x] The eight safe Headless preferences remain portable Backup/Restore values but follow Plexamp's own defaults during Reset.
- [x] Preview exposes bounded **setting names only** under Technical changed paths, never old/new values.
- [x] Plexamp live music-player volume is part of the native transaction: target **100%**, same-origin player API, verified apply and exact pre-reset rollback.
- [x] Physical post-reset diagnostics classified `equalizerPresets` as a runtime-populated/non-convergent catalogue rather than a Resettable user choice. It is excluded from native Reset comparison/fingerprinting while remaining inside the exact rollback snapshot.

#### Current Home Reset boundary — preserve structure, reset presentation

Physical investigation disproved the earlier assumption that deleting local order/hidden records necessarily means “factory Home”. Those records can be delta overrides over another effective Home baseline.

The currently accepted product boundary is therefore:

- [x] preserve Home section order;
- [x] preserve hidden/visible choices;
- [x] preserve custom-added sections;
- [x] preserve validated custom section titles;
- [x] reset only current-context per-section `viewSettings` presentation data to Plexamp's own per-section defaults;
- [x] do not open/mutate order, hidden, editor, custom-hub, auth or cache values during this Home Reset owner.

The bounded family is:

```text
mmkv.default\discovery:customizations:<context>::/library/sections/<id>:<hub-id>:viewSettings
```

Built-in non-default `viewSettings` are removed. Custom-section presentation fields are stripped while the custom title is retained. Real-profile testing established URL-like characters in both context/hub identifiers; the matcher remains structurally bounded and fails closed on an unclassified `viewSettings` family key rather than reporting a false zero.

Physical acceptance proves that Home presentation returns to Plexamp's per-section defaults while the commissioned Home order and visibility choices remain intact.

#### Full Home-customisation reset — persistence authority investigation

A genuinely fresh disposable Chromium profile has now materially changed the preferred design and disproved the assumption that the known Local Storage customisation family is the complete Home persistence authority.

Physical evidence on 5 September established:

- [x] before Plex login/library selection, the live discovery-hub backing collection exists but contains **0 hubs**;
- [x] after signing into the same fresh profile, selecting the intended library and making **no Home changes**, Plexamp populated **12 effective Home hubs by itself**;
- [x] the untouched default Home visibly contains **12 sections**, strongly correlating the 12 runtime hubs with the 12 rendered default Home sections without treating that count as a permanent Plexamp invariant;
- [x] the narrow runtime authority is `rootStore.discovery.$mobx.values.hubs.value.$mobx.values`;
- [x] all 12 hub objects expose consistent logical Home metadata shapes such as `hubIdentifier`, `source`, `title`, `type` and `items`, with many also exposing `hubKey`, `key` and `size`;
- [x] the bounded `scripts/inspect-plexamp-home-hubs.py` probe emits names/types/collection lengths only and does not read primitive values or invoke getters;
- [x] the untouched authenticated/library-selected profile has **zero** `mmkv.default\discovery:customizations:*` keys: 0 `order`, 0 `hidden`, 0 `viewSettings`, 0 `editing`, 0 `customHubs`, 0 `other`, 0 invalid structures and 0 contexts;
- [x] moving the default **Mixes for you** section down two places produced **no key-family delta** in that Local Storage namespace;
- [x] the moved order survived a normal page refresh while that namespace remained empty;
- [x] the moved order then survived a **full disposable Chromium process exit and relaunch using the same profile**, while the same Local Storage probe still returned all-zero family/context counts.

The **0-hub pre-login state is not itself a factory Home target**; it represents an unresolved authentication/library context. The useful positive finding remains that Plexamp can build the effective default Home itself once authentication and library context exist. However, the later order experiment establishes an equally important negative finding: **the known `mmkv.default\discovery:customizations:*` Local Storage family is not the complete Home persistence authority**.

The durable order owner is therefore currently **unclassified**. It may be another browser-local persistence surface; IndexedDB is a candidate but is not assumed or treated as proven. The reorder is no longer plausibly only live MobX/session state because it survived a complete browser-process restart.

The preferred full-Home design remains “let Plexamp rebuild itself”, but its mutation boundary is now deliberately unresolved:

1. preserve Plex authentication/session, selected library, commissioned player name/output and unrelated browser/cache state;
2. identify the complete bounded persistence authority for Home customisation rather than assuming one Local Storage family is exhaustive;
3. do **not** construct, copy or directly mutate the transient runtime hub array;
4. only after the persistence owner is classified, capture exact rollback state for the narrowly proven Home-owned records;
5. clear only those classified Home-owned records and trigger the narrowest proven Plexamp Home reload/re-fetch mechanism;
6. let Plexamp regenerate its own effective Home;
7. verify the rebuilt logical Home plus continued login/library state before the outer Reset transaction finalises.

This remains preferable to hard-coding the observed 12 rows because hub identity/membership is account/library/runtime-derived and may legitimately evolve with Plexamp. But a full production Home reset **must not** be implemented by deleting only the old Local Storage order/hidden/view families.

Next physical investigation:

- [x] inventory the known Home customisation Local Storage key families on the untouched disposable profile: all recognised family counts and matching-key/context counts are zero;
- [x] isolate an order-only edit and prove it is durable across page refresh and full Chromium process restart while the known Local Storage family remains empty;
- [ ] run the new bounded `scripts/inspect-plexamp-browser-storage.py` metadata probe against the current tracer profile: Local/Session Storage key-family counts plus IndexedDB database/object-store **names only**, with no Web Storage values, IndexedDB records or transactions;
- [ ] use that current metadata inventory only to identify candidate persistence surfaces; because there is no pre-edit baseline from this broader probe, do not attribute the order change from a single inventory alone;
- [ ] classify the actual durable order persistence authority before making any additional visibility/presentation/custom-section edits, using a still-narrower comparison or second genuinely fresh disposable baseline if needed;
- [ ] once order ownership is understood, continue one change at a time for hidden/visible state, presentation and one custom section/title;
- [ ] prove a reversible disposable-profile scrub of only the complete classified Home-owned state followed by Plexamp rebuild returns to the untouched effective Home while login and selected library remain intact;
- [ ] define exact full-Reset semantics for custom-added sections/titles from that evidence;
- [ ] only then consider replacing the accepted presentation-only production owner.

Until that experiment passes, presentation-only Home Reset remains the proven production boundary.

#### ACP audio and AirPlay Reset baseline — corrected

The shipped Reset baseline is deliberately neutral/full-scale:

- [x] Master EQ enabled, Bass/Mid/Treble all 0.0 dB;
- [x] Music Master 100%;
- [x] Plexamp trim 100%;
- [x] AirPlay trim 100%;
- [x] Maximum Alarm Volume 100%;
- [x] AirPlay session-start volume **100%**.

The earlier nominal 80% / physically observed 79% Music Master result remains useful ALSA quantisation evidence but is no longer the Reset default.

The brief 10% AirPlay session-start change introduced during the 5 September follow-up was a typo, immediately corrected back to the intended 100% full-scale baseline.

#### Physical and automated evidence

- [x] Exact `4e01b289fbfec352d41d345a50e22dcc30bf53a3` physically produced a complete commissioned-Pi Preview with bounded native names and real Home `viewSettings` counts: one state showed 25 total changes including 15 Home presentation records.
- [x] Recreated full-state Review reached **Ready to confirm** with 20 server-owned, 16 native Plexamp and 14 Home-presentation changes.
- [x] The first full Confirm exposed the false ACP-stale hand-off because the old browser/server check reused the broader #90 restore token; retained browser-native/Home rollback restored the prestate correctly.
- [x] The hand-off is now split correctly: `owner_tokens.a_clockwork_plex` fingerprints only ACP target/current state; the broader #90 `restore_preview_token` remains separate for the actual server restore transaction; commissioning keeps its own fingerprint.
- [x] The corrected full transaction then completed physically. Plexamp Home presentation reset while order/visibility stayed put; Plexamp player volume became 100%; ACP EQ became 0/0/0 dB and all four persistent mixer levels became 100%.
- [x] A fresh Preview then exposed three native residual names: `activeTab`, `equalizerPresets`, `showFullScreenPlayerOnStart`. A second Reset converged `activeTab` and `showFullScreenPlayerOnStart`; a further Preview left only `equalizerPresets`.
- [x] `equalizerPresets` is now excluded as physically proven runtime-normalised state, with a regression that simulates post-reset repopulation and proves exact rollback still retains/restores the pre-reset catalogue.
- [x] **Tests #4575** passed on `07fec02c85a6871cc3a74160b7cd029ff7736f2c`: compile, JavaScript/page wiring, shell checks and **1029 tests** in 53.364s.
- [x] AirPlay session-start default corrected in source/regression from the accidental 10% back to the intended 100%.
- [x] Fresh disposable Chromium broad and narrow read-only probes physically established the 0 → 12 authenticated effective-Home rebuild and the bounded discovery-hub authority.
- [x] The new narrow hub probe's own four regression tests passed; the first full CI run exposed only missing script/test catalogue entries, which were corrected immediately.
- [x] The untouched Home-customisation inventory physically returned zero matching keys/families while the 12-section Home was fully rendered.
- [x] **Tests #4586** passed on `1468d7e58a44664d67b7237f16633a3afce93f4b`: compile, JavaScript/page wiring, shell checks and the complete **1037-test** unit suite.
- [x] The order-only tracer physically survived page refresh and a full disposable Chromium process restart while the known Local Storage Home namespace remained empty.
- [ ] The broader browser-storage metadata probe and its four regression guards must pass CI before its physical output is used as evidence.

#### Remaining gate before #93 can close

- [ ] Get the broader browser-storage metadata diagnostic candidate green in CI.
- [ ] Classify the durable Home order persistence authority, then continue the one-change-at-a-time Home investigation.
- [ ] Complete the reversible scrub/rebuild experiment only after the complete Home-owned persistence surface is bounded.
- [ ] Decide from that evidence whether full Home structure joins #93 or remains a tightly scoped follow-up; the presentation-only implementation itself is physically accepted.
- [ ] Pull/reboot the eventual final accepted branch head so Chromium reloads the packaged production bridge.
- [ ] Fresh production Preview must no longer report `equalizerPresets` as a native Reset difference.
- [ ] If the commissioned Pi ever contains the short-lived 10% AirPlay start value, ACP Preview should offer one change back to **100%**; apply it and verify both AirPlay session-start and persistent AirPlay trim are 100%.
- [ ] Keep the Home `viewSettings` backup/restore completeness follow-up open until implemented or explicitly deferred.
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
7. **Appliance resilience** — cross-cutting release-quality track
8. **Events calendar**

This priority list is authoritative.

## Future product backlog

These are post-v0.4.0 product areas, not commitments to one release. Design/test independently before promotion to `main`.

### High-resolution Plexamp audio / mixer-EQ path

The current v0.4.0 audio profiles use a fixed **16-bit / 44.1 kHz** shared music path. Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

Before production mutation, use `scripts/audio/preflight-eq.sh` as the **read-only bedroom-Pi validation gate**. The **accepted production SD remains protected**; **a separate spare SD is the disposable acceptance target** for destructive route/lifecycle experiments.

- [ ] Physical capability audit with known 16/44.1, 24/48, 24/96 and 24/192 Plex files; record Plexamp mode/rate, DAC hardware params and live ALSA state.
- [ ] Choose a managed high-resolution bus by measured CPU/stability/latency rather than maximum-number enthusiasm.
- [ ] Remove the managed 16/44.1 bottleneck while preserving source trims → Music Master → fixed -6.5 dB reserve → Bass/Mid/Treble → limiter and post-EQ scheduled-alarm join.
- [ ] Define truthful EQ-active high-resolution and native-bypass behaviour; never call a path bit-perfect while volume/reserve/limiting/resampling remains active.
- [ ] Investigate source-rate-native Direct Plexamp across 44.1/48/88.2/96/176.4/192 kHz.
- [ ] Define deliberate resampling policy for Plexamp and lower-rate AirPlay sources.
- [ ] Expose source, processing and final DAC format/rate separately in diagnostics.
- [ ] Regression/physical acceptance: route/fallback, EQ active/bypass, alarm takeover, AirPlay both directions and recovery.

### Astronomy — major application area

Treat Astronomy as a touch-first numerical astronomy section in the spirit of Peter Duffett-Smith rather than decorative horoscope content. 🔭

- [ ] Deterministic local/offline calculation authority with reference fixtures and tolerances.
- [ ] Observer/location model reusing existing coordinates/timezone where sensible.
- [ ] Overview/Tonight: Julian Date, local/Greenwich sidereal time, Sun/Moon headline state and useful events.
- [ ] Sun: rise/transit/set, twilight classes, day length, RA/Dec and altitude/azimuth.
- [ ] Moon: rise/transit/set, phase/age/illumination, next principal phases, distance/angular diameter, RA/Dec and altitude/azimuth.
- [ ] Planets Mercury–Neptune: rise/transit/set and useful position/magnitude/elongation data where reliable.
- [ ] Touch-first 1280×720 navigation plus night presentation.
- [ ] Validate circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Appliance resilience — cross-cutting release-quality track

Detailed design/security constraints: [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md).

- [ ] Investigate intermittent read-only root-filesystem/SD behaviour observed during real commissioned-Pi testing; collect storage/kernel evidence before changing policy.
- [ ] Reduce avoidable appliance writes where this does not weaken rollback/history/recovery.
- [ ] Design kiosk-safe Wi-Fi recovery: bounded temporary NetworkManager-backed recovery AP, on-screen QR join path and local captive-portal-style SSID/passphrase entry.
- [ ] Keep Wi-Fi credentials out of query strings, argv, logs, browser history and persistent recovery pages.
- [ ] Define recovery timeout/rollback so a failed reconfiguration cannot strand the appliance indefinitely.
- [ ] Add truthful health/status for storage, network and critical appliance services without turning diagnostics into an automatic mutator.

### Events calendar

- [ ] Define source/credential ownership before implementation; calendar credentials must remain outside ordinary portable configuration.
- [ ] Build a cache-first, touch-friendly upcoming-events model suitable for the bedside dashboard.
- [ ] Reuse global date/time formatting and existing screen/idle ownership.
- [ ] Design stale/offline behaviour so previously fetched events remain useful without pretending to be current.
- [ ] Keep external event links/navigation out of the kiosk unless explicitly designed and safely owned.

## Release gate for the next version

Before promoting the next development cycle to `main`:

- all included feature branches must be merged into `develop` only after their own automated and physical acceptance;
- the clean-room installer/runbook must still pass on the supported hardware path;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and the live roadmap must describe the actual shipped state;
- the accepted production appliance must not be used as the disposable target for destructive audio/storage experiments;
- release version/tag/name is assigned only after final scope and acceptance are known.