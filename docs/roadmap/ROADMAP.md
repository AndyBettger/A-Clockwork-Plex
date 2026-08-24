# A Clockwork Plex Roadmap

**Last updated:** 24 August 2026  
**Active development branch:** `develop`  
**Stable branch:** `main`  
**PR #2:** merged into `main` on 23 August 2026.  
**Current release:** **`v0.4.0` — Unified Bedside Appliance — PUBLISHED 23 August 2026.**

> This roadmap began as the EQ/audio-installer plan. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, AirPlay acquired an arbitration layer, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation, release and future-product roadmap.

Detailed earlier chronology is preserved separately so completed engineering does not bury the useful bit:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — detailed early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — exact pre-consolidation roadmap snapshot through the original replacement-SD physical checkpoint;
- [`../development/evidence/final-clean-room-physical-progress-2026-08-21.md`](../development/evidence/final-clean-room-physical-progress-2026-08-21.md) — replacement-SD physical evidence;
- [`../development/testing/fresh-appliance-acceptance-runbook.md`](../development/testing/fresh-appliance-acceptance-runbook.md) — formal clean-room acceptance procedure;
- [`../development/evidence/release-hygiene-audit-2026-08-19.md`](../development/evidence/release-hygiene-audit-2026-08-19.md) — repository/release-hygiene record.

Normal appliance owners do not need any of those files to install the clock. That job belongs to [`../INSTALL.md`](../INSTALL.md).

## Branch and release model

- `main` is the current supported stable appliance and the normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work may use short-lived `feature/<name>` branches created from `develop` and merged back to `develop` once validated.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- the next release version is intentionally **not assigned yet**; choose it when the actual next-release scope is clear rather than guessing from the first backlog item.
- the old `feature/alarm-engine` branch was retired after the v0.4.0 merge and deleted on 23 August 2026; its product history remains preserved by `main`, PR #2 and the immutable `v0.4.0` tag.

## Current `develop` cycle

### Development-cycle bootstrap — COMPLETE at checkpoint #84

- [x] Created `develop` from post-release `main` head `a2ccc85cbd1d264e7ebedcf50b82084a4289c09a`.
- [x] Switched GitHub Actions push validation from `feature/alarm-engine` to `develop`; `main` remains covered.
- [x] Established `v0.4.0` as the released baseline for all new work.
- [x] Added Events calendar, BBC News and Astronomy to the live product backlog.
- [x] Retired/deleted the old `feature/alarm-engine` branch ref after owner confirmation.

### High-resolution audio feasibility audit — COMPLETE at checkpoint #85; implementation OPEN

The post-v0.4.0 audio review confirmed that hi-res Plexamp playback is a genuine appliance audio-path feature rather than merely a Plexamp preference change.

- [x] The current managed EQ split-bus profile hard-codes the shared music bus and CamillaDSP capture/playback to **`S16_LE` / `44100` Hz**.
- [x] The current Direct/fallback profile also hard-codes its shared `dmix` path to **`S16_LE` / `44100` Hz**, so disabling/bypassing the managed EQ does not currently provide a native hi-res Plexamp path.
- [x] The Raspberry Pi DAC Pro hardware is capable of substantially higher resolution/sample rates than the present appliance bus. Exact accepted appliance formats/rates remain a later physical audit.
- [x] AirPlay remains a lower-rate source; a future higher-resolution internal bus must preserve AirPlay compatibility without making false hi-res claims.
- [x] Scheduled-alarm takeover, Maximum Alarm Volume authority and recovery remain non-negotiable.

No production audio format was changed by #85. Detailed implementation work remains under **High-resolution Plexamp audio / mixer-EQ path** below.

### Friendly forecast-location entry — COMPLETE at checkpoint #86

- [x] Added read-only `GET /api/weather/forecast/locations?q=...`: Open-Meteo for normal place searches plus Postcodes.io fallback for full UK postcodes when Open-Meteo has no match.
- [x] Added Settings → Weather → Online forecast friendly town/city/postcode selection while retaining exact latitude/longitude as advanced fallback.
- [x] Location lookup stages the existing forecast fields only; **Save Changes** remains the sole configuration persistence authority.
- [x] Physical town search passed with Milland on the development Pi.
- [x] Initial physical exact-postcode test exposed the real Open-Meteo gap for `GU30 7JS`; the Postcodes.io fallback subsequently resolved it successfully and drove the Weather forecast after Save Changes.
- [x] The same physical pass exposed far-future `Unknown conditions` daily cards. Both the seven-day foundation renderer and long-range completion renderer now suppress unusable unknown-condition days without shifting Today/Tomorrow labels or duplicating dates.
- [x] Final physical re-check showed the exact postcode forecast working and no remaining `Unknown conditions` daily card across the configured long range.
- [x] The owner confirmed the final synchronized `develop` Actions run green.

