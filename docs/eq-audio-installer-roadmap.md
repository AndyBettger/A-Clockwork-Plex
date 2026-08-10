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
- [x] Alarm-audio and Shairport-name helper packaging now share guarded `scripts/install-appliance-helpers.sh`, preserving the existing runtime implementations while adding exact rollback and project-user-aware sudo policy.
- [x] Deterministic Shairport integration renderer owns candidate config transformation for `acp_airplay`, lifecycle callbacks and metadata without altering receiver name/unrelated settings.
- [x] Safe root apply/rollback ownership for AirPlay lifecycle wrappers, metadata FIFO/service and Shairport integration through guarded `scripts/install-airplay-integration.sh`.
- [ ] Guarded root `--apply` with explicit confirmation and immediately repeated matching package/host/preflight gates.
- [ ] Root-owned package + venv + `requirements.txt` mutation transaction and explicit package rollback policy.
- [ ] Apply observation-provider config/secret-reference safely retaining Open-Meteo forecast config.
- [ ] Dashboard/kiosk integration under one root commit boundary and appliance verifier final gate.
- [ ] Deliberate non-production whole-appliance failure injection with exact restoration.
- [ ] Physical fresh Direct acceptance: Plexamp, alarm isolation, truthful **Install required** EQ UI.
- [ ] Physical fresh EQ acceptance: split-bus/EQ/alarm isolation and reboot.
- [ ] Deliberate real WU current/history payload inspection with station ID/runtime secret installed on host, never pasted into chat/config/browser.
- [ ] Whole-appliance fresh-Pi/repeatable-install acceptance.

**Exit condition:** source/read-only ownership, 2×2 lifecycle, transaction primitives, fresh Direct activation, restricted-helper packaging and guarded AirPlay integration are green. Remaining major gates are guarded top-level/package/weather/dashboard mutation/rollback, deliberate whole-appliance failure restoration and physical fresh-appliance acceptance.

#### Phase 7 checkpoint #7 — package ownership, verifier and 2×2 lifecycle — **PASS**

Package ownership and the single appliance verifier landed. The integrated matrix exposed only source/test contract mismatches: provider-name normalization, actual weather API payload shape, nested EQ payload, descriptive heredoc text confusing a static read-only assertion, a missing root-plan verifier command and one exact-spacing assertion. These were corrected without weakening safety. **Tests #3003 / run `31355427351` — PASS** at `3606f59`, including 1440 unit tests.

#### Phase 7 checkpoint #8 — whole-appliance transaction primitives — **PASS**

`installer/lib/transaction.sh` adds explicit stateless transaction-directory capture/restore primitives without enabling production installation. Regular file or deliberate absence is captured with SHA/mode/ownership metadata; symlinks/directories and duplicate capture are rejected; paths/services restore in reverse order; live service capture/restore is production-root-only; alternate-root file capture supports CI.

The first run, **Tests #3007 / run `31355957280`**, failed four new/roadmap tests only: three transaction tests omitted the library's explicit transaction-directory argument, and compacting the active roadmap had removed the historical `scripts/audio/preflight-eq.sh` safety-gate wording required by regression coverage. No production mutation occurred; compile/JS/page/shell syntax all passed. The tests were corrected to use the explicit stateless API and Phase 3 wording was restored. **Tests #3013 / run `31356363970` — PASS** at `bc7b1fe`.

#### Phase 7 checkpoint #9 — guarded alarm-safe Direct component — **PASS**

`scripts/audio/install-direct.sh` now owns the fresh Direct route activation rather than promoting the legacy shared-audio installer. It defaults to prepare-only, requires `--activate --confirm INSTALL-DIRECT-AUDIO`, validates exact alarm-safe source SHA `654ff170...`, captures the previous active route and production service state, stops the three audio/dashboard applications only for the route switch, restores their previous state and rolls back the previous route/service state on failure. Alternate-root activation and post-route failure injection prove exact rollback without touching live ALSA/systemd.

The first Direct CI, **Tests #3023 / run `31356602256`**, failed two new tests because the installer pre-created the transaction directory that `acp_transaction_begin` intentionally owns. It now creates a private parent and lets the transaction library create a child. No production mutation occurred. **Tests #3025 / run `31356684593` — PASS** at `b60b2b9`.

#### Phase 7 checkpoint #10 — guarded restricted-helper packaging — **PASS**

