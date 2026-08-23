# A Clockwork Plex Roadmap

**Last updated:** 23 August 2026  
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

### Development-cycle bootstrap — COMPLETE at checkpoint #84

- [x] Created `develop` from post-release `main` head `a2ccc85cbd1d264e7ebedcf50b82084a4289c09a`.
- [x] Switched GitHub Actions push validation from `feature/alarm-engine` to `develop`; `main` remains covered.
- [x] Established `v0.4.0` as the released baseline for all new work.
- [x] Added the first post-release product ideas — Events calendar, BBC News and Astronomy — to the live roadmap.
- [x] Retired/deleted the old `feature/alarm-engine` branch ref after owner confirmation; GitHub branch discovery subsequently verified it absent.

### High-resolution audio feasibility audit — COMPLETE at checkpoint #85; implementation OPEN

The post-v0.4.0 audio review confirmed that hi-res Plexamp playback is a genuine appliance audio-path feature rather than merely a Plexamp preference change.

- [x] The current managed EQ split-bus profile hard-codes the shared music bus and CamillaDSP capture/playback to **`S16_LE` / `44100` Hz**.
- [x] The current Direct/fallback profile also hard-codes its shared `dmix` path to **`S16_LE` / `44100` Hz**, so disabling/bypassing the managed EQ does not currently provide a native hi-res Plexamp path.
- [x] The Raspberry Pi DAC Pro hardware is capable of substantially higher resolution/sample rates than the present appliance bus, and Plexamp Headless on Linux can output higher-rate material. The exact accepted appliance formats/rates must still be proved against this Pi, DAC and Plexamp build before changing the production profile.
- [x] AirPlay is not the primary hi-res source requirement. Its own protocol/receiver format limits are lower than 96/192 kHz-class Plex material; the requirement is to keep AirPlay handoff and playback compatible with whatever higher-resolution internal music bus is selected without making false hi-res claims for the source.
- [x] The existing alarm authority remains non-negotiable: scheduled alarms must continue to bypass Music Master/music EQ, retain Maximum Alarm Volume authority and take over reliably regardless of the Plexamp source format.

The implementation work is tracked below under **High-resolution Plexamp audio / mixer-EQ path**. No production audio format has been changed by this audit.

### Friendly forecast-location entry — COMPLETE at checkpoint #86

The first implementation item of the post-v0.4.0 `develop` cycle is the Weather forecast-location helper.

