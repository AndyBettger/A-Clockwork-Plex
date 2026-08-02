# A Clockwork Plex

A Raspberry Pi touchscreen appliance for Plexamp Headless, NFC-triggered albums,
AirPlay, a bedside Clock, local Weather and scheduled alarms.

It is the dashboard companion to
[`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener),
which reads NFC album tags and starts Plexamp playback.

> **Development branch:** `feature/alarm-engine` is the current production
> candidate. PR #2 remains draft and unmerged until explicit approval is given.

> **EQ safety:** the old bare `scripts/install-master-eq.sh` production path
> remains blocked. The guarded CamillaDSP production rollout is the next
> substantive engineering phase; EQ itself has not been abandoned.

## Physically validated appliance

The bedroom Raspberry Pi has validated:

- dashboard kiosk startup into the Clock after a real reboot;
- persistent preloaded Plexamp presentation and NFC album playback;
- AirPlay Ready/Now Playing, metadata, transport and volume;
- one configurable AirPlay receiver name used by Settings, Shairport Sync, the
  dashboard and the iPhone destination list;
- bidirectional Plexamp/AirPlay handoff and rapid iPhone resume handling;
- shared ALSA audio and calibrated master/source/alarm trims;
- multiple scheduled alarms with real clock-triggered alarm playback;
- Snooze, repeated ringing and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- manual music resume after the alarm;
- Ecowitt live observations plus cached Open-Meteo forecasts;
- unified Weather scrolling and rounded horizontal forecast controls;
- unified iPad-style Settings with one revisioned autosave authority;
- touch-keyboard editing, detailed dirty indicators and managed AirPlay restart;
- read-only audio route diagnostics and deliberate alarm-audio tests.

Weather-provider work was the **final development stage** for major subsystem
implementation and has been built and physically validated. The current
completion pass adds scheduled display dimming, one dashboard-wide clock-format
authority, truthful 1–16 day forecast presentation and refreshed About/status
information before the separate guarded production-EQ phase.

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| Clock | `/clock` | Segmented clock/date and compact local-weather cards. |
| Weather | `/weather` | Ecowitt station console plus cached Open-Meteo outlook. |
| Plexamp | `/plexamp` | Fallback route for the persistent Plexamp layer. |
| AirPlay | `/airplay` | Receiver-ready, paused and Now Playing states. |
| Settings | `/settings` | iPad-style split view with revisioned autosave. |
| Alarm | `/alarm` | Ringing, Snoozed and deliberate Dismiss controls. |

## Audio path

```text
Plexamp  -> acp_plexamp --\
AirPlay  -> acp_airplay ---+-> acp_master -> acp_dmix -> physical DAC
Alarm    -> acp_alarm -----/
```

Plexamp and Shairport Sync remain running. Handoffs and alarm priority use
transport commands, not service stops or exclusive-DAC takeovers.

The human-facing level scale is amplitude based:

```text
100% =   0.00 dB
 50% ≈  -6.02 dB
 25% ≈ -12.04 dB
 10% = -20.00 dB
```

Raw ALSA percentages are therefore expected to differ.

## Authority model

```text
ActiveAlarmScheduler
  timing, recurrence, DST, recovery, Snooze and Dismiss

ScheduledAlarmAudioManager
  local-tone playback through acp_alarm

RetainedBidirectionalHandoffCoordinator
  AirPlay hold, transport, Plexamp/AirPlay handoff and alarm audio priority

MixerController
  live player/sender controls and persistent ALSA trims

ScreenProjectionController
  visible surface, manual leases, activity and immediate alarm takeover

UnifiedSettingsService
  revisioned validation, one config write and domain-specific post-save hooks

ACPTime
  one 12/24-hour presentation policy for dashboard time displays

ACPDisplayDimming
  overnight visual dim schedule, touch-to-wake and Clock night presentation
```

The browser requests explicit actions and renders server state. It does not
restart services, own playback hold timers or independently arbitrate audio
sources.

See [`docs/application-state-architecture.md`](docs/application-state-architecture.md).

## Unified Settings

Settings uses a persistent left category column and right detail pane:

```text
Settings
├── General
├── Display
├── Weather
├── Alarms
├── AirPlay
├── Audio
├── Plexamp
├── Advanced
└── About
```

Configuration autosaves through one revisioned API transaction:

```text
GET  /api/settings
POST /api/settings
```

The backend validates each domain through its specialist validator, rejects
stale writes, writes `config.json` once and wakes or refreshes affected runtime
owners. Immediate actions remain separate, including live mixer moves, forecast
refresh-now, alarm tests, emergency stop and runtime diagnostics.

Weather unit presets are shortcuts only. Temperature, pressure, rain and wind
remain independently selectable and become **Custom** when appropriate.

The Advanced Audio page is diagnostic, not a route editor. Physical DAC, shared
PCM and mixer readiness are read-only. Changing the live audio route remains a
guarded maintenance operation with rollback.

## Display and clock format

The 12/24-hour setting is the dashboard presentation authority for the main
Clock, AirPlay mini clock, alarm display, Weather timestamps, forecast hours,
Advanced diagnostics and status timestamps. Alarm configuration values remain
stored as unambiguous 24-hour `HH:MM` values.

Scheduled night dimming provides:

- enable/disable;
- start and end time, including schedules crossing midnight;
- adjustable visual brightness level;
- touch-to-wake duration;
- optional very-dark Clock mode;
- subtle burn-in shifting;
- guaranteed full brightness on the Alarm screen and outside the schedule.

Dimming uses a browser overlay. It does not invoke `xrandr`, alter a Pi display
driver, require root, or touch the audio graph.

## Weather observations and forecast

Ecowitt custom upload remains authoritative for live observations. Open-Meteo is
used only for online forecast guidance and is isolated behind a local cache. The
last good forecast survives dashboard restarts and remains available during
provider or internet failure with a visible stale-data warning.

Open-Meteo supports up to 16 forecast days. Settings exposes 1, 3, 5, 7, 10, 14
and 16 days, and the Weather page renders every daily item actually returned.
Hourly and forecast-update times follow the global 12/24-hour setting.

## Scheduled alarms

A real sounding alarm requires both safety keys under **Settings → Alarms →
Sound**:

1. **Enable alarm sound**
2. **Enable scheduled alarm sound**

When a scheduled occurrence rings:

1. the Alarm screen appears immediately;
2. the selected tone starts through `acp_alarm`;
3. playing Plexamp and/or AirPlay is paused;
4. a source restarted during the same alarm is paused again;
5. Snooze stops the tone and schedules its return;
6. Dismiss completes the occurrence;
7. music remains paused until deliberately resumed.

The timing scheduler does not play audio directly. It delegates sound to the
promoted scheduled-alarm-audio manager, which is why the scheduler's internal
playback flag remains false while the public status can correctly report sound
enabled.

See [`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## Managed AirPlay receiver name

The AirPlay receiver name is one setting used by the dashboard and advertised
Shairport Sync receiver. A narrowly restricted helper edits only `general.name`
in the fixed Shairport configuration, validates the candidate on an isolated
port and identity, restarts only Shairport Sync, verifies active state and rolls
back on failure.

Install the helper deliberately:

```bash
sudo bash scripts/install-shairport-name-helper.sh
```

Changing the name from Settings requires confirmation because it briefly
interrupts an active AirPlay session.

## Dashboard kiosk

The guarded kiosk installer defaults to inspection mode. Apply mode backs up
touched desktop-session files, disables only Chromium launches aimed directly
at Plexamp port `32500`, waits for the dashboard API and uses a dedicated
Chromium profile:

```bash
bash scripts/install-dashboard-kiosk.sh
bash scripts/install-dashboard-kiosk.sh --apply --confirm INSTALL-DASHBOARD-KIOSK
```

It does not restart or reconfigure Plexamp Headless, Shairport Sync or ALSA.

## Equaliser

Settings-hosted EQ controls retain:

- enabled/bypassed;
- Bass;
- Mid;
- Treble;
- reset to flat;
- backend health.

The guarded CamillaDSP laboratory and physical-rehearsal assets remain in the
branch. Production activation must capture exact state, preserve the known-good
shared mixer and provide automatic rollback.

```text
Do not run: sudo bash scripts/install-master-eq.sh
```

## Main APIs

```text
GET/POST /api/settings
GET      /api/state
GET      /api/playback/state
GET      /api/playback/events
POST     /api/playback/events
POST     /api/playback/command
POST     /api/screen/state

GET/POST /api/alarms/config
GET      /api/alarms/audio
POST     /api/alarms/audio/settings
POST     /api/alarms/audio/test
POST     /api/alarms/audio/stop
GET/POST /api/alarms/scheduler
GET      /api/alarms/active
POST     /api/alarms/snooze
POST     /api/alarms/dismiss

GET/POST /api/weather/forecast
GET/POST /api/weather/forecast/config
```

## Requirements and development install

Designed for Raspberry Pi OS with Python 3, Chromium kiosk mode, Plexamp
Headless, Shairport Sync, ALSA utilities and optionally an Ecowitt station plus
the NFC companion project. The Flask service listens on port `8088` and is
intended for a trusted LAN.

```bash
git clone https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
git switch feature/alarm-engine
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp config.example.json config.json
python app/runner.py
```

## Update and test

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
bash scripts/run-tests.sh
sudo systemctl restart a-clockwork-plex.service
```

Hard-refresh Chromium after browser assets change with `Ctrl+Shift+R`.

Useful diagnostics:

```bash
curl -s http://localhost:8088/api/settings | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/playback/state | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/scheduler | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/audio | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/audio/mixer | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/weather/forecast | venv/bin/python -m json.tool
```

## Remaining roadmap

1. Physically validate scheduled dimming, touch-to-wake, global 12/24-hour
   presentation, 16-day Weather rendering and cleaned Advanced/About pages.
2. Make only small layout corrections discovered on the 1024×600 screen.
3. Begin the separate guarded production-EQ rollout without using the blocked
   bare installer.
4. Run the final release smoke test.
5. Obtain explicit approval before making PR #2 ready or merging it.

PR #2 remains draft and unmerged until that explicit approval is given.
