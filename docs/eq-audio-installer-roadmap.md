# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 17 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed history through Phase 7 checkpoint #6 is preserved in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. Detailed real spare-SD bootstrap attempts after checkpoint #26 are recorded in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`. This file is the active implementation/acceptance authority.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Fresh Direct keeps Plexamp/AirPlay under Music Master while alarm joins the DAC-facing mix independently.
- `scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate.
- Do not use the old bare `scripts/install-master-eq.sh` production path.
- An already-installed EQ appliance is now a **supported convergent source state** when the whole-appliance installer is asked for Direct. Do not require a manual EQ uninstall.
- EQ → Direct convergence must remain inside the outer application transaction: specialist teardown retains the pre-EQ backup, rollback restores that backup and the pre-transition live `snd_aloop` state before captured EQ services are reactivated, and retained backup cleanup occurs only after successful outer commit.

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
- Current observations may be Ecowitt custom push or Weather Underground PWS.
- The configurable historical-rainfall periods remain exactly **Today**, **Last 7 days**, **Current month** and **Current year**; default is Last 7 days.
- Today uses live `dailyrainin`; completed historical days use WU daily `precipTotal`.
- `weather-rainfall-history.json` is a station-scoped, secret-free supplemental cache. Numeric daily totals live under `days`; confirmed successful-query station-offline dates live separately as `no_station_data` gap markers. `null` day markers are not an accepted final cache state.
- Missing/invalid completed dates are fetched in contiguous WU requests of at most 31 days. If a successful range omits a date, that date is retried once as a single-day request before it may be classified as a confirmed station-data gap.
- Confirmed station-data gaps are not repeatedly re-fetched. They do **not** make otherwise successful history an API failure: the sum of recorded days remains visible as a **minimum recorded** total with explicit coverage information.
- Legacy `null` unavailable markers from the earlier implementation are treated as missing and retried.
- An actual provider/configuration/credential failure remains an error for the selected historical aggregate and must never take current observations down.
- Live observation source and WU history source are independent; Ecowitt Push may remain live while WU supplies history.
- Commission current source and WU history under **Settings → Weather → Observation source**. The accepted physical presentation uses a bordered live-source badge at the top-right of the Observation source card and a separate bordered history badge at the top-right of the Historical rainfall card.
- Weather Settings cards and source grids use deliberate touch-friendly separation on both supported landscape targets, including 1024×600.
- Rainy Day Fund historical summaries are independent of the single configurable history period and expose **This week / Last week / This month / Last month / This year / Last year**. The station-lifetime **Total rain** gauge is retained only when Ecowitt actually supplies it.
- Rainy Day Fund may scroll horizontally by touch so the six/seven gauges remain readable without crushing the 1280×720 or 1024×600 layouts. Coverage notes use concise copy such as `3 days not recorded`.
- WU API key is write-only commissioning data: never returned to the browser, stored in `config.json`/browser storage, placed in argv or logged.
- Persistent secret storage is root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`; the restricted helper receives key material on stdin.
- Selecting/reconverging **Ecowitt Push for live observations must preserve the exact existing managed WU credential file** because WU may still supply supplemental rainfall history. If that managed file was absent, Ecowitt convergence must keep it absent; it must never invent, rewrite or reveal a credential.

### Player/runtime

