# A Clockwork Plex

A Raspberry Pi touchscreen appliance for Plexamp Headless, NFC-triggered albums,
AirPlay, a bedside clock, local weather and scheduled alarms — with considerably
more state management than the average bedside clock strictly requires.

A Clockwork Plex is the dashboard layer for
[`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener).
The companion listener reads NFC album tags and starts Plexamp playback; this
project provides the touchscreen, audio arbitration, alarm runtime and appliance
behaviour around it.

> **Development branch:** `feature/alarm-engine` contains the current production
> candidate. Draft PR #2 remains deliberately unmerged while cleanup and physical
> regression testing continue. Do not merge it without explicit approval.

> **EQ safety:** the known-good direct shared mixer remains the live production
> graph. Do not run `sudo bash scripts/install-master-eq.sh`. Production EQ
> integration remains blocked.

## Current status

The bedroom Raspberry Pi has physically validated:

- Clock, navigation and touch-driven Settings;
- persistent preloaded Plexamp presentation;
- AirPlay Ready/Now Playing and sender controls;
- bidirectional Plexamp/AirPlay handoff;
- persisted ten-minute AirPlay pause hold;
- shared ALSA audio and Mk II mixer controls;
- multiple scheduled alarms with local tones;
- real clock-triggered alarm playback;
- Snooze, repeated ringing and Dismiss;
- Plexamp and AirPlay pause during alarm priority;
- manual music resume after the alarm;
- alarm configuration persistence and keyboard-safe editing.

| Area | Current behaviour |
|---|---|
| **Clock** | Custom segmented time/date display with configurable 12/24-hour format and compact local-weather cards. |
| **Weather** | Existing Ecowitt local-station console and upload endpoint. Final provider work is deliberately the last development stage. |
| **Plexamp** | Plexamp Headless is preloaded in a persistent hidden iframe and promoted when selected or requested by NFC. |
| **AirPlay** | Shairport Sync stays alive through the shared mixer; artwork, metadata, progress, transport and volume are exposed on the touchscreen. |
| **Playback authority** | One server-side coordinator owns AirPlay hold timing, transport intent, bidirectional handoff and alarm audio priority. |
| **Shared audio** | Plexamp, AirPlay and alarms use source trims, one Master stage and a common ALSA `dmix` output. |
| **Mk II mixer** | Player-aware Plexamp/AirPlay live faders, persistent trims, Master, Alarm ceiling and AirPlay START level. |
| **Alarms** | Multiple alarms, DST-aware scheduling, restart recovery, local tones, scheduled sound, Snooze, Dismiss and music-source takeover. |
| **Settings** | General settings autosave; alarm configuration and audio use dedicated validated APIs. Alarm tests and diagnostics live under Advanced. |
| **Screen projection** | Server-owned surface selection with manual leases, input activity, playback generations and immediate alarm priority. |
| **Master EQ** | Interface and laboratory work retained, but no production backend is enabled. |

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Segmented clock/date and compact weather cards. |
| **Weather** | `/weather` | Detailed local weather-station console. |
| **Plexamp** | `/plexamp` | Route fallback for the persistent full-screen Plexamp layer. |
| **AirPlay** | `/airplay` | Receiver-ready, paused and Now Playing states. |
| **Settings** | `/settings` | General, Weather, Alarms, AirPlay, Audio, Plexamp, Advanced and About workspaces. |
| **Alarm** | `/alarm` | Full-screen ringing, Snoozed and deliberate Dismiss controls. |

## How the pieces fit together

```text
NFC tag
  -> Plexamp-NFC-Listener
       -> Plexamp Headless on localhost:32500
       -> A Clockwork Plex selects Plexamp surface

Ecowitt station
  -> POST /api/weather/ecowitt
       -> Clock cards and Weather console

Plexamp  -> acp_plexamp --\
AirPlay  -> acp_airplay ---+-> acp_master -> acp_dmix -> physical DAC
Alarm    -> acp_alarm -----/
```

Application ownership:

```text
ActiveAlarmScheduler
  time, recurrence, DST, occurrence recovery, Snooze and Dismiss

ScheduledAlarmAudioManager
  local-tone playback through acp_alarm

PlaybackCoordinator
  AirPlay hold, transport, Plexamp/AirPlay handoff and alarm audio priority

MixerController
  live player/sender controls and persistent ALSA trims

ScreenProjectionController
  visible surface, manual leases, activity and immediate alarm takeover
```

The browser requests actions and renders state. It does not restart services,
manage hold timers or independently decide which source owns the speakers.

More detail is in
[`docs/application-state-architecture.md`](docs/application-state-architecture.md).

## Alarm behaviour

A real sounding alarm requires both safety keys under **Settings → Alarms**:

1. **Enable alarm sound**
2. **Enable scheduled alarm sound**

When a scheduled occurrence rings:

1. the Alarm screen appears immediately;
2. the selected local tone starts through `acp_alarm`;
3. playing Plexamp and/or AirPlay is paused;
4. restarting either source during the same alarm causes it to be paused again;
5. Snooze stops the alarm and it returns after the configured interval;
6. Dismiss completes that occurrence;
7. music remains paused until deliberately resumed.

Visual-only tests do not pause music. Controlled audio tests remain finite and
backend-capped.

Alarm configuration is a JavaScript model posted as JSON to
`/api/alarms/config`, so it intentionally uses a dedicated **Save alarms** action
rather than the simpler general Settings form autosave. The save card returns to
normal page flow while the on-screen keyboard is open.

The complete safety and regression guide is in
[`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## Playback and screen state APIs

Main application endpoints:

```text
GET  /api/state
GET  /api/playback/state
GET  /api/playback/events
POST /api/playback/events
POST /api/playback/command
POST /api/screen/state
```

Alarm endpoints:

```text
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
scheduler object. The top-level and nested `playback_enabled` values should agree.

## Shared audio and mixer

The live path is:

```text
Plexamp player volume -> acp_plexamp trim --\
AirPlay sender volume -> acp_airplay trim ---+-> acp_master -> acp_dmix -> DAC
Alarm fade/target     -> acp_alarm trim -----/
```

The human-facing fader scale is amplitude based:

```text
100% =   0.00 dB
 50% ≈  -6.02 dB
 25% ≈ -12.04 dB
 10% = -20.00 dB
```

Raw ALSA percentages therefore differ from dashboard percentages. Diagnostic APIs
expose both values.

### AirPlay START level

START is independent from AirPlay live volume and trim:

```text
START = requested live fader position for the next AirPlay session
TRIM  = persistent downstream calibration
```

Changing START during a session does not alter that session.

## Startup, idle return and screen leases

Settings → General separates:

- **Startup page** — first surface shown at the root kiosk URL;
- **Idle return page** — destination after inactivity when playback is quiet.

Manual navigation creates a server-side lease. Touch and keyboard activity renew
it. New playback activity may interrupt a background page, but ordinary track
progression within the same Plexamp queue does not. A ringing alarm always
interrupts every manual lease immediately.

## Settings

Top-level workspaces:

```text
GENERAL | WEATHER | ALARMS | AIRPLAY | AUDIO | PLEXAMP | ADVANCED | ABOUT
```

- General, Weather, AirPlay and Plexamp fields use general form autosave.
- Alarm cards use `/api/alarms/config` and **Save alarms**.
- Alarm sound safety uses `/api/alarms/audio/settings`.
- Mixer controls use dedicated live/trim APIs.
- Alarm tests, runtime diagnostics and physical audio details live under Advanced.

## Requirements

Designed for Raspberry Pi OS with:

- Python 3 and `venv`;
- Chromium in kiosk mode;
- Plexamp Headless on `http://localhost:32500`;
- Shairport Sync;
- ALSA utilities;
- an Ecowitt-compatible station for current local weather support;
- `Plexamp-NFC-Listener` and a supported NFC reader when using tags.

The Flask service listens on port `8088` by default. It is intended for a trusted
LAN. Do not expose the control APIs directly to the public internet without
appropriate authentication and a secure reverse proxy.

## Quick start

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

Open:

```text
http://localhost:8088
```

## Running as a service

```bash
cd ~/A-Clockwork-Plex
sudo cp systemd/a-clockwork-plex.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now a-clockwork-plex.service
systemctl status a-clockwork-plex.service --no-pager
```

## Updating an existing installation

For ordinary Python, CSS, JavaScript or documentation changes:

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
bash scripts/run-tests.sh
sudo systemctl restart a-clockwork-plex.service
```

Hard-refresh Chromium after browser assets change:

```text
Ctrl+Shift+R
```

Only refresh the shared audio installation when managed ALSA/helper files have
actually changed:

```bash
sudo bash scripts/install-shared-audio.sh
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Plexamp should explicitly select:

```text
A Clockwork Plex - Plexamp
```

## Testing

Run the complete suite:

```bash
bash scripts/run-tests.sh
```

GitHub Actions also checks Python compilation, JavaScript syntax, shell safety,
alarm/runtime behaviour, stereo tone rendering, mixer conversion, AirPlay state
resolution, coordinator ownership, screen projection and guarded DSP laboratories.

Useful live summaries:

```bash
curl -s http://localhost:8088/api/playback/state | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/scheduler | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/alarms/audio | venv/bin/python -m json.tool
curl -s http://localhost:8088/api/audio/mixer | venv/bin/python -m json.tool
```

## Repository layout

```text
A-Clockwork-Plex/
├── app/
│   ├── runner.py
│   ├── dashboard_core.py
│   ├── application_state.py
│   ├── playback_*.py
│   ├── screen_projection*.py
│   ├── alarm_*.py
│   ├── mixer_controller.py
│   ├── templates/
│   └── static/
├── docs/
├── scripts/
├── systemd/
├── tests/
├── config.example.json
├── requirements.txt
└── README.md
```

## Remaining roadmap

1. Continue Stage 11 diagnostic, documentation and compatibility cleanup.
2. Complete the physical regression matrix across alarms, Plexamp, AirPlay,
   navigation and service restarts.
3. Keep production EQ integration blocked unless a separately approved design
   passes its laboratory, rollback and physical regression criteria.
4. Complete the weather-provider work as the **final development stage**.
5. Update release notes and obtain explicit approval before making PR #2 ready or
   merging it.

PR #2 remains draft and unmerged until that explicit approval is given.