Initial location implementation/CI-wiring head: `fe118fb16ef282d6f55682699c1118e721c60b03`.  
Combined postcode/full-range follow-up code/test head: `a7fd2835c6f1bdb7a45591c6bfc1b17732e4f344`.  
Final #86 roadmap/acceptance head: `f901503e9ea4baaf32cc6b9ddcc474456f6745b2`.

### WU supplemental indoor expiry — COMPLETE at checkpoint #87

- [x] With Weather Underground selected, fresh Ecowitt indoor supplementation was deliberately withheld past the configured freshness window.
- [x] Weather removed the **Indoor** row instead of presenting stale values while WU outdoor/current observations remained available.
- [x] Clock retained its paired card layout but replaced expired indoor readings with **—**.
- [x] Re-enabling Ecowitt caused indoor temperature/humidity to reappear automatically on both Clock and Weather with no service restart.
- [x] Owner-supplied 1280×720 screenshots document the expired states.

**Weather priority #1 for the post-v0.4.0 cycle is complete.**

### Configuration ownership and backup-format audit — COMPLETE at checkpoint #88

The Settings/appliance-ownership cycle began by classifying persistent data before implementing backup or restore mutation. Governing rule:

> **Back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

- [x] Added [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) with the ownership matrix, versioned envelope, restore transaction model and reset relationship.
- [x] Classified ordinary ACP settings as a **normalised portable model**, never raw `config.json` bytes.
- [x] Classified alarms, display/night choices, Weather non-secret choices, AirPlay preferences, logical EQ and four mixer percentages as portable user-owned state.
- [x] Established hard exclusions: WU/Plex credentials and claim/session material, browser cookies/session storage, player/machine identity, private keys, raw ALSA state, audio topology, installer state, caches and volatile runtime files.
- [x] Added `scripts/audit-plexamp-preferences.py`, content-blind by default and progressively narrowed through explicit safe audit modes; unknown/auth/device/browser values were never dumped.
- [x] Physical Plexamp 4.13.2 Headless inventory found **35 Settings files: 11 safe-looking candidate names and 24 unclassified/excluded files**.
- [x] Established the exact typed Headless portable allow-list from the commissioned Pi: `audioConversionBitrate`, `autoPlayEnabled`, `cacheSize`, `cachingWiFi`, `loudnessLeveling`, `precacheNetworkSpeed`, `sampleRateConversionQuality`, `sampleRateMatching`.
- [x] `audioDeviceUuid` is device-specific and must be recommissioned; `premium` is account/capability-derived and excluded; `playerName` remains a separate future device-label decision rather than an ordinary preference.
- [x] Browser discovery identified Plexamp at `http://localhost:32500` and MMKV web keys under `mmkv.default\<key>` without decoding their values.
- [x] `@Plexamp:resources`, all `*:cachedItems`, session/auth material and unrelated browser state are explicitly excluded.
- [x] A physical Home reorder experiment proved the contextual `discovery:customizations:...:order` family owns Home item ordering.
- [x] A real physical hide experiment created the complete per-hub `...:<hub-id>:hidden` key plus transient `...:<hub-id>:editing` state. `hidden` is the useful preference; `editing` is excluded.
- [x] Chromium LevelDB compaction changed which historical records were visible between samples. Therefore raw LevelDB/profile files are **discovery evidence only, never the production backup authority**.
- [x] Future browser Home export must operate through a live allow-listed Plexamp-browser authority and save logical order/hidden choices. Restore must discover the freshly claimed target account/library context instead of copying source context identifiers literally.

#88 is closed. No raw Plexamp profile or Chromium profile is a supported backup unit.

### Configuration backup/export — IN PROGRESS at checkpoint #89

The schema-v1 secret-safe export and its first physical commissioned-Pi acceptance are complete. Work now concentrates on the controlled live Plexamp Home bridge.