- **Plexamp Headless remains the player for this release.** Caldera migration is out of Phase 7 scope.
- Plexamp Headless: `4.13.2`, official archive SHA `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.
- Node: `20.20.2` linux-arm64, SHA `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`, installed beneath `/opt/a-clockwork-plex` without replacing distribution Node.
- Fresh account/player setup is an explicit local interactive checkpoint; claim material is never a normal installer/evidence field.
- An unclaimed fresh runtime exits `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`; after local claim/name, rerun resumes.

### Fresh-Pi hardware/bootstrap

- The real bedroom Pi/HAT/display is the physical target, but the accepted production SD card remains removed and untouched. A separate spare SD is the disposable acceptance target.
- No global OS upgrade, `rpi-update`, Pi EEPROM/bootloader update, HAT EEPROM write or external hardware firmware update belongs to appliance bootstrap.
- PN532: I2C bus `1`, address `0x24`; project user groups `i2c`, `gpio`, `spi`.
- Accepted DAC: Raspberry Pi DAC Pro, ALSA `CARD=Pro`.
- Already-working `CARD=Pro` is accepted without boot mutation; managed fallback is `rpi-dacpro` only when required. A different identified HAT fails closed.
- Any I2C/DAC boot mutation exits `75` and requires an operator-controlled reboot; the installer never reboots automatically.
- `install.sh --fresh-bootstrap` owns staged package → hardware → player → NFC → full-preflight → application construction.

## Phase status

### Phases 0–6 — **Complete**

Roadmap/baseline, artifact inventory, standalone EQ lifecycle, non-production/read-only validation, bedroom-Pi EQ installation, interface acceptance and real reboot/failure/uninstall/reinstall acceptance are complete. Phase 6 physically proved install → reboot → controlled Camilla failure → alarm-safe failback → repair → uninstall → Direct reboot → reinstall.

### Phase 7 — full appliance installer integration — **In progress: physical Direct construction/verification and core WU history acceptance complete; Rainy Day Fund retest, hands-on Direct behaviour, EQ/reboot and repeat-install acceptance remain**

#### WU Settings commissioning — physical PASS

- [x] Dedicated write-only credential manager/API outside the revisioned Settings transaction.
- [x] Restricted stdin-only secret helper and root-owned `0600` environment file.
- [x] Set/Replace/Remove key, credential status and Test connection controls.
- [x] Running-process environment update without dashboard restart.
- [x] Sanitized provider test path and source tests.
- [x] Ecowitt-live weather convergence preserves an existing commissioned WU history credential byte-for-byte and preserves prior absence when none exists.
- [x] **Physical:** real WU credential commissioned locally without key disclosure; write-only status/config boundaries verified; WU supplemental history stayed healthy with Ecowitt Push live; later Ecowitt reconvergence preserved the exact managed WU credential and root `0600` metadata. Evidence: `docs/weather-physical-followup-2026-08-17.md`.

#### Historical rainfall + Weather source workspace — core physical PASS; Rainy Day Fund source/CI PASS, physical retest pending

- [x] Observation Source is its own Weather subpage; Station owns dashboard labels/refresh.
- [x] Explicit current-source and history status badges remain card-local and truthful (`Ecowitt Push`, `WU Ready`, `History ready`, setup/degraded states).
- [x] Exact configurable Today / Last 7 days / Current month / Current year model.
- [x] Live Today semantics and station-scoped secret-free WU daily cache.
- [x] <=31-day missing-range batching and single-day retry of dates omitted from successful range responses.
- [x] Confirmed successful-query station gaps are cached separately from numeric totals and do not cause repeated fetches.
- [x] Minimum-recorded totals remain visible with explicit missing-day coverage; actual API/config/credential failures remain distinct and supplemental to live observations.
- [x] Rainy Day Fund source projection now receives six independent calendar summaries (This/Last week, month and year), retaining station-lifetime Total only when supplied by Ecowitt.
- [x] Rainy Day Fund uses a touch-friendly horizontal strip for the expanded gauge set.
- [x] Physical Settings presentation, WU commissioning, Ecowitt/WU independence, credential preservation, Today, Last 7 days, Current month and Current year selected-period behavior are accepted.
- [x] Physical Current-year gap case: 226/229 days recorded, confirmed gaps on `2026-03-03`, `2026-03-05`, `2026-03-07`, `status: ready`, `complete: true`, `coverage_complete: false`, `total_in: 21.38`; two consecutive forced refreshes both reported `fetched_ranges: 0` / `retried_dates: 0`.
- [x] Rainy Day Fund blank-gauge root cause identified: the rainfall wrapper patched the `app.main` facade while Flask's context processor resolved `dashboard_core.weather_detail_data`. Source head `6316a63fbc109967ccd517a631796be01b859ba2` patches the real core projection and passed Tests #3485 / run `31991516804`.
- [ ] **Physical:** load the corrected Rainy Day Fund projection, allow one-time previous-year backfill, require the second refresh to show both `fetched_ranges: 0` and `gauge_fetched_ranges: 0`, confirm all six calendar gauges plus optional lifetime Total, horizontal touch scrolling, and concise missing-day notes; then perform the structural cache inspection.

#### Fresh package/hardware/NFC bootstrap — source/CI complete

- [x] Additive fresh prerequisites including `i2c-tools`, `python3-lgpio`, `raspi-config` without global upgrade.
- [x] Paired app/NFC venv transaction; NFC exposes Debian `lgpio` via `--system-site-packages` while dependency authority is scoped to the recursive listener graph.
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

#### EQ artifact acquisition — source/CI complete

- [x] Guarded `scripts/fetch-camilladsp-4.1.3.sh`.
- [x] Official archive and accepted executable hashes both pinned/verified.
- [x] Independent temporary probe confirmed archive `d9a170...aca5` extracts executable `e04c7a...edfa`; temporary probe workflow removed afterwards.

#### Spare-SD physical acceptance handoff

- [x] Runbook uses a spare SD while production card remains untouched.
- [x] Runbook covers fresh baseline/evidence, Direct, exits `75`/`76`, independent verifiers, NFC/AirPlay/alarm, guarded Camilla fetch, EQ, reboot, repeat install and WU Settings/history.
- [x] First Trixie apply exposed inherited-system NFC `pip check` noise; checkpoint #26 repair is green.
- [x] Subsequent attempts physically proved paired venvs, PN532 `0x24`, `CARD=Pro`, pinned Node/Plexamp claim/resume, NFC, full preflight, dashboard/kiosk, Direct route, restricted helpers and AirPlay. Detailed evidence is in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`.
- [x] Protected `/etc/sudoers.d` verification was repaired at both helper-owner and final-verifier boundaries.
- [x] 16 August retry proved the complete prerequisite substrate again and then exposed the installed-EQ → requested-Direct convergence gap; evidence: `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`, exit `2`.
- [x] Checkpoint #28 source repair supports transactional EQ → Direct convergence; regression coverage proves success and forced rollback.
- [x] **Physical fresh Direct installation and verification:** 17 August guarded convergence completed from the existing EQ state with root installer exit `0`, `ROOT_INSTALL=COMMITTED`, `APPLICATION_VERIFY=PASS`, `FRESH_BOOTSTRAP_VERIFY=PASS`, `APPLIANCE_VERIFY=PASS`, canonical Direct SHA and clean EQ/loopback residue. Evidence is recorded in `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] **Weather physical follow-up core:** Settings presentation, WU commissioning, live/history independence, Ecowitt credential preservation and selected-period gap semantics passed physically; evidence is recorded in `docs/weather-physical-followup-2026-08-17.md`.
- [ ] **Weather Rainy Day Fund follow-up:** physically retest corrected core projection, six historical calendar gauges, optional lifetime Total and horizontal touch scroll after one-time previous-year backfill.
- [ ] Physical PN532/NFC playback + dashboard-switch/debounce acceptance.
- [ ] Physical AirPlay/PlaybackCoordinator completion notes.
- [ ] Physical Music Master = 0% versus real scheduled-alarm isolation acceptance.
- [ ] Physical Direct-mode truthful **Install required** EQ UI acceptance.
- [ ] Physical EQ installation, split-bus identity and audible Bass/Mid/Treble/bypass acceptance.
- [ ] Reboot acceptance with bootstrap/application/audio verifiers green.
- [ ] Repeat whole-appliance install with no ownership drift or renewed claim/reboot checkpoint.
- [ ] Commit/finalize the dated physical result/evidence documents; only then close Phase 7.

**Phase 7 exit condition:** the spare-SD appliance passes Direct → physical feature checks → EQ → reboot → repeat-install, with real WU commissioning/core history and Rainy Day Fund presentation accepted and `verify-fresh-bootstrap.sh`, `verify-appliance.sh` and `scripts/audio/verify-audio.sh` green where applicable; dated evidence is committed. PR #2 remains Draft throughout.

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
- **#26 — Trixie first apply dependency-boundary repair — PASS (source/CI).** Tests #3353 / run `31895570826`, `85db50016af086454208c2e0216f479d8b451790`. Later physical evidence supersedes #26 as the Pi source target.
- **#27 — cached historical rainfall + Weather Observation Source workspace — PASS (source/CI).** Commit `28baf6fd91b4169813fbdbbe99d7b613fde8d151`; Tests #3411 / run `31972466589`. Its original unavailable-marker cache policy is superseded by the later confirmed-gap model.
- **Post-#27 documentation incident — repaired.** `7479d6308417561983bbde87e3a9a788686388a1` failed only because the test-pinned Weather heading was changed; the exact `# 14. Commission Weather Underground through Settings` heading was restored and remains contract-pinned.
- **#28 — installed EQ → requested Direct convergence — PASS (source/CI).** Physical Attempt 6 reached application transition after package/venv, PN532 `0x24`, `CARD=Pro`, claimed Plexamp, NFC and full preflight passed, then the old hard guard rejected the already-EQ spare SD with exit `2`; evidence `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`. Commit `4bfd9d0ed83927473d0ae70f5947761de6fad817` replaces that rejection with specialist EQ teardown under the outer application transaction, retained pre-EQ backup/tombstone handling and pre-service `snd_aloop` rollback restoration; Tests #3421 / run `31975846667` passed. Commit `b4e64fcf279843a7f928c5da41252adb11aae00a` adds focused success/forced-rollback/retained-backup/order regression coverage; Tests #3423 / run `31976778069` passed.
- **Post-#28 physical Direct convergence — PASS.** Commit `ec86c76bc0a6c9aec53bc51394bc06a15028cda8` records the 17 August spare-SD root install exit `0`, both independent Direct verifiers PASS, canonical Direct route identity and clean post-EQ residue. Hands-on Direct feature checks remain open.
- **#29 — retryable WU rainfall gaps + Weather card spacing follow-up — PASS (source/CI), semantics later superseded.** Commit `967e684ca51b07ad25731d78401a195cde024081` introduced retryable omitted/invalid dates and responsive card spacing; Tests run `31981475409` / #3445 passed. Its all-or-nothing total rule is superseded by the confirmed station-gap/minimum-recorded model physically accepted below.
- **#30 — Weather physical-follow-up convergence — PASS (source/CI), presentation evolved during physical acceptance.** Commit `bd3124e0bbb8682d8faf0f3cc44725fc7da9fc8c` added credential preservation and strengthened source-card spacing. Physical acceptance subsequently settled on card-local live/history status badges rather than the transient global-heading placement. Tests run `31984835861` / #3451 passed.
- **#31 — confirmed station gaps + Rainy Day Fund projection — core physical PASS / gauge source-CI PASS.** On `plexamp-test`, Current year physically returned 226/229 days, three confirmed March station gaps, `status: ready`, `complete: true`, `total_in: 21.38`, and two repeated refreshes at zero fetch/retry cost. Settings showed **History ready** with explicit minimum-recorded coverage. The blank Rainy Day Fund then exposed a `main` facade versus `dashboard_core` context-projection bug. Source commit `6316a63fbc109967ccd517a631796be01b859ba2` patches the real Flask projection, adds This/Last week/month/year summaries plus optional lifetime Total, one-time prior-year backfill and horizontal touch scrolling; Tests #3485 / run `31991516804` passed. Physical gauge retest remains open.

No checkpoint is recorded as fully physically complete until its exact physical gates pass. Source/CI PASS does not substitute for remaining physical acceptance.
