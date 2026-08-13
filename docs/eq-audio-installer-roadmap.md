# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 13 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed physical/CI history through Phase 7 checkpoint #6 is preserved verbatim in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. This file is the active implementation/acceptance authority; later checkpoints are retained below in compact form.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Fresh Direct: Plexamp/AirPlay remain under Music Master while alarm joins the DAC-facing mix independently.
- Presentation-only Settings changes do not alter runtime/audio routing.
- `scripts/audio/preflight-eq.sh` remains the historical **read-only bedroom-Pi validation gate**. **No bedroom-Pi installation** was permitted until that gate passed; do not replace that evidence with a mutating rehearsal.
- Do not run the old bare `scripts/install-master-eq.sh` production path.

| Identity | Accepted value |
|---|---|
| Historical Phase 6 direct rollback | `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` |
| Fresh alarm-safe Direct / managed failback | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| +2/0/+2 Camilla config | `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578` |
| CamillaDSP | `4.1.3`, SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |

The historical `08d00093...` route remains the exact rollback identity for the physically accepted bedroom-Pi Phase 6 lifecycle. It is **not** the future fresh Direct profile because that historical graph routes alarm through Music Master.

### Weather

- Open-Meteo remains the forecast provider.
- Current observations may be Ecowitt custom push or Weather Underground PWS.
- No local weather cache/fan-out server is part of the design; each WU appliance polls upstream independently.
- WU provider/station configuration belongs in **Settings → Weather**, not in normal appliance-install commissioning.
- The WU API key is **write-only commissioning data**: it may be typed into the local Settings page and submitted to the dedicated credential endpoint, but it is never returned to the browser, stored in browser storage, written to `config.json`, placed in argv or logged.
- Persistent WU secret storage remains root-owned `/etc/default/a-clockwork-plex-weather` as `WEATHER_UNDERGROUND_API_KEY`, mode `0600`; the dashboard service consumes that EnvironmentFile on boot.
- A restricted helper receives new key material on **stdin**, preserves unrelated environment-file lines and owns set/remove only. After a successful helper write/remove, the running dashboard updates its in-memory environment so no service restart is required.
- Both observation providers write through one shared observation store/current/extrema/local-pressure-history authority.
- WU historical aggregates are not fabricated into instantaneous barometer samples without a real-payload contract proving that is sound.

### Player/runtime direction

- **Plexamp Headless remains the A-Clockwork-Plex player runtime for this release.** Caldera migration is out of scope for Phase 7 because it does not provide the local Plexamp browsing interface this appliance uses.
- Full-appliance bootstrap must install/pin the compatible Plexamp Headless runtime rather than treating it as a preinstalled external package.
- The production Plexamp installer must not depend on a mutable community `curl | bash` installer or an unverified `latest` archive; exact compatibility archive identity/checksum and Node runtime strategy must be pinned first.
- Any later player-runtime migration is a separate roadmap project, not part of WU commissioning.

### Fresh-Pi hardware/bootstrap direction

- The fresh-appliance installer may use the exact bedroom Pi/HAT/display hardware only after the accepted SD card has a verified off-device full image and has been replaced by a genuinely fresh Raspberry Pi OS image.
- Global OS upgrade, `rpi-update`, Pi EEPROM/bootloader update and external hardware firmware update are outside appliance bootstrap because rewriting the SD-card image would not restore them.
- Known NFC hardware contract is PN532 on I2C bus `1`, address `0x24`; project user needs `i2c`, `gpio` and `spi` groups.
- Accepted DAC runtime identity is ALSA `CARD=Pro`, but the exact physical DAC HAT model/boot `dtoverlay` contract has **not** yet been captured. The installer must fail closed rather than guess it.
- A bootstrap-required reboot is an explicit stop/resume state, never an automatic reboot side effect.
- Detailed staged ownership is recorded in `docs/fresh-pi-bootstrap-ownership-design.md`.

## Phase status

### Phase 0 — roadmap and baseline — **Complete**
Direct audio recovered and baseline/roadmap established.

### Phase 1 — artifact inventory — **Complete**
Exact audio contract, route identities and managed-file inventory established.

### Phase 2 — standalone EQ lifecycle — **Complete**
Guarded install/verify/repair/uninstall lifecycle accepted under non-production tests.

### Phase 3 — non-production/read-only validation — **Complete**
`scripts/audio/preflight-eq.sh` proved exact before/after state equality before any bedroom-Pi installation was permitted.

### Phase 4 — bedroom-Pi EQ installation — **Complete**
Split-bus installed, verified and physically audible.

