# EQ-capable Audio + Full Appliance Installer Roadmap

**Last updated:** 18 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 — must remain Draft/open/unmerged until explicit owner approval.

## Historical evidence

Detailed history through Phase 7 checkpoint #6 is preserved in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. Detailed real spare-SD bootstrap attempts after checkpoint #26 are recorded in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`. This file is the active implementation/acceptance authority and must be updated as physical acceptance progresses.

## Settled invariants

### Audio

- Scheduled alarms **bypass Music Master**; UI copy must never imply otherwise.
- EQ music: Plexamp/AirPlay → source trims → Music Master → fixed `-6.5 dB` reserve → Bass/Mid/Treble → final limiter → DAC.
- Alarm: per-alarm target/fade → **Maximum Alarm Volume** → joins after music reserve/EQ → final limiter → DAC.
- Alarm fade must be perceptible and unambiguous: the configured target is the destination, Maximum Alarm Volume is a ceiling, and the implementation must not silently clamp a hidden start level to the same value and thereby eliminate the fade. Snooze/re-ring starts a new ring cycle and therefore a new fade-in.
- Fresh Direct keeps Plexamp/AirPlay under Music Master while alarm joins the DAC-facing mix independently.
- `scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate.
- Do not use the old bare `scripts/install-master-eq.sh` production path.
- An already-installed EQ appliance is now a **supported convergent source state** when the whole-appliance installer is asked for Direct. Do not require a manual EQ uninstall.
- EQ → Direct convergence must remain inside the outer application transaction: specialist teardown retains the pre-EQ backup, rollback restores that backup and the pre-transition live `snd_aloop` state before captured EQ services are reactivated, and retained backup cleanup occurs only after successful outer commit.
- Once guarded Direct construction/verifiers and a focused playback/NFC/EQ-status smoke have passed, do **not** require a redundant full Direct AirPlay/alarm/handoff replay before EQ promotion. The meaningful final regression is post-EQ, where the changed route can affect those behaviors.
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
- Supplementary Ecowitt indoor readings must carry their own freshness timestamp. When no recent indoor push exists, Clock indoor cards are omitted and the Weather Main conditions **Indoor** row is omitted rather than displaying stale values or `—` placeholders.
- Ecowitt custom upload is a single-destination path on the physically used station setup. Documentation must explain that one station cannot directly push the same custom feed to several A Clockwork Plex appliances; WU's cloud PWS source is the practical shared live source for multiple appliances, with a directly-fed appliance optionally gaining indoor readings.
- The configurable historical-rainfall periods remain exactly **Today**, **Last 7 days**, **Current month** and **Current year**; default is Last 7 days.
- Today uses live `dailyrainin`; completed historical days use WU daily `precipTotal`.
- When the live provider lacks native Hourly rain/Event rain (notably WU), A Clockwork Plex may derive them locally from persisted successive daily-rain observations. Native provider values take precedence when present.
- Derived Hourly rain is a rolling preceding-60-minute accumulation. Derived Event rain is persistent across refresh/reboot and follows one documented reset rule; deterministic/synthetic tests are sufficient for source acceptance when physical rainfall is unavailable, with a later real wet-weather observation allowed as non-blocking follow-up.
- The Weather rain panel retains two visual groups — current/today rain and **Rainy Day Fund** — but both groups participate in one horizontal scrolling surface with one forecast-style custom rail/thumb. Current-rain cards use the available panel height rather than remaining a short fixed row.
- `weather-rainfall-history.json` is a station-scoped, secret-free supplemental cache. Numeric daily totals live under `days`; confirmed successful-query station-offline dates live separately as `no_station_data` gap markers. `null` day markers are not an accepted final cache state.
- Missing/invalid completed dates are fetched in contiguous WU requests of at most 31 days. If a successful range omits a date, that date is retried once as a single-day request before it may be classified as a confirmed station-data gap.
- Confirmed station-data gaps are not repeatedly re-fetched. They do **not** make otherwise successful history an API failure: the sum of recorded days remains visible as a **minimum recorded** total with explicit coverage information.
- Legacy `null` unavailable markers from the earlier implementation are treated as missing and retried.
- An actual provider/configuration/credential failure remains an error for the selected historical aggregate and must never take current observations down.
- Live observation source and WU history source are independent; Ecowitt Push may remain live while WU supplies history.
- Commission current source and WU history under **Settings → Weather → Observation source**. The accepted physical presentation uses a bordered live-source badge at the top-right of the Observation source card and a separate bordered history badge at the top-right of the Historical rainfall card.
- Weather Settings cards and source grids use deliberate touch-friendly separation on both supported landscape targets, including 1024×600.
- Rainy Day Fund historical summaries are independent of the single configurable history period and expose **This week / Last week / This month / Last month / This year / Last year**.
- The final Rainy Day Fund total is **Rain lifetime**, not merely Last year + This year and not an unverified live Ecowitt counter. It is calculated from WU daily history from the first discovered WU record through today.
- Older lifetime history is isolated in station-scoped, secret-free `weather-rainfall-lifetime.json`; it never races the selected-period / Rainy Day Fund comparison cache. Discovery and coverage use WU ranges of at most 31 days and preserve the same confirmed-gap semantics.
- Because documented WU PWS metadata exposes no station-inception field, lifetime discovery walks backwards and treats 24 consecutive empty 31-day probes as the automatic pre-station boundary, with `weather.historical_rainfall.lifetime_start_date` available as an explicit override for unusual multi-year mid-life outages. The hard automatic discovery floor is 1995.
- Once lifetime discovery and coverage are both complete, later lifetime refreshes are cache-only and issue zero WU requests.
- During one-time lifetime backfill, the gauge must say **Backfilling earlier WU history**; once ready it identifies the first WU record date and any real missing-day coverage.
- Rain presentation uses the **same custom rounded rail/thumb control as the forecast strips**. Chromium's native rain scrollbar, including its arrow buttons, stays hidden. Touch strip scrolling, thumb drag, rail clicks and keyboard navigation remain supported.
- Coverage notes use concise copy such as `3 days not recorded`.
- WU API key is write-only commissioning data: never returned to the browser, stored in `config.json`/browser storage, placed in argv or logged.
- Persistent secret storage is root-owned `/etc/default/a-clockwork-plex-weather`, mode `0600`; the restricted helper receives key material on stdin.
- Selecting/reconverging **Ecowitt Push for live observations must preserve the exact existing managed WU credential file** because WU may still supply supplemental rainfall history. If that managed file was absent, Ecowitt convergence must keep it absent; it must never invent, rewrite or reveal a credential.
- Both rainfall cache files are runtime state and must stay ignored by Git; generating `weather-rainfall-lifetime.json` must not dirty the checkout.

### Player/runtime

- **Plexamp Headless remains the player for this release.** Caldera migration is out of Phase 7 scope.
- Plexamp Headless: `4.13.2`, official archive SHA `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.
- Node: `20.20.2` linux-arm64, SHA `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`, installed beneath `/opt/a-clockwork-plex` without replacing distribution Node.
- Fresh account/player setup is an explicit local interactive checkpoint; claim material is never a normal installer/evidence field.
- `setup.sh` is the normal human-facing first-install entry point and owns CamillaDSP artifact acquisition plus interactive Plexamp claim handoff. `install.sh --fresh-bootstrap` remains the guarded lower-level appliance installation engine; both files have distinct final-release roles and are not duplicates to be merged merely for repository tidiness.
- An unclaimed fresh runtime exits `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`; interactive `setup.sh` launches the installed Plexamp claim process and resumes after the saved claim state exists.

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

