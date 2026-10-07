# Native Plexamp desktop / visualiser migration

**Status:** ACTIVE — Phase A UI foundation; no native Plexamp production migration authorised  
**Roadmap item:** #94  
**Last updated:** 4 October 2026

## Goal

Investigate replacing the legacy Plexamp Headless + embedded browser UI with the
current ARM64 Linux desktop Plexamp so the bedside appliance gains native
visualisers and a supported desktop-player lifecycle without losing the parts of
A Clockwork Plex that are already physically accepted:

- NFC media launch;
- the managed `acp_plexamp` audio entry point and downstream trim / Music Master /
  CamillaDSP EQ / limiter / alarm-safe graph;
- alarm and AirPlay playback ownership;
- touchscreen-first navigation;
- backup/reset ownership;
- deterministic recovery and rollback.

This is a rehearsal-first migration. The accepted Headless runtime remains the
rollback until a native-player candidate passes all physical gates.

## Preferred player architecture

The preferred experiment is **native Plexamp as the real local decoder/player**,
not a second Plexamp instance acting only as a remote UI for Headless.

Target:

```text
NFC / ACP playback policy
          |
          v
native Plexamp
          |
          v
     acp_plexamp
          |
          v
Plexamp Trim -> Music Master -> reserve -> EQ -> limiter
          |
          +---- alarm-safe join
          |
          v
         DAC
```

A two-player arrangement may still be useful temporarily for discovery, but is
not the intended visualiser architecture because a remote controller does not
own the locally decoded audio data required by the visualiser.

## Phase A implementation checkpoint — A0

The first implementation checkpoint introduces a fail-safe same-document surface host without migrating any product surface yet.

Current ownership:

- `app/static/js/acp-surface-host.js` owns the future same-document lifecycle registry and View Transition commit boundary.
- A destination registers only when it has an explicit asynchronous `prepare()` function that returns a synchronous `commit()` function. This lets data/assets be prepared before the visual transition starts.
- `page-transitions.js` remains the navigation policy entry point for now, including screen-projection/manual-lease handling and Plexamp special cases.
- After those policy checks, `page-transitions.js` asks the surface host whether the destination is registered. Registered routes may commit in-document; unregistered routes continue through the existing full-document `window.location.assign()` path.
- The host updates active-surface body/navigation state and browser history only after a successful commit.
- If preparation fails, the host returns control so the caller can use the accepted full-route fallback.
- No Clock, Weather, News or Settings destination is registered at A0, so production navigation is intentionally unchanged.

This seam is the prerequisite for incremental migration. It avoids a flag-day SPA rewrite and provides a measurable rollback boundary for each surface.

### First migration candidate — implemented, physical gate pending

Use **Clock ↔ Weather** as the first real surface pair unless code inspection exposes a stronger blocker. It exercises:

- Clock hydration/live timers;
- Weather's data-heavy rendered surface and refresh lifecycle;
- per-surface CSS/script ownership;
- browser history/manual screen leases;
- the fixed 1280×720 appliance presentation.

Weather currently refreshes itself with a timed `window.location.reload()`. That must be retired as part of this first migration. The long-lived surface should instead consume an ACP-local Weather view-model/snapshot and patch changed values in place. Returning to Weather after another ACP surface should trigger an immediate snapshot refresh, while routine updates must preserve scroll/focus/open-panel state and must not invoke the top-level navigation transition engine.

The intended eventual browser boundary is one long-lived ACP document containing **all ACP-owned application surfaces** (Clock, Weather, News, AirPlay, Settings, Astronomy, future Events and alarm/takeover presentation). This does not mean one enormous permanently active DOM: surfaces may be lazily prepared, mounted, suspended and resumed behind the Surface Host contract. **Native Plexamp is the deliberate exception** and lives as a separate native application/workspace; the ACP desktop shell owns navigation and transitions across that process boundary.

Do not bring Settings transaction ownership, News modal/scroll lifecycle or Plexamp's persistent overlay into the first same-document experiment.

#### Clock ↔ Weather implementation shape

The first pair is implemented as a mount-once incremental bridge rather than a template rewrite:

- the initial Clock or Weather content is wrapped as a mounted surface after the shared navigation layer has moved its controls to `body`;
- the first visit to the other member of the pair fetches ACP's read-only rendered surface document from `/api/surfaces/<surface>`; this endpoint deliberately does not call `set_mode()`;
- missing destination styles load before commit; missing destination scripts load once after commit, when the destination is the active surface;
- both Clock and Weather DOM trees remain mounted thereafter and visibility toggles under the Surface Host, preserving their local interaction state;
- same-document activation synchronises `/api/mode/<surface>` after the visual commit while the existing manual lease/screen-projection policy remains the navigation authority;
- Weather's former periodic `window.location.reload()` has been retired. A Weather surface controller obtains a fresh ACP-rendered snapshot, replaces only the Weather data grid, preserves vertical and Rain-history scroll positions, leaves the forecast console mounted and rebinds refreshed grid controls;
- a failed surface preparation/script activation returns to the existing full-route fallback rather than trapping the appliance in a half-migrated state.

At this checkpoint only Clock and Weather register with the Surface Host, and only when the initial document itself is Clock or Weather. Entering Weather from News/Settings/AirPlay still uses the accepted full route; broader surface convergence follows only after this pair is physically accepted.

#### First physical result

The commissioned appliance confirms that the mount-once pair is visibly faster and eliminates full-page bootstrap flashes. Weather can refresh in place without resetting the reader's position, and Clock remains live after a round-trip.

The first pass also exposed two browser-lifecycle details that must be owned explicitly in the shell architecture:

- browser View Transition defaults are not ACP product motion; the shell maps ACP's configured transition style/duration to the View Transition snapshots. **Physical retest passed all configured styles and duration control**;
- component geometry measured during a surface commit can be temporarily zero/unstable. Custom controls such as Forecast scrollbars therefore need an explicit post-activation/settled-layout measurement hook rather than assuming first-frame geometry is authoritative.

These findings reinforce the Surface Host lifecycle model rather than arguing for a return to multi-document navigation.


#### A2 News migration — physically accepted

News validates that the Surface Host can own a more stateful content surface than Clock/Weather. The mounted News implementation pauses hidden refresh work, preserves story/category scroll state, defers custom-scrollbar geometry until the surface is settled, and retains article-detail/QR behaviour. Exact A2 candidate `b4e0943038779862816e65f1e291ae2b4ef2e571` passed Tests #5087 and the commissioned appliance physically accepted the News round-trip and transition behaviour.

#### A3 Settings migration — physically accepted

Settings is the first migrated surface where **transactional UI state must outlive navigation**. It therefore remains mount-once rather than being re-rendered on every visit:

- the read-only surface renderer supplies the same Settings template context as the ordinary GET route but never calls `set_mode()`;
- destination scripts load only after the Surface Host has committed Settings as the active surface, preserving existing `body[data-active-page="settings"]` initialisation guards;
- staged form values, active section/subpage and local Settings DOM state remain mounted across other ACP surfaces;
- background Settings diagnostics that previously relied on `pagehide` now also require Settings to be the active ACP surface before polling network endpoints, because hidden mounted surfaces no longer receive a document teardown;
- reactivation provides an explicit refresh opportunity for those diagnostics;
- AirPlay remains on the full-document fallback until Settings has passed its physical gate.

This is an important shell invariant: **surface-hidden is an application lifecycle state distinct from browser-hidden and document-unloaded**. Future ACP surfaces with timers, observers or background fetches must account for all three states explicitly.


The first A3 physical pass adds a second invariant: **persisted configuration and live-document configuration are separate responsibilities once document replacement is removed**. In the old route model, a successful save could rely on the next Flask-rendered document to repopulate root data attributes and page labels. A long-lived shell cannot rely on that implicit rebootstrap.

Therefore:

- a successful Settings transaction must project shell-owned values such as transition style/duration, startup/idle ownership, theme and clock format back into the live shell authority;
- the dashboard preference reader must prefer already-applied live values over immutable server boot attributes after initial bootstrap;
- surface-owned configuration changes must invalidate or refresh every affected mounted surface after persistence. Weather refreshes its detailed surface from the successful Settings event; Clock also refreshes its weather/status projection immediately and on Clock activation, so a save completing after navigation cannot leave either mounted Weather identity behind;
- server-rendered bootstrap controls that are retired by an enhancement (the old Settings Save/Discard bar) must have a first-paint-safe presentation rather than depending on late JavaScript to hide them.

This keeps autosave persistence authoritative without reintroducing full-document reloads as a hidden configuration-application mechanism.


A3 physical acceptance confirms these invariants on the commissioned Pi. The final Clock weather-title follow-up passed without document reload.

The migration also makes the former user-configurable **Dashboard observation refresh** cadence obsolete. Observation acquisition cadence belongs to the observation provider/service, while mounted ACP presentation refresh is shell lifecycle. Clock and Weather therefore use a fixed internal 60-second presentation refresh only while visible, plus immediate activation and relevant-settings refreshes. The retired `weather.auto_refresh_seconds` key is no longer exposed through Unified Settings or portable backup; old stored values are tolerated and ignored for upgrade compatibility.

#### A4 AirPlay migration — physically accepted

AirPlay is the first mounted surface whose presentation has several high-frequency clients while the underlying playback/session authorities remain useful even when the page is not visible. A4 therefore separates **AirPlay service authority** from **AirPlay presentation activity**.

`airplay-surface-lifecycle.js` is a presentation-only visibility authority. AirPlay is considered visible only when:

- `body[data-active-page="airplay"]` is authoritative;
- the browser document is visible;
- the persistent native Plexamp overlay is not visibly covering ACP.

It publishes only visibility changes, including Plexamp overlay class changes, so unrelated AirPlay body-class updates do not repeatedly reactivate clients.

The mounted AirPlay clients now follow that lifecycle:

- `airplay-live.js` suspends `/api/status` polling and progress/clock presentation ticks while hidden;
- coordinator transport and navigation clients suspend their 750 ms polling loops;
- receiver-volume polling and adaptive skip-mode polling suspend while hidden;
- the segmented mini-clock and outside-card compatibility synchroniser stop their timers while hidden;
- AirPlay layout and title-marquee measurement skip hidden geometry and explicitly remeasure on activation.

This does **not** move playback authority into the browser. Shairport/session state, playback coordinator commands, MPRIS observation, MixerController receiver volume and screen projection retain their existing owners. The shell only decides when the AirPlay DOM needs presentation work.


Commissioned-Pi acceptance confirms the complete AirPlay mounted-surface path, including manual and automatic entry, hidden-surface catch-up and return from the native Plexamp overlay.

A post-A4 Settings finding adds a small but important enhancement rule for the long-lived shell: **when upgrading a hydrated form control to a stricter HTML input type, install its constraints before changing the type and preserve the hydrated value explicitly**. Chromium's range-input sanitisation can otherwise apply default 0–100 bounds during the conversion itself. The Motion duration slider now sets its 0–2000 bounds/50 ms step first, then switches to `type=range`, restores the prior value and exposes a visible numeric output. This prevents presentation enhancement from mutating authoritative Settings data.


A second post-A4 finding generalises that rule from ranges to all Settings enhancements: **the server snapshot is authoritative; presentation widgets must be capable of representing that snapshot before they may participate in autosave**. The transition-style select previously gained several valid choices only after Javascript enhancement, so an early snapshot could assign a value the initial native select could not represent and lose it before enhancement.

