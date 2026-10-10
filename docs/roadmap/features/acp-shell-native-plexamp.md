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
- [x] Physically compare Clock → Weather → Clock on the commissioned Pi: **core behaviour PASSED** — materially snappier, no black flash/full reload, active navigation/mode correct, Clock resumes correctly, Weather live refresh preserves reading position, forecast/wind/rain functionality intact.
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

### A2 — News migration

A2 extends the accepted Surface Host contract from Clock/Weather to **News**.

Implementation:

- [x] Generalise the pair-specific loader into `acp-application-surfaces.js`.
- [x] Register Clock, Weather and News as the first mounted ACP application-surface set.
- [x] Expose News through the existing read-only `/api/surfaces/<surface>` endpoint without calling `set_mode()`.
- [x] Pause News data refresh work while the mounted News surface is hidden; refresh once when News becomes active again.
- [x] Preserve story/category scroll positions across routine News data refresh.
- [x] Make News story/category custom scrollbars ignore hidden zero-height geometry and remeasure on `acp:surface-settled`.
- [x] Retain article detail / QR handoff logic inside the mounted News DOM.
- [x] Keep Settings and AirPlay unregistered so their accepted full-document fallback remains available.
- [x] Exact A2 candidate `b4e0943038779862816e65f1e291ae2b4ef2e571` passed **Tests #5087**.
- [x] Commissioned-Pi physical acceptance passed: Clock/Weather ↔ News round-trips, News interaction/repeated visits and configured transitions behave correctly; Settings fallback remained intact during the A2 gate.


### A2 physical acceptance — COMPLETE

News is now physically accepted as the third mounted ACP application surface. The commissioned appliance confirms that repeated News visits no longer cause a full-document boot, the configured transition choreography remains correct, and the News page remains functionally intact after Clock/Weather round-trips.

Checkpoint A2 is therefore closed.

### A3 — Settings migration

A3 extends the same accepted application-surface contract to **Settings**, while preserving Settings' stronger transaction and UI-state ownership.

Implementation:

- [x] Register Settings alongside Clock, Weather and News in `acp-application-surfaces.js`.
- [x] Expose Settings through the read-only `/api/surfaces/<surface>` renderer without calling `set_mode()`.
- [x] Render the mounted Settings document with the normal Settings page context so server-rendered choices are not lost during lazy mounting.
- [x] Load Settings-only CSS/scripts lazily after the visual commit, when `body[data-active-page="settings"]` is already authoritative.
- [x] Preserve the mounted Settings DOM across ACP navigation so staged values, active section/subpage and modal/form state are not destroyed by a Clock/Weather/News round-trip.
- [x] Suspend alarm-diagnostics, lifetime-rainfall and live-audio-path network polling while Settings is not the active ACP surface; refresh again when Settings is reactivated.
- [x] Keep AirPlay unregistered so the established full-document fallback remains a clean escape path while A3 is proven.
- [x] A3 implementation passed **Tests #5089**; implementation + documentation candidate `2ca0997b1f063bc6a3a38c09a4d6ea2e04ab1d72` passed **Tests #5091**.
- [x] Physically test Clock/Weather/News ↔ Settings round-trips: same-document navigation/transition ownership passed.
- [x] Physically test Settings section/subpage controls, touch keyboard/selects and autosave persistence: passed.
- [x] Physically test Audio Hardware and alarm diagnostics after mounted-surface migration: passed.
- [x] Confirm AirPlay remains on the intentional full-document fallback: passed; its legacy transition remains intentionally unchanged until AirPlay migration.
- [x] Retest transition style/duration live projection: passed without hard document reload.
- [x] Retest mounted Weather identity projection: Weather page title/reporting-station name update correctly after autosave without hard reload.
- [x] Retest a hard reload directly on Settings: obsolete manual Save/Discard bar no longer appears during bootstrap.
- [x] Repeat Clock/Weather/News ↔ Settings circuit and keyboard interaction: passed.
- [x] Final A3 retest: Clock weather-panel title updates immediately after Weather identity autosave without a hard reload.

A3 must not weaken Settings transaction/autosave ownership merely to make navigation faster. A failed lazy mount/script activation still falls back to the ordinary `/settings` route.

### A3 first physical pass — core accepted, live-projection follow-up required

Commissioned-Pi testing confirms the mounted Settings architecture itself is healthy:

- Clock/Weather/News ↔ Settings navigation is correct;
- Settings sections, subpages, touchscreen keyboard and controls work;
- changes persist through the established autosave owner;
- Audio Hardware and alarm diagnostics render correctly;
- AirPlay remains a clean full-document fallback.

The first pass also exposed an architectural dependency left over from multi-document navigation. Autosaved values were correctly written to the server, but some visual/runtime configuration only became authoritative when Flask rendered a new document. In the long-lived ACP document this meant a new transition style/duration, Weather page title or reporting-station name could remain visually stale until a hard reload.

The follow-up removes that implicit reload dependency:

- validated Settings snapshots are projected back into `ACPDashboardPreferences`;
- dashboard-preference reads prefer the live document state after bootstrap rather than repeatedly falling back to server boot attributes;
- successful Weather-section autosaves emit an application event that invalidates the mounted Weather view, including the race where the user navigates away before autosave completes;
- the obsolete manual Save/Discard controls are hidden by Settings CSS from first paint instead of waiting for the autosave owner to initialise.

The previous A3 test wording mentioning manual **Save** and **Discard** was stale: the accepted Settings product uses autosave. The corrected physical gate tests autosave persistence and live projection instead.


### A3 second physical pass — one Clock projection remains

The second commissioned-Pi pass confirms the main persistent-document correction works:

- transition style and duration apply immediately to subsequent ACP transitions;
- Weather's detailed page title and reporting-station copy refresh from the saved Weather identity without a hard document reload;
- direct Settings hard reload no longer flashes the retired Save/Discard transaction bar;
- repeated Settings round-trips and keyboard interaction remain healthy.

The Clock page still showed the old Weather panel title until document reload. This is a separate mounted-surface refresh gap rather than a Settings persistence failure: `clock-dashboard.js` already reads the current title from `/api/status`, but its old fixed interval had no immediate Settings-save or Clock-reactivation hook.

The A3 follow-up now:

- listens for successful `acp:settings-saved` Weather transactions and refreshes the mounted Clock weather panel immediately;
- refreshes Clock weather/status whenever Clock becomes active;
- refreshes Clock weather/status without reloading the document;
- replaces the old permanently running interval with an active-surface timeout, so hidden Clock no longer polls weather/status unnecessarily.

The focused commissioned-Pi retest passed: the Clock weather-panel title now follows Weather identity autosave without a document reload. The Settings → News **Refresh feeds now** follow-up also works physically. Combined A3 Clock-projection and bounded News-refresh candidate `a72079fcb9688aa47b086238866439a127c4299c` passed **Tests #5105** (compile, JavaScript/page/shell checks and full regression suite).

### A3 physical acceptance — COMPLETE

A3 is closed. Settings is now the fourth physically accepted mounted ACP application surface. The accepted persistent-document contract covers transactional autosave, live shell configuration projection, affected-surface invalidation, hidden-surface polling suspension and first-paint-safe enhancement behaviour.

As a post-acceptance cleanup, the former **Dashboard observation refresh** field is retired from Settings and portable configuration. Clock and Weather presentation refresh now use a shell-owned 60-second cadence only while visible, with immediate refresh on activation and relevant Settings changes. Legacy `auto_refresh_seconds` values may remain in old config files but are ignored, so upgrades require no migration.

### A4 — AirPlay migration

A4 should migrate the remaining ACP-owned AirPlay page onto the accepted Surface Host contract without changing AirPlay playback/control authority. The work must preserve AirPlay's live metadata, artwork, mini-clock, playback/volume controls, hold/pause coordination and source-ownership behaviour while removing its current full-document transition boundary.

- [x] Audit AirPlay scripts for document-load/pagehide assumptions, timers and observers that need mounted-surface suspend/resume handling.
- [x] Add a dedicated AirPlay surface-lifecycle helper that distinguishes active AirPlay visibility from a merely mounted DOM, browser-hidden state and the native Plexamp overlay.
- [x] Register AirPlay as the fifth ACP application surface and expose its read-only surface document without changing mode during preparation.
- [x] Suspend/resume live metadata/status, coordinator transport/navigation, receiver-volume, adaptive skip-mode, outside-card and mini-clock work with surface visibility; remeasure layout/title presentation on activation.
- [x] Preserve AirPlay control-plane and audio authority unchanged; no Shairport, playback-coordinator, MPRIS or MixerController ownership moves into the shell.
- [x] AirPlay lifecycle candidate `2f351a9b83332c75cdd8d94d3ccebceb27362cf4` passed **Tests #5128** (compile, JavaScript/page/shell checks and full regression suite).
- [x] Physically test ACP ↔ AirPlay round-trips, ready/idle state, live metadata/artwork, transport/skip/volume controls, mini-clock/weather glance, automatic AirPlay projection, native Plexamp overlay return, active navigation/footer mode and configured transition motion: all passed on the commissioned Pi.
- [x] Keep native Plexamp separate; A4 completes the current ordinary ACP-owned top-level browser surface set once physically accepted.

### A4 physical acceptance — COMPLETE

A4 is closed. AirPlay is now the fifth physically accepted mounted ACP application surface. Manual navigation, automatic AirPlay projection, playback metadata/artwork, transport and navigation controls, receiver volume, weather/clock glance, hidden-surface catch-up and native-Plexamp-overlay return all behave correctly without reverting to full-document navigation.

This completes the ordinary ACP browser-surface convergence portion of Phase A.

### Post-A4 Settings hydration audit — candidate

Physical use after A4 exposed two related hydration races.

The first affected **Transition duration**:

1. Settings initially renders `display.transition_duration_ms` as a text input.
2. Unified Settings may hydrate a value such as 800 or 1200 ms before `settings-display-sections.js` upgrades the field.
3. The old upgrade changed `type` to `range` **before** setting `min=0` and `max=2000`.
4. Chromium therefore temporarily applied the HTML range defaults (0–100) and could clamp the already-hydrated value into that range.
5. A later Settings interaction/autosave could persist the clamped value.

The duration correction sets range bounds/step before changing input type, explicitly restores the pre-upgrade value, exposes the exact current millisecond value and repaints the range after hydration. Commissioned-Pi retest confirms the duration now remains stable across mounted round-trips and hard reloads.

The retest then exposed the same ownership problem in **Transition style**. The initial HTML only contained Grow and fade, Crossfade and Instant; the remaining accepted styles were added later by Javascript. If the local Settings API hydrated a value such as `vertical-lift` before that enhancement ran, the native select could not represent the value. The later option rebuild then fell back to the first option, **Grow and fade**, and a later autosave could persist that accidental fallback.

The follow-up is deliberately broader than one Motion field:

- all eight accepted transition styles now exist in the initial Settings HTML;
- Motion enhancement adds missing options non-destructively instead of replacing the select contents;
- legacy stored `none` is exposed canonically as the UI's `instant` value;
- the shared Settings hydrator preserves any valid saved select value that is not one of the current preset options by adding a temporary **Current saved value** choice rather than clearing it;
- custom select presentation receives an explicit `acp:settings-hydrated` signal instead of relying on the two-second safety refresh;
- dynamically inserted night-dimming, alarm-indicator and rainfall controls use the same hydration authority;
- numeric preset controls also resynchronise from the authoritative snapshot on hydration;
- save collection now starts from the authoritative loaded snapshot and rereads **only dirty Settings sections/providers**, preventing an unrelated stale control from overwriting another section;
- a direct `/settings` document load now participates in the hydration-aware first-paint gate, so template defaults are not deliberately revealed before the Settings API has resolved.

The code audit covered the currently loaded Settings enhancement owners, including Display/Motion, numeric presets, custom selects, Weather observation/rainfall controls, night dimming/interaction, alarm indicator, News provider UI, alarm editor ownership, AirPlay receiver ownership and read-only diagnostic enhancements. Alarm and News domain editors retain their own authoritative model/provider contracts.

One focused physical retest remains: select a non-default Motion style that was formerly Javascript-only (for example Vertical lift), wait for autosave, hard refresh Settings and confirm both the displayed style and subsequent transitions remain unchanged. The user does **not** need to manually retest every Settings value; the broader preservation/dirty-section contracts are regression-covered.

Settings hydration-audit candidate `92af74bbf9ed61d81b5a55ef4092cb5288d1ea01` passed **Tests #5152** (compile, Javascript/page/shell checks and full regression suite).


### Post-A4 Settings hydration physical acceptance — COMPLETE

Commissioned-Pi retest passes. A non-default transition style that previously existed only after Javascript enhancement now survives autosave and a direct hard reload, the selected style remains visible in Settings, the actual ACP transitions use that style, and the already-fixed duration remains stable.

The Settings hydration audit is therefore closed. The next active Phase A task is the reusable component/design-token boundary.



### Phase A component/design-system boundary — first slice

