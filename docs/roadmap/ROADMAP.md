# A Clockwork Plex Roadmap

**Updated:** 22 October 2026 · **Release:** v0.4.0 (published 23 August 2026)  
**Working feature branch:** `feature/acp-shell-native-plexamp` · **Integration:** `develop` · **Stable:** `main`

> **Development / test appliance, not yet a bedside production deployment.** Prefer useful physical end-to-end acceptance and fast iteration over long chains of staging gates. Keep a straightforward return to stock Squeekboard and avoid changing the accepted audio path, but ordinary display/keyboard settings can be changed and reset during testing.

## Current focus — #94 Phase B native Linux Plexamp

**Priority 1: native Plexamp shell integration.** C3 native Squeekboard is functionally accepted on the test Pi, including deliberate fallback/restart; installer packaging remains a release task. Native Plexamp is already running as an experimental Linux Flatpak alongside Headless; the ACP shell / transitions (Phase A) are physically accepted.

| Area | Status | Next useful action |
| --- | --- | --- |
| Shell, Settings, navigation, spatial transitions, night Clock | **Complete — physically accepted** | Maintenance only |
| Native Plexamp Wayland navigation | **B1/B2 prototype physically accepted** | 21 Oct: 12/12 Pi tests pass; native handle matches ACP responsive size, hover and height; last pixel comparison shows only a 1px horizontal-centre difference in the VNC capture, accepted as screenshot/scaling tolerance. Clean 90s shutdown, no GTK deprecation; previous taps and focus proved. **B3 keyboard/drawer physical proof passed:** Squeekboard D-Bus `Visible=False` when closed, `True` while native Plexamp Search opens C3 keyboard. Overlay disappears instead of rising above keyboard; touches on the diagnostic nav buttons register, Plexamp closes drawer, ACP focus request returns to the live Chromium toplevel; 4/4 focused tests pass. **21 Oct physical retest passed:** ACP-shaped drawer opens, raised handle, all button taps registered, keyboard hides/restores both, ACP escape focuses Chromium, 5/5 tests pass. **21 Oct B3 real-routing first Pi run: PARTIAL, not accepted.** 4/4 mailbox tests + 6/6 drawer tests; dashboard active, restarted, GET `/api/native-navigation/next` returned valid empty JSON. `--route-pages` Weather selection submitted successfully; labwc focus to Chromium succeeded, but ACP stayed on Home. Chromium was not confirmed refreshed to load the newly added JS bridge. **21 Oct real Weather routing PHYSICALLY PASSED after explicit Chromium refresh:** selecting Weather with native Plexamp forward navigates ACP; first attempt briefly showed existing Home before Weather, then ACP nav opened/hid on its regular timeout; repeat with Weather already active showed Weather directly. **21 Oct staged pre-focus Pi PARTIAL:** 6/6 bridge and 7/7 drawer tests, service/status PASS. Native Weather from ACP Home got `taken` twice for 10s while Plexamp remained foreground; manually focusing ACP then completed Weather. Repeating Weather after it was already active got `ready` and switched without Home flash. Evidence points to a Chromium background rendering/transition dependency; **22 Oct curtain Pi PARTIAL VISUAL PASS:** 9/9 bridge and 8/8 drawer tests; twice reached `ready`→ACP focus→`painted`→curtain fade, revealing Weather without a reported Clock flash. WayVNC captured duplicate native GTK/ACP navigation bars during the fade, plus a top Weather header band also present in the settled screenshot. The GTK Window opacity call emitted a deprecation warning. **22 Oct refined curtain Pi PARTIAL PASS:** 9/9 drawer tests; twice logged native drawer/handle hidden before curtain, Weather `ready`→ACP focus→`painted`→fade, without the GTK opacity warning or duplicate drawer. A new WayVNC screenshot reveals the remaining Weather title-over-blank-content interval before forecast/instrument panels render. `painted` after two rAFs was too early for Weather's separate asynchronous forecast fetch. **22 Oct current Weather handoff PROVISIONALLY ACCEPTED by user:** 10/10 bridge + 9/9 drawer tests passed; native Weather requested in background, Chromium reported route `ready`, focus succeeded, paint acknowledgment and curtain fade completed. User reports it looks better; the richer Weather presentation will be revisited with the planned expanded Weather page, alongside the future Astronomy page. This is NOT approval of all destinations, or spatial native-window animation. **22 Oct palette proof test run: 11/12 bridge and 11/11 drawer tests passed; the single bridge failure is an obsolete hard-coded asset version (`weather-ready-v5` vs current `theme-colors-v6`), NOT a runtime regression. Test corrected to require versioned JS asset references without pinning revision IDs; Pi rerun pending.** **New B3 theme parity prototype staged, Pi UNTESTED:** Chromium reports only the computed nine navigation colour tokens through a strict loopback, short-lived in-memory palette snapshot; GTK preview uses them only with `--theme-from-acp` and otherwise retains accepted Classic Dark CSS. No C3, audio or production boot changes. |
| Squeekboard UK text / compact numeric layouts | **Pi accepted in C3** | UK text, signed decimals/numeric pads, time QWERTY, and ACP Settings scroll verified |
| Private Squeekboard CSS, ACP daytime / night palettes | **Scheduled night → day physically accepted** | C3 automatically changed to Astronomy Red and back while native Plexamp stayed fullscreen; typing survived both changes |
| Chromium C3 background callback while native Plexamp foreground | **Passed:** 660s, max gap 5.087s | No Python replacement scheduler warranted on this evidence |
| Linux input activity with Plexamp foreground | **Passed:** six devices, sequence 230→246, Logitech K800 key | Complete native touchscreen/focus acceptance |
| Squeekboard C3 + one system keyboard | **COMPLETE on development Pi** | Stop restored vendor PID 45352 + ACP HTML keyboard; re-enabled/restarted C3 PID 47322, sync enabled. Installer-owned packaging still pending |
| Sunrise/sunset night schedule | **Deferred until Astronomy** | Use shared Sun calculations, seasonal offsets and sensible earliest evening start/wake limits |
| Fresh-Pi native installer, Plexamp profile Backup/Restore/Reset | **Required, not implemented for Flatpak** | Installer-owned C3 artifact + native Plexamp Flatpak, live portable settings, safe Reset, clean-Pi acceptance |