### Phase 5 — feature/interface acceptance — **Complete**
Plexamp/AirPlay routing, EQ, fixed headroom, Music Master/alarm isolation, Maximum Alarm Volume, Output Levels, NFC/handoff, limiter protection and truthful UI physically accepted.

### Phase 6 — failure/reboot/uninstall acceptance — **Complete**
Real lifecycle passed: install → reboot → controlled Camilla failure → automatic alarm-safe failback → repair → explicit uninstall → direct-only reboot → reinstall. Exact historical uninstall returned `08d00093...`; reinstall restored split-bus and saved `+2 / 0 / +2`.

### Phase 7 — full appliance installer integration — **In progress**

Completed and previously green source/CI work:

- [x] Guarded root plan/apply boundary and single application transaction.
- [x] Direct/EQ × Ecowitt/WU profile matrix and alarm-safe Direct owner.
- [x] Package/venv bootstrap, weather owner, dashboard/kiosk owner, helper owner and AirPlay owner.
- [x] Exact application rollback including fresh-EQ unwind-before-outer-restore.
- [x] Profile-aware final verifier and split pre/post-package fresh-host preflight.
- [x] WU current-observation poller/health/shared store plus read-only current/history payload inspector.
- [x] WU key-file contract for the existing installer-driven compatibility path, with secret excluded from config/argv/output.
- [x] Fresh-appliance physical acceptance runbook prepared.

WU Settings commissioning:

- [x] Dedicated write-only WU credential manager/API added outside the revisioned `/api/settings` transaction.
- [x] Restricted `a-clockwork-plex-weather-secret` helper added; set receives the secret on stdin and remove carries no secret material.
- [x] Helper packaging/sudo policy added to `scripts/install-appliance-helpers.sh` and included in outer application rollback capture.
- [x] Settings Weather presenter adds Set/Replace key, Remove key, credential status and Test connection controls without a `data-setting-path` secret field or browser storage.
- [x] Successful set/remove updates the running dashboard environment and wakes the observation worker without restarting the dashboard service.
- [x] Test Connection uses the existing WU observation service/parser and returns only sanitized station/status/timestamp information.
- [x] WU commissioning source tests and full CI passed at checkpoint #21.
- [ ] Real WU acceptance: select provider/station in Settings, enter the API key locally, run Test connection, verify live observations/health, and confirm the secret never appears in Settings/config/log output.

Fresh-Pi bootstrap ownership work:

- [x] Additive package owner expanded with `i2c-tools`, `python3-lgpio` and `raspi-config`; no global upgrade/firmware path added.
- [x] Guarded `scripts/install-platform-hardware.sh` source owner added: prepare-only default, explicit confirmation, I2C enable, hardware groups, PN532 `0x24` verification and explicit reboot-resume result.
- [x] Hardware owner refuses to invent a DAC overlay; missing `CARD=Pro` reports `DAC-COMMISSIONING-REQUIRED` / `NO-GUESSED-OVERLAY`.
- [x] `docs/fresh-pi-bootstrap-ownership-design.md` records the staged fresh-OS → complete-appliance target and authority boundaries.
- [ ] Full CI must pass before this source slice receives checkpoint #22.
- [ ] Capture/pin exact accepted DAC HAT identity and boot overlay from the accepted bedroom image before wipe/reimage; then promote DAC configuration into the guarded hardware owner.
- [ ] Pin exact Plexamp Headless compatibility archive checksum/download contract and reviewed Node runtime strategy.
- [ ] Installer owns pinned compatible **Plexamp Headless** runtime plus account/player commissioning boundary.
- [ ] Installer owns the Plexamp NFC Listener without importing its legacy kiosk/AirPlay ownership.
- [ ] Move current preflight requirements to the correct sides of package/hardware/Plexamp/NFC bootstrap and wire staged reboot/resume through root `install.sh`.
- [ ] Final verifier expands to cover owned Plexamp runtime, PN532/I2C, DAC boot identity and NFC listener.
- [ ] Fresh-appliance runbook safety moves from hostname-only prohibition to a verified off-device SD-image/reimage guard so the exact bedroom hardware can be used safely after its accepted card is backed up.
- [ ] Physical fresh Direct acceptance: Plexamp, alarm isolation and truthful **Install required** EQ UI.
- [ ] Physical fresh EQ acceptance: split-bus/EQ/alarm isolation and reboot.
- [ ] Repeat whole-appliance install and require zero ownership drift.
- [ ] Commit dated physical result/evidence before Phase 7 closure.

**Phase 7 exit condition:** WU Settings commissioning is source/CI and physically accepted; the installer owns all software/hardware bootstrap required to turn a fresh Raspberry Pi OS installation into the complete appliance; Direct and EQ physical fresh installs pass; reboot and repeat-install acceptance pass; final verifier is green. PR #2 remains Draft throughout.

