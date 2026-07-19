# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, local Ecowitt weather, a bedside clock and alarm features — hopefully with no toast-related incidents.

A Clockwork Plex is the dashboard/appliance layer for [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The NFC listener reads album tags and starts Plexamp playback; this project provides the touchscreen interface around it.

## Current status

The Clock, Weather, embedded Plexamp, AirPlay Ready/Now Playing, navigation, Settings workspace, alarm runtime and controlled alarm-audio tests are working on Raspberry Pi touchscreen hardware. Scheduled alarm audio remains deliberately locked while the shared-audio path is being proven.

| Area | Current behaviour |
|---|---|
| **Clock** | Large custom fourteen-segment SVG clock and date, 12/24-hour format, balanced punctuation and live weather cards. |
| **Clock weather cards** | Touch-configurable ordering with compact combined cards for indoor/outdoor temperature, indoor/outdoor humidity, wind speed/gust, rain today/event rain and solar/UV. |
| **Weather** | Detailed Ecowitt console with conditions, daily low/high values, 16-point wind direction, pressure/barometer forecast, rain gauges, station status and auto-refresh. |
| **Plexamp** | Plexamp Headless embedded in a dashboard iframe so the touchscreen navigation handle remains available. |
| **NFC handoff** | A successful NFC album scan can start Plexamp and switch the dashboard to the embedded Plexamp screen. |
| **AirPlay handoff** | Shairport Sync pauses Plexamp and changes the dashboard mode while both services remain alive through the shared ALSA mixer. |
| **AirPlay Ready/Now Playing** | Receiver-ready page plus artwork, metadata, progress, volume, transport controls and a glance row containing time/date, outdoor temperature/humidity and barometer status. |
| **Shared audio** | Plexamp, AirPlay and alarm sources feed source-specific trims, one master stage and a common ALSA `dmix` output. |
| **Audio controls** | Persistent vertical trims under Settings → Audio plus a player-aware live mixer in the bottom navigation drawer. |
| **Alarms** | Multiple-alarm configuration, local tones, DST-aware scheduling, screen takeover, Snooze, slide-to-dismiss and controlled audio tests. |
| **Navigation and mode watcher** | Hidden bottom drawer plus browser-side mode polling, so kiosk mode does not depend on `xdotool`. |

## Visual system

The current interface uses a shared instrument-console design across Clock, Weather, AirPlay and Audio:

- reusable SVG fourteen-segment digits and letters;
- Oxanium for display headings and Atkinson Hyperlegible for general UI text;
- DejaVu/Arial fallbacks when the web fonts are unavailable;
- common segment sizing, unit alignment, decimal and colon spacing;
- illuminated Weather panels, compass, pressure console and dynamic rain gauges;
- vertical mixer faders with human-facing perceptual volume scaling.

The editable segment geometry lives in `docs/airplay-segment-cell.svg`; the shared renderer is in `app/static/js/segment-display.js`.

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Default idle screen with the segmented clock/date and compact weather cards. |
| **Weather** | `/weather` | Detailed weather-station console. |
| **Plexamp** | `/plexamp` | Dashboard-hosted Plexamp iframe with the navigation handle. |
| **AirPlay** | `/airplay` | AirPlay Ready, paused and Now Playing states. |
| **Settings** | `/settings` | Touchscreen configuration page, including Audio and Alarms workspaces. |
| **Alarm** | `/alarm` | Full-screen ringing, snoozed and dismiss controls. |

## How the pieces fit together

```text
NFC tag
  └─> Plexamp-NFC-Listener
        ├─> Plexamp Headless playback on localhost:32500
        └─> A Clockwork Plex mode switch to /plexamp

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
        ├─> publish artwork/metadata/progress
        └─> return to Clock when finished
```

## Repository layout

```text
A-Clockwork-Plex/
├── app/
│   ├── main.py
│   ├── dashboard_core.py
│   ├── alarm_*.py
│   ├── audio_mixer.py
│   ├── templates/
│   └── static/
├── docs/
│   ├── alarm-audio-testing.md
│   └── testing.md
├── scripts/
│   ├── install-shared-audio.sh
│   ├── a-clockwork-plex-audio-mixer.py
│   ├── install-airplay-hooks.sh
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

The Flask service listens on port `8088` by default. It is intended as a trusted-LAN appliance; do not expose its control endpoints directly to the public internet without adding suitable authentication and a secure reverse proxy.

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

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
bash scripts/run-tests.sh
sudo systemctl restart a-clockwork-plex.service
```

When shared-audio or Shairport files change, also run:

```bash
sudo bash scripts/install-shared-audio.sh
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

After CSS or JavaScript changes, hard-refresh Chromium once with `Ctrl+Shift+R`.

## Shared audio and mixer

Install or refresh the shared audio path:

```bash
cd ~/A-Clockwork-Plex
sudo bash scripts/install-shared-audio.sh
```

Plexamp should explicitly use:

```text
A Clockwork Plex - Plexamp
```

Persistent calibration lives under **Settings → Audio**. The bottom navigation drawer has a separate **Audio** control that changes live Master, Plexamp, AirPlay and Alarm levels immediately.

The dashboard faders use a perceptual amplitude scale:

```text
50% ≈ -6 dB
25% ≈ -12 dB
10% ≈ -20 dB
```

The raw ALSA percentage shown by `alsamixer` is therefore expected to differ.

Detailed installation, staged testing and rollback instructions are in [`docs/alarm-audio-testing.md`](docs/alarm-audio-testing.md).

## Alarm status

The current alarm branch includes:

- multiple persistent alarms;
- local timezone and DST handling;
- reboot recovery and duplicate-occurrence protection;
- full-screen takeover;
- Snooze and slide-to-dismiss;
- synthesised local tones;
- controlled shared-mixer audio tests.

Ordinary scheduled alarm playback remains locked until the controlled test path is fully proven.

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

## Navigation drawer

A small handle remains at the bottom of each dashboard page:

- tap or swipe up to reveal navigation;
- choose Clock, Weather, Plexamp, AirPlay or Settings;
- press **Audio** for the live player-aware mixer;
- the ordinary drawer auto-hides quickly, while the live mixer remains open longer for adjustment.

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

## NFC integration

Install and run [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener) alongside this project. A successful scan triggers Plexamp playback and calls `scripts/display-mode.sh plexamp` so the dashboard follows the new music.

## Testing

Run the complete test suite:

```bash
bash scripts/run-tests.sh
```

GitHub Actions checks Python compilation, JavaScript and shell syntax, alarm scheduling/runtime behaviour, 44.1 kHz stereo tone rendering, shared-mixer safety, perceptual volume conversion and Plexamp player-volume control.

Further details are in [`docs/testing.md`](docs/testing.md).