### Phase 7 — full appliance installer integration — **In progress: final Weather/alarm source work is green; physical acceptance, Clock annunciator, final public clean-room install, verifiers and release hygiene remain**

#### WU Settings commissioning — physical PASS

- [x] Dedicated write-only credential manager/API outside the revisioned Settings transaction.
- [x] Restricted stdin-only secret helper and root-owned `0600` environment file.
- [x] Set/Replace/Remove key, credential status and Test connection controls.
- [x] Running-process environment update without dashboard restart.
- [x] Sanitized provider test path and source tests.
- [x] Ecowitt-live weather convergence preserves an existing commissioned WU history credential byte-for-byte and preserves prior absence when none exists.
- [x] **Physical:** real WU credential commissioned locally without key disclosure; write-only status/config boundaries verified; WU supplemental history stayed healthy with Ecowitt Push live; later Ecowitt reconvergence preserved the exact managed WU credential and root `0600` metadata. Evidence: `docs/weather-physical-followup-2026-08-17.md`.

#### Historical rainfall + Weather source workspace — physical PASS

- [x] Observation Source is its own Weather subpage; Station owns dashboard labels/refresh.
- [x] Explicit current-source and history status badges remain card-local and truthful (`Ecowitt Push`, `WU Ready`, `History ready`, setup/degraded states).
- [x] Exact configurable Today / Last 7 days / Current month / Current year model.
- [x] Live Today semantics and station-scoped secret-free WU daily cache.
- [x] <=31-day missing-range batching and single-day retry of dates omitted from successful range responses.
- [x] Confirmed successful-query station gaps are cached separately from numeric totals and do not cause repeated fetches.
- [x] Minimum-recorded totals remain visible with explicit missing-day coverage; actual API/config/credential failures remain distinct and supplemental to live observations.
- [x] Rainy Day Fund source projection receives six independent calendar summaries (This/Last week, month and year).
- [x] Calculated final gauge is WU-backed **Rain lifetime**, combining the older discovered archive with previous/current year rather than relabelling a two-year sum or trusting an unrelated station counter.
- [x] Older archive uses separate `weather-rainfall-lifetime.json`, backward discovery, bounded coverage fill, confirmed gaps and request-quiet settled state.
- [x] Rainy Day Fund uses the same custom forecast rail/thumb mechanism rather than Chromium's native scrollbar.
- [x] Physical Settings presentation, WU commissioning, Ecowitt/WU independence, credential preservation, Today, Last 7 days, Current month and Current year selected-period behavior are accepted.
- [x] Physical Current-year gap case: 226/229 days recorded, confirmed gaps on `2026-03-03`, `2026-03-05`, `2026-03-07`, `status: ready`, `complete: true`, `coverage_complete: false`, `total_in: 21.38`; two consecutive forced refreshes both reported `fetched_ranges: 0` / `retried_dates: 0`.
- [x] Rainy Day Fund blank-gauge root cause identified: the rainfall wrapper patched the `app.main` facade while Flask's context processor resolved `dashboard_core.weather_detail_data`. Source head `6316a63fbc109967ccd517a631796be01b859ba2` patches the real Flask projection and adds This/Last week/month/year summaries plus prior-year backfill; Tests #3485 / run `31991516804` passed. The corrected gauges were subsequently physically accepted under #32.
- [x] Lifetime archive settles without continued WU traffic; source/CI head `22455624917ce456087e3a11041937b3c0526623` passed Tests #3523 / run `31994639762`, including both rainfall-service lifecycle/wake ownership and custom-scroll regressions.
- [x] **Physical Rainy Day Fund/lifetime closure:** forecast-style custom scrolling physically matches the forecast strips with no native arrow buttons; the gauge set includes This/Last week/month/year plus **Rain lifetime**; lifetime settled at `status: ready`, `discovery_complete: true`, `coverage_complete: true`, first WU record `2023-12-30`, 368 older numeric days and zero older gaps; dashboard displayed **2634.0 mm** with **11 days not recorded**; a subsequent forced lifetime refresh returned `fetched_ranges: 0` / `retried_dates: 0`; recent/lifetime cache structural checks both passed with no secrets/null/invalid values; live observations remained `provider: ecowitt_push`, `status: push`, worker running. Evidence: `docs/weather-physical-followup-2026-08-17.md`.