`scripts/install-appliance-helpers.sh` is now the guarded packaging/sudo-policy owner for the alarm-audio and Shairport receiver-name helpers. The actual helper algorithms remain in `scripts/a-clockwork-plex-alarm-audio-helper.sh` and `scripts/a-clockwork-plex-shairport-name.py`; the new installer does not fork those implementations. It defaults to prepare-only, requires `--activate --confirm INSTALL-APPLIANCE-HELPERS`, validates the selected project user, renders only the established restricted sudo actions, captures all four helper/policy targets and restores exact prior files/modes or absence if activation fails. Alternate-root tests prove normal install, wrong-token/invalid-user rejection and injected-failure rollback.

`installer/lib/components.sh` and the read-only component adapter report this shared guarded packaging owner for both helper components. **Tests #3037 / run `31357016840` — PASS** at `8356e80`. No production mutation occurred.

#### Phase 7 checkpoint #11 — deterministic Shairport integration candidate — **PASS**

`scripts/a-clockwork-plex-shairport-integration.py` produces a candidate Shairport configuration instead of asking an installer to edit the live file with ad-hoc `sed`/echo logic. It sets ALSA output to `acp_airplay`, installs the physically accepted active-state lifecycle callbacks, timeout/completion policy and metadata pipe settings, removes retired rehearsal settings, preserves receiver name/unrelated assignments and is byte-stable on repeat rendering. **Tests #3045 / run `31357275403` — PASS** at `9795c0a`. No live Shairport config or service was changed.

#### Phase 7 checkpoint #12 — guarded AirPlay integration owner — **PASS**

AirPlay lifecycle and metadata are now one guarded specialist boundary instead of two legacy immediate-mutating installers. `scripts/a-clockwork-plex-airplay-wrappers.py` renders the accepted START/END callback scripts from one source; the old `scripts/install-airplay-hooks.sh` delegates to that renderer rather than carrying a second copy of the runtime logic. START only publishes the AirPlay lifecycle event; END retains the accepted Shairport DBus Playing/Available checks and publishes pause/disconnect events to the existing PlaybackCoordinator authority.

`scripts/install-airplay-integration.sh` defaults to prepare-only and requires `--activate --confirm INSTALL-AIRPLAY-INTEGRATION`. It renders wrapper and Shairport candidates, validates the candidate through the Shairport parser **before** replacing the live config, preserves unrelated Shairport settings/receiver name and captured file metadata, owns the metadata FIFO/unit lifecycle, retires the obsolete play-end wrapper/sudo policy, captures Shairport service state and rolls back exact prior files/absence, FIFO mode/state and services on failure. Production validation is fixed to `/usr/bin/shairport-sync`; the validation-binary override and post-install failure injection are alternate-root test facilities only.

CI caught only test/fixture and mode-boundary defects while building this owner, with no production mutation: **Tests #3053 / run `31424266991`** exposed three stale assertions still inspecting the legacy installer after wrapper ownership moved; the corrected source-location coverage then passed at `0ee2507` / run `31424599120`. **Tests #3061 / run `31424865001`** exposed two file-mode parsing failures plus one diagnostics assertion; those were corrected at `5a3781a`. **Tests #3065 / run `31425471627`** then exposed only a test fixture that assumed `mkfifo(0620)` ignored process umask—the implementation had correctly restored the actually captured `0600`; the fixture now establishes `0620` explicitly and run `31425968201` passed.

Finally, both `airplay-hooks` and `airplay-metadata` component records/read-only adapter output now point at the shared guarded owner while root `install.sh` still does **not** invoke it. **Tests #3072 / run `31426194328` — PASS** at `9847c2e` after that ownership promotion.

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

1. Add the guarded top-level `install.sh --apply` confirmation/outer transaction boundary around the now-green Direct, AirPlay and restricted-helper owners, but keep production mutation refused while package/weather stages are incomplete.
2. Define root-owned package/venv/`requirements.txt` mutation and rollback policy before allowing package mutation.
3. Apply observation-provider config/secret reference safely while retaining Open-Meteo forecast configuration.
4. Integrate dashboard/kiosk and the final `scripts/verify-appliance.sh` gate under the same whole-appliance commit/rollback boundary.
5. Inject deliberate alternate-root whole-appliance failures and prove exact restoration before any fresh-Pi physical rehearsal.
6. Only then run physical fresh Direct, fresh EQ and real WU acceptance.

No local weather caching/fan-out server is part of the design.

## Roadmap maintenance discipline

- Material completion/block/scope change updates this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- Check this roadmap before reporting status.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap updates.
