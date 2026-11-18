# WebKit preview — saved transition styles and timings

Issue #94, development Pi only. This checks saved Settings against the ephemeral WebKit renderer. The accepted forced Cover preview is a separate comparison. Native Plexamp cross-window transitions are a later integration gate.

## Current round and results

**Round 1 uses page 2000ms and drawer open/close 1000ms for all nine styles.** The drawer value is its opening/closing animation, not its inactivity timeout. Faster timings follow only after this round passes.

[Results CSV](webkit-transition-results.csv) is the maintained attempt log: one row per style/attempt, with timings, Settings/API evidence, visual result, next action and attachment names. Preserve failed attempts when appending retests. Blank measurements mean no result, not zero or PASS. Earlier preview acceptance is separate from this standardized round.

**Current test is GF-004, Grow and fade.** GF-001 and GF-002 flashed the outgoing page at completion. GF-003 (`d5883158`) cleared the flash on all six routes and exposed a smoothness problem. Weather → News received seven frame callbacks and paused for up to 504ms by keyboard and 478ms by drawer. Use those results to compare GF-004 at the same timings. The other eight styles await their first Round 1 run. [GF-003 route measurements](test-catalogue.md#18-november-2026--growfade-frame-timings-on-the-pi)

## Start the Settings-driven preview

Pull and restart ACP once to load the updated application script. If you kept the settings from GF-003, launch the preview directly after restarting. To change them, save **Grow and fade**, **page transition 2000ms** and **navigation transition 1000ms** under **Settings → Display → Motion** in the normal ACP window.

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
sudo systemctl restart a-clockwork-plex.service
```

```bash
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

After changing and saving Motion settings in the normal ACP window, return to the idle preview and press **F8**. This intentionally reloads Clock with a cache-busted GET, bringing fresh server-template settings. Counters/mounted pages reset for that document. The 300s window deadline does not reset: relaunch the same command between batches if needed. Escape exits.

## Style matrix

For each row, save the style, press F8, then run **F2 → F3 → F1** and **drawer Weather → News → Home**, allowing each route to finish. Record flash, geometry/card painting, direction, stutter, selected marker and final pill. The nine options may be split into three sessions of three styles.

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

For **GF-004**, run **F2 → F3 → F1**, then **drawer Weather → News → Home**. Let each page settle and watch for one more second. Check whether the grow and fade look smooth, especially on both News entries, and whether the old page stays gone. Keep the output and recording together.

Expect six changed/settled routes, six uses of **`frame-transform`**, final phase `released`, page budget 2000ms, zero native transitions and zero remaining copies at rest. Compare each released `frames`, `maxFrameGapMs` and `elapsedMs` with the same GF-003 route. Larger callback counts and shorter gaps would support a visible improvement. Record the visual result from the Pi.

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
- The CSV's final four columns record whether the old page returned at completion, the fewest frame callbacks on any measured route, the longest gap between callbacks, and the longest measured frame loop. Enter measurements only for runs that expose them. Use the per-route table for keyboard/drawer comparisons.
- F8 is an intentional document boundary. Ordinary F1–F5/drawer changes must remain same-document. Check completion/errors and video per style, rather than adding counters across F8 resets.

Keep command output and a recording with the chosen styles/timings identified. Passing lifecycle tests does not close this Pi visual/timing gate or overall resource acceptance.
