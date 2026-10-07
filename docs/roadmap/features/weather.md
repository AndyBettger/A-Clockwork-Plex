# Weather

**Status:** CORE COMPLETE; rain-event maintenance MERGED; #94 live-surface integration ACTIVE; post-#94 presentation revamp queued  
**Primary implementation:** #86 Friendly forecast-location entry, #87 WU supplemental indoor expiry

## Accepted scope

- Friendly town/city/postcode forecast-location entry with manual coordinate fallback.
- Weather Underground and Ecowitt observation ownership as documented by the current Weather architecture.
- Historical rainfall/cache-backed current and previous calendar periods.
- Supplemental indoor readings expire when stale rather than remaining indefinitely.
- Touch-first Weather presentation, forecast and rainfall views physically accepted.

## Current maintenance — rainfall event semantics

The live WU path derives Hourly Rain and Event Rain when the provider does not supply native values.

### Maintenance implementation — 4 October 2026

The focused rain-event correction is implemented, physically accepted and merged into `develop`. The commissioned Pi passed the live backend/state migration check and the existing Rain-panel dry-weather presentation check.

- Rain today is the station's live calendar-day total.
- Rain this week is Monday through today: cached WU daily totals for completed days plus today's live total.
- Event Rain is independent of calendar day/week and survives midnight.
- ACP-derived Event Rain now uses an explicit **2-hour continuously dry inter-event gap** rather than the former Ecowitt-compatible 24-hour / 1 mm reset rule.
- Native provider `hourlyrainin` / `eventrainin` values are never replaced.

### ACP-derived event definition

- **Default:** **2 hours continuously dry**.
- An event starts with the first positive rain increment after the previous event has closed.
- An active event survives midnight and calendar week/month boundaries.
- An event closes when the current rain rate is zero **and** no positive rain increment has occurred for at least the configured dry-gap duration.
- Remove the preceding-24-hours / 1 mm criterion from ACP's derived event reset rule.
- Make the dry-gap duration configurable later in Weather Settings; keep 2 hours as the ACP default unless physical use gives a reason to change it.
- Persist active `event_started_at` / `event_last_rain_at`, the completed event total/start/end/closed timestamps, and the configured dry-gap duration.
- While active, the existing Rain panel now shows **Active rain event** with total and start time.
- After closure, retain a lightweight **Last rain event** summary with start/end and total rather than leaving the user with an unexplained zero.
- Decide separately whether ACP should eventually own a provider-independent Event Rain definition even when a native Ecowitt `eventrainin` is present; do not silently override native provider data during the first WU-derived fix.

This two-hour model deliberately separates the observed example pattern into distinct events: the previous day's isolated shower, the ~03:00 shower, the ~07:00 spell and the ~10:30 heavy burst.

### Midnight rollover defect

**Live bug identified 30 September 2026:** the derived WU event accumulator currently uses dashboard receipt time for the calendar-day rollover. A poll at `2026-09-30T00:00:04` retained a **1.02 mm** increment which was almost certainly the previous day's still-visible WU daily counter; the later genuine new-day counter drop was treated as a reset/correction but the already-added 1.02 mm was never removed.

The derivation now uses the station observation timestamp (`dateutc` converted to local appliance time) as its rainfall chronology, while retaining ACP receipt time separately for diagnostics. Stale/out-of-order station observations cannot move the derived rain counters backwards. Regression coverage includes the observed midnight-lag failure shape, true midnight rollover, two-hour closure, distinct showers after a dry gap, and out-of-order observations.

## #94 live-surface integration

The current multi-document Weather page periodically calls `window.location.reload()` while Weather owns the visible surface. This refreshes the values but also resets the user's scroll position and interaction context.

During #94 Clock ↔ Weather migration:

- [x] replace whole-document reload with a Weather surface controller that obtains a current ACP-local rendered snapshot and refreshes the Weather data grid in place;
- [x] preserve vertical scroll position and Rain/history horizontal scroll across routine updates;
- [x] fetch current state immediately when Weather becomes active after being hidden, so a long-lived document does not show stale values on return;
- [ ] further reduce DOM replacement so individual readings can be patched without rebuilding the whole Weather grid once the reusable component model is established;
- keep the existing server-side WU observation worker authoritative for remote polling; the browser should consume ACP's local current state rather than independently polling Weather Underground;
- [x] keep the forecast availability pill theme-owned: non-stale **Forecast Ready** text follows the selected daytime accent instead of retaining Classic cyan, while stale state remains a semantic warning colour;
- [ ] preserve Weather's full palette while it is the **outgoing** live surface in Spatial-row navigation: forecast rails and active-page-scoped forecast layout now consume the compositor's local Weather surface context rather than reverting to base cyan/geometry when global body state switches to Clock; physical retest pending;
- keep routine Weather data changes separate from navigation motion: no View Transition merely because temperature, rain, pressure or station status changed.

