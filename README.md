# A Clockwork Plex

A Raspberry Pi touchscreen appliance for Plexamp Headless, NFC-triggered albums,
AirPlay, a bedside clock, local weather and scheduled alarms.

It is the dashboard companion to
[`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener),
which reads NFC album tags and starts Plexamp playback.

> **Development branch:** `feature/alarm-engine` is the current production
> candidate. PR #2 remains draft and unmerged until explicit approval is given.

> **EQ safety:** the known-good direct shared mixer remains the live production
> graph. Do not run `sudo bash scripts/install-master-eq.sh`. Production EQ
> integration remains blocked.

## Physically validated

The bedroom Raspberry Pi has validated:

- Clock, navigation and touchscreen Settings;
- persistent preloaded Plexamp presentation;
- AirPlay Ready/Now Playing, metadata, transport and volume;
- bidirectional Plexamp/AirPlay handoff;
- persisted ten-minute AirPlay pause hold;
- shared ALSA audio and Mk II mixer controls;
- multiple scheduled alarms with local tones;
- real clock-triggered alarm playback;
- Snooze, repeated ringing and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- manual music resume after the alarm;
- alarm configuration persistence and keyboard-safe editing.

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| Clock | `/clock` | Segmented clock/date and compact local-weather cards. |
| Weather | `/weather` | Detailed Ecowitt local-station console. |
| Plexamp | `/plexamp` | Fallback route for the persistent Plexamp layer. |
| AirPlay | `/airplay` | Receiver-ready, paused and Now Playing states. |
| Settings | `/settings` | General, Weather, Alarms, AirPlay, Plexamp, Advanced and About. |
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
```

The browser requests explicit actions and renders server state. It does not
restart services, own hold timers or independently arbitrate audio sources.

See [`docs/application-state-architecture.md`](docs/application-state-architecture.md).

## Scheduled alarms

A real sounding alarm requires both safety keys under **Settings → Alarms**:

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

Alarm cards are saved as one validated JSON model through `/api/alarms/config`,
so they use **Save alarms** rather than general form autosave. The save card
returns to document flow while the on-screen keyboard is open. Testing and
runtime diagnostics live under Advanced.

See [`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## Main APIs

```text
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
```

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

Only refresh the shared audio installation when its managed files actually
change:

```bash
sudo bash scripts/install-shared-audio.sh
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Plexamp should explicitly select `A Clockwork Plex - Plexamp`.

Useful live diagnostics:

```bash
curl -s http://localhost:8088/api/playback/state | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/scheduler | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/audio | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/audio/mixer | venv/bin/python -m json.tool
```

## Remaining roadmap

1. Continue Stage 11 diagnostic, documentation and compatibility cleanup.
2. Complete the physical regression matrix across alarms, Plexamp, AirPlay,
   navigation and service restarts.
3. Keep production EQ integration blocked unless a separately approved design
   passes laboratory, rollback and physical regression criteria.
4. Complete the weather-provider work as the **final development stage**.
5. Update release notes and obtain explicit approval before making PR #2 ready or
   merging it.

PR #2 remains draft and unmerged until that explicit approval is given.