- [x] Added a read-only backend `GET /api/weather/forecast/locations?q=...` lookup. General town/city/place searches use Open-Meteo geocoding; a full UK postcode that receives no Open-Meteo match now falls back to the no-auth Postcodes.io lookup service and returns a sanitised coordinate/timezone result. Queries are whitespace-normalised and bounded, provider responses are parsed defensively, and only an allow-listed result shape is returned to the browser.
- [x] Added a dedicated Settings presenter, `settings-weather-location.js`, on the existing **Weather → Online forecast** page. It accepts a town, city or postcode using the existing touchscreen keyboard, presents selectable matches, and stages the selected latitude, longitude and timezone into the existing unified Settings controls.
- [x] Preserved one configuration authority: location lookup never writes configuration, wakes Weather services or refreshes the forecast by itself. The normal **Save Changes** transaction remains the only persistence path.
- [x] Kept manual coordinates available and relabelled them **Latitude (advanced)** / **Longitude (advanced)** so exact coordinate entry remains a supported fallback.
- [x] Added regression coverage to the existing Weather forecast test modules without increasing the maintained test-module catalogue: query validation/normalisation, provider result sanitisation, Open-Meteo failure handling, full-UK-postcode fallback, non-postcode no-fallback behaviour, read-only API behaviour, Settings field staging/load order and JavaScript syntax. The location presenter is also included in the workflow's explicit JavaScript syntax gate.
- [x] The owner confirmed the requested GitHub Actions **Tests** run on the first #86 `develop` implementation/roadmap head `2d1dd0e603da2d77c28fb78596d14ae3b61791db` was green.
- [x] Physical 1280×720 town-search path passed on the development Pi after switching to `develop`, pulling and running `setup.sh`: searching **Milland** returned a valid match; selecting it staged the latitude/longitude; Save Changes completed normally; and the Weather page displayed the forecast for the selected location. The supplied VNC screenshot also confirms the new location-search card and advanced coordinate controls fit cleanly within the existing Settings layout.
- [x] The first physical postcode attempt identified a real provider gap rather than a UI fault: exact `GU30 7JS` returned no Open-Meteo result. The implementation now detects full UK postcode syntax and, only when Open-Meteo returns no match, resolves it through Postcodes.io. The UK result is reduced to the same safe location shape and uses `Europe/London`; no new credential or Settings persistence path is introduced.
- [x] The same physical Weather-page check exposed a far-future presentation issue: the **16-day completion renderer** could append an otherwise empty-looking `Unknown conditions` daily card. Both forecast stages now skip daily entries whose normalised condition tone is `unknown`. Foundation cards carry `data-forecast-date`, and the completion renderer extends the strip by missing forecast date rather than raw card count, preserving original Today/Tomorrow indices and preventing duplicates if an unknown day appears anywhere in the range. Both static assets are cache-busted.
- [x] Regression coverage now protects the seven-day foundation filter, original-index hand-off, full configured-range extension, date-based deduplication, unknown-day suppression in the completion stage and JavaScript syntax.
- [x] Final physical #86 re-check passed on 23 August 2026: exact `GU30 7JS` returned a usable postcode result, selecting/saving it populated the forecast coordinates and the Weather page rendered the selected forecast normally; scrolling the configured long-range Daily outlook showed no remaining **Unknown conditions** cards.
- [x] Final #86 CI closure: the owner confirmed the latest `develop` Actions **Tests** run after the postcode/long-range follow-up and roadmap synchronization head `f901503e9ea4baaf32cc6b9ddcc474456f6745b2` was green.

Initial location implementation/CI-wiring head: `fe118fb16ef282d6f55682699c1118e721c60b03`.  
Combined postcode-fallback + full-range unknown-day follow-up code/test head: `a7fd2835c6f1bdb7a45591c6bfc1b17732e4f344`.

### WU supplemental indoor expiry — COMPLETE at checkpoint #87

The remaining Weather follow-up was a physical proof of the already-tested freshness contract for Ecowitt indoor supplementation while Weather Underground remains the selected outdoor/current authority.

- [x] The development Pi was left on Weather Underground while fresh Ecowitt indoor temperature/humidity was deliberately withheld long enough to exceed the configured Ecowitt freshness window.
- [x] The Weather page removed the **Indoor** row entirely after expiry rather than retaining stale indoor values; WU outdoor temperature, humidity and the rest of the selected-provider data remained live.
- [x] The Clock page retained the existing paired temperature/humidity card layout but replaced the stale indoor halves with **—**, making absence explicit instead of presenting old readings as current.
- [x] After Ecowitt data was re-enabled, indoor temperature/humidity reappeared automatically on both Clock and Weather without a service restart or manual refresh.
- [x] Owner-supplied 1280×720 VNC screenshots on 23 August 2026 document both expired states. No runtime change was required; this closes the physical validation follow-up for the existing freshness implementation.

**Weather priority #1 for the post-v0.4.0 cycle is complete. The next active priority is Settings and appliance ownership.**

### Configuration ownership and backup-format audit — IN PROGRESS at checkpoint #88

The Settings/appliance-ownership cycle begins by classifying persistent data before any backup or restore mutation is implemented. The governing rule is: **back up logical user choices through their owning authority; do not copy implementation directories wholesale.**