The post-A4 Settings hydration gate is closed, so Phase A has moved to the reusable component/design-token boundary.

Implementation candidate:

- [x] Add `app/static/css/acp-design-tokens.css` as a page-agnostic semantic vocabulary between the existing palette authority and application-surface CSS.
- [x] Keep the accepted palette variables (`--panel`, `--panel-border`, `--text`, `--muted`, `--accent`, `--accent-strong`) authoritative rather than creating a competing colour system.
- [x] Route shared `.panel`, `.weather-card` and `.button` primitives through semantic tokens with exact accepted values.
- [x] Route top-level AirPlay, Weather-detail and News container chrome through the same semantic palette/elevation boundary without changing their feature geometry.
- [x] Add regression coverage for token load order, palette derivation and first migrated consumers.
- [x] Document component/token ownership and incremental migration rules in [ACP component / design-token architecture](../../development/architecture/acp-design-system.md).
- [x] First component/token slice candidate `c751cd3eb50829d0937842965d0bed0581870e0c` passed **Tests #5168**.
- [x] Representative commissioned-Pi visual sanity pass accepted: Classic Dark plus a non-Classic theme remain stable across Clock, Weather, News, Settings and AirPlay; ordinary buttons, Clock Weather cards and main News/AirPlay/Weather panels show no visual regression.
- [x] Continue with the next safe reusable contracts: status pills, ordinary touch rows/buttons, form chrome, modal chrome and custom scrollbars. Keep specialised audio/weather/display geometry component-owned until separately justified.

This is intentionally an **ownership refactor, not a redesign**. Existing theme-closure sheets remain until a migrated component contract fully replaces their job and has been physically accepted.


### Component/design-system boundary — second slice

With the first slice physically accepted, the next bounded migration covers ordinary interaction chrome while preserving all accepted values:

- [x] Add shared form-control tokens for field border/fill/focus and field radius.
- [x] Keep the Settings field-container 7% neutral fill separate from the existing 8% card fill so tokenisation does not subtly change the accepted presentation.
- [x] Route native Settings fields and custom in-document select triggers through the same form-control tokens.
- [x] Route ordinary Settings subpage rows and News category/story touch surfaces through neutral component fills while preserving their existing geometry and active/focus states.
- [x] Route News/Weather status-pill radius and semantic foreground/border ownership through component/palette aliases without changing warning/stale states.
- [x] Give News vertical and Weather/Rain horizontal custom scrollbars one shared geometry contract: 8 px track, 4 px thumb and 42 px minimum thumb.
- [x] Route ordinary kiosk-safe modal text/accent chrome through semantic colour tokens; retain its existing modal geometry/background/elevation.
- [x] Extend static regression coverage across form, touch, modal and scrollbar consumers.
- [x] Second component/token slice candidate `58be4c8ac64dde13c6f9537ca5a8db7a1fd4bdda` passed **Tests #5179**.
- [x] Perform a bounded visual/interaction sanity pass on Settings fields/selects, News category/story/status UI, Weather forecast/rain rails and the kiosk-safe link dialog: accepted on the commissioned Pi, including a non-Classic theme.

Specialised warning/error/success paint, Settings alarm/audio controls, Weather gauge/compass presentation and media-specific AirPlay geometry remain component-owned.

### Component/design-system physical acceptance — COMPLETE

The reusable token/component boundary is now sufficient for the shell work: ordinary palette aliases, panel/card/button primitives, form/select chrome, ordinary touch rows, status-pill geometry, custom-scrollbar geometry and kiosk-modal semantic colours are physically accepted. Further componentisation should now be demand-driven by real reuse rather than continuing as a CSS-cleanup project in its own right.

The next Phase A task is **shell-owned bottom-edge navigation**.


### Shell-owned bottom-edge navigation — ownership slice

Before changing gestures or appearance, navigation ownership is being made real rather than simulated:

- [x] Render `_nav.html` once from `base.html`, alongside the persistent shell layers.
- [x] Remove `_nav.html` from Clock, Weather, News, Settings, AirPlay and Plexamp page templates.
- [x] Remove the obsolete `nav-layer.js` DOM-relocation shim that moved page-owned navigation out of `<main>`.
- [x] Simplify `acp-application-surfaces.js`: mounted surfaces no longer need special filtering to discard duplicate `nav-drawer` / `nav-handle` nodes.
- [x] Keep the current handle, swipe-up/tap behaviour, drawer, Audio mixer, active-state ownership and Plexamp overlay behaviour unchanged for this slice.
- [x] Add regression coverage proving there is exactly one shell-owned navigation include and no page-owned duplicates.
- [x] Shell-navigation ownership candidate `e352c40069e652cbae1ced9a02c7443342d896b1` passed **Tests #5191** on rerun attempt 2; the first attempt was cancelled before executing tests.
- [x] Hardened lifecycle retest accepted on the commissioned Pi: repeated mounted-surface navigation no longer requires forced refresh, tap/swipe reopen correctly on ACP surfaces, Audio remains present, mixer/EQ works and Plexamp→ACP handoff is stable. Remaining issue is specifically swipe initiation over the Plexamp iframe.


#### Shell-navigation lifecycle hardening

The first structural candidate proved that shell ownership alone was not enough. Physical use showed that persistent controls also need persistent **behavioural ownership**.

The hardened contract is:

- `nav-drawer.js` is one-instance guarded so it cannot silently accumulate duplicate tap/touch handlers in the long-lived document;
- bottom-handle tap/swipe handling is delegated from `document` and resolves the current `#nav-handle` rather than depending on one captured element instance;
- swipe-open suppresses the immediately following synthetic click so it cannot reopen-and-close in the same gesture;
- the Audio button is static `_nav.html` shell markup rather than an opportunistically injected button;
- Audio mixer setup is idempotent and reruns after `acp:surface-settled`;
- EQ content, EQ drawer placement and Audio drawer motion also reassert on surface settlement;
- nav lifecycle APIs forward to the current shell controller rather than holding stale drawer/handle references;
- asset versions were bumped so the Pi cannot combine the new shell template with an old cached navigation script.

The ownership/lifecycle correction is now physically accepted.

#### Home-indicator gesture slice

The first interaction slice addresses the remaining Plexamp boundary and gesture symmetry:

- [x] Replace the dark 116×30 navigation pill presentation with a small iPhone-style home indicator.
- [x] Keep the real button/gesture target wider than the visible bar so touch can begin on ACP-owned shell chrome even when Plexamp's iframe fills the display.
- [x] Bound that invisible target to 300 px maximum width × 30 px high so it does not become a large transparent interception layer over Plexamp controls.
- [x] Keep shell z-order above persistent Plexamp so the gesture target is reachable from the native-player overlay.
- [x] Closed + swipe up opens navigation.
- [x] Open + swipe down closes navigation.
- [x] Tap remains as a fallback.
- [x] Suppress the synthetic follow-up click after either swipe direction.
- [x] Version both nav CSS and Javascript so the Pi receives the new interaction layer together.
- [x] Add regression coverage for gesture symmetry, bounded hit geometry and shell-above-Plexamp z-order.
- [x] Home-indicator gesture candidate `8dffa93a04167ac4806974b2603c6e17f955d42a` passed **Tests #5204**.
- [x] Refined home-indicator physical retest accepted: Plexamp Library/Search taps including inner edges are no longer intercepted; swipe-up/open, swipe-down/close and tap fallback all work from Plexamp; Audio remains stable.


#### Refined Plexamp hit target + AirPlay first-paint correction

The first home-indicator candidate proved swipe reach over the Plexamp iframe, but its invisible target was too greedy. On the commissioned Pi, taps near the inner edges of Plexamp's Library and Search buttons could be intercepted by ACP and open the ACP drawer instead.

The refined contract is:

- the ACP gesture target is reduced from 300×30 px to roughly 180–200 px wide × 22 px high;
- the visible white home indicator grows to roughly 140 px, so the visible affordance now corresponds much more honestly to the usable swipe zone;
- ACP remains above the Plexamp iframe only in that narrow bottom-centre strip;
- swipe-up/open, swipe-down/close and tap fallback remain unchanged.

The same physical pass exposed an unrelated AirPlay first-mount flash: before `/api/status` resolved, the generic player layout briefly showed transport/volume controls and then collapsed into route-ready layout. AirPlay now stages an explicit `airplay-session-unresolved` state before first mounted commit (and on direct AirPlay document load). That unresolved state shares route-ready geometry and hides inactive controls. `airplay-live.js` removes the unresolved class atomically when the authoritative status response applies the real idle/active state.

Combined navigation/AirPlay candidate `735cf5162fa37ef138ab3f2fca18ba97e5d19ee4` passed **Tests #5216**.

The refined home-indicator and AirPlay first-paint slice is now physically accepted. Idle AirPlay first mount no longer flashes playback controls or visibly rejiggles.

#### Navigation-mode overlay/recede — Level A candidate

The next slice implements the production-first navigation treatment before attempting the spatial carousel:

- [x] Add a shell-owned backdrop between live application content and navigation chrome.
- [x] Keep the active ACP surface or Plexamp iframe live underneath rather than snapshotting/reloading it.
- [x] When navigation opens, apply a small 0.965 recede scale, 10 px upward translation and rounded edge treatment to the active application.
- [x] Use CSS individual `scale` / `translate` properties so navigation-mode motion can coexist with ACP's transform-based View Transitions and Plexamp handoff animations.
- [x] Extend Plexamp's own transition list so its recede animates smoothly rather than snapping.
- [x] Dim the live application with a shell scrim while keeping the drawer/indicator above it.
- [x] Make tapping the scrim dismiss navigation.
- [x] Respect reduced-motion preference.
- [x] Keep current drawer/buttons, Audio panel, gesture semantics and destination transition behaviour unchanged.
- [x] Add regression coverage for z-order, backdrop dismissal, recede geometry, reduced motion and Plexamp transition coexistence.
- [x] Level-A navigation-mode candidate `5ca3214cd942784025a6e39ed5c26ddd48a683b7` passed **Tests #5226**.
- [~] Level-A shell-state preservation now passes physically across ACP↔Plexamp, normal auto-hide still closes navigation, Audio is unchanged, and the deeper recede clears the drawer. The remaining work is visual refinement: full-scale lift candidate `1600e053bd18283a0de2016062fc6289ee6803d4` keeps the live application at 100% size and moves it upward instead of shrinking it; focused retest pending.



#### Level-A Plexamp consistency / deeper recede follow-up

Physical testing confirmed the Level-A visual model but found two refinements:

- ACP→ACP destination changes preserve the open drawer and receded new surface, while entering/leaving Plexamp still closed the drawer because `plexamp-persistent.js` explicitly called the nav lifecycle hide path.
- The original `0.965 / -10px` recede was too subtle for the current drawer height; the drawer still covered the lower portion of the live page.

The follow-up contract is:

- explicit manual shell navigation preserves `nav-open/nav-mode` across ACP→Plexamp and Plexamp→ACP;
- automatic screen-projection changes do **not** inherit an open drawer;
- Plexamp `show`, `hide` and `prepareNavigation` accept a presentation-only `preserveNavigation` option;
- Plexamp→the already-underlying ACP surface preserves nav without a reload;
- Plexamp→a different ACP surface carries a short-lived pathname-scoped `sessionStorage` navigation-mode token through the existing full-document fallback; `nav-drawer.js` restores the drawer before the booting document is revealed;
- the live application recedes to `0.84`, lifts `28px`, and uses a `28px` radius so its bottom edge sits above the ordinary navigation drawer rather than beneath it.

Candidate `d11bfd3f3574dda86a14bfdb1f3dbdccb5c913ac` passed **Tests #5233**.

The 6 October physical retest passes that cross-application contract. Manual ACP→Plexamp and Plexamp→ACP navigation keeps the drawer visible, including the different-ACP full-document path; auto-hide still works and Audio behaves as before. The `0.84 / -28px` geometry also succeeds at its original job: the live application's bottom edge clears the drawer.

#### Level-A full-scale lift refinement

Commissioned-Pi testing confirms the full-scale direction is visually better than the 0.84 recede: typography and controls stay at their normal size and the shell feels like it is temporarily borrowing display space rather than shrinking the application.

The first full-scale candidate used a 90 px lift. Physical feedback showed that this was too large; the next 28 px candidate moved too little and allowed the ordinary drawer to cover the bottom of the live page again. The visual target is now explicit: the top edge of the ordinary navigation drawer should meet the bottom edge of the lifted live surface, making the drawer appear attached beneath the page rather than floating over it.

The active refinement therefore:

- keeps `scale: 1` throughout navigation mode;
- removes the guessed fixed lift;
- measures the ordinary navigation strip at runtime from the main-nav row height, drawer vertical padding/borders and the drawer's bottom inset;
- writes that measurement to `--acp-navigation-reveal-height`;
- lifts ACP and Plexamp by exactly that measured amount;
- recalculates on navigation open, surface settlement and viewport resize;
- deliberately measures only the ordinary main-nav row, so opening the large Audio mixer does not suddenly shove the background application almost off-screen;
- retains the dim backdrop, rounded live-surface edge and exact normal geometry restoration when navigation closes.

