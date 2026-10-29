# A Clockwork Plex — Project Roadmap

**Updated:** 29 October 2026 · **Published release:** v0.4.0 (23 August 2026)  
**Active development branch:** `feature/acp-shell-native-plexamp` · **Integration:** `develop` · **Stable:** `main`

> This is the **project-level overview**, not a test diary. A Clockwork Plex is currently running on a **development/test Raspberry Pi**, not yet a signed-off bedside appliance. Feature-specific requirements, acceptance results, defects and next checks belong in the linked [feature roadmaps](features/README.md) and [testing catalogue](../development/testing/test-catalogue.md).

## Project status at a glance

- **Core ACP features:** Clock, Weather, BBC News, AirPlay, Settings and the accepted high-resolution audio/mixer-EQ path are established. Current feature scope and any outstanding integration/merge gates are recorded individually below.
- **In active development — #94:** a unified native GTK shell for ACP pages and native Plexamp. C3 system Squeekboard and joined GTK navigation have passed bounded physical tests; the current Chromium-owned Audio mixer works but still causes **duplicate GTK/Chromium navigation during transitions**.
- **Selected architecture, not yet implemented:** host existing ACP HTML/CSS/JS pages in GTK3 + WebKitGTK; keep the native Plexamp Wayland Flatpak separate; use one GTK navigation owner and an Audio overlay that works over either app without switching focus. Preserve Chromium/Headless as rollback during migration.
- **Next milestone:** GTK/WebKitGTK renders all five ACP pages with the DMA-BUF renderer disabled (**11/11 focused tests PASS; 0.25–0.76s document loads**), but AirPlay animations are unacceptably slow and the decorated probe window supplies **853×418**, not 853×480, of content. Test a **process-only forced-shared-memory compositor** and real fullscreen viewport before starting shell migration or changing Weather CSS. **B4.4 installer/autostart remains deferred.**

## Feature portfolio

| Feature | Overall status | Summary / next decision |
| --- | --- | --- |
| [Weather (#86–#87)](features/weather.md) | **Core complete** | Forecast/location, observations, indoor expiry and rainfall accepted; detailed, Settings-style Weather redesign planned after the new shell foundation |
| [Settings and appliance ownership (#88–#90, #93)](features/settings-appliance-ownership.md) | **Complete for accepted ACP scope** | Portable configuration, Backup/Restore/Reset and rollback; native Plexamp-specific settings packaging remains #94 work |
| [Touchscreen text entry (#91)](features/touchscreen-text-entry.md) | **Complete for original ACP scope** | Native C3 Squeekboard extension is tracked under #94 |
| [BBC News (#92)](features/bbc-news.md) | **Complete** | Feed/cache/QR/refresh and theme/status semantics accepted |
| [High-resolution audio and mixer-EQ (#85)](features/high-resolution-audio.md) | **Physically accepted** | S32_LE / 192 kHz processing, CamillaDSP mixer/EQ, AirPlay and alarms preserved; feature file remains authority for outstanding merge gate and Direct source-rate-native work |
| [ACP shell / native Plexamp (#94)](features/acp-shell-native-plexamp.md) | **Active — Phase B** | GTK navigation and native focus accepted; **Audio visual UX unresolved**; GTK/WebKit shell prototype next, installer/startup later |
| [Astronomy](features/astronomy.md) | **Planned** | Touch-first Sun/Moon/planet/observing surface with shared location/time; reserved between Weather and News in future Spatial Row |
| [Appliance resilience](features/appliance-resilience.md) | **Planned, with investigations underway** | Storage/SD reliability, system time, offline recovery and future SSD/installer hardening |
| [Events calendar](features/events-calendar.md) | **Planned** | Touch-friendly, cache-first events with defined source and stale/offline behaviour |

## Current development milestone — #94

**Accepted on the development Pi:** native Plexamp Flatpak and exact focus identification; C3 Squeekboard layouts and night/day integration; single joined GTK drawer/indicator, theme parity, page routing, configured motion and inactivity, and bounded native Plexamp handoffs. Functional Audio open/close and return-to-origin also pass, including **9/9 Audio + 8/8 route tests** at the latest reported revision. Those are targeted test results, not a full release acceptance.

**Still open:** the current Chromium mixer competes visually with GTK navigation (two bars/animations); opening it from Plexamp requires a compositor handoff to ACP. The planned standalone overlay and GTK/WebKit shell have **not yet been built or tested**. No production B4.4 promotion, fresh-Pi installer acceptance, or complete backup/restore for the native Flatpak.

**Next development steps** (detailed scope/checks live in [#94](features/acp-shell-native-plexamp.md)):

1. Run the [#94 temporary GTK3/WebKitGTK GET-only renderer probe](features/acp-shell-native-plexamp.md) without removing Chromium; first verify page rendering, fonts/themes and performance. Same-document transitions and Squeekboard are later integration checks, not claimed by this probe.
2. Connect the accepted GTK navigation to the WebKit host and native Plexamp, then build an independent Audio overlay using the existing backend and EQ controls. Recheck no duplicate navigation and no unintended focus change.
3. Prototype a coordinated visual reveal for ACP ↔ native Plexamp. True live window embedding is **not** available through GTK3 on native Wayland; any snapshot-assisted Spatial Row is optional and must pass resource/focus tests.
4. After physical acceptance, complete B4.4 supervised startup, recovery, installer integration and native Plexamp Backup/Restore/Reset. Retain the known-good fallback.

## Planned follow-on work

- **Astronomy:** build on the unified page host, with shared coordinates, IANA timezone, twilight/rise/set and observing information; then provide the common Sun-event calculation authority for sun-aware display dimming.
- **Expanded Weather:** responsive, touch-friendly detailed/scrollable panels, historical trends and forecast/data-freshness status; preserve the current weather APIs and asynchronous ready/paint checks.
- **Sun-aware night mode:** sunrise/sunset-relative timing with offset controls, winter evening minimum and retained manual schedule.
- **Resilience and events:** develop against the settled UI/runtime, rather than hardening interfaces likely to be retired. Continue SD read-only/storage diagnosis and evaluate SSD where appropriate.
- **Audio maintenance:** leave source-rate-native Direct work deferred unless #94 acceptance or operational evidence changes the priority.

## Working rules and release gate

The Pi is a **test rig**: prefer focused tests plus one real, bounded acceptance trial per meaningful change; don't rerun already accepted suites without a regression. Protect the current CamillaDSP/ALSA alarm/music paths, avoid unexpected audio changes, and keep a straightforward return to stock Squeekboard and the existing Chromium/Headless display route.

For the next release: visually accepted unified UI and Audio overlay, functional native Plexamp, Squeekboard, alarm/AirPlay/NFC parity, restart/recovery and installer/upgrade/restore acceptance, plus CI coverage. **These release criteria are not all met.**

## Documentation and history

- [Feature roadmap index](features/README.md) — feature owners, scope and status.
- [#94 current feature roadmap](features/acp-shell-native-plexamp.md) — implementation detail, active decisions and gate results.
- [#94 detailed progress preserved through 29 October 2026](features/acp-shell-native-plexamp-progress-history-through-2026-10-29.md) — dated test history formerly in this overview; **historic entries are not current instructions**.
- [Development and testing catalogue](../development/testing/test-catalogue.md) — detailed evidence and test procedures.
- Historical snapshots: [19 October 2026 full project roadmap](../archive/acp-roadmap-full-history-2026-10-19.md), [Phase 7 checkpoint 6](history-through-phase7-checkpoint6.md), [checkpoint 64](history-through-checkpoint64.md).