- [x] Added `app/configuration_backup.py` with **schema version 1** and metadata sourced from `app/static/app-version.json`.
- [x] Export builds from the existing normalised Unified Settings authority and selects an explicit portable subset instead of serialising the public snapshot wholesale.
- [x] ACP export currently includes startup/idle choices, display/day/night presentation, Weather labels/units/cards/forecast/provider/rainfall settings, alarm configuration and AirPlay user preferences.
- [x] WU API credentials are never read by this exporter. The target-owned `api_key_env` implementation detail is also omitted; the ordinary station ID and timing choices remain portable.
- [x] Installer/hardware fields such as alarm ALSA/hardware device names and Plexamp localhost/pause/service plumbing are deliberately omitted.
- [x] EQ exports as the logical enabled/band model. Available shared mixer state exports as the four user-facing percentages (`master`, `plexamp`, `airplay`, `alarm`) rather than ALSA state files.
- [x] The exact eight #88 Plexamp Headless preferences export through strict name/type parsing. Unknown, malformed, device-identity and account/auth files are not copied.
- [x] Plexamp runtime version is included from non-sensitive local package metadata when available.
- [x] `GET /api/settings/backup` returns a pretty JSON attachment named `A-Clockwork-Plex-backup-YYYY-MM-DD_HHMMSS.json` with `Cache-Control: no-store`; it performs no configuration mutation.
- [x] Settings exposes **Advanced → Backup & restore → Download backup** and clearly states that credentials/authentication are excluded. Backup is an immediate read-only action and does not participate in staged **Save Changes**.
- [x] `export_report` records warnings and deliberate omissions. The server-only export continues to report browser Home preferences omitted unless the kiosk browser adds a validated live snapshot.
- [x] Regression coverage proves representative fake WU secrets, Plex auth/device/account state, hardware device fields and target-specific Plexamp plumbing do not enter the generated backup; endpoint attachment/no-store behaviour is also covered.
- [x] CI syntax/compile/page-wiring gates include the backup backend and download control.
- [x] The initial commissioned-Pi physical export passed on 24 August 2026: schema `1`; ACP domains `airplay, alarms, dashboard, display, weather`; audio sections `eq, mixer`; all eight approved Headless preferences; **0 warnings**; two deliberate omissions; and the structural forbidden-key checker reported **NONE**.
- [x] Corrected two CI-only regressions exposed during #89: the new architecture document is now catalogued and backup filenames preserve the source/appliance timezone rather than converting to the GitHub runner timezone.
- [x] Added `browser/plexamp-bridge/` as a Manifest V3 unpacked content extension with **no permissions, no background worker and no general browser-debug interface**. It is scoped only to Plexamp loopback origins on port `32500`.
- [x] The kiosk launcher loads that local extension from the repository when present. It does **not** expose a Chrome remote-debugging port; if bridge files are absent, normal kiosk launch remains available and backup fails safely back to the recorded omission.
- [x] The bridge reads host-page Local Storage only inside Plexamp and recognises only live `discovery:customizations:*:order` and per-hub `*:hidden` records. `editing`, caches, resources, session/auth state and unrelated preferences are not part of its output.
- [x] Added strict dashboard-side response validation. The Settings download flow fetches the existing server backup, requests the live Home snapshot using `postMessage`, merges only validated logical `order`/`hidden` data **inside the kiosk browser**, then creates the downloaded file locally. Browser preference values are not POSTed to the dashboard service or persisted as a server-side staging file.
- [x] Added automated bridge safety coverage: loopback-only manifest, no extension permissions/network/cookie authority, no remote-debugging launcher flag, and a Node-backed logical Home snapshot test that excludes editor/cache/auth fixtures.
- [x] First live-bridge physical probe on 24 August 2026 proved the extension/request path is active and fails closed: a fresh backup contained no `plexamp.browser_preferences`, retained the deliberate browser omission, and recorded exactly one warning: `browser bridge unsupported-hidden-format`. No unsupported value was exposed.
- [x] Hardened the bridge after that physical probe so it now calls `getItem()` **only after** a Local Storage key matches the exact `:order` / `:hidden` allow-list. Editor/cache/resource/auth-adjacent values are no longer merely excluded from output; they are not opened by the bridge at all. Added regression coverage for that read boundary.
- [x] Added a compact safe shape diagnostic for unrecognised `:hidden` / `:order` encodings. It reports only a format class and length/count token (for example typed-boolean vs JSON-array shape), never the stored value or hub identifier. Bridge revision is now `1.0.1`.
- [ ] Physical live-bridge format follow-up: restart kiosk Chromium with bridge `1.0.1`, download a fresh backup and capture only the resulting safe `browser bridge ...` warning token. Use that token to teach the parser the exact Plexamp encoding without dumping the Local Storage value.
- [ ] Physical live-bridge acceptance: after the format parser is narrowed, confirm `plexamp.browser_preferences.home` is present with sensible order/hidden counts while the forbidden-key checker remains clean.
- [ ] Final #89 synchronized Actions run must be green after the live-bridge implementation and physical follow-up.