The same pass also separates two previously mixed timing authorities. Before this refinement, the drawer/indicator themselves used a fixed 180 ms transition, while the backdrop and live-surface lift used `--acp-transition-in-duration`, derived from the ordinary Display → Motion page-transition duration. Navigation now has one dedicated timing contract:

- Settings → Display → Motion exposes **Navigation transition duration**;
- stored as `dashboard.navigation_transition_duration_ms` and surfaced as `display.navigation_transition_duration_ms`;
- default 180 ms, range 0–1000 ms in 20 ms steps;
- controls the navigation drawer, home indicator, dim backdrop and ACP/Plexamp lift/rounding;
- ordinary application-surface transition style/duration remains independent.

The setting is live-projected into the long-lived shell, included in portable configuration backup and defaults to 180 ms on existing configs that do not yet contain the key.

The 28 px candidate plus independent navigation timing passed **Tests #5241/#5242**. Physical testing accepts the independent Navigation transition duration, ACP↔Plexamp preservation, auto-hide and the existing Audio controls; only the 28 px geometry failed visually because the drawer again covered live content. Runtime-measured geometry candidate `97b3b5f9323853b3f05699140740c53f5094b4e6` then passed **Tests #5243**, with docs-synchronised head `27d32c16101761787d416c1bc9370a2499294b60` passing **Tests #5244**.

The 6 October physical retest accepts the **measured live-surface reveal height**: the page now rises by the right amount and the drawer no longer covers it. It also accepts the dedicated Navigation transition duration, ordinary destination switching, ACP↔Plexamp handling, normal auto-hide and Audio functionality. One visual mismatch remains in the home indicator itself: it still follows the historical fixed `64px/56px` path with generic `ease`, while the page follows the measured reveal height with the shell cubic-bezier. At a deliberately slow 1000 ms navigation duration this looks like the indicator is dragging through resistance rather than being attached to the page.

#### Indicator parity, Audio overlay and AirPlay snapshot hydration

Candidate `007f6622e92645e5a5c597f2922f6e561c126f2d` makes three bounded follow-ups:

- **Home indicator:** uses the same `--acp-navigation-reveal-height`, duration and `cubic-bezier(.16, .84, .24, 1)` as the live ACP/Plexamp surface. The fixed `-64px/-56px` offsets are removed, so the visible indicator should now move as part of the page/nav assembly rather than lagging it.
- **Audio:** the ordinary nav drawer no longer grows upward into a special Audio layout. Selecting Audio leaves the nav in its normal bottom position and opens the existing mixer as a fixed overlay above the current application surface. The mixer is shell-owned, remains above the dim backdrop but below ordinary navigation, and its reveal/hide uses the configured **application Transition duration** (`--acp-transition-duration`), deliberately independent of Navigation transition duration. The old `audio-polish.js` fixed 225/300/320 ms motion owner is retired to avoid two animation authorities fighting.
- **AirPlay first snapshot:** the Surface Host now supports an optional async `beforeSnapshot` hook inside the View Transition update callback. AirPlay marks each entry unresolved, loads/activates its surface scripts, waits for the reusable AirPlay hydration authority to report a settled status/segmented glance row, and only then lets Chromium capture the incoming snapshot. The existing `activate` stage remains the post-commit logical-mode owner.

The reported screenshot with AirPlay on the left and News still visible on the right is partly expected: with **Cover reveal** and a 2000 ms Transition duration, the old News snapshot remains visible while the new snapshot uncovers it. The genuine defect is visible *inside* the incoming AirPlay half: the mini-clock is still only its four static colon dots and the layout subsequently reflows after hydration. The pre-snapshot gate targets that defect without changing what Cover reveal is supposed to look like.

Candidate `007f6622e92645e5a5c597f2922f6e561c126f2d` passed the full maintained suite as **Tests #5245**, with documentation-synchronised head `515027990df2db89ff361ffaae17ef0b68acada2` passing **Tests #5246**.

The next commissioned-Pi pass accepts most of that slice:

- the **home indicator now moves exactly with the live page**, including at the intentionally slow 1000 ms Navigation transition duration;
- the **Audio overlay is physically accepted**: the normal bottom nav remains in place, the mixer fades/lifts over the live surface, the translucent glass treatment looks correct over both Plexamp and AirPlay, and changing ordinary Transition duration changes the overlay timing while Navigation duration remains independent;
- the **AirPlay pre-snapshot hydration gate is accepted** on first and repeated visits: the segmented mini-clock/weather/status geometry is stable during Cover reveal, with no later vertical correction;
- the existing ACP/Plexamp and Audio round-trips remain healthy.

The same slow-motion test makes the remaining drawer mismatch obvious. The page and indicator now share the measured distance and shell easing, but the nav drawer itself still starts from `calc(100% + 18px)` and uses generic `ease`. On opening the page/indicator therefore reach their destination first and wait for the drawer; on closing the page visibly moves down behind a drawer that is still catching up. The intended physical model is stricter: **live page, white indicator and ordinary nav bar are one sheet**. Their vertical deltas must be equal in magnitude and driven by the same easing/duration at every animation frame.

A separate interaction defect was also exposed: tapping the nav button for the **already-active ACP page** did not enter the Surface Host at all. The global link interceptor returned early for the same URL without calling `preventDefault()`, so Chromium performed a normal document navigation. That explains the black screen flash, page reappearance and lost nav state. Plexamp does not show the defect because its route is presentation-owned, and Audio is a button/overlay rather than an anchor.

Candidate `eeca5a4fc6e5be87f0801008cb94e50cadbf6e40` therefore:

- gives the nav drawer a closed offset of exactly `--acp-navigation-reveal-height` and the same `cubic-bezier(.16, .84, .24, 1)` as the page/indicator;
- changes the drawer from its historical transform path to the same individual `translate` contract used by the live surface assembly;
- treats an already-active ACP main-nav destination as an explicit consumed no-op, preventing the browser default reload and leaving navigation open.

The first code head correctly changed production behaviour but caused **Tests #5247** to fail on one regression assertion that still expected the retired same-URL early-return string. Updating that regression to express the new Plexamp-safe contract produced candidate `eeca5a4fc6e5be87f0801008cb94e50cadbf6e40`, which passed the full maintained suite as **Tests #5248**; documentation head `2982de64c41c1492948a1e2937cf80fe82d503a6` then passed **Tests #5249**.

Because the physical requirement is explicitly that page, indicator and navigation behave like **one piece of paper**, the final follow-up also removes the drawer's independent opacity transition. Candidate `dc434d7a9e94604e167c2dc401d1dc42914aef1c` keeps the drawer fully present for the whole measured slide, using delayed visibility only after the close completes, so there is no separate fade that can make a correctly positioned drawer still appear to lag. It passed the full maintained suite as **Tests #5250**, and documentation-synchronised head `94b2985c9f1c23e3adab9b2f3ef3350c81b20e63` passed **Tests #5251**.

### Level-A navigation physical acceptance — COMPLETE

The final commissioned-Pi retest passes all five focused gates:

- **one-sheet motion:** live ACP/Plexamp surface, white home indicator and ordinary nav drawer remain visually attached throughout both open and close, including the deliberately slow 1000 ms timing test;
- **Plexamp parity:** the same sheet motion works over Plexamp without regressing its persistent-overlay handoff;
- **current-route no-op:** tapping the already-active Clock, Weather, News, AirPlay or Settings button produces no transition, no black document reload and leaves navigation open;
- **Plexamp current destination:** the existing Plexamp-specific current-destination behaviour remains correct;
- **Audio overlay:** the accepted translucent mixer still fades/lifts over the current surface and remains independent of Navigation transition timing.

Together with the preceding accepted AirPlay hydration, ACP↔Plexamp shell-state, auto-hide and backdrop tests, **Level A is closed**. The production baseline is therefore a full-scale live surface with measured bottom-edge reveal, shell-owned navigation timing, a persistent home indicator/nav assembly, and Audio as an application-duration overlay.

The Audio overlay motion is intentionally **not yet a transition-style preset**. It is a one-sided component overlay animation (opacity + 18 px lift + 0.985→1 scale) over a still-live translucent background, whereas the Motion style list controls old/new whole-application View Transition snapshots. It is closest in character to Grow and fade but has a different compositing contract. A page-transition analogue can be considered after Level A is closed rather than mixing a new style into this acceptance gate.

Level-A documentation head `02af155ea2d536e774f5ef07a7c745ff80315f5c` passed **Tests #5252**.

### Level-B B0 — one bounded spatial-row commit

The first Level-B experiment is deliberately **not** a general carousel implementation. It proves one adjacent destination movement against the accepted Level-A shell before adding bidirectional ordering, snapshots or cross-application work.

B0 is restricted to this exact path:

```text
Clock + navigation open
        |
        | tap Weather
        v
manual Weather lease accepted
        |
        v
Level-A navigation sheet closes
(using Navigation transition duration)
        |
        v
ONE same-document View Transition
Clock  <----------------  Weather
        |
        v
Weather settled full-screen
```

Implementation rules:

- only the main-nav **Clock → Weather** path while navigation mode is already open receives `spatialCommitDirection: "forward"`;
- direct Clock→Weather navigation, Weather→Clock, all other ACP destinations, Plexamp and automatic screen projection remain unchanged;
- spatial selection deliberately opts out of Level-A's "preserve open navigation across destination changes" rule because the Level-B model says selection exits navigation before destination commit;
- the navigation sheet is allowed to finish its accepted close motion before the destination snapshot is taken, using `display.navigation_transition_duration_ms`;
- the Surface Host still calls `document.startViewTransition(commit)` exactly once;
- only for that one commit, `data-acp-spatial-commit="forward"` overrides the configured View Transition keyframes;
- the first B0 destination motion used outgoing `-34vw / 0.94` and incoming `+34vw / 0.94`; commissioned-Pi testing rejected that visual composition because it reads as Weather sliding over a faded/washed Clock backing and exposes the white document root at the incoming edge rather than as two neighbouring surfaces;
- the temporary spatial dataset is removed after the transition and also in the Surface Host fail-safe `finally` path;
- the accepted Level-A shell remains the production fallback if B0 feels gimmicky, janks on the Pi or proves too visually busy.

The first implementation head `34969583305a4867f3e47a6da258ee4bf7db67c1` failed **Tests #5253** only because two static regression assertions expected the pre-B0 source spelling for navigation preservation and `transition.finished.catch`. Production behaviour was not the failing condition. Compatibility/cleanup head `60412c433ef8539e9c776fb228f47234e33878af` preserves those accepted contracts, adds fail-safe spatial-dataset cleanup and passed the full maintained suite as **Tests #5254**.

#### B0 first physical pass — lifecycle passes, spatial presentation rejected

The commissioned-Pi result cleanly separates the architecture from the animation choice:

- [x] Clock → Weather selection first dismisses navigation.
- [x] Exactly one destination movement occurs.
- [x] No Cover Reveal follows it; there is no black frame, full-document reload or second Weather appearance.
- [x] Weather → Clock remains the ordinary configured transition.
- [x] Clock → News/AirPlay/Settings/Plexamp remain ordinary accepted behaviour.
- [ ] **Row metaphor:** failed. The old Clock surface becomes a pale/grey backing and Weather visibly slides over it rather than both pages reading as a continuous horizontal strip.

The captured transition frame explains the failure. With the incoming Weather snapshot translated by `34vw` and scaled to `0.94`, its left edge begins at approximately `34vw + 3vw = 37vw`. The screenshot shows almost exactly that much pure white document background before the Weather snapshot begins. Scale and opacity therefore introduced empty canvas/overlay cues—the opposite of the intended neighbouring-surface metaphor.

#### B0 v2 — edge-locked strip

Candidate `eb5cd5950152f9336dc5a0ac8b32bcf58fce4c95` keeps the existing one-commit lifecycle but simplifies the spatial composition to the strongest possible row invariant:

```text
Clock                       Weather
|<------ 100vw ------>|<------ 100vw ------>|
              ↓ same animation fraction
Clock shifts left one viewport while Weather shifts in
from exactly one viewport to the right.
```

- no spatial opacity change;
- no spatial scale change;
- outgoing Clock: `translateX(0) → translateX(-100vw)`;
- incoming Weather: `translateX(100vw) → translateX(0)`;
- identical configured application Transition duration and easing for both snapshots;
- the old right edge and new left edge therefore remain coincident throughout the movement, preventing the root background from opening between them.

#### B0 v2 second physical pass — row geometry works, outgoing snapshot races

The edge-locked geometry is a material improvement:

- [x] when the outgoing Clock snapshot is valid, Clock and Weather move together with a continuous vertical seam;
- [x] Weather no longer looks like an overlay floating over a grey Clock card;
- [x] the one-commit/no-reload/no-second-reveal behaviour remains intact;
- [x] reverse and unrelated destinations remain on their accepted configured transitions;
- [ ] **snapshot consistency:** intermittent failure remains. On many runs the region that should contain the outgoing Clock snapshot is solid white while Weather still follows the correct edge-locked path.

The paired screenshots are diagnostically useful. In the good frame, the left region contains the expected right-hand portion of Clock while Weather begins exactly at the moving seam. In the bad frame, Weather begins at essentially the same seam position but the entire outgoing region is white. This means the `±100vw` geometry is doing what it should; the problem is that Chromium sometimes receives/captures a blank old root texture before the spatial animation begins.

B0's navigation-exit boundary was timer based:

```text
hide navigation
      ↓
wait navigation duration + 24 ms
      ↓
startViewTransition()
```

That is not a strong enough compositor/paint contract on the Pi. CSS transition duration describes animation timing, not proof that the final composited application texture has been painted and is ready for a View Transition snapshot.

#### B0 v3 — compositor-settled snapshot barrier

Candidate `c2093f63b075db92d3b491ac2a820d8dfc003477` keeps the accepted edge-locked animation but strengthens the handoff:

1. install a listener on `main.screen` **before** closing navigation;
2. close the accepted Level-A sheet;
3. wait for the live surface's actual `translate` `transitionend` (or `transitioncancel`);
4. retain a conservative timeout only as a fail-safe;
5. after the CSS transition has really ended, wait for **two requestAnimationFrame turns**, with a `getBoundingClientRect()` layout read between them;
6. only then call the Surface Host / `document.startViewTransition()`.

The extra frames are intentional. The old-root image used by the View Transition is a compositor capture; the test must ensure the full-size Clock surface has actually survived the Level-A transform handoff and reached a paint opportunity before Chromium is asked to photograph it.

Candidate `c2093f63b075db92d3b491ac2a820d8dfc003477` passed the full maintained suite as **Tests #5258**, with documentation head `754a2a7d979dd2c556557ba0e0b947b789f61c93` passing **Tests #5259**.

#### B0 v3 repeated physical pass — REJECTED

The stronger nav-settle barrier did **not** cure the white outgoing surface. In 20 consecutive commissioned-Pi Clock→Weather transitions:

- **1/20** showed Clock correctly;
- **19/20** showed the outgoing Clock region as a plain white rectangle;
- Weather still followed the correct edge-locked path;
- there was still exactly one destination movement and no reload/double-reveal regression.

Because the failure became more frequent after adding extra post-nav settle time, the evidence no longer supports a simple "snapshot requested too early" explanation. The unreliable component is the **old-root View Transition texture itself** on this Pi/browser path. Continuing to add arbitrary delay would therefore be cargo-cult timing rather than an architecture fix.

#### B0 v4 — live-DOM spatial strip

The experiment now stops asking Chromium to provide an outgoing root snapshot.

Candidate `114b945f4bc132bbc14922eac045e582330703cd` keeps the accepted B0 selection policy and one-destination lifecycle, but changes the presentation engine only for this bounded Clock→Weather path:

1. after navigation has closed, clone the currently mounted **live Clock DOM** from `main.screen`;
2. preserve the current body background on that outgoing clone so it is visually self-contained;
3. place the real live `main.screen` one viewport to the right;
4. commit Weather into the real mounted surface;
5. animate the outgoing Clock clone `0 → -100vw` and the live Weather host `+100vw → 0` with the same configured application Transition duration/easing;
6. remove the temporary Clock clone and return the real screen to normal geometry;
7. continue the normal Surface Host activation/history/settled lifecycle.

This is intentionally **not** a second general transition framework. The Surface Host exposes a lifecycle hook (`prepared.spatialCommit`) for the one B0 relation; all ordinary ACP destination transitions still use `document.startViewTransition()`. If B0 is rejected, Level A remains unchanged.

Important side effect: the home indicator remains real shell chrome rather than being baked into a moving root screenshot. That is closer to the intended desktop-shell ownership model.

Automated coverage verifies:

- the B0 policy remains restricted to Clock→Weather from open navigation;
- the spatial path calls `prepared.spatialCommit` instead of root View Transition snapshot animation;
- the outgoing layer is a DOM clone of the current mounted screen;
- the incoming layer is the real live mounted Weather surface;
- both use exact `±100vw` edge-lock motion;
- cleanup always removes the temporary layer and inline transform;
- the retired `data-acp-spatial-commit` root keyframes are gone.

Candidate `114b945f4bc132bbc14922eac045e582330703cd` passed the full maintained suite as **Tests #5260**.

#### B0 v4 physical pass — live-DOM mechanism ACCEPTED

The commissioned-Pi retest accepts the new presentation primitive:

- [x] repeated Clock→Weather runs consistently keep the outgoing Clock surface present;
- [x] Clock and Weather remain joined at the moving seam with no white snapshot failure;
- [x] the home indicator remains shell-owned rather than baked into a root texture;
- [x] there is still one destination movement only, with no Cover Reveal, black frame, reload or second Weather appearance;
- [x] Weather settles fully live/interactable;
- [x] the same mechanism remains visually coherent after changing daytime theme, including Crimson Glow.

The mechanism is therefore good enough to keep. The next issue is **policy**, not rendering.

#### B0 v5 — integrate Spatial row into the custom Transition style system

Physical feedback correctly identifies that an always-on spatial Clock→Weather path would silently override the user's selected Transition style. B0 was allowed to do that temporarily to prove the mechanism, but production motion policy must remain user-owned.

The architecture is now:

- **Transition style remains authoritative.**
- Existing values—Grow and fade, Crossfade, Horizontal slide, Vertical lift, Cover reveal, Zoom, Blur dissolve and Instant—retain their existing behaviour.
- A new explicit **Spatial row (prototype)** choice opts into the Level-B live-DOM navigation model.
- The bounded live-DOM B0 path activates only when:
  - navigation is open;
  - Clock is the active ACP surface;
  - Weather is selected from the main nav;
  - the configured Transition style is `spatial-row`.
- With any other selected style, Clock→Weather uses that ordinary configured style exactly as before.
- While Spatial row remains incomplete, unsupported relations use the accepted **Horizontal slide** View Transition as a temporary fallback. This avoids inventing a half-implemented reverse carousel while still keeping the setting valid and predictable.
- Transition **duration** continues to apply to Spatial row's live-DOM movement.
- Navigation transition duration still owns only the drawer/page/indicator sheet opening and closing.

Candidate `24ead76bc2245332354637c5c301f7dac938beb2` adds `spatial-row` to frontend preference normalisation, Unified Settings validation, the Motion selector and the transition-style fallback mapping. It passed the full maintained suite as **Tests #5262**.

Physical B0-v5 gate:

- [x] Selecting another ordinary Transition style restores that configured transition rather than silently invoking Spatial row.
- [x] Selecting **Spatial row (prototype)** opts Clock→Weather into the accepted live-DOM strip.
- [x] Changing away from Spatial row immediately returns authority to the selected ordinary style.
- [ ] While Spatial row is selected, Weather→Clock and unrelated destinations should use the temporary Horizontal slide fallback without reloads or broken state.
- [x] Transition duration continues to control the live-DOM Spatial row speed.
- [x] Theme changes remain independent of transition-style choice.

Candidate `24ead76bc2245332354637c5c301f7dac938beb2` passed **Tests #5262**, with documentation head `41a05786fabd2998d83cc84f634c4526fd207051` passing **Tests #5263**.

#### B0 v6 — freeze the outgoing surface geometry

A new physical screenshot comparison exposed a small but real jank at the start of the spatial movement: the outgoing Clock's large time/date block jumps upward as soon as the strip begins, even though the stationary full-screen Clock was correctly laid out immediately beforehand.

This is not an animation-distance bug. It comes from **global destination CSS leaking into the outgoing live clone**:

```css
/* base Clock/main-screen geometry */
.screen {
  grid-template-rows: minmax(0, 1fr) auto auto;
}

/* destination Weather geometry */
body.mode-weather .screen {
  grid-template-rows: auto minmax(0, 1fr) auto;
}
```

The spatial compositor clones `main.screen` while Clock is active, but the normal Surface Host commit then changes `body.mode-clock` to `body.mode-weather` before the outgoing clone has finished travelling. Because the clone is still a `.screen`, Weather's screen rule immediately reflows the clone into Weather row geometry. The Clock weather panel happens to retain approximately the same vertical boundary, while the flexible hero row changes position, which is why the time/date visibly jump upward in the captured transition frame.

Candidate `646fe343b760879704804f73e0126cc061170494` fixes this without hard-coding Clock dimensions. Before the destination commit, ACP copies the outgoing screen's **computed layout contract** onto the clone as inline values:

- grid template rows/columns;
- grid auto-flow/auto tracks;
- alignment;
- row/column gaps;
- screen padding.

The outgoing layer is therefore layout-frozen in its real pre-transition geometry while the incoming live `main.screen` remains free to adopt Weather's destination-specific layout. This is the correct ownership boundary for a two-surface compositor: the old surface keeps its old geometry for the duration of the handoff; the new surface uses new geometry immediately.

Candidate `646fe343b760879704804f73e0126cc061170494` passed the full maintained suite as **Tests #5264**.

Focused physical B0-v6 gate:

- [x] Stationary Clock and the first moving frame retain the same time/date/alarm/weather-panel geometry.
- [x] Clock translates left without internal reflow.
- [x] Weather adopts its normal detailed-layout geometry while entering from the right.
- [x] The seam remains edge-locked and the accepted theme/style-selection behaviour remains intact.

### Level-B B0 physical acceptance — COMPLETE

B0 now proves the key spatial-row mechanism on the commissioned Pi: explicit style opt-in, live-DOM rather than unreliable old-root snapshots, one committed destination lifecycle, edge-locked viewport motion, per-surface outgoing layout preservation, theme independence and correct Transition-duration ownership.

The accepted implementation lineage is:

- live-DOM pivot `114b945f4bc132bbc14922eac045e582330703cd` / **Tests #5260**;
- explicit Spatial-row style `24ead76bc2245332354637c5c301f7dac938beb2` / **Tests #5262**;
- outgoing-layout freeze `646fe343b760879704804f73e0126cc061170494` / **Tests #5264**;
- final docs/status heads **#5265–#5266** green.

#### B1 — ordered, bidirectional Clock ↔ Weather row

The next experiment adds the smallest real row model rather than another special-case reverse animation. The row order is currently:

```text
Home  <---->  Weather
index 0         index 1
```

Navigation derives direction from those indices:

- Clock → Weather = **forward**;
- Weather → Clock = **reverse**;
- only adjacent implemented row members receive the live-DOM Spatial-row compositor;
- all other destinations under Spatial row continue to use the documented Horizontal-slide fallback.

The application-surface compositor mirrors the same two-item order and validates the requested direction against the actual outgoing/incoming pair. The existing live-DOM path is now direction-neutral:

- **forward:** outgoing `0 → -100vw`, incoming `+100vw → 0`;
- **reverse:** outgoing `0 → +100vw`, incoming `-100vw → 0`;
- both preserve the outgoing surface's computed layout before destination body-mode changes;
- both use the configured application Transition duration/easing;
- both retain the same Surface Host commit/activate/history/settled ownership.

Candidate `d8b74c0d83036544d6b352c33768bfdc1c46ff8c` implements B1 and passed the full maintained suite as **Tests #5267**.

Focused physical B1 gate:

- [x] Clock → Weather still looks exactly like the accepted B0 movement.
- [ ] Weather → Clock performs the mirrored Spatial-row movement: Weather leaves right while Clock enters from the left.
- [ ] The moving seam remains joined in both directions with no white gap, overlap or internal page reflow.
- [ ] Clock and Weather both settle fully live/interactable after their respective incoming movements.
- [ ] Transition duration affects both directions equally.
- [ ] Selecting any non-Spatial transition restores the normal configured style in both directions.
- [ ] News/AirPlay/Settings/Plexamp remain outside the ordered row for B1 and keep their existing Spatial-row fallback/accepted behaviour.

#### B1 first physical pass — reverse direction was discarded by the host

The screenshots initially look like a compositor problem because Weather fades away while Clock becomes visible underneath, with only a very short lateral movement. The code path explains that exact visual:

1. navigation's ordered-row logic correctly derives `reverse` for Weather → Clock;
2. `page-transitions.js` passes `spatialCommitDirection: "reverse"`;
3. the Surface Host still contained the older B0 normaliser:
   ```js
   options.spatialCommitDirection === 'forward' ? 'forward' : ''
   ```
4. `reverse` was therefore converted to an empty direction **before** the application-surface `spatialCommit` hook;
5. the host fell back to its ordinary View Transition path;
6. because the selected style is Spatial row and unsupported relations still temporarily map to Horizontal slide, Chromium ran `acp-out-horizontal-slide` / `acp-in-horizontal-slide`: only ±4–5vw plus an opacity fade.

