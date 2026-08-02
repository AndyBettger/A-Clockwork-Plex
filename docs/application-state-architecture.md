# Application state and authority architecture

## Purpose

A Clockwork Plex uses explicit authorities instead of asking browser scripts,
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
  ├── RetainedBidirectionalHandoffCoordinator
  ├── MixerController
  ├── ScreenProjectionController
  ├── LinuxInputActivityMonitor
  └── compact specialist providers

Configuration authorities
  ├── UnifiedSettingsService
  ├── MasterEqualizer
  └── ShairportNameManager

Presentation authorities
  ├── ACPTime
  └── ACPDisplayDimming

Browser clients
  ├── autosave configuration through one revisioned transaction
  ├── request explicit runtime actions
  └── render server state
```

The known-good direct shared ALSA mixer remains the production audio graph. The
old bare master-EQ installer remains blocked. Production EQ is the next separate
guarded rollout around that validated graph.

## Composition order

Order matters because later authorities consume promoted specialist truth:

```python
app = dashboard.app
promote_server_time_formatting(dashboard)
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
state hub. The final playback authority therefore observes the promoted alarm
policy rather than the timing scheduler's internal no-player flag.

The unified Settings service is registered after specialist owners so it can
validate and commit configuration without duplicating their runtime logic.

## ApplicationStateHub

`ApplicationStateHub` provides a versioned, failure-isolated snapshot.

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
- previous/next navigation when supported;
- the persisted AirPlay pause hold;
- AirPlay-to-Plexamp and Plexamp-to-AirPlay takeover;
- retained ceded AirPlay sessions;
- rapid iPhone resume detection from Shairport metadata;
- alarm priority over both music sources;
- command diagnostics and independent-observation confirmation.

It never restarts Plexamp or Shairport Sync and does not edit the ALSA graph.

### Source priority

```text
real sounding alarm
  > newest deliberate music playback transition
  > retained/held AirPlay session
  > idle policy
```

Screen ownership is separate from audio ownership. A manual Settings or Clock
lease can remain visible while background music continues, but a ringing alarm
always interrupts the lease.

## AirPlay lifecycle and bidirectional handoff

A paused but connected AirPlay sender remains retained for the configured hold
period. The coordinator persists the hold start, deadline, phase, reason and last
error, so a dashboard restart reloads the original deadline.

When AirPlay starts while Plexamp is playing, Plexamp receives one Pause command.
When genuine Plexamp playback starts while AirPlay owns audio, AirPlay receives
one Pause command and the sender remains retained until its existing deadline.
Fresh iPhone resume evidence from the Shairport metadata FIFO becomes newer user
intent and pauses Plexamp again. Browsing either surface does not manufacture a
handoff.

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

A real sounding scheduled alarm is recognised only when an active non-test
occurrence is ringing and `scheduled_playback_enabled` is true. Releasing alarm
priority never automatically resumes music; the resume policy is explicitly
`manual`.

The scheduler intentionally contains no audio player. Its internal
`playback_enabled` field remains false as an ownership boundary. Public alarm
payloads are projected from the promoted audio manager and identify:

```text
playback_owner:  scheduled-alarm-audio-manager
playback_policy: two-key-safety-gate
```

Logs and diagnostics therefore describe audio as **delegated**, not disabled.

## Mixer authority

`MixerController` owns compact live and trim APIs.

- Plexamp live volume uses Plexamp's player endpoint.
- AirPlay live volume uses the sender adapter and confirmation model.
- Master and Alarm live controls write ALSA without persistence.
- Persistent trims use the restricted mixer helper.
- Latest-value-wins queues prevent stale sender responses overwriting newer
  requests.

Browser faders display controller state; they do not invent confirmed volume.

## Screen projection authority

`ScreenProjectionController` owns the recommended visible surface. It considers
current playback source/generation, manual navigation leases, configured startup
and idle destinations, Linux touchscreen activity, alarm priority and the actual
visible browser surface.

Important rules:

- Alarm interrupts every manual lease immediately.
- A new playback generation may interrupt a background/manual page.
- Ordinary track progression within the same Plexamp queue does not.
- Manual pages remain visible until their inactivity lease expires unless a
  higher-priority event occurs.
- The browser acknowledges manual navigation before performing a transition so
  stale projection responses cannot undo the user's action.

The guarded kiosk launcher waits for `/api/state`, uses an isolated Chromium
profile and opens the dashboard rather than Plexamp directly. A real reboot has
physically validated startup into the Clock.

## Unified Settings authority

`UnifiedSettingsService` owns appliance configuration through:

```text
GET  /api/settings
POST /api/settings
```

A snapshot includes one revision, all editable domains, capabilities and compact
Shairport, EQ and forecast health.

An autosave transaction:

1. rejects a stale revision;
2. validates every submitted domain;
3. uses specialist normalisers for alarms, alarm audio, forecasts and display
   dimming;
