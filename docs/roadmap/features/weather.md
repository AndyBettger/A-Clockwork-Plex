# Weather

**Status:** COMPLETE through #87; maintenance only  
**Primary implementation:** #86 Friendly forecast-location entry, #87 WU supplemental indoor expiry

## Accepted scope

- Friendly town/city/postcode forecast-location entry with manual coordinate fallback.
- Weather Underground and Ecowitt observation ownership as documented by the current Weather architecture.
- Historical rainfall/cache-backed current and previous calendar periods.
- Supplemental indoor readings expire when stale rather than remaining indefinitely.
- Touch-first Weather presentation, forecast and rainfall views physically accepted.

## Current maintenance note — rainfall semantics

The live WU path derives Hourly Rain and Event Rain when the provider does not supply native values.

- Rain today is the station's live calendar-day total.
- Rain this week is Monday through today: cached WU daily totals for completed days plus today's live total.
- Event Rain is independent of calendar day/week and survives midnight.
- The derived event resets only when the current rain rate is zero, the trailing hour is dry, and the rolling preceding 24 hours contain **less than 1 mm** of rain.
- Native provider `hourlyrainin` / `eventrainin` values are never replaced.

A live 30 September 2026 storm exposed a useful sanity-check case: Event Rain may legitimately exceed Rain Today, and can exceed Rain This Week only when the event began before the current Monday and has not yet met the reset rule. Inspect persisted event state when that relationship is unexpected.

Maintenance candidate: persist explicit `event_started_at`, `event_last_rain_at` and last-reset diagnostics so a multi-day Event Rain total can explain its calendar provenance after the rolling 24-hour increment list has aged away. Surface the start date/time alongside Event Rain in the Weather UI.

**Live bug identified 30 September 2026:** the derived WU event accumulator currently uses dashboard receipt time for the calendar-day rollover. A poll at `2026-09-30T00:00:04` retained a **1.02 mm** increment which was almost certainly the previous day's still-visible WU daily counter; the later genuine new-day counter drop was treated as a reset/correction but the already-added 1.02 mm was never removed. This explains Event Rain being about 1.0 mm higher than both the retained post-midnight increments and the calendar-week history. Fix the derivation to use the station observation timestamp (`dateutc` converted to local time) as its rainfall chronology, add a guarded rollover regression fixture, and preserve the accepted event reset rule rather than papering over the discrepancy in presentation.

## Detailed authorities

- `../../development/evidence/weather-physical-followup-2026-08-17.md`
- weather implementation/tests under `app/weather_*.py` and `tests/test_weather_*.py`
