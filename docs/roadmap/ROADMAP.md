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

### #93 Reset-to-defaults workflow — REVISED FINAL PHYSICAL ACCEPTANCE OPEN

PR #9 remains **Draft and unmerged**. Do not promote it until the revised commissioned-Pi transaction passes and the owner explicitly accepts it.

#### Physically accepted foundations

- [x] ACP Reset transaction generated from version-controlled defaults through production normalisers.
- [x] ACP stale-preview, verification and rollback semantics physically accepted.
- [x] Final 1280×720 Preview/Review/Ready/Confirm presentation physically accepted.
- [x] Same-appliance Plexamp commissioning owner: captured player-name baseline + dynamically resolved **`A Clockwork Plex - Plexamp`** output.
- [x] Deliberate player rename + **Follows system output** produced exactly two differences and Reset restored both without exposing name/UUID values.

#### Native Plexamp settings owner

- [x] Disposable Chromium testing proved Plexamp **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings.
- [x] Read-only bundle inspection established `global.app.rootStore.settings` as the real Plexamp 4.13.2 settings authority.
- [x] Native owner calls Plexamp's real `settings.resetToDefaults()`; no webpack scanning, `eval`, generic page execution, remote debugging or arbitrary DOM automation.
- [x] The eight safe Headless preferences remain portable Backup/Restore values but follow Plexamp's own defaults during Reset.
- [x] Preview now exposes bounded **setting names only** under Technical changed paths, never old/new values. This lets a residual “1 setting differs” be identified safely.
- [x] Plexamp live music-player volume is part of the native transaction: target **100%**, same-origin player API, verified apply and exact pre-reset rollback.

#### Revised Home boundary — preserve structure, reset presentation

Physical investigation disproved the earlier assumption that deleting local order/hidden records necessarily means “factory Home”. Those records can be delta overrides over another effective Home baseline.

The product boundary is therefore now:

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

Built-in non-default `viewSettings` are removed. Custom-section presentation fields are stripped while the custom title is retained. Apply is fingerprint/stale-protected, verifies convergence and retains exact rollback bytes until the outer transaction succeeds.

#### ACP audio Reset baseline — revised

The shipped Reset baseline is now deliberately neutral/full-scale:

- [x] Master EQ enabled, Bass/Mid/Treble all 0.0 dB;
- [x] Music Master 100%;
- [x] Plexamp trim 100%;
- [x] AirPlay trim 100%;
- [x] Maximum Alarm Volume 100%.

The earlier nominal 80% / physically observed 79% Music Master result remains useful ALSA quantisation evidence but is no longer the Reset default.

AirPlay's separate 60% **session-start volume** remains a user preference/runtime policy and is not the persistent AirPlay trim baseline.

#### Automated evidence

- [x] Revised browser/native/Home/audio implementation reached automated green at `c1b98dc018b2e60d4ed8c6fba0999d022155eef9` / **Tests #4550**.
- [x] Compile, JavaScript/page wiring and shell checks all passed.
- [x] Full suite: **1027 tests passed**.
- [x] Regression coverage now includes native changed-key diagnostics, Plexamp player-volume Reset/rollback, Home `viewSettings` reset with exact structure preservation, and all four persistent mixer defaults at 100%.

#### Remaining physical gate before #93 can close

- [ ] Pull and fully reboot the final documentation-synchronised candidate so Chromium reloads the packaged bridge scripts.
- [ ] Set at least one ordinary Plexamp preference away from default and Plexamp player volume below 100%.
- [ ] Change one or more Home section presentation/view options while keeping the desired Home order/visibility/custom sections in place.
- [ ] Optionally keep a temporary player name + Follows system output to re-prove the already accepted commissioning participant inside the combined transaction.
- [ ] Preview must be complete and expose only bounded setting names/counts/fingerprints, not raw values.
- [ ] Review → Confirm & reset.
- [ ] Verify ordinary Plexamp settings follow Plexamp defaults and live Plexamp player volume becomes 100%.
- [ ] Verify Home presentation returns to Plexamp per-section defaults while order, visibility and custom sections remain unchanged.
- [ ] Verify commissioned player name and **A Clockwork Plex - Plexamp** output are restored when deliberately changed.
- [ ] Verify neutral ACP EQ and Music Master/Plexamp trim/AirPlay trim/Maximum Alarm Volume all at 100%.
- [ ] Verify Plex login and selected library survive, with normal playback and dashboard navigation.
- [ ] Fresh Preview converges to zero native/Home-presentation/commissioning differences; ACP should also be zero if intentionally left at shipped defaults.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or merges.

Detailed authority: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**Do not begin high-resolution-audio implementation until #93 is closed.**

## Agreed implementation order

Unless deliberately reprioritised:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — #88–#90 COMPLETE; #93 revised final physical acceptance OPEN
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