## Weather page revamp — queued after #94 Phase A

The current Weather feature is functionally accepted, but its presentation should eventually be brought up to the standard planned for Astronomy rather than remaining a largely flat detail page.

- [ ] Rebuild Weather as an application surface on the post-#94 single-document/component foundation rather than adding more one-off page CSS.
- [ ] Use a Settings-like section model so current conditions, rain, temperature/humidity, wind, pressure, solar/UV, station status and historical/records views are discoverable without overloading one screen.
- [ ] Keep a concise at-a-glance Weather overview, with deeper touch sections rather than forcing every datum onto the first screen.
- [ ] Add useful graphs rather than decorative charts. Initial candidates: pressure/trend, rainfall rate + accumulation, temperature/humidity, and wind speed/gust/direction.
- [ ] In the Pressure / Barometer panel, use the currently empty space beside the Relative Pressure card for a compact **12/24-hour pressure-history graph** (simple line or bar trace, visually similar to a small instrument history strip). It should complement rather than replace the textual barometer forecast/trend.
- [ ] Extend the bounded pressure-history source beyond the current short window only as needed for that graph; prefer 12 h or 24 h selectable/appropriate retention and coordinate the write/downsampling policy with Appliance Resilience.
- [ ] Investigate a bounded local observation-history store to support graphs and records. Define retention/downsampling, restart/recovery, export and storage-write behaviour before committing to long-term logging.
- [ ] Coordinate any local history design with Appliance Resilience so useful graphs do not create unnecessary SD-card write amplification.
- [ ] Reuse the global ACP design system/tokens and graph components so Astronomy and Weather do not invent two unrelated data-visualisation languages.
- [ ] Preserve offline/stale/source truthfulness and provider ownership while improving the presentation.

## Detailed authorities

- [Weather physical follow-up](../../development/evidence/weather-physical-followup-2026-08-17.md)
- [Live Weather state / derived rain implementation](../../../app/weather_live_state.py)
- [Weather live-state regression tests](../../../tests/test_weather_live_state.py)
- [Weather rainfall-history implementation](../../../app/weather_rainfall_history.py)


## Acceptance for this maintenance branch

- [x] Station-time chronology implemented.
- [x] Midnight stale-total regression fixture added.
- [x] Two-hour inter-event dry gap implemented.
- [x] Active and last-event provenance persisted.
- [x] Existing Weather rain panel projects active/last-event provenance for WU-derived events only.
- [x] Native provider Event Rain ownership preserved.
- [x] Implementation PR CI green at code head `cd967a174ba749d264ef1f1858040ae76104bfa3`.
- [x] Commissioned Pi updated to the code head; ACP restarted cleanly and WU observation status returned `ready`.
- [x] Live v2 state migration checked: `chronology_source=dateutc`, 7200-second dry gap, empty increments, zero active event, no legacy event carried forward, and the WU `dateutc` observation projected to appliance-local chronology correctly.
- [x] Existing Weather Rain panel visually checked on the commissioned touchscreen after the update: the four current rain gauges correctly showed zero and no stale derived event was presented.
- [ ] Real-rain behaviour observed when nature eventually cooperates; useful follow-up evidence only and **not a merge blocker**.

## #94 Clock ↔ Weather physical checkpoint — 4 October 2026

- Same-document Clock → Weather → Clock navigation is materially snappier than the prior full-document route.
- No black flash, page boot or obvious browser reload was observed.
- Active navigation state and footer Mode tracking are correct.
- Clock continues updating normally after returning from Weather.
- Weather forecast, wind direction and Rain controls remain functional.
- Routine Weather refresh now updates data **without moving the page back to the top**, which is physically accepted.
- [x] The former user-facing **Dashboard observation refresh** interval is retired and physically checked absent on the commissioned Pi: observation acquisition keeps its provider-owned cadence, while Clock/Weather presentation refresh is a fixed shell-owned 60-second visible-surface cadence with immediate activation/settings refresh; Clock ↔ Weather remains healthy after the cleanup.
- Two presentation defects were identified for immediate follow-up:
  1. same-document motion used Chromium's default dissolve/crossfade regardless of the configured ACP transition style;
  2. Forecast Outlook strips remained horizontally scrollable but their custom rails were hidden, while the Rain rail remained correct.
- Both defects are bounded to the new same-document presentation lifecycle and are not regressions in Weather data ownership.
