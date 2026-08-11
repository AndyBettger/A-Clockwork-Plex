# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 11 August 2026  
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

- [x] Root `install.sh` remains plan-only by default; guarded production apply now exists behind exact confirmation and matching preflight gates.
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
- [x] Guarded root `--apply` establishes the package/venv baseline, repeats full host preflight and delegates all application mutation to one guarded application transaction.
- [x] Guarded package + venv + `requirements.txt` bootstrap owner with explicit additive-package rollback policy and exact staged-venv restoration.
- [x] Apply observation-provider config/secret-reference safely retaining Open-Meteo forecast config.
- [x] Dashboard service/kiosk integration share one guarded owner inside the application commit boundary; appliance verifier is the final commit gate.
- [x] Deliberate non-production whole-appliance failure injection proves exact restoration for Direct and fresh-EQ paths, including EQ-uninstall-before-outer-restore ordering.
- [x] Fresh WU install uses one key-file path contract across root install, preflight, guarded weather owner and standalone/final verifier; secret value never enters normal CLI/config/browser/output.
- [x] Read-only WU current/recent-history payload inspector reports live schema/pressure evidence without mutating observation/history state.
- [x] Fresh host gating is split correctly around package ownership: platform/external preflight before additive bootstrap, full package-aware host preflight afterward.
- [x] `docs/fresh-appliance-acceptance-runbook.md` prepared with hard bedroom-Pi guard and Direct → EQ → WU → repeat-install physical sequence.
- [ ] Physical fresh Direct acceptance: Plexamp, alarm isolation, truthful **Install required** EQ UI.
- [ ] Physical fresh EQ acceptance: split-bus/EQ/alarm isolation and reboot.
- [ ] Deliberate real WU current/history payload inspection with station ID/runtime secret installed on host, never pasted into chat/config/browser.
- [ ] Whole-appliance fresh-Pi/repeatable-install acceptance.

**Exit condition:** source ownership, 2×2 lifecycle, guarded package/weather/dashboard/audio/helper/AirPlay owners, two-stage fresh-host gating, root apply delegation, final verifier commit gate, WU key-file/inspection contracts and alternate-root Direct/fresh-EQ rollback are green. Remaining Phase 7 gates are physical fresh Direct, fresh EQ, real WU and repeatable whole-appliance acceptance.

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

#### Phase 7 checkpoint #13 — guarded top-level apply boundary — **PASS**

Root `install.sh` now accepts `--apply --confirm APPLY-A-CLOCKWORK-PLEX` but remains deliberately non-mutating. Missing or wrong confirmation is rejected before package/host gates; EQ apply additionally requires the verified CamillaDSP path. A confirmed apply repeats the selected `scripts/check-appliance-packages.sh` and `scripts/preflight-appliance.sh` gates, loads/verifies the whole-appliance transaction primitives, but does **not** call `acp_transaction_begin` and does not invoke any specialist `--activate` path. If both read-only gates pass it exits fail-closed with code 3 and a `MUTATION_BLOCKED` marker.

`tests/test_root_installer_apply_gate.py` covers default plan-only behaviour, missing/wrong confirmation, confirmed Direct gate execution followed by the deliberate mutation block, confirmation misuse, EQ CamillaDSP input enforcement, help text and static non-invocation of the guarded specialist owners. Commits `0ad1c49` and `64ab63b` contain the implementation and regression coverage.

The first normal PR run, **Tests #3081 / run `31443722305`**, passed compilation and shell/JS wiring but failed one stale existing unit assertion that still expected the old `--apply is not implemented yet` refusal. The production code and new guarded-apply tests were not the failure. `tests/test_full_installer_plan.py` was updated at `f424479` to assert the new explicit-confirmation boundary instead. **Tests #3083 / run `31443831762` — PASS** at `f424479`, including unit tests and all earlier workflow steps. No production mutation occurred and no bedroom-Pi action is requested at this checkpoint.

#### Phase 7 checkpoint #14 — guarded package and venv bootstrap owner — **PASS**

`scripts/install-appliance-packages.sh` now owns the package/Python-environment bootstrap boundary. It remains prepare-only by default and requires `--activate --confirm INSTALL-APPLIANCE-PACKAGES`. Production activation queries the declared APT prerequisites, installs only missing packages through `apt-get` with `--no-install-recommends`, and repeats the read-only package gate. Package rollback is deliberately **additive rather than destructive**: packages successfully installed as shared host prerequisites are never automatically removed, purged or autoremoved after a later failure because doing so could damage unrelated/shared dependency state.

The repository venv has a stronger exact rollback boundary. A complete candidate venv is built alongside the project, `requirements.txt` is installed into it, `pip check` and Flask import verification must pass, and only then is the existing `venv` moved aside and the candidate renamed into place on the same filesystem. Any activation-stage failure restores the exact prior venv directory (including metadata carried by the rename) or exact prior absence. Alternate-root activation never simulates APT implicitly; it uses an explicit non-production Python override, and post-swap failure injection proves both previous-directory and previous-absence restoration.

