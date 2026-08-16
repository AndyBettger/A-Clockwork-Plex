# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 16 August 2026  
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
- Historical rainfall periods are exactly **Today**, **Last 7 days**, **Current month** and **Current year**; default is Last 7 days.
- Today uses live `dailyrainin`; completed historical days use WU daily `precipTotal`.
- `weather-rainfall-history.json` is a station-scoped, secret-free supplemental cache for completed WU days/unavailable markers and is ignored by Git.
- Only missing completed dates are fetched, grouped into contiguous requests of at most 31 days. A successfully queried date without usable data is cached as unavailable.
- Incomplete history suppresses the aggregate rather than displaying a misleading partial total. History failure must not take current observations down.
- Live observation source and WU history source are independent; Ecowitt Push may remain live while WU supplies history.
- Commission current source and WU history under **Settings → Weather → Observation source**.
- WU API key is write-only commissioning data: never returned to the browser, stored in `config.json`/browser storage, placed in argv or logged.
- Persistent secret storage is root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`; the restricted helper receives key material on stdin.

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

### Phase 7 — full appliance installer integration — **In progress: source/CI green through EQ → Direct convergence; physical Direct commit retry, Weather history and EQ/reboot acceptance remain**

#### WU Settings commissioning — source/CI complete

- [x] Dedicated write-only credential manager/API outside the revisioned Settings transaction.
- [x] Restricted stdin-only secret helper and root-owned `0600` environment file.
- [x] Set/Replace/Remove key, credential status and Test connection controls.
- [x] Running-process environment update without dashboard restart.
- [x] Sanitized provider test path and source tests.
- [ ] **Physical:** enter real station ID/key locally, Test connection, verify live health and prove secret absence from Settings/config/log output.

#### Historical rainfall + Weather source workspace — source/CI complete

- [x] Observation Source is its own Weather subpage; Station owns dashboard labels/refresh.
- [x] Explicit current-source status (`Ecowitt Push`, `WU Ready`, setup/degraded states).
- [x] Exact Today / Last 7 days / Current month / Current year model.
- [x] Live Today semantics and station-scoped secret-free WU daily cache.
- [x] <=31-day missing-range batching and unavailable-date caching.
- [x] Incomplete-total suppression and live/history source independence.
- [x] Weather Rainy Day Fund receives the selected completed historical aggregate without disturbing Rain Today/current observations.
- [x] Checkpoint #27 full CI green.
- [ ] **Physical:** commission WU history, exercise all four periods, prove second completed Current-year refresh fetches zero additional ranges, verify cache has no secret fields and confirm history failure leaves live observations healthy.

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
- [x] 16 August retry proved the complete prerequisite substrate again and then exposed the remaining installed-EQ → requested-Direct convergence gap; evidence: `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`, exit `2`.
- [x] Checkpoint #28 source repair now supports transactional EQ → Direct convergence; regression coverage proves success and forced rollback.
- [ ] **Physical fresh Direct installation and verification:** fast-forward the same spare SD to the latest green branch head, reuse the existing evidence directory, rerun the timestamped Direct apply, and require root installer exit `0` plus both independent verifiers PASS. Do not manually uninstall EQ.
- [ ] Physical PN532/NFC playback + dashboard-switch/debounce acceptance.
- [ ] Physical AirPlay/PlaybackCoordinator completion notes.
- [ ] Physical Music Master = 0% versus real scheduled-alarm isolation acceptance.
- [ ] Physical Direct-mode truthful **Install required** EQ UI acceptance.
- [ ] Physical historical-rainfall/WU source-workspace acceptance.
- [ ] Physical EQ installation, split-bus identity and audible Bass/Mid/Treble/bypass acceptance.
- [ ] Reboot acceptance with bootstrap/application/audio verifiers green.
- [ ] Repeat whole-appliance install with no ownership drift or renewed claim/reboot checkpoint.
- [ ] Real WU Settings/Test Connection acceptance.
- [ ] Commit a dated physical result/evidence document; only then close Phase 7.

**Phase 7 exit condition:** the spare-SD appliance passes Direct → physical feature checks → EQ → reboot → repeat-install → real WU live/history commissioning with `verify-fresh-bootstrap.sh`, `verify-appliance.sh` and `scripts/audio/verify-audio.sh` green where applicable; dated evidence is committed. PR #2 remains Draft throughout.

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
- **#27 — cached historical rainfall + Weather Observation Source workspace — PASS (source/CI).** Commit `28baf6fd91b4169813fbdbbe99d7b613fde8d151`; Tests #3411 / run `31972466589`. Physical WU/history acceptance remains open.
- **Post-#27 documentation incident — repaired.** `7479d6308417561983bbde87e3a9a788686388a1` failed only because the test-pinned Weather heading was changed; the exact `# 14. Commission Weather Underground through Settings` heading was restored and remains contract-pinned.
- **#28 — installed EQ → requested Direct convergence — PASS (source/CI).** Physical Attempt 6 reached application transition after package/venv, PN532 `0x24`, `CARD=Pro`, claimed Plexamp, NFC and full preflight passed, then the old hard guard rejected the already-EQ spare SD with exit `2`; evidence `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`. Commit `4bfd9d0ed83927473d0ae70f5947761de6fad817` replaces that rejection with specialist EQ teardown under the outer application transaction, retained pre-EQ backup/tombstone handling and pre-service `snd_aloop` rollback restoration; Tests #3421 / run `31975846667` passed. Commit `b4e64fcf279843a7f928c5da41252adb11aae00a` adds focused success/forced-rollback/retained-backup/order regression coverage; Tests #3423 / run `31976778069` passed. Physical retry remains pending.