That is precisely the fade/overlay effect captured in the physical screenshots. The live-DOM reverse compositor itself had not actually been exercised.

Candidate `8a3b300a7e9d55807aaa3d76993689260f5356ac` changes the Surface Host direction contract to accept both `forward` and `reverse`, with regression coverage so a future refactor cannot silently collapse reverse back to the fallback path. It passed the full maintained suite as **Tests #5269**.

The same physical pass exposed a separate small theme defect on Weather: `.weather-forecast-status` had theme-owned border/background but its text still inherited `var(--acp-color-accent)`, leaving **Forecast Ready** cyan under Amber Terminal and Crimson Glow. The correction gives **non-stale** forecast status text `var(--accent-strong)` in the non-Classic theme layer; `.is-stale` deliberately keeps its semantic warning colour.

Focused retest:

- [x] With Spatial row selected, Weather → Clock now uses the full live-DOM reverse strip rather than the short fading Horizontal-slide fallback.
- [x] Weather travels right while Clock enters from the left.
- [ ] The moving seam/no-gap/no-internal-reflow contract still needs one final explicit acceptance pass after the styling correction below.
- [x] Forecast Ready follows the selected daytime theme; stale-warning colour remains semantic.
- [x] Clock → Weather remains unchanged.
- [ ] The outgoing Weather surface must retain its selected theme colours—including both forecast scroll rails—for the entire reverse movement.

#### B1 second physical pass — outgoing Weather lost global theme context

The reverse compositor is now genuinely running, but the screenshots expose a different class of problem: while Weather is stationary its custom forecast scrollbar is Crimson/Green as expected; the instant the reverse slide begins, the outgoing Weather scrollbar changes to Classic cyan.

This is the styling equivalent of the earlier Clock layout leak. The live outgoing layer is a clone of `main.screen`, but the normal destination commit changes the **global** document state to Clock before that Weather clone has left the viewport. Weather's non-Classic component rules were scoped like:

```css
html[data-daytime-theme]:not([data-daytime-theme="classic_dark"])
body[data-active-page="weather"] .weather-forecast-scrollbar-thumb { ... }
```

Once `body[data-active-page]` becomes `clock`, those selectors stop applying to the still-visible outgoing Weather clone. Its markup then falls back to the base forecast CSS, whose historical default is cyan. Clock→Weather does not show the bug because Weather is the **incoming** live destination and therefore owns the global Weather state throughout its entrance.

The compositor now gives each outgoing clone an explicit local presentation identity:

```text
data-acp-surface-context="weather"
```

Weather's non-Classic component selectors accept either the live global Weather body state **or** an outgoing clone carrying Weather context. That preserves the selected palette without freezing pixels or copying dozens of computed colour values. Candidate `5ca3ad46c511451fa8aa971332d33f7779b5046a` implements the theme-context contract and passed **Tests #5271**.

A follow-up audit found the forecast console itself also had two active-page-scoped layout rules. Candidate `5a0b5313f593d92d949fba6989e93cda0d74b6e7` extends those rules to the same outgoing Weather context, preventing width/margin changes during the reverse handoff as well. **Tests #5272** found only a stale cache-bust expectation in `test_weather_forecast_ui.py`; candidate `a8d7ffc24b26b4543406049f73dc79e1aa6c7e61` updates that assertion and passed the full maintained suite as **Tests #5273**.

Focused B1-v3 retest:

- [x] Under Crimson Glow, Weather's forecast rails remain Crimson from stationary state through the entire Weather→Clock slide.
- [x] Under Green Phosphor, the rails remain Green rather than reverting to cyan.
- [x] Forecast Ready and the other Weather theme accents remain palette-owned while the page is leaving.
- [x] The reverse movement continues to use the full live-DOM strip rather than the fade fallback.
- [x] Clock→Weather remains unchanged.

### B1-v3 outgoing presentation-context acceptance — COMPLETE

The outgoing Weather surface now carries enough local identity to remain visually Weather after the live document has already committed Clock. The commissioned-Pi retest confirms that the custom forecast rails no longer lose their daytime-theme palette during the reverse handoff. This closes the theme/presentation-context defect that followed the earlier layout-context fix.

The remaining B1 acceptance work was about the **two-way row as a whole**, not Weather styling:

- [x] no seam gap/overlap or internal reflow appears in either direction over repeated runs;
- [x] both incoming surfaces settle fully live/interactable;
- [x] Transition duration affects forward and reverse equally;
- [x] choosing a non-Spatial transition restores that configured style in both directions;
- [x] News/AirPlay/Settings/Plexamp remain outside the B1 row and retain their documented fallback/accepted behaviour.

### Level-B B1 physical acceptance — COMPLETE

The commissioned Pi now accepts the full two-member ordered row: Clock↔Weather is symmetric, edge-locked, theme/layout-context safe, duration-owned and opt-in through the existing Transition style system.

#### B2 — add News as the third adjacent row member

The next step expands only one position in the existing navigation order:

```text
Home  <---->  Weather  <---->  News
  0               1              2
```

B2 intentionally keeps **adjacency** as the spatial-commit rule:

- Clock↔Weather remains the accepted B1 live-DOM strip;
- Weather→News is a new **forward** live-DOM strip;
- News→Weather is the mirrored **reverse** live-DOM strip;
- Clock↔News is non-adjacent, so for B2 it deliberately keeps the documented Horizontal-slide fallback rather than inventing long-jump behaviour;
- AirPlay, Settings and Plexamp remain outside this row slice.

News is a good third member because it is already a physically accepted mounted ACP surface and its primary page styling is token/local-component based rather than depending on a body-mode screen-grid override. The existing compositor still freezes the outgoing root-screen geometry and stamps source-surface presentation context, so Weather retains its accepted layout/theme identity when leaving for News.

Candidate `35f22445be5d7ca7ce93a646c245e1be0a4dec41` extends both the navigation row and compositor row from `['clock','weather']` to `['clock','weather','news']` while keeping the adjacent-only guard, and passed the full maintained suite as **Tests #5276**.

Focused B2 physical gate:

- [x] Weather → News moves forward as one full-viewport edge-locked strip.
- [x] News → Weather moves in the exact reverse direction.
- [x] Weather keeps its selected theme and forecast geometry while leaving for News.
- [x] News retains its category/story/ticker layout and remains fully interactive after arriving and after returning from Weather.
- [x] Clock↔Weather remains unchanged.
- [x] Clock→News and News→Clock remain on the temporary Horizontal-slide fallback for this slice.
- [x] Transition duration and non-Spatial style ownership continue to behave exactly as accepted.

### Level-B B2 physical acceptance — COMPLETE

The commissioned Pi now accepts the three-member adjacent row `Clock ↔ Weather ↔ News`. Both new Weather↔News directions are edge-locked and fully interactive, Weather preserves its outgoing layout/theme context, Clock↔Weather remains unchanged, and non-adjacent Clock↔News deliberately stays on the bounded fallback.

The small **News page theme-polish defect** found during B2 is now physically accepted: the **News ready** and **BBC feed date/time** pill borders follow the active daytime palette rather than retaining the legacy cyan/light-blue accent. Candidate `1d41fbfbbea7f2e02abab2a5352c889ec3c2ee0e` passed **Tests #5278**, and documentation head `2dc809d2120fe5a694287b5274192ac4a3a9f3ab` passed **Tests #5279**.

#### B3 — staged long jumps across the visible spatial row

B2 deliberately left Clock↔News on the short Horizontal-slide fallback because they are two positions apart. The first B3 code candidate removed that guard and used one direct viewport handoff. Although technically clean, physical/product review rejects that **model** before acceptance: Spatial row should communicate that these surfaces occupy real neighbouring positions, whereas a direct Clock→News handoff is visually little different from an ordinary reveal style.

The revised B3 rule is therefore **literal row traversal with one logical destination**:

```text
Home  <---->  Weather  <---->  News

Clock → News : Clock | Weather | News strip moves left by 200vw
News → Clock : News | Weather | Clock strip moves right by 200vw
```

Important semantics:

- Weather is visibly present between Clock and News during the motion;
- Weather is **not** logically activated, added to browser history or published as a destination event;
- only the selected destination is committed by the Surface Host;
- the configured Transition duration applies once to the **whole 200vw movement**, not once per viewport;
- adjacent one-position movements remain 100vw and otherwise unchanged;
- the same easing, outgoing layout freeze and per-surface presentation-context rules remain authoritative.

To do that without bringing back unreliable Chromium root snapshots, the compositor now builds a temporary DOM strip:

1. clone/freeze the real outgoing surface;
2. ensure any intermediate row member is mounted;
3. synchronously present that intermediate under its own temporary body mode, clone its real DOM/layout/background, then restore the true source before a paint can occur;
4. place the final live destination at its row distance;
5. animate every layer together for one configured duration;
6. remove temporary layers and leave only the selected destination live.

The initial direct-handoff candidate `205908549f11f1682d077c4df28029f917dd2592` passed **Tests #5280** but is superseded by this product decision. Staged-strip candidate `f8e8fea368fefb46f9ed2739a586aaceb84e9232` passed **Tests #5283**; comment/regression alignment head `f84ecd625a4d8a0aab1bfa582147797d3c4fc3b4` passed **Tests #5284**.

Focused B3-v2 physical gate:

- [x] Clock → News shows Weather physically between them as one continuous leftward strip.
- [x] News → Clock shows Weather physically between them as the exact reverse strip.
- [x] Weather passes through without becoming the logical active destination or causing a second settle/navigation event.
- [x] The configured Transition duration is the duration of the **complete** Clock↔News movement; it does not take twice as long as configured.
- [x] The three moving surfaces remain edge-locked with no white gaps, overlaps, fade/overlay or internal reflow.
- [x] Clock and News settle fully live/interactable after long jumps.
- [x] Existing Clock↔Weather and Weather↔News movements remain unchanged.
- [x] Selecting a non-Spatial transition restores that configured style for Clock↔News.
- [x] AirPlay, Settings and Plexamp remain outside the B3 row and unchanged.

### Level-B B3 physical acceptance — COMPLETE

The commissioned Pi accepts the literal staged-row model. Non-adjacent ACP surfaces now visibly traverse their real neighbours while retaining a single logical destination commit and one configured total duration.

The accompanying News status correction is also accepted: the rail pill describes the active category rather than inheriting an unrelated feed's degraded state. A real active-feed warning deliberately remains semantic rather than theme decorative:

- **News ready** follows the selected daytime palette;
- **Cached news / Stale cache** remains amber/yellow under Green Phosphor, Crimson Glow and other themes;
- that warning colour is intentional because it communicates degraded freshness rather than surface identity.

#### B4 — add AirPlay as the fourth ACP row member

The ACP browser-surface row now expands to:

```text
Home  <---->  Weather  <---->  News  <---->  AirPlay
```

This row is an **ACP application-surface order**, not a literal copy of every bottom-nav button. Plexamp is the deliberate cross-application workspace exception and Audio is a shell overlay, so neither belongs between News and AirPlay in the browser-surface strip.

B4 keeps the accepted B3 semantics unchanged:

- News↔AirPlay is a normal adjacent 100vw strip;
- Clock/Weather↔AirPlay long jumps visibly traverse every intermediate ACP row member;
- the configured Transition duration still covers the entire movement once;
- only AirPlay is logically committed when it is the selected destination;
- AirPlay's existing pre-snapshot/hydration authority remains responsible for stable segmented-clock/glance geometry before it starts entering;
- leaving AirPlay uses the same outgoing DOM-clone contract as Clock/Weather/News.

Because AirPlay has a few non-Classic theme rules scoped through `body[data-active-page="airplay"]`, B4 extends those rules to `[data-acp-surface-context="airplay"]` as well. This prevents an outgoing AirPlay clone from dropping back to Classic/cyan pulse and screen-border paint when the global body switches to News/Weather/Clock.

Candidate `9be2934e329ffaeb69d94e9cbfedda09bf8644d5` extends both spatial-row authorities to `['clock','weather','news','airplay']` and adds the outgoing AirPlay theme-context selectors. It passed the full maintained suite as **Tests #5286**.

The first commissioned-Pi B4 pass is **mostly successful but not accepted**. News→AirPlay, total-duration ownership, edge-locked multi-surface travel, endpoint interactivity, the accepted Clock↔Weather↔News row, non-Spatial transition ownership, Plexamp and Audio all pass. The first follow-up then separated two independent defects:

1. **AirPlay departure state corruption — FIXED PHYSICALLY.** B4's intermediate-surface capture had called the real `commitSurface()` while temporarily showing News/Weather and again while restoring AirPlay. Restoring AirPlay therefore ran `markAirPlayUnresolved()`, stripping the live now-playing/session classes before the outgoing clone was secured. B4-v2 candidate `c8e2790d449eb6c99e5e632b18b2197fdda1d138` separates presentation-only staging from logical activation with `presentMountedSurface()`; the commissioned-Pi retest confirms playing AirPlay now retains its controls, metadata and artwork geometry until movement begins.
2. **Endpoint screen-format leak — FIXED PHYSICALLY.** The remaining vertical hitch reproduced in both directions around AirPlay and was also visible on News→AirPlay. The cause was deterministic: `airplay.css` owns the live page with `body.mode-airplay .screen { display: block; }`, while ordinary ACP screens are grid containers. Spatial clones also carry class `.screen`. When the logical destination commit toggled `body.mode-airplay` before horizontal animation started, an outgoing Clock/News clone changed **grid → block**; when leaving AirPlay, its outgoing clone changed **block → grid**. B4-v3 now freezes the source screen's computed formatting mode before commit, preventing that body-mode leak. Commissioned-Pi retesting confirms News→AirPlay, Clock→AirPlay and both ready/now-playing AirPlay→Clock all remain vertically stable until horizontal motion begins.

B4-v2 regression guard `a805f274750bc6bd3a3e0c9a976cbda7cfae0a64`, cache-bust head `c1317b2dd3d9e107848d21d329c127504c816a4d` and aligned test head `22dc15b5a1270de6f7b045654e373e526a430058` passed through **Tests #5292**, with documentation-synchronised head `d22374e7b984a9df9a0f8ee4e11b02c9c4fa79a1` passing **Tests #5294**.

B4-v3 candidate `ed656f8fba24925aaab75cea2b25ff8ebffdc2b9` extends `freezeOutgoingScreenLayout()` to pin the source screen's computed `display` and `overflow` values as inline clone formatting before the destination body mode changes. This keeps News/Clock clones grid-formatted while entering AirPlay and keeps AirPlay clones block-formatted while leaving it. Regression head `eab572e565b041125af1b9e61e31bfa9400b767d`, cache-bust `6e0552e98bb1d49392a4335f4937277b3b24beed` and aligned test head `17151fbeed91144548adbc9bb5eab81584111e18` follow. The display-freeze implementation passed **Tests #5296**, the aligned regression/cache head passed **Tests #5299**, the detailed documentation head passed **Tests #5300**, the roadmap-synchronised head passed **Tests #5301**, and the pre-acceptance documentation head passed **Tests #5302**. The focused commissioned-Pi retest now passes in every remaining direction. **Level-B B4 is physically accepted.**

Focused B4 physical gate:

- [x] News → AirPlay moves as one adjacent full-viewport strip with AirPlay already hydrated/stable while entering.
- [x] AirPlay → News is the exact reverse with the source retaining both its session state **and its block-format screen geometry** until movement begins.
- [x] Clock/News → AirPlay begins horizontally without the outgoing grid screen changing vertical geometry when `mode-airplay` is committed.
- [x] AirPlay → Clock visibly traverses News then Weather in reverse with active/idle source presentation and bottom glance row remaining fixed until horizontal movement starts.
- [x] A deliberately slow Transition duration applies once to the complete 300vw Clock↔AirPlay movement.
- [x] All four moving surfaces remain edge-locked with no gaps, overlap, fade or internal reflow once movement begins.
- [x] AirPlay controls/status remain live after arrival and after returning from another row surface.
- [x] Existing Clock↔Weather↔News behaviour remains unchanged.
- [x] Cover reveal (or another non-Spatial style) still performs its ordinary direct destination transition.
- [x] Plexamp and Audio behaviour remain unchanged.

**B4 gate complete.**

#### B5 — separate workspace navigation from shell utilities

Product review after B4 changes the navigation model rather than adding Settings mechanically as a fifth row member.

The bottom sheet now has two semantic groups:

```text
WORKSPACES                                      UTILITIES
Clock   Weather   News   AirPlay   Plexamp      [Audio] [Settings]
```

The utility controls should be visually separated toward the right-hand edge rather than styled as ordinary page pills:

- **Settings** uses a modern inline SVG cog icon.
- **Audio** uses a modern inline SVG speaker-with-waves icon rather than a musical note, because the control owns appliance-wide mixer/EQ/audio behaviour rather than only music playback.
- SVGs use a stable `viewBox`, `currentColor` and CSS sizing so they scale cleanly with the navigation treatment and themes.
- icon-only controls retain full touch targets and explicit accessible names/labels;
- Settings remains a mounted ACP application surface for lifecycle/state preservation, but it is **not** a member of the spatial workspace row;
- Audio remains the accepted shell overlay and is likewise **not** a spatial row member.

This changes presentation and navigation semantics only; it must not weaken Settings autosave/state preservation or Audio overlay ownership.

B5 implementation candidate:

- `be9351567e81a0f308681c343bc94d7e10ebdc5b` splits `_nav.html` into explicit `nav-workspaces` and `nav-utilities` groups and places the visible workspace controls in the intended order `Clock → Weather → News → AirPlay → Plexamp`.
- `4ee212c6013993a7fc4b1a95593ba433a69cefb6` adds the right-edge utility layout, divider, compact touch targets and scalable `currentColor` SVG treatment.
- `fef4860c4bac75ee5b6bcb932e91b5c724af71ca` updates the defensive Audio-button installer so a missing runtime control is recreated inside the utility group rather than inserted into the wrong parent.
- `5600301dceee5460704fe82c92d20c5448346764` bumps the shell navigation asset versions. Its **Tests #5315** failure is the expected transient stale-marker assertion before the next commit updates the regression fixture.
- `27723265773c03274b1d8a77917990e650c4ce6d` aligns regression coverage for grouping, visible order, inline SVG/accessibility ownership and the new asset markers; it passed the full maintained suite as **Tests #5316**.

B5 deliberately changes **visible nav order only** for Plexamp. The accepted Spatial-row engine remains `Clock ↔ Weather ↔ News ↔ AirPlay` until B6; Plexamp does not gain spatial traversal merely because its button now occupies the intended terminal visual position.

Focused B5 physical gate:

- [x] Navigation opens with workspace pills grouped together on the left/centre and a clearly separated Audio/Settings utility cluster near the right edge.
- [x] Visible workspace order is `Clock, Weather, News, AirPlay, Plexamp` without crowding, wrapping or overlap at 1280×720.
- [x] Audio shows a clean speaker-with-waves SVG and Settings a clean cog SVG; both remain sharp at normal scale and under VNC.
- [x] Utility icons inherit Classic Dark and at least one non-Classic daytime theme correctly, including active/open state.
- [x] Audio icon opens/closes the existing mixer overlay exactly as before and its active state follows the overlay.
- [x] Settings icon enters the existing mounted Settings surface; repeated return preserves Settings state/autosave behaviour.
- [x] Workspace buttons retain current navigation behaviour; B5 has not given Plexamp Spatial-row semantics before B6.
- [x] Home-indicator reveal height, page/drawer sheet motion and auto-hide remain healthy with the nested nav groups.

**B5 utility-cluster core is physically accepted.** Product review of that accepted layout immediately identified a shell-presentation refinement before B6.

##### B5 refinement — persistent navigation above workspace transitions

The navigation bar is shell chrome, not page content. It should therefore remain visually above destination transitions until its own inactivity policy hides it.

Refined contract:

- ordinary View Transitions occur **behind** navigation rather than painting over/dimming the drawer;
- Spatial-row transitions likewise start immediately behind an open navigation bar instead of first waiting for navigation to slide away;
- **Overlay content** is the new default navigation presentation: opening navigation leaves the current workspace in place and overlays/dims it;
- **Lift content** remains available as a Display → Motion option, retaining the accepted measured live-page lift for users who prefer it;
- the existing **Navigation transition duration** remains the authority for drawer/indicator/backdrop motion (and the optional page lift);
- add **Navigation inactivity time** under Display → Motion as a 0–30 second slider in 1-second steps; `0` means **Never auto-hide**;
- while the Audio mixer is open, navigation inactivity auto-hide is suspended regardless of the configured timeout;
- workspace and utility controls gain a roughly 15–20% larger touch target and one shared control height; workspace pills become rounded rectangles while Audio/Settings retain compact circular icon controls;
- the drawer itself uses the normal ACP card radius rather than a pill/half-circle end treatment.

Implementation:

- `deaf1f29f80f5f027437db2f43436d13659abe0a` adds persisted `navigation_presentation` and `navigation_inactivity_seconds` settings.
- `8d4ee1c98ba2f8d7e45ad4453d7202d46ec895e4` / `df68650242f2a9f7158f5a187cd80aed8aea9f6a` add the Motion controls and slider restoration.
- `8ce79f4591fcce6b3ed4cc57ebe5161c20d0336b` / `6b746b0eb081cbf1a3360dcdf887a1abbaed9486` project the settings into the long-lived shell.
- `ee9f7ee1e9734524da4b0c857f4c99df66758709` replaces the fixed 6/60-second timers with the user-owned inactivity timeout and makes Audio suspend auto-hide.
- `bf5aa2c205a5dca5d72d6cfe52ae984bc2788a1a` removes the Spatial-row pre-transition navigation-close wait so the shell stays present.
- `5a8a3bad117635459db9260050e215c3fc483e16` makes the shell a non-animated named View Transition layer above page snapshots, adds Overlay/Lift presentation ownership and enlarges/re-shapes the controls/drawer.
- `9597f55b29c26bd234c5efc7ee8b1a1280490b73` aligns the final control size/radii with ACP design tokens; regression alignment follows through `eb00e963ebe8aa6b5185c56fdd8bc2b885501bef`.
- Intermediate CI reds during the setting/cache/test sequence were stale regression expectations; the first fully aligned implementation passed **Tests #5333**, the final larger-control/radius treatment passed **Tests #5334**, and its aligned regression head passed **Tests #5335**. Roadmap/documentation sync then passed **Tests #5336–#5337**.
- The first commissioned-Pi follow-up confirms the persistent-shell model is substantially correct. Ordinary transitions, Spatial-row shell persistence, Overlay mode, inactivity ownership and Audio timeout suspension all pass. Two real edge cases were found: Lift+Spatial forced the outgoing clone down before horizontal movement, and Plexamp→Settings still used the legacy full-document handoff. Touch sizing passed but the workspace labels wanted more visual weight.
- Follow-up implementation removes the clone's forced zero translate (`3861a2b2d360a2b895ef274b225788d7261dd714`), keeps mounted ACP destinations including Settings inside the live shell when leaving Plexamp (`ea868dc141de484c24d7c279f252e6f3cf199bc2`), reorders the Motion controls and adopts **Home** as the human-facing name for the internal `clock` workspace, themes pending/saving Settings state instead of using warning yellow, enlarges nav labels without changing their padding/gaps, and brings Classic Dark Audio glass in line with the other themes. The aligned behavioural/regression head passed **Tests #5349**; the final Classic Dark transparency polish passed **Tests #5350**, documentation/initial Home-status alignment passed **Tests #5353**, and the final Home-identity regression head passed **Tests #5354**.

Focused refinement physical gate:

- [x] With Cover reveal (and another ordinary transition), navigation remains visually above and unchanged while the page transition runs behind it, including Plexamp→Settings.
- [x] Spatial row begins immediately behind the still-open navigation bar; it no longer waits for navigation to close first.
- [x] Default **Overlay content** leaves the live page at its normal vertical position while opening/closing navigation.
- [x] **Lift content** remains selectable and uses the measured reveal height. The Spatial outgoing-page drop is fixed and physically retested.
- [x] Navigation transition/inactivity ownership behaves independently of application Transition duration in the tested shell flows.
- [x] Navigation inactivity values, including `0 = Never`, behave correctly and shell interaction resets the timer.
- [x] Audio remains open while the mixer is active; closing Audio resumes the configured inactivity timeout.
- [x] Enlarged workspace and utility controls share one height, are comfortably touchable and do not wrap at 1280×720. The final ~15% workspace-label increase is physically accepted with the existing height, horizontal padding and inter-button gaps unchanged.
- [x] Drawer and workspace-button corner radii read as ACP rounded rectangles rather than a pill-ended bar.

Additional B5 presentation polish from this gate:

- Settings → Display → Motion places its two choice controls in one column: **Transition style** above **Navigation presentation**, with the two duration sliders opposite them.
- “changed / pending / saving” Settings chrome follows the selected theme accent; semantic failure remains red and warning colours remain reserved for actual warnings.
- Classic Dark Audio uses the same glass/translucency idea as the coloured daytime themes rather than an almost-opaque navy sheet.
- the primary `clock` workspace is now presented to users as **Home**. Internal route/state identifiers remain `/clock` / `clock` for compatibility.
- possible workspace SVG treatment is being evaluated separately before implementation: Home, Weather and News can use semantic symbols while AirPlay/Plexamp can use recognisable product marks; Audio and Settings retain their accepted utility icons.
- the October 9 focused Pi retest passed the Lift+Spatial fix, Plexamp→Settings shell persistence, Motion layout, themed save-state chrome and Classic Dark Audio glass. Only workspace label size remained open; the final candidate increases the label clamp from `1.02rem/2.55vmin/1.18rem` to `1.17rem/2.9vmin/1.36rem` (about 15%). The final label-size implementation/regression head passed **Tests #5357** and the commissioned-Pi visual retest is accepted. **B5 is physically complete.**

