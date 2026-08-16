# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 16 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed physical/CI history through Phase 7 checkpoint #6 is preserved verbatim in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. This file is the active implementation/acceptance authority; later checkpoints are retained below in compact form. Detailed spare-SD physical bootstrap attempts after checkpoint #26 are recorded in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Fresh Direct: Plexamp/AirPlay remain under Music Master while alarm joins the DAC-facing mix independently.
- `scripts/audio/preflight-eq.sh` remains the historical **read-only bedroom-Pi validation gate**. **No bedroom-Pi installation** was permitted until that gate passed; do not replace that evidence with a mutating rehearsal.
- Do not run the old bare `scripts/install-master-eq.sh` production path.

| Identity | Accepted value |
|---|---|
| Historical Phase 6 Direct rollback | `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` |
| Fresh alarm-safe Direct / managed failback | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| +2/0/+2 Camilla config | `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578` |
| CamillaDSP executable | `4.1.3`, SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| CamillaDSP official aarch64 archive | SHA `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a` |

The historical `08d00093...` route remains the exact rollback identity for the physically accepted Phase 6 lifecycle. It is **not** the fresh Direct profile because that historical graph routes alarm through Music Master.

### Weather

- Open-Meteo remains the forecast provider.
- Current observations may be Ecowitt custom push or Weather Underground PWS.
- There is **no general current-observation cache/fan-out server**. The dedicated `weather-rainfall-history.json` file is a narrow supplemental cache containing only per-station completed-day WU rainfall totals/unavailable markers; it contains no credential material and is ignored by Git.
- Historical rainfall periods are exactly **Today**, **Last 7 days**, **Current month** and **Current year**. Today always uses the live station `dailyrainin`; completed historical days use Weather Underground daily `precipTotal`.
- Historical completed days are cache-first and immutable. Only missing completed dates are fetched, collapsed into contiguous Weather Underground requests of at most 31 days. A successfully queried date with no usable provider record is cached as unavailable so refreshes do not hammer the API.
- Historical rainfall is supplemental. Failure, missing credentials or incomplete history must not take current observations down and must not present a misleading partial total.
- Live source and history source are independent: Ecowitt Push may remain the current-observation provider while the configured WU station/key supplies historical rainfall.
- Current-observation source and WU historical-rainfall commissioning belong under **Settings → Weather → Observation source**; Station is reserved for dashboard labels/refresh.
- WU API key is **write-only commissioning data**: it may be submitted locally to the dedicated credential endpoint but is never returned to the browser, written to `config.json`, stored in browser storage, placed in argv or logged.
- Persistent WU secret storage is root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`; restricted helper receives new key material on stdin.
- Successful set/remove updates the running dashboard environment so no dashboard restart is required.

### Player/runtime

- **Plexamp Headless remains the player for this release.** Caldera migration is out of scope for Phase 7.
- Pinned Plexamp Headless compatibility runtime:
  - version `4.13.2`;
  - official archive `https://plexamp.plex.tv/headless/Plexamp-Linux-headless-v4.13.2.tar.bz2`;
  - 14,566,439 bytes;
  - SHA-256 `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.
- Pinned Node runtime:
  - `20.20.2` linux-arm64;
  - SHA-256 `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`;
  - installed under `/opt/a-clockwork-plex`, not by NodeSource/nvm and not as a replacement for the distribution Node.
- Fresh account/player setup is an explicit local interactive checkpoint. Claim material is never a normal installer argument or evidence field.
- A fresh unclaimed runtime exits `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`; after local claim/name and Ctrl-C, rerunning the root installer resumes.

### Fresh-Pi hardware/bootstrap

- Physical target is the actual bedroom Pi/HAT/display, but **the accepted production SD card is removed and kept untouched**. A separate spare SD card is the disposable fresh-install target.
- This supersedes the earlier plan to wipe/reimage the accepted card; no backup/restore operation is required merely to perform the fresh test.
- Global OS upgrade, `rpi-update`, Pi EEPROM/bootloader update, HAT EEPROM write and external hardware firmware update remain outside appliance bootstrap.
- PN532 contract: I2C bus `1`, address `0x24`; project user groups `i2c`, `gpio`, `spi`.
- Accepted DAC is **Raspberry Pi DAC Pro**, runtime ALSA `CARD=Pro`.
- Hardware owner first accepts an already-working `CARD=Pro` without changing boot config. If required, it uses the documented `rpi-dacpro` path; older IQaudIO hardware receives the compatibility HAT-overlay suppression block before `rpi-dacpro`. An identified different HAT fails closed.
- Any I2C/DAC boot mutation exits `75` with an operator-controlled reboot/resume contract; the installer never reboots automatically.
- Root `install.sh --fresh-bootstrap` owns staged package → hardware → player → NFC → full-preflight → application construction. The compatibility route remains separately fail-closed and unchanged.

## Phase status

### Phases 0–6 — **Complete**

Roadmap/baseline, artifact inventory, standalone EQ lifecycle, non-production/read-only validation, bedroom-Pi EQ installation, feature/interface acceptance, and real reboot/failure/uninstall/reinstall acceptance are complete. Phase 6 physically proved install → reboot → controlled Camilla failure → alarm-safe failback → repair → uninstall → Direct reboot → reinstall.

### Phase 7 — full appliance installer integration — **In progress: spare-SD Direct substrate largely proven; final Direct commit-gate rerun, Weather history and EQ/reboot acceptance remain**

#### WU Settings commissioning — source/CI complete

- [x] Dedicated write-only credential manager/API outside the revisioned Settings transaction.
- [x] Restricted stdin-only WU secret helper and root-owned `0600` environment file.
- [x] Settings controls for Set/Replace/Remove key, credential status and Test connection.
- [x] Running-process environment update without dashboard restart.
- [x] Sanitized real-provider test path and source tests.
- [x] Checkpoint #21 green.
- [ ] **Physical:** enter real station ID/key locally, Test connection, verify live observations/health and prove secret absence from Settings/config/log output.

#### Historical rainfall + Weather source workspace — source/CI complete

- [x] Observation Source promoted to its own Weather subpage; Station now owns dashboard labels/refresh.
- [x] Live-source status pill uses explicit current-source wording (`Ecowitt Push`, `WU Ready`, degraded/setup states).
- [x] Exact period model: Today / Last 7 days / Current month / Current year; default Last 7 days.
- [x] Today uses live `dailyrainin` and does not require or call WU history.
- [x] WU daily `precipTotal` cache is station-scoped, secret-free and requests only missing completed dates in <=31-day contiguous ranges.
- [x] Missing provider records are remembered as unavailable and incomplete history suppresses the aggregate rather than displaying a partial total.
- [x] WU history remains available while Ecowitt is the live current-observation source.
- [x] Existing Weather page Rainy Day Fund receives the selected completed historical aggregate without disturbing Rain Today/current observations.
- [x] Focused source coverage: 14 rainfall/settings tests plus Python/JavaScript syntax checks; full Tests workflow #3411 / run `31972466589` passed at checkpoint #27.
- [ ] **Physical:** commission WU history, exercise all four periods, prove a completed second Current-year refresh fetches zero additional ranges, verify cache contains no secret fields, and prove a history failure leaves live observations operational.

#### Fresh package/hardware/NFC bootstrap — source/CI complete

- [x] Additive package owner includes `i2c-tools`, `python3-lgpio`, `raspi-config` without global OS/firmware upgrade.
- [x] Paired app + NFC venv transaction; NFC uses `--system-site-packages` for `lgpio`.
- [x] NFC dependency verification keeps pip as the dependency authority while scoping failures to the recursive vendored listener graph; unrelated Debian system-site metadata gaps are informational and unclassified output fails closed.
- [x] Guarded I2C/groups/PN532 owner and read-only immediate `0x24` probe.
- [x] Deterministic Raspberry Pi DAC Pro commissioning with transactional marker-bounded boot config and explicit reboot checkpoint.
- [x] Exact vendored NFC Listener source from upstream commit `8f5f04213b22cfb5affc6931cb2db91fd07de537`.
- [x] Guarded project-user-aware `nfc-listener.service`; no import of the old standalone setup script's kiosk/AirPlay/Plexamp-handoff authority.
- [x] Fresh bootstrap verifier covers pinned player runtime, claim state, PN532, `CARD=Pro`, NFC source/venv/unit/service and local Plexamp API.

#### Plexamp compatibility runtime — source/CI complete

- [x] Exact Plexamp 4.13.2 archive identity pinned from official artifact probe.
- [x] Exact Node 20.20.2 linux-arm64 identity pinned.
- [x] Downloads are verified before extraction or live-state mutation.
- [x] Staged runtime/service transaction with exact rollback and idempotent claimed rerun.
- [x] Local interactive claim checkpoint; no claim token CLI/env/log path.
- [x] Local `plexamp.service` uses pinned Node and exposes port `32500` after claim.

#### EQ artifact acquisition — source/CI complete

- [x] Guarded `scripts/fetch-camilladsp-4.1.3.sh` added.
- [x] Official aarch64 release archive SHA and physically accepted executable SHA are both pinned and checked before promotion.
- [x] Temporary network probe independently confirmed archive `d9a170...aca5` extracts executable `e04c7a...edfa`; probe workflow was removed after evidence collection.

#### Spare-SD physical acceptance handoff

- [x] `docs/fresh-appliance-acceptance-runbook.md` rewritten for a **spare SD card** while the production card remains untouched.
- [x] Runbook covers fresh OS/source baseline, evidence capture, Direct install, exit `75` reboot resume, exit `76` Plex claim resume, independent bootstrap/application verifiers, NFC/AirPlay/alarm checks, guarded Camilla acquisition, EQ promotion, reboot, repeat-install and WU Settings commissioning.
- [x] Full source/CI handoff passed at checkpoint #25.
- [x] First real Debian 13/Trixie spare-SD Direct apply exposed inherited-system NFC `pip check` noise safely; scoped repair is checkpoint #26.
- [x] Subsequent physical attempts proved paired venvs, PN532 `0x24`, `CARD=Pro` without boot mutation, pinned Node/Plexamp acquisition, local Plexamp claim/resume, guarded NFC service, full host preflight, dashboard/kiosk, alarm-safe Direct routing, restricted helper packaging and guarded AirPlay integration. Exact attempts/blockers/repairs are preserved in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`.
- [x] The latest physical Direct attempt reached the final whole-appliance verifier; every check passed except two protected `/etc/sudoers.d` presence reads. The independent verifier was then corrected to inspect those two production-root paths through read-only `sudo -n`, with regression coverage green.
- [ ] Physical fresh Direct installation and verification — fast-forward the same spare SD to the **latest green branch head**, rerun idempotently and require the corrected final verifier/transaction to commit with root installer exit `0`.
- [ ] Physical PN532/NFC playback + dashboard-switch acceptance.
- [ ] Physical AirPlay/PlaybackCoordinator acceptance completion notes.
- [ ] Physical Music Master = 0% versus real scheduled-alarm isolation acceptance.
- [ ] Physical Direct-mode truthful **Install required** EQ UI acceptance.
- [ ] Physical historical-rainfall/WU source-workspace acceptance.
- [ ] Physical EQ installation, split-bus identity and audible Bass/Mid/Treble/bypass acceptance.
- [ ] Reboot acceptance with bootstrap/application/audio verifiers green.
- [ ] Repeat whole-appliance install with no ownership drift or renewed claim/reboot checkpoint.
- [ ] Real WU Settings/Test Connection acceptance.
- [ ] Commit a dated physical result/evidence document; only then close Phase 7.

