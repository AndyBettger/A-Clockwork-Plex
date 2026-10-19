# A Clockwork Plex Roadmap

**Updated:** 19 October 2026 · **Release:** v0.4.0 (published 23 August 2026)  
**Working feature branch:** `feature/acp-shell-native-plexamp` · **Integration:** `develop` · **Stable:** `main`

> **Development / test appliance, not yet a bedside production deployment.** Prefer useful physical end-to-end acceptance and fast iteration over long chains of staging gates. Keep a straightforward return to stock Squeekboard and avoid changing the accepted audio path, but ordinary display/keyboard settings can be changed and reset during testing.

## Current focus — #94 Phase B native Linux Plexamp

**Priority 1: finish one reliable system Squeekboard keyboard usable in ACP and native fullscreen Plexamp.** Native Plexamp is already running as an experimental Linux Flatpak alongside Headless; the ACP shell / transitions (Phase A) are physically accepted.

| Area | Status | Next useful action |
| --- | --- | --- |
| Shell, Settings, navigation, spatial transitions, night Clock | **Complete — physically accepted** | Maintenance only |
| Native Plexamp Linux launch / fullscreen / visualiser / ACP hand-off | **Working in discovery** | Keep Headless as fallback until final acceptance |
| Squeekboard UK text / compact number layouts | **Working in bounded trials** | Consolidate into a practical single-keyboard flow |
| Private Squeekboard CSS, ACP daytime / night palettes | **Live hot reload demonstrated** | Exercise *real* scheduled start/end in fullscreen Plexamp |
| Chromium C3 background callback while native Plexamp foreground | **Passed:** 660s, max gap 5.087s | No Python replacement scheduler warranted on this evidence |
| Linux input activity with Plexamp foreground | **Passed:** six devices, sequence 230→246, Logitech K800 key | Complete native touchscreen/focus acceptance |
| Squeekboard long-running C3 + automatic single keyboard | **Long-running/theming physically passed; Settings UI fix CI green / Pi pending** | ACP automatically suppresses its HTML keyboard when C3 is live; Settings focuses scroll above native OSK |
| Sunrise/sunset night schedule | **New feature — next implementation slice** | Add `Fixed times` / `Sunset → sunrise` setting with existing location/cached Sun data, DST and fallback |
| Production/reboot/crash recovery, native audio and stable release | **Still pending** | Close after keyboard is settled |

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
| 6 | [ACP shell / native Plexamp modernisation (#94)](features/acp-shell-native-plexamp.md) | **ACTIVE — Phase B / C3 native keyboard** |
| 7 | [Astronomy](features/astronomy.md) | **Queued:** once #94 native UI settled |
| 8 | [Appliance resilience](features/appliance-resilience.md) | **Queued** |
| 9 | [Events calendar](features/events-calendar.md) | **Queued** |

The UI foundation is already ready for Astronomy. Its reserved spatial slot is **Home → Weather → Astronomy → News → AirPlay → Plexamp**. Finish the native Plexamp/keyboard work first so new surfaces do not inherit a temporary input model.

## Next actionable development sequence

1. **C3: finish Squeekboard.** Physically verify automatic day→night→day palette changes with native Plexamp Search in front. Then exercise UK text/numeric keyboard, focus continuity, same process hot CSS, hide/show and fault recovery in one consolidated pass.
2. **Make the system keyboard usable after restart.** Introduce reversible user-session ownership rather than requiring a timed C3 development trial for every test. Keep the stock binary as fallback; no installation to global paths.
3. **Sunset/sunrise dimming.** Let the user choose fixed 22:00–07:00 or automatic local sunset→sunrise. Reuse forecast location and cached astronomy times, permit modest offsets, handle UK DST, lack of location, polar edge cases and stale data clearly; retain fixed times as fallback.
4. **Close Phase B.** Confirm native Plexamp audio, alarm/AirPlay/NFC handoff, touchscreen behaviour, focus, service recovery and eventual stable package candidate. Retain Headless until accepted.
5. **Move to Astronomy**, followed by resilience/calendar.

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