#### Final Weather + alarm polish — source/CI PASS; physical acceptance pending

- [x] **Source/CI:** WU remains outdoor authority while a direct Ecowitt push may store only fresh supplementary indoor temperature/humidity; stale/absent supplementary data is omitted from Clock and Weather presentation rather than replacing WU or leaving placeholder rows.
- [x] **Source/CI:** WU Hourly rain and Event rain are derived from persisted successive rain observations, while native Ecowitt Hourly/Event values retain precedence. Synthetic coverage includes rolling-hour accumulation, event reset, midnight rollover, station changes and active rain between gauge increments.
- [x] **Source/CI:** WU `precipTotal` maps to `dailyrainin`; the Clock rain composite renders whenever either Rain today or Event rain is available, so Event rain absence alone cannot hide a valid Rain today value.
- [x] **Source/CI:** current/today rain and Rainy Day Fund participate in one horizontally scrolling surface with one forecast-style custom scrollbar and full-height current-rain cards.
- [x] **Source/CI:** scheduled alarms with Fade enabled start each ring cycle from silence and ramp to the selected target after the Maximum Alarm Volume ceiling is applied; Fade disabled starts immediately at the target. The alarm editor now exposes **Fade in** with Off/5/10/20/30/60-second choices while preserving unusual existing saved durations, and new/saved alarms canonicalise the retired hidden start value to 0%.
- [x] `INSTALL.md` documents the Ecowitt one-custom-destination limitation and recommends WU as the shared live source for several appliances; carry the same guidance into the final README rewrite.
- [x] The stale weather-source-authority test was updated for supplementary indoor semantics and the complete combined source/UI head passed **Tests #3643 / run `32094143655`**.
- [ ] **Physical:** with WU selected, confirm Rain rate / Hourly rain / Rain today / Event rain presentation, shared rain-row scrolling and Rainy Day Fund layout on the Touch Display 2.
- [ ] **Physical:** confirm a Pi receiving Ecowitt custom push gains indoor temp/humidity, and a WU-only Pi hides the Clock indoor cards and Weather Indoor row when no fresh indoor push exists.
- [ ] **Physical:** set a deliberately obvious 20–30 second Fade in, trigger a real scheduled alarm during Plexamp playback, confirm audible ramp from silence to target, Snooze, and confirm the re-ring performs a fresh fade before Dismiss.