**Phase 7 exit condition:** the spare-SD fresh appliance passes Direct → physical feature checks → EQ → reboot → repeat-install → real WU live/history commissioning with `verify-fresh-bootstrap.sh`, `verify-appliance.sh` and `scripts/audio/verify-audio.sh` green where applicable; dated evidence is committed. PR #2 remains Draft throughout.

## Phase 7 checkpoint record

- **#7 — package ownership, verifier and 2×2 lifecycle — PASS.** Tests #3003 / run `31355427351`, `3606f59`.
- **#8 — whole-appliance transaction primitives — PASS.** Tests #3013 / run `31356363970`, `bc7b1fe`. Historical Phase 3 read-only safety wording remains pinned.
- **#9 — guarded alarm-safe Direct component — PASS.** Tests #3025 / run `31356684593`, `b60b2b9`.
- **#10 — guarded restricted-helper packaging — PASS.** Tests #3037 / run `31357016840`, `8356e80`.
- **#11 — deterministic Shairport integration candidate — PASS.** Tests #3045 / run `31357275403`, `9795c0a`.
- **#12 — guarded AirPlay integration owner — PASS.** Tests #3072 / run `31426194328`, `9847c2e`.
- **#13 — guarded top-level apply boundary — PASS.** Tests #3083 / run `31443831762`, `f424479`.
- **#14 — guarded package and venv bootstrap owner — PASS.** Tests #3095 / `31355427351`; root ownership Tests #3099 / `31444400034`, `e106c47`.
- **#15 — guarded weather observation configuration owner — PASS.** Tests #3107 / run `31446688664`, `a52686d`.
- **#16 — shared dashboard owner, application transaction and promoted root apply — PASS.** Tests #3149 / run `31451271274`, `16f30fe`.
- **#17 — alternate-root whole-appliance rollback including fresh EQ — PASS.** Tests #3151 / run `31451366362`, `1a38270`.
- **#18 — first-install WU key-file contract — PASS.** Tests #3171 / run `31452097877`, `d131644`.
- **#19 — read-only real WU payload inspector — PASS.** Tests #3175 / run `31452388309`, `caa583d`.
- **#20 — fresh package/bootstrap preflight ordering — PASS.** Tests #3185 / run `31452688437`, `ac7cec8`.
- **#21 — WU Settings commissioning/write-only credential boundary — PASS.** Tests #3219 / run `31663696066`, `7a901109e996e8b4cb342e915a708b02ed745d28`.
- **#22 — guarded fresh-Pi I2C/PN532 hardware bootstrap foundation — PASS.** Tests #3237 / run `31664328721`, `d4570fb176013d7f96608ede96dd114510bf5d2a`.
- **#23 — pinned NFC runtime, paired venv bootstrap and guarded NFC service owner — PASS.** Tests #3263 / run `31664707020`, `63fa8825e4949d8805e43db5beb346c2a3c6b9b6`.
- **#24 — staged fresh-bootstrap preflight/root route with fail-closed player boundary — PASS.** Tests #3285 / run `31691861309`, `bf701e4ba256c45c0fd295f88026bfbe5a54ffc9`.
- **#25 — test-ready spare-SD fresh appliance: pinned Plexamp/Node, deterministic DAC Pro, fresh verifier, guarded Camilla fetcher and physical runbook — PASS.** Tests #3339 / run `31848016743`, `a3f05ebee67565cfaa5a6f7a605fc770a7b4fbd8`.
- **#26 — spare-SD Debian 13/Trixie first apply: real fresh-package boundary exposed and repaired — PASS (source/CI).** The first physical apply exposed unrelated inherited Debian metadata inside the system-site-packages NFC venv; the owner now scopes fail-closed dependency authority to the recursive vendored NFC graph while reporting unrelated host metadata informationally. Tests #3353 / run `31895570826`, `85db50016af086454208c2e0216f479d8b451790` passed. Subsequent physical progress moved far beyond this checkpoint and is recorded separately in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`; do not use #26 as the current Pi source target.
- **#27 — cached historical rainfall + Weather Observation Source workspace — PASS (source/CI).** Commit `28baf6fd91b4169813fbdbbe99d7b613fde8d151` adds the secret-free per-day WU rainfall cache, <=31-day missing-range batching, live-Today semantics, incomplete-total suppression, runtime Weather gauge integration, source/history-independent Settings layout and exact four-period control. Focused validation passed 14 rainfall/settings tests plus Python/JavaScript syntax checks; full Tests #3411 / run `31972466589` passed compile, JavaScript/page wiring and shell syntax, unit tests and diagnostics upload. Physical WU/history acceptance remains open.

