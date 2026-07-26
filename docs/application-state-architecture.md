# Application state architecture

## Purpose

A Clockwork Plex is moving from several browser scripts, shell hooks and source-specific workers toward one interface-facing application state model.

The design separates overall application authority from specialist controllers:

```text
ApplicationStateHub
├── PlaybackCoordinator
├── DspController          (later provider)
├── MixerController        (later provider)
├── WeatherService         (provider stage)
└── SettingsRepository     (provider stage)
```

The browser will eventually request actions and render the resulting state. It will not infer whether a source is playing by inspecting an icon that it drew itself.

## Stage one: observation foundation

The first implementation established the read-only hub.

- `GET /api/state` returns a versioned snapshot.
- `PlaybackCoordinator` observes Plexamp, AirPlay, alarms and the persisted dashboard mode.
- It reports `current_screen` and `recommended_screen` separately.
- Existing Shairport and Plexamp handoff mechanisms remain in control.
- No service, mixer, DSP route or dashboard mode is changed by the hub.

Physical Raspberry Pi validation confirmed that idle, Plexamp, AirPlay, paused-AirPlay and disconnect observations matched the appliance. The systemd service was migrated from `app/main.py` to the real composition entrypoint, `app/runner.py`.

## Stage two: event-assisted observation

Stage two adds a bounded playback event journal while keeping command ownership disabled.

- `GET /api/playback/state` returns a compact playback-only snapshot.
- `GET /api/playback/events` returns recent source transitions.
- `POST /api/playback/events` accepts validated internal adapter events.
- Existing `/api/airplay/start` and `/api/airplay/end` routes are translated into coordinator lifecycle events without changing their established behaviour.
- Fresh Shairport metadata can introduce an AirPlay pause even when MPRIS is stale.
- Once journalled, the pause remains authoritative for the complete hold until a newer resume or disconnect event supersedes it.
- `authority` is `event-assisted-observer` and `commands_enabled` remains `false`.

The shared snapshot carries compact alarm operational status. Full scheduler and alarm-audio histories remain on specialist diagnostic endpoints rather than being returned on every touchscreen state poll.

## Playback state model

The playback snapshot includes:

- active source and decision reason;
- current and recommended screens;
- whether the screen agrees with policy;
- Plexamp observed state;
- AirPlay connection, effective playback state, raw MPRIS evidence and state source;
- compact alarm scheduler and alarm-audio state;
- recent source events;
- handoff policy and the no-restart guarantee.

A paused but connected AirPlay sender remains the active source during the deliberate ten-minute hold.

## Application-state revisions

`ApplicationStateHub` calculates a stable signature from domain state.

- Repeated reads of unchanged state retain the same revision.
- A meaningful domain change increments the revision.
- `generated_at` changes on each response but does not itself increment the revision.
- A failing provider is isolated and reported through `components`; it cannot prevent other domains from being returned.

This failure isolation is important when weather and DSP providers are added. A weather timeout must not break playback state, and a DSP health error must not hide an alarm.

## Temporary AirPlay code

The experimental browser-side AirPlay control coordinator is no longer loaded by the AirPlay page. Its polling and button-repair logic is not part of the new authority model.

The existing `airplay-live.js` renderer and production handoff hooks remain in place until PlaybackCoordinator command ownership has passed physical regression tests.

## Planned migration

1. Validate the event-assisted coordinator during start, pause, long hold, resume, disconnect and Plexamp competition.
2. Feed explicit pause/hold-expiry events from the Shairport adapter.
3. Move the ten-minute AirPlay hold from a detached shell watchdog into coordinator state.
4. Add guarded playback commands while retaining rollback to the existing hooks.
5. Make playback pages render only hub state.
6. Remove obsolete handoff workers, browser inference and shell ownership after regression tests pass.
7. Add `DspController` and `MixerController` providers.
8. Add provider-based `WeatherService` normalisation.

## Safety boundary

Stage two does not promote CamillaDSP or change the physical audio path. The known-good direct shared mixer remains production. Playback commands are still disabled and existing hooks remain responsible for real handoffs while the new state model is verified.
