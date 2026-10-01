# Weather

**Status:** COMPLETE through #87; focused maintenance + post-#94 presentation revamp queued  
**Primary implementation:** #86 Friendly forecast-location entry, #87 WU supplemental indoor expiry

## Accepted scope

- Friendly town/city/postcode forecast-location entry with manual coordinate fallback.
- Weather Underground and Ecowitt observation ownership as documented by the current Weather architecture.
- Historical rainfall/cache-backed current and previous calendar periods.
- Supplemental indoor readings expire when stale rather than remaining indefinitely.
- Touch-first Weather presentation, forecast and rainfall views physically accepted.

## Current maintenance — rainfall event semantics

The live WU path derives Hourly Rain and Event Rain when the provider does not supply native values.

### Current implementation

- Rain today is the station's live calendar-day total.
- Rain this week is Monday through today: cached WU daily totals for completed days plus today's live total.
- Event Rain is independent of calendar day/week and survives midnight.
- The current derived event follows Ecowitt-compatible semantics: it resets only when the current rain rate is zero, the trailing hour is dry, and the rolling preceding 24 hours contain **less than 1 mm** of rain.
- Native provider `hourlyrainin` / `eventrainin` values are never replaced.

That Ecowitt-style rule is too sticky for ACP's intended UK use: several distinct showers separated by clear multi-hour dry periods can remain one event merely because more than 1 mm fell somewhere in the preceding 24 hours.

### Proposed ACP-derived event definition

Use an explicit **inter-event dry period** rather than the 24-hour threshold.

- **Recommended default:** **2 hours continuously dry**.
- An event starts with the first positive rain increment after the previous event has closed.
- An active event survives midnight and calendar week/month boundaries.
- An event closes when the current rain rate is zero **and** no positive rain increment has occurred for at least the configured dry-gap duration.
- Remove the preceding-24-hours / 1 mm criterion from ACP's derived event reset rule.
- Make the dry-gap duration configurable later in Weather Settings; keep 2 hours as the ACP default unless physical use gives a reason to change it.
- Persist `event_started_at`, `event_last_rain_at`, `event_closed_at`/last-reset diagnostics and the completed event total.
- While active, show e.g. **Event rain — 8.1 mm · Since 22:39**.
- After closure, retain a lightweight **Last rain event** summary with start/end and total rather than leaving the user with an unexplained zero.
- Decide separately whether ACP should eventually own a provider-independent Event Rain definition even when a native Ecowitt `eventrainin` is present; do not silently override native provider data during the first WU-derived fix.

This two-hour model deliberately separates the 30 September/1 October observed pattern into distinct events: yesterday's isolated shower, the ~03:00 shower, the ~07:00 spell and the ~10:30 heavy burst.

### Midnight rollover defect

**Live bug identified 30 September 2026:** the derived WU event accumulator currently uses dashboard receipt time for the calendar-day rollover. A poll at `2026-09-30T00:00:04` retained a **1.02 mm** increment which was almost certainly the previous day's still-visible WU daily counter; the later genuine new-day counter drop was treated as a reset/correction but the already-added 1.02 mm was never removed.

Fix the derivation to use the station observation timestamp (`dateutc` converted to local appliance time) as its rainfall chronology and add a guarded midnight-lag regression fixture. Event start/last-rain timestamps must use that same station chronology.

## Weather page revamp — queued after #94 Phase A

The current Weather feature is functionally accepted, but its presentation should eventually be brought up to the standard planned for Astronomy rather than remaining a largely flat detail page.

- [ ] Rebuild Weather as an application surface on the post-#94 single-document/component foundation rather than adding more one-off page CSS.
- [ ] Use a Settings-like section model so current conditions, rain, temperature/humidity, wind, pressure, solar/UV, station status and historical/records views are discoverable without overloading one screen.
- [ ] Keep a concise at-a-glance Weather overview, with deeper touch sections rather than forcing every datum onto the first screen.
- [ ] Add useful graphs rather than decorative charts. Initial candidates: pressure/trend, rainfall rate + accumulation, temperature/humidity, and wind speed/gust/direction.
- [ ] Investigate a bounded local observation-history store to support graphs and records. Define retention/downsampling, restart/recovery, export and storage-write behaviour before committing to long-term logging.
- [ ] Coordinate any local history design with Appliance Resilience so useful graphs do not create unnecessary SD-card write amplification.
- [ ] Reuse the global ACP design system/tokens and graph components so Astronomy and Weather do not invent two unrelated data-visualisation languages.
- [ ] Preserve offline/stale/source truthfulness and provider ownership while improving the presentation.

## Detailed authorities

- [Weather physical follow-up](../../development/evidence/weather-physical-followup-2026-08-17.md)
- [Live Weather state / derived rain implementation](../../../app/weather_live_state.py)
- [Weather live-state regression tests](../../../tests/test_weather_live_state.py)
- [Weather rainfall-history implementation](../../../app/weather_rainfall_history.py)



- `../../development/evidence/weather-physical-followup-2026-08-17.md`
- weather implementation/tests under `app/weather_*.py` and `tests/test_weather_*.py`
