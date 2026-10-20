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
| C3 — runtime hot CSS / native keyboard | 🟡 Nearly accepted | Hot themes, single keyboard, field scrolling and decimal keypad passed on Pi; night boundary/startup/stop remain |
| D — sun-aware night dimming | ⏳ Deferred after Astronomy | Shared solar engine; seasonal offsets plus evening/morning clock limits |
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
- [x] **Untimed C3 dev session physically accepted:** `scripts/try-squeekboard-c3-dev.py` starts one native Squeekboard without a three-minute timeout; working theme hot-swap and fullscreen Plexamp typing observed. The original vendor startup remains available via `--stop`; its actual restoration after stop is still awaiting a Pi check.
- [x] **19 October Pi result:** long-running C3 dev session beyond 180 s; one candidate PID **1895183**, stock absent, native keyboard works in ACP and fullscreen native Plexamp, theme changes follow ACP and persist between surfaces; after restarting the ACP service `/api/osk/c3/theme-sync/status` returns `enabled:true`.
- [x] **Single-keyboard Settings UI and scrolling physically accepted:** C3 automatically suppresses ACP's legacy HTML keyboard; the actual Settings detail pane scrolls the focused latitude control clear of Squeekboard. Native Plexamp text and theme updates still work.
- [x] **19 October Pi numeric keypad acceptance:** compact Squeekboard numeric keyboard appears for latitude and signed fractional longitude, with minus and decimal keys; forecast coordinates retain precision, and Display night start/end show the intended time-capable QWERTY layout. C3 remains active, theme sync reports `enabled:true`.
- [ ] **20 October follow-up — concrete C3 startup failure located and corrected in code, Pi retest pending:** Running the desktop entry's exact `--startup` command manually with stock PID **1508** reached the C3 palette preflight, then failed `TrialError: C3 trial must initially show Classic Dark`. The private CSS stage retained a **valid but non-default palette** after prior theme changes. The old short trial intentionally starts Classic Dark; the untimed dev/login path now explicitly allows any *exact verified* C3 palette without changing CSS or bypassing checks. The bootstrap also reports preflight failure cleanly instead of surfacing a Python traceback. This proves why that manual attempt failed but **does not by itself establish** whether the XDG desktop entry was executed at login (no user journal files available). **Next:** pull, run direct `--startup` once, check single candidate and enabled theme-sync, then reboot to determine whether desktop XDG autostart actually invokes it. Do not switch startup mechanisms without this evidence.
- [ ] **20 October Pi reboot: C3 autostart FAILED, vendor fallback PASS.** XDG `~/.config/autostart/a-clockwork-plex-c3-dev.desktop` remained managed/enabled (`dev_autostart_enabled:true`), but after reboot `acp-squeekboard-c3-dev.service` was inactive, `state_present:false`, `theme_sync_eligible:false`, `/api/osk/c3/theme-sync/status` disabled, and only the genuine stock `/usr/bin/squeekboard` PID 1508 was running. ACP therefore showed its built-in keyboard, as expected without C3. This proves the fallback; **it does not prove** whether XDG autostart was skipped or `--startup` ran and exited with an error. Next gather current login/autostart entries and boot logs, then directly exercise `python3 scripts/try-squeekboard-c3-dev.py --startup ~/acp-c3-hot-css-arm64-test-only.zip` once with vendor running; if that passes, fix labwc/XDG startup invocation instead of rewriting the working keyboard. Verify login ownership on a later reboot, then final night boundaries and native Plexamp focus.
- [ ] Verify re-entry/restart and error recovery; then mark C3 accepted.

**Keep basic safety, reduce ceremony:** a working stock OSK recovery path is important because losing all input is inconvenient; a seven-minute schedule rollback and new bespoke diagnostic subprocess for every normal display adjustment are not requirements for this test appliance.

### D. Sun-aware night dimming — deferred until Astronomy

**19 October decision:** do not implement solar scheduling during C3 or before full native Plexamp navigation. Build one shared local Sun-event calculation authority in [Astronomy](astronomy.md), then add sun-aware night dimming as an Astronomy follow-on. The existing fixed 22:00–07:00 schedule remains selectable.

**Design idea to refine then:** sliders for signed sunrise/sunset offsets (hours and minutes), showing the actual resolved local time. Crucially, an offset alone would dim the screen in the middle of winter afternoons. Add a **not-before evening dim time** (example: later of sunset+30 min and 21:00), and consider morning limits so summer sunrise at 04:30 cannot brighten the appliance too early. Reuse weather coordinates, local timezone/DST and cached solar events. No need to build a separate astrology/astronomy calculation service within #94.

### B. Close native Plexamp once the keyboard works

