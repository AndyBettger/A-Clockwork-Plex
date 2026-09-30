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

Maintenance candidate: persist explicit `event_started_at` / last-reset diagnostics so a multi-day Event Rain total can explain its calendar provenance after the rolling 24-hour increment list has aged away. Do not change the accepted reset semantics merely to make totals look more intuitive.

## Detailed authorities

- `../../development/evidence/weather-physical-followup-2026-08-17.md`
- weather implementation/tests under `app/weather_*.py` and `tests/test_weather_*.py`
