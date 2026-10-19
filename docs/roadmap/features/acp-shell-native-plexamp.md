# ACP shell / native Linux Plexamp — #94

**Status:** Phase A complete; Phase B active. **Current priority: finish native Squeekboard (C3)**.  
**Branch:** `feature/acp-shell-native-plexamp` · **Updated:** 19 October 2026

> This is a **working feature checklist**, not a chronological test transcript. The Raspberry Pi is a development appliance; move through complete vertical slices, with a brief focused test and physical check per feature. Detailed pre-cleanup history is preserved in the [full feature archive](../../archive/acp-shell-native-plexamp-full-history-2026-10-19.md).

## At a glance

| Workstream | State | What counts as finished |
| --- | --- | --- |
| A — ACP shell and spatial navigation | ✅ Accepted | Five ACP surfaces, nav drawer, utility overlays, animations, night Clock |
| B — native Linux Plexamp | 🟡 Functional discovery | Normal start, fullscreen, search, playable audio, end-to-end ACP integration |
| C1 — Settings text entry and field reachability | ✅ ACP browser accepted | Native/custom keyboard text and numeric field access, scroll-to-focus |
| C2 — Squeekboard UK keyboard and themes | ✅ Bounded trial demonstrated | British layout, compact numeric, private 23-palette stage |
| C3 — runtime hot CSS / native keyboard | 🟡 Active | Reliable day/night changes, stable input/focus, then practical persistent ownership |
| D — sun-aware night dimming | 🔜 Next enhancement | Fixed schedule or sunset→sunrise based on configured location |
| E — production readiness | ⏳ Later | Stable Plexamp build, reboot and crash recovery, cross-source integration |

## Do next — short acceptance path

### C3. Complete the keyboard rather than expand diagnostics

- [x] Verified native Squeekboard runs in labwc on the Pi, appears above native Plexamp with controlled session handover.
- [x] UK keys and compact numeric purpose; staged ACP themes (Classic Dark, Midnight Blue, astronomy).
- [x] Candidate-only GResource/GTK CSS can repaint within a running native process; red/blue handoff physically accepted.
- [x] Browser night preview events trigger the existing CSS bridge without keyboard restart.
- [x] Linux local input remains detectable with native Plexamp in front: six devices, `230 → 246`, last observed Logitech K800 key.
- [x] Chromium's existing 5-second C3 sync callback ran steadily behind fullscreen native Plexamp for 660 seconds (max gap 5.087 s, 0 gaps >15 s). This does **not** prove palette changes themselves.
- [x] Manual read-only browser/server night schedule comparison passed; Python-side schedule/observation parity test utilities are available.
- [x] Baseline Pi `--plan` for exact C3 artifact passed, original vendor OSK only, theme-sync disabled; ten focused `try-c3-night-boundary.py` tests passed.
- [ ] **Next physical acceptance:** test **day → night → day** across real clock schedule boundaries while native Plexamp Search stays in front. Verify keyboard *palette* and typing, not just callback cadence. The available schedule helper `scripts/try-c3-night-boundary.py` is optional; test-rig settings are freely resettable.
- [ ] Test tap, UK typing, compact numbers, Done/Cancel, Search focus and keyboard hide/show after palette switch in **one** regression pass.
- [x] Implement reversible, **untimed dev-session** systemd launch: `scripts/try-squeekboard-c3-dev.py` (`--plan` / `--start` / `--status` / `--stop`). ACP existing browser owns palette writes; no autostart/package changes and stock OSK restored on normal stop/candidate exit. **Physical Pi acceptance still pending.**
- [x] **19 October Pi result:** long-running C3 dev session beyond 180 s; one candidate PID **1895183**, stock absent, native keyboard works in ACP and fullscreen native Plexamp, theme changes follow ACP and persist between surfaces; after restarting the ACP service `/api/osk/c3/theme-sync/status` returns `enabled:true`.
- [ ] **Settings single-keyboard/scroll fix (CI GREEN: 1,494 tests, 3 skipped; Pi acceptance pending):** existing five-second theme-sync status GET now informs `ACPKeyboardChoice.setSystemActive()`; live C3 automatically suppresses ACP's old HTML keyboard, removes the five-minute choice dependency and restores the ACP fallback on a confirmed stop. The native focus-reveal CSS now scopes to stable `body[data-active-page="settings"]` rather than `body.mode-settings`, leaving the shell full-size while scrolling the right detail pane above the keyboard. Verify Weather forecast coordinates, WU Replace, News URL, numeric entry and return to ACP keyboard on `--stop`.
- [ ] Confirm the dev session stays usable over real day/night boundaries, preserves Plexamp Search focus, and restores vendor keyboard after `--stop`. Then plan the final reboot/startup owner.
- [ ] Verify re-entry/restart and error recovery; then mark C3 accepted.

**Keep basic safety, reduce ceremony:** a working stock OSK recovery path is important because losing all input is inconvenient; a seven-minute schedule rollback and new bespoke diagnostic subprocess for every normal display adjustment are not requirements for this test appliance.

### D. Night dimming from sunset to sunrise

**New agreed behaviour:** provide **Schedule mode: Fixed times / Sunset → sunrise** in Display → Night dimming.

