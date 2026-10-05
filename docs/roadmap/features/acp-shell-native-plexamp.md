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
- [~] First physical pass confirmed ACP gestures but showed the 300×30 Plexamp overlay was too wide/tall and intercepted the inner edges of Plexamp Library/Search taps. Refined candidate uses a ~180–200×22 px hit target with a ~140 px visible indicator; physical retest pending.


#### Refined Plexamp hit target + AirPlay first-paint correction

The first home-indicator candidate proved swipe reach over the Plexamp iframe, but its invisible target was too greedy. On the commissioned Pi, taps near the inner edges of Plexamp's Library and Search buttons could be intercepted by ACP and open the ACP drawer instead.

The refined contract is:

- the ACP gesture target is reduced from 300×30 px to roughly 180–200 px wide × 22 px high;
- the visible white home indicator grows to roughly 140 px, so the visible affordance now corresponds much more honestly to the usable swipe zone;
- ACP remains above the Plexamp iframe only in that narrow bottom-centre strip;
- swipe-up/open, swipe-down/close and tap fallback remain unchanged.

The same physical pass exposed an unrelated AirPlay first-mount flash: before `/api/status` resolved, the generic player layout briefly showed transport/volume controls and then collapsed into route-ready layout. AirPlay now stages an explicit `airplay-session-unresolved` state before first mounted commit (and on direct AirPlay document load). That unresolved state shares route-ready geometry and hides inactive controls. `airplay-live.js` removes the unresolved class atomically when the authoritative status response applies the real idle/active state.

Combined navigation/AirPlay candidate `735cf5162fa37ef138ab3f2fca18ba97e5d19ee4` passed **Tests #5216**.

After this slice is accepted, continue with the **navigation-mode overlay/recede treatment**, then the spatial row/carousel experiment with exactly one committed destination transition.