#### Final Clock/navigation polish — after current Weather/alarm acceptance

- [x] **Source/CI:** make the injected Audio navigation button use the same application font size/weight as Clock, Weather, Plexamp, AirPlay and Settings; regression coverage added.
- [x] **Source/CI:** correct the 14-segment glyph map so numeric `0` lights the bottom-left → top-right slash diagonals while capital `O` remains unslashed, and remove the bottom horizontal segment from `W`; regression coverage added.
- [ ] **Physical:** confirm the corrected Audio button typography and `0`/`W` segment shapes on the bedside display after the current Weather/alarm source batch is pulled.
- [ ] Add an LCD-style **alarm set** indicator to the Clock page, positioned in a top corner and visually integrated with the 14-segment display rather than looking like a generic web icon.
- [ ] Alarm indicator presentation: use a simple bell SVG derived from the supplied visual reference, treat it like an LCD annunciator with a faint unlit state and a restrained lit glow/brightness rather than full clock-white, and size it at roughly 60% of the large Clock seconds height subject to physical visual tuning.
- [ ] Add a user-facing alarm-indicator mode with at least **Any future scheduled occurrence** and **Next occurrence within 12 hours** behaviours; the indicator must follow the scheduler's actual next-occurrence authority rather than merely checking whether an alarm definition exists.
- [ ] Ensure the annunciator respects Classic/Astronomy night treatment, dimming/burn-in presentation and 1024×600/1280-class Clock layouts without colliding with the main time/date/weather cards.

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
- [x] Public `setup.sh` now owns the CamillaDSP fetch/verification and automatically launches Plexamp Headless at the claim checkpoint; no CamillaDSP session variable or separate Plexamp launch command is part of the normal operator path.

#### EQ artifact acquisition — source/CI + physical complete

