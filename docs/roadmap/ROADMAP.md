# A Clockwork Plex Roadmap

**Last updated:** 6 October 2026  
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
- [~] Prototype shell-owned bottom-edge navigation. **Lifecycle, refined home-indicator gestures and AirPlay first-paint correction are physically accepted:** Plexamp Library/Search taps are no longer intercepted, swipe-up/open and swipe-down/close work over Plexamp, tap fallback remains, and idle AirPlay first mount no longer flashes playback controls or reflows. Combined candidate `735cf5162fa37ef138ab3f2fca18ba97e5d19ee4` passed **Tests #5216** and docs-synchronised head `90f68352fb180d0afdee95b5c762cbe29445f0ec` passed **Tests #5218**. The active slice is now Level-A navigation mode: shell backdrop plus a small live-surface recede on ACP and Plexamp, preserving the current drawer/buttons and avoiding carousel/workspace complexity until this production-first treatment is physically accepted. Level-A navigation mode is physically sound across ACP and Plexamp: open/close, dimming, backdrop dismissal, manual ACP↔Plexamp shell-state preservation and normal auto-hide all pass commissioned-Pi testing. The full-scale treatment is preferred over the 0.84 recede, and the runtime-measured reveal height from `97b3b5f9323853b3f05699140740c53f5094b4e6` / **Tests #5243–#5244** is physically accepted for the live page: the ordinary drawer now sits at the right vertical boundary instead of covering the application or leaving a large gap. The dedicated **Navigation transition duration** setting is also physically accepted. The remaining Level-A polish identified on 6 October is threefold: (1) the home indicator still used a fixed 64/56 px path and generic easing, so at long navigation durations it visibly lagged the measured page motion; (2) Audio should remain a normal bottom-nav destination but open its mixer as an overlay above the current live surface, using the ordinary configured application Transition duration rather than enlarging the nav drawer; and (3) AirPlay can still be captured by a same-document View Transition before its segmented glance row/status-owned geometry has hydrated. The visible old News content on the right side of the reported first AirPlay screenshot is the expected **Cover reveal** old-snapshot half at the configured 2000 ms duration; the empty four-dot AirPlay mini-clock and subsequent geometry correction inside the incoming half are the real hydration bug. Candidate `007f6622e92645e5a5c597f2922f6e561c126f2d` addressed those three and passed **Tests #5245**, with documentation-synchronised head `515027990df2db89ff361ffaae17ef0b68acada2` passing **Tests #5246**. The 6 October commissioned-Pi retest accepts the indicator/live-page synchronisation, Audio overlay (including its transparent presentation and configured application-duration fade/lift), ordinary Audio timing ownership, AirPlay pre-snapshot hydration, repeated AirPlay returns and the existing Plexamp/Audio round-trips. One navigation motion mismatch remained: the drawer itself still used its older off-screen transform distance and generic `ease`, so at a deliberately slow 1000 ms setting the page/indicator moved together while the drawer visibly arrived later and remained behind while closing. The same retest also exposed a separate same-route bug: tapping the already-active ACP nav button fell through to the browser's default same-URL navigation, causing a black hard-reload flash and closing navigation. Candidate `eeca5a4fc6e5be87f0801008cb94e50cadbf6e40` made the drawer part of the same measured sheet—same `--acp-navigation-reveal-height`, duration and easing—and explicitly consumed already-active ACP nav taps as no-ops so nav mode remains open; it passed **Tests #5248**, with documentation head `2982de64c41c1492948a1e2937cf80fe82d503a6` passing **Tests #5249**. To match the user's “one piece of paper” requirement literally rather than only geometrically, final candidate `dc434d7a9e94604e167c2dc401d1dc42914aef1c` also removes the drawer's independent opacity fade: the drawer remains visible for the entire slide and is hidden only once the closed motion completes. It passed the full maintained suite as **Tests #5250**, and documentation-synchronised head `94b2985c9f1c23e3adab9b2f3ef3350c81b20e63` passed **Tests #5251**. **Level-A navigation is now physically accepted on the commissioned Pi:** page, home indicator and drawer move as one measured sheet at the configured Navigation transition duration; ACP and Plexamp preserve shell state correctly; auto-hide/backdrop dismissal remain correct; Audio is an accepted translucent overlay using ordinary Transition duration; AirPlay first-entry/re-entry geometry is stable; and tapping an already-active ACP destination is a consumed no-op with no black reload flash. Level-A acceptance head `02af155ea2d536e774f5ef07a7c745ff80315f5c` passed **Tests #5252**. The active Phase A slice is now **Level-B B0 — one bounded spatial-row commit**. To isolate presentation from lifecycle, B0 applies only when navigation is open on **Clock** and the user selects the adjacent **Weather** destination. After the manual-screen lease is accepted, navigation exits using the already-accepted Navigation transition duration; only then does the Surface Host perform exactly one same-document View Transition. That one commit temporarily overrides the configured reveal style with a deliberately obvious row movement: Clock travels left by 34vw while receding to 0.94 scale and Weather enters from +34vw/0.94 scale, using the ordinary configured application Transition duration. Every other destination and every direct/non-navigation Clock→Weather change remains on the accepted Level-A/configured-transition path. Initial head `34969583305a4867f3e47a6da258ee4bf7db67c1` exposed two stale regression-string assertions rather than product defects (**Tests #5253**); compatibility/cleanup head `60412c433ef8539e9c776fb228f47234e33878af` passed the full maintained suite as **Tests #5254**. The first commissioned-Pi B0 physical pass is **not accepted visually**: functional boundaries pass (one destination movement only, no Cover Reveal/black frame/reload/second Weather reveal, reverse and other destinations remain ordinary), but the spatial metaphor does not yet read as neighbouring surfaces. The 34vw + 0.94-scale composition exposes the document's white root behind the incoming snapshot—visible in the captured frame as Weather beginning at roughly 37% of the viewport—and the old Clock snapshot reads as a washed/grey backing layer while Weather slides over it. Refinement candidate `eb5cd5950152f9336dc5a0ac8b32bcf58fce4c95` removes scale and opacity choreography entirely and changes B0 to an **edge-locked one-viewport strip**: Clock moves `0 → -100vw` while Weather moves `+100vw → 0`, with identical duration/easing, so their adjoining edges remain coincident and no page background can be exposed. Physical retest is required before any B0 generalisation. Native Plexamp production migration remains blocked.

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