- [x] Added [`../development/architecture/configuration-backup-ownership.md`](../development/architecture/configuration-backup-ownership.md) and linked it from the development index. It defines the ownership matrix, portable/non-portable boundary, proposed versioned JSON envelope, restore transaction model and relationship to reset-to-defaults.
- [x] Classified ordinary A Clockwork Plex user configuration as a **normalised portable Settings model**, not raw `config.json` bytes. Alarm schedules, display/night choices, Weather non-secret configuration and logical AirPlay preferences are candidates; installer/hardware plumbing remains target-owned.
- [x] Established hard exclusions for managed secrets and identity: the WU API key, Plex account/authentication/claim material, browser cookies/session data, machine/player identity, private keys, caches and volatile runtime state must never enter an ordinary backup.
- [x] Classified specialist audio preferences by owner: Bass/Mid/Treble/bypass are exported as logical EQ values and later restored through `MasterEqualizer`; persistent mixer state is exported as the four user-facing percentages and later restored through the restricted mixer helper rather than copying ALSA state.
- [x] Classified `state.json`, alarm/audio/playback runtime files, forecast/rainfall caches, install markers/rollback payloads and generated caches/logs as **regenerable runtime state** and excluded them from ordinary backup.
- [x] Defined the Plexamp boundary: `~/.local/share/Plexamp/Settings` is persistent across runtime repair but must not be copied wholesale because preferences coexist with state/resources/identity/authentication material. The kiosk Chromium profile at `~/.config/a-clockwork-plex/chromium-profile` likewise must never be archived wholesale because Plexamp UI preferences may coexist with browser login/session data.
- [x] Added `scripts/audit-plexamp-preferences.py`, a deliberately read-only/content-blind inventory helper. It lists only safe-looking `@Plexamp:settings:*` key suffixes and file sizes, filters sensitive/unclassified names without printing them, and reports only the presence of fixed Chromium storage-area directories. It never opens Plexamp or Chromium storage values.
- [x] Added regression coverage to the existing Plexamp safety test module and catalogued the new script. The test fixture includes secret-looking Plexamp values and proves they are not emitted by the helper. Local compile/fixture execution of the helper passed before requesting a physical inventory.
- [ ] Run the read-only helper on the commissioned development Pi and capture only its safe output so the actual Plexamp 4.13.2 preference-key set can be classified.
- [ ] From that inventory, establish an exact Headless preference allow-list and decide whether browser-side Home/layout preferences can be extracted narrowly enough to support safely. If not, leave those browser-side settings as an explicit manual-reconfiguration item rather than weakening the authentication boundary.

No backup/export, import/restore or reset mutation has been enabled by #88 yet. The audit deliberately defines ownership first.

Repository-side #88 audit/documentation began at `cea4e1abec1a57e058f82ab47f8001ef32cff43c`; safe live-inventory helper/test/catalogue head before roadmap synchronization: `2d61858a4ca4fa52ce5dce3f57188b129b170c46`.

## Current supported release

**A Clockwork Plex `v0.4.0` — Unified Bedside Appliance** is the current published release.

- Accepted and merged `main` commit: `d5481b4d52627cbf57a2aa32f974d619fb38ee75`.
- GitHub Actions **Tests #4200** passed on that exact merged `main` commit.
- The published `v0.4.0` tag was verified against the merge commit with GitHub's commit comparison: **identical**, `ahead_by=0`, `behind_by=0`, no changed files.
- `main` is the normal supported installation/update channel.
- `v0.4.0` is an immutable accepted-release snapshot. Later `main`/`develop` bookkeeping and development commits are not part of the tagged release.

## Settled release invariants

### Audio

- Scheduled alarms **bypass Music Master** and music EQ.
- EQ music path: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm path: per-alarm start/target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- CamillaDSP is pinned to accepted `4.1.3`; canonical unit is `a-clockwork-plex-camilladsp.service`.
- The supported audio lifecycle is under `scripts/audio/`.
- `scripts/audio/preflight-eq.sh` remains the historical **read-only bedroom-Pi validation gate** and diagnostic; it is not the normal installer path.

### Weather

- Open-Meteo supplies forecast data.
- Ecowitt Push or Weather Underground PWS may supply current observations; the selected current provider is authoritative for outdoor values.
- Fresh Ecowitt data may supplement WU indoor temperature/humidity only.
- Stale supplementary indoor readings expire instead of remaining forever.
- WU selected-period rainfall history supplies Today / Last 7 days / Current month / Current year.
- A separate WU lifetime service automatically discovers and backfills the full station archive for Rainy Day Fund/lifetime totals; it runs independently of the selected rainfall period.
- WU secrets remain outside browser configuration, argv and logs and are managed through the restricted root-owned secret path.
- Repeat plain `setup.sh` preserves the commissioned Weather provider unless an explicit provider change is requested.

