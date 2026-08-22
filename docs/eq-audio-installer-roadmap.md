# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 22 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

This file is the **active implementation and acceptance authority**. Completed engineering history is preserved rather than allowed to swamp the remaining release work:

- detailed history through Phase 7 checkpoint #6: `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`;
- exact active-roadmap snapshot through checkpoint #64: `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md`;
- earlier spare-SD bootstrap evidence: `docs/fresh-bootstrap-physical-progress-2026-08-15.md`;
- focused EQ/Direct physical evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`;
- focused Weather physical evidence: `docs/weather-physical-followup-2026-08-17.md`;
- final replacement-SD clean-room evidence: `docs/final-clean-room-physical-progress-2026-08-21.md`.

The checkpoint-#64 archive is the exact pre-consolidation roadmap blob, not a rewritten summary. Use it when detailed chronology before the current release-hygiene pass is needed. The consolidated active roadmap retained its current safety contracts and passed Tests #4083 / run `32544561709` with **972/972 unit tests PASS** after CI caught and forced restoration of the exact preflight/production-SD wording.

## Settled release invariants

### Audio

- Scheduled alarms **bypass Music Master**.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm start/target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Fresh Direct keeps Plexamp/AirPlay under Music Master while the alarm joins the DAC-facing mix independently.
- `scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate; it is retained as a diagnostic/acceptance tool, not a production installation path.
- EQ → Direct convergence remains inside the outer application transaction with rollback restoring the pre-EQ backup and prior `snd_aloop` state before captured EQ services are reactivated.
- Canonical CamillaDSP unit: `a-clockwork-plex-camilladsp.service`; do not use the unrelated generic `camilladsp.service` identity for acceptance.
- Accepted CamillaDSP: `4.1.3`; executable SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`; official aarch64 archive SHA `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a`.
- The laboratory-era bare `scripts/install-master-eq.sh` path and pre-production ALSA/CamillaDSP rehearsal scripts are retired. The supported audio lifecycle is `scripts/audio/preflight-eq.sh`, `install-direct.sh`, `install-eq.sh`, `repair-audio.sh`, `uninstall-eq.sh` and `verify-audio.sh`.

### Weather

- Open-Meteo remains the forecast provider.
- Live outdoor observations may be Ecowitt custom push or Weather Underground PWS; the selected live provider is authoritative.
- When WU is selected, fresh Ecowitt push may supplement indoor temperature/humidity only and must never overwrite WU outdoor observations.
- Stale supplementary indoor readings disappear rather than being displayed indefinitely.
- Historical-rainfall periods remain exactly **Today**, **Last 7 days**, **Current month** and **Current year**; default is Last 7 days.
- WU rainfall-history refresh ownership is serialized across background/manual/Test Connection/Settings refresh owners.
- WU API keys remain write-only commissioning data in root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`; they must not be returned to the browser, placed in argv or logged.
- Restricted `/usr/local/bin/a-clockwork-plex-weather-secret status` exposes only `WEATHER_SECRET_CONFIGURED=0|1` for verifier use.
- Selecting/reconverging Ecowitt Push preserves an existing managed WU credential because WU may continue supplying rainfall history.
- Plain repeat `setup.sh` without an explicit Weather selection preserves the already-commissioned live provider; an explicit `--weather-observations` choice remains authoritative.

### Player/runtime and installer ownership