Initial #89 implementation sequence:
- backup service: `6497fb12c65c873daa866c67cd5ee8142287325f`;
- runner registration: `04437daa316da6a969bd982267b3f3d73daf4646`;
- secret-exclusion/API regression coverage: `6757619d3557c7c72d667bc626731010d519af70`;
- Settings download control: `4f8bc32878dd0dac58526aaa7bc5b719db79c42e`;
- ownership architecture synchronization: `2cb91d5ea57235ad5373f8f7489efc4f27dc0d04`;
- CI-gate wiring: `ec190533b8fe81ebf9cda3d062db7d41bcd85210`;
- CI catalogue/timezone corrections: `9a71c8da0998eb96900e9326e9c09b0c356c790f`, `7612c281531216beff10dfab3c411dadf067d994`;
- live bridge manifest/content/client/launcher/download integration: `e7c3b6ebe70038c86b23ecdffff937e9cd318abc` through `1f81d4381db6ad6d232452cc98f4a9a68df8c506`;
- bridge regression/CI gating: `93e8e5cb514af85beb5933758d7f575e9d2ab286`, `f0ca0fac67002d5ae580d793ed809433a8df6bc0`;
- physical fail-closed hardening/shape diagnostic: `d19235465f91bc7569151626ec758bf556ea232f`, `662e23e9b0e691b58623f798a3f22ec304a02dde`, `9ec2c87a4ab4df746ffa7d04975075e3303a2ee6`.

Restore/import remains a separate later operation; #89 does not enable restore mutation.

## Current supported release

**A Clockwork Plex `v0.4.0` — Unified Bedside Appliance** is the current published release.

- Accepted and merged `main` commit: `d5481b4d52627cbf57a2aa32f974d619fb38ee75`.
- GitHub Actions **Tests #4200** passed on that exact merged `main` commit.
- Published `v0.4.0` was verified identical to the merge commit (`ahead=0`, `behind=0`, no changed files).
- `main` is the normal supported installation/update channel.
- `v0.4.0` is immutable; later `main`/`develop` work is not part of that tag.

## Settled release invariants

### Audio

- Scheduled alarms **bypass Music Master** and music EQ.
- EQ music path: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm path: per-alarm start/target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- CamillaDSP is pinned to accepted `4.1.3`; canonical unit is `a-clockwork-plex-camilladsp.service`.
- The supported audio lifecycle is under `scripts/audio/`.
- `scripts/audio/preflight-eq.sh` is the historical read-only bedroom-Pi validation gate/diagnostic, not the normal installer path.

### Weather

- Open-Meteo supplies forecast data.
- Ecowitt Push or Weather Underground PWS may supply current observations; the selected current provider is authoritative for outdoor values.
- Fresh Ecowitt data may supplement WU indoor temperature/humidity only; stale supplementary values expire.
- WU selected-period rainfall history supplies Today / Last 7 days / Current month / Current year.
- A separate WU lifetime service discovers/backfills the full station archive independently of the selected rainfall period.
- WU secrets remain outside browser configuration, argv and logs under the restricted root-owned secret path.
- Repeat plain `setup.sh` preserves the commissioned Weather provider unless explicitly changed.

### Appliance/bootstrap

- `setup.sh` is the normal public installer; `appliance-installer.sh` is the guarded lower-level engine.
- Plexamp Headless `4.13.2`, appliance Node `20.20.2` arm64 and CamillaDSP `4.1.3` are the accepted v0.4.0 runtime identities.
- The accepted production SD remains protected; **a separate spare SD is the disposable acceptance target** for clean-room release validation.
- Validated hardware: Raspberry Pi Touch Display 2, PN532 I2C bus 1/address `0x24`, Raspberry Pi DAC Pro (`CARD=Pro`).
- Required boot mutation stops at an explicit reboot checkpoint.

### Presentation/runtime

- Seven daytime themes and accepted Classic/Astronomy night presentation are closed unless a real regression appears.
- Touch-to-wake, scheduled night dimming and burn-in shifting are implemented and are not future backlog items.
- Settings touch controls, alarm weekday/status presentation, clock-colon timing, AirPlay marquee/classification, navigation and EQ bypass presentation are accepted.

## v0.4.0 acceptance and release history

