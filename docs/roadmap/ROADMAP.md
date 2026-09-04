# A Clockwork Plex Roadmap

**Last updated:** 4 September 2026  
**Active development branch:** `develop`  
**Stable branch:** `main`  
**Current release:** **`v0.4.0` — Unified Bedside Appliance — PUBLISHED 23 August 2026.**

> This roadmap began as the EQ/audio-installer plan. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, AirPlay acquired an arbitration layer, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation, release and future-product roadmap. Detailed engineering chronology belongs in the history/development documents rather than burying the useful current plan.

Historical and specialist authorities:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — detailed early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot through replacement-SD acceptance;
- [`../development/evidence/final-clean-room-physical-progress-2026-08-21.md`](../development/evidence/final-clean-room-physical-progress-2026-08-21.md) — replacement-SD physical evidence;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) — #88–#90 portability/restore ownership;
- [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md) — checkpoint #93 Reset ownership, transaction boundaries and remaining physical gate;
- [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md) — queued storage/Wi-Fi resilience design.

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not this development roadmap.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop` and returns to `develop` only after validation.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally not assigned until its actual scope is clear.
- the old `feature/alarm-engine` branch was retired after v0.4.0; history remains in `main`, PR #2 and the immutable release tag.

## Current development cycle

### #84 Development-cycle bootstrap — COMPLETE

- [x] Created `develop` from post-release `main` head `a2ccc85cbd1d264e7ebedcf50b82084a4289c09a`.
- [x] GitHub Actions validates `develop` and `main`.
- [x] Established v0.4.0 as the baseline for all new work.
- [x] Added Events calendar, BBC News and Astronomy to the product backlog.

### #85 High-resolution audio feasibility audit — COMPLETE; implementation queued

The current managed EQ and Direct/fallback profiles both use a fixed **`S16_LE` / `44100` Hz** shared music path. The Raspberry Pi DAC Pro is capable of higher rates, but no production format/rate change was made by #85.

Accepted constraints for later implementation:

- AirPlay compatibility must remain truthful to the received source format;
- scheduled-alarm takeover, Maximum Alarm Volume and recovery are non-negotiable;
- bypass/native/bit-perfect claims must be based on measured ALSA/DAC state, not UI labels;
- appliance reliability outranks a bit-perfect badge.

### #86 Friendly forecast-location entry — COMPLETE

- [x] Added read-only friendly town/city/postcode lookup using Open-Meteo and Postcodes.io fallback for full UK postcodes.
- [x] Settings → Weather → Online forecast can stage a friendly location while retaining exact latitude/longitude as advanced fallback.
- [x] Save Changes remains the only persistence authority.
- [x] Physical Milland and `GU30 7JS` tests passed.
- [x] Long-range `Unknown conditions` cards were suppressed without corrupting Today/Tomorrow/date labelling.

### #87 WU supplemental indoor expiry — COMPLETE

- [x] Stale Ecowitt indoor supplementation is removed after the configured freshness window while WU outdoor observations remain live.
- [x] Weather removes the Indoor row; Clock retains paired geometry with `—` placeholders.
- [x] Re-enabling Ecowitt restores indoor values automatically without service restart.

**Weather priority #1 for this cycle is complete.**

### #88 Configuration ownership and backup-format audit — COMPLETE

- [x] Portable ACP settings are a normalised logical model, never raw `config.json` bytes.
- [x] Credentials/auth/session state, hardware identity/topology, raw ALSA state, runtime caches and machine identity are excluded.
- [x] Commissioned Plexamp 4.13.2 audit found 35 Headless Settings files: 11 safe-looking candidate names and 24 unclassified/excluded.
- [x] Exact portable Headless allow-list established: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `playerName` and `audioDeviceUuid` remain excluded from portable Backup/Restore; #93 gives them a separate same-appliance commissioning owner.
- [x] Plexamp Home `order` / per-hub `hidden` browser families were physically classified without turning the Chromium profile or LevelDB into a backup unit.

### #89 Configuration backup/export — COMPLETE

- [x] **Configuration backup/export** schema-v1 path is physically accepted.
- [x] Export contains normalised ACP settings, logical EQ/mixer, and the exact eight typed Headless preferences.
- [x] WU/Plex credentials, browser auth/session, player/device identity, hardware topology and runtime/cache state are excluded.
- [x] Permission-free loopback-only Plexamp browser bridge adds validated logical Home order/hidden data in browser memory.
- [x] Physical final export captured **15 ordered Home identifiers + 1 hidden identifier**, no browser omission and zero warnings.

### #90 Configuration import/restore — COMPLETE

All four restore phases are physically accepted:

- [x] read-only parse/validate/Preview with changed paths/counts rather than old/new values;
- [x] stale-protected transactional ACP Settings/EQ/mixer restore with reverse rollback;
- [x] exact-version eight-value Plexamp Headless restore through the narrow restricted owner and service coordination;
- [x] target-context-aware Plexamp Home order/hidden restore with exact raw browser rollback;
- [x] guided **Preview → choose A Clockwork Plex / Plexamp / both → Review selected restore → Confirm & restore** presentation physically accepted at 1280×720;
- [x] final combined physical restore applied one ACP/server + one Plexamp Home change and converged back to zero differences.

Detailed evidence and ownership remain in [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md).

### #91 Touchscreen Plexamp text entry — COMPLETE

- [x] Shared Settings keyboard uses true one-shot Shift and theme-aware presentation.
- [x] **Plexamp Search keyboard/bridge** physically accepted; results update while text is entered and Done dismisses cleanly.
- [x] General Plexamp text fields physically accepted for Home section Title, Smart Playlist Name/Description, Home Screen section Title and Player Name.
- [x] Bridge remains permission-free, loopback-only and excludes login/password fields.

### #92 BBC News — COMPLETE

- [x] BBC RSS-only feed/cache authority implemented for Top Stories, UK, World, Science and Technology.
- [x] Public model strips article links/GUIDs; no outbound article navigation is possible.
- [x] Background last-good cache, stale/degraded presentation and Top Stories ticker physically accepted.
- [x] Settings, left-rail News page, touch scrolling, weather-style scrollbar, startup and idle-return integration physically accepted.
- [x] Real Wi-Fi loss proved cached News/ticker remains usable and fresh behaviour resumes after reconnect.

### #93 Reset-to-defaults workflow — FINAL COMBINED PHYSICAL ACCEPTANCE OPEN

**Already physically accepted:**

- [x] ACP Reset transaction generated from version-controlled defaults through production normalisers.
- [x] 27-change commissioned-Pi ACP Reset, including physically observable **79%** Music Master default.
- [x] Reset presentation: hidden-before-Preview, Review/Ready layout and full-width final confirmation.
- [x] Same-appliance Plexamp commissioning Reset on 3 September 2026: setup-captured `playerName` baseline plus dynamically resolved **`A Clockwork Plex - Plexamp`** output. A deliberate player rename + **Follows system output** produced exactly two differences and Reset restored both without leaking name/UUID values.

**Native Plexamp/Home semantics now established:**

- [x] Disposable fresh Chromium profile with the same Plex account/library proved the genuine default Home is browser/device-local rather than account-synchronised.
- [x] Plexamp **Debugging → Reset to Defaults** preserves login and selected library while resetting ordinary settings.
- [x] Plexamp **Home Screen → Reset order** restores default Home ordering.
- [x] Reset order alone leaves deliberately hidden sections hidden, so Home visibility requires its own bounded reset owner.

**Implementation automated-green:**

- [x] `browser/plexamp-bridge/native-reset.js` invokes Plexamp's own `settings.resetToDefaults()` rather than maintaining guessed ACP copies of ordinary Plexamp defaults.
- [x] Native Preview exposes only bounded status/count/fingerprint and excludes commissioning identity.
- [x] All eight portable Headless preferences are excluded from native Reset counting, captured before Plexamp's reset, immediately re-applied/verified afterwards, and included in rollback verification. #93 therefore does not consume the later high-resolution-audio policy scope.
- [x] Home Reset covers bounded modern contextual order/hidden records plus exact legacy `discovery:customizations:order` / `hidden` records, with stale refusal and exact raw rollback.
- [x] Extension remains one isolated permission-free loopback content-script entry; the native page-world script is one loopback-scoped packaged resource injected by that bridge. No remote debugging/background/cookie authority was added.
- [x] Combined client retains browser-owner rollback tokens, revalidates the reviewed ACP server token before server mutation, then lets the existing ACP/commissioning transaction apply and verify.
- [x] Exact code candidate `fe2409f36584d360afc05c474bfbea6e8ff4657a` passed **Tests #4506: 1027 tests in 51.242s, `OK`** with compile, JavaScript/page-wiring, shell, extension-security and unit gates green.

**Remaining physical gate before #93 can close:**

- [ ] Fully restart Chromium/kiosk on the final docs-synchronised branch candidate so the changed extension is loaded.
- [ ] Record the eight protected Headless values before testing.
- [ ] Deliberately change harmless ordinary Plexamp settings, Home order and Home visibility; optionally repeat the already-accepted commissioning deviations as an integration check.
- [ ] Preview must report bounded native/Home/commissioning work without exposing credentials, player-name values, UUIDs or raw Home values.
- [ ] Confirm Reset and verify: ordinary Plexamp defaults restored; genuine default Home order restored; deliberately hidden section visible again; commissioned player/output correct; all eight protected Headless values unchanged; login and selected library preserved; playback/dashboard healthy.
- [ ] Fresh Preview must converge to zero native/Home/commissioning differences. ACP can also be checked at zero once the appliance is intentionally left at shipped ACP defaults.
- [ ] Explicit owner acceptance required before PR #9 leaves Draft or is merged.

Detailed architecture: [`../development/architecture/reset-to-defaults.md`](../development/architecture/reset-to-defaults.md).

**Do not begin high-resolution-audio implementation until #93 is closed.**

## Future product backlog — next development cycle

These are post-v0.4.0 ideas, not commitments to one release. Design/test independently before promotion to `main`.

### Agreed implementation order

Unless deliberately reprioritised, implementation proceeds in this order:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — #88–#90 COMPLETE; #93 ACP/presentation + Plexamp commissioning PHYSICALLY ACCEPTED; native Plexamp settings + Home order/visibility automated-green; final combined physical acceptance OPEN
3. **Touchscreen Plexamp text entry** — COMPLETE at checkpoint #91
4. **BBC News** — COMPLETE at checkpoint #92
5. **High-resolution Plexamp audio / mixer-EQ path**
6. **Astronomy**
7. **Appliance resilience** — cross-cutting release-quality track
8. **Events calendar**

This priority list is authoritative.

### Settings and appliance ownership

- [x] Configuration ownership audit — COMPLETE #88.
- [x] Configuration backup/export — COMPLETE #89.
- [x] Configuration import/restore — COMPLETE #90.
- [ ] Reset-to-defaults — final native/Home commissioned-Pi acceptance OPEN #93; PR #9 remains Draft and must not merge without explicit owner approval.

### Touchscreen Plexamp text entry

- [x] Shared touch keyboard physically accepted.
- [x] Plexamp Search keyboard/bridge physically accepted.
- [x] General classified Plexamp text fields physically accepted.

### BBC News

- [x] Feed/cache/Settings/UI/ticker/startup/idle/stale recovery physically accepted at #92.

### High-resolution Plexamp audio / mixer-EQ path

The current v0.4.0 audio profiles use a fixed **16-bit / 44.1 kHz** shared bus. Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

Before any production mutation, use `scripts/audio/preflight-eq.sh` as the **read-only bedroom-Pi validation gate**. The **accepted production SD remains protected**; **a separate spare SD is the disposable acceptance target** for destructive route/lifecycle experiments.

- [ ] **Physical capability audit.** Use known 16/44.1, 24/48, 24/96 and 24/192 Plex files. Record Plexamp output mode/rate, DAC `aplay --dump-hw-params` and live ALSA `/proc/asound/.../hw_params`.
- [ ] **Choose managed high-resolution bus.** Compare at least 24/96 and 24/192-class operation for CPU, stability, latency and CamillaDSP; do not choose 192 kHz merely because hardware advertises it.
- [ ] **Remove managed 16/44.1 bottleneck** while preserving source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → limiter and post-EQ scheduled-alarm join.
- [ ] **EQ-active high-resolution + native bypass.** Report managed bypass rather than claiming bit-perfect whenever volume/reserve/limiting/resampling remains active.
- [ ] **Investigate source-rate-native Direct Plexamp** across 44.1/48/88.2/96/176.4/192 kHz and sample-rate matching.
- [ ] **Define deliberate resampling policy** for Plexamp and lower-rate AirPlay sources.
- [ ] **Expose truthful diagnostics:** source format/rate, internal processing format/rate and final DAC format/rate separately.
- [ ] **Regression + physical acceptance:** route/fallback, EQ active/bypass, alarm takeover, AirPlay both directions and recovery.

### Astronomy — major new application area

Treat Astronomy as a multi-screen touch section in the spirit of Peter Duffett-Smith: useful numerical astronomy rather than decorative horoscope content. 🔭

- [ ] Deterministic local/offline calculation authority with reference fixtures/tolerances.
- [ ] Observer/location model reusing existing latitude/longitude/timezone where sensible.
- [ ] Overview/Tonight: Julian Date, local/Greenwich sidereal time, Sun/Moon headline state and useful rise/set events.
- [ ] Sun: sunrise/transit/sunset, civil/nautical/astronomical twilight, day length, RA/Dec, altitude/azimuth.
- [ ] Moon: rise/transit/set, phase/age/illumination, next principal phases, distance/angular diameter, RA/Dec, altitude/azimuth.
- [ ] Planets: Mercury–Neptune rise/transit/set and useful position/magnitude/elongation data where reliable.
- [ ] Touch-first 1280×720 navigation plus night presentation.
- [ ] Validation for circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Appliance resilience — cross-cutting release-quality track

Detailed design/security constraints live in [`../development/architecture/appliance-resilience.md`](../development/architecture/appliance-resilience.md).

- [ ] Investigate intermittent read-only root-filesystem/SD behaviour observed during real commissioned-Pi testing; collect storage/kernel evidence before changing policy.
- [ ] Reduce avoidable appliance writes where this does not weaken rollback/history/recovery semantics.
- [ ] Design kiosk-safe Wi-Fi recovery: bounded temporary NetworkManager-backed recovery AP, on-screen QR join path and local captive-portal-style SSID/passphrase entry.
- [ ] Credentials must never enter query strings, argv, logs, browser persistence or ACP backup; privileged network mutation must remain narrow.
- [ ] Physical Wi-Fi recovery acceptance using touchscreen + phone only, without disrupting working Ethernet.
- [ ] Multi-day storage-endurance physical gate after write hardening.

### Events calendar

- [ ] **Events calendar design spike.** Prefer local-first storage and/or read-only iCalendar/ICS/CalDAV as starting points; cloud-provider integrations remain separate.
- [ ] Today, upcoming events and compact month/date views; distinguish all-day/timed events.
- [ ] Calendar Settings/ownership must keep credentials/remote secrets out of browser-visible configuration and make offline/stale state explicit.
- [ ] Calendar events never silently become alarm-clock alarms; reminders require explicit future policy.

### Weather

- [x] Friendly forecast-location entry — COMPLETE #86.
- [x] WU supplemental-indoor expiry — COMPLETE #87.

**Weather is complete for the agreed next-cycle scope.**

## Deliberately not on the future list

Already implemented/accepted: scheduled alarms and real playback; night dimming/touch-to-wake; burn-in shifting; Weather history/provider selection; idle-return/dashboard behaviour; alarm Settings/status; AirPlay receiver naming; managed EQ and source/master/alarm gain controls; fresh-install/setup automation.

Keeping completed work off the future list matters. Otherwise the roadmap starts requesting features the appliance already has, which is an impressively inefficient form of time travel. 🕰️

## v0.4.0 release exit sequence

1. [x] Physical replacement-SD clean-room acceptance through #64.
2. [x] Repository/release hygiene through #72.
3. [x] Documentation/portability/branch hygiene through #77.
4. [x] Maintainer test-suite catalogue (#78).
5. [x] Settings → About/version contract (#79).
6. [x] Release-ready README/INSTALL and visual first-use material (#80).
7. [x] Pre-approval validation (#81).
8. [x] Final blank-Pi follow-up/spot-check (#82).
9. [x] Explicit owner approval for PR #2 merge — received 23 August 2026.
10. [x] PR #2 merged to `main`; exact merge `d5481b4d52627cbf57a2aa32f974d619fb38ee75` passed Tests #4200; `v0.4.0` published and verified identical (#83).

**All v0.4.0 release gates are complete.**