- **Plexamp Headless remains the player for this release.** Caldera migration is outside Phase 7.
- Plexamp Headless: `4.13.2`, official archive SHA `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.
- Appliance Node: `20.20.2` linux-arm64, SHA `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`, installed beneath `/opt/a-clockwork-plex` without replacing distribution Node.
- `setup.sh` is the normal human-facing installer and owns CamillaDSP artifact acquisition plus the interactive Plexamp claim handoff.
- `appliance-installer.sh` is the guarded lower-level transactional engine.
- The stale root `install.sh` duplicate is retired and must not return.
- An unclaimed fresh runtime exits `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`; normal claim material is never an installer/evidence field.
- `installer/repository-dependencies.txt` pins the source closure required by both supported installer paths.

### Fresh-Pi hardware/bootstrap

- The accepted production SD remains protected; a separate spare SD is the disposable acceptance target, and the final physical acceptance used the replacement spare card.
- PN532: I2C bus `1`, address `0x24`; project user groups `i2c`, `gpio`, `spi`.
- Accepted DAC: Raspberry Pi DAC Pro, ALSA `CARD=Pro`.
- Already-working `CARD=Pro` is accepted without boot mutation; managed fallback is `rpi-dacpro` only when required.
- No global OS upgrade, `rpi-update`, Pi EEPROM/bootloader update, HAT EEPROM write or external hardware firmware update belongs to appliance bootstrap.
- Any required I2C/DAC boot mutation exits `75`; the installer never reboots automatically.

### Presentation/runtime closure

- Shared segment source is `app/static/js/segment-display.js`; selected Version 3 geometry is physically accepted and regression-pinned with its editable SVG/cache identity.
- Seven daytime themes are accepted; Classic Dark retains its established baseline, non-Classic themes own native dashboard presentation, Plexamp remains visually excluded, and Classic/Astronomy night behavior remains as accepted.
- Settings touch-control/palette closure, AirPlay long-form classifier/marquee, Clock colon rendered-second cadence, night preview, navigation, alarm annunciator and final EQ bypass presentation are physically accepted through checkpoint #55.
- Presentation should remain closed unless later validation exposes a genuine regression.

## Phase status

### Phases 0–6 — **Complete**

Standalone EQ lifecycle, guarded transactions, bedroom-Pi physical audio acceptance and rollback/failure paths are complete. Detailed history remains in the archived roadmap material above.

### Phase 7 — **In progress: physical release gate complete; repository/release hygiene and final validation remain**

The replacement-SD clean-room sequence is complete through checkpoint #64: fresh installer/bootstrap, Plexamp GUI/output commissioning, EQ, WU/rainfall-history retest, AirPlay, NFC, real scheduled-alarm fade/safety, representative reboot, both formal verifier sets, repeat public `setup.sh` with commissioned WU preserved, and final empty `git status --porcelain` proof all passed.

Release hygiene has now completed four deliberate executable-retirement batches plus retained-script documentation closure:

- checkpoint #65 retired the historical Stage-C executable validation subsystem and its dedicated positive test suite;
- checkpoint #66 retired the obsolete pre-production audio laboratory/rehearsal layer and moved CI shell-syntax coverage onto the six supported `scripts/audio/` lifecycle scripts;
- checkpoint #67 retired superseded standalone helper installers while retaining their transactional owner and runtime helpers;
- checkpoint #68 retired legacy AirPlay source-tree callbacks/installers that predated the PlaybackCoordinator/guarded integration ownership;
- checkpoint #69 classified every surviving script by purpose/safety/use, regression-enforced that catalogue, and converged the local test runner onto discovered current source.

No additional replacement-SD physical clean-room gate is currently outstanding.

## Deferred/non-blocking follow-ups

- [ ] **WU-only indoor expiry:** on a future appliance receiving no fresh Ecowitt custom push, confirm Clock indoor cards and the Weather Indoor row disappear after freshness expiry. Source expiry tests are green; do not disrupt the working single Ecowitt destination solely to manufacture this case.
- [ ] **Friendly forecast-location entry:** replace coordinate-first normal commissioning with place/postcode/location lookup that writes the existing latitude/longitude settings; retain exact manual coordinates as an advanced/fallback path. This remains non-blocking unless explicitly promoted.

## Remaining Phase 7 execution sequence — authoritative order

1. [x] **Runtime/generated-state + `.gitignore` audit.** Known runtime/cache/log/build/editor state is ignored and regression-protected; checkpoint #64 physically proved normal commissioned operation leaves tracked source clean.
2. [x] **Fresh-install repository dependency closure.** `installer/repository-dependencies.txt` is enforced by both supported installer entry paths.
3. [x] **PR #2 release-candidate description refresh.** PR remains Draft/open/unmerged.
4. [x] **Replacement-SD physical release gate.** Complete through checkpoint #64; no additional clean-room physical gate is outstanding.
5. [x] **Retire obsolete Stage-C validation subsystem.** Checkpoint #65 / Tests #4075 passed.
6. [x] **Retire obsolete pre-production audio laboratory/rehearsal subsystem.** Fourteen laboratory/rehearsal scripts and thirteen dedicated historical safety-test modules were removed; `tests/test_retired_audio_lab_guard.py` pins their absence and the retained production lifecycle. Checkpoint #66 / Tests #4085 passed.
7. [x] **Complete retained script/helper inventory and documentation.** Superseded standalone helper installers and legacy AirPlay artifacts were retired at checkpoints #67/#68. `scripts/README.md` now documents every surviving file in the retained script directories by purpose, safety and intended use; `tests/test_script_catalog.py` dynamically enforces coverage and the local `scripts/run-tests.sh` discovers current source instead of pinning stale paths. Checkpoint #69 / Tests #4095 passed.
8. [ ] **Complete deliberate `docs/` history review.** The exact through-#64 roadmap snapshot is preserved; continue classifying/archive-consolidating genuinely superseded stage documents without deleting useful provenance, then proofread active operator/architecture docs.
9. [ ] **Remove temporary development branches/refs** created during final testing, leaving only intentional long-lived/release refs before merge.
10. [ ] **Rerun final tracked-file/install-dependency audit after cleanup** so every file required by `setup.sh` / `appliance-installer.sh` is present and no retained file survives solely because an obsolete experiment once used it.
11. [ ] **Run the complete validation suite after all cleanup** and pin the final count/status.
12. [ ] **Obtain explicit owner approval** before PR #2 leaves Draft or merges.

## Final repository/release hygiene checklist

- [x] Initial classification audit: `docs/release-hygiene-audit-2026-08-19.md`.
- [x] README rewritten/proofread for the actual release candidate and completed physical clean-room state.
- [x] Installer naming reduced to `setup.sh` + `appliance-installer.sh`; stale root `install.sh` removed.
- [x] Runtime/generated-state and `.gitignore` coverage audited/regression-protected.
- [x] Fresh-install dependency closure pinned/enforced.
- [x] PR #2 description refreshed while retaining Draft/open/unmerged state.
- [x] Replacement-SD exact runtime checkout proved clean at checkpoint #64.
- [x] Obsolete Stage-C implementation/harness/fixtures/positive tests retired and guarded at checkpoint #65.
- [x] Obsolete pre-production audio laboratory/rehearsal scripts and their dedicated historical tests retired and guarded at checkpoint #66.
- [x] Superseded standalone helper installers retired and guarded at checkpoint #67.
- [x] Legacy AirPlay callbacks/display fallback/unguarded metadata-listener installer retired and guarded at checkpoint #68.
- [x] Every retained script classified/documented in `scripts/README.md`, catalogue completeness regression-protected, and the local validation runner converged at checkpoint #69.
- [x] Oversized active roadmap history through checkpoint #64 preserved byte-for-byte in `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md`; this file carries current authority and remaining work.
- [x] Complete retained script/helper inventory beyond the two large historical subsystems.
- [ ] Finish deliberate historical-doc classification/archive/consolidation and active-doc proofreading.
- [ ] Remove temporary development refs.
- [ ] Rerun final dependency/tracked-file audit after cleanup.
- [ ] Run complete post-cleanup validation.
- [ ] Owner approval; only then may PR #2 leave Draft or merge.

**Phase 7 exit condition:** the accepted physical release candidate remains unchanged; deliberate repository/docs/ref cleanup and final validation must complete, then explicit owner approval is required. PR #2 remains Draft throughout.

## Recent Phase 7 checkpoint record

Detailed checkpoints #7–#55 are preserved in `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md`.

- **#56 — release-hygiene runtime-state audit + fresh-install dependency closure — PASS (source/CI).** `installer/repository-dependencies.txt` pins the supported source closure and both installer paths fail closed early on an incomplete payload. Code head `ae2497450b5b9d106c2eb4d86301bd1bc32c455b`; Tests #4012 / run `32430838605`: compile/JavaScript/page/shell PASS, **1,762/1,762 unit tests PASS**.
- **#57 — PR #2 release-candidate description refresh — PASS (metadata; Draft preserved).** Stale historical/future-work narrative was replaced with the integrated release candidate. PR remained open, Draft and unmerged.
- **#58 — WU rainfall-history refresh serialization — PASS (source/CI + replacement-SD physical).** The complete cache refresh transaction is mutex-serialized. Code/CI through `0723da83a4a08a332e7eb42bf2016b564c2e72d5`; Tests #4035 / run `32520278486`, **1,763/1,763 PASS**. Replacement-SD Current year/Test Connection/Last 7 days/Current year retest reproduced no atomic `.tmp` rename collision.
- **#59 — replacement-SD AirPlay handoff/EQ proof — PASS (physical).** AirPlay takeover, EQ/bypass/return and disconnect behavior passed without Plexamp/Shairport/CamillaDSP restarts.
- **#60 — replacement-SD NFC album-tag/debounce proof — PASS (physical).** Correct album playback, debounce behavior and malformed-read rejection passed with NFC service stable.
- **#61 — replacement-SD real scheduled-alarm fade/safety proof — PASS (physical).** Takeover, fade, Snooze/re-ring, Dismiss and Music-Master-independent alarm lane all passed while retaining the dedicated alarm ceiling.
- **#62 — replacement-SD representative reboot + first formal verifiers — PASS (physical).** Dashboard/Plexamp/NFC/Shairport/CamillaDSP recovered; bootstrap verifier, WU appliance verifier and audio verifier all passed with zero structured warnings/failures.
- **#63 — repeat public setup commissioned-Weather idempotence — PASS (source/CI + replacement-SD physical).** Source head `215bcedb43369844b5968ae24a7169e49636ef99` added preserve-commissioned-profile behavior after the first repeat exposed WU→Ecowitt provider drift. Tests #4063 passed; the physical retest preserved `weather-underground`, required no renewed claim/reboot checkpoint, and all repeat verifiers plus real Plexamp/EQ operation passed.
- **#64 — replacement-SD final clean-checkout proof — PASS (physical).** Exact physically tested runtime/source head `215bcedb43369844b5968ae24a7169e49636ef99` produced no `git status --porcelain` output after repeat setup/verifiers/normal operation. Physical clean-room acceptance is complete.
- **#65 — obsolete Stage-C validation subsystem retirement — PASS (source/CI).** `da58f1586ca03827399f915af0301b9a104bf7e2` removed the Stage-C implementation/harness/fixtures; Tests #4073 then correctly exposed 77 still-coupled positive `tests/test_stage_c*.py` modules. Follow-up `ea043030086fe4afb92e8ed682c62eb254c98ae3` removed those historical tests and added `tests/test_retired_stage_c_guard.py`. **Tests #4075 / run `32541368986` PASS:** compile, JavaScript/page wiring, shell syntax and **972/972 unit tests PASS**.
- **#66 — obsolete pre-production audio laboratory/rehearsal retirement — PASS (source/CI).** Exact cleanup commit `5fbc0a43f86b93132c3e132a9cd1cf0adad4b4f7` removed 14 laboratory/rehearsal scripts — including the disabled bare `scripts/install-master-eq.sh` path, ALSA/CamillaDSP lab scripts and historical physical rehearsals — plus 13 dedicated safety-test modules whose only subject was that retired machinery. `tests/test_retired_audio_lab_guard.py` now pins all 27 retired paths absent, requires the six supported `scripts/audio/` lifecycle files to remain present, and requires CI to syntax-check those supported paths instead of the retired labs. `scripts/prepare-plexamp-upgrade-rehearsal.sh` was deliberately retained because it remains a separate read-only maintenance diagnostic with current safety coverage. **Tests #4085 / run `32544751465` PASS:** compile PASS, JavaScript/page wiring PASS, shell syntax PASS and **900/900 unit tests PASS**.
- **#67 — superseded standalone helper-installer retirement — PASS (source/CI).** Commit `82896ccaa88de52eced2a309e730256878f236b8` removed `scripts/install-shared-audio.sh`, `scripts/install-alarm-audio-helper.sh` and `scripts/install-shairport-name-helper.sh` while retaining the real runtime helpers and guarded transactional `scripts/install-appliance-helpers.sh` owner. `tests/test_retired_legacy_helper_installers_guard.py` pins that boundary and the old wrong shared-audio installer now stays absent rather than surviving as a negative fixture. **Tests #4089 / run `32545282737` PASS:** compile, JavaScript/page wiring, shell syntax and **903/903 unit tests PASS**.
- **#68 — legacy AirPlay source-tree artifact retirement — PASS (source/CI).** Commit `9b4edfa41a0cb037bd9ce041ca097e9502be03a8` removed static `shairport-airplay-start.sh`/`shairport-airplay-end.sh` callbacks that directly stopped/started Plexamp, their old `display-mode.sh` fallback and the unguarded standalone `install-airplay-metadata-listener.sh`. The current renderer publishes lifecycle intent to PlaybackCoordinator and `install-airplay-integration.sh` remains the guarded transactional owner. `tests/test_retired_legacy_airplay_scripts_guard.py` pins those retired paths absent. **Tests #4091 / run `32545747002` PASS:** compile, JavaScript/page wiring, shell syntax and **907/907 unit tests PASS**.
- **#69 — retained-script catalogue + local validation-runner convergence — PASS (source/CI).** `scripts/run-tests.sh` was converged at `49e38695b4b138fe0b903f3b051cbc6a2d8b676d` to discover all current Python under `app/` + `scripts/`, all shell under `scripts/`, and all dashboard JavaScript before running the complete unit suite. Final head `39cee18c51a9958eba2da53e7310b43105d0f2a9` added `scripts/README.md`, documenting every retained regular script file by purpose/safety/intended use, plus `tests/test_script_catalog.py` to dynamically enforce catalogue completeness. **Tests #4095 / run `32546030629` PASS:** compile, JavaScript/page wiring, shell syntax and **911/911 unit tests PASS**.

No checkpoint is recorded as fully physically complete until its required physical gates pass. Source/CI PASS does not substitute for a remaining bedside/clean-room acceptance gate; checkpoints #65–#69 are intentionally source/CI release-hygiene checkpoints and do not reopen the already-complete physical gate.