### Appliance/bootstrap

- `setup.sh` is the normal public installer.
- `appliance-installer.sh` is the guarded lower-level transactional engine.
- Plexamp Headless `4.13.2`, appliance Node `20.20.2` arm64 and CamillaDSP `4.1.3` remain the accepted pinned runtime identities for this release.
- The accepted production SD remains protected; **a separate spare SD is the disposable acceptance target** used for clean-room validation.
- Validated hardware remains Raspberry Pi Touch Display 2, PN532 on I2C bus 1/address `0x24`, and Raspberry Pi DAC Pro as ALSA `CARD=Pro`.
- Required boot mutation stops at an explicit reboot checkpoint; the installer never decides that rebooting the bedroom is a fun surprise.

### Presentation/runtime

- Seven daytime themes and accepted Classic/Astronomy night presentation are closed unless a real regression is found.
- Touch-to-wake, scheduled night dimming and burn-in shifting are implemented; do **not** resurrect those as stale future-roadmap items.
- Settings touch controls, alarm weekday presentation/status pills, clock-colon timing, AirPlay marquee/classification, navigation and EQ bypass presentation are accepted.

## v0.4.0 acceptance and release history

### Physical clean-room acceptance — COMPLETE through checkpoint #64

The original replacement spare SD passed fresh bootstrap, Plexamp commissioning/playback, managed EQ, Weather/WU history, AirPlay, NFC, real scheduled alarms including Snooze/re-ring/Dismiss and Music-Master independence, reboot recovery, repeat public setup, formal verifiers and a final clean tracked checkout.

The exact original physically tested runtime/source head remains `215bcedb43369844b5968ae24a7169e49636ef99`. Later repository-hygiene/documentation work did not reopen that physical gate unless it changed appliance runtime behaviour.

### Release hygiene — COMPLETE through checkpoint #72

- #65 retired obsolete Stage-C executable/test scaffolding.
- #66 retired the pre-production audio laboratory/rehearsal layer.
- #67 retired superseded helper installers.
- #68 retired legacy AirPlay callbacks/installers.
- #69 catalogued every retained script and repaired the local test runner.
- #70 classified current vs historical documentation.
- #71 completed temporary-ref and tracked-file/install-dependency cleanup.
- #72 completed the post-cleanup validation suite: Tests #4103, **915/915 PASS**; closing synchronization Tests #4105 also **915/915 PASS**.

### Final polish after documentation review — COMPLETE through checkpoint #77

- **#73 documentation usability — COMPLETE:** normal-user docs are separated from `assets/`, `development/`, `roadmap/` and `archive/`; `tests/test_docs_catalog.py` prevents engineering clutter returning to the user-facing docs root.
- **#74 installer identity portability — COMPLETE:** supported installer/runtime sources no longer contain live `/home/andy`, `${USER:-andy}`, `User=andy` or `Group=andy` assumptions. CamillaDSP uses the generic `User=ACP_PROJECT_USER` source template rendered to the selected project user while retaining `Group=audio`.
- **#75 post-polish validation — COMPLETE:** implementation head `0698ebb6ac786812740312f96cf8b09cb221e41d`; Tests #4127 / run `32554699819`: compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **922/922 unit tests PASS** (`Ran 922 tests in 44.797s`, `OK`).
- **#76 historical branch provenance — COMPLETE:** the remaining historical refs were proved to contain no unmerged product work requiring integration.
- **#77 historical branch deletion — COMPLETE:** the owner deleted both obsolete refs and they were subsequently verified absent.

### Final release-preparation polish — COMPLETE through checkpoint #81