**B5 PHYSICALLY ACCEPTED — 2026-10-09.**

#### B6 — promote the row from browser surfaces to shell workspaces

**Status: ACTIVE.**

The accepted B4 compositor proved a literal ACP browser-surface strip. Before native Plexamp migration, generalise that product concept into a **shell-owned workspace order** whose positions are independent of renderer technology.

Current target order:

```text
Home  <---->  Weather  <---->  News  <---->  AirPlay  <---->  Plexamp
```

Reserved future order once Astronomy is implemented:

```text
Home  <---->  Weather  <---->  Astronomy  <---->  News  <---->  AirPlay  <---->  Plexamp
```

The distinction is deliberate:

- Home/Weather/News/AirPlay/Astronomy are ACP browser application surfaces;
- Plexamp is the terminal media workspace;
- today Plexamp is represented by the persistent browser player layer;
- later it becomes the native Wayland Plexamp application;
- **its row position, navigation direction and shell choreography do not change when the renderer changes**.

##### B6a — shell-owned topology authority

The first B6 slice is structural rather than visual:

- new `workspace-topology.js` owns the live order `clock → weather → news → airplay → plexamp`, presentation label **Home**, route mapping and renderer ownership;
- the same authority records the future reserved order `clock → weather → astronomy → news → airplay → plexamp` without making Astronomy routable early;
- the ACP live-DOM compositor derives its ACP-only order from this shell authority instead of carrying a private four-item array;
- `page-transitions.js` uses the same topology for direction/path decisions;
- renderer ownership is explicit (`acp` vs `plexamp`), so Plexamp does not have to masquerade as an `ACPSurfaceHost` surface.