The Settings boundary is therefore hardened as follows:

- accepted enum choices required for normal operation are present at first paint rather than relying on a later destructive option rebuild;
- if a backend-normalised saved value falls outside a preset dropdown's convenience choices, hydration adds a temporary current-value option instead of clearing the native select;
- programmatic hydration explicitly resynchronises custom-select and range presentation;
- dynamically inserted controls reuse the same hydration authority where practical;
- full-document Settings entry waits for the first authoritative Settings load (with a bounded fallback) before revealing the page;
- transactions clone the last authoritative snapshot and read values only from dirty UI sections/providers. Unrelated Settings controls therefore cannot overwrite authoritative values merely because they were temporarily stale or not yet enhanced.

This dirty-section rule is the defensive backstop for the entire Settings page: presentation hydration errors remain local rather than becoming cross-section configuration writes.


Commissioned-Pi retest confirms the hydration boundary: a formerly Javascript-only transition style and the transition-duration range both survive direct Settings hard reload while remaining authoritative for the live shell. The Settings hydration correction is accepted.


#### Phase A component/design-system boundary

With the ordinary ACP browser surfaces and Settings hydration contract accepted, presentation ownership now moves toward a reusable component/design-token layer. The first slice introduces semantic component tokens without changing feature geometry or service ownership. Shared panels/cards/buttons and the top-level Weather, News and AirPlay surface chrome consume the new vocabulary while the existing palette remains authoritative.

Detailed rules and migration inventory: [ACP component / design-token architecture](acp-design-system.md).

## ACP UI rendering decision

The native Plexamp investigation also exposes a separate ACP question: **should
Chromium continue to render the ACP product surfaces, or should those surfaces
eventually move into a native UI?**

The current transition implementation is not one uniform rendering model:

- ordinary ACP routes perform full document navigation and therefore have
  outgoing/incoming page boot choreography;
- Plexamp is a special persistent iframe/overlay with its own lifecycle;
- Settings behaves more like an in-document application with tabs/subpages;
- selected pages have hydration-aware reveal delays;
- screen projection, playback handoff and manual-surface leases can all influence
  when a transition is considered complete.

That mixture explains why the accepted transitions can still feel slightly less
immediate than a single continuously rendered appliance shell even after careful
optimisation.

### Decision options

Evaluate three architectures rather than framing this as a binary browser/native
choice:

1. **Current multi-document Chromium** — lowest migration cost, but retains the
   full-document navigation and mixed lifecycle boundaries that currently make
   transitions hardest to perfect.
2. **Single long-lived web surface inside an ACP shell** — keep Flask/HTML/CSS/JS
   and most current feature code, but migrate top-level ACP navigation toward one
   continuously loaded application surface. Page changes become in-process
   surface/state changes rather than browser document replacements.
3. **Native ACP surfaces** — implement some or all ACP pages in a native animated
   UI toolkit. If this path proves worthwhile, a declarative scene/state toolkit
   such as Qt/QML is a stronger fit than traditional widget-style UI because ACP
   relies heavily on touch, transforms, transitions and fixed 1280x720 appliance
   composition.

The preferred investigation order is **2 before 3**. The existing Flask APIs,
settings model, backup/reset ownership, themes, News, Weather, alarms and other
page logic are valuable working assets. Do not rewrite them merely to solve a
transition-ownership problem that may disappear once navigation stops causing
full document replacement.

A native shell may therefore own navigation and animation even if ACP content
continues to be web-rendered.

### Native rewrite threshold

A full or partial native rewrite is justified only if a prototype demonstrates
clear practical advantages over a single-document web surface in:

- transition smoothness and input latency;
- memory/GPU use on the commissioned Pi;
- touchscreen behaviour;
- visual consistency with the current ACP look;
- startup/recovery;
- implementation complexity;
- maintainability of Weather/News/Settings/Alarm-rich screens;
- testability and accessibility.

The existing look and feel is a product requirement regardless of rendering
technology.

## ACP design system and web framework boundary

The rendering investigation should preserve the long-standing separation between
content, layout and presentation rather than coupling page markup to a framework
theme.

Model ACP as four layers:

1. **content/data** — weather, news, alarms, settings values and playback state;
2. **reusable components** — setting row, status card, fader, forecast tile,
   segmented readout, navigation item and similar product primitives;
3. **design tokens/system** — colour roles, typography, spacing, radii, border
   treatment, elevation, touch targets and animation timings;
4. **application surfaces** — Clock, Weather, News, Settings, Astronomy and other
   top-level experiences.

Themes should primarily change design tokens. New feature markup should consume
reusable ACP components rather than inventing one-off card/field framing that
then needs a second styling pass.

### Material and third-party design systems

Do not adopt Material Web wholesale as the ACP visual identity. Material Design
is useful as a reference for token/component discipline, interaction states and
accessibility, but ACP has an established bespoke appearance and fixed appliance
geometry. The official Material Web Components project is currently in
maintenance mode, making it a poor new long-term foundation for the product.

If a component framework is introduced, evaluate it as an implementation aid,
not as the visual design authority. Prefer small primitives that can render ACP's
own design tokens and markup. Candidate approaches include native Web
Components/Lit-style custom elements and a compile-time component framework such
as Svelte; the prototype should justify any framework with lower complexity,
better reuse or smoother interaction rather than fashion.

### View-transition prototype

The single-document web candidate should explicitly prototype the browser View
Transition API for top-level ACP surface changes.

Preferred model:

```text
one ACP document
    |
    +-- Clock surface
    +-- Weather surface
    +-- News surface
    +-- Settings surface
    +-- Astronomy surface

state change -> document.startViewTransition(...) -> DOM surface swap
```

This removes the current full-document unload/boot/reveal boundary. The browser
captures the old view and new view for animation while ACP changes application
state inside one document.