- [x] **#78 maintainer test-suite catalogue — COMPLETE:** [`../development/testing/test-catalogue.md`](../development/testing/test-catalogue.md) catalogues all **155** live `tests/test_*.py` modules by subsystem and purpose. `tests/test_test_catalog.py` enforces exact two-way agreement between the Markdown catalogue and live module set. Exact catalogue head `3850bfbb331bae8db88776cc31f26ce76116edf2`; Tests #4167 / run `32612845331`: **925/925 PASS** (`Ran 925 tests in 44.832s`, `OK`).
- [x] **#79 Settings → About/version metadata — COMPLETE:** `app/static/app-version.json` carries durable release identity **`0.4.0` / `v0.4.0` / `Unified Bedside Appliance`** and About describes current appliance capabilities rather than transient development phases. Exact implementation head `6fccf0ef106a7e124a44b1bbac33a5feab4b9bfe`; Tests #4173 / run `32613370524`: **925/925 PASS** (`Ran 925 tests in 44.586s`, `OK`).
- [x] **#80 release-ready public documentation and visual first-use — COMPLETE:** README/INSTALL describe **`main` as the normal supported install/update channel** and published tags/releases as immutable snapshots. The old public “production candidate” / `feature/alarm-engine` install path is regression-forbidden. `docs/INSTALL.md` contains the compact visual first-use tour. Exact implementation head `bef278f64845255f86e5c1be654f84b0b2744e98`.
- [x] **#81 final post-polish validation — COMPLETE:** Tests #4177 / run `32614635007` against `bef278f64845255f86e5c1be654f84b0b2744e98`: Python compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **925/925 unit tests PASS** (`Ran 925 tests in 45.380s`, `OK`).

### Final blank-Pi release follow-up — COMPLETE at checkpoint #82

A final wipe-and-install release-candidate run was deliberately performed before owner approval. The blank appliance successfully reached normal operation and the owner confirmed Weather commissioning, managed EQ, Plexamp and AirPlay were working normally. Settings → About physically displayed the prepared **0.4.0 / Unified Bedside Appliance / v0.4.0** identity and the resulting `settings-about.png` was added to the curated documentation set.

The run found two small pre-release issues rather than an installer/runtime failure:

1. **Raspberry Pi OS documentation path:** the desktop size/appearance control is **Preferences → Control Centre → General**, not Control Centre → Appearance. `docs/INSTALL.md` is corrected and `tests/test_user_setup_installer.py` now forbids the stale path.
2. **WU rainfall status scope ambiguity:** the existing `232 of 235 days recorded`-style message describes only the selected Today / Last 7 days / Current month / Current year period. The separate full-station lifetime backfill was already running independently, which is why the Weather page could simultaneously say that the station archive was still backfilling. Settings did not expose that second status clearly. A new read-only `settings-weather-lifetime-status.js` presenter now labels the dropdown **Selected period** and adds **Full station history**, reading the existing `/api/weather/rainfall/lifetime` endpoint and showing `Backfilling full history` / `Full history ready` without altering the lifetime service or its cache/backfill behaviour.

`settings-about.png` is now part of the guarded screenshot catalogue and the visual first-use guide.

Exact follow-up implementation/docs head: `5ad1eec5bf36c5c40ea793c21c75ccd0597ac668`. Tests #4193 / run `32622918557`: Python compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **927/927 unit tests PASS** (`Ran 927 tests in 30.881s`, `OK`). The increase from 925 to 927 is the two new full-station-history Settings regression tests. Roadmap contract synchronization head `c9e0846cdf0c7becc7a61fb10a0172c5618949d6`; Tests #4197 also passed the complete maintained gate.

Final #82 physical evidence on 23 August 2026:

- [x] On the freshly commissioned Pi, **Settings → Weather → Observation source** showed the selected-period rainfall result and the separate **Full station history** status cleanly at 1280×720. Changing Current year → Last 7 days → Current month → Current year updated the selected-period result correctly and did not reset or hide the lifetime status. The full archive reported **Full history ready**.
- [x] NFC playback was physically tested successfully on the fresh installation.
- [x] A real scheduled alarm was physically tested successfully through ring → Snooze → re-ring → Dismiss.

The owner explicitly approved PR #2 for merge after those checks on **23 August 2026**.