- [x] Experimental ARM64 Plexamp Flatpak installed alongside accepted Headless rollback; native window launch/fullscreen and visualiser physically seen.
- [x] **Embedded/browser Plexamp only:** ACP ↔ the persistent Plexamp *iframe* has working nav, transitions, spatial-row sequencing and return paths in Phase A.
- [ ] **Native Linux Plexamp navigation (NOT IMPLEMENTED):** integrate the separately launched Flatpak Wayland window with ACP's nav indicator/drawer, switch-back navigation, and transition model. Current `scripts/launch-native-plexamp.sh --fullscreen` launches a separate Wayland toplevel; `app/static/js/plexamp-persistent.js` and `page-transitions.js` animate the browser iframe, **not** the native window. Ensure the active native player can reveal the ACP navigation while retaining focus, and support a reversible compositor/window handoff. This is Phase B work and has never had physical acceptance.
- [x] Native versus Headless audio A/B runs without DSP errors in focused ten-minute tests; occasional single glitches and ALSA warnings were separately observed.
- [ ] Resolve any remaining real audio routing/CTL warnings without disrupting CamillaDSP, alarm bypass, music trim/EQ or AirPlay.
- [ ] Verify search, typing, media controls, return from ACP, alarms, AirPlay and NFC with the accepted native OSK.
- [ ] Confirm auto-launch, reboot/recovery and a suitable stable Plexamp channel; retain Headless until genuine physical sign-off.
- [ ] Document accepted user-facing operation and promotion/rollback.

### B installer and configuration portability — **mandatory before #94 release**

The existing `setup.sh` / `appliance-installer.sh` fresh-Pi installation is built around **Plexamp Headless, Chromium and the distro keyboard**. Merely testing a manually staged C3 ZIP or launching a Flatpak does **not** make native Plexamp installable. Treat these as explicit development-to-installation acceptance gates:

- [ ] Extend the normal appliance installation system to select/download/verify a pinned **native Plexamp ARM64 Flatpak** and its runtime/permissions, with sensible upgrade/rollback and offline/error messages. Do not assume the beta Flatpak used on the bedroom Pi is an acceptable stable release.
- [ ] Package the validated C3 binary, UK layouts, compact numeric layout and GTK/CSS resources through a reproducible installer-owned artifact. Choose/repair the keyboard login startup owner as an install option; no dependency on a personal ZIP in `~/` or manually written labwc config.
- [ ] On a genuinely fresh Pi, prove setup installs the native app, selected output, Squeekboard, ACP navigation and 1280×720 UI with correct login/reboot ordering, and leaves stock keyboard/Headless as documented fallback where available. Installer must be idempotent and survive upgrades.
- [ ] **Investigate native Flatpak settings ownership for ACP Backup → Restore → Reset.** The current schema-v2 ACP Backup/Reset uses a browser-iframe Plexamp settings owner, a live Chromium bridge and Headless; this is **not evidence** that the separately launched Flatpak's profile at `~/.var/app/com.plexamp.Plexamp` is already covered. Inventory which preferences and Home/customisations are portable and which are account/session/machine specific.
- [ ] Design a **live native-owner adapter** for portable preferences and Home, with opt-in preview/apply/rollback for Backup/Restore and logical Reset (ordinary preferences, not application deletion or forced sign-out). Preserve account authentication, selected library and the selected ACP audio device unless the user explicitly chooses a wider reset. Never blindly copy Flatpak browser profile databases, identity tokens, cookies or credentials into the normal portable backup.
- [ ] Physically accept on a fresh second install: Backup on original → Restore on clean install → compare portable preferences and navigation; separately Reset → Preview convergence while account sign-in and audio are preserved. Document when fresh Plex sign-in/claim is unavoidable.

**Engineering split:** C3 login integration first; native Plexamp shell navigation/launch second; then installer and portability owner before Phase-B release. The [configuration backup ownership](../../development/architecture/configuration-backup-ownership.md) and [reset-to-defaults architecture](../../development/architecture/reset-to-defaults.md) remain authoritative for existing, browser-backed behaviour; don't conflate those with a separate Flatpak process.

## Phase A — accepted, no rework planned

**Complete:** A0–A4 same-document Clock, Weather, News, Settings and AirPlay; life-cycle, live refresh, scroll state and component/theme boundaries; persistent nav/home-indicator; spatial ordered row/long jumps; **ACP–embedded browser Plexamp iframe** handoff; Audio/Settings utility placement; normal/night transitions and dark-room bouncing Clock. Browser: Chromium physically accepted; a speculative Firefox switch is not on the current task list.

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

**Finish line for #94:** Squeekboard works in ACP and native Plexamp with day/night colours, native **navigation/drawer/transition handoff** is implemented and physically accepted, native audio + app handoffs work, and the development-only keyboard trial is replaced. **Sun-aware scheduling is not a #94 release blocker**; it follows Astronomy's shared solar calculations.