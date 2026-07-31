# Application state and authority architecture

## Purpose

A Clockwork Plex now uses server-side application authorities instead of asking
browser scripts, shell hooks and individual pages to negotiate ownership among
themselves.

The central rule is:

> Observe broadly, but assign each state transition and command to one owner.

The current composition is built in `app/runner.py`:

```text
Dashboard core and specialist runtimes
  ├── ActiveAlarmScheduler
  ├── ScheduledAlarmAudioManager
  ├── shared audio mixer
  └── source observers

ApplicationStateHub
  ├── final PlaybackCoordinator authority
  ├── MixerController
  ├── ScreenProjectionController
  ├── LinuxInputActivityMonitor
  └── compact specialist providers

Browser clients
  ├── request explicit actions
  └── render server state
```

The known-good direct shared ALSA mixer remains the production audio graph.
Production master-EQ integration is still blocked and is not part of this
architecture promotion.

## Composition order

Order matters because later authorities consume promoted specialist truth:

```python
scheduled_alarm_audio = promote_scheduled_alarm_audio(dashboard)
register_scheduled_alarm_status_api(dashboard)
application_state_hub = build_default_application_state_hub(dashboard)
playback_coordinator = promote_playback_authority(application_state_hub, dashboard)
screen_projection = register_activity_screen_projection(...)
register_application_state_api(...)
register_playback_command_api(...)
master_equalizer = register_audio_eq(app)
```

Scheduled alarm audio and its public status projection are registered before the
state hub. The final playback authority therefore observes the real promoted alarm
policy rather than the scheduler foundation's internal no-player flag.

## ApplicationStateHub

`ApplicationStateHub` provides a versioned, failure-isolated snapshot.

Main endpoints:

```text
GET  /api/state
GET  /api/playback/state
GET  /api/playback/events
POST /api/playback/events
POST /api/playback/command
```

Important properties:

- repeated reads of unchanged domain state retain the same revision;
- `generated_at` changes on each response without incrementing the revision;
- one failing provider is reported under `components` and cannot suppress other
  domains;
- full specialist histories remain on specialist endpoints;
- the playback snapshot contains compact evidence, policy and command history.

## Final playback authority

The production playback service is a
`RetainedBidirectionalHandoffCoordinator`, promoted exactly once by
`playback_authority.py`.

It owns:

- explicit AirPlay transport commands;
- previous/next navigation when the sender supports them;
- the persisted ten-minute AirPlay pause hold;
- AirPlay-to-Plexamp takeover;
- Plexamp-to-AirPlay takeover;
- retained ceded AirPlay sessions;
- alarm audio priority over both music sources;
- command diagnostics and independent-observation confirmation.

It never restarts Plexamp or Shairport Sync and does not edit the ALSA graph.

### Source priority

The effective priority is:

```text
real sounding alarm
  > newest deliberate music playback transition
  > retained/held AirPlay session
  > idle policy
```

Screen ownership is separate from audio ownership. A manual Settings or Clock
lease can remain visible while background music continues, but a ringing alarm
always interrupts the lease.

## AirPlay lifecycle and pause hold

A paused but connected AirPlay sender remains retained for the configured hold
period, normally 600 seconds.

The coordinator persists:

- hold start;
- hold deadline;
- phase;
- reason;
- last error.

A dashboard restart reloads the original deadline instead of restarting it.
Fresh resume cancels the hold. Sender disconnect ends it immediately. Expiry
releases the session without manufacturing a source transport command.

## Bidirectional music handoff

### AirPlay starts while Plexamp is playing

1. Shairport publishes the AirPlay lifecycle event.
2. The final coordinator observes a fresh playing episode.
3. Plexamp receives one Pause command.
4. Repeated observations do not issue repeated commands.
5. The Plexamp service remains running.

### Plexamp starts while AirPlay is playing

1. The coordinator detects a genuine paused/stopped-to-playing Plexamp transition.
2. AirPlay receives one Pause command.
3. The sender session is retained in a ceded state for the existing or newly
   created hold deadline.
4. A later independent AirPlay paused observation confirms the command.
5. Browsing the Plexamp surface without starting playback does not pause AirPlay.

## Alarm authority

Alarm responsibility is deliberately divided:

```text
ActiveAlarmScheduler
  clock, recurrence, DST, recovery, occurrence queue, Snooze, Dismiss

ScheduledAlarmAudioManager
  local tone rendering through acp_alarm

PlaybackCoordinator
  pause Plexamp/AirPlay and hold alarm audio priority

ScreenProjectionController
  immediate Alarm surface
```

A real sounding scheduled alarm is recognised only when:

- an active non-test occurrence is in the `ringing` phase; and
- `scheduled_playback_enabled` is true.

The coordinator pauses each playing source once. If a source is restarted during
the same alarm, it is paused again. Releasing alarm priority never automatically
resumes music; the resume policy is explicitly `manual`.

Alarm takeover diagnostics live at:

```text
/api/playback/state → handoffs.alarm_takeover
```

## Public alarm status projection

The scheduler runtime intentionally contains no audio player. Its internal
`playback_enabled` field remains false as an implementation boundary.

`alarm_audio_status_scheduled.py` projects the promoted audio manager's policy
onto public scheduler payloads. Therefore these fields must agree:

```text
/api/alarms/audio.scheduled_playback_enabled
/api/alarms/scheduler.playback_enabled
/api/alarms/scheduler.scheduler.playback_enabled
/api/alarms/active.playback_enabled
/api/alarms/active.scheduler.playback_enabled
```

The nested public scheduler object also identifies:

```text
playback_owner:  scheduled-alarm-audio-manager
playback_policy: two-key-safety-gate
```

When sound is locked, `playback_lockout_reason` identifies the actual disabled
safety key rather than exposing an obsolete development-stage message.

## Mixer authority

`MixerController` owns the compact live and trim APIs.

- Plexamp live volume uses Plexamp's player endpoint.
- AirPlay live volume uses the sender adapter and confirmation model.
- Master and Alarm live controls write their ALSA stages without persisting.
- Persistent trims use the restricted mixer helper and explicit persistence.
- Latest-value-wins queues prevent stale sender responses from overwriting newer
  requests.

Browser faders display controller state; they do not invent confirmed volume.

## Screen projection authority

`ScreenProjectionController` owns the recommended visible surface.

It considers:

- current playback source and generation;
- manual navigation leases;
- configured startup and idle destinations;
- Linux touchscreen/input activity;
- alarm priority;
- current visible browser surface.

Important rules:

- Alarm interrupts every manual lease immediately.
- A new playback generation may interrupt a background/manual page.
- Ordinary track progression within the same Plexamp queue does not.
- Settings and other manual pages remain visible until their inactivity lease
  expires unless a higher-priority event occurs.
- The browser acknowledges manual navigation before performing the transition,
  preventing an in-flight projection response from undoing the user's action.

## Browser boundary

Browser clients are presentation and explicit-input adapters.

They may:

- request a transport or navigation action;
- report genuine local input activity;
- acknowledge the surface that was actually shown;
- render coordinator and specialist state.

They must not:

- restart audio services;
- infer transport truth from an icon they drew;
- independently arbitrate Plexamp versus AirPlay;
- create or extend an AirPlay hold timer;
- manufacture repeated activity;
- decide that alarm audio may play.

The old browser-side AirPlay control coordinator, legacy idle-return client and
staged server promotion wrappers are no longer loaded.

## Runtime persistence

Small atomic JSON stores preserve deadlines and recovery state:

- alarm scheduler/runtime state;
- alarm audio runtime diagnostics;
- playback hold/ceded state;
- dashboard/application state where appropriate.

Writes use a temporary file followed by replacement so an interrupted write does
not leave a partially written runtime document.

## Current physical validation

The bedroom Raspberry Pi has validated:

- AirPlay pause hold and restart retention;
- bidirectional Plexamp/AirPlay takeover;
- navigation and transport state rendering;
- manual screen leases and playback interruption rules;
- real scheduled alarm audio;
- Snooze and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- no automatic music resume after alarm release;
- dedicated alarm configuration persistence;
- keyboard-safe alarm save UI.

## Remaining work

The current cleanup/release stage includes:

1. remove stale diagnostics and documentation from earlier promotion stages;
2. continue regression checks across alarm, Plexamp, AirPlay, navigation and
   service restart boundaries;
3. keep production EQ integration blocked until a separately approved path meets
   its laboratory and rollback criteria;
4. complete final weather-provider work last;
5. update release documentation and obtain explicit approval before merging PR #2.

PR #2 remains draft and must not be merged without explicit approval.
