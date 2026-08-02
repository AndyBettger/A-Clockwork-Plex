# A Clockwork Plex

A Raspberry Pi touchscreen appliance for Plexamp Headless, NFC-triggered albums,
AirPlay, a bedside clock, local weather and scheduled alarms.

It is the dashboard companion to
[`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener),
which reads NFC album tags and starts Plexamp playback.

> **Development branch:** `feature/alarm-engine` is the current production
> candidate. PR #2 remains draft and unmerged until explicit approval is given.

> **EQ safety:** the old bare `scripts/install-master-eq.sh` production path
> remains blocked. The unified Settings integration uses the existing master-EQ
> authority and is awaiting focused physical validation with the new Settings
> screen.

## Physically validated

The bedroom Raspberry Pi has validated:

- Clock, navigation and the previous touchscreen Settings surface;
- persistent preloaded Plexamp presentation;
- AirPlay Ready/Now Playing, metadata, transport and volume;
- bidirectional Plexamp/AirPlay handoff;
- rapid iPhone AirPlay resume after Plexamp takeover;
- persisted ten-minute AirPlay pause hold;
- shared ALSA audio and Mk II mixer controls;
- multiple scheduled alarms with local tones;
- real clock-triggered alarm playback;
- Snooze, repeated ringing and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- manual music resume after the alarm;
- alarm configuration persistence and keyboard-safe editing;
- Ecowitt live observations plus cached Open-Meteo forecasts;
- forecast provider access, stale-cache fallback and the unified 1024×600
  Weather scroll layout.

The new unified iPad-style Settings screen, managed Shairport receiver-name path
and Settings-hosted EQ controls are code-complete and covered by CI, but require
the focused physical validation described in
[`docs/post-weather-settings-redesign.md`](docs/post-weather-settings-redesign.md).

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| Clock | `/clock` | Segmented clock/date and compact local-weather cards. |
| Weather | `/weather` | Detailed Ecowitt station console plus cached Open-Meteo outlook. |
| Plexamp | `/plexamp` | Fallback route for the persistent Plexamp layer. |
| AirPlay | `/airplay` | Receiver-ready, paused and Now Playing states. |
| Settings | `/settings` | iPad-style split view with one staged configuration transaction. |
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
```

The browser requests explicit actions and renders server state. It does not
restart services, own hold timers or independently arbitrate audio sources.

See [`docs/application-state-architecture.md`](docs/application-state-architecture.md).

## Unified Settings

Settings now uses a persistent left category column and a right detail pane.
Large categories use short subpages rather than one very long form.

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

Configuration is staged and saved through one revisioned API transaction:

```text
GET  /api/settings
POST /api/settings
```

The backend validates each domain through its established specialist validator,
rejects stale-page writes, writes `config.json` once and then wakes or refreshes
the affected runtime owners.

Immediate controls remain separate:

- persistent ALSA output trims;
- forecast refresh-now;
- alarm tests and emergency stop;
- scheduler recalculation;
- authority and service diagnostic refreshes.

Weather presets are shortcuts only. Temperature, pressure, rain and wind units
remain independently selectable and display **Custom** when they no longer match
a preset.

See [`docs/post-weather-settings-redesign.md`](docs/post-weather-settings-redesign.md).

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

Visual-only tests do not pause music. Controlled tests remain finite and
backend-capped.

The full alarm model, alarm defaults and both audio safety keys are now staged
inside the unified Settings transaction. Testing and runtime diagnostics remain
under Advanced and act immediately rather than dirtying Settings.

See [`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## AirPlay receiver name

The AirPlay receiver name is one setting used by the dashboard and the advertised
Shairport Sync receiver.

A narrowly restricted helper edits only `general.name` in the fixed Shairport
configuration, validates the candidate, restarts only Shairport Sync, verifies
that it returned active and rolls back on failure.

Install that helper deliberately on the Pi:

```bash
sudo bash scripts/install-shairport-name-helper.sh
```

Changing the receiver name from Settings requires confirmation because it will
briefly interrupt an active AirPlay session.

## Weather observations and forecast

Ecowitt custom upload remains authoritative for live observations. Open-Meteo is
used only for online forecast guidance and is isolated behind a local cache.
The last good forecast survives dashboard restarts and remains available during
provider or internet failure with a visible stale-data warning.

Forecast configuration participates in the unified Settings transaction and does
not require an API key. **Refresh forecast now** remains an immediate action.
Disabled or incomplete configuration makes no external request.

## Equaliser

The Audio Settings category retains:

- enabled/bypassed;
- Bass;
- Mid;
- Treble;
- staged reset to flat;
- backend health.

EQ configuration is committed through the unified transaction and uses the
existing master-EQ authority with rollback if the overall save fails. The old
bare master-EQ installer remains blocked and is not part of the normal Settings
rollout.

## Main APIs

```text
GET/POST /api/settings

GET  /api/state
GET  /api/playback/state
GET  /api/playback/events
POST /api/playback/events
POST /api/playback/command
POST /api/screen/state

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

The dedicated alarm and forecast configuration endpoints remain compatibility
contracts while the active Settings page uses `/api/settings`.

Public alarm status projects the promoted audio manager's truth onto the nested
scheduler object, so top-level and nested `playback_enabled` values should agree.

## Requirements

Designed for Raspberry Pi OS with Python 3, Chromium kiosk mode, Plexamp
Headless, Shairport Sync, ALSA utilities, and optionally the Ecowitt station and
NFC companion project.

The Flask service listens on port `8088` and is intended for a trusted LAN.

## Install

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

Open `http://localhost:8088`.

## Update and test

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
bash scripts/run-tests.sh
sudo systemctl restart a-clockwork-plex.service
```

Hard-refresh Chromium after browser assets change with `Ctrl+Shift+R`.

Do not rerun the shared-audio installation for the Settings rollout. Install only
the new receiver-name helper when deliberately testing that feature:

```bash
sudo bash scripts/install-shairport-name-helper.sh
```

The old bare master-EQ installer remains blocked:

```text
Do not run: sudo bash scripts/install-master-eq.sh
```

Useful live diagnostics:

```bash
curl -s http://localhost:8088/api/settings | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/playback/state | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/scheduler | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/audio | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/audio/mixer | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/weather/forecast | venv/bin/python -m json.tool
```

## Revised remaining roadmap

Weather-provider work was the **final development stage** for major subsystem
implementation and has been built and physically validated. The unified iPad
Settings consolidation is now code-complete.

Remaining work:

1. Physically validate the new split-view Settings page at 1024×600, including
   Save/Discard, subpages, touch keyboard and dirty indicators.
2. Install and validate the restricted Shairport receiver-name helper, including
   the warning, actual iOS receiver name, dashboard consistency and rollback-safe
   service restart.
3. Validate the Settings-hosted EQ controls against the proven production EQ
   authority; do not use the old bare installer.
4. Make any small layout or wording corrections found during that focused pass.
5. Finish delegated scheduler wording and remove dead compatibility files once
   no active path or test depends on them.
6. Refresh final release notes and run one focused appliance smoke test.
7. Obtain explicit approval before making PR #2 ready or merging it.

PR #2 remains draft and unmerged until that explicit approval is given.