4. requires confirmation before restarting Shairport Sync;
5. applies receiver name and EQ through their owners;
6. writes `config.json` once;
7. rolls back applied system values if the write fails;
8. wakes or refreshes scheduler, forecast and screen owners;
9. returns a fully normalised snapshot.

The browser has one autosave owner. Dirty indicators identify the affected
category, subpage and field. The obsolete sticky Save bar was hidden after
physical testing showed it obscured controls and the touch keyboard.

Runtime actions remain separate and immediate: mixer movement, alarm tests and
stop, forecast refresh-now, scheduler recalculation and diagnostic refreshes.

## Display presentation authorities

### ACPTime

`ACPTime` is the dashboard-wide 12/24-hour client authority. It formats the Clock,
AirPlay mini clock, Alarm current-time display, Weather/forecast times, Advanced
diagnostics and marked status timestamps. The server's existing timestamp hook
is promoted to the same setting so server-rendered values agree.

Alarm configuration remains stored as 24-hour `HH:MM`; this is data entry rather
than a presentation clock.

### ACPDisplayDimming

`ACPDisplayDimming` owns scheduled visual dimming. Its model includes enablement,
start/end times, visual brightness, touch-to-wake duration, optional dark Clock
mode and burn-in shifting.

It is deliberately browser-only:

- no root privileges;
- no `xrandr` or backlight driver calls;
- no system service changes;
- no audio-graph changes.

The first interaction while dimmed is consumed to wake the display without
activating the underlying control. The Alarm page always bypasses dimming. The
overlay clears automatically outside the schedule.

## Weather authority

Ecowitt remains authoritative for live observations. `WeatherForecastService`
owns Open-Meteo access, normalisation, caching, stale fallback and provider
health.

Open-Meteo supports up to 16 configured days. The Weather foundation renderer
retains the first established seven cards, while a completion renderer appends
all remaining daily objects returned by the local cache endpoint. The browser
never calls Open-Meteo directly.

## Managed Shairport receiver name

`ShairportNameManager` is an unprivileged client for the fixed root-owned helper:

```text
/usr/local/bin/a-clockwork-plex-shairport-name
```

The helper may only read the fixed configuration, change `general.name`, validate
a candidate on an isolated identity/port, replace atomically, restart and verify
Shairport Sync, and restore the original configuration on failure.

The Flask process receives no general root privileges. Rename, iPhone discovery,
connection, screen takeover and audio have all been physically validated.

## Audio diagnostics boundary

Everyday Audio contains real controls or configuration. Advanced Audio is
read-only diagnostics plus deliberate finite tests.

The stale shared-mixer checkbox, Physical DAC text field and Alarm PCM form field
are removed from Advanced. The configured route and mixer health remain visible,
but changing the production output route requires a guarded maintenance
procedure with exact-state backup and rollback.

Advanced diagnostics poll only while visible and at a slower passive cadence to
reduce journal noise.

## Equaliser authority

The unified Settings transaction uses `MasterEqualizer` for enabled/bypass, Bass,
Mid, Treble, persistent values and health. The Settings controls remain visible
while the backend is unavailable, but changed EQ values cannot be committed until
the production authority reports ready.

The old bare production installer remains blocked. The guarded CamillaDSP rollout
must preserve the shared mixer, capture exact state and provide automatic
rollback.

## Browser boundary

Browser clients may autosave a normalised configuration model, request explicit
actions, report genuine input activity, acknowledge the displayed surface and
render server state.

They must not restart services directly, edit system configuration directly,
infer transport truth from an icon, arbitrate Plexamp versus AirPlay, create an
AirPlay hold timer or decide that alarm audio may play.

The active Settings page no longer loads the old horizontal-tab,
`settings-tabs.js`, old autosave, alarm-workspace or scheduled-audio injector
clients.

## Runtime persistence

Small atomic JSON stores preserve alarm runtime, alarm-audio diagnostics,
playback hold/ceded state, cached forecast and dashboard/application state. Writes
use a temporary file followed by replacement.

## Current physical validation

The bedroom Raspberry Pi has validated:

- kiosk reboot into the dashboard Clock;
- Plexamp and NFC playback;
- bidirectional Plexamp/AirPlay handoff;
- managed AirPlay receiver naming and discovery;
- real scheduled alarm audio, Snooze and Dismiss;
- no automatic music resume after an alarm;
- shared ALSA mixer and output trims;
- Ecowitt observations and cached Open-Meteo forecast presentation;
- unified iPad Settings autosave and touch keyboard;
- read-only audio route presentation.

The current completion pass awaits focused physical validation of display
dimming, global 12/24-hour presentation, 16-day rendering, cleaned Advanced Audio
and updated About. Production EQ follows as a separate guarded phase.

PR #2 remains draft and must not be merged without explicit approval.
