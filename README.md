# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, local Ecowitt weather, a bedside clock and alarm features — hopefully with no toast-related incidents.

A Clockwork Plex is the dashboard/appliance layer for [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The NFC listener reads album tags and starts Plexamp playback; this project provides the touchscreen interface around it.

> Development note: the `feature/alarm-engine` branch contains the current alarm runtime, shared ALSA audio path, Mk II live mixer, unified AirPlay layout and persistent preloaded Plexamp layer. Draft PR #2 remains deliberately unmerged while Raspberry Pi testing continues. Ordinary scheduled alarm audio is still locked.

## Current status

The Clock, Weather, embedded Plexamp, AirPlay Ready/Now Playing, navigation, autosaving Settings workspace, alarm runtime, shared audio path and controlled alarm-audio tests are working on Raspberry Pi touchscreen hardware.

| Area | Current behaviour |
|---|---|
| **Clock** | Large custom fourteen-segment SVG clock and date, 12/24-hour format, balanced punctuation and live weather cards. |
| **Clock weather cards** | Touch-configurable ordering with compact combined cards for indoor/outdoor temperature, indoor/outdoor humidity, wind speed/gust, rain today/event rain and solar/UV. |
| **Weather** | Detailed Ecowitt console with conditions, daily low/high values, 16-point wind direction, pressure/barometer forecast, rain gauges, station status and auto-refresh. |
| **Plexamp** | Plexamp Headless is preloaded in a hidden persistent iframe and promoted into a full-screen layer when selected or requested by NFC, avoiding routine grey reload and home-to-Now-Playing flashes. |
| **NFC handoff** | A successful NFC album scan can start Plexamp and promote the preloaded Plexamp layer. |
| **AirPlay handoff** | Shairport Sync pauses Plexamp and changes dashboard mode while both services remain alive through the shared ALSA mixer. Returning to Plexamp arms a watcher; AirPlay is paused or stopped only when Plexamp actually begins playing. |
| **AirPlay Ready/Now Playing** | Receiver-ready page plus artwork, metadata, progress, transport controls, shared live-volume control and a glance row. Ready and Now Playing share one measured artwork/logo square and one right-column grid. |
| **Shared audio** | Plexamp, AirPlay and alarm sources feed source-specific trims, one master stage and a common ALSA `dmix` output. |
| **Mk II audio console** | A full-height live mixer with a wide Master bus, Alarm ceiling, player-aware Plexamp/AirPlay faders, persistent trims, AirPlay START preset and fascia controls that correctly go to 11. |
| **Settings** | General, Weather, AirPlay, Plexamp and Advanced controls autosave. Audio and Alarms retain dedicated validated APIs. |
| **Idle return** | The configured dashboard idle timeout is playback-aware: quiet non-Clock screens return to Clock, while active Plexamp, AirPlay or alarm playback prevents the return. |
| **Alarms** | Multiple-alarm configuration, local tones, DST-aware scheduling, reboot recovery, full-screen takeover, Snooze, slide-to-dismiss and controlled audio tests. |
| **Navigation and motion** | Hidden bottom drawer, player-aware Audio console, browser-side mode polling, animated drawer open/close, persistent Plexamp promotion and subtle page transitions. |

## Visual system

The interface uses a shared instrument-console design across Clock, Weather, AirPlay and Audio:

- reusable SVG fourteen-segment digits and letters;
- Oxanium for display headings and Atkinson Hyperlegible for general UI text;
- DejaVu/Arial fallbacks when the web fonts are unavailable;
- common segment sizing, unit alignment, decimal and colon spacing;
- illuminated Weather panels, compass, pressure console and dynamic rain gauges;
- tactile rotary controls with navy faces and cyan datum marks;
- calibrated vertical mixer faders with proper caps, alternating graduations and 0–11 fascia markings;
- measured AirPlay hero geometry that keeps artwork/logo, copy and controls aligned across Ready and Now Playing;
- brief appliance-style page transitions, with immediate alarm takeover and reduced-motion support.

The editable segment geometry lives in `docs/airplay-segment-cell.svg`; the shared renderer is in `app/static/js/segment-display.js`.

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Default idle screen with the segmented clock/date and compact weather cards. |
| **Weather** | `/weather` | Detailed weather-station console. |
| **Plexamp** | `/plexamp` | Route fallback for the preloaded full-screen Plexamp layer. |
| **AirPlay** | `/airplay` | AirPlay Ready, paused and Now Playing states. |
| **Settings** | `/settings` | Touchscreen configuration page with General, Weather, Alarms, AirPlay, Audio, Plexamp, Advanced and About workspaces. |
| **Alarm** | `/alarm` | Full-screen ringing, snoozed and deliberate dismiss controls. |

## How the pieces fit together

```text
NFC tag
  └─> Plexamp-NFC-Listener
        ├─> Plexamp Headless playback on localhost:32500
        └─> A Clockwork Plex mode switch to plexamp
              └─> promote the already preloaded Plexamp iframe

Ecowitt custom upload
  └─> /api/weather/ecowitt
        └─> Clock and detailed Weather screens

Plexamp  ──> acp_plexamp ┐
AirPlay  ──> acp_airplay ├──> acp_master ──> acp_dmix ──> DAC
Alarm    ──> acp_alarm   ┘

AirPlay session
  └─> Shairport Sync hooks
        ├─> pause Plexamp without stopping its service
        ├─> switch dashboard to /airplay
        ├─> publish artwork, metadata, progress and sender state
        ├─> apply the saved START level to the live AirPlay fader
        └─> return to Clock when finished

Open Plexamp while AirPlay is playing
  └─> arm handoff watcher
        ├─> browsing Plexamp leaves AirPlay alone
        └─> Plexamp begins playing → Pause AirPlay → Stop fallback if required
```

## Repository layout

```text
A-Clockwork-Plex/
├── app/
│   ├── main.py
│   ├── dashboard_core.py
│   ├── alarm_config.py
│   ├── alarm_scheduler.py
│   ├── alarm_runtime.py
│   ├── alarm_audio.py
│   ├── alarm_audio_core.py
│   ├── audio_mixer.py
│   ├── templates/
│   └── static/
├── docs/
│   ├── alarm-audio-testing.md
│   ├── testing.md
│   └── airplay-segment-cell.svg
├── scripts/
│   ├── install-shared-audio.sh
│   ├── a-clockwork-plex-audio-mixer.py
│   ├── install-airplay-hooks.sh
│   ├── run-tests.sh
│   └── ...
├── systemd/
│   └── a-clockwork-plex.service
├── config.example.json
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

## Requirements

The project is designed for a Raspberry Pi running Raspberry Pi OS with:

- Python 3 and `venv`;
- Chromium in kiosk mode;
- Plexamp Headless listening on `http://localhost:32500`;
- Shairport Sync for AirPlay integration;
- ALSA utilities for shared audio and alarm playback;
- an Ecowitt-compatible weather station when weather data is required;
- `Plexamp-NFC-Listener` and a supported NFC reader for tag-triggered playback.

The Flask service listens on port `8088` by default. It is intended as a trusted-LAN appliance; do not expose its control endpoints directly to the public internet without suitable authentication and a secure reverse proxy.

## Quick start

```bash
git clone https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp config.example.json config.json
python app/main.py
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

### Updating an existing installation

For ordinary application, CSS or JavaScript changes:

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

When shared-audio, ALSA-helper or Shairport files change, also run the staged installer and restart the audio services:

```bash
sudo bash scripts/install-shared-audio.sh
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

## Shared audio path

Install or refresh the shared audio path:

```bash
cd ~/A-Clockwork-Plex
sudo bash scripts/install-shared-audio.sh
```

Plexamp should explicitly use:

```text
A Clockwork Plex - Plexamp
```

The shared path is:

```text
Plexamp player volume → acp_plexamp trim ┐
AirPlay sender volume → acp_airplay trim ├→ acp_master → acp_dmix → DAC
Alarm fade/target     → acp_alarm trim   ┘
```

This lets alarm tones mix over Plexamp or AirPlay without stopping either service and avoids repeated exclusive-DAC handoffs.

Detailed installation, staged testing and rollback instructions are in [`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## Mk II live audio console

Open the bottom drawer and select **Audio**. The console contains three main strips.

### Master bus

- a large **MASTER** knob controlling the final shared output;
- a separate **ALARM** ceiling knob;
- no duplicate Master or Alarm faders, because each knob already owns its underlying ALSA stage.

### Plexamp strip

- **TRIM** knob: persistent downstream calibration after Plexamp's own player volume;
- live fader: Plexamp's real player volume, reflected by Plexamp's Now Playing interface.

### AirPlay strip

- **TRIM** knob: persistent downstream calibration after the sender volume;
- live fader: current AirPlay sender gain using the dashboard's perceptual scale;
- **START** knob: the live-fader position requested for the next AirPlay connection.

The controls use a 0–11 fascia while APIs continue using 0–100 internally. Fader requests use latest-value-wins queues, local pointer ownership and readback protection so polling cannot pull a control away while it is being touched.

## Volume scales

The dashboard's player and trim controls use an amplitude-style scale:

```text
50% ≈ -6 dB
25% ≈ -12 dB
10% ≈ -20 dB
```

The raw ALSA percentage shown by `alsamixer` is expected to differ. For example, dashboard 50% appears near the top of an ALSA soft-volume control because both represent approximately -6 dB.

Shairport exposes the iPhone sender through a much steeper native taper. A Clockwork Plex translates between that native scale and the dashboard scale so equivalent gain combinations behave predictably:

```text
AirPlay fader 50% + trim 100% ≈ AirPlay fader 100% + trim 50%
```

The iPhone's visible percentage may therefore differ from the dashboard's 0–11 position. The dashboard represents resulting gain; the phone represents Shairport's native sender position.

## AirPlay START behaviour

START is independent from both live volume and AirPlay trim:

```text
START = where the live AirPlay fader should land on the next connection
TRIM  = separate downstream calibration
```

Changing START during an active session does not alter that current session. The new target is saved for the next connection and committed at the AirPlay session boundary, including rapid disconnect/reconnect cases.

## AirPlay layout

Ready and Now Playing use one measured hero grid:

- the left media square is calculated from the hero's available height;
- artwork fills that square with equal top, bottom and left breathing room;
- the Ready logo occupies the same square;
- both right-hand columns begin at the same horizontal position;
- both use the same right margin;
- progress and volume controls finish on that same right edge;
- Ready pulses originate at the visual centre of the AirPlay arcs, begin at a smaller radius and expand beneath the copy.

## AirPlay Now Playing

The AirPlay page provides:

- artwork, title, artist and album;
- previous, play/pause and next controls;
- elapsed and remaining time;
- a live volume slider using the same `/api/audio/live` queue and scale as the Audio drawer;
- a 0–11 visible readout;
- segmented time/date, outdoor temperature/humidity and barometer status.

## Persistent Plexamp layer

Every normal dashboard document preloads one Plexamp iframe invisibly. Selecting Plexamp or receiving an NFC-driven `plexamp` mode request promotes that iframe with a short fade/scale transition.

Benefits:

- Plexamp normally finishes its initial home/Now-Playing rendering before it is visible;
- opening and closing Plexamp within the current dashboard document does not rebuild the iframe;
- audio/player state remains connected while the layer is hidden;
- the navigation drawer remains above the layer;
- direct `/plexamp` navigation remains available as a fallback.

Moving between separate dashboard routes still creates a new document and warms a new hidden iframe. This is deliberately smaller and safer than converting the entire dashboard into a single-page application.

## Idle return

`dashboard.idle_timeout_seconds` defaults to 180 seconds. The browser now uses it on every non-Clock screen.

After the timeout, the dashboard checks real playback state:

- Plexamp playing → remain on the current screen;
- AirPlay playing → remain on the current screen;
- alarm takeover or alarm audio active → remain on the current screen;
- no playback → set mode to Clock and return with the normal page transition.

Pointer, touch, keyboard, wheel and form input activity reset the timer. A value of `0` disables idle return.

## Settings and autosave

Settings uses top-level workspaces:

```text
GENERAL | WEATHER | ALARMS | AIRPLAY | AUDIO | PLEXAMP | ADVANCED | ABOUT
```

General, Weather, AirPlay, Plexamp and Advanced controls autosave and briefly show **Saving…**, **Saved** or **Save failed**. Audio trims and alarm configuration use their own APIs so live mixer state, validation and safety rules are preserved.

## Alarm status

The current alarm branch includes:

- multiple persistent alarms;
- labels, times, weekdays, local tones, fades and target volumes;
- default snooze of eight minutes with configurable alternatives;
- local timezone and DST handling;
- spring-forward and fall-back behaviour;
- reboot recovery and duplicate-occurrence protection;
- persistent ringing, snoozed, dismissed and expired states;
- full-screen takeover;
- giant Snooze control and deliberate slide-to-dismiss;
- simultaneous occurrence queueing;
- 16-bit, 44.1 kHz dual-mono stereo local tones;
- selected-tone playback with Emergency Buzzer fallback;
- controlled direct-tone and full-screen tests;
- backend-enforced test-volume safety cap.

Ordinary scheduled alarm playback remains locked until the controlled test and shared-audio paths are fully proven.

## Kiosk browser

Point Chromium at the dashboard rather than directly at Plexamp:

```text
http://localhost:8088/clock
```

A typical labwc autostart command is:

```bash
sleep 10
chromium --kiosk --start-maximized --noerrdialogs --disable-infobars --no-first-run "http://localhost:8088/clock" &
```

## Weather station setup

A Clockwork Plex accepts Ecowitt/custom uploads at:

```text
/api/weather/ecowitt
```

Typical station settings:

| Setting | Value |
|---|---|
| Protocol | Ecowitt |
| Server IP / hostname | Raspberry Pi IP address |
| Port | `8088` |
| Path | `/api/weather/ecowitt` |
| Upload interval | `60` seconds |

Sensitive keys including `passkey`, `password`, `secret`, `token`, `api_key` and `apikey` are omitted from new stored uploads and redacted from status output when found in older state.

## Testing

Run the complete test suite:

```bash
bash scripts/run-tests.sh
```

GitHub Actions checks Python compilation, JavaScript and shell syntax, alarm/runtime behaviour, stereo tone rendering, mixer safety, perceptual volume conversion, AirPlay scale round trips, fader/state isolation, START-boundary handling, unified AirPlay layout, idle return and persistent Plexamp scripts.

## Development roadmap

Immediate next work on `feature/alarm-engine`:

1. Pi-test the unified AirPlay layout, Ready pulse origin, idle return and persistent Plexamp promotion;
2. add a guarded master-output **Bass / Mid / Treble** EQ stage with centre detents, neutral reset, bypass, installer backup and rollback;
3. repeat complete Plexamp, AirPlay, alarm-overlay, Snooze and Dismiss regression testing;
4. opt in scheduled local-tone alarm playback only after the controlled path is proven;
5. add Plexamp and stream alarm sources with local-tone fallback;
6. final hardening, documentation, merge and release.