### Release publication — COMPLETE at checkpoint #83

- [x] PR #2 was merged to `main` as `d5481b4d52627cbf57a2aa32f974d619fb38ee75`.
- [x] The exact post-merge `main` workflow, **Tests #4200**, completed green.
- [x] GitHub release/tag **`v0.4.0` — Unified Bedside Appliance** was published on 23 August 2026.
- [x] GitHub comparison confirmed `v0.4.0` and `d5481b4d52627cbf57a2aa32f974d619fb38ee75` are identical.

**v0.4.0 is released.** New development now integrates on `develop`; the released tag remains immutable.

## Future product backlog — next development cycle

These are post-v0.4.0 ideas. They are not commitments to one release and should be designed/tested independently before promotion to `main`.

### Agreed implementation order

Unless the owner deliberately reprioritises the cycle, implementation should proceed in this order:

1. **Weather** — COMPLETE through #87
2. **Settings and appliance ownership** — IN PROGRESS at #88, including safe non-authentication Plexamp preference backup/restore investigation
3. **Touchscreen Plexamp text entry**
4. **BBC News**
5. **Events calendar**
6. **High-resolution Plexamp audio / mixer-EQ path**
7. **Astronomy**

This priority list is authoritative for work order. The detailed sections below remain the technical reference catalogue and do not imply a different implementation priority.

### High-resolution Plexamp audio / mixer-EQ path

The current v0.4.0 audio profiles intentionally use a fixed **16-bit / 44.1 kHz** shared bus. The next-cycle goal is to let high-resolution Plex material retain materially higher resolution through the appliance **with managed EQ active**, while providing a measured source-rate-native/bit-perfect path when processing is bypassed and the appliance safety contracts permit it.

- [ ] **Physical capability audit on the development Pi.** Use known 16/44.1, 24/48, 24/96 and 24/192 Plex files. Record Plexamp's selected output mode/rate, `aplay --dump-hw-params` for the DAC Pro and the live ALSA `/proc/asound/.../hw_params` state. Confirm the exact formats/rates accepted by this hardware/software combination before selecting a production bus.
- [ ] **Choose the managed high-resolution bus.** Compare at least 24/96 and 24/192-class operation (using the appropriate ALSA container format such as `S32_LE` where required) for CPU load, stability, latency and CamillaDSP behaviour. Do not select 192 kHz merely because the DAC advertises it if 96 kHz is the better appliance engineering trade-off.
- [ ] **Remove the 16/44.1 bottleneck from the managed EQ split bus.** Preserve the existing source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → limiter contract and the post-EQ scheduled-alarm join.
- [ ] **EQ-active high-resolution plus native bypass.** The preferred user experience is: EQ active → accepted high-resolution managed DSP path; EQ bypass → source-rate-native Direct path and bit-perfect playback where measured conditions prove it. Because Music Master, source trims, reserve, limiting or resampling would themselves alter samples, the implementation must either bypass those operations too for true native playback or clearly report a managed-bypass state instead of falsely claiming bit-perfect output.
- [ ] **Investigate a source-rate-native Direct Plexamp path.** Determine whether Plexamp can hand 44.1/48/88.2/96/176.4/192 kHz material directly to the DAC with reliable sample-rate matching. The existing Bypass EQ control may become the route selector if that remains intuitive, but only adopt a native Direct mode if alarm takeover, Maximum Alarm Volume authority, source handoff and recovery remain deterministic; appliance reliability outranks a bit-perfect badge.
- [ ] **Define resampling policy.** If the managed mixer/EQ uses one fixed high-resolution rate, use a deliberate high-quality conversion policy for lower/different-rate Plexamp material and for AirPlay rather than relying on accidental/default conversions hidden in an ALSA `plug` chain.
- [ ] **Preserve AirPlay compatibility.** Treat AirPlay according to the format actually delivered by Shairport Sync; do not advertise 96/192 kHz AirPlay simply because the internal bus can run at that rate. Prove AirPlay → Plexamp and Plexamp → AirPlay handoff after high-rate playback.
- [ ] **Expose truthful audio diagnostics.** Make it possible to inspect/report source format/rate, internal processing format/rate and final DAC format/rate so future troubleshooting can distinguish “24/96 source” from “24/96 actually reaching the DAC”.
- [ ] **Automated regression coverage.** Protect accepted format/rate configuration, route rendering, safe fallback, EQ active/bypass behaviour and alarm authority. Never allow a hi-res change to weaken the tested scheduled-alarm bypass contract.
- [ ] **Physical acceptance matrix.** Exercise 16/44.1, 24/48, 24/96 and 24/192 Plex material through EQ active and native/bypass operation; test a real scheduled alarm during high-rate Plexamp playback; then test AirPlay takeover and return. Only describe a path as native/bit-perfect when measured ALSA/DAC parameters prove it.