Candidate chain: `90477c75971a580cb1f6b933cb23395df2af21aa` → `34f4ab39314866a64d48462a2263b0dde6b56cf8` → `d4bf62237dec8c1947c7f41b3cf5985f628fe939` → `283dd435127f9875524ed69c6b62f7c4dec47922`. The first topology CI run (**Tests #5364**) was an expected stale B4 regression assertion against the removed hard-coded row; the aligned regression is included in the following B6b candidate.

##### B6b — adjacent AirPlay ↔ Plexamp renderer boundary

The second slice makes only the adjacent cross-renderer boundary spatial:

- explicit Spatial-row navigation from AirPlay to Plexamp animates the live AirPlay screen `0 → -100vw` while the persistent Plexamp layer moves `+100vw → 0`;
- Plexamp → AirPlay is the exact reverse: Plexamp `0 → +100vw`, AirPlay `-100vw → 0`;
- both use the full application Transition duration once, with the accepted Spatial easing;
- navigation remains persistent shell chrome above both moving renderers;
- Plexamp iframe/process state is not recreated; the persistent player layer itself moves;
- if AirPlay is not already the mounted underlay when returning from Plexamp, it is committed/hydrated first without animation, then participates as the incoming adjacent workspace;
- non-Spatial styles continue through the accepted Plexamp transition backend unchanged;
- **long jumps involving Plexamp are deliberately not spatial yet**. Home/Weather/News ↔ Plexamp remain on the accepted ordinary backend until B6c stages the intermediate ACP workspaces.

Implementation heads: `34c0a8fb099b41f062a9b81b7172b12fab7ad6e9` (Plexamp renderer adapter), `003a60cfb9d69c73a7402e2ced0ea61487389c52` (navigation routing), `e9d2a643770905298c5abbab01d9804b214d3580` (asset versions), and `6faf264ffdbee69d429c3fa5629c45bc2bdb2f0f` (aligned topology/adjacent regression). The first combined run **Tests #5368** exposed only two stale static assertions from the topology/handoff refactor; aligned regression head `7619686be2b12a1439f154d9e5c12b84aa3ddfa2` passes the full maintained suite as **Tests #5370**. Commissioned-Pi acceptance is complete.

Focused B6b physical gate:

**10 October 2026 commissioned-Pi result:** all eight visual/behavioural checks pass. A possible audio-continuity issue was investigated before B6b sign-off: Plexamp music is clean while the UI is idle, but brief glitches are audible during page transitions and while navigating between Settings sections/subpages. Because Settings internal navigation is primarily synchronous panel hide/show + layout/paint rather than the B6b spatial animation, investigation is treating this as a wider UI-load / real-time-audio interaction rather than assuming the new AirPlay↔Plexamp adapter is solely responsible.

**First diagnostic capture — 2026-10-10 02:42 BST:** after deliberately exercising transitions and Settings navigation while Plexamp played 44.1 kHz / 16-bit FLAC, only one audible glitch was noticed. The last-five-minute CamillaDSP/Plexamp journal contained no underrun/overrun/XRUN/stall report; the kernel journal contained no ALSA, MMC or throttling event. `vcgencmd get_throttled` returned `0x0`, SoC temperature was 67°C and the ARM clock remained ~2.4 GHz. Snapshot process load showed Chromium renderer as the dominant user-space consumer (~38% CPU), GPU Chromium ~6.5%, WayVNC ~4.7%, CamillaDSP ~1.6% and Plexamp Node ~0.3%. One Plexamp log line reported `ALSA ... Invalid CTL acp_plexamp`; this is a control-interface lookup rather than an XRUN and is not yet correlated with the audible glitch. The evidence therefore does **not** currently implicate the downstream CamillaDSP graph or thermal/storage failure; next isolate UI rendering from remote-display encoding by comparing the same workload with the VNC viewer disconnected versus connected. Follow-up A/B testing with and without an active VNC viewer reproduced **no audible glitch** despite aggressive transitions and Settings navigation. Thread inspection showed CamillaDSP and Plexamp under ordinary TS scheduling, memory remained healthy (~3.1 GiB available), zram swap was unused, and PSI files were simply unavailable on this kernel. The test track itself contains deliberate ticks/clicks which may have been mistaken for a glitch. **B6b audio continuity is therefore accepted with a monitor-only note: reopen investigation only if a repeatable symptom returns.**


- [x] AirPlay → Plexamp is one clean adjacent 100vw movement with both live surfaces visible edge-to-edge and no fade/gap.
- [x] Plexamp → AirPlay is the exact reverse.
- [x] A slow Transition duration applies once to the complete AirPlay↔Plexamp movement.
- [x] Open navigation remains fixed above both moving workspaces.
- [x] Plexamp playback/UI state remains continuous. The earlier suspected audible glitch could not be reproduced in a deliberate VNC-connected/disconnected stress test; no XRUN/kernel/throttling/storage evidence was found. Treat as a watch item only if a repeatable symptom returns.
- [x] AirPlay live/ready state remains correct after returning from Plexamp.
- [x] Cover reveal (or another non-Spatial style) still uses the existing ordinary Plexamp transition.
- [x] Home/Weather/News → Plexamp still use ordinary transition behaviour for now; no fake partial spatial long jump is introduced.

**B6b PHYSICALLY ACCEPTED — 2026-10-10.** All eight visual/behavioural checks pass and the suspected audio issue is not reproducible under targeted stress.

##### B6c — literal long-jump traversal to/from Plexamp

B6c extends the accepted shell topology beyond the adjacent AirPlay↔Plexamp boundary without making Plexamp an ACP browser surface.

For a forward long jump such as `Home → Plexamp`:

```text
Home → Weather → News → AirPlay → Plexamp
```

the source plus intermediate ACP workspaces are captured as presentation-only live-DOM layers in their literal row positions, while the **real persistent Plexamp layer** occupies the terminal slot. The entire strip moves once across the configured Transition duration.

Reverse traversal mirrors the same topology. For example `Plexamp → Home` stages AirPlay, News and Weather between the live Plexamp source and the committed live Home destination, then moves the complete strip right in one movement.

Important lifecycle rules:

- the accepted adjacent `spatialShow()` / `spatialHide()` path remains intact; long jumps use separate `spatialShowPath()` / `spatialHidePath()` renderer adapters;
- ACP intermediate workspaces are presentation-only captures and are never logically activated;
- AirPlay is now allowed to be an **intermediate** workspace, so its script-owned status is refreshed while its wrapper is still hidden, then its measured layout is synchronously calibrated during the capture window;
- the real AirPlay wrapper is never left visible across an `await`, preventing a pre-transition flash;
- Home/Weather/News/AirPlay capture layers remain inert and are removed after travel;
- the persistent Plexamp iframe/player itself moves; it is not cloned/reloaded;
- one configured application Transition duration owns the full multi-workspace journey;
- navigation remains persistent shell chrome above the moving strip;
- automatic projection and non-Spatial transition styles retain their accepted existing paths.

Key implementation chain:

- `9e2eadce98bb6deba98775d63ea0e4284c9a2bc4` adds presentation-only AirPlay preview refresh;
- `c2a2e233f24fce8b001fca87f971e40a6f48e218` exposes ACP staged-strip capture;
- `e12bd0e14f114835487be506ade9195f09ee2d7b` adds long-path Plexamp renderer adapters;
- `05f084d44de5b356b5e05abcbbe30ce73d707039` routes long Spatial requests through those adapters;
- `eb7a7bcae4cf2e4393598f673e136899a0c1b6ef` keeps AirPlay hidden while awaiting preview hydration;
- `73c1dd73f6145c9d8e5068d9dcf6ab342f39e381` adds synchronous AirPlay layout/marquee preview calibration;
- final regression/cache alignment is through `f10ee196629051d449a624075727fcf1c28793a2`.

Intermediate **Tests #5384/#5390** reds were stale static expectations only; the final aligned B6c head passes the complete maintained suite as **Tests #5391**.

Focused B6c physical gate:

**10 October 2026 commissioned-Pi result:** clean sweep. All ten long-jump checks pass, including literal forward/reverse order, shortened paths, one total duration, first-pass AirPlay staging, persistent navigation, Lift/Overlay geometry, Plexamp state continuity and non-Spatial fallback. No audio glitches were heard during this stress test. **B6c is physically accepted.**

- [x] Home → Plexamp visibly traverses Weather → News → AirPlay → Plexamp in that exact order.
- [x] Weather → Plexamp traverses News → AirPlay → Plexamp; News → Plexamp traverses AirPlay → Plexamp.
- [x] Plexamp → Home is the exact reverse: Plexamp → AirPlay → News → Weather → Home.
- [x] Plexamp → Weather and Plexamp → News preserve the corresponding shortened reverse paths.
- [x] One slow Transition duration applies to the **entire** long journey, not once per workspace.
- [x] Intermediate AirPlay is presentation-correct on the **first** long jump, including route-ready/now-playing geometry, with no pre-transition flash.
- [x] Open navigation remains fixed above the complete long strip.
- [x] Plexamp playback/UI state survives long jumps exactly as it did for the accepted adjacent boundary; the commissioned-Pi retest also produced no audio glitches.
- [x] Lift and Overlay navigation presentations both retain correct vertical geometry during the long strip.
- [x] Cover reveal (or another non-Spatial style) continues to use the ordinary Plexamp transition; automatic projection also remains non-Spatial.

This should make native Plexamp migration easier: the shell first owns a stable workspace index/order, then the Phase-B migration replaces only the Plexamp endpoint implementation and cross-application transition backend. Do not force native Plexamp into `ACPSurfaceHost` merely to satisfy the spatial metaphor; introduce/retain a shell/workspace abstraction above browser-surface and native-application implementations.

B6 physical gates should prove:

- AirPlay↔Plexamp behaves as an adjacent workspace movement with the same left/right spatial meaning as the ACP row;
- Home/Weather/News↔Plexamp long jumps preserve literal intermediate workspace order and one configured overall movement duration where technically appropriate;
- reverse Plexamp→ACP navigation mirrors the same topology;
- the home indicator/navigation utility cluster remains shell-owned above both implementations;
- automatic Plexamp projection does not masquerade as a user-requested multi-workspace traversal;
- later native Plexamp can inherit the same terminal slot without changing button order or navigation direction.

**B6 PHYSICALLY ACCEPTED — 2026-10-10.** The shell-owned topology `Home ↔ Weather ↔ News ↔ AirPlay ↔ Plexamp` is now physically proven across ACP↔ACP, adjacent ACP↔Plexamp and long cross-renderer traversal, while preserving native-Plexamp renderer independence.

#### B7 — night-clock anti-burn-in bouncing cluster — final Phase-A polish before Astronomy

**Status: ACTIVE.**

Replace/extend the existing simple night burn-in shift with an optional continuous **bouncing cluster** mode inspired by classic screen-saver motion.

The moving object is one rigid visual group containing:

- the time;
- the date row;
- the alarm indicator/symbol when present.

Required behaviour:

- the group travels continuously within the safe visible night-clock area;
- edge collisions use ordinary specular reflection: the incident component reverses at the boundary so the cluster visibly “bounces” rather than jumping to a new random location;
- time/date/alarm retain their internal spacing and move together;
- a **Night burn-in motion speed** setting controls the travel speed independently of page/navigation transition duration;
- preserve the existing static/periodic-shift behaviour as a fallback or selectable motion style until the bouncing mode is physically accepted;
- use transform-based motion and recalculate bounds safely after viewport/layout/alarm-indicator changes without allowing any part of the cluster to leave the visible area;
- respect reduced-motion/accessibility policy and all existing night dim/wake behaviour;
- physically accept long-running 1280×720 motion for smoothness, edge reflection, no clipping, no obvious repeated short loop and no interference with alarm takeover/navigation.

##### B7 candidate — reflected night Clock motion

The first B7 candidate preserves the old anti-burn-in implementation as an explicit mode rather than silently replacing it.

Settings → Display → Night dimming now exposes:

- **Anti-burn-in motion:** Off / Periodic shift / Bouncing;
- **Night burn-in motion speed:** originally 1–20 px/s/default 6; after the first physical pass the range is **1–120 px/s** with fresh/default value **40 px/s**, enabled only for Bouncing. Existing saved values such as 6 px/s remain valid and are not silently migrated.

The saved mode is `display.night_burn_in_motion`; speed is `display.night_burn_in_speed_px_per_second`. The legacy `night_burn_in_shift` boolean remains mirrored for older configuration/client compatibility. Existing configurations with the old checkbox off migrate to **Off**; existing enabled configurations migrate to **Periodic shift**. Fresh example configuration remains Periodic until Bouncing is physically accepted.

Runtime ownership is split cleanly:

- `display-dimming.js` decides whether the Clock is currently eligible for night anti-burn-in motion (scheduled/preview night state, not interacting, Clock visible, no Alarm takeover);
- `night-burn-in-motion.js` owns movement only;
- Periodic shift preserves the accepted nine-position ±4 px pattern on the existing five-minute cadence;
- Bouncing uses `requestAnimationFrame`, an initial non-axis-aligned vector and pixels-per-second velocity;
- the first candidate gave time, date and alarm annunciator the same CSS individual `translate`, proving rigid movement but exposing that the alarm was still positioned against the viewport-sized Clock hero;
- the follow-up introduces a layout-transparent daytime `#clock-burn-in-cluster` which becomes the real positioned/bounded object only in very-dark Clock mode; the alarm is then anchored inside the cluster's top-right corner and one `translate` moves the entire group;
- the real cluster box defines safe movement limits with a viewport margin, eliminating the remote alarm-annunciator "outrigger" that artificially collapsed the available travel area;
- a collision reflects only the velocity component normal to that edge, giving ordinary specular reflection;
- bounds are recalculated through `ResizeObserver`/viewport resize and the position is clamped back inside the safe area;
- long renderer stalls are capped to a 50 ms motion step so resume cannot teleport the cluster through an edge;
- `prefers-reduced-motion: reduce` automatically substitutes Periodic shift for continuous Bouncing;
- same-document surface activation/settling immediately starts or stops motion instead of waiting for the 15-second night-state refresh;
- leaving night Clock mode, interaction/wake state, document hiding or page teardown stops continuous motion safely.

Implementation/regression chain is aligned through `1637f17d54e7b21fc6f9cb02ded7867ba8c1ca7d`; the complete maintained suite passes as **Tests #5405**.

Focused B7 physical gate:

**10 October 2026 first commissioned-Pi pass:** partial acceptance. Rigid motion, persistence, Off/Periodic fallback, navigation stop/resume and Alarm takeover all worked. The first safe-bounds implementation was technically correct but the annunciator was anchored to the viewport-sized hero, making it a remote top-right outlier; this produced a very large top/right exclusion and tiny vertical travel. The 20 px/s ceiling also felt too slow, the inactive night annunciator was effectively invisible, named navigation transition layers could show the selected daytime palette above the astronomy overlay, and one or two brief full-white transition flashes were observed.

- [x] Off leaves the night Clock stationary.
- [x] Periodic shift retains the previously accepted subtle five-minute behaviour.
- [x] Bouncing moves time, date and alarm annunciator together with no change in their relative spacing.
- [~] Left/right/top/bottom reflection worked, but the first candidate's alarm geometry made the usable bounds visibly wrong; retest the rebased cluster.
- [~] No clipping was reported, but 1280×720 safe-area acceptance must be repeated with the corrected cluster geometry.
- [~] Speed changes persisted correctly, but 20 px/s was still slow and 6 px/s was "positively snail like"; retest the widened 1–120 px/s scale (40 px/s fresh/default, saved legacy values preserved).
- [ ] Entering the configured night interaction state stops/resets the motion; when the interaction timeout expires on Home, motion resumes safely.
- [x] Navigating away from Home stops the motion; returning to Home during an eligible idle night state resumes it safely.
- [x] Alarm takeover remains fully visible and is not moved/dimmed by the burn-in engine; dismissing the Alarm returned directly to the eligible bouncing Clock without falsely replaying the dismissal as night interaction.
- [~] Several-minute operation remained stable until the normal three-minute idle policy projected the actively-playing Plexamp workspace; repeat smoothness/loop observation at a useful speed after the geometry fix.

##### B7 follow-up candidate — cluster geometry + dark-room shell closure

The follow-up directly addresses the physical findings:

- `#clock-burn-in-cluster` is `display: contents` in normal/daytime layout, preserving the accepted Clock geometry, and becomes a centred positioned flex container only in very-dark Clock mode;
- the alarm annunciator is rebased to that cluster's top-right corner, taking advantage of the naturally empty area above the smaller seconds readout instead of sitting near the viewport corner;
- the bounce engine now moves/bounds that single cluster rather than maintaining three independent translated targets;
- inactive alarm indication is explicitly lifted to a visible-but-dimmer night level throughout the active night treatment, while a scheduled alarm retains the stronger active state;
- Bouncing speed is 1–120 px/s with 1 px/s steps and a fresh/default value of 40 px/s; existing saved values are preserved exactly;
- astronomy-night shell chrome receives an explicit red/dark palette before named View Transition capture, preventing persistent nav snapshots from revealing the selected daytime theme above the multiply overlay;
- the View Transition top layer now has an explicit `#02040a` canvas, switching to black whenever the document night treatment is active, so a transient Chromium snapshot gap cannot expose the browser's white default canvas.

The first follow-up implementation passed the full suite as **Tests #5417**; the migration-safe speed-scale refinement on implementation head `9e56da66d36299d890e816c4d2c2fc0ac481a4f6` passes the full suite as **Tests #5421**.

**10 October 2026 second commissioned-Pi pass:** the wider speed range is physically useful and **40 px/s feels suitable as the normal/default value**. The inactive alarm bell is now visible as intended. The rebased bell, however, sits inside the clock face over the seconds rather than just outside it, and the visible edge clearance still feels too generous even though it is now symmetrical. The segment glow is not part of `getBoundingClientRect()` collision geometry, so it is retained. Astronomy-night navigation is still wrong during ordinary ACP page transitions: named nav snapshots temporarily appear in the selected daytime palette until the transition ends and the document overlay resumes. One additional brief full-white transition flash was also observed but was not reproducible or tied to a specific route.

##### B7 follow-up v3 — visible bounds + transition-top-layer night safety

The next focused candidate addresses those remaining findings:

- the alarm bell remains anchored to the compact night Clock cluster but is moved just above/slightly outside its top-right corner rather than over the seconds;
- the cluster remains the single translated object, while collision bounds are measured from the **visible union of time + date + alarm bell** so wrapper whitespace cannot create a fake margin;
- the deliberate edge safety margin is reduced from 20 px to **10 px**;
- the segment glow is retained because CSS shadows/filters do not affect the geometric bounding boxes used by the collision engine;
- `#acp-night-dim-overlay` now has its own named View Transition layer with a z-index above the persistent navigation snapshots, so the exact night treatment remains above navigation during ordinary ACP transitions instead of disappearing beneath the transition top layer;
- night style is mirrored onto the document root so transition pseudo-elements can preserve astronomy multiply behaviour;
- the View Transition canvas, root group, root image-pair and root old/new snapshots all receive explicit dark backing (`#02040a`, black when night-active);
- the separate live-DOM Spatial-row path also receives explicit dark/black backing, covering both transition implementations against a transient white browser canvas.

Implementation/regression head `2828f17e56306849844f4305016fc12c4e11a0f5` passes the complete maintained suite as **Tests #5434**. Focused commissioned-Pi retest remains the B7 closure gate.

**10 October 2026 third commissioned-Pi pass:** the 10 px/visible-child bounds are improved and the inactive bell remains correct. The bell still needs one final placement adjustment: it should sit immediately to the right of the seconds with its top aligned to the hours/minutes. The v3 named-overlay experiment is rejected: ordinary ACP transitions displayed a bright full-screen red frame, and one transition from around AirPlay showed a darker red snapshot region moving down the screen while the red shell remained visible. Spatial-row transitions did **not** show the red frame, confirming that the regression is specific to the View Transition overlay composition rather than the live-DOM strip. The old daytime-nav leak was not seen in this round.

##### B7 follow-up v4 — real night nav capture, no overlay snapshot

V4 removes the failed overlay-as-View-Transition-layer approach entirely:

- `#acp-night-dim-overlay` is once again an ordinary part of the page/root snapshot; it has no `view-transition-name`, so Chromium cannot isolate the pure-red multiply layer as an opaque top-layer image;
- the dedicated `acp-night-dim-overlay` transition pseudo rules are removed;
- the previously added dark safety backing remains on the View Transition canvas, root group/image-pair/old/new snapshots and the independent live-DOM Spatial strip, preserving protection against a white browser canvas;
- the nav itself is now given a **real computed astronomy-night palette before snapshot capture** by a new late-loading `night-shell-closure.css`;
- that closure stylesheet loads after all daytime theme/component styles and uses a higher-specificity night-state selector, fixing the actual cascade problem that let daytime nav colours survive underneath the document overlay;
- Plexamp is deliberately excluded from the late ACP nav override because its accepted transition path was already correct;
- the night Clock now has a `.clock-time-row`: it is layout-transparent during normal/daytime presentation, but in very-dark Clock mode it becomes a flex row with the time first and the alarm annunciator second;
- the bell is therefore a normal layout sibling directly to the **right of the seconds**, top-aligned with the main time instead of being absolutely guessed into place;
- the bounce engine still measures visible time/date/bell geometry with the accepted 10 px safe margin and keeps 40 px/s as the physically preferred fresh/default speed.

Implementation/regression head `90021e616a110f7da75e8381ef3e84fbd331efc9` passes the complete maintained suite as **Tests #5444**. Focused Pi verification of bell placement, night nav capture and transition-flash closure remains required.

**10 October 2026 fourth commissioned-Pi pass:** the new flex-row bell placement passes physically. The user requested the remaining 10 px collision margin be removed so the visible cluster bounces at the actual viewport edge. The v4 overlay regression is gone — no bright-red transition screen was seen — but the nav drawer still appears in its daytime palette during **every ordinary ACP View Transition** tested, except the separate Plexamp/Audio paths. Under Spatial row, ACP workspace transitions correctly keep the nav red; only Settings and return-from-Settings show the daytime nav because Settings deliberately falls back to the ordinary View Transition backend. This cleanly isolates the remaining nav issue to the named `acp-nav-drawer` View Transition snapshot rather than night state, Spatial composition or Plexamp. No white/red full-screen flash was reported in this round.

##### B7 follow-up v5 — edge bounce + nav-snapshot-only tint

V5 narrows the fix to the actual failing layer:

- `SAFE_MARGIN_PX` is now **0**, so collision bounds are the visible time/date/bell union against the real viewport edge;
- the failed late live-nav closure stylesheet is no longer loaded and has been removed from the repository;
- the night overlay remains an ordinary part of the root/page snapshot and is never promoted into its own View Transition layer;
- the dark safety colour is kept only on the **stationary** View Transition canvas plus the night document background;
- dark backgrounds are removed from the animated root old/new/image-pair snapshot pseudos, because their motion can expose the backing as a travelling dark/red rectangular slab;
- only the temporary `acp-nav-drawer` snapshot is night-treated: its View Transition group gets a clipped pure-red backing, the old drawer copy is hidden, and the incoming drawer snapshot uses `mix-blend-mode: multiply`;
- this locally reproduces the normal astronomy red multiply treatment on the one named snapshot that sits above the page overlay, without introducing any full-screen overlay snapshot;
- the independent live-DOM Spatial strip retains its accepted dark/black safety canvas and requires no nav tint because its persistent nav is already physically correct.

Implementation/cleanup head `9949442191f3a544411fcfec594bc557eeeef474` passes the complete maintained suite as **Tests #5452**. Focused commissioned-Pi verification of edge bounce and ordinary-transition nav snapshot tint remains the B7 closure gate.

**Astronomy does not start until B5–B7 are physically accepted.** Its reserved workspace position is between Weather and News so the eventual row becomes `Home ↔ Weather ↔ Astronomy ↔ News ↔ AirPlay ↔ Plexamp` without another navigation-model redesign.

