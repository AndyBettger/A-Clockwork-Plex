# A Clockwork Plex Roadmap

**Last updated:** 4 September 2026  
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
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — #93 Reset ownership and current physical gate;
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

### #89 Configuration backup/export — COMPLETE

- [x] **Configuration backup/export** schema-v1 path physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer and the exact eight typed Headless preferences.
- [x] Credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state excluded.
- [x] Permission-free loopback browser bridge adds validated logical Home choices.
- [x] Physical final export captured **15 ordered Home identifiers + 1 hidden identifier** with zero warnings.

### #90 Configuration import/restore — COMPLETE

- [x] Read-only parse/validate/Preview with paths/counts rather than values.
- [x] Stale-protected ACP Settings/EQ/mixer restore with reverse rollback.
- [x] Exact-version eight-value Plexamp Headless restore through the narrow restricted owner.
- [x] Target-context-aware Home order/hidden restore with exact raw rollback.
- [x] Guided **Preview → choose ACP / Plexamp / both → Review → Confirm & restore** presentation physically accepted at 1280×720.
- [x] Final combined physical restore converged back to zero differences.

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

### #93 Reset-to-defaults workflow — FINAL COMBINED PHYSICAL ACCEPTANCE OPEN

PR #9 remains **Draft and unmerged**. Do not promote it until the final commissioned-Pi combined transaction passes and the owner explicitly accepts it.

#### Physically accepted foundations

- [x] ACP Reset transaction generated from version-controlled defaults through production normalisers.
- [x] Real commissioned-Pi ACP Reset, including physically observable **79%** Music Master default.
- [x] Final 1280×720 Preview/Review/Ready/Confirm presentation.
- [x] Same-appliance Plexamp commissioning owner: captured player-name baseline + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Deliberate player rename + **Follows system output** produced exactly two differences and Reset restored both without exposing name/UUID values.

#### Native Plexamp/Home semantics established

- [x] Disposable fresh Chromium profile using the same account/library proved the genuine default Home is browser/device-local (`Mixes for You` first in the physical test).
- [x] Plexamp **Debugging → Reset to Defaults** preserves login/library while resetting ordinary settings.
- [x] Plexamp **Home Screen → Reset order** restores default Home ordering.
- [x] Reset order alone does not unhide a hidden section, so visibility has its own bounded Reset ownership.

#### First combined physical candidate — useful fail-closed result

On 4 September 2026 the first combined native/Home candidate was pulled and the appliance fully rebooted.

Physical Preview proved:

- [x] the changed extension was loaded;
- [x] Home Reset correctly saw **1 deliberate order + 1 deliberate visibility record**;
- [x] commissioning correctly saw **2 deliberate changes**;
- [x] Preview exposed only logical paths/counts, not raw Home values, player name or UUID;
- [x] native settings inspection failed closed as `runtime-unavailable`, so Review/Confirm stayed blocked and nothing was partially reset.

The four deliberate test deviations remain intentionally in place for the corrected candidate:

- Artists hidden;
- Recently Added in Music moved to the top;
- temporary Plexamp player name;
- audio output changed to Follows system output.

#### Native runtime correction — automated green

Read-only inspection of the installed Plexamp 4.13.2 static bundle established that module `92895` proxies settings through `global.app.rootStore.settings`. The real bundle is a closed webpack IIFE and does not expose the `webpackChunk*` runtime/cache assumed by the first implementation.

- [x] Native owner now uses Plexamp's application-global settings store directly.
- [x] No webpack module scanning, `eval`, generic JavaScript execution or arbitrary DOM automation is used.
- [x] Extension remains one isolated permission-free loopback content-script entry plus one loopback-scoped packaged page-world resource; no background/cookie/remote-debug authority.
- [x] Native Preview remains bounded status/count/fingerprint only; `playerName` and `audioDeviceUuid` stay separately commissioned.
- [x] Native apply uses Plexamp's own `settings.resetToDefaults()`, verifies against a fresh settings instance and retains exact rollback state until the outer transaction succeeds.
- [x] Corrected implementation `c2754171b6394485306df6aebf21df4d2c2e3e33` passed **Tests #4512: 1027 tests in 49.344s, `OK`**, including compile, JavaScript/page-wiring, shell and full unit suite.

#### Corrected Headless Reset ownership

The eight safe Headless preferences remain the exact portable **Backup/Restore** allow-list, but they are **not ACP-owned Reset baselines**.

Earlier #88/#90 audit values and the different values observed on 4 September are evidence of real appliance state, not Plexamp-default constants. #93 now lets these ordinary Plexamp settings follow Plexamp's own `resetToDefaults()` semantics. Future high-resolution work may deliberately claim specific values later, but must establish that ownership explicitly rather than inheriting an accidental Reset policy.

#### Remaining physical gate before #93 can close

- [ ] Pull and fully reboot the final documentation-synchronised corrected candidate.
- [ ] Preview must become complete: native Plexamp + Home + commissioning owners all inspect successfully.
- [ ] Native Preview must expose only bounded count/fingerprint semantics, not raw settings.
- [ ] Review → Confirm & reset.
- [ ] Verify ordinary Plexamp settings follow Plexamp defaults.
- [ ] Verify genuine default Home order is restored and Artists is visible again.
- [ ] Verify commissioned player name and **A Clockwork Plex - Plexamp** output are restored.
- [ ] Verify Plex login and selected library survive, with normal playback and dashboard navigation.
- [ ] Verify the eight safe Headless preferences follow Plexamp's own defaults rather than an ACP hard-coded baseline.
- [ ] Fresh Preview converges to zero native/Home/commissioning differences; ACP should also be zero if left at shipped defaults.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**Do not begin high-resolution-audio implementation until #93 is closed.**

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — #88–#90 COMPLETE; #93 final combined physical acceptance OPEN
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

The current v0.4.0 audio profiles use a fixed **16-bit / 44.1 kHz** shared bus. Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

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