The detailed chronology remains in the history/evidence documents linked at the top of this file. Current release milestones:

- Physical clean-room appliance acceptance completed through #64 on the replacement spare SD; exact original tested runtime/source head `215bcedb43369844b5968ae24a7169e49636ef99`.
- Repository/release hygiene completed through #72; Tests #4103 and closing #4105 passed.
- Documentation/portability/branch polish completed through #77; #75 Tests #4127 passed **922/922**.
- #78 catalogued all **155** live `tests/test_*.py` modules and added two-way catalogue enforcement; Tests #4167 passed **925/925**.
- #79 added durable Settings → About release metadata; Tests #4173 passed **925/925**.
- #80 completed release-ready README/INSTALL and visual first-use guidance.
- #81 final post-polish validation Tests #4177 passed **925/925**.
- #82 final blank-Pi follow-up physically proved Weather full-history presentation, NFC and a real scheduled alarm ring → Snooze → re-ring → Dismiss. Follow-up Tests #4193 passed **927/927**, synchronization Tests #4197 also passed.
- #83 PR #2 merged to `main` as `d5481b4d52627cbf57a2aa32f974d619fb38ee75`; exact post-merge **Tests #4200** passed; `v0.4.0` was published and verified identical.

**All v0.4.0 release gates are complete.**

## Future product backlog — next development cycle

These are post-v0.4.0 ideas, not commitments to one release. Design/test independently before promotion to `main`.

### Agreed implementation order

Unless deliberately reprioritised, implementation proceeds in this order:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — IN PROGRESS at #89; #88 ownership/Plexamp discovery COMPLETE
3. **Touchscreen Plexamp text entry**
4. **BBC News**
5. **Events calendar**
6. **High-resolution Plexamp audio / mixer-EQ path**
7. **Astronomy**

This priority list is authoritative. Detailed sections below are technical reference and do not imply a different order.

### Settings and appliance ownership

- [ ] **Configuration backup/export — IN PROGRESS at #89.** Schema-v1 secret-free ACP/Plexamp-Headless export is physically accepted on the commissioned Pi. The live loopback-only browser bridge is also physically reaching Plexamp and failing closed as designed, but Plexamp's `:hidden` value encoding still needs one safe shape-classification pass before Home order/hidden values can be included.
- [x] **Plexamp preference backup feasibility/discovery — COMPLETE at #88.** Exact Headless allow-list and browser Home `order` / per-hub `hidden` key families are physically mapped. Auth/resource/caches/editor/device identity are excluded. Raw Plexamp/Chromium profiles and LevelDB are not backup units.
- [ ] **Configuration import/restore.** Parse/validate an exported file first, preview changes, then apply through the same owners transactionally. Never blindly overwrite installer-owned, secret or Plexamp-owned material. Plexamp restore is allow-listed, version-aware and performed only after fresh claim/library commissioning.
- [ ] **Reset-to-defaults workflow.** Add an intentional confirmation-gated reset that distinguishes user configuration from appliance/runtime ownership instead of recommending manual JSON deletion.

### Touchscreen Plexamp text entry

- [ ] **Plexamp search keyboard/bridge.** The ACP Settings screen has its own touchscreen keyboard, but embedded Plexamp is a separate origin/surface. Investigate a safe touchscreen text-entry bridge that does not depend on the desktop OS on-screen keyboard. The permission-free localhost-only content bridge introduced by #89 is the preferred foundation if physical acceptance confirms it behaves reliably.

### News

- [ ] **BBC News headlines page.** Use BBC RSS/Atom feeds, assuming they remain publicly available at implementation time; do not scrape BBC HTML. Start with top headlines and optionally UK/World/Science/Technology where the feed catalogue supports it cleanly.
- [ ] **Cached/background feed handling.** Fetch outside render, cache the last successful feed, show update/source time and fail gracefully to stale-but-labelled content. News failure must never affect the appliance.
- [ ] **Safe headline presentation.** Sanitise feed markup, preserve BBC attribution and define kiosk-safe article opening.
- [ ] **Touch layout.** Favour a readable headline list/cards with clear age/source information and natural Touch Display 2 scrolling.

### Events calendar

- [ ] **Events calendar design spike.** Define the first data model: local-first storage and/or read-only iCalendar/ICS/CalDAV are preferable starting points; optional cloud-provider integrations remain separate.
- [ ] **Useful bedside views.** Today, upcoming events and a compact month/date browser; clearly distinguish all-day/timed events.
- [ ] **Calendar Settings/ownership.** Keep credentials/remote secrets out of browser-visible configuration and make offline/stale state explicit.
- [ ] **Reminders are separate.** Calendar events never silently become alarm-clock alarms; any future reminder needs explicit user policy and audio/priority semantics.

