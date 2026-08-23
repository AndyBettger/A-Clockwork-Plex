# A Clockwork Plex Roadmap

**Last updated:** 23 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — explicit owner approval for merge received on 23 August 2026.

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

## Release-candidate status

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

## Future product backlog — non-blocking

These are useful ideas that are **not required for the accepted release candidate**.

### Weather

- [ ] **Friendly forecast-location entry.** Add place/postcode/location lookup that writes the existing forecast latitude/longitude settings. Keep exact coordinate entry as an advanced/fallback path.
- [ ] **WU-only indoor-expiry physical confirmation.** On an appliance receiving no fresh Ecowitt push, physically confirm that Clock indoor cards and the Weather Indoor row disappear after freshness expiry. Source expiry tests are already green; this is a validation follow-up, not a missing core feature.

### Settings and appliance ownership

- [ ] **Configuration backup/export.** Provide a supported way to export ordinary appliance Settings without leaking managed secrets or volatile runtime/cache state.
- [ ] **Configuration import/restore.** Validate an exported configuration before applying it transactionally; do not blindly overwrite installer-owned or secret material.
- [ ] **Reset-to-defaults workflow.** Add an intentional, confirmation-gated Settings reset that distinguishes user configuration from appliance/runtime ownership instead of recommending manual deletion of JSON files.

### Touchscreen Plexamp text entry

- [ ] **Plexamp search keyboard/bridge.** The A Clockwork Plex Settings screen has its own touchscreen keyboard, but the embedded Plexamp UI is a separate surface. Investigate a safe touchscreen text-entry bridge that does not depend on the desktop OS on-screen keyboard.

## Deliberately not on the future list

These older wish-list items were subsequently implemented and accepted: scheduled alarms and real playback; night dimming and touch-to-wake; burn-in shifting; Weather history/provider selection; idle-return/dashboard behaviour; alarm Settings/status; AirPlay receiver naming; managed EQ and source/master/alarm gain controls; fresh-install/setup automation.

Keeping completed work off the future list matters. Otherwise the roadmap eventually starts requesting features the appliance already has, which is an impressively inefficient form of time travel. 🕰️

## Release exit sequence

1. [x] Physical replacement-SD clean-room acceptance through #64.
2. [x] Repository/release hygiene through #72.
3. [x] Documentation/portability/branch hygiene through #77.
4. [x] Maintainer test-suite catalogue (#78).
5. [x] Settings → About/version contract (#79).
6. [x] Release-ready README/INSTALL and visual first-use material (#80).
7. [x] Pre-approval validation (#81).
8. [x] Final blank-Pi follow-up/spot-check (#82).
9. [x] **Explicit owner approval for PR #2 merge — received 23 August 2026.**
10. [ ] Merge PR #2 to `main`, verify the exact resulting `main` commit/CI, then create GitHub release/tag `v0.4.0` from that accepted `main` commit.