No checkpoint is recorded as PASS until its exact tested state has passed full CI. Source/CI PASS does not substitute for remaining physical gates.

### Phase 8 — cleanup and release preparation — **Not started**

- [ ] Preserve final Stage C archival evidence before deleting obsolete working material.
- [ ] Mark retained Stage C transactional material historical/non-production.
- [ ] Retire orphan Settings presenter code after supported presenters freeze.
- [ ] Retire obsolete self-mutating Phase 2 workflows after preserving useful history; do not reactivate them.
- [ ] Freeze supported appliance/player/weather/install contract after Phase 7 physical acceptance.
- [ ] **Rewrite `README.md` for the finished appliance and installer before PR #2 is merged**: features/screenshots, hardware, Plexamp Headless, NFC, Direct/EQ, alarms, AirPlay, Weather Settings/history, install, first-run, update/recovery and troubleshooting.
- [ ] Link installer/verifier/EQ repair/uninstall/recovery docs.
- [ ] Record final physical results/deviations.
- [ ] Run final CI/release review.
- [ ] Review PR #2 separately; do not make ready or merge without explicit owner approval.

## Immediate next action

1. **Fast-forward `plexamp-test` to the latest green `feature/alarm-engine` head**, verify exact SHA/clean tree, and recover the existing evidence directory from `$HOME/.acp-phase7-evidence-path` rather than creating a new one.
2. Rerun the same timestamped `install.sh --fresh-bootstrap --audio direct --weather-observations ecowitt-push` apply. The existing EQ appliance is an accepted input state: **do not manually uninstall EQ**. Require the already-proven substrate to reconverge, the new EQ → Direct transition to complete, final application verifier to pass, `ROOT_INSTALL=COMMITTED`, and root installer exit `0`. Preserve any nonzero log without manual fix-forward.
3. Run `verify-fresh-bootstrap.sh` and `verify-appliance.sh --audio direct`, then check canonical Direct route SHA and absence of the EQ installed marker.
4. Complete Direct physical checks: Plexamp/NFC display handoff/debounce, AirPlay/PlaybackCoordinator, Music Master = 0% versus scheduled-alarm isolation and truthful Direct-mode **Install required** EQ state.
5. Under **Settings → Weather → Observation source**, commission WU history and exercise/cache-check all four periods without exposing the key.
6. Complete guarded EQ promotion, reboot and repeat-install acceptance; commit the dated physical result. Only then move to Phase 8 README/release work.

## Roadmap maintenance discipline

- Material completion/block/scope changes update this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates record exact scope/result/evidence.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- `docs/fresh-appliance-acceptance-runbook.md` must stay synchronized with fresh-Pi procedure/evidence requirements.
- `docs/fresh-bootstrap-physical-progress-2026-08-15.md` records the real spare-SD attempt chain.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap/runbook updates.