- [x] Guarded `scripts/fetch-camilladsp-4.1.3.sh`.
- [x] Official archive and accepted executable hashes both pinned/verified.
- [x] Independent temporary probe confirmed archive `d9a170...aca5` extracts executable `e04c7a...edfa`; temporary probe workflow removed afterwards.
- [x] Physical spare-card check returned `CAMILLA_ARTIFACT=PASS-EXISTING`; independent version/SHA verification matched the accepted 4.1.3 executable exactly.

#### Spare-SD physical acceptance handoff

- [x] Runbook uses a spare SD while production card remains untouched.
- [x] Runbook covers fresh baseline/evidence, Direct, exits `75`/`76`, independent verifiers, guarded Camilla fetcher, EQ, post-EQ NFC/AirPlay/alarm regression, reboot, repeat install and WU Settings/history.
- [x] First Trixie apply exposed inherited-system NFC `pip check` noise; checkpoint #26 repair is green.
- [x] Subsequent attempts physically proved paired venvs, PN532 `0x24`, `CARD=Pro`, pinned Node/Plexamp claim/resume, NFC, full preflight, dashboard/kiosk, Direct route, restricted helpers and AirPlay. Detailed evidence is in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`.
- [x] Protected `/etc/sudoers.d` verification was repaired at both helper-owner and final-verifier boundaries.
- [x] 16 August retry proved the complete prerequisite substrate again and then exposed the installed-EQ → requested-Direct convergence gap; evidence: `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`, exit `2`.
- [x] Checkpoint #28 source repair supports transactional EQ → Direct convergence; regression coverage proves success and forced rollback.
- [x] **Physical fresh Direct installation and verification:** 17 August guarded convergence completed from the existing EQ state with root installer exit `0`, `ROOT_INSTALL=COMMITTED`, `APPLICATION_VERIFY=PASS`, `FRESH_BOOTSTRAP_VERIFY=PASS`, `APPLIANCE_VERIFY=PASS`, canonical Direct SHA and clean EQ/loopback residue. Evidence is recorded in `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] **Focused Weather physical acceptance:** Settings presentation, WU commissioning, live/history independence, Ecowitt credential preservation, selected-period gap semantics, six comparison gauges, custom forecast-style rain scrolling, genuine WU Rain lifetime, settled request-quiet behavior, both cache structural checks and continued live Ecowitt operation all passed physically. Evidence: `docs/weather-physical-followup-2026-08-17.md`.
- [x] **Focused Direct pre-EQ smoke:** Plexamp playback healthy; known NFC tag triggered local playback and requested Plexamp dashboard state; Audio and Settings Master equaliser truthfully reported **Install required**. Full Direct handoff/alarm replay is intentionally not a promotion blocker; evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] Runtime lifetime cache is ignored by Git; generated `weather-rainfall-lifetime.json` no longer dirties the checkout.
- [x] **Physical persistent EQ installation and split-bus identity verification:** guarded fresh-bootstrap EQ apply exited `0` with `ROOT_INSTALL=COMMITTED`, `APPLICATION_TRANSACTION=COMMITTED`, `APPLICATION_VERIFY=PASS`, independent fresh-bootstrap/appliance/audio verifiers all PASS, canonical split-bus SHA `1bc69f...08bd9`, installed marker present, Plexamp audible and EQ controls effective. Canonical `a-clockwork-plex-camilladsp.service` is active/enabled/running; the generic `camilladsp.service` name is not the managed unit. Evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] **Post-EQ physical regression:** Plexamp and AirPlay both remained healthy through EQ; audible EQ changes and bypass worked; Music Master at 0% silenced music while a real scheduled alarm remained audible; Maximum Alarm Volume capped the alarm independently; Snooze/re-ring/Dismiss passed; NFC playback/dashboard handoff and immediate repeat-tag debounce passed. No issue found. Evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- [x] **Operator `INSTALL.md` walkthrough on a fresh spare SD:** the appliance reached a working dashboard with WU weather populated, Plexamp through EQ, AirPlay through EQ and NFC working. This walkthrough pre-dates the final `setup.sh` CamillaDSP/claim UX simplification, so it does not replace the final clean-room public-entry-point run.
- [x] **Functional reboot acceptance:** after configuration the Pi was fully restarted and returned with dashboard, WU weather, Plexamp/EQ, AirPlay/EQ and NFC behaving normally. Formal post-reboot bootstrap/application/audio verifier evidence remains to be captured.
- [x] **Fresh-install scheduled-alarm functional acceptance:** with Plexamp playing, a real scheduled alarm paused/took over Plexamp, Snooze worked, the alarm re-rang, and Dismiss completed cleanly. Per-alarm target and Maximum Alarm Volume cap were observed; fade behaviour exposed the hidden-start-level issue now repaired in source under checkpoint #37.
- [x] **Lower-level repeat-install acceptance:** rerunning `install.sh` against the already-installed appliance without pulling new source completed without warnings/errors, requested no reboot and left dashboard/EQ behaviour unchanged.
- [ ] Run bootstrap/application/audio verifiers after a representative final reboot and commit the evidence.
- [ ] After Weather/alarm/Clock UI polish and installer/docs settle, wipe the spare SD once more and perform the final `INSTALL.md` clean-room run using **`setup.sh`** from the first public command through claim, Plexamp GUI commissioning, WU configuration, playback/EQ/AirPlay/NFC/alarm and reboot.
- [ ] Rerun the final public `setup.sh` on that installed card to prove idempotence with no renewed claim/reboot checkpoint or ownership drift.
- [ ] Commit/finalize the final clean-room/reboot/repeat physical result/evidence documents; only then close Phase 7.

