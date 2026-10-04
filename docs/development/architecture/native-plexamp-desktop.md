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
