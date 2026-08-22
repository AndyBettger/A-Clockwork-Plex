# A Clockwork Plex Roadmap

**Last updated:** 22 August 2026  
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

### Final polish after documentation review — IN PROGRESS

- **#73 documentation usability:** reduce `docs/` root to normal-user material plus clearly separated `development/`, `roadmap/` and `archive/` areas; rename the live project roadmap away from its obsolete EQ-installer-era title; preserve roadmap/history evidence rather than deleting it.
- **#74 installer identity portability:** remove live `/home/andy`/default-to-`andy` assumptions from supported installer/runtime tooling while preserving genuine historical evidence paths in the archive; add regression coverage so another appliance user does not unexpectedly become Andy by shell expansion. 😄
- Re-run the complete validation suite after #73/#74 and refresh PR #2 metadata while keeping it Draft/open/unmerged.

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

### Documentation polish

- [ ] **Release screenshots / visual first-use guide.** Add a compact set of current screenshots to the public documentation once the final branch is merged, without turning the README back into a development diary.

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
3. [ ] Finish #73 documentation layout/roadmap rename and validate references/catalogue tests.
4. [ ] Finish #74 live `andy` portability sweep and regression coverage.
5. [ ] Re-run the complete final validation suite on the resulting branch head and pin the exact result here and in PR #2.
6. [ ] Resolve/retire the two remaining historical development branches after their unique work is proved already integrated or obsolete.
7. [ ] **Explicit owner approval.** Only then may PR #2 leave Draft or merge.

**PR #2 must remain Draft/open/unmerged until that explicit approval is given.**