#### Final repository/release hygiene — required before merge

- [ ] Inventory the complete PR/repository file set and remove obsolete one-off test scaffolding, temporary probe assets, generated files and superseded installer/testing leftovers that are not required for a fresh installation, maintained development tests, diagnostics, rollback or useful historical evidence.
- [ ] Review the large `docs/` history deliberately: retain the active installation/operation documentation and evidence worth preserving; archive/consolidate superseded phase documents where appropriate rather than blindly deleting useful provenance.
- [ ] Keep `setup.sh` and `install.sh` unless the final dependency audit disproves their distinct roles: `setup.sh` is the simple operator entry point; `install.sh` is the guarded lower-level installer/recovery engine.
- [ ] Rewrite `README.md` for the finished appliance: supported hardware, what the project does, one-command installation, Plexamp commissioning, audio/EQ/AirPlay/NFC overview, Weather provider choices/limitations, updating, troubleshooting pointers and links to `docs/INSTALL.md`.
- [ ] Ensure `.gitignore` covers all runtime/generated weather/evidence state that must not dirty a normal checkout and confirm a fresh installed appliance does not create tracked-file changes.
- [ ] Run a final tracked-file/install-dependency audit so every file required by `setup.sh`/`install.sh` is present after cleanup and no retained file exists merely because it was used by an obsolete physical experiment.
- [ ] Get the complete validation suite green after cleanup; PR #2 remains Draft until all release-hygiene and final physical gates are complete and owner approval is explicit.