Keep the ACP desktop shell as the transition authority only where navigation
crosses a process/workspace boundary (for example ACP <-> native Plexamp).
Within the ACP web surface, browser-native view transitions should be preferred
over a second competing top-level animation engine.

### Carousel interaction versus page transitions

Treat the spatial row/carousel as a **navigation-mode presentation**, not another
independent transition system.

When the user swipes up:

1. the shell enters navigation mode and the active surface recedes;
2. the horizontal surface row/carousel becomes the selection metaphor;
3. tapping a destination establishes the target/direction;
4. navigation mode exits;
5. exactly one destination transition commits.

For ACP-to-ACP changes, the destination commit should normally be a
same-document View Transition. For ACP-to-native-Plexamp changes, the desktop
shell performs the workspace/application transition.

Existing transition styles may survive as **destination reveal styles** (fade,
slide, cover, etc.), but they must be coordinated by one state machine rather
than running in parallel with the carousel. If the carousel provides the whole
spatial movement, the destination reveal should be deliberately restrained.

### Level-B B0 bounded spatial commit

The first carousel experiment intentionally implements **one relation only: Clock → Weather from open navigation**. Clock and Weather are already the oldest physically accepted mounted-surface pair, so they isolate spatial presentation from surface-lifecycle risk.

B0 does not build a second transition engine. Navigation policy marks that one selection with `spatialCommitDirection: "forward"` after manual-screen ownership has accepted Weather. The shell then exits navigation and waits for the configured Navigation transition duration. Once the Level-A sheet has returned to its closed state, the existing Surface Host performs its normal single `document.startViewTransition(commit)`.

For that one View Transition, the host temporarily exposes `data-acp-spatial-commit="forward"` on the document root. The first visual candidate used `±34vw`, 0.94 scale and opacity depth cues. Physical testing rejected that composition: because the snapshots no longer tiled the viewport, the incoming Weather edge exposed the white root background and the outgoing Clock read as a faded backing layer, producing an **overlay** metaphor rather than a row.

B0 v2 therefore uses an edge-lock invariant instead of depth effects:

- old Clock: `translateX(0) → translateX(-100vw)`, full scale/full opacity;
- new Weather: `translateX(100vw) → translateX(0)`, full scale/full opacity;
- duration: existing application `transition_duration_ms`;
- easing: the same ACP destination-transition cubic-bezier for both snapshots.

Because the two snapshots move equal distances with identical timing, the old snapshot's right edge and the new snapshot's left edge are coincident at every animation fraction. Physical testing confirms that geometric invariant when both root snapshots are valid.

The second B0 physical pass exposed a separate boundary: **snapshot readiness after navigation-sheet motion**. A nominal timeout equal to the navigation CSS duration is insufficient evidence that Chromium has painted the live surface's post-transform texture. On the Raspberry Pi the View Transition could occasionally capture the outgoing Clock root as blank/white even though Weather then followed the correct edge-locked trajectory. The architecture must therefore wait on a rendered-state signal rather than elapsed wall-clock time.

For B0 v3, the navigation policy attached to `main.screen` before closing the Level-A sheet and waited for the real `translate` `transitionend`/`transitioncancel` event, followed by two animation frames and a layout read. Repeated physical testing rejected that approach: 19 of 20 old-root captures were still white. The architecture therefore treats this as an unreliable **browser snapshot primitive** for the Pi spatial case rather than as a scheduling bug.

B0 v4 deliberately changes only the spatial presentation primitive. The mounted-surface model already keeps the outgoing ACP DOM alive, so the experiment can use that real DOM instead of asking Chromium to photograph the root:

- clone the current `main.screen` while Clock is still the visible mounted surface;
- make the clone non-interactive and copy the body background onto it;
- position the real live `main.screen` at `+100vw`;
- commit Weather into the real screen;
- use Web Animations to move the Clock clone to `-100vw` and Weather to `0` with identical timing;
- remove the clone and inline transform in a `finally` cleanup.

The Surface Host supports this through an optional `prepared.spatialCommit` lifecycle hook. The hook receives the normal `commit` callback, so logical surface ownership, body mode, navigation state, history, activation and settled events remain centralized in the existing host. Ordinary ACP transitions still use the View Transition API exactly as before.

This live-DOM strip has two architectural advantages beyond avoiding the blank texture: it uses the same mounted-surface objects the future carousel would actually own, and shell chrome such as the home indicator remains a real fixed shell layer rather than becoming part of a frozen root image. Commissioned-Pi testing accepts this mechanism across repeated runs and theme changes.

### Transition-style ownership for spatial navigation

A spatial compositor must not silently replace the user's chosen application Transition style. The B0 hard override was a test harness, not an acceptable production policy.

The Motion setting is therefore the policy selector, while individual styles are free to use different rendering backends:

- Grow/fade, Crossfade, Horizontal slide, Vertical lift, Cover reveal, Zoom and Blur dissolve continue to use the existing View Transition implementation;
- Instant continues to suppress decorative application movement;
- **Spatial row** uses the live-DOM mounted-surface strip where that relation has been implemented.

This keeps the user-facing model simple: **one Transition style setting, one Transition duration setting**. The implementation technology is an internal concern. Selecting Cover reveal must mean Cover reveal even when the destination was chosen from shell navigation; selecting Spatial row explicitly opts into spatial navigation semantics.

B0 proved Clock→Weather physically. B1 introduces the first actual ordered row with two members: `['clock', 'weather']`. Navigation derives forward/reverse direction from the current and target indices, and the application-surface compositor validates the same relation independently before animating. Both directions therefore use one direction-neutral live-DOM primitive rather than separate page-specific effects. Destinations outside the currently implemented row continue to map to Horizontal slide while Spatial row is selected; that fallback remains temporary and must disappear as the ordered model expands.

