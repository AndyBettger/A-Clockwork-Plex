# Application state and authority architecture

## Purpose

A Clockwork Plex uses server-side authorities instead of asking browser scripts,
shell hooks and individual pages to negotiate ownership among themselves.

The central rule is:

> Observe broadly, but assign each state transition and command to one owner.

The current composition is built in `app/runner.py`:

```text
Dashboard core and specialist runtimes
  ├── ActiveAlarmScheduler
  ├── ScheduledAlarmAudioManager
  ├── shared audio mixer
  ├── Open-Meteo forecast cache
  └── source observers

ApplicationStateHub
  ├── final PlaybackCoordinator authority
  ├── MixerController
  ├── ScreenProjectionController
  ├── LinuxInputActivityMonitor
  └── compact specialist providers

Configuration authorities
  ├── UnifiedSettingsService
  ├── MasterEqualizer
  └── ShairportNameManager

Browser clients
  ├── stage configuration through one revisioned transaction
  ├── request explicit runtime actions
  └── render server state
```

The known-good direct shared ALSA mixer remains the production audio graph. The
old bare master-EQ installer remains blocked. EQ configuration in the new
Settings screen uses the existing master-EQ authority and is awaiting focused
physical validation.

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
weather_forecast = WeatherForecastService(...)
shairport_name = ShairportNameManager()
unified_settings = UnifiedSettingsService(...)
register_unified_settings_api(app, unified_settings)
```

Scheduled alarm audio and its public status projection are registered before the
state hub. The final playback authority therefore observes the real promoted
alarm policy rather than the scheduler foundation's internal no-player flag.

The unified Settings service is registered after its specialist owners so it can
validate and commit configuration without duplicating their runtime logic.

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
- rapid iPhone resume detection from Shairport metadata;
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

### AirPlay is resumed quickly from the iPhone

1. Shairport's metadata FIFO emits its play-resume evidence.
2. The final coordinator recognises that event as newer user intent.
3. Plexamp is paused.
4. AirPlay becomes the active source and recommended screen.
5. A stale MPRIS `Playing` label alone cannot trigger the reverse handoff.

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

The saved idle destination is restored into the screen authority when the
service starts. Startup, idle, Clock format and transition preferences are
server-authoritative before first paint; browser storage is only a temporary
compatibility mirror for older Clock renderers.

## Unified Settings authority

`UnifiedSettingsService` owns staged appliance configuration through:

```text
GET  /api/settings
POST /api/settings
```

A snapshot includes:

- one revision derived from the normalised public configuration;
- all editable configuration domains;
- capability flags;
- compact Shairport, EQ and forecast health.

A save:

1. rejects a stale revision;
2. validates every submitted domain;
3. asks specialist normalisers to validate alarms, alarm audio and forecasts;
4. requires explicit confirmation before restarting Shairport Sync;
5. applies the receiver name and EQ through their owners;
6. writes `config.json` once;
7. rolls back applied system values if the write fails;
8. wakes or refreshes the scheduler, forecast and screen owners;
9. returns a fully normalised new snapshot.

The browser keeps one sticky Save/Discard bar and dirty indicators per category.
A separate transaction guard blocks pointer, keyboard and form resubmission while
a confirmed save is active.

### Configuration versus actions

Configuration uses the transaction. Runtime actions remain explicit specialist
commands:

- live or persistent mixer movement;
- alarm tests and stop;
- forecast refresh-now;
- scheduler recalculation;
- diagnostic refreshes.

Those actions do not make the Settings transaction dirty.

## Managed Shairport receiver name

`ShairportNameManager` is an unprivileged client for the fixed root-owned helper:

```text
/usr/local/bin/a-clockwork-plex-shairport-name
```

The helper may only:

- read the fixed `/etc/shairport-sync.conf`;
- change `general.name`;
- validate a candidate configuration;
- replace the file atomically;
- restart and verify `shairport-sync.service`;
- restore the original configuration on failure.

It exposes only `status` and `set <validated name>` through a restricted sudoers
policy. The Flask process receives no general root privileges.

## Equaliser authority

The unified Settings transaction uses `MasterEqualizer` for:

- enabled/bypass state;
- Bass;
- Mid;
- Treble;
- persistent band values;
- backend health.

EQ settings remain visible even when the backend is unavailable, but a changed EQ
model cannot be committed until that authority reports ready. Applied EQ values
are rolled back if the overall Settings transaction fails.

The old bare production installer remains blocked and is not called by Settings.

## Browser boundary

Browser clients are presentation and explicit-input adapters.

They may:

- stage a normalised configuration model;
- request one revisioned Settings transaction;
- request a transport or navigation action;
- report genuine local input activity;
- acknowledge the surface that was actually shown;
- render coordinator and specialist state.

They must not:

- restart services directly;
- edit system configuration directly;
- infer transport truth from an icon they drew;
- independently arbitrate Plexamp versus AirPlay;
- create or extend an AirPlay hold timer;
- manufacture repeated activity;
- decide that alarm audio may play.

The active Settings page no longer loads the old horizontal-tab, autosave,
alarm-workspace or scheduled-audio injector clients.

## Runtime persistence

Small atomic JSON stores preserve deadlines and recovery state:

- alarm scheduler/runtime state;
- alarm audio runtime diagnostics;
- playback hold/ceded state;
- cached online forecast;
- dashboard/application state where appropriate.

Writes use a temporary file followed by replacement so an interrupted write does
not leave a partially written runtime document.

## Current physical validation

The bedroom Raspberry Pi has validated:

- AirPlay pause hold and restart retention;
- bidirectional Plexamp/AirPlay takeover;
- rapid iPhone AirPlay resume;
- navigation and transport state rendering;
- manual screen leases and playback interruption rules;
- real scheduled alarm audio;
- Snooze and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- no automatic music resume after alarm release;
- alarm configuration persistence and keyboard-safe editing;
- Ecowitt observations and cached Open-Meteo forecast presentation.

The unified iPad Settings screen, managed Shairport name helper and Settings EQ
controls are covered by CI and await focused physical validation.

## Remaining work

1. validate the iPad split-view Settings layout, staging, Discard and touch
   keyboard at 1024×600;
2. install and validate the restricted Shairport receiver-name helper;
3. validate Settings-hosted EQ controls against the proven backend without using
   the old bare installer;
4. make small layout, wording or compatibility corrections found during that
   pass;
5. refresh release documentation and run one focused appliance smoke test;
6. obtain explicit approval before making PR #2 ready or merging it.

PR #2 remains draft and must not be merged without explicit approval.
