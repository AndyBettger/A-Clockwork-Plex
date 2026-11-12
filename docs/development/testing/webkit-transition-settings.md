# WebKit preview — saved transition styles and timings

Issue #94, development Pi only. This checks saved Settings against the ephemeral WebKit renderer. The accepted forced Cover preview is a separate comparison. Native Plexamp cross-window transitions are a later integration gate.

## Start the Settings-driven preview

Pull and restart ACP once for the updated application asset. Subsequent setting changes need no service restart. In the **normal ACP window**, open **Settings → Display → Motion**, choose a style, set **page transition 800ms / navigation transition 180ms**, and Save. The preview still refuses Settings POSTs; do not save through its Settings page.

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

The configured profile preserves the saved style and both timings. It enables accepted F11 navigation, F10 for actual Spatial routes, covered content preparation and News copies **only when Cover Reveal is selected**. Do not add the forced-Cover readiness/layer flags to this command. No new backend write capability is enabled.

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

On a normal day-renderer path the six-route counters are: ordinary styles **6 native transitions**, Cover **4 native + 2 News copy reveals**, Spatial **6 frame-strip movements**, Instant **no native/copy/strip animation**. No retained guard/mask/strip at rest. Record `astronomyNightActive` and actual renderer: the existing Astronomy Red live-DOM path can legitimately replace native capture. Native promise failures, incomplete content waits, incorrect style/duration, visual artifacts or missing route completion are not passes.

## Timing checks

After style coverage, use Crossfade and Cover Reveal to compare page **300ms → 1200ms** while keeping navigation **180ms**. Then hold page **800ms** and compare navigation **100ms → 800ms**. Repeat one Spatial Clock→News movement at a short/long page duration to check the whole multi-page movement. Finish with page **0ms / navigation 0ms**, verifying no timed movement; restore the preferred Settings afterwards.

Page and drawer timing must vary independently. Total request time includes preparation, network, layout and capture overhead; it need not equal animation duration. Slow scheduling or a nominal 120fps recording does not prove display FPS. Do not lengthen settled content waits to hide a renderer issue.

## Read the output

- `configuredSettings.source:'server-template'`, `raw`, normalized `saved`, and **`matches:true`** verify the effective preference choice/page/nav values against that document's saved settings. A local override must report a mismatch.
- `cssPageDuration` / `cssNavigationDuration` expose the actual root CSS timing variables; `navChrome` includes computed drawer/handle transition durations. Page values normalize in 50ms steps, navigation in 20ms steps, retaining zero.
- `nativeTransitions.lastPresentation` reports the style/requested duration/CSS value at capture and samples available `acp-in-*` / `acp-out-*` animation timings once at native readiness. `not-exposed` / `unavailable` explicitly means no effect-level timing evidence, not a fabricated success. `coverReveal` remains a compatibility alias for these native counters in configured mode.
- `newsLiveCover.durationMs` and `frameStripLast.durationMs` report the copy/Spatial renderer's actual configured animation budget. `prefersReducedMotion` records the system preference; note any legitimate reduced-motion override.
- F8 is an intentional document boundary. Ordinary F1–F5/drawer changes must remain same-document. Check completion/errors and video per style, rather than adding counters across F8 resets.

Keep command output and a recording with the chosen styles/timings identified. Passing lifecycle tests does not close this Pi visual/timing gate or overall resource acceptance.
