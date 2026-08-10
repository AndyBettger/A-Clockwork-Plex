# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 10 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed physical/CI history through Phase 7 checkpoint #6 is preserved verbatim in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. That archive retains failure journals, Stage C history, physical evidence and prior decisions; do not rewrite it. This file is the active implementation/acceptance authority.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Fresh Direct: Plexamp/AirPlay remain under Music Master while alarm joins the DAC-facing mix independently.
- Presentation-only Settings changes do not alter runtime/audio routing.

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
- WU API key is a server-environment secret, never normal Settings/config/browser data.
- Both providers write through one shared observation store/current/extrema/local-pressure-history authority.
- WU historical aggregates are not fabricated into instantaneous barometer samples without a real-payload contract proving that is sound.

## Phase status

### Phase 0 — roadmap and baseline — **Complete**
Direct audio recovered and baseline/roadmap established.

### Phase 1 — artifact inventory — **Complete**
Exact audio contract, route identities and managed-file inventory established.

### Phase 2 — standalone EQ lifecycle — **Complete**
Guarded install/verify/repair/uninstall lifecycle accepted under non-production tests.

### Phase 3 — non-production/read-only validation — **Complete**
`scripts/audio/preflight-eq.sh` was the **read-only bedroom-Pi validation gate** and proved exact before/after state equality. **No bedroom-Pi installation** was permitted before it passed.

### Phase 4 — bedroom-Pi EQ installation — **Complete**
Split-bus installed, verified and physically audible.

### Phase 5 — feature/interface acceptance — **Complete**
Plexamp/AirPlay routing, EQ, fixed headroom, Music Master/alarm isolation, Maximum Alarm Volume, Output Levels, NFC/handoff, limiter protection and truthful UI physically accepted.

### Phase 6 — failure/reboot/uninstall acceptance — **Complete**
Real lifecycle passed: install → reboot → controlled Camilla failure → automatic alarm-safe failback → repair → explicit uninstall → direct-only reboot → reinstall. Exact historical uninstall returned `08d00093...`; reinstall restored split-bus and saved `+2 / 0 / +2`. Bedroom Pi remains in the healthy accepted EQ-capable state.

### Phase 7 — full appliance installer integration — **In progress**

Completed source/read-only work:

- [x] Root `install.sh` plan-only orchestrator; production `--apply` remains blocked.
- [x] Repeatable Direct/EQ, Ecowitt/WU, project-user and non-interactive profile choices.
- [x] Alarm-safe Direct profile at exact `654ff170...`.
- [x] EQ baseline bridge `--baseline phase6-direct|alarm-safe-direct`; historical default preserved.
- [x] Exact uninstall restores the route genuinely captured before EQ activation.
- [x] WU current-observation provider/poller/health plus shared Ecowitt/WU observation store.
- [x] Unified Settings backend/browser provider controls with no WU API-key field.
- [x] Open-Meteo forecast remains independent.
- [x] Specialist component inventory/read-only adapters and fresh-Pi prerequisite gate.
- [x] Package/artifact ownership plus read-only package checker; Plexamp Headless classified as external prerequisite.
- [x] Profile-aware appliance post-install verifier.
- [x] Complete rooted/non-production **Direct/EQ × Ecowitt/WU 2×2 profile matrix**, including real rooted EQ install/uninstall and exact `654ff170...` restoration.
- [x] Whole-appliance transaction primitives: explicit file/absence capture, metadata, reverse restore, production-root service state capture/restore and alternate-root testability.
- [x] Guarded alarm-safe Direct activation owner `scripts/audio/install-direct.sh`, with prepare-only default, explicit confirmation, exact checksum install and rollback/failure-injection coverage.
- [ ] Guarded root `--apply` with explicit confirmation and immediately repeated matching package/host/preflight gates.
- [ ] Safe root apply/rollback ownership for legacy immediate-mutating specialist installers.
- [ ] Root-owned package + venv + `requirements.txt` mutation transaction and explicit package rollback policy.
- [ ] Apply observation-provider config/secret-reference safely retaining Open-Meteo forecast config.
- [ ] Dashboard/kiosk integration under one root commit boundary and appliance verifier final gate.
- [ ] Deliberate non-production whole-appliance failure injection with exact restoration.
- [ ] Physical fresh Direct acceptance: Plexamp, alarm isolation, truthful **Install required** EQ UI.
- [ ] Physical fresh EQ acceptance: split-bus/EQ/alarm isolation and reboot.
- [ ] Deliberate real WU current/history payload inspection with station ID/runtime secret installed on host, never pasted into chat/config/browser.
- [ ] Whole-appliance fresh-Pi/repeatable-install acceptance.