### Fast development/testing rules

- The Pi is a **test rig**: use compact checks and one real Pi acceptance pass per logical feature, not a new guard subsystem for every settings change.
- Keep an easily recoverable stock `/usr/bin/squeekboard` and existing audio/Headless routes. Recover a failed keyboard handover promptly; no duplicate keyboards or changes to `/usr/bin`.
- A display setting change is not a production incident. Record the baseline once, use and restore it as needed. Keep rigorous CI/static checks and short physical smoke tests.
- `scripts/try-c3-night-boundary.py` is an **optional existing guarded rehearsal**, not a prerequisite for ordinary development. Its read-only `--plan` was physically accepted; `--arm` has **not** been run.
- Keep detailed findings in [the feature roadmap](features/acp-shell-native-plexamp.md) and implementation/test catalogue, not repeated date-by-date paragraphs here.

## Agreed implementation order

| Order | Track | Status |
| ---: | --- | --- |
| 1 | [Weather (#86–#87)](features/weather.md) | **COMPLETE / MERGED**; enhancements queued |
| 2 | [Settings / appliance ownership (#88–#90, #93)](features/settings-appliance-ownership.md) | **Complete** |
| 3 | [Touchscreen text entry (#91)](features/touchscreen-text-entry.md) | **Complete** for browser ACP; native Squeekboard in #94 |
| 4 | [BBC News (#92)](features/bbc-news.md) | **Complete** |
| 5 | [High-resolution Plexamp audio / mixer-EQ (#85)](features/high-resolution-audio.md) | **COMPLETE / MERGED**; source-rate-native Direct deferred |
| 6 | [ACP shell / native Plexamp modernisation (#94)](features/acp-shell-native-plexamp.md) | **ACTIVE — Phase B native window navigation; C3 physically accepted** |
| 7 | [Astronomy](features/astronomy.md) | **Queued:** once #94 native UI settled |
| 8 | [Appliance resilience](features/appliance-resilience.md) | **Queued** |
| 9 | [Events calendar](features/events-calendar.md) | **Queued** |

The UI foundation is already ready for Astronomy. Its reserved spatial slot is **Home → Weather → Astronomy → News → AirPlay → Plexamp**. Finish the native Plexamp/keyboard work first so new surfaces do not inherit a temporary input model.

## Next actionable development sequence

1. **C3 complete on development Pi.** Native/ACP input, numerical and UK layouts, CSS, scheduled night/day, reboot autostart, stop-to-stock and return-to-C3 have passed. Do not repeat the trials; installer-owned C3 packaging remains separate.
2. **Phase B native Plexamp navigation.** **B1 focus handoff physically passed** (actual `Plexamp` and `chromium` Wayland IDs, both directions, no fullscreen state changes). ACP-owned touchable OVERLAY-layer indicator is visually accepted (within 1 VNC pixel), with safe edge hitbox and reversible B1 focus already accepted. **Next design a genuinely usable native overlay drawer while Plexamp remains visible**, reusing ACP navigation semantics for page selection and focus handoff; do not mistake a focus-only tap for a native navigation drawer or install an auto-start yet. Then address feasible cross-process transitions.
3. **Complete native Plexamp Phase B.** Build native nav/drawer and transition handoff, finish audio/alarm/AirPlay/NFC and recovery; **integrate native Flatpak + C3 into fresh-Pi setup and investigate native Flatpak Backup/Restore/Reset** before calling #94 release-ready. Retain Headless as fallback.
4. **Build Astronomy and shared Sun calculations.** Reuse the weather location/timezone for rise/set/twilight and deterministic local-time/DST handling.
5. **Add sun-aware dimming after Astronomy.** Use sunrise/sunset-relative sliders and a configurable **not-before evening time** to avoid dimming during winter afternoons; consider morning limits. Keep fixed 22:00–07:00 as an option. Then resilience/calendar.

## Maintenance queue

- Weather charts and richer history without unnecessary SD writes.
- Manual BBC News refresh is already physically accepted.
- Source-rate-native direct audio work remains deferred until after #94.

## Branch housekeeping

- Feature work stays on `feature/acp-shell-native-plexamp` until accepted, with docs/tests updated alongside real milestones.
- `develop` remains the integration target; `main` remains the published stable branch.
- Retired merged feature branches can be cleaned up later; don't switch branches simply to test keyboard themes.

## Feature roadmaps

See [feature index](features/README.md), especially [#94 Native Plexamp](features/acp-shell-native-plexamp.md) and [Astronomy](features/astronomy.md). Engineering architecture lives in [native Linux Plexamp desktop](../development/architecture/native-plexamp-desktop.md) and [touchscreen text entry](../development/architecture/touchscreen-text-entry.md).

## Release gate for the next version

Native Plexamp and Squeekboard accepted, audio/alarm/AirPlay/NFC preserved, restart and recovery validated, CI green, and installation/upgrade guidance updated. None of these is an obstacle to everyday **test-rig** iteration.

## History

Full chronology preserved before cleanup in [19 October 2026 project roadmap snapshot](../archive/acp-roadmap-full-history-2026-10-19.md); older snapshots: [Phase 7 / checkpoint 6](history-through-phase7-checkpoint6.md), [checkpoint 64](history-through-checkpoint64.md). **History is reference, not the current TODO list.**