Implementation/test commits are `3b12321`, `e5f0038`, `68a4d83`, `96897ca` and `56dff3d`. **Tests #3095 / run `31444251583` — PASS** at `56dff3d`, including compile, shell/JS wiring and unit tests. Root `install.sh` then promoted this guarded package owner into its declared specialist boundary at `f87d463` without invoking it; the top-level apply path still stops after read-only gates and now reports `MUTATION_BLOCKED=WEATHER-DASHBOARD-STAGES-INCOMPLETE`. Root regression coverage was updated at `e106c47`, and **Tests #3099 / run `31444400034` — PASS** at `e106c47`. No production mutation occurred and no bedroom-Pi action is requested at this checkpoint.

#### Phase 7 checkpoint #15 — guarded weather observation configuration owner — **PASS**

`scripts/install-weather-config.sh` now owns only the observation-provider configuration and Weather Underground secret boundary. It defaults to prepare-only and requires `--activate --confirm INSTALL-WEATHER-CONFIG`. The external installer choice remains `ecowitt-push|weather-underground`, translated to the runtime-native `weather.provider` values `ecowitt_push|weather_underground`. Existing unrelated configuration is retained; Open-Meteo forecast configuration is deliberately untouched. Weather Underground station ID is stored under `weather.weather_underground`, while the API key is accepted only through a key-file path and rendered to `/etc/default/a-clockwork-plex-weather` as `WEATHER_UNDERGROUND_API_KEY`; literal secret command-line/config fields are not supported. Historical inline `api_key` fields are removed. Selecting Ecowitt removes the managed WU environment file after successful configuration.

The owner stages and validates candidate JSON/secret files before mutation, never restarts services, and records/restores exact prior `config.json` and managed-secret bytes/existence on failure. Alternate-root failure injection after the config replacement and after secret mutation proves restoration of both prior files and deliberate prior absence; secret mode is verified as `0600`. `systemd/a-clockwork-plex.service` now has an optional `EnvironmentFile=-/etc/default/a-clockwork-plex-weather`, leaving service installation/restart ownership with the guarded dashboard installer rather than this weather owner.

Implementation/test commits are `669023a`, `b87bd06` and `a52686d`. **Tests #3107 / run `31446688664` — PASS** at `a52686d`, including compile, shell/JS wiring and unit tests. No production mutation occurred and no bedroom-Pi action is requested at this checkpoint.

#### Phase 7 checkpoint #16 — shared dashboard owner, application transaction and promoted root apply — **PASS**

Dashboard service installation and kiosk autostart now share guarded `scripts/install-dashboard-integration.sh` rather than two independent mutation/rollback authorities. It is prepare-only by default, requires `--activate --confirm INSTALL-DASHBOARD-INTEGRATION`, renders and validates both candidates before mutation, captures both targets in one transaction, preserves the Weather Underground environment-file hook and verifies `/api/state` on production activation. Alternate-root tests prove exact restoration of previous files/modes and previous absence.

`installer/lib/application_transaction.sh` adds the outer application-managed capture boundary after package/venv bootstrap. It captures configuration, weather environment, dashboard/kiosk, helper policies, AirPlay/Shairport integration, the metadata FIFO, Direct/EQ route/state and relevant production service state. `scripts/install-appliance-application.sh` is the single guarded mutation sequencer: weather → dashboard → Direct baseline → optional EQ → helpers → AirPlay → `scripts/verify-appliance.sh`. The verifier is inside the commit boundary. A fresh EQ installed by the transaction is explicitly unwound through `scripts/audio/uninstall-eq.sh` before generic application-state restoration.

Root `install.sh --apply --confirm APPLY-A-CLOCKWORK-PLEX` is now promoted beyond the former `MUTATION_BLOCKED` boundary. It repeats the package/artifact and host/preflight gates, establishes the additive package/verified-venv prerequisite baseline through `scripts/install-appliance-packages.sh`, then delegates all application mutation to `scripts/install-appliance-application.sh`; it does not duplicate specialist mutation logic. Weather Underground apply accepts station ID plus an API-key **file path** only, and root regression coverage proves the secret value is never echoed/logged by the root installer.

CI deliberately caught contract drift while this boundary was promoted: stale AirPlay verifier/profile fixtures, two semantic wrapper markers and several plan-text assertions all failed closed and were corrected without weakening the accepted runtime/safety contracts. The first fully green promoted-root head was **Tests #3149 / run `31451271274` — PASS** at `16f30fe`.

#### Phase 7 checkpoint #17 — alternate-root whole-appliance rollback, including fresh EQ — **PASS**

The application transaction now has deliberate late failure injection after specialist mutation. Direct-path coverage proves weather/config, dashboard/kiosk, Direct route, helper, Shairport/AirPlay files and FIFO state restore to exact captured bytes/modes or absence. Fresh-EQ coverage starts from a deliberately different pre-appliance route and a pre-existing FIFO, installs Direct then EQ, proceeds through helpers and AirPlay, injects failure after AirPlay, and requires the accepted EQ uninstaller to run **before** the outer application restore.

The fresh-EQ test then verifies the original pre-appliance route bytes/mode, project config, Shairport config and FIFO mode are restored exactly, while the fresh EQ marker, CamillaDSP service/binary, dashboard unit and AirPlay wrapper return to prior absence. The rollback ordering is also statically pinned so a future refactor cannot silently invert EQ teardown and generic restoration. **Tests #3151 / run `31451366362` — PASS** at `1a38270`.

#### Phase 7 checkpoint #18 — first-install WU key-file contract — **PASS**

Fresh Weather Underground installation no longer depends on a secret being pre-exported in the invoking shell. Root apply, host preflight, guarded weather configuration, whole-application sequencing and standalone/final appliance verification now share the same explicit **API-key file path** contract. Preflight and verifier validate file shape without displaying the value; `config.json` stores only station ID plus environment-variable name; production runtime secret material remains in `/etc/default/a-clockwork-plex-weather` and is consumed by the dashboard service EnvironmentFile.

Regression coverage proves root orchestration forwards the file path but never the secret value, including stdout/stderr/log assertions. The application transaction can perform a genuine first WU install and still satisfy its final verifier without an operator manually exporting the credential. **Tests #3171 / run `31452097877` — PASS** at `d131644`.

#### Phase 7 checkpoint #19 — read-only real WU payload inspector — **PASS**

`scripts/inspect-weather-underground-payloads.py` now provides the deliberate current/history inspection path required by the accepted weather design. It uses the existing WU current and one-day history URL builders, accepts station ID plus API-key file, never displays credential-bearing URLs, and writes no config/dashboard/history state. It reports observation counts, field/unit structure, timestamp evidence and pressure-related paths, and runs the current payload through the existing dashboard mapper.

History remains conservative by design: aggregate/range fields such as `pressureAvg`, `pressureMin` and `pressureMax` are not treated as instantaneous barometer samples. Even a history payload where every row exposes `obsTimeUtc + numeric imperial.pressure` is labelled only **YES — REVIEW REQUIRED**, never automatically ingested. Synthetic schema tests prove both behaviours and secret redaction. **Tests #3175 / run `31452388309` — PASS** at `caa583d`.

#### Phase 7 checkpoint #20 — fresh package/bootstrap preflight ordering — **PASS**

A final fresh-OS audit found an ownership-order contradiction: `git`, `curl`, Python/venv, ALSA utilities, Shairport Sync and Chromium are explicitly installer-owned packages, but the original full host preflight required several of them to exist before package bootstrap. The same preflight now has a `--bootstrap-pending` platform/external mode. Before package mutation, OS/architecture/project-user/DAC/external Plexamp/profile-specific safety still fail closed while installer-owned package prerequisites may report `READY`. After the guarded package/venv bootstrap, root runs normal full preflight and those owned prerequisites must actually exist before application mutation starts.

Root regression coverage pins the five-stage order: package/artifact check → pre-bootstrap platform gate → package/venv bootstrap → full post-bootstrap host gate → one application transaction. WU key-file input reaches both preflights without exposing the secret. **Tests #3185 / run `31452688437` — PASS** at `ac7cec8`.

`docs/full-appliance-installer-design.md` is now aligned with the implemented architecture, and `docs/fresh-appliance-acceptance-runbook.md` records the stop-on-first-failure physical Direct → EQ → WU → repeat-install procedure with a hard `plexamp-bedroom` guard.

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

1. Choose/prepare the disposable fresh target and execute sections 1–5 of `docs/fresh-appliance-acceptance-runbook.md` through **physical fresh Direct acceptance**. Stop on the first failed gate and record evidence before any retry.
2. On the same accepted fresh target, execute EQ promotion/reboot acceptance and require split-bus/EQ/alarm isolation plus both verifiers.
3. Run the read-only real WU current/history inspector, then WU runtime acceptance with station ID and key-file secret installed on the host only.
4. Repeat the whole-appliance EQ+WU install on the already-configured fresh target and require a clean verifier result with no ownership drift.
5. Commit the dated physical result document; only then can Phase 7 be considered for closure.

No local weather caching/fan-out server is part of the design.

## Roadmap maintenance discipline

- Material completion/block/scope change updates this file immediately.
- A phase is not complete until its exit condition passes.
- Failed gates are recorded with exact scope/result.
- Physical Pi mutation records route/checksum, relevant service state and rollback.
- Check this roadmap before reporting status.
- PR #2 remains Draft and must not be made ready/merged without explicit owner approval.
- Owner should not need to prompt for routine roadmap updates.
