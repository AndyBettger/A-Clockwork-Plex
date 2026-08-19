# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 19 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed history through Phase 7 checkpoint #6 is preserved in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. Detailed spare-SD bootstrap attempts after checkpoint #26 are recorded in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`. Focused EQ/Direct evidence is in `docs/eq-to-direct-physical-verification-2026-08-17.md`, and focused Weather acceptance is in `docs/weather-physical-followup-2026-08-17.md`.

This file is the **active implementation and acceptance authority**. Completed engineering history stays available, but the roadmap should describe the repository and release candidate that actually exist now rather than preserving stale intermediate names or future-work statements.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm start/target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Alarm fade is explicit and audible: the configured target is the destination; Maximum Alarm Volume is the ceiling; Fade start is a per-alarm value, default 10% for new alarms; start is constrained not to exceed target; Fade Off starts immediately at target; Snooze/re-ring starts a fresh fade cycle.
- Fresh Direct keeps Plexamp/AirPlay under Music Master while the alarm joins the DAC-facing mix independently.
- `scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate.
- Do not use the old bare `scripts/install-master-eq.sh` production path.
- An already-installed EQ appliance is a supported convergent source state when the whole-appliance installer is asked for Direct. Do not require manual EQ uninstall.
- EQ → Direct convergence remains inside the outer application transaction: specialist teardown retains the pre-EQ backup, rollback restores that backup and pre-transition `snd_aloop` state before captured EQ services are reactivated, and retained backup cleanup occurs only after successful outer commit.
- The canonical managed CamillaDSP unit is `a-clockwork-plex-camilladsp.service`; acceptance and diagnostics must not use the unrelated generic name `camilladsp.service`.

| Identity | Accepted value |
|---|---|
| Historical Phase 6 Direct rollback | `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` |
| Fresh alarm-safe Direct / managed failback | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| +2/0/+2 Camilla config | `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578` |
| CamillaDSP executable | `4.1.3`, SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| CamillaDSP official aarch64 archive | SHA `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a` |

The historical `08d00093...` route is physical Phase 6 rollback evidence only; it is not the fresh Direct profile because that old graph routes alarm through Music Master.

### Weather

- Open-Meteo remains the forecast provider.
- Current outdoor observations may be Ecowitt custom push or Weather Underground PWS.
- The selected live provider remains authoritative for outdoor/current weather. If WU is selected, an Ecowitt push may supply **supplementary indoor temperature/humidity only**; it must never overwrite WU outdoor observations.
- Supplementary Ecowitt indoor readings carry their own freshness timestamp. When no recent indoor push exists, Clock indoor cards and the Weather Main **Indoor** row are omitted rather than displaying stale values or placeholders.
- The physically used Ecowitt setup provides one custom-upload destination. For several A Clockwork Plex appliances, WU is the practical shared live source; the directly-fed appliance may additionally gain fresh indoor readings.
- Historical-rainfall periods remain exactly **Today**, **Last 7 days**, **Current month** and **Current year**; default is Last 7 days.
- Today uses live `dailyrainin`; completed historical days use WU daily `precipTotal`.
- When a provider lacks native Hourly rain/Event rain, A Clockwork Plex may derive them locally from persisted successive daily-rain observations. Native provider values take precedence.
- Derived Hourly rain is the rolling preceding-60-minute accumulation. Derived Event rain persists across refresh/reboot and follows the tested documented dry-reset rule.
- When WU lacks native `maxdailygust`, A Clockwork Plex tracks the highest successive current gust for the selected station/calendar day and persists it across dashboard restarts; native provider max retains precedence.
- Current/today rain and **Rainy Day Fund** participate in one horizontal scroll surface using the forecast-style custom rail/thumb.
- `weather-rainfall-history.json` and `weather-rainfall-lifetime.json` are station-scoped, secret-free runtime caches and remain ignored by Git.
- Confirmed station gaps are distinguished from provider/configuration failures and are not repeatedly re-fetched.
- Rain lifetime is calculated from WU daily history from the first discovered station record through today; settled lifetime refreshes are request-quiet.
- WU API keys are write-only commissioning data. Persistent secret storage is root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`, and key material is never returned to the browser, placed in argv or logged.
- Selecting/reconverging Ecowitt Push preserves an existing managed WU credential exactly because WU may continue supplying rainfall history.

### Player/runtime and installer names

