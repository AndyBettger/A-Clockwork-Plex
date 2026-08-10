# Full appliance installer and multi-node weather design

**Status:** Phase 7 design foundation  
**Started:** 10 August 2026  
**Branch:** `feature/alarm-engine`

## Goal

A Clockwork Plex should be installable as a complete Raspberry Pi appliance rather than reconstructed from a remembered sequence of component scripts. The top-level installer is an orchestrator: it owns the sequence, selected capabilities and final verification, while specialist components retain authority for their own subsystem.

This is especially important for repeatable multi-appliance deployment. A second, third or replacement clock should be reproducible from the same installer inputs without copying machine-specific state or teaching a new installer a second version of the audio graph.

## Installer authority

The intended entry point is the repository-root `install.sh`.

The first Phase 7 implementation is deliberately **plan-only**. It accepts the future repeatable choices and reports the intended component graph, but `--apply` is blocked until the component boundaries and rollback rules are implemented and tested.

Initial profile arguments:

```text
--audio direct|eq
--weather-observations ecowitt-push|weather-underground
--non-interactive
```

The top-level installer must not become another implementation of audio routing. For EQ-capable audio it will call the accepted `scripts/audio/*` lifecycle. Direct audio remains a first-class profile and will receive its own supported component boundary rather than making the older `scripts/install-shared-audio.sh` a competing authority.

The current component inventory shows mixed generations of installer style. `install-dashboard-service.sh` and `install-dashboard-kiosk.sh` already use check-first guarded activation, while several older helpers install immediately. Phase 7 should wrap or refactor those components behind one consistent top-level plan/apply contract instead of blindly chaining them together.

## Intended fresh-Pi sequence

```text
A Clockwork Plex installer
  1. prerequisite / hardware / OS checks
  2. application files and Python requirements
  3. dashboard service
  4. Shairport Sync integration and lifecycle hooks
  5. AirPlay metadata listener
  6. alarm-audio and managed helper permissions
  7. selected audio profile
       direct
       or EQ-capable -> accepted scripts/audio lifecycle
  8. selected weather-observation provider
  9. dashboard kiosk startup
 10. appliance-level verification report
```

The exact ordering may be refined as dependencies are made explicit, but each subsystem should have one owner and a verifiable post-condition.

## Weather architecture for several clocks

### Existing split of responsibilities

The current application already separates two weather jobs conceptually:

- **observations** provide the local/current station readings displayed on the Clock and Weather pages;
- **forecast** uses the independent Open-Meteo service and cache.

That separation should be preserved. Changing the observation source must not replace the accepted Open-Meteo forecast service.

### Problem with local Ecowitt custom push

The current `ecowitt_push` path is suitable for the existing clock because the weather station can send its custom local-network upload to that appliance. It does not scale cleanly when the station can target only one local destination.

The multi-appliance solution must **not** introduce a new always-on local weather fan-out/cache server. Each clock should be capable of obtaining current observations independently from a supported upstream provider.

### Supported observation providers

#### `ecowitt_push`

Keep the current provider for installations where the station can push directly to that clock. This remains the default during the migration so existing installations do not change behaviour unexpectedly.

#### `weather_underground`

Add Weather Underground PWS as the first remote-pull provider. The station ID is normal configuration, while the API key is referenced by environment-variable name and should not be written into `config.json` or returned through normal settings/status payloads.

The provider foundation in `app/weather_observations.py` defines:

- configuration normalisation and validation;
- the current-observation endpoint contract;
- the recent-history endpoint contract for later pressure-history work;
- mapping of available Weather Underground current fields into the dashboard's established weather keys.

The initial mapper deliberately requests imperial PWS values because the existing dashboard key contract already distinguishes Fahrenheit, mph and inch-based precipitation. It maps pressure to an explicit `pressurein` key so later wiring can preserve correct inHg-to-hPa conversion instead of treating the value as an unlabeled pressure number.

Remote PWS observations will not necessarily contain every field supplied by an Ecowitt local upload. In particular, indoor readings and Ecowitt-specific sensor/battery fields may be absent. The UI should show unavailable data as unavailable rather than synthesising it.

#### Met Office WOW

Do not add WOW as a new production dependency. The Met Office has announced retirement of the Weather Observations Website during 2026, so building a new multi-appliance observation path around it would create a near-term migration problem. Existing station uploads to WOW may continue while the service remains available, but A Clockwork Plex should not depend on it for its new remote observation mode.

## Pressure history / barometer

The dashboard already maintains its own local pressure history and uses an approximately three-hour comparison for the barometer trend. That mechanism remains useful regardless of provider.

For a Weather Underground clock there are two stages:

1. every successful current-observation poll contributes the current pressure to the existing local history;
2. investigate using Weather Underground PWS recent-history data to seed several hours on startup so the barometer does not need to warm up for roughly three hours after first installation/reboot/cache loss.

The upstream history APIs expose recent rapid and hourly PWS records, but their documented pressure fields are aggregates/ranges/trend values rather than an obviously equivalent instantaneous pressure sample. We should inspect the real station response before choosing a conversion. If the semantics are not strong enough to reconstruct trustworthy historical points, the correct fallback is a temporarily warming-up barometer while local polls accumulate — not invented pressure history.

No shared local cache server is required for either approach; each appliance owns only its small local display/history cache.

## Configuration direction

Example shape:

```json
{
  "weather": {
    "provider": "weather_underground",
    "weather_underground": {
      "station_id": "YOUR_STATION_ID",
      "api_key_env": "WEATHER_UNDERGROUND_API_KEY",
      "refresh_seconds": 60,
      "stale_seconds": 300,
      "request_timeout_seconds": 8,
      "pressure_history_hours": 6
    },
    "forecast": {
      "provider": "open_meteo"
    }
  }
}
```

The real API key belongs in the service environment or a root-managed environment file, not in the example or committed configuration.

## First implementation checkpoint

Source foundation now exists for:

- root `install.sh` read-only appliance plan;
- Direct/EQ-capable installer selection;
- Ecowitt-push/Weather-Underground observation selection;
- non-interactive planning;
- explicit retention of Open-Meteo forecasts;
- Weather Underground configuration validation, URL construction and current-field mapping;
- regression tests for the plan and weather-provider foundation.

No bedroom-Pi audio or weather runtime is changed by this checkpoint. Weather Underground polling is not yet wired into `runner.py`, Settings or the live weather state; `--apply` remains deliberately blocked.

## Next implementation steps

1. define the supported Direct-audio component boundary and prerequisite ownership;
2. make the top-level installer consume component check/plan results without mutation;
3. implement `WeatherObservationService` using the same owned-background-service pattern as `WeatherForecastService`;
4. provide one dashboard storage function used by both Ecowitt push and remote observation service;
5. add provider selection/status to unified Settings without exposing the API key;
6. inspect a real Weather Underground PWS current/history response before accepting pressure-history bootstrap semantics;
7. add non-production integration tests for both weather providers and both audio profiles;
8. only then add guarded top-level installer activation and fresh-Pi physical rehearsal.
