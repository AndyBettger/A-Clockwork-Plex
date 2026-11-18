# WebKit preview — saved transition styles and timings

Issue #94, development Pi only. This checks saved Settings against the ephemeral WebKit renderer. The accepted forced Cover preview is a separate comparison. Native Plexamp cross-window transitions are a later integration gate.

## Current round and results

**Round 1 uses page 2000ms and drawer open/close 1000ms for all nine styles.** The drawer value is its opening/closing animation, not its inactivity timeout. Faster timings follow only after this round passes.

[Results CSV](webkit-transition-results.csv) is the maintained attempt log: one row per style/attempt, with timings, Settings/API evidence, visual result, next action and attachment names. Preserve failed attempts when appending retests. Blank measurements mean no result, not zero or PASS. Earlier preview acceptance is separate from this standardized round.

**Grow and fade passed Round 1. Crossfade (CF-001) is next.** All six Grow and fade routes settled on `521535c6`. The operator saw smoother motion and the outgoing page stayed gone. Weather → News had 46 and 47 callbacks by keyboard and drawer, up from seven each. Eight styles await a Round 1 result. [GF-004 Pi measurements](test-catalogue.md#18-november-2026--grow-and-fade-passes-round-1)

## Start the Settings-driven preview

In the **normal ACP window**, open **Settings → Display → Motion**, choose **Crossfade**, keep **page transition 2000ms / navigation transition 1000ms** and save. The GF-004 build of ACP already supports this test. If the preview is still open and idle, return to it and press **F8** to reload Clock with the saved settings. If the preview has ended, start a fresh one from Clock with the following command.

```bash
cd ~/A-Clockwork-Plex
env -u WEBKIT_DISABLE_DMABUF_RENDERER \
  WEBKIT_DMABUF_RENDERER_FORCE_SHM=1 \
  /usr/bin/python3 scripts/try-webkit-gtk-shell.py \
  --show --page clock \
  --surface-transition-trial \
  --surface-transition-mode configured \
  --rain-width-trial --weather-flick-trial \
  --seconds 300 --width 853 --height 480 --fullscreen
```

The configured profile reads the saved style and both timings. It enables F11 navigation, F10 for Spatial routes, covered content preparation and News copies for Cover Reveal. For Grow and fade, GF-004 uses each frame timestamp to set the opacity and centred transform of the source and destination viewports. Each page keeps its layout and scroll position. The renderer hides the old page before the live destination takes over.

Leave F6/F7/F10/F11 untouched during this matrix so the accepted comparison settings stay consistent.

F8 fetches the saved settings and resets the route counters for the new document. A fresh launch also reads the saved settings. Each session lasts up to 300s. Escape exits.

## Style matrix

For each style, run **F2 → F3 → F1** from Clock, then **drawer Weather → News → Home**. Let each transition finish and watch for one further second. Record the selected style, page motion, any flash or stutter, News card alignment, selected navigation button and final pill. Pause the round if a style fails.

| Settings label | Effective style | Expected distinction |
| --- | --- | --- |
| Grow and fade | `grow-fade` | Small page grow/fade |
| Crossfade | `crossfade` | Opacity change |
| Horizontal slide | `horizontal-slide` | Small horizontal slide/fade |
| Vertical lift | `vertical-lift` | Vertical lift/fade |
| Cover reveal | `cover-reveal` | Direct wipe to target; News uses accepted DOM copies |
| Zoom | `zoom` | Larger scale/fade |
| Blur dissolve | `blur-dissolve` | Blur/fade |
| Spatial row (prototype) | `spatial-row` | Clock↔News traverses Weather; configured duration covers the whole movement |
| Instant | `none` | No timed page animation; a stored page duration does not enable one |

**CF-001 checks.** The pages should stay in place as one fades out and the other fades in. Watch both entries into News and the first second after each handoff for the outgoing page flashing back. Keep the output and recording together.

For the ordinary day renderer, expect six changed and settled routes, six native transitions started/ready/finished, zero route or native errors and zero uses of Grow and fade copies. Look for `configuredSettings.matches: true`, style `crossfade`, CSS timings of 2000ms/1000ms and a 1s drawer/handle. If WebKit exposes the animation timings, both `acp-in-crossfade` and `acp-out-crossfade` should report 2000ms.

For later normal day-renderer tests: the remaining ordinary styles use **6 native transitions**, Cover **4 native + 2 News copy reveals**, Spatial **6 frame-strip movements**, Instant **no native/copy/strip animation**. No retained guard/mask/strip at rest. Record `astronomyNightActive` and actual renderer: the existing Astronomy Red live-DOM path can legitimately replace native capture. Native promise failures, incomplete content waits, incorrect style/duration, visual artifacts or missing route completion are not passes.

## Timing checks

**Deferred until all nine styles pass Round 1 at 2000/1000ms.** Then use Crossfade and Cover Reveal to compare page **300ms → 1200ms** while keeping navigation **1000ms**. Hold page **2000ms** when comparing navigation **100ms → 800ms**. Repeat one Spatial Clock→News movement at a short/long page duration to check the whole multi-page movement. Finish with page **0ms / navigation 0ms**, verifying no timed movement; restore the preferred Settings afterwards.

Page and drawer timing must vary independently. Total request time includes preparation, network, layout and capture overhead; it need not equal animation duration. Slow scheduling or a nominal 120fps recording does not prove display FPS. Do not lengthen settled content waits to hide a renderer issue.

## Read the output

- `configuredSettings.source:'server-template'`, `raw`, normalized `saved`, and **`matches:true`** verify the effective preference choice/page/nav values against that document's saved settings. A local override must report a mismatch.
- `cssPageDuration` / `cssNavigationDuration` expose the actual root CSS timing variables; `navChrome` includes computed drawer/handle transition durations. Page values normalize in 50ms steps, navigation in 20ms steps, retaining zero.
- `nativeTransitions.lastPresentation` reports the style/requested duration/CSS value at capture and samples available `acp-in-*` / `acp-out-*` animation timings once at native readiness. `not-exposed` / `unavailable` explicitly means no effect-level timing evidence, not a fabricated success. `coverReveal` remains a compatibility alias for these native counters in configured mode.
- `newsLiveCover.durationMs` and `frameStripLast.durationMs` report the copy/Spatial renderer's actual configured animation budget. `prefersReducedMotion` records the system preference; note any legitimate reduced-motion override.
- `pageCopies` reports Grow/fade's route, renderer, phase, preparation time, duration budget and frame-loop measurements. The GF-004 `samples` contain the two masks' computed opacity and transform at the start, near the middle when a callback is available, and at the end. Zero duration or reduced motion produces just a final sample. The incoming mask ends at opacity 1 and the identity transform, and the outgoing mask ends at opacity 0. `pageCopiesApplied` counts uses and `pageCopyCount` counts masks still attached.
- The CSV records whether the old page returned, the fewest frame callbacks, the longest callback gap and the longest frame loop. These three frame statistics use only routes with final frame timings. The last column gives the number of such routes. A route can settle between log samples. Its in-progress values belong in the per-route notes.
- F8 is an intentional document boundary. Ordinary F1–F5/drawer changes must remain same-document. Check completion/errors and video per style, rather than adding counters across F8 resets.

Keep command output and a recording with the chosen styles/timings identified. Passing lifecycle tests does not close this Pi visual/timing gate or overall resource acceptance.