## Phase 7 checkpoint record

- **#7 — package ownership, verifier and 2×2 lifecycle — PASS.** Tests #3003 / run `31355427351`, `3606f59`.
- **#8 — whole-appliance transaction primitives — PASS.** Tests #3013 / run `31356363970`, `bc7b1fe`. This checkpoint also permanently pins the Phase 3 `scripts/audio/preflight-eq.sh` read-only safety wording.
- **#9 — guarded alarm-safe Direct component — PASS.** Tests #3025 / run `31356684593`, `b60b2b9`.
- **#10 — guarded restricted-helper packaging — PASS.** Tests #3037 / run `31357016840`, `8356e80`.
- **#11 — deterministic Shairport integration candidate — PASS.** Tests #3045 / run `31357275403`, `9795c0a`.
- **#12 — guarded AirPlay integration owner — PASS.** Final ownership promotion Tests #3072 / run `31426194328`, `9847c2e`.
- **#13 — guarded top-level apply boundary — PASS.** Tests #3083 / run `31443831762`, `f424479`.
- **#14 — guarded package and venv bootstrap owner — PASS.** Package baseline Tests #3095 / run `31444251583`, `56dff3d`; root ownership promotion Tests #3099 / run `31444400034`, `e106c47`.
- **#15 — guarded weather observation configuration owner — PASS.** Tests #3107 / run `31446688664`, `a52686d`.
- **#16 — shared dashboard owner, application transaction and promoted root apply — PASS.** Tests #3149 / run `31451271274`, `16f30fe`.
- **#17 — alternate-root whole-appliance rollback including fresh EQ — PASS.** Tests #3151 / run `31451366362`, `1a38270`.
- **#18 — first-install WU key-file contract — PASS.** Tests #3171 / run `31452097877`, `d131644`.
- **#19 — read-only real WU payload inspector — PASS.** Tests #3175 / run `31452388309`, `caa583d`.
- **#20 — fresh package/bootstrap preflight ordering — PASS.** Tests #3185 / run `31452688437`, `ac7cec8`.
- **#21 — WU Settings commissioning and write-only credential boundary — PASS.** Tests #3219 / run `31663696066`, `7a901109e996e8b4cb342e915a708b02ed745d28`.

No Phase 7 checkpoint after #21 is recorded as PASS until its exact tested state has passed full CI.

### Phase 8 — cleanup and release preparation — **Not started**

- [ ] Preserve final Stage C archival reference/evidence before deleting obsolete working material.
- [ ] Mark retained Stage C transactional material historical/non-production.
- [ ] Retire orphan Settings presenter code after supported presenters freeze.
- [ ] Retire obsolete self-mutating Phase 2 workflows after preserving useful history; do not repair/reactivate them.
- [ ] Freeze the supported appliance/player/weather/install contract after Phase 7 physical acceptance.
- [ ] **Rewrite `README.md` for the finished appliance and installer before PR #2 is merged**: features/screenshots, hardware, Plexamp Headless, NFC, Direct/EQ, alarms, AirPlay, Weather Settings commissioning, installation, first-run setup, update/recovery and troubleshooting.
- [ ] Link installer/verifier/EQ repair/uninstall/recovery docs.
- [ ] Record final physical results/deviations.
- [ ] Run final CI/release review.
- [ ] Review PR #2 separately; do not make ready or merge without explicit owner approval. README/code/installer must describe the same release when the PR lands in `main`.

## Immediate next action

1. Obtain full green CI for the fresh-Pi hardware/package source slice; if exact-head green, record checkpoint #22.
2. Continue source work while physical access is pending: pin Plexamp runtime acquisition/Node identity and build the NFC-only runtime owner without importing the old NFC setup script's kiosk/AirPlay behaviour.
3. Before wiping the accepted bedroom card, capture its exact DAC HAT/boot-overlay identity and run the existing read-only Plexamp upgrade evidence collector; then take/verify the off-device full SD image.
4. Perform real WU commissioning acceptance from the local Settings page using the real station ID/API key on the appliance only; do not paste the key into chat or config.
5. Once complete bootstrap ownership is green, install fresh Raspberry Pi OS on the same target hardware and execute Direct → EQ → reboot → WU → repeat-install acceptance.
6. Commit the dated physical result document; only then consider Phase 7 closure and the Phase 8 README/release pass.

No local weather caching/fan-out server is part of the design.

## Roadmap maintenance discipline

- Material completion/block/scope change updates this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- Check this roadmap before reporting status.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap updates.