### Astronomy — major new application area

The Astronomy feature should be treated as a **multi-screen section with its own touch navigation**, closer in interaction model to Settings than to a single Clock/Weather dashboard page. The aim is a bedside astronomy reference in the spirit of Peter Duffett-Smith's *Astronomy with your Pocket Calculator / Spreadsheet / Personal Computer*: useful numerical astronomy rather than a decorative horoscope page. 🔭

- [ ] **Astronomy technical spike and calculation authority.** Prefer deterministic local/offline calculations for the core ephemeris rather than making the appliance dependent on a live astronomy API. Evaluate an appropriate maintained astronomy library/ephemeris source versus compact well-tested Duffett-Smith/Meeus-style calculations. Define accuracy tolerances and reference fixtures before implementation.
- [ ] **Observer/location model.** Reuse the appliance's existing latitude/longitude/timezone where sensible, while allowing Astronomy-specific confirmation/override if needed. All rise/set/transit calculations must clearly use the configured observer and local date/time.
- [ ] **Astronomy overview / Tonight screen.** Provide a concise observing summary and navigation into the detailed screens. Candidate data includes Julian Date, local/Greenwich sidereal time, Sun/Moon headline state and notable rise/set events for the current night.
- [ ] **Sun screen.** Candidate values: sunrise, solar transit/noon, sunset, civil/nautical/astronomical twilight, day length, right ascension/declination and current altitude/azimuth. Equinox/solstice/seasonal information may be added where it remains genuinely useful on a bedside display.
- [ ] **Moon screen.** Candidate values: moonrise/transit/moonset, phase name, age, illuminated fraction, next principal phases, distance, angular diameter, right ascension/declination and current altitude/azimuth.
- [ ] **Planets screen(s).** Mercury through Neptune with rise/transit/set times and useful current positional data such as RA/Dec and altitude/azimuth. Investigate adding magnitude, elongation, distance and constellation where the chosen calculation source supports them reliably.
- [ ] **Astronomy navigation/presentation.** Design a touch-first sub-navigation that works at 1280×720 without cramming all data onto one screen. The normal global drawer must remain reachable. Night-theme presentation should be considered from the start rather than bolted on later.
- [ ] **Astronomy validation suite.** Regression-test mathematical outputs against known reference dates/locations with explicit tolerances, including difficult edge cases such as circumpolar objects, no-rise/no-set days and DST/local-date boundaries.

### News

- [ ] **BBC News headlines page.** Build a lightweight News surface from BBC RSS/Atom feeds (assuming the feeds remain publicly available at implementation time) rather than scraping BBC HTML. Begin with top headlines and allow additional sections such as UK, World, Science/Technology if the feed catalogue supports them cleanly.
- [ ] **Cached/background feed handling.** Fetch outside the page-render path, cache the last successful feed, show source/update time and fail gracefully to stale-but-labelled headlines when the network is unavailable. News failure must never affect the rest of the appliance.
- [ ] **Safe headline presentation.** Sanitise feed-provided markup, preserve BBC attribution and decide how article opening should work in kiosk mode without trapping the user outside A Clockwork Plex.
- [ ] **Touch layout.** Favour a readable headline list/cards with clear age/source information rather than a dense newspaper layout; scrolling must work naturally on the Touch Display 2.

### Events calendar

