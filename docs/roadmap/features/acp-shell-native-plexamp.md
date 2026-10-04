# ACP shell / native Plexamp modernisation

**Issue:** #94  
**Status:** ACTIVE — Phase A UI foundation on `feature/acp-shell-native-plexamp`

## Why this moves before Astronomy

Astronomy is a rich new application surface. Building it in the current multi-document navigation model and immediately migrating it would be avoidable rework.

#94 therefore starts with the UI foundation first. Astronomy may begin once that foundation is physically accepted; it does not need to wait for every final native-Plexamp lifecycle/resilience gate if the application-surface contract is already stable.

## Phase A — ACP UI foundation

### Checkpoint A0 — fail-safe surface host foundation

- [x] Branch from accepted `develop` after #85 and the bounded Weather rain-event fix.
- [x] Add `app/static/js/acp-surface-host.js` as the future same-document surface lifecycle owner.
- [x] Define an explicit asynchronous `prepare() -> commit()` contract so destination work can be prepared before a DOM swap.
- [x] Use the browser View Transition API when available and transition settings allow it, with a direct synchronous commit fallback.
- [x] Let `page-transitions.js` delegate only destinations explicitly registered with the surface host.
- [x] Preserve the existing `window.location.assign()` route path for every unmigrated surface.
- [x] Add CI syntax checking and repository tests that pin the fail-safe/load-order contract.
- [x] Implement the first real ACP surface pair: **Clock ↔ Weather** now mount once inside the long-lived document, dynamically loading the other surface's CSS/scripts only when first visited.
- [x] Replace Weather's timed `window.location.reload()` with an in-place ACP-local refresh controller. The Weather grid refreshes without replacing the document, preserving vertical position and Rain-history horizontal scroll.
- [x] Keep screen-projection/manual-lease ownership in front of the visual commit and synchronise logical mode after same-document activation.
- [x] Preserve the full-document route fallback for News, Settings, AirPlay and all other unmigrated destinations.
- [x] Implementation CI green at `7eda544e26ea932ba44897fea696cb49e28cccbb`.
- [~] Physically compare Clock → Weather → Clock on the commissioned Pi: **core behaviour PASSED** — materially snappier, no black flash/full reload, active navigation/mode correct, Clock resumes correctly, Weather live refresh preserves reading position, forecast/wind/rain functionality intact.
- [x] Configured ACP transition styles physically retested: all styles now visibly differ on Clock ↔ Weather and the configured transition-duration setting is honoured.
- [x] Forecast Outlook custom horizontal rails physically retested across **first visit → leave Weather → second visit**; both rails remain visible and functional on subsequent visits.
- [x] Fallback navigation to unmigrated **News** and **Settings** remains correct after the A1 lifecycle fixes.

**Important:** A0 changes architecture ownership but deliberately changes **no current product route behaviour**. No Clock/Weather/News/Settings surface is registered yet; the accepted multi-document path remains the fallback.

- [ ] Prototype one long-lived ACP web document with top-level application surfaces instead of full document navigation.
- [ ] Move all ACP-owned top-level surfaces into that long-lived document: Clock, Weather, News, AirPlay, Settings, Astronomy and future application surfaces. Alarm remains ACP-owned as a forced/takeover surface. Native Plexamp is the deliberate cross-application exception.
- [ ] Replace full-document periodic refreshes with surface-owned live data updates that preserve scroll position, focus, open panels, modal state and horizontal scrollers. Routine data refresh must not trigger a top-level View Transition.
- [ ] Establish an ACP component/design system: data → reusable components → design tokens → application surfaces.
- [ ] Prototype browser View Transitions for ACP-to-ACP surface changes.
- [ ] Prototype the native ACP desktop shell: bottom home indicator, swipe-up navigation, transition/workspace ownership and optional system keyboard.
- [ ] Prototype the spatial row/carousel as navigation mode, with exactly one committed destination transition.
- [ ] Benchmark Chromium and Firefox on the commissioned Pi; keep Chromium unless Firefox shows a meaningful appliance-level advantage.
- [ ] Preserve the existing ACP look and themes.
- [ ] Physically accept touch, transition smoothness, startup/recovery and 1280×720 presentation.

## Phase B — native Plexamp

- [ ] Install current ARM64 Linux Plexamp reversibly alongside the accepted runtime.
- [ ] Confirm visualisers on the real Pi/display and measure CPU/GPU cost.
- [ ] Prove native Plexamp can feed the accepted `acp_plexamp` ALSA boundary without bypassing ACP audio ownership.
- [ ] Classify Companion/playMedia/timeline compatibility for existing NFC tags and playback observation.
- [ ] Prove touchscreen Search/text entry.
- [ ] Integrate native Plexamp as a second compositor workspace/surface under the ACP shell.
- [ ] Prove alarm/AirPlay arbitration, Direct failback, reboot/autostart and rollback.
- [ ] Keep Headless until every native-player gate passes.

## Detailed authority

- [Native Plexamp / ACP shell architecture](../../development/architecture/native-plexamp-desktop.md)

### 4 October 2026 A1 physical feedback

The first same-document Clock ↔ Weather test on the commissioned appliance validates the architectural direction:

- transition latency is noticeably lower than the old multi-document route;
- there is no black frame or page-bootstrap flash;
- mounted Clock remains live after a Weather round-trip;
- Weather background data refresh no longer resets vertical position;
- mode/navigation ownership remains in sync.

Two defects are classified as presentation-lifecycle follow-ups, not architecture blockers:

1. Chromium defaulted to a dissolve because the new View Transition snapshots were not yet mapped to ACP's configured transition-style keyframes.
2. Forecast strips measured their custom scrollbar geometry too early during first mounted-surface activation and could leave the rails hidden even though horizontal scrolling still worked.

The branch now maps ACP motion preferences onto View Transition root snapshots and explicitly remeasures Forecast rails over settled frames/activation events. Physical retest remains required.

### A1 follow-up — configured motion accepted; Forecast lifecycle hardened

Physical retest confirms ACP's existing transition-style and transition-duration preferences now drive the same-document View Transition path correctly.

The Forecast custom-scrollbar defect was narrowed further: rails are present on first Weather visit, disappear only after a leave/return cycle, and return after a full document refresh. This proves the strip content remains scrollable and isolates the problem to hidden mounted-surface geometry. The Forecast scrollbar now preserves its last known state when ResizeObserver sees zero-width hidden geometry and performs an authoritative remeasurement after the Surface Host emits `acp:surface-settled` once `transition.finished` resolves.

### A1 physical acceptance — COMPLETE

The Clock ↔ Weather same-document pair is physically accepted on the commissioned appliance.

Accepted behaviour:

- faster/smoother navigation with no full-document boot flash;
- all configured ACP transition styles and duration control honoured;
- active navigation/footer Mode ownership correct;
- Clock remains live after Weather round-trips;
- Weather refreshes in place without resetting reading position;
- Forecast rails remain visible and synchronised on first and subsequent visits;
- Rain controls remain functional;
- unmigrated News and Settings routes continue to fall back safely to the legacy full-document path.

Checkpoint A1 is therefore closed. Subsequent ACP surfaces may now migrate incrementally onto the same Surface Host contract.
