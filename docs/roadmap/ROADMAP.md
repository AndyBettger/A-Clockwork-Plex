# A Clockwork Plex Roadmap

**Last updated:** 23 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — **must remain Draft, open and unmerged until explicit owner approval.**

> This roadmap began as the EQ/audio-installer plan. Then the installer acquired the rest of the appliance, the alarm clock acquired an audio engine, Weather acquired history, AirPlay acquired an arbitration layer, and the phrase “small follow-up” lost all legal meaning. 😁 This is now the project-wide roadmap.

## Roadmap authority and history

This file is the single live implementation, release and future-product roadmap.

Detailed earlier chronology is preserved separately so completed engineering does not bury the useful bit:

- [`history-through-phase7-checkpoint6.md`](history-through-phase7-checkpoint6.md) — detailed early Phase 7 chronology;
- [`history-through-checkpoint64.md`](history-through-checkpoint64.md) — exact pre-consolidation roadmap snapshot through the final replacement-SD physical checkpoint;
- [`../development/evidence/final-clean-room-physical-progress-2026-08-21.md`](../development/evidence/final-clean-room-physical-progress-2026-08-21.md) — final replacement-SD physical evidence;
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
- WU rainfall history supplies Today / Last 7 days / Current month / Current year plus retained Rainy Day Fund/lifetime data.
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

The replacement spare SD passed fresh bootstrap, Plexamp commissioning/playback, managed EQ, Weather/WU history, AirPlay, NFC, real scheduled alarms including Snooze/re-ring/Dismiss and Music-Master independence, reboot recovery, repeat public setup, formal verifiers and a final clean tracked checkout.

The exact physically tested runtime/source head remains `215bcedb43369844b5968ae24a7169e49636ef99`. Later repository-hygiene/documentation work does not reopen that physical gate unless it changes appliance runtime behaviour.

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

- **#73 documentation usability — COMPLETE:** `docs/` now contains only the normal-user files `README.md`, `INSTALL.md` and `appliance-installer.md` plus the deliberately separated `assets/`, `development/`, `roadmap/` and `archive/` trees. `docs/README.md` points normal owners straight to installation, documentation images are isolated under `docs/assets/`, the live roadmap is `docs/roadmap/ROADMAP.md`, and `tests/test_docs_catalog.py` prevents development-paper or loose-image creep back into the root.
- **#74 installer identity portability — COMPLETE:** supported installer/runtime sources no longer contain live `/home/andy`, `${USER:-andy}`, `User=andy` or `Group=andy` assumptions. The remaining CamillaDSP service exception caught by the first portability run was converted to the generic `User=ACP_PROJECT_USER` source template and is rendered by the EQ installer to the selected project user while retaining `Group=audio`. Historical evidence is intentionally untouched.
- **#75 final post-polish validation — COMPLETE:** implementation head `0698ebb6ac786812740312f96cf8b09cb221e41d`; Tests #4127 / run `32554699819`: compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **922/922 unit tests PASS** (`Ran 922 tests in 44.797s`, `OK`). The only workflow notice was GitHub Actions' hosted-runner Node-runtime deprecation warning for current action versions; it is not an appliance/runtime/test failure.
- **#76 historical branch provenance — COMPLETE:** `feature/typography-weather-bridge` is the exact 63-commit head of merged PR #1 and its work was squash-merged into `main` as `c69b2ee9f0ceed119d07e6d696e8b4a723abb614`; `stage-c-terminal-install-20260806` has 23 unique commits whose complete 16-file delta is confined to the Stage-C script/implementation/test families deliberately retired at #65 and forbidden by `tests/test_retired_stage_c_guard.py`. Neither branch contains product work that should be merged. Both refs were therefore safe to delete.
- **#77 historical branch deletion — COMPLETE:** the owner deleted both obsolete refs, and a subsequent GitHub branch search on 22 August 2026 returned no match for either `feature/typography-weather-bridge` or `stage-c-terminal-install-20260806`. Repository branch hygiene is therefore closed.

The roadmap/PR status synchronization after #75 is documentation/metadata only and does not alter the physically accepted appliance runtime.

### Final release-preparation polish — IN PROGRESS through checkpoint #78

These items were deliberately identified before owner approval so they are finished on the feature branch rather than discovered after merge:

- [x] **#78 maintainer test-suite catalogue — COMPLETE:** [`../development/testing/test-catalogue.md`](../development/testing/test-catalogue.md) now catalogues all **155** live `tests/test_*.py` modules by subsystem and purpose, documents full-suite/module/individual-test invocation and a shared expected-result contract, and deliberately leaves individual `test_*` case enumeration to verbose `unittest` discovery rather than maintaining a second 900+ row list. `tests/test_test_catalog.py` enforces exact two-way agreement between the Markdown catalogue and the live module set and protects the run/result documentation contract. The testing overview and development-doc map both link the catalogue. Exact catalogue head `3850bfbb331bae8db88776cc31f26ce76116edf2`; Tests #4167 / run `32612845331`: Python compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **925/925 unit tests PASS** (`Ran 925 tests in 44.832s`, `OK`). This is the catalogue checkpoint validation, **not** the final release validation, because About/version and final release-document wording still remain to change.
- [ ] **Settings → About/version metadata refresh.** The About page already consumes `app/static/app-version.json`, but that metadata is stale (`0.4.0-dev`, `feature/alarm-engine`, and the obsolete phase `Production EQ guarded rollout next`). Refresh the release identity and make version/build maintenance explicit and regression-covered so About remains trustworthy as development and releases continue.
- [ ] **Release-ready README and INSTALL wording.** Remove production-candidate/feature-branch wording at the correct point in the merge/release sequence and document `main` as the normal supported install/update channel while tags/releases remain immutable version snapshots.
- [ ] **Release screenshots / visual first-use guide.** Twelve privacy-safe 1280×720 release screenshots are committed under `docs/assets/screenshots/`, covering daytime Clock, night Clock, active alarm, Alarm Settings, Master EQ Settings, Weather Settings, forecast/current/wind-rain Weather views, AirPlay Ready/Now Playing and Plexamp Now Playing. The separate Weather station-status frame containing a live station identifier was intentionally not committed. The Now Playing screenshots may include contextual third-party media artwork; rights remain with their respective rights holders. The public root README now uses a curated subset inside **What you get**: paired day/night Clock views, paired forecast/current Weather views, Plexamp Now Playing, paired AirPlay Ready/Now Playing views, and the active scheduled-alarm screen. The deeper Settings frames remain available for the visual first-use material. A refreshed About screenshot should be captured after the About/version work. A physical hardware hero photograph and finished NFC sleeve photograph remain welcome later but are **not release blockers**.
- [ ] **Final post-polish validation.** Re-run the maintained full compile/syntax/unit-test gate after the About/version and release-documentation changes; pin the exact green result before owner approval.

## Future product backlog — non-blocking

These are ideas that were discussed during development, remain useful, and are **not required for the accepted release candidate**.

### Weather

- [ ] **Friendly forecast-location entry.** Add place/postcode/location lookup that writes the existing forecast latitude/longitude settings. Keep exact coordinate entry as an advanced/fallback path.
- [ ] **WU-only indoor-expiry physical confirmation.** On an appliance receiving no fresh Ecowitt push, physically confirm that Clock indoor cards and the Weather Indoor row disappear after freshness expiry. Source expiry tests are already green; this is a validation follow-up, not a missing core feature.

### Settings and appliance ownership

- [ ] **Configuration backup/export.** Provide a supported way to export ordinary appliance Settings without leaking managed secrets or volatile runtime/cache state.
- [ ] **Configuration import/restore.** Validate an exported configuration before applying it transactionally; do not blindly overwrite installer-owned or secret material.
- [ ] **Reset-to-defaults workflow.** Add an intentional, confirmation-gated Settings reset that distinguishes user configuration from appliance/runtime ownership instead of recommending manual deletion of JSON files.

These Settings-management ideas were discussed early in the project but are not present in the current Settings surface or public documentation.

### Touchscreen Plexamp text entry

- [ ] **Plexamp search keyboard/bridge.** The A Clockwork Plex Settings screen has its own touchscreen keyboard, but the embedded Plexamp UI is a separate surface. Earlier kiosk requirements explicitly called for Plexamp search to remain usable without attaching a physical keyboard or mouse. Investigate a safe touchscreen text-entry bridge that does not depend on the desktop OS on-screen keyboard.

## Deliberately not on the future list

Several things appeared on much older wish-lists but were subsequently implemented and accepted:

- scheduled alarms and real playback;
- night dimming and touch-to-wake;
- burn-in shifting;
- Weather history and provider selection;
- idle-return/dashboard behaviour;
- alarm Settings and status;
- AirPlay receiver naming;
- managed EQ and source/master/alarm gain controls;
- fresh-install/setup automation.

Keeping completed work off the future list matters. Otherwise the roadmap eventually starts requesting features the appliance already has, which is an impressively inefficient form of time travel. 🕰️

## Release exit sequence

1. [x] Physical replacement-SD clean-room acceptance through #64.
2. [x] Stage-C/audio-lab/helper/AirPlay retirement and repository hygiene through #72.
3. [x] Finish #73 documentation layout/roadmap rename and validate references/catalogue tests.
4. [x] Finish #74 live `andy` portability sweep and regression coverage.
5. [x] Re-run the complete final validation suite and pin the exact result here and in PR #2.
6. [x] Prove the two remaining historical development branches contain no unmerged product work (#76).
7. [x] Delete and verify the obsolete refs `feature/typography-weather-bridge` and `stage-c-terminal-install-20260806` (#77).
8. [x] Complete the maintainer test-suite catalogue and its drift protection (#78).
9. [ ] Refresh Settings → About/version metadata and make its maintenance/release contract explicit.
10. [ ] Finish release-ready README/INSTALL wording and the curated screenshot/visual first-use material.
11. [ ] Run and pin the final full validation suite after all release-preparation polish.
12. [ ] **Explicit owner approval.** Only then may PR #2 leave Draft or merge.
13. [ ] After merge, verify the exact `main` result/CI and create the GitHub release/tag from that accepted `main` commit.

**PR #2 must remain Draft/open/unmerged until that explicit approval is given.**