### High-resolution Plexamp audio / mixer-EQ path

The current v0.4.0 audio profiles intentionally use a fixed **16-bit / 44.1 kHz** shared bus. Goal: materially higher-resolution Plex playback with managed EQ active, plus a measured source-rate-native/bit-perfect path when processing is bypassed and safety permits it.

- [ ] **Physical capability audit.** Use known 16/44.1, 24/48, 24/96 and 24/192 Plex files. Record Plexamp output mode/rate, DAC `aplay --dump-hw-params` and live ALSA `/proc/asound/.../hw_params` before selecting a production bus.
- [ ] **Choose the managed high-resolution bus.** Compare at least 24/96 and 24/192-class operation (appropriate ALSA container such as `S32_LE` where required) for CPU, stability, latency and CamillaDSP. Do not choose 192 kHz merely because the DAC advertises it.
- [ ] **Remove the 16/44.1 bottleneck from managed EQ.** Preserve source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → limiter and the post-EQ scheduled-alarm join.
- [ ] **EQ-active high-resolution plus native bypass.** Preferred UX: EQ active → accepted high-res DSP path; EQ bypass → source-rate-native Direct path and bit-perfect only where measured. If volume/reserve/limiting/resampling remain active, report managed bypass rather than falsely claiming bit-perfect.
- [ ] **Investigate source-rate-native Direct Plexamp.** Test 44.1/48/88.2/96/176.4/192 kHz direct-to-DAC and sample-rate matching. Existing Bypass EQ may become route selector only if alarm takeover, Maximum Alarm Volume, handoff and recovery stay deterministic; **appliance reliability outranks a bit-perfect badge**.
- [ ] **Define resampling policy.** If DSP uses one fixed high rate, choose deliberate high-quality conversion for other Plexamp rates and AirPlay rather than accidental ALSA `plug` conversion.
- [ ] **Preserve AirPlay compatibility.** Treat AirPlay according to its actual received format; do not advertise 96/192 kHz AirPlay merely because the internal bus can run there. Prove both handoff directions after high-rate playback.
- [ ] **Expose truthful diagnostics.** Report source format/rate, internal processing format/rate and final DAC format/rate separately.
- [ ] **Automated regression.** Protect route rendering/fallback, EQ active/bypass and scheduled-alarm authority.
- [ ] **Physical acceptance matrix.** Exercise all four source-rate classes through EQ/native modes, a real scheduled alarm during high-rate playback, then AirPlay takeover/return. Use “native/bit-perfect” only when measured ALSA/DAC parameters prove it.

### Astronomy — major new application area

Treat Astronomy as a **multi-screen touch section** with its own sub-navigation, in the spirit of Peter Duffett-Smith: useful numerical astronomy rather than decorative horoscope content. 🔭

- [ ] **Technical spike/calculation authority.** Prefer deterministic local/offline ephemeris. Compare a maintained astronomy library/ephemeris source with compact well-tested Duffett-Smith/Meeus-style calculations. Define reference fixtures/tolerances first.
- [ ] **Observer/location model.** Reuse existing latitude/longitude/timezone where sensible, with explicit Astronomy confirmation/override if needed.
- [ ] **Overview / Tonight.** Julian Date, local/Greenwich sidereal time, Sun/Moon headline state and notable current-night rise/set events.
- [ ] **Sun.** Sunrise/transit/sunset; civil/nautical/astronomical twilight; day length; RA/Dec; altitude/azimuth; useful seasonal events where reliable.
- [ ] **Moon.** Moonrise/transit/moonset; phase/age/illumination; next principal phases; distance/angular diameter; RA/Dec; altitude/azimuth.
- [ ] **Planets.** Mercury–Neptune rise/transit/set and useful position data; investigate magnitude, elongation, distance and constellation where reliable.
- [ ] **Navigation/presentation.** Touch-first 1280×720 sub-navigation, global drawer always reachable, night presentation designed from the outset.
- [ ] **Validation.** Reference dates/locations plus circumpolar/no-rise/no-set/polar/DST/local-date edge cases.

### Weather

- [x] Friendly forecast-location entry — COMPLETE #86.
- [x] WU-only supplemental-indoor expiry physical confirmation — COMPLETE #87.

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