**Phase 7 exit condition:** the spare-SD appliance passes Direct construction + focused smoke → EQ → post-EQ physical regression → functional/formal reboot → final public `setup.sh` clean-room install and repeat-install, with final Weather/alarm/Clock UI polish accepted, `verify-fresh-bootstrap.sh`, `verify-appliance.sh` and `scripts/audio/verify-audio.sh` green where applicable, release hygiene/README complete and dated evidence committed. PR #2 remains Draft throughout.

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
- **#23 — pinned NFC runtime, paired venv and guarded NFC service owner — PASS.** Tests #3263 / run `31664707020`, `63fa8825e4949d88026bfbe5a54ffc9`.
- **#24 — staged fresh-bootstrap preflight/root route with fail-closed player boundary — PASS.** Tests #3285 / run `31691861309`, `bf701e4ba256c45c0fd295f88026bfbe5a54ffc9`.
- **#25 — test-ready spare-SD appliance: Plexamp/Node, DAC Pro, verifier, Camilla fetcher/runbook — PASS.** Tests #3339 / run `31848016743`, `a3f05ebee67565cfaa5a6f7a605fc770a7b4fbd8`.
- **#26 — Trixie first apply dependency-boundary repair — PASS (source/CI).** Tests #3353 / run `31895570826`, `85db50016af086454208c2e0216f479d8b451790`. Later physical evidence supersedes #26 as the Pi source target.
- **#27 — cached historical rainfall + Weather Observation Source workspace — PASS (source/CI).** Commit `28baf6fd91b4169813fbdbbe99d7b613fde8d151`; Tests #3411 / run `31972466589`. Its original unavailable-marker cache policy is superseded by the later confirmed-gap model.
- **Post-#27 documentation incident — repaired.** `7479d6308417561983bbde87e3a9a788686388a1` failed only because the test-pinned Weather heading was changed; the exact `# 14. Commission Weather Underground through Settings` heading was restored and remains contract-pinned.
- **#28 — installed EQ → requested Direct convergence — PASS (source/CI).** Physical Attempt 6 reached application transition after package/venv, PN532 `0x24`, `CARD=Pro`, claimed Plexamp, NFC and full preflight passed, then the old hard guard rejected the already-EQ spare SD with exit `2`; evidence `/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-222614.txt`. Commit `4bfd9d0ed83927473d0ae70f5947761de6fad817` replaces that rejection with specialist EQ teardown under the outer application transaction, retained pre-EQ backup/tombstone handling and pre-service `snd_aloop` rollback restoration; Tests #3421 / run `31975846667` passed. Commit `b4e64fcf279843a7f928c5da41252adb11aae00a` adds focused success/forced-rollback/retained-backup/order regression coverage; Tests #3423 / run `31976778069` passed.
- **Post-#28 physical Direct convergence — PASS.** Commit `ec86c76bc0a6c9aec53bc51394bc06a15028cda8` records the 17 August spare-SD root install exit `0`, both independent Direct verifiers PASS, canonical Direct route identity and clean post-EQ residue.
- **#29 — retryable WU rainfall gaps + Weather card spacing follow-up — PASS (source/CI), semantics later superseded.** Commit `967e684ca51b07ad25731d78401a195cde024081` introduced retryable omitted/invalid dates and responsive card spacing; Tests run `31981475409` / #3445 passed. Its all-or-nothing total rule is superseded by the confirmed station-gap/minimum-recorded model physically accepted below.
- **#30 — Weather physical-follow-up convergence — PASS (source/CI), presentation evolved during physical acceptance.** Commit `bd3124e0bbb8682d8faf0f3cc44725fc7da9fc8c` added credential preservation and strengthened source-card spacing. Physical acceptance subsequently settled on card-local live/history status badges rather than the transient global-heading placement. Tests run `31984835861` / #3451 passed.
- **#31 — confirmed station gaps + Rainy Day Fund projection — PASS (core physical + source/CI; final presentation closed under #32).** On `plexamp-test`, Current year physically returned 226/229 days, three confirmed March station gaps, `status: ready`, `complete: true`, `total_in: 21.38`, and two repeated refreshes at zero fetch/retry cost. Settings showed **History ready** with explicit minimum-recorded coverage. The blank Rainy Day Fund then exposed a `main` facade versus `dashboard_core` context-projection bug. Source commit `6316a63fbc109967ccd517a631796be01b859ba2` patches the real Flask projection and adds This/Last week/month/year summaries plus prior-year backfill; Tests #3485 / run `31991516804` passed. The corrected gauges were subsequently physically accepted under #32.
- **#32 — forecast-style Rainy Day Fund scroll + genuine WU Rain lifetime — PASS (source/CI + physical).** The rain strip hides Chromium's native arrow-button scrollbar and reuses the forecast rail/thumb mechanism. `WeatherRainfallLifetimeService` independently discovers/backfills older WU daily history, combines it with previous/current year into **Rain lifetime**, exposes sanitized `/api/weather/rainfall/lifetime` status and becomes request-quiet after discovery+coverage settle. Implementation head `bbdcc74dde455269def9b5bcb72c3601e295c6b2`; lifecycle regression synchronization head `22455624917ce456087e3a11041937b3c0526623`; full Tests #3523 / run `31994639762` PASS. Physical head `f0ea56557ba3d2fd09b624c9162ceea6c30de6f9` displayed the accepted custom scrollbar and **Rain lifetime 2634.0 mm since first WU record 30/12/2023 · 11 days not recorded**. Settled lifetime POST returned `fetched_ranges: 0` / `retried_dates: 0`; `weather-rainfall-history.json` validated with 582 numeric days / 11 recognized gaps and `weather-rainfall-lifetime.json` with 368 numeric days / zero gaps, both free of secrets/null/invalid values; Ecowitt remained `status: push` with its observation worker running. Focused Weather acceptance is physically complete.
- **#33 — focused Direct pre-EQ smoke + UI/runtime hygiene — PASS (physical/source).** On the verified Direct spare card, Plexamp playback remained healthy, a known NFC tag triggered local playback and the Plexamp dashboard state, and both EQ surfaces truthfully showed **Install required**. The Master equaliser status is now styled with the same explicit bordered pill treatment, and `weather-rainfall-lifetime.json` is ignored as runtime state. Full Direct AirPlay/alarm replay is intentionally deferred to the post-EQ regression where it can validate the new route.
- **#34 — guarded persistent EQ promotion — PASS (physical).** On `plexamp-test`, the fresh-bootstrap EQ apply committed cleanly from the physically accepted alarm-safe Direct state. Root/application transactions and all three independent verifiers passed; the active route matched the canonical split-bus SHA, the installed marker and loopback identity were correct, Plexamp audio/EQ were physically working, and `a-clockwork-plex-camilladsp.service` was active/enabled/running. Evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- **#35 — focused post-EQ regression — PASS (physical).** Plexamp and AirPlay both passed through the installed EQ path with working EQ/bypass; Music Master 0% silenced music without silencing a real alarm; Maximum Alarm Volume remained independent; Snooze/re-ring/Dismiss and NFC playback/dashboard/debounce all passed with no issues found. Evidence: `docs/eq-to-direct-physical-verification-2026-08-17.md`.
- **#36 — first complete operator INSTALL walkthrough + functional reboot/repeat-install/alarm closure — PARTIAL PASS (physical, 18 August).** A freshly prepared spare SD completed the then-current `INSTALL.md` path and produced a working dashboard with WU observations, Plexamp through EQ, AirPlay through EQ and NFC. A full reboot preserved normal behaviour. A real scheduled alarm paused Plexamp, took audio ownership, Snoozed/re-rang and Dismissed successfully. A same-source `install.sh` rerun completed without warnings/errors or reboot request and left dashboard/EQ unchanged. Remaining from this checkpoint: physically accept the source-complete final Weather/alarm and tiny Clock/nav fixes, add/accept the alarm annunciator, capture formal post-reboot verifiers, then perform one final wiped-SD run of the **new** public `setup.sh` path (including integrated CamillaDSP acquisition and automatic Plexamp claim launch) plus a repeat `setup.sh` idempotence pass.
- **#37 — final WU supplementary indoor/derived rain + alarm fade + nav/segment source closure — PASS (source/CI, physical pending).** WU outdoor authority now admits only separately fresh Ecowitt indoor supplementation; WU Hourly/Event rain is locally derived with persisted event state and Ecowitt-native values retain priority; the current and historical rain groups share one scroll surface; scheduled alarm fade starts from silence and is now a visible per-alarm setting; the Audio nav typography and numeric `0`/`W` segment glyphs are corrected. The stale WU authority contract was updated and the combined implementation passed **Tests #3643 / run `32094143655`**. Physical Touch Display/weather/alarm checks remain open above.

No checkpoint is recorded as fully physically complete until its exact physical gates pass. Source/CI PASS does not substitute for remaining physical acceptance.