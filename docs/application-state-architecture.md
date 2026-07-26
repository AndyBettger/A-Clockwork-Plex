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

Stage two added a bounded playback event journal while keeping command ownership disabled.

- `GET /api/playback/state` returns a compact playback-only snapshot.
- `GET /api/playback/events` returns recent source transitions.
- `POST /api/playback/events` accepts validated internal adapter events.
- Existing `/api/airplay/start` and `/api/airplay/end` routes are translated into coordinator lifecycle events without changing their established behaviour.
- Fresh Shairport metadata can introduce an AirPlay pause even when MPRIS is stale.
- Once journalled, the pause remains authoritative until a newer resume or disconnect event supersedes it.

Physical validation confirmed the expected idle, Plexamp, AirPlay, pause, long-pause, resume and disconnect states. The shared snapshot carries compact alarm operational status; full alarm histories remain on specialist endpoints.

## Stage three: coordinator-owned AirPlay hold

Stage three transfers the ten-minute pause hold from a detached shell watchdog into `PlaybackCoordinator`.

- Shairport START remains a thin adapter that pauses Plexamp and publishes the established AirPlay start route.
- Shairport END classifies the transition as paused, disconnected or a stale END after resume.
- A paused sender posts `airplay.paused` to `/api/playback/events`.
- The coordinator persists the hold deadline in `playback-runtime.json`.
- A dashboard restart reloads the existing deadline instead of restarting the ten-minute period.
- A background coordinator worker monitors disconnect and deadline expiry without depending on the browser.
- Resume/start events cancel the hold immediately.
- Disconnect ends the held session immediately.
- Expiry marks the AirPlay session ended and returns the dashboard to its configured idle destination.
- The shell wrappers contain no generation token, detached watchdog, repeated sleep loop or browser heartbeat.

The authority boundary remains deliberately narrow:

```text
source transport control        disabled
screen/session return on expiry enabled
Plexamp/Shairport restarts      never used
mixer or DSP changes            none
```

The playback snapshot reports:

- `authority: airplay-hold-owner`;
- `commands_enabled: false`;
- `command_capabilities.source_control: false`;
- `command_capabilities.screen_return_on_hold_end: true`;
- coordinator worker health;
- hold owner, phase, deadline, remaining seconds and any completion error.

## Playback state model

The playback snapshot includes:

- active source and decision reason;
- current and recommended screens;
- whether the screen agrees with policy;
- Plexamp observed state;
- AirPlay connection, effective playback state, raw MPRIS evidence and state source;
- persisted AirPlay hold state;
- compact alarm scheduler and alarm-audio state;
- recent source events;
- handoff policy and the no-restart guarantee.

A paused but connected AirPlay sender remains the active source until resume, disconnect or hold expiry.

## Application-state revisions

`ApplicationStateHub` calculates a stable signature from domain state.

- Repeated reads of unchanged state retain the same revision.
- A meaningful domain change increments the revision.
- `generated_at` changes on each response but does not itself increment the revision.
- A failing provider is isolated and reported through `components`; it cannot prevent other domains from being returned.

This failure isolation is important when weather and DSP providers are added. A weather timeout must not break playback state, and a DSP health error must not hide an alarm.

## Temporary AirPlay code

The experimental browser-side AirPlay control coordinator is no longer loaded. Its polling and button-repair logic is not part of the new authority model.

The existing `airplay-live.js` renderer remains temporarily, so the visible Play/Pause icon may still disagree with the coordinator. The next interface stage will render playback controls directly from `/api/playback/state`.

## Planned migration

1. Physically validate coordinator hold ownership, restart recovery, resume cancellation, disconnect handling and full expiry.
2. Add guarded source arbitration commands while retaining rollback to the established handoff paths.
3. Make AirPlay and Plexamp pages render only hub state.
4. Remove obsolete mode watchers, browser inference and legacy source handoff workers after regression tests pass.
5. Add `DspController` and `MixerController` providers.
6. Add provider-based `WeatherService` normalisation.

## Safety boundary

Stage three does not promote CamillaDSP or change the physical audio path. The known-good direct shared mixer remains production. The coordinator owns only AirPlay lifecycle timing and the resulting screen/session return; source transport arbitration still uses the established production mechanisms.