- **Plexamp Headless remains the player for this release.** Caldera migration is outside Phase 7.
- Plexamp Headless: `4.13.2`, official archive SHA `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.
- Node: `20.20.2` linux-arm64, SHA `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`, installed beneath `/opt/a-clockwork-plex` without replacing distribution Node.
- Fresh account/player setup is an explicit local interactive checkpoint; claim material is never a normal installer/evidence field.
- `setup.sh` is the normal human-facing first-install entry point and owns CamillaDSP artifact acquisition plus the interactive Plexamp claim handoff.
- `appliance-installer.sh` is the guarded lower-level transactional appliance installer/recovery engine. `setup.sh` delegates to it.
- The stale root `install.sh` duplicate has been removed from the release candidate after maintained callers/tests were migrated. Historical evidence that says `install.sh` remains truthful for the command used at that earlier checkpoint, but it is **not** a current supported entry point.
- An unclaimed fresh runtime exits `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`; interactive `setup.sh` launches installed Plexamp Headless for claim and resumes after claim state exists.

### Fresh-Pi hardware/bootstrap

- The real bedroom Pi/HAT/display is the physical target, but the accepted production SD remains protected. A separate spare SD is the disposable acceptance target.
- No global OS upgrade, `rpi-update`, Pi EEPROM/bootloader update, HAT EEPROM write or external hardware firmware update belongs to appliance bootstrap.
- PN532: I2C bus `1`, address `0x24`; project user groups `i2c`, `gpio`, `spi`.
- Accepted DAC: Raspberry Pi DAC Pro, ALSA `CARD=Pro`.
- Already-working `CARD=Pro` is accepted without boot mutation; managed fallback is `rpi-dacpro` only when required. A different identified HAT fails closed.
- Any I2C/DAC boot mutation exits `75` and requires an operator-controlled reboot; the installer never reboots automatically.
- `appliance-installer.sh --fresh-bootstrap` owns staged package → hardware → player → NFC → full-preflight → application construction.

### Clock segment display

- The shared runtime source is `app/static/js/segment-display.js`; individual pages must not carry competing private segment geometry.
- Numeric `0` uses the accepted slash diagonals; capital `O` remains unslashed; `W` has no bottom horizontal segment.
- **Version 3 segment geometry is the selected release-candidate geometry.** The runtime paths, editable `docs/airplay-segment-cell.svg` companion and `20260819-segment-v3` cache identity are regression-pinned together.
- The geometry should not be casually reworked during release cleanup. Any future art change must update the shared runtime source, editable companion and regression identity together.

## Phase status

### Phases 0–6 — **Complete**

Roadmap/baseline, artifact inventory, standalone EQ lifecycle, non-production/read-only validation, bedroom-Pi EQ installation, interface acceptance and real reboot/failure/uninstall/reinstall acceptance are complete. Phase 6 physically proved install → reboot → controlled Camilla failure → alarm-safe failback → repair → uninstall → Direct reboot → reinstall.

### Phase 7 — full appliance installer integration — **In progress: functional/audio/Weather/annunciator work is physically accepted; V3 segment geometry and installer naming are source/CI complete; daytime-theme presentation, final clean-room install, formal verifiers and release hygiene remain**

#### WU Settings commissioning — physical PASS

- [x] Write-only credential manager/API, restricted stdin-only secret helper and root-owned `0600` environment file.
- [x] Set/Replace/Remove/Test controls and running-process environment update without dashboard restart.
- [x] Ecowitt-live convergence preserves an existing commissioned WU history credential byte-for-byte and preserves prior absence.
- [x] **Physical:** real WU credential commissioned locally without disclosure; live/history independence and credential preservation verified. Evidence: `docs/weather-physical-followup-2026-08-17.md`.

#### Historical rainfall + Weather source workspace — physical PASS

- [x] Observation Source workspace, independent live/history badges and exact Today / Last 7 days / Current month / Current year model.
- [x] <=31-day WU batching, omitted-day single retry, confirmed-gap caching and minimum-recorded totals.
- [x] Six Rainy Day Fund calendar summaries plus genuine WU-backed Rain lifetime.
- [x] Separate lifetime cache, bounded backward discovery, confirmed gaps and request-quiet settled state.
- [x] Shared forecast-style rain scrollbar with no native Chromium arrow-button scrollbar.
- [x] Physical WU commissioning, selected-period behavior, gap semantics, lifetime backfill/settling, cache structure and Ecowitt/WU independence accepted. Evidence: `docs/weather-physical-followup-2026-08-17.md`.

#### Final Weather + alarm polish — source/CI + current-Pi physical PASS; one WU-only check deferred

- [x] WU outdoor authority with fresh Ecowitt indoor supplement only.
- [x] WU-derived Hourly/Event rain with persistence/reset synthetic coverage; native values retain precedence.
- [x] WU-derived/persisted daily max gust with native precedence.
- [x] Four current rain gauges and one shared rain scroll surface physically accepted.
- [x] Supplemented WU+Ecowitt indoor readings physically accepted without outdoor authority leakage.
- [ ] **Physical — WU-only deferred/non-blocking:** on a later appliance receiving no fresh Ecowitt custom push, confirm Clock indoor cards and Weather Indoor row disappear after freshness expiry. Source expiry tests are already green; do not disrupt the working single direct Ecowitt destination solely to manufacture this case.
- [x] Configurable alarm Fade start/Fade duration, target/cap semantics, Plexamp takeover, Snooze/re-ring and Dismiss physically accepted.
- [x] WU max gust physically present on Clock and Weather.

#### Final Clock/navigation polish — annunciator physical PASS; V3 geometry selected

- [x] Audio navigation typography matches neighbouring navigation buttons.
- [x] Numeric `0` slash semantics, unslashed capital `O`, and `W` without the bottom segment are regression-pinned.
- [x] LCD-style alarm-set annunciator uses scheduler `scheduled_for`, supports **Next alarm within 12 hours** / **Any future alarm**, is passive/non-clickable and inherits Clock theme/dimming.
- [x] +20° bell orientation/four ticks and balanced active brightness are physically accepted in daytime, Classic night and Astronomy night.
- [x] **Version 3 segment artwork selection:** the selected V3 path geometry is now the shared runtime source, the editable SVG identifies it as the selected geometry, the base template is cache-busted with `20260819-segment-v3`, and regression coverage pins all three together. Head `fb62ad16fbfd706a252d399eb99f2edbf01b8c84` added the final source contract. Treat V3 as selected rather than an open geometry-design task.

#### Daytime theme — **planned next, before the final wiped-SD release run**

- [ ] Perform the separately requested daytime-theme presentation phase now that the segment geometry is stable.
- [ ] Keep this phase presentation-only: it must not alter scheduler behavior, alarm/audio ownership, Weather authority, playback handoff, installer behavior or other accepted functional contracts.
- [ ] Preserve the already accepted Classic/Astronomy night behavior unless the owner explicitly asks for a night-mode change while reviewing the daytime work.
- [ ] Keep the selected V3 segment geometry as the display-art baseline rather than combining theme work with another geometry redesign.
- [ ] Add focused source/regression coverage for whatever daytime-theme authority is introduced and obtain bedside visual acceptance before the final clean-room wipe.
- [ ] The detailed colour/art direction remains owner-led; do not invent a final palette or appearance merely to tick this roadmap item off.

#### Fresh package/hardware/NFC bootstrap — source/CI complete

- [x] Additive fresh prerequisites including `i2c-tools`, `python3-lgpio`, `raspi-config` without global upgrade.
- [x] Paired app/NFC venv transaction; NFC exposes Debian `lgpio` via `--system-site-packages` while dependency authority is scoped to the listener graph.
- [x] Guarded I2C/groups/PN532 owner and live `0x24` probe.
- [x] Deterministic Raspberry Pi DAC Pro commissioning and reboot contract.
- [x] Exact vendored NFC Listener source at upstream `8f5f04213b22cfb5affc6931cb2db91fd07de537`.
- [x] Guarded project-user-aware `nfc-listener.service`.
- [x] Fresh verifier covers player claim/runtime, PN532, `CARD=Pro`, NFC source/venv/unit/service and local Plexamp API.

#### Plexamp compatibility runtime — source/CI complete

- [x] Exact Plexamp 4.13.2 and Node 20.20.2 identities pinned.
- [x] Downloads verified before live mutation.
- [x] Staged runtime/service transaction with exact rollback and idempotent claimed rerun.
- [x] Local interactive claim checkpoint with no claim-token CLI/env/log path.
- [x] `plexamp.service` uses pinned Node and exposes local port `32500` after claim.
- [x] Public `setup.sh` owns CamillaDSP fetch/verification and automatically launches Plexamp at the claim checkpoint.

#### EQ artifact acquisition — source/CI + physical complete

- [x] Guarded `scripts/fetch-camilladsp-4.1.3.sh`.
- [x] Official archive and accepted executable hashes both pinned/verified.
- [x] Independent temporary probe confirmed archive → executable identity; temporary probe workflow removed afterwards.
- [x] Physical spare-card check returned `CAMILLA_ARTIFACT=PASS-EXISTING`; independent version/SHA matched accepted 4.1.3 exactly.

#### Installer naming/release contract — source/CI complete

- [x] Keep the two real roles: human-facing `setup.sh` and guarded lower-level engine.
- [x] Rename/retain the guarded engine unambiguously as `appliance-installer.sh`; `setup.sh` delegates to this file.
- [x] Migrate maintained installer plan/apply/preflight/package/component/verifier tests from the old root name.
- [x] Remove the stale root `install.sh` duplicate rather than shipping three apparent installer entry points.
- [x] CI explicitly syntax-checks `setup.sh`, `appliance-installer.sh` and `segment-display.js`, verifies `setup.sh` delegates to `appliance-installer.sh`, and verifies `install.sh` is absent.
- [x] Exact combined head `3a55c556ccbd61e81a6aa7f758894cdd98aa7446` passed Tests #3769 / run `32216799590`; the Pi was not used as the syntax checker.

#### Spare-SD physical acceptance handoff

- [x] Spare SD used while production card remains untouched.
- [x] Complete prerequisite substrate physically proved: paired venvs, PN532 `0x24`, `CARD=Pro`, pinned Node/Plexamp claim/resume, NFC, dashboard/kiosk, Direct route, restricted helpers and AirPlay.
- [x] Installed EQ → requested Direct convergence physically proved, then persistent EQ promotion and post-EQ regression physically passed. Evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] Focused Weather physical acceptance passed. Evidence: `docs/weather-physical-followup-2026-08-17.md`.
- [x] First complete operator `INSTALL.md` walkthrough on a fresh spare SD reached working WU weather, Plexamp/EQ, AirPlay/EQ and NFC. This preceded the final `setup.sh` CamillaDSP/claim simplification and therefore does not replace the release-candidate clean-room run.
- [x] Functional reboot returned dashboard, WU, Plexamp/EQ, AirPlay/EQ and NFC normally.
- [x] Real scheduled alarm on the fresh install passed takeover, Snooze/re-ring and Dismiss; later fade refinements were separately physically accepted.
- [x] Historical lower-level idempotence pass: the then-current engine was rerun under its old `install.sh` filename without warnings/errors or reboot request. The engine is now named `appliance-installer.sh`; the final public repeat proof is `setup.sh`, not this historical command.
- [x] Dashboard direct-script import regression found after a Weather update was repaired and physically reboot-verified.
- [ ] After the daytime-theme phase is visually accepted, run bootstrap/application/audio verifiers after a representative final reboot and commit the evidence.
- [ ] Wipe the spare SD once more and perform the final `INSTALL.md` clean-room run using **`setup.sh`** from the first public command through reboot checkpoint if required, integrated Camilla fetch, Plexamp claim/resume, Plexamp GUI commissioning, WU configuration, playback/EQ, AirPlay, NFC, alarm/fade and reboot.
- [ ] Rerun final public `setup.sh` on that installed card to prove idempotence with no renewed claim/reboot checkpoint or ownership drift.
- [ ] Confirm normal operation does not dirty tracked files (`git status --porcelain`).
- [ ] Commit/finalize the final clean-room/reboot/repeat evidence documents; only then close Phase 7.

#### Final repository/release hygiene — classification started; broad destructive cleanup waits for clean-room proof

- [x] Initial classification audit in `docs/release-hygiene-audit-2026-08-19.md`.
- [x] README rewritten for the actual release candidate; one final proofread remains after the clean-room run.
- [x] Installer naming audit resolved the ambiguity: retain `setup.sh` + `appliance-installer.sh`; remove stale `install.sh`.
- [ ] Inventory the complete repository/PR file set and remove obsolete one-off test scaffolding, temporary probes, generated files and superseded installer/testing leftovers not required for fresh installation, maintained tests, diagnostics, rollback or useful historical evidence.
- [ ] Review the large `docs/` history deliberately: preserve active operator/architecture/evidence authority; archive/consolidate truly superseded stage documents rather than blindly deleting provenance.
- [ ] Ensure `.gitignore` covers all runtime/generated state and confirm a normally operating fresh appliance leaves the checkout clean.
- [ ] Refresh stale PR #2 description before it leaves Draft; its current body still describes persistent EQ as future work.
- [ ] Remove temporary development branches/refs created during final testing and leave only intentional long-lived/release branches before merge.
- [ ] Run a final tracked-file/install-dependency audit so every file required by `setup.sh`/`appliance-installer.sh` is present after cleanup and no retained file survives merely because it was used by an obsolete experiment.
- [ ] Run the complete validation suite after cleanup. PR #2 remains Draft until release hygiene, final physical gates and explicit owner approval are complete.

**Phase 7 exit condition:** daytime presentation is accepted; the spare-SD appliance passes functional/formal reboot plus the final public `setup.sh` clean-room install and repeat-install; `verify-fresh-bootstrap.sh`, `verify-appliance.sh` and `scripts/audio/verify-audio.sh` are green where applicable; the repository is clean and documented; and explicit owner approval is given. PR #2 remains Draft throughout.

## Phase 7 checkpoint record

- **#7 — package ownership, verifier and 2×2 lifecycle — PASS.** Tests #3003 / run `31355427351`, `3606f59`.
- **#8 — whole-appliance transaction primitives — PASS.** Tests #3013 / run `31356363970`, `bc7b1fe`.
- **#9 — guarded alarm-safe Direct component — PASS.** Tests #3025 / run `31356684593`, `b60b2b9`.
- **#10 — guarded restricted-helper packaging — PASS.** Tests #3037 / run `31357016840`, `8356e80`.
- **#11 — deterministic Shairport integration candidate — PASS.** Tests #3045 / run `31357275403`, `9795c0a`.
- **#12 — guarded AirPlay integration owner — PASS.** Tests #3072 / run `31426194328`, `9847c2e`.
- **#13 — guarded top-level apply boundary — PASS.** Tests #3083 / run `31443831762`, `f424479`.
- **#14 — guarded package and venv bootstrap owner — PASS.** Tests #3095; root ownership Tests #3099 / run `31444400034`, `e106c47`.
- **#15 — guarded weather observation configuration owner — PASS.** Tests #3107 / run `31446688664`, `a52686d`.
- **#16 — shared dashboard owner/application transaction/promoted root apply — PASS.** Tests #3149 / run `31451271274`, `16f30fe`.
- **#17 — alternate-root whole-appliance rollback including fresh EQ — PASS.** Tests #3151 / run `31451366362`, `1a38270`.
- **#18 — first-install WU key-file contract — PASS.** Tests #3171 / run `31452097877`, `d131644`.
- **#19 — read-only real WU payload inspector — PASS.** Tests #3175 / run `31452388309`, `caa583d`.
- **#20 — fresh package/bootstrap preflight ordering — PASS.** Tests #3185 / run `31452688437`, `ac7cec8`.
- **#21 — WU Settings commissioning/write-only credential boundary — PASS.** Tests #3219 / run `31663696066`, `7a901109e996e8b4cb342e915a708b02ed745d28`.
- **#22 — guarded fresh-Pi I2C/PN532 hardware foundation — PASS.** Tests #3237 / run `31664328721`, `d4570fb176013d7f96608ede96dd114510bf5d2a`.
- **#23 — pinned NFC runtime, paired venv and guarded NFC service owner — PASS.** Tests #3263 / run `31664707020`, `63fa8825e4949d8805e43db5beb346c2a3c6b9b6`.
- **#24 — staged fresh-bootstrap preflight/root route with fail-closed player boundary — PASS.** Tests #3285 / run `31691861309`, `bf701e4ba256c45c0fd295f88026bfbe5a54ffc9`.
- **#25 — test-ready spare-SD appliance: Plexamp/Node, DAC Pro, verifier, Camilla fetcher/runbook — PASS.** Tests #3339 / run `31848016743`, `a3f05ebee67565cfaa5a6f7a605fc770a7b4fbd8`.
- **#26 — Trixie first-apply dependency-boundary repair — PASS (source/CI).** Tests #3353 / run `31895570826`, `85db50016af086454208c2e0216f479d8b451790`.
- **#27 — cached historical rainfall + Weather Observation Source workspace — PASS (source/CI).** `28baf6fd91b4169813fbdbbe99d7b613fde8d151`; Tests #3411 / run `31972466589`. Later confirmed-gap semantics supersede its initial unavailable-marker policy.
- **#28 — installed EQ → requested Direct convergence — PASS (source/CI + later physical).** `4bfd9d0ed83927473d0ae70f5947761de6fad817` plus focused regression `b4e64fcf279843a7f928c5da41252adb11aae00a`; Tests #3421/#3423. Physical Direct convergence was later recorded in `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- **#29 — retryable WU rainfall gaps + Weather spacing — PASS (source/CI), semantics later superseded.** `967e684ca51b07ad25731d78401a195cde024081`; Tests #3445.
- **#30 — Weather physical-follow-up convergence — PASS (source/CI), presentation evolved during acceptance.** `bd3124e0bbb8682d8faf0f3cc44725fc7da9fc8c`; Tests #3451.
- **#31 — confirmed station gaps + Rainy Day Fund projection — PASS.** Current-year physical gap case and corrected projection accepted; `6316a63fbc109967ccd517a631796be01b859ba2`, Tests #3485.
- **#32 — forecast-style Rainy Day Fund scroll + genuine WU Rain lifetime — PASS (source/CI + physical).** Settled lifetime behavior and cache integrity physically accepted; source/lifecycle head through `22455624917ce456087e3a11041937b3c0526623`, Tests #3523.
- **#33 — focused Direct pre-EQ smoke + UI/runtime hygiene — PASS (physical/source).** Plexamp/NFC healthy and EQ surfaces truthfully reported Install required.
- **#34 — guarded persistent EQ promotion — PASS (physical).** Canonical split-bus route, service identity and independent verifiers passed.
- **#35 — focused post-EQ regression — PASS (physical).** Plexamp/AirPlay/EQ, Music Master isolation, alarm cap/Snooze/re-ring/Dismiss and NFC all passed.
- **#36 — first complete operator INSTALL walkthrough + functional reboot/repeat-engine/alarm closure — PARTIAL PASS (physical, 18 August).** Working fresh appliance and historical lower-level rerun proved; final public `setup.sh` clean-room/repeat proof remains.
- **#37 — WU supplementary indoor/derived rain + initial fade + nav/segment mapping closure — PASS (source/CI + substantial physical).** Tests #3643; physical rain/indoor/nav/fade acceptance followed.
- **#38 — dashboard direct-import recovery + WU max gust + configurable alarm fade start — PASS (source/CI + physical).** `fb041f6` recovery Tests #3651; combined fade/max-gust head `19b1edfb8d40a4ae9e27a29d19fd9988e19194fd`, Tests #3669; physical accepted.
- **#39 — LCD-style Clock alarm annunciator — PASS (source/CI; physical follow-up exposed activation/artwork refinements).** `e687d14de733161645a9a37dde6936ba4e478fe0`, Tests #3687.
- **#40 — annunciator activation/artwork correction — PASS (source/CI + partial physical).** `15b699724ba6feeda72cfddc0e008587aaea21b1`, Tests #3701; activation/orientation/ticks accepted, brightness then refined.
- **#41 — annunciator brightness balance — PASS (source/CI + physical).** `f815603b0b27893d495dbf570e928ebbef73afa5`, Tests #3709; final annunciator accepted.
- **#42 — release-hygiene classification + README modernization — PASS (documentation/source; broad destructive cleanup deferred).** `docs/release-hygiene-audit-2026-08-19.md` classifies production/test/history assets; README reflects the release candidate.
- **#43 — selected Version 3 segment geometry + unambiguous installer naming — PASS (source/CI).** V3 runtime/editable/cache contract is pinned by `fb62ad16fbfd706a252d399eb99f2edbf01b8c84`. The guarded engine is `appliance-installer.sh`, maintained callers/tests were migrated, stale `install.sh` was removed, and CI explicitly checks both release installer entry points plus `segment-display.js`. Exact combined head `3a55c556ccbd61e81a6aa7f758894cdd98aa7446` passed Tests #3769 / run `32216799590`. The remaining bedside V3 visual check belongs to the next presentation acceptance pass rather than installer naming.

No checkpoint is recorded as fully physically complete until its exact physical gates pass. Source/CI PASS never substitutes for a remaining bedside or clean-room acceptance gate.
