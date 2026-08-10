# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 10 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

The exact detailed roadmap that carried the project from the pre-EQ baseline through Phase 7 source checkpoint #6 is preserved verbatim at:

`docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`

That archive retains the detailed physical Phase 4–6 acceptance evidence, Stage C history, failure journals, checksums, CI checkpoints and prior decision trail. This active file is now the current implementation/acceptance authority so routine roadmap maintenance remains readable; the archive is historical evidence and should not be edited to rewrite past results.

## Settled invariants

### Audio semantics

- Scheduled alarms **bypass Music Master**.
- Visible copy must never imply Music Master affects alarm audio.
- EQ-capable music path: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm path: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/tone processing → final limiter → DAC.
- Direct fresh-appliance audio preserves the same ownership principle: Plexamp/AirPlay remain under Music Master while alarm joins the DAC-facing mix independently.
- Presentation-only Settings changes must not alter runtime/audio routing.

### Accepted identities

| Identity | SHA-256 / value | Meaning |
|---|---|---|
| Historical Phase 6 direct route | `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` | Exact rollback target for the physically accepted bedroom-Pi Phase 6 lifecycle; **not** the future fresh Direct profile |
| Alarm-safe Direct route | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` | Fresh-appliance Direct profile and managed no-DSP failback route; alarm bypasses Music Master |
| EQ split-bus route | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` | Accepted active EQ route |
| Accepted +2/0/+2 Camilla config | `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578` | Physically accepted fixed-headroom configuration |
| CamillaDSP | `4.1.3`, SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` | Verified aarch64 artifact; must not be silently substituted/downloaded |

### Weather semantics

- Open-Meteo remains the forecast provider.
- Current observations may be Ecowitt custom push or Weather Underground PWS.
- No local weather cache/fan-out server is part of the design.
- Each Weather Underground appliance polls the upstream PWS independently.
- The WU API key is a server-environment secret, not normal Settings/config/browser data.
- Both observation providers write through one shared observation store, including local pressure-history accumulation.
- WU historical pressure aggregates are not reinterpreted as instantaneous barometer samples unless a real payload later proves a trustworthy like-for-like field.

## Phase status

### Phase 0 — roadmap and baseline — **Complete**

Direct audio was recovered, baseline state captured and the implementation roadmap established.

### Phase 1 — artifact inventory — **Complete**

Exact audio contract, managed-file inventory and accepted route identities were documented.

### Phase 2 — standalone EQ lifecycle — **Complete**

Guarded install, verify, repair and uninstall entrypoints plus shared libraries are accepted under non-production tests.

### Phase 3 — non-production/read-only validation — **Complete**

Real-Pi prepare-only/preflight proved exact before/after production-state equality with no mutation.

### Phase 4 — bedroom-Pi EQ installation — **Complete**

The split-bus graph was installed on the real Pi, verified and physically audible.

### Phase 5 — feature/interface acceptance — **Complete**

Physically accepted: Plexamp/AirPlay music routing, Bass/Mid/Treble, EQ persistence/bypass/neutral, fixed `-6.5 dB` reserve, Music Master behaviour, alarm independence and Maximum Alarm Volume, Output Levels UI, NFC playback/handoff, final `-1 dB` limiter protection and truthful EQ UI.

### Phase 6 — failure/reboot/uninstall acceptance — **Complete**

The complete real-Pi lifecycle passed:

`install → reboot → controlled CamillaDSP failure → automatic alarm-safe direct failback → supported repair → explicit uninstall → exact historical direct reboot → reinstall`

Accepted results include:

- reboot persistence of split-bus, `snd_aloop` and saved EQ;
- corrected deterministic CamillaDSP failure handling with `Restart=no` and no failback ordering deadlock;
- automatic failback kept Plexamp/AirPlay/dashboard usable without manual recovery;
- UI distinguished **Direct failback**, **Install required** and active EQ truthfully;
- explicit uninstall restored exact historical direct route `08d00093...` and removed supported EQ assets;
- direct-only reboot remained usable;
- reinstall restored split-bus, saved `+2 / 0 / +2`, fixed headroom and audible Plexamp/EQ.

The bedroom Pi remains in this healthy accepted EQ-capable state unless a later physical gate explicitly changes it.

### Phase 7 — full appliance installer integration — **In progress**

Completed source/read-only work:

- [x] Root `install.sh` exists as a deliberately plan-only whole-appliance orchestrator; `--apply` remains blocked.
- [x] Repeatable `--audio direct|eq`, `--weather-observations ecowitt-push|weather-underground`, `--project-user` and non-interactive profile choices exist.
- [x] Alarm-safe Direct profile is materialised and checksum-validated at `654ff170...`.
- [x] Standalone EQ first-install baseline bridge supports explicit `--baseline alarm-safe-direct` while preserving historical `phase6-direct` default behaviour.
- [x] Exact uninstall continues to restore the route genuinely captured before EQ activation.
- [x] Weather Underground current-observation provider, polling lifecycle and health endpoint exist.
- [x] Ecowitt push and WU polling share one observation-state/history authority.
- [x] Unified Settings backend/browser controls support observation-provider choice without exposing the WU API key.
- [x] Open-Meteo forecast remains independent.
- [x] Remaining specialist component inventory and read-only adapter checks are explicit.
- [x] Fresh-Pi prerequisite gate exists for platform/user/hardware/profile assumptions.
- [x] Package/artifact ownership is defined and a read-only package checker exists.
- [x] Plexamp Headless is truthfully classified as an external prerequisite rather than an unsupported installer-owned download.
- [x] Appliance-level profile-aware post-install verifier exists and remains read-only.
- [x] Complete rooted/non-production **Direct/EQ × Ecowitt/WU 2×2 profile matrix** passes, including real rooted EQ install/uninstall lifecycle and exact alarm-safe Direct restoration.
- [ ] Design and implement guarded root `--apply` with explicit confirmation and matching host/package/preflight gates.
- [ ] Give legacy immediate-mutating specialist installers a safe root-level apply/rollback contract without duplicating their implementation logic.
- [ ] Implement root-owned package + venv + `requirements.txt` mutation transaction and rollback.
- [ ] Establish alarm-safe Direct as the common fresh-build audio baseline, then optionally call accepted standalone EQ activation.
- [ ] Apply observation-provider configuration/secret reference safely while retaining Open-Meteo forecast config.
- [ ] Finish root-level dashboard/kiosk orchestration and run the appliance verifier as the commit gate.
- [ ] Add deliberate non-production failure injection/rollback coverage for guarded root activation.
- [ ] Physically accept a fresh Direct appliance build, including audible Plexamp/alarm isolation and truthful **Install required** EQ UI.
- [ ] Physically accept a fresh EQ-capable appliance build, including split-bus/EQ/alarm isolation and reboot.
- [ ] Inspect the real Weather Underground station current/history payload only when station ID/runtime credentials are deliberately available; do not put the API key in chat/config/browser.
- [ ] Complete whole-appliance fresh-Pi acceptance for supported profile combinations/repeatable installs.

**Exit condition:** source/read-only ownership, post-install verification and the complete non-production 2×2 profile lifecycle are green. Remaining major gates are guarded top-level activation/rollback and physical fresh-appliance acceptance.

#### Phase 7 source checkpoint #7 — package ownership, verifier and complete 2×2 lifecycle

Package ownership now explicitly covers the root-installer Debian/Raspberry Pi OS package set (`git`, `curl`, `python3`, `python3-venv`, `alsa-utils`, `shairport-sync`, `chromium`), future venv/`requirements.txt` ownership, external Plexamp Headless prerequisite and pinned CamillaDSP artifact. The checker is read-only and distinguishes package availability/state without running apt/pip/download mutation.

`scripts/verify-appliance.sh` is now the single profile-aware read-only end-state verifier. It checks common dashboard/AirPlay/helper/Shairport/kiosk integration, exact Direct/EQ profile state, selected weather configuration, Open-Meteo retention, secret hygiene and — on a real root — service/API truthfulness. Alternate-root mode allows the same contract to be exercised in CI without touching system state.

`tests/test_appliance_profile_matrix.py` now exercises all four Direct/EQ × Ecowitt/WU combinations through root planning, package/preflight contracts, materialised common integration state and the whole-appliance verifier. EQ cases execute the real rooted standalone installer with `--baseline alarm-safe-direct`, verify the resulting appliance, uninstall and require exact return to `654ff170...`.

The first integrated matrix/plan CI passes exposed only source/test contract defects, not a production mutation: provider-name normalization (`ecowitt_push` versus `ecowitt-push`), the actual top-level shape of `/api/weather/observations`, the nested `eq` object returned by `/api/audio/eq`, a static test falsely reading descriptive heredoc text as executable `pip install`, one missing root-plan verifier command, and a stale exact-spacing assertion. These were corrected without weakening the read-only boundary.

CI sequence:

- `ce4f29c` / Tests #2993: first complete matrix attempt, failed and exposed integration-contract mismatches.
- `7a8cd27` / Tests #2995 / run `31354009373`: reduced/clarified failures; eight source/test contract failures remained.
- `908f560`, `a07fb90`, `b86ab4d`: verifier normalization, command-aware package safety test and explicit profile-matched verifier plan.
- `b86ab4d` / Tests #3001: only one stale project-user spacing assertion remained.
- `3606f59` / **Tests #3003 / run `31355427351` — PASS**: compile, JS/page wiring, shell syntax and **1440 unit tests** all green, including the complete 2×2 profile matrix.

No Phase 7 source checkpoint has been deployed to the bedroom Pi.

### Phase 8 — cleanup and release preparation — **Not started**

- [ ] Record an archival reference for the final Stage C branch/head evidence before removing historical material.
- [ ] Delete/retire obsolete Stage C terminal-install working material after archival reference is preserved.
- [ ] Mark retained Stage C transactional material historical/non-production where needed.
- [ ] Retire orphan Settings presentation code once supported presenters are frozen.
- [ ] Retire obsolete self-mutating Phase 2 workflows after preserving useful historical evidence; do not repair/reactivate them.
- [ ] Update `README.md` for Direct/EQ appliance profiles, weather observation choices and supported install/verify/repair/uninstall commands.
- [ ] Link full installer, verifier, EQ repair/uninstall and recovery documentation.
- [ ] Record final physical results and accepted deviations.
- [ ] Review PR #2 separately; do not make ready or merge without explicit approval.

**Exit condition:** a future owner can identify and rebuild the supported appliance path without reconstructing project history.

## Immediate next action

The bedroom Pi remains untouched in the healthy accepted Phase 6 EQ-capable split-bus state while Phase 7 source work continues.

Next engineering sequence:

1. design the guarded top-level `--apply` transaction with a new explicit confirmation token and mandatory matching host/package/preflight checks;
2. define safe apply/rollback ownership for the legacy specialist component scripts instead of blindly chaining immediate mutations;
3. implement root-owned package/venv mutation with captured pre-state and deterministic rollback;
4. establish alarm-safe Direct `654ff170...` as the fresh-build audio baseline, optionally hand off to standalone EQ using `--baseline alarm-safe-direct`;
5. apply selected weather observation config/secret reference while preserving Open-Meteo forecast, then dashboard/kiosk integration;
6. make `scripts/verify-appliance.sh` the final commit gate and roll back on a failed post-install verification;
7. exercise failure injection and exact restoration in non-production before any fresh-Pi physical rehearsal;
8. only then schedule physical Direct/EQ fresh-build acceptance and later deliberate live-WU payload inspection.

No new local weather caching/fan-out server is part of the design.

## Roadmap maintenance discipline

This file remains part of the implementation workflow.

- Any material completion, blocker or scope/architecture change updates this file in the same change or immediately afterward.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result rather than silently retried away.
- Any physical Pi mutation records route/checksum, relevant service state and rollback outcome.
- Check this roadmap before reporting project status in chat.
- PR #2 remains Draft and must not be made ready or merged without explicit owner approval.
- The owner should not need to prompt for routine roadmap updates.