- [ ] **Events calendar design spike.** Add a touch-friendly calendar/upcoming-events surface. Define the first supported data model before coding: local-first event storage and/or read-only standards-based calendar input such as iCalendar/ICS/CalDAV are preferable starting points; optional cloud-provider integration can remain separate.
- [ ] **Useful bedside views.** Candidate views are Today, upcoming events and a compact month/date browser, with clear all-day versus timed events.
- [ ] **Calendar Settings/ownership.** Keep credentials or remote calendar secrets out of browser-visible configuration, follow the same managed-secret principles used by Weather, and make offline/stale state explicit.
- [ ] **Reminders are a separate decision.** Do not silently convert calendar events into alarm-clock alarms. If event reminders are later added, they need an explicit user-controlled policy and clear priority/audio behaviour.

### Weather

- [x] **Friendly forecast-location entry — COMPLETE at #86.** Town/city and full UK postcode lookup are implemented and physically proven end-to-end on the development Pi. Exact `GU30 7JS` resolves through the postcode fallback when required, Save Changes applies the staged coordinates/timezone, the Weather page follows the selected location, and the long-range renderer no longer shows unusable **Unknown conditions** daily cards. Exact coordinate entry remains the advanced/fallback path. Final `develop` Actions confirmation was green.
- [x] **WU-only indoor-expiry physical confirmation — COMPLETE at #87.** With WU selected and Ecowitt indoor supplementation withheld past freshness expiry, the Weather Indoor row disappeared, the Clock indoor halves showed **—**, WU outdoor/current data remained available, and indoor values returned automatically after Ecowitt pushes resumed.

**Weather is complete for the agreed next-cycle scope.**

### Settings and appliance ownership

- [ ] **Configuration backup/export — design/ownership audit in progress at #88.** Export ordinary appliance preferences as a versioned normalised model rather than raw config/runtime files, excluding managed secrets and machine-specific implementation state.
- [ ] **Plexamp preference backup feasibility — live inventory pending at #88.** Investigate an allow-listed backup of useful non-authentication Plexamp preferences rather than copying the whole Plexamp profile. Headless/server-side preferences under the Plexamp Settings store and browser-side experience preferences must be treated separately. Candidate restore data may include device/audio preferences and user experience/home-layout choices where their storage and semantics are understood. Explicitly exclude Plex authentication/account tokens, claim material, browser session cookies, machine identity, caches and logs. The backup format must be versioned and restore must preserve correct ownership/permissions and tolerate Plexamp-version changes safely.
- [ ] **Configuration import/restore.** Validate an exported configuration before applying it transactionally; do not blindly overwrite installer-owned, secret or Plexamp-owned material. Any supported Plexamp preference restore should be allow-listed and best-effort/version-aware rather than a raw profile replacement.
- [ ] **Reset-to-defaults workflow.** Add an intentional, confirmation-gated Settings reset that distinguishes user configuration from appliance/runtime ownership instead of recommending manual deletion of JSON files.

### Touchscreen Plexamp text entry

- [ ] **Plexamp search keyboard/bridge.** The A Clockwork Plex Settings screen has its own touchscreen keyboard, but the embedded Plexamp UI is a separate surface. Investigate a safe touchscreen text-entry bridge that does not depend on the desktop OS on-screen keyboard.

## Deliberately not on the future list

These older wish-list items were subsequently implemented and accepted: scheduled alarms and real playback; night dimming and touch-to-wake; burn-in shifting; Weather history/provider selection; idle-return/dashboard behaviour; alarm Settings/status; AirPlay receiver naming; managed EQ and source/master/alarm gain controls; fresh-install/setup automation.

Keeping completed work off the future list matters. Otherwise the roadmap eventually starts requesting features the appliance already has, which is an impressively inefficient form of time travel. 🕰️

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
10. [x] PR #2 merged to `main`; exact merge commit `d5481b4d52627cbf57a2aa32f974d619fb38ee75` passed Tests #4200; GitHub release/tag `v0.4.0` published and verified identical to that commit (#83).

**All v0.4.0 release gates are complete.**