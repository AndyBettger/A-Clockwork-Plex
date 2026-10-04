# A Clockwork Plex Roadmap

**Last updated:** 4 October 2026  
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
| 6 | ACP shell / native Plexamp modernisation (#94) | **ACTIVE — PHASE A** | First same-document surface migration on the new fail-safe surface-host contract | [ACP shell / native Plexamp](features/acp-shell-native-plexamp.md) |
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
- **Branch cleanup:** the merged News feature branches are safe to delete when branch housekeeping is explicitly performed.

## Current focus — #94 Phase A ACP UI foundation

The accepted Weather rain-event fix is merged into `develop`. The active branch is `feature/acp-shell-native-plexamp`.

Checkpoint A0 establishes the migration seam without changing current product-route behaviour:

- [x] ACP Surface Host loaded before the legacy page-transition owner.
- [x] Explicit `prepare() -> commit()` destination lifecycle.
- [x] Same-document View Transition ownership with a direct fallback.
- [x] `page-transitions.js` delegates only explicitly registered destinations.
- [x] Unmigrated Clock/Weather/News/Settings routes still fall through to the accepted full-document navigation path.
- [x] CI syntax/catalogue coverage added.
- [x] Implement the first Clock ↔ Weather same-document surface pair with mount-once DOM ownership and lazy destination assets.
- [x] Replace Weather's timed full-page reload with in-place live updates that preserve vertical and Rain-history scroll position.
- [~] Clock ↔ Weather physical A1 core passed: faster same-document switching, no page flash/reload, correct mode/navigation, Clock continuity and Weather in-place refresh.
- [ ] Retest configured View Transition motion and Forecast custom-scrollbar visibility after bounded fixes, then confirm fallback navigation to an unmigrated page.
- [ ] Converge all ACP-owned surfaces into the long-lived document; native Plexamp remains the intentional separate application/workspace.
- [ ] Establish the reusable component/design-token boundary.
- [ ] Prototype shell-owned bottom-edge navigation after the web-surface contract is proven.

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