No checkpoint is recorded as PASS until its exact tested state has passed full CI. Source/CI PASS does not substitute for the remaining physical gates.

### Phase 8 — cleanup and release preparation — **Not started**

- [ ] Preserve final Stage C archival reference/evidence before deleting obsolete working material.
- [ ] Mark retained Stage C transactional material historical/non-production.
- [ ] Retire orphan Settings presenter code after supported presenters freeze.
- [ ] Retire obsolete self-mutating Phase 2 workflows after preserving useful history; do not repair/reactivate them.
- [ ] Freeze the supported appliance/player/weather/install contract after Phase 7 physical acceptance.
- [ ] **Rewrite `README.md` for the finished appliance and installer before PR #2 is merged**: features/screenshots, hardware, Plexamp Headless, NFC, Direct/EQ, alarms, AirPlay, Weather Settings commissioning/history, installation, first-run setup, update/recovery and troubleshooting.
- [ ] Link installer/verifier/EQ repair/uninstall/recovery docs.
- [ ] Record final physical results/deviations.
- [ ] Run final CI/release review.
- [ ] Review PR #2 separately; do not make ready or merge without explicit owner approval. README/code/installer must describe the same release when the PR lands in `main`.

## Immediate next action

1. **Fast-forward `plexamp-test` to the latest green `feature/alarm-engine` head** (not checkpoint #26), verify branch identity and a clean tree, and preserve the existing physical evidence directory.
2. Rerun the same idempotent spare-SD `--fresh-bootstrap --audio direct` apply. Require the already-proven package/venv/hardware/Plexamp/NFC/application stages to reconverge and the corrected protected-sudoers final verifier to let the complete Direct transaction commit with root installer exit `0`. Stop on any new unexplained host-only blocker.
3. Complete Direct physical checks: Plexamp/NFC display handoff, AirPlay/PlaybackCoordinator, Music Master = 0% versus scheduled-alarm isolation and truthful Direct-mode EQ status.
4. Under **Settings → Weather → Observation source**, commission WU history, exercise Today / Last 7 days / Current month / Current year, verify cache-only second Current-year refresh and secret absence, and confirm live current observations remain healthy if history is unavailable.
5. Complete guarded EQ promotion, reboot and repeat-install acceptance, then commit the dated physical result document. Only then consider Phase 7 complete and move to the Phase 8 README/release pass.

## Roadmap maintenance discipline

- Material completion/block/scope change updates this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- Check this roadmap before reporting status.
- `docs/fresh-appliance-acceptance-runbook.md` must be updated whenever a source/physical change alters the current fresh-Pi procedure or acceptance evidence required.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap/runbook updates.