Direction is part of the Surface Host presentation contract and must survive intact from navigation policy to the prepared surface hook. B1 physical testing exposed an old B0 assumption in the host that normalised only `forward` and converted every other value to empty. That silently routed a valid reverse relation into the ordinary View Transition fallback, whose Horizontal-slide keyframes include opacity fading and only a few viewport-percent of movement. The host now explicitly accepts `forward` **or** `reverse`; unknown values alone are rejected. This keeps fallback behaviour for genuinely unsupported relations without masking a supported reverse direction.

The live-DOM compositor must also preserve **per-surface layout context** across the handoff. The Surface Host changes global body mode/data-active-page as part of committing the destination; destination CSS may legitimately style `main.screen` itself. For example, Weather changes the screen grid from `minmax(0, 1fr) auto auto` to `auto minmax(0, 1fr) auto`. If the outgoing clone remains dependent on global body selectors, it can relayout into destination geometry before leaving the viewport.

For B0 the compositor therefore snapshots the outgoing screen's computed **layout properties, not its pixels**: grid templates/auto tracks, alignment, gaps and padding are copied inline onto the temporary outgoing DOM layer before the destination commit. The old surface keeps its old geometry while the incoming real screen immediately adopts the destination mode.

B1 adds the complementary **presentation-context** rule. A live outgoing DOM surface cannot depend exclusively on selectors keyed to the document's single global `body[data-active-page]` value, because the destination commit legitimately changes that value before the outgoing surface has left the viewport. The compositor marks the temporary layer with `data-acp-surface-context="<outgoing-surface>"`. Surface-specific CSS that must remain visually authoritative during handoff can target either the live body state or this local outgoing context. Weather's theme component rules and forecast-console active-page rules are the first consumers.

This is preferable to copying computed colours onto every descendant: theme variables remain live, semantic states remain semantic, and the DOM surface still responds as a coherent surface. The architecture rule for any future multi-surface carousel is therefore two-part: **surface-local layout context plus surface-local presentation context**; global body mode remains the logical destination authority, not the sole styling authority for every simultaneously visible surface.

This policy also clarifies automatic projection: the destination mechanism should obey the selected application Transition style unless a product-critical event (for example alarm takeover) explicitly bypasses decorative animation.

The attribute is presentation-only and is removed after the transition, with a `finally` cleanup if the transition path fails. It does not alter logical surface order, history, leases, Weather lifecycle or persisted settings.

B0's asymmetric Clock→Weather test boundary is now closed: commissioned-Pi testing accepts the live-DOM row metaphor and its layout/style ownership. B1's architectural question is narrower—does the same ordered pair remain coherent when traversed in reverse without introducing a second code path or direction-specific geometry bug? Only after that two-member contract is physically accepted should a third surface be inserted into the order.

## Browser-engine evaluation

Changing browser should be treated as a measured optimisation experiment, not a
design migration.

Raspberry Pi OS supports Chromium and Firefox as first-class browser choices.
Compare the same single-document ACP prototype under Raspberry Pi OS Chromium
and Firefox for:

- animation frame pacing/jank;
- touch input latency;
- memory and GPU usage;
- startup time;
- View Transition behaviour;
- fullscreen/kiosk and Wayland integration;
- on-screen keyboard behaviour;
- remote-debug/recovery tooling.

Chromium remains the baseline because it is the Raspberry Pi OS-default path
already qualified by ACP. Firefox is the useful comparison because it is a
genuinely different rendering engine. Switching away from Chromium must justify
the cost of requalifying the existing kiosk, autoplay, iframe, touch and recovery
assumptions.

The likely optimisation order is therefore:

1. single-document ACP surface;
2. ACP component/design-system cleanup;
3. View Transition API;
4. measure Chromium;
5. compare Firefox only if performance or interaction still leaves a material gap.

## Display ownership

### Preferred first experiment: two compositor workspaces

Rather than stacking two fullscreen applications on one desktop, test:

- workspace 1: Chromium A Clockwork Plex dashboard;
- workspace 2: native Plexamp;
- deterministic ACP-owned switching between them;
- window rules that keep each application on its intended workspace;
- alarm takeover allowed to force the ACP workspace immediately.

The appliance must first verify its actual compositor/session at runtime rather
than assume labwc merely because it is the current Raspberry Pi OS default.

### Transitions

The current ACP screen changes feel deliberately polished and should not regress
to an abrupt desktop flash merely because Plexamp becomes native.

Top-level transition ownership should move into the ACP desktop shell so the same
visual grammar can cover:

- ACP web-surface to ACP web-surface navigation;
- ACP to native Plexamp workspace changes;
- native Plexamp back to ACP;
- alarm-forced presentation.

Content applications should provide readiness/state signals, not each implement
their own incompatible top-level transition choreography.

Preferred investigation:

1. ACP requests a screen/application transition.
2. A small ACP-owned Wayland overlay covers the output.
3. The overlay performs a short fade/slide.
4. The compositor switches workspace underneath.
5. The overlay reveals the destination.

This keeps animation policy under ACP while leaving the supported compositor
responsible for actual window/workspace ownership.

Compiz-style cube/exposé experiments are welcome as a development curiosity, but
must not become a reason to replace the supported compositor unless an
alternative proves equally reliable for boot, VNC, touch, alarms and recovery.

Alarm takeover is safety/product behaviour and may bypass decorative animation
if necessary.

## ACP desktop shell candidate

A small, independently restartable **ACP desktop shell** is worth prototyping as
the shared owner of UI that must appear above both Chromium and native Plexamp.

Possible responsibilities:

- bottom home-indicator affordance plus swipe-up navigation surface;
- cross-application navigation state;
- transition overlay and optional snapshot-based spatial effects;
- deterministic ACP/Plexamp workspace switching;
- optional system-level on-screen keyboard surface.