- [ ] Reuse the **existing Weather forecast latitude/longitude/timezone and daily sunrise/sunset** from Open-Meteo, instead of asking for a second location.
- [ ] In sun mode, transition at **local sunset** and return at **local sunrise**, updating day by day; support optional offset minutes (sunset earlier/later; sunrise earlier/later) after basic flow works.
- [ ] Respect Europe/London BST/GMT and local dates; no assumption that sunrise/sunset remain fixed seasonally.
- [ ] If no coordinates or daily Sun times exist (or there is polar day/night), clearly show a status and **fall back to existing fixed 22:00–07:00** times; no mandatory network roundtrip at each boundary.
- [ ] Keep Classic/Astronomy night themes, alarm suppression, interactions, preview, bouncing Clock and native keyboard following the same resolved scheduled state.
- [ ] One small calculation/contract test set and one practical UK Pi acceptance; avoid exhaustive manual minute-by-minute rehearsals.

**Important:** Sunrise/sunset are the Sun crossing the horizon, *not* civil twilight/dusk. Twilight options can be added later if useful; begin with the literal sunrise/sunset request.

### B. Close native Plexamp once the keyboard works

- [x] Experimental ARM64 Plexamp Flatpak installed alongside accepted Headless rollback; native window launch/fullscreen and visualiser physically seen.
- [x] ACP ↔ native Plexamp nav/return paths integrated in the accepted Phase-A workspace shell.
- [x] Native versus Headless audio A/B runs without DSP errors in focused ten-minute tests; occasional single glitches and ALSA warnings were separately observed.
- [ ] Resolve any remaining real audio routing/CTL warnings without disrupting CamillaDSP, alarm bypass, music trim/EQ or AirPlay.
- [ ] Verify search, typing, media controls, return from ACP, alarms, AirPlay and NFC with the accepted native OSK.
- [ ] Confirm auto-launch, reboot/recovery and a suitable stable Plexamp channel; retain Headless until genuine physical sign-off.
- [ ] Document accepted user-facing operation and promotion/rollback.

## Phase A — accepted, no rework planned

**Complete:** A0–A4 same-document Clock, Weather, News, Settings and AirPlay; life-cycle, live refresh, scroll state and component/theme boundaries; persistent nav/home-indicator; spatial ordered row/long jumps; ACP–Plexamp handoff; Audio/Settings utility placement; normal/night transitions and dark-room bouncing Clock. Browser: Chromium physically accepted; a speculative Firefox switch is not on the current task list.

**Future slot:** `Home ↔ Weather ↔ Astronomy ↔ News ↔ AirPlay ↔ Plexamp`. Astronomy remains a separate post-#94 feature; avoid widening #94 into its full astronomy implementation.

## Quick developer commands

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
# Only needed after code changes in relevant modules:
venv/bin/python -m unittest discover -s tests -p 'test_squeekboard_theme_sync.py' -v
venv/bin/python -m unittest discover -s tests -p 'test_c3_night_boundary_guard.py' -v
# Normal preflight / optional bounded dev trial:
python3 scripts/try-squeekboard-hot-css.py --plan ~/acp-c3-hot-css-arm64-test-only.zip
python3 scripts/stage-squeekboard-hot-css.py --check
# Longer-running C3 session (manual stop, no autostart):
python3 scripts/try-squeekboard-c3-dev.py --plan ~/acp-c3-hot-css-arm64-test-only.zip
# python3 scripts/try-squeekboard-c3-dev.py --start ~/acp-c3-hot-css-arm64-test-only.zip
# python3 scripts/try-squeekboard-c3-dev.py --status
# python3 scripts/try-squeekboard-c3-dev.py --stop
# Live C3 trial is deliberate, disruptive and has its own 180s/240s recovery:
# python3 scripts/try-squeekboard-hot-css.py --start ~/acp-c3-hot-css-arm64-test-only.zip --theme-sync
```

Use `venv/bin/python` for Flask-dependent tests; system `python3` may not have Flask. For physical acceptance, one practical end-to-end test is better than repeating the same preflight and compiler checks after documentation-only commits.

## Dependencies and reference material

- [Master roadmap](../ROADMAP.md)
- [Astronomy feature (later)](astronomy.md)
- [Native Linux Plexamp architecture](../../development/architecture/native-plexamp-desktop.md)
- [Touchscreen text-entry architecture](../../development/architecture/touchscreen-text-entry.md)
- [Developer test catalogue](../../development/testing/test-catalogue.md)
- [C3 keyboard trial and schedule helper instructions](../../../scripts/README.md)

## History and evidence

- [**Archived entire detailed chronology (19 October 2026)**](../../archive/acp-shell-native-plexamp-full-history-2026-10-19.md) — original 1,900-line working log, preserved exactly; no loss of past decisions, commands, commits or tests.
- [Full project roadmap snapshot](../../archive/acp-roadmap-full-history-2026-10-19.md).
- Keep new accepted results here as **one checkpoint line per complete capability**, not many near-identical dated appendices.

**Finish line for #94:** Squeekboard works natively in Plexamp and ACP, night/day and sun mode both switch cleanly, native audio + app hand-offs behave correctly, and the development-only keyboard trial can be retired. Then build Astronomy.