# A Clockwork Plex Roadmap

**Last updated:** 7 October 2026  
**Active integration branch:** `develop`  
**Active feature branch:** `feature/acp-shell-native-plexamp`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This is the project dashboard: what is complete, what is active, what comes next, and where the detailed feature roadmaps live. Engineering chronology belongs in the feature/development documents, not here. 😁

## Agreed implementation order

This is the authoritative product order.

| Order | Feature / track | Status | Next boundary | Feature roadmap |
| ---: | --- | --- | --- | --- |
| 1 | Weather (#86–#87) | **COMPLETE / MAINTENANCE MERGED** | Larger page revamp after #94 Phase A | [Weather](features/weather.md) |
| 2 | Settings & appliance ownership (#88–#90, #93) | **COMPLETE** | Maintenance only | [Settings / ownership](features/settings-appliance-ownership.md) |
| 3 | Touchscreen text entry (#91) | **COMPLETE** | Native-app text entry moves to #94 | [Touchscreen text entry](features/touchscreen-text-entry.md) |
| 4 | BBC News (#92) | **COMPLETE** | Maintenance only | [BBC News](features/bbc-news.md) |
| 5 | High-resolution Plexamp audio / mixer-EQ (#85) | **COMPLETE / MERGED** | Maintenance only; source-rate-native Direct remains deferred until post-#94 | [High-resolution audio](features/high-resolution-audio.md) |
| 6 | ACP shell / native Plexamp modernisation (#94) | **ACTIVE — PHASE A** | Shell-owned bottom-edge navigation | [ACP shell / native Plexamp](features/acp-shell-native-plexamp.md) |
| 7 | Astronomy | **QUEUED** | First new product surface on the accepted #94 UI foundation | [Astronomy](features/astronomy.md) |
| 8 | Native Plexamp completion / appliance resilience | **QUEUED** | Finish #94 native-player gates, then harden the resulting runtime | [#94](features/acp-shell-native-plexamp.md) · [Resilience](features/appliance-resilience.md) |
| 9 | Events calendar | **QUEUED** | Source/credential ownership first | [Events calendar](features/events-calendar.md) |

### Why #94 now precedes Astronomy

The #94 work is no longer merely “add a Plexamp visualiser”. It includes the ACP application-shell and navigation foundation.

Astronomy would otherwise be built as another full-document page and then immediately migrated. The efficient boundary is:

1. close and merge #85 — **complete**;
2. complete the bounded Weather rain-event maintenance branch — **complete / merged**;
3. complete **#94 Phase A** — **active**: single long-lived ACP web surface, component/design system, View Transition/navigation-shell prototype;
4. build Astronomy as the first new surface on that foundation;
5. complete the native Plexamp/player migration and then the full resilience track.

If native Plexamp discovery becomes a long side quest, Astronomy need not wait for every Phase B player/resilience gate once the Phase A application-surface contract is accepted.

## Maintenance queue

These are bounded corrections/improvements to accepted features; they do not change the main feature order.

- **Weather rain events — MERGED:** station-observation chronology, the **2-hour inter-event dry gap**, completed-event provenance and guarded rollover/out-of-order regression coverage are now in `develop`.
- **Weather page revamp:** after #94 Phase A, rebuild Weather as a sectioned application surface with useful graphs and investigate bounded local observation history/retention without creating avoidable SD-card writes.
- **BBC News manual refresh — PHYSICALLY ACCEPTED:** Settings → News **Refresh feeds now** successfully forces the existing validated feed service after connectivity recovery instead of waiting for normal cache TTL/background cadence.
- **Branch cleanup:** the merged News feature branches are safe to delete when branch housekeeping is explicitly performed.

## Current focus — #94 Phase A ACP UI foundation

The accepted Weather rain-event fix is merged into `develop`. The active branch is `feature/acp-shell-native-plexamp`.

Checkpoint A0 establishes the migration seam without changing current product-route behaviour:

- [x] ACP Surface Host loaded before the legacy page-transition owner.
- [x] Explicit `prepare() -> commit()` destination lifecycle.
- [x] Same-document View Transition ownership with a direct fallback.
- [x] `page-transitions.js` delegates only explicitly registered destinations.
- [x] Unmigrated routes retained the full-document fallback during staged migration; Clock, Weather, News, Settings and AirPlay are now all accepted mounted ACP surfaces.
- [x] CI syntax/catalogue coverage added.
- [x] Implement the first Clock ↔ Weather same-document surface pair with mount-once DOM ownership and lazy destination assets.
- [x] Replace Weather's timed full-page reload with in-place live updates that preserve vertical and Rain-history scroll position.
- [x] Clock ↔ Weather A1 physically accepted: faster same-document switching, no page flash/reload, correct mode/navigation, Clock continuity, Weather in-place refresh and stable repeated-visit controls.
- [x] Configured View Transition styles and duration physically accepted on Clock ↔ Weather.
- [x] Forecast custom-scrollbar visibility survives repeated Weather visits; News and Settings legacy fallback navigation physically accepted at A1.
- [x] A2 News same-document migration accepted: generic application-surface loader, hidden-refresh suspension, preserved News scroll state and settled-layout scrollbar ownership; exact candidate Tests #5087 passed and commissioned-Pi round-trips/transitions are physically accepted.
- [x] A3 Settings same-document migration physically accepted: Settings round-trips, controls/keyboard, autosave, live transition settings, Weather identity projection, Clock weather-title projection, first-paint behaviour and diagnostics all pass on the commissioned Pi. Combined A3/News follow-up candidate `a72079fcb9688aa47b086238866439a127c4299c` passed **Tests #5105**.
- [x] Post-A3 Weather presentation cleanup physically accepted: **Dashboard observation refresh** is removed from Settings; Clock/Weather still activate and refresh normally with their shell-owned visible-surface cadence.
- [x] A4 AirPlay same-document migration physically accepted: manual/automatic AirPlay projection, ready/idle presentation, metadata/artwork, transport/skip/volume controls, mini-clock/weather glance, hidden-surface catch-up, native Plexamp overlay return, active navigation/footer mode and repeated configured transitions all pass on the commissioned Pi. Candidate `2f351a9b83332c75cdd8d94d3ccebceb27362cf4` passed **Tests #5128**.
- [x] Converge all ordinary ACP-owned browser surfaces into the long-lived document: Clock, Weather, News, Settings and AirPlay are physically accepted. Native Plexamp remains the intentional separate application/workspace.
- [x] Establish the reusable component/design-token boundary for the ordinary ACP shell primitives. **Both bounded token slices are physically accepted:** Classic Dark and a non-Classic theme remain visually stable across Clock, Weather, News, Settings and AirPlay; Settings fields/selects, News touch/status UI, Weather/News/Rain custom scrollbars and the kiosk-safe dialog all pass commissioned-Pi checks. First-slice candidate `c751cd3eb50829d0937842965d0bed0581870e0c` passed **Tests #5168**; second-slice candidate `58be4c8ac64dde13c6f9537ca5a8db7a1fd4bdda` passed **Tests #5179** and docs-synchronised head `7dea1d736f4e28ca0d0efcdf8d35911ea6f9e152` passed **Tests #5180**. The next active Phase A boundary is shell-owned bottom-edge navigation.
- [~] Complete the shell-owned bottom-edge navigation and spatial workspace model:
  - [x] **Level A — production navigation shell accepted.** Home-indicator gestures, measured page/drawer movement, dim/backdrop behaviour, ACP↔Plexamp shell-state preservation, current-route no-op handling, Audio overlay ownership and AirPlay pre-snapshot hydration are physically accepted. Acceptance head `02af155ea2d536e774f5ef07a7c745ff80315f5c` passed **Tests #5252**.
  - [x] **B0–B1 — Clock ↔ Weather spatial row accepted.** The unreliable root-snapshot experiment was replaced by a live-DOM strip; outgoing layout/presentation is frozen correctly and both directions use one full-viewport movement with the configured total duration.
  - [x] **B2–B3 — News added and literal long-jump traversal accepted.** `Clock ↔ Weather ↔ News` behaves as a true ordered row; non-adjacent jumps visibly pass through intermediate surfaces without logically activating them, and semantic News warning chrome remains intentionally theme-independent.
  - [x] **B4 — AirPlay added and physically accepted.** `Clock ↔ Weather ↔ News ↔ AirPlay` passes adjacent and long-jump tests. AirPlay staging no longer corrupts session state, and travelling clones retain their computed screen format so no pre-motion vertical reflow occurs. Automated coverage is green through **Tests #5302**.
  - [~] **B5 — persistent-shell refinement functionally accepted; final typography check remaining.** The focused October 9 Pi retest passes the Lift+Spatial correction, Plexamp→Settings shell persistence, Motion control layout, themed pending/saving state and Classic Dark Audio glass. Overlay/Spatial layering, inactivity ownership, Audio timeout suspension, control height and rounded-rectangle geometry are accepted. The only remaining visual note is that workspace labels still read slightly small, so their font clamp has been increased by a further ~15% without changing accepted button height, horizontal padding or gaps. The previous implementation chain is green through **Tests #5354**; one final label-size CI/visual check remains. Plexamp remains outside Spatial-row traversal until B6.
  - [ ] **B6 — promote the row to shell-owned workspace topology.** Target order becomes `Home ↔ Weather ↔ News ↔ AirPlay ↔ Plexamp`; reserve Astronomy between Weather and News. Plexamp keeps the same terminal workspace position when its renderer later changes from the current persistent browser layer to native Wayland Plexamp.
  - [ ] **B7 — night-clock anti-burn-in bouncing cluster.** Add an optional transform-driven mode where time, date and alarm indicator move as one rigid group, reflect from safe-area edges and use an independent speed setting.
  - [ ] **Astronomy starts after B5–B7 are physically accepted**, using the reserved order `Home ↔ Weather ↔ Astronomy ↔ News ↔ AirPlay ↔ Plexamp`.


Do not start the native Plexamp production migration yet. Phase A first proves the ACP application-surface contract; Headless remains the accepted player runtime.

Detailed status: [features/acp-shell-native-plexamp.md](features/acp-shell-native-plexamp.md).

## Branch housekeeping

Current visible working branches:

- `main` — supported stable release branch.
- `develop` — accepted integration branch, including #85 and the merged Weather rain-event maintenance.
- `feature/acp-shell-native-plexamp` — active #94 branch.

The accepted Weather maintenance branch has been deleted after merge.

## Feature roadmaps

Feature-level progress lives under [`features/`](features/README.md):

- [Weather](features/weather.md)
- [Settings and appliance ownership](features/settings-appliance-ownership.md)
- [Touchscreen text entry](features/touchscreen-text-entry.md)
- [BBC News](features/bbc-news.md)
- [High-resolution audio](features/high-resolution-audio.md)
- [ACP shell / native Plexamp](features/acp-shell-native-plexamp.md)
- [Astronomy](features/astronomy.md)
- [Appliance resilience](features/appliance-resilience.md)
- [Events calendar](features/events-calendar.md)

Detailed architecture, test plans and physical evidence remain under `docs/development/`. Historical roadmap snapshots remain in this directory.

## Specialist authorities

- [High-resolution audio architecture](../development/architecture/high-resolution-audio.md)
- [AirPlay / hi-res physical investigation](../development/testing/airplay-hi-res-buffer-investigation.md)
- [Native Plexamp / ACP shell architecture](../development/architecture/native-plexamp-desktop.md)
- [BBC News architecture](../development/architecture/bbc-news.md)
- [Configuration backup ownership](../development/architecture/configuration-backup-ownership.md)
- [Reset-to-defaults architecture](../development/architecture/reset-to-defaults.md)
- [Appliance resilience architecture](../development/architecture/appliance-resilience.md)
- [Fresh appliance acceptance runbook](../development/testing/fresh-appliance-acceptance-runbook.md)

Normal appliance owners should start with [`../INSTALL.md`](../INSTALL.md), not the development roadmaps.

## Branch and release model

- `main` is the supported stable appliance and normal installation/update channel.
- `develop` is the integration branch for the next release cycle.
- substantial isolated work uses short-lived `feature/<name>` branches from `develop`.
- published `vX.Y.Z` tags/releases are immutable accepted snapshots.
- feature branches do not merge merely because CI is green: relevant Raspberry Pi/touchscreen behaviour must pass its physical acceptance gate first.
- the next release version is intentionally not assigned until its real scope is clear.

## Release gate for the next version

Before promoting the next development cycle to `main`:

- all included feature branches must be merged into `develop` only after automated and relevant physical acceptance;
- the clean-room installer/runbook must still pass on supported hardware;
- repeat `bash setup.sh` must remain safe/idempotent;
- repository/docs catalogues and these roadmaps must describe the actual shipped state;
- materially risky audio/storage experiments must remain isolated to feature branches with a known-good rollback/rebuild path through `develop` or `main`;
- release version/tag/name is assigned only after final scope and acceptance are known.

## History

- [history-through-phase7-checkpoint6.md](history-through-phase7-checkpoint6.md) — early Phase 7 chronology.
- [history-through-checkpoint64.md](history-through-checkpoint64.md) — pre-consolidation roadmap snapshot.

Those files are historical records, not current instructions.