Explicit non-responsibilities:

- no audio routing;
- no playback arbitration;
- no NFC media interpretation;
- no alarm scheduling;
- no persistent settings authority beyond its own presentation preferences.

The shell should fail open: if it crashes, Chromium/Plexamp audio must continue,
and there must remain an SSH/VNC recovery path.

## Navigation shell and bottom-edge gesture

The preferred end-state is **not** a permanently visible navigation pill.

Use a small iPhone-style horizontal home indicator at the bottom edge to make the
gesture discoverable without permanently occupying useful content space.

Preferred interaction:

1. content is full screen with only the small bottom indicator visible;
2. swipe upward from the bottom edge;
3. the ACP desktop shell reveals the navigation surface;
4. the current content visually recedes enough to establish that navigation is a
   separate system layer;
5. the user chooses another ACP surface or native Plexamp;
6. the shell performs the selected transition;
7. navigation slides away and the destination returns to full-screen scale.

### Navigation presentation experiments

Test two levels of ambition.

**Level A — production-first overlay**

- current app remains live beneath the shell;
- shell dims/slightly masks the content and slides navigation in from the bottom;
- target selection triggers the transition/workspace switch;
- no compositor modification and no live-window scaling requirement.

**Level B — spatial surface strip / carousel**

Investigate the proposed model where ACP surfaces conceptually form a horizontal
row. When navigation opens, the active surface appears to shrink/recede and the
shell can slide toward the selected destination before committing the real page
or workspace switch.

Do not require the compositor to provide arbitrary live-window scaling. If a
convincing spatial transition needs a frozen screenshot/texture of the current
surface, treat that as an optional presentation technique and measure latency,
GPU cost and failure behaviour. The actual application/workspace remains the
authority underneath.

A true live Compiz-style window strip would require compositor-level transforms
that labwc intentionally does not provide as a product API; do not make a custom
compositor a prerequisite for ACP navigation.

### Cross-application ownership

The bottom indicator and revealed navigation must be visible over both Chromium
ACP and native Plexamp. Therefore they belong to the ACP desktop shell rather
than either content application.

During an incremental migration the browser's current HTML pill may remain as a
fallback, but the target design is one cross-application shell affordance rather
than two separate navigation implementations.


The first browser-shell ownership slice removes one historical ambiguity. `_nav.html` is now rendered once by `base.html`, outside `main.screen`, rather than being included by every page and moved into `<body>` by `nav-layer.js`. Mounted application surfaces therefore contain application content only; primary navigation is persistent shell chrome. The relocation shim is removed.

This slice deliberately retains the accepted handle/drawer interaction so structural ownership can be physically accepted independently from the later home-indicator/navigation-mode presentation.

Physical testing of that ownership slice exposed a second requirement: persistent shell DOM needs persistent **behavioural** ownership too. A shell control must not depend on a listener bound once to a particular element instance if later application-surface work can leave that instance stale. The navigation handle therefore uses delegated document-level tap/touch handling and resolves the current shell node on demand. The shell Audio button is static markup, while its dynamic mixer/EQ internals are idempotently reasserted after `acp:surface-settled`.

The shell also one-instance guards `nav-drawer.js`; this prevents duplicate long-lived listeners from turning one tap into multiple open/close toggles. Asset versioning is part of the boundary because a persistent shell cannot safely mix a newly rendered template with a stale cached behaviour owner.


Commissioned-Pi retest accepts that lifecycle contract. One cross-application input boundary remains important: pointer/touch events originating inside the persistent Plexamp iframe do not bubble into the ACP document. The shell must therefore own a real hit target above the iframe for any bottom-edge gesture it expects to work while Plexamp is visible.

The first home-indicator pass confirmed the cross-iframe approach, but physical testing showed 300×30 px was still large enough to intercept the inner edges of Plexamp Library/Search taps. The accepted design rule is therefore stricter: the ACP-owned region should be only modestly wider than the visible indicator and as shallow as reliable touch acquisition allows. The refined candidate uses roughly 180–200×22 px around a roughly 140 px visible bar. Swipe-up opens, swipe-down closes, and tap remains a fallback.

AirPlay also needs an explicit first-paint state in the long-lived shell. A newly mounted AirPlay surface is now staged as `airplay-session-unresolved` before it becomes visible. That state deliberately shares route-ready geometry and hides transport controls until the authoritative status response changes the body to idle or active. Direct AirPlay document loads receive the same unresolved class from the server template. This prevents asynchronous state resolution from visibly reflowing a false generic-player first frame.

### Gesture gate

Physically test:

- collision with Plexamp's Home/Library/Search/Settings bar near the bottom edge;
- ordinary vertical scrolling;
- touch starts within the narrow home-indicator target;
- slow/short swipes versus intentional navigation swipes;
- accidental activation during visualiser interaction;
- alarms and forced screen changes;
- screen dim/night behaviour;
- VNC as a development convenience, without making perfect VNC gesture fidelity
  a production requirement.

A tap on the home indicator may optionally reveal navigation as an accessibility
fallback.


### Production-first navigation mode

The refined home-indicator/cross-iframe gesture contract is physically accepted. Before attempting the Level-B spatial carousel, the shell now implements the Level-A treatment described above:

- the active application remains live;
- a shell backdrop sits above content but below navigation;
- opening navigation slightly recedes the active ACP surface or Plexamp layer using individual CSS `scale` and `translate` properties;
- the backdrop dims the content and owns outside-tap dismissal;
- drawer buttons and destination switching remain unchanged.

Using individual transform properties is deliberate. ACP page transitions and the persistent Plexamp handoff already use the `transform` property; navigation mode must compose with those systems rather than replace their animation value. Plexamp's transition list therefore explicitly includes `scale`, `translate` and `border-radius` so the recede animates consistently.

This Level-A treatment is the production fallback even if the later spatial-carousel experiment proves too expensive or visually fragile on the Pi.


Physical acceptance also establishes that **navigation mode is shell state, not application state**. An explicit destination change made while navigation is open should keep that shell state regardless of whether the destination is another mounted ACP surface or persistent Plexamp. Plexamp presentation APIs therefore accept a `preserveNavigation` hint for explicit shell navigation. Automatic projection changes intentionally do not use it.

The remaining Plexamp→different-ACP full-document fallback transfers only that presentation state through a short-lived pathname-scoped `sessionStorage` token. The incoming nav owner consumes it before the booting document is revealed, preserving the Level-A visual contract without making navigation persistence a server concern.

The `0.84 / -28px` follow-up physically proves the required clearance: the live application's bottom edge can sit above ordinary navigation while shell state survives the Plexamp boundary. It also shows that an app-card scale is not necessary for the production treatment. At 1280×720, shrinking the whole application to 84% costs useful legibility and makes cross-document restore more visibly expose the moment when recede geometry is applied.

The full-scale experiment confirms `scale: 1` is the better production model. Fixed translations are not robust enough, however: `-90px` over-corrects and creates a large void, while `-28px` under-corrects and lets the drawer cover live content. The production geometry therefore derives the reveal distance from the ordinary drawer itself. `nav-drawer.js` measures the main navigation row plus the drawer's vertical padding, borders and bottom inset, publishes that as `--acp-navigation-reveal-height`, and ACP/Plexamp translate upward by exactly that value. Commissioned-Pi testing accepts this measured live-surface distance. The home indicator is part of the same physical assembly and must therefore use the **same** variable, duration and easing; historical fixed `64px/56px` handle offsets are not an independent geometry authority.

Navigation motion owns an independent timing authority. Application-surface changes continue to use `transition_duration_ms` and the selected transition style. Opening/closing ordinary navigation uses `navigation_transition_duration_ms` (default 180 ms) through `--acp-navigation-transition-duration` for the drawer, indicator, backdrop and ACP/Plexamp lift/rounding. This avoids a long page-transition preference making a small shell gesture sluggish.

The commissioned-Pi slow-motion test tightens "synchronised" into a geometry invariant rather than merely a shared duration: the **live surface bottom edge, home indicator and drawer top edge form one moving sheet**. If the measured reveal height is `H`, the live surface and indicator move `0 → -H` while the drawer moves `+H → 0`, using the same easing curve. At every intermediate animation fraction their adjoining edges therefore remain coincident. A drawer-specific `calc(100% + 18px)` path or generic `ease` violates that invariant even if the endpoints happen to look correct. The drawer also has no independent opacity choreography: it is visible throughout the sheet movement and becomes hidden only after the closed position is reached, preventing a separate fade from creating a perceptual lag despite correct geometry. The final commissioned-Pi retest passes this invariant in both directions at 1000 ms and at normal timing; this Level-A motion contract is now physically accepted.

Audio is a deliberate exception because it is a **content overlay opened from navigation**, not an enlargement of navigation itself. The ordinary bottom nav therefore stays at its normal measured position. The mixer is a fixed shell overlay between the backdrop and nav, laid over the current application surface, and its reveal/hide uses `--acp-transition-duration` so it follows the user's ordinary application Transition duration. The older `audio-polish.js` animation owner is retired; one component should not have fixed 225/300/320 ms timings fighting the configured motion authority.

### Current-route navigation is a shell no-op

A main-nav tap on the already-active mounted ACP surface is not a navigation request and must never fall through to browser default link behaviour. The persistent shell owns the interaction: consume the event, leave the active surface untouched and preserve the current navigation-mode state. This is distinct from Plexamp, whose visible presentation can legitimately differ from the underlying ACP route, and from Audio, which is a shell overlay button rather than a route.

The former `target.href === window.location.href` early return was unsafe because it returned **before** `preventDefault()`; Chromium then performed a normal same-URL document load, producing a black boot flash and discarding the open drawer. Current-route detection now compares the target pathname with the Surface Host's `activeRoute()` and explicitly consumes the tap while Plexamp is not visibly open. Commissioned-Pi testing passes this contract across all mounted ACP destinations: no transition, no hard reload and navigation remains open.

### Pre-snapshot hydration for script-owned surfaces

Same-document View Transitions introduce another lifecycle boundary beyond `activated` and `settled`: Chromium captures the **incoming snapshot immediately after the update callback**. If a destination's final geometry is produced by target-specific JavaScript, activating those scripts only after `updateCallbackDone` is too late—the transition can freeze an unhydrated target and then visibly reflow when the live DOM catches up.

The Surface Host therefore supports an optional async `beforeSnapshot` hook. The update callback commits the destination DOM/body state, then awaits `beforeSnapshot` before Chromium captures the new snapshot. This hook is intentionally opt-in rather than a new global delay.

AirPlay is the first user of the boundary. On each AirPlay entry the application-surface owner resets the body to `airplay-session-unresolved`, ensures the AirPlay scripts are loaded, publishes activation, and awaits `ACPAirPlayHydration.waitForReady()`. The reusable hydration authority waits for resolved idle/active/metadata state plus two animation frames before signalling readiness. This ensures the segmented mini-clock, weather glance and status-dependent hero geometry are already stable in the **incoming snapshot**. The configured transition itself is unchanged: for example, Cover reveal still legitimately shows the old page on the unrevealed side while it runs.

## Touchscreen keyboard

The existing ACP Search keyboard is browser/DOM-owned and therefore cannot type
into a separate native Plexamp window.

Native migration is blocked until Plexamp Search and other ordinary text fields
are usable from the touchscreen.

Investigation order:

1. test the current Raspberry Pi OS Wayland on-screen keyboard over native
   fullscreen/maximised Plexamp;
2. test the same keyboard over Chromium kiosk to document the current layering
   difference;
3. if the distribution keyboard is unreliable, prototype an ACP-owned overlay
   keyboard using an appropriate Wayland input / virtual-keyboard mechanism;
4. keep password/login/claim entry outside any broad ACP key-injection bridge
   unless separately reviewed;
5. verify focus, Shift/backspace, dismissal, repeated searches and return to ACP.

If an ACP desktop shell is created, the navigation overlay and keyboard may share
that process, but the keyboard remains presentation/input plumbing rather than
playback authority.

## NFC / Companion compatibility

Current NFC tags contain Plex playMedia URLs which the listener rewrites to the
local Plexamp Companion receiver. Discovery must establish whether native Linux
Plexamp exposes compatible local receiver endpoints for:

- `/player/playback/playMedia`;
- timeline/status polling used by ACP;
- queue/activity semantics used to detect a fresh NFC launch.

Prefer adapting the endpoint/configuration around the existing tag format rather
than rewriting the physical NFC library.

## Audio acceptance

Native Plexamp must be able to feed the existing ACP-owned audio boundary.

Preferred route:

```text
native Plexamp -> ALSA acp_plexamp -> accepted fixed-192 managed graph
```

Physical gates include:

- native app sees/selects `acp_plexamp` or an equivalent controlled host ALSA
  endpoint;
- no competing Plexamp EQ/volume authority is silently introduced;
- Plexamp trim, Music Master and ACP EQ remain effective;
- fixed-192 processing/DAC diagnostics remain truthful;
- Direct failback/recovery remains valid;
- AirPlay and alarm takeover behaviour remains accepted.

## Runtime and resilience boundary

#94 begins **after #85 and before Astronomy**. Its Phase A application-shell /
single-document foundation is accepted before Astronomy starts, so Astronomy is
not knowingly built in the legacy multi-document model and then migrated.

Astronomy may begin once that UI/application-surface contract is stable; it does
not need to wait for every later native-Plexamp lifecycle gate if those player
experiments are still continuing. Full Appliance Resilience follows the
modernisation so it hardens the architecture that actually survives #94 rather
than fully hardening components that may be retired.

However, #94 itself must still prove minimum resilience before migration:

- reversible install/uninstall;
- Headless rollback retained;
- clean reboot/autostart;
- Plexamp crash and restart;
- Chromium crash and restart;
- desktop-shell crash and restart if introduced;
- alarm behaviour during/after player failure;
- VNC/SSH recovery;
- no boot loop if native Plexamp cannot start.

## Remote support

The commissioned appliance is routinely inspected over VNC/SSH. Any workspace,
overlay, native Plexamp or keyboard design must remain visible and operable both
on the physical touchscreen and through the supported remote-access path.

A design that works locally but leaves VNC blind to the foreground Plexamp or ACP
overlay is not acceptable.

## Backup / reset ownership

Do not assume the current browser bridges or Headless storage map directly onto
the rewritten native app.

Classify before migration:

- login/claim identity;
- player identity/name;
- native Plexamp preferences;
- Home customisation;
- visualiser preference;
- selected ACP audio device;
- portable vs machine-local state;
- Reset behaviour;
- Backup/Restore behaviour.

## Acceptance boundary

Headless may be retired only after the native candidate passes:

- visualiser/GPU load;
- ALSA/ACP audio path;
- NFC;
- Companion/timeline observation;
- touchscreen keyboard;
- Chromium/Plexamp workspace switching;
- navigation/edge return path;
- transition presentation;
- alarms;
- AirPlay handoff;
- Direct failback/recovery;
- backup/reset ownership;
- reboot/autostart;
- crash/recovery;
- longer ordinary-use stability.

### Settled-layout lifecycle

The first Forecast control regression exposed an important distinction between **activated** and **settled** surfaces. A mounted surface can be logically active while the compositor is still animating old/new View Transition snapshots, and a hidden mounted surface can legitimately report zero-width geometry to ResizeObserver.

The Surface Host therefore exposes two different lifecycle moments:

- `acp:surface-activated` — logical destination is committed and may begin normal application work;
- `acp:surface-settled` — emitted only after the browser View Transition's `finished` promise resolves, suitable for geometry-dependent controls.

Geometry-dependent components must not interpret zero-width measurements from a hidden mounted surface as authoritative state. Forecast custom scrollbars now preserve their previous visibility while hidden and remeasure on the settled event.

### Clock ↔ Weather A1 accepted

Physical retest closes the first same-document migration gate:

- configured transition style and duration are authoritative;
- geometry-dependent Forecast controls survive repeated hide/show cycles using the settled-layout lifecycle;
- Clock and Weather remain healthy across repeated round-trips;
- News and Settings continue to use the fail-safe full-route fallback.

This establishes the Surface Host contract as suitable for incremental migration of additional ACP-owned application surfaces.

### A2 — News joins the application-surface set

After Clock ↔ Weather A1 acceptance, the pair-specific loader is replaced by the generic `acp-application-surfaces.js` owner. The first registered set is now Clock, Weather and News.

News keeps its existing local `/api/news` ownership and rendered UI logic. The mounted-surface adaptation is lifecycle-only:

- hidden News does not continue useful 60-second refresh work;
- reactivation fetches one fresh local News snapshot;
- story/category scroll positions are preserved across routine snapshot renders;
- story and category custom scrollbars follow the same hidden-geometry / `surface-settled` rule established by Weather;
- the article-detail / QR modal remains part of the mounted News surface;
- Settings and AirPlay remain outside the registered set during A2 to preserve a known full-route escape/fallback path.

This is intentionally an incremental migration, not a News redesign.
