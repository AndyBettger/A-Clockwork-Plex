# Application state architecture

## Purpose

A Clockwork Plex is moving from several browser scripts, shell hooks and source-specific workers toward one interface-facing application state model.

The design separates overall application authority from specialist controllers:

```text
ApplicationStateHub
├── PlaybackCoordinator
├── DspController          (next stage)
├── MixerController        (next stage)
├── WeatherService         (provider stage)
└── SettingsRepository     (provider stage)
```

The browser will eventually request actions and render the resulting state. It will not infer whether a source is playing by inspecting an icon that it drew itself.

## Stage one: observation only

The first implementation is intentionally read-only.

- `GET /api/state` returns a versioned snapshot.
- `PlaybackCoordinator` observes Plexamp, AirPlay, alarms and the persisted dashboard mode.
- It reports `current_screen` and `recommended_screen` separately.
- `commands_enabled` remains `false`.
- Existing Shairport and Plexamp handoff mechanisms remain in control.
- No service, mixer, DSP route or dashboard mode is changed by the hub.

This lets physical testing compare the coordinator's view with actual behaviour before control authority is transferred.

## Playback state model

The playback snapshot includes:

- active source;
- current and recommended screens;
- whether the screen agrees with policy;
- Plexamp observed state;
- AirPlay connection, playback and metadata state;
- alarm scheduler and alarm-audio state;
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

The existing `airplay-live.js` renderer and production handoff hooks remain in place until the PlaybackCoordinator is promoted from observer to command owner.

## Planned migration

1. Validate `/api/state` on the physical Pi during Plexamp, AirPlay, paused-AirPlay hold and alarm-screen states.
2. Record disagreements between current and recommended screen without acting on them.
3. Add event ingestion and explicit command handling to `PlaybackCoordinator`.
4. Move the ten-minute AirPlay hold from a detached shell watchdog into coordinator state.
5. Make playback pages render only hub state.
6. Add `DspController` and `MixerController` providers.
7. Add provider-based `WeatherService` normalisation.
8. Remove obsolete mode watchers, browser inference and shell ownership after regression tests pass.

## Safety boundary

Stage one does not promote CamillaDSP or change the physical audio path. The known-good direct shared mixer remains production while the control architecture is built and verified.
