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
Clock  <---->  Weather
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
Clock  <---->  Weather  <---->  News
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
Clock  <---->  Weather  <---->  News

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
Clock  <---->  Weather  <---->  News  <---->  AirPlay
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

The first commissioned-Pi B4 pass is **mostly successful but not accepted**. News→AirPlay, total-duration ownership, edge-locked multi-surface travel, endpoint interactivity, the accepted Clock↔Weather↔News row, non-Spatial transition ownership, Plexamp and Audio all pass. Two departure/entry presentation defects remain:

1. **AirPlay departure state corruption.** When AirPlay was the source, B4's intermediate-surface capture called the real `commitSurface()` while temporarily showing News/Weather and again while restoring AirPlay. Restoring AirPlay therefore ran `markAirPlayUnresolved()`, stripping the live now-playing/session classes before the outgoing clone was secured. The observed result exactly matches this path: controls disappear, route-ready copy appears and the artwork/copy geometry changes before the horizontal movement begins.
2. **Clock→AirPlay pre-motion vertical hitch.** After the navigation sheet closes, the Clock presentation visibly shifts before the long spatial movement begins. Other spatial destinations do not show the same visible hitch. This remains a focused physical retest item rather than being assumed fixed by the AirPlay-state correction.

B4-v2 candidate `c8e2790d449eb6c99e5e632b18b2197fdda1d138` separates presentation-only staging from logical activation with `presentMountedSurface()`. Intermediate captures and restoration now change only which mounted wrapper is visible; they never invoke `commitSurface()`, so an outgoing AirPlay session cannot be marked unresolved merely because the compositor is assembling the strip. Regression guard `a805f274750bc6bd3a3e0c9a976cbda7cfae0a64`, cache-bust head `c1317b2dd3d9e107848d21d329c127504c816a4d` and aligned test head `22dc15b5a1270de6f7b045654e373e526a430058` follow. Physical retest and CI are pending.

Focused B4 physical gate:

- [x] News → AirPlay moves as one adjacent full-viewport strip with AirPlay already hydrated/stable while entering.
- [ ] AirPlay → News is the exact reverse **without changing the outgoing AirPlay session/geometry before movement**; first pass failed because staging marked AirPlay unresolved.
- [ ] Clock → AirPlay visibly traverses Weather then News before AirPlay arrives **without a pre-motion vertical hitch after navigation closes**; row traversal itself passes.
- [ ] AirPlay → Clock visibly traverses News then Weather in reverse **while preserving the exact active/idle source presentation until movement starts**.
- [x] A deliberately slow Transition duration applies once to the complete 300vw Clock↔AirPlay movement.
- [x] All four moving surfaces remain edge-locked with no gaps, overlap, fade or internal reflow once movement begins.
- [x] AirPlay controls/status remain live after arrival and after returning from another row surface.
- [x] Existing Clock↔Weather↔News behaviour remains unchanged.
- [x] Cover reveal (or another non-Spatial style) still performs its ordinary direct destination transition.
- [x] Plexamp and Audio behaviour remain unchanged.

Do not add Settings as a fifth row member until AirPlay passes this gate.


