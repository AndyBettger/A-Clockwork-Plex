# A Clockwork Plex Roadmap

**Last updated:** 30 September 2026  
**Active integration branch:** `develop`  
**Active feature branch:** `feature/hi-res-audio-eq`  
**Stable branch:** `main`  
**Current release:** **v0.4.0 — Unified Bedside Appliance — published 23 August 2026**

> This is the project dashboard: what is complete, what is active, what comes next, and where the detailed feature roadmaps live. Engineering chronology belongs in the feature/development documents, not here. 😁

## Agreed implementation order

This is the authoritative product order.

| Order | Feature / track | Status | Next boundary | Feature roadmap |
| ---: | --- | --- | --- | --- |
| 1 | Weather (#86–#87) | **COMPLETE** | Maintenance only | [Weather](features/weather.md) |
| 2 | Settings & appliance ownership (#88–#90, #93) | **COMPLETE** | Maintenance only | [Settings / ownership](features/settings-appliance-ownership.md) |
| 3 | Touchscreen text entry (#91) | **COMPLETE** | Native-app text entry moves to #94 | [Touchscreen text entry](features/touchscreen-text-entry.md) |
| 4 | BBC News (#92) | **COMPLETE** | Maintenance only | [BBC News](features/bbc-news.md) |
| 5 | High-resolution Plexamp audio / mixer-EQ (#85) | **ACTIVE — FINAL GATE** | Longer mixed-source production soak, journal inspection, merge to `develop` | [High-resolution audio](features/high-resolution-audio.md) |
| 6 | ACP shell / native Plexamp modernisation (#94) | **NEXT** | Phase A: single-document ACP surface, design system, shell/navigation prototype | [ACP shell / native Plexamp](features/acp-shell-native-plexamp.md) |
| 7 | Astronomy | **QUEUED** | First new product surface on the accepted #94 UI foundation | [Astronomy](features/astronomy.md) |
| 8 | Native Plexamp completion / appliance resilience | **QUEUED** | Finish #94 native-player gates, then harden the resulting runtime | [#94](features/acp-shell-native-plexamp.md) · [Resilience](features/appliance-resilience.md) |
| 9 | Events calendar | **QUEUED** | Source/credential ownership first | [Events calendar](features/events-calendar.md) |

### Why #94 now precedes Astronomy

The #94 work is no longer merely “add a Plexamp visualiser”. It includes the ACP application-shell and navigation foundation.

Astronomy would otherwise be built as another full-document page and then immediately migrated. The efficient boundary is:

1. close and merge #85;
2. complete **#94 Phase A** — single long-lived ACP web surface, component/design system, View Transition/navigation-shell prototype;
3. build Astronomy as the first new surface on that foundation;
4. complete the native Plexamp/player migration and then the full resilience track.

If native Plexamp discovery becomes a long side quest, Astronomy need not wait for every Phase B player/resilience gate once the Phase A application-surface contract is accepted.

## Current focus — #85 high-resolution audio

The commissioned managed audio path is physically accepted at **S32_LE / 192 kHz**. Plexamp, AirPlay, EQ controls, receiver-owned AirPlay volume, alarms, promoted Direct failback/recovery and truthful Source/Processing/DAC diagnostics have all passed their relevant physical gates.

### Remaining before merge to `develop`

- [ ] Run a longer ordinary mixed Plexamp/AirPlay production stability soak.
- [ ] Inspect a bounded CamillaDSP/Shairport journal for underrun, overrun, XRUN, stall, Broken pipe and error/fail recovery.
- [ ] Confirm final CI is green.
- [ ] Reconcile final docs/catalogues and merge the accepted branch to `develop`.

A true source-rate-native / bit-perfect Direct bypass is **not** part of this merge gate. The older roadmap mixed that later ambition into #85; it is deferred until #94 settles the future Plexamp runtime.

Detailed status: [features/high-resolution-audio.md](features/high-resolution-audio.md).

## Branch housekeeping

Current long-lived/visible branches:

- `main` — supported stable release branch.
- `develop` — accepted integration branch.
- `feature/hi-res-audio-eq` — active #85 branch.
- `feature/news-article-qr` — fully contained in `develop`; stale branch name only.
- `feature/news-custom-feeds` — fully contained in `develop`; stale branch name only.

The two News feature branches contain **no commits absent from `develop`** and are safe to delete after an explicit branch-cleanup action.

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