**Exit condition:** source/read-only ownership, 2×2 lifecycle, transaction primitives and the fresh Direct component owner are green. Remaining major gates are guarded whole-appliance mutation/rollback and physical fresh-appliance acceptance.

#### Phase 7 checkpoint #7 — package ownership, verifier and 2×2 lifecycle — **PASS**

Package ownership and the single appliance verifier landed. The integrated matrix exposed only source/test contract mismatches: provider-name normalization, actual weather API payload shape, nested EQ payload, descriptive heredoc text confusing a static read-only assertion, a missing root-plan verifier command and one exact-spacing assertion. These were corrected without weakening safety. **Tests #3003 / run `31355427351` — PASS** at `3606f59`, including 1440 unit tests.

#### Phase 7 checkpoint #8 — whole-appliance transaction primitives — **PASS**

`installer/lib/transaction.sh` adds explicit stateless transaction-directory capture/restore primitives without enabling production installation. Regular file or deliberate absence is captured with SHA/mode/ownership metadata; symlinks/directories and duplicate capture are rejected; paths/services restore in reverse order; live service capture/restore is production-root-only; alternate-root file capture supports CI.

The first run, **Tests #3007 / run `31355957280`**, failed four new/roadmap tests only: three transaction tests omitted the library's explicit transaction-directory argument, and compacting the active roadmap had removed the historical `scripts/audio/preflight-eq.sh` safety-gate wording required by regression coverage. No production mutation occurred; compile/JS/page/shell syntax all passed. The tests were corrected to use the explicit stateless API and Phase 3 wording was restored. **Tests #3013 / run `31356363970` — PASS** at `bc7b1fe`.

#### Phase 7 checkpoint #9 — guarded alarm-safe Direct component — **PASS**

`scripts/audio/install-direct.sh` now owns the fresh Direct route activation rather than promoting the legacy shared-audio installer. It defaults to prepare-only, requires `--activate --confirm INSTALL-DIRECT-AUDIO`, validates the exact alarm-safe source SHA `654ff170...`, captures the previous active route and production service state, stops the three audio/dashboard applications only for the route switch, restores their previous state, and rolls back the previous route/service state if activation fails. Alternate-root activation and a non-production post-route failure injection prove exact rollback without touching live ALSA/systemd.

The first CI after adding the Direct installer, **Tests #3023 / run `31356602256`**, failed two new tests because the installer created its transaction directory with `mktemp -d` and then correctly called `acp_transaction_begin`, whose contract requires the transaction directory itself not to exist yet. The installer now creates a private temporary parent and lets the transaction library create a child directory. No production mutation occurred. **Tests #3025 / run `31356684593` — PASS** at `b60b2b9`, including the new prepare/activation/wrong-token/failure-rollback Direct tests.

No Phase 7 checkpoint has been deployed to the bedroom Pi.

### Phase 8 — cleanup and release preparation — **Not started**

- [ ] Preserve final Stage C archival reference/evidence before deleting obsolete working material.
- [ ] Mark retained Stage C transactional material historical/non-production.
- [ ] Retire orphan Settings presenter code after supported presenters freeze.
- [ ] Retire obsolete self-mutating Phase 2 workflows after preserving useful history; do not repair/reactivate them.
- [ ] Update README for appliance profiles, weather choices and supported lifecycle commands.
- [ ] Link installer/verifier/EQ repair/uninstall/recovery docs.
- [ ] Record final physical results/deviations.
- [ ] Review PR #2 separately; do not make ready or merge without explicit approval.

## Immediate next action

Bedroom Pi stays untouched in healthy Phase 6 EQ-capable split-bus state.

1. Add the guarded top-level apply confirmation/transaction boundary around the green component infrastructure while still refusing incomplete production stages.
2. Give the four legacy immediate-mutating specialist installers safe prepare/apply/rollback boundaries without duplicating subsystem logic.
3. Define package/venv mutation and rollback policy before allowing package mutation.
4. Root orchestration should establish Direct via `scripts/audio/install-direct.sh`, then optionally hand off to standalone EQ using `--baseline alarm-safe-direct`.
5. Apply weather-provider config/secret reference while retaining Open-Meteo, then dashboard/kiosk.
6. Treat `scripts/verify-appliance.sh` failure as install failure and reverse rollback.
7. Inject failures in non-production and prove restoration before any fresh-Pi physical rehearsal.

No local weather caching/fan-out server is part of the design.

## Roadmap maintenance discipline

- Material completion/block/scope change updates this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- Check this roadmap before reporting status.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap updates.
