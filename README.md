# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, local Ecowitt weather, a bedside clock and future alarm features — hopefully with no toast-related incidents.

A Clockwork Plex is the dashboard/appliance layer for [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The NFC listener reads album tags and starts Plexamp playback; this project provides the touchscreen interface around it.

## Current status

The Clock, Weather, embedded Plexamp, AirPlay Ready/Now Playing, navigation and Settings screens are working on Raspberry Pi touchscreen hardware. Alarm playback, idle return and automatic day/night dimming are represented in Settings but remain future work.

| Area | Current behaviour |
|---|---|
| **Clock** | Large custom fourteen-segment SVG clock and date, 12/24-hour format, balanced punctuation and live weather cards. |
| **Clock weather cards** | Touch-configurable ordering with compact combined cards for indoor/outdoor temperature, indoor/outdoor humidity, wind speed/gust, rain today/event rain and solar/UV. |
| **Weather** | Detailed Ecowitt console with conditions, daily low/high values, 16-point wind direction, pressure/barometer forecast, rain gauges, station status and auto-refresh. |
| **Plexamp** | Plexamp Headless embedded in a dashboard iframe so the touchscreen navigation handle remains available. |
| **NFC handoff** | A successful NFC album scan can start Plexamp and switch the dashboard to the embedded Plexamp screen. |
| **AirPlay handoff** | Shairport Sync hooks pause/stop Plexamp while AirPlay owns the DAC, then restart Plexamp and return to Clock when the session ends. |
| **AirPlay Ready/Now Playing** | Receiver-ready page plus artwork, metadata, progress, volume, transport controls and a glance row containing time/date, outdoor temperature/humidity and barometer status. |
| **AirPlay pause hold** | Pausing from the Pi screen keeps Now Playing available for resume, with a watchdog to prevent stale sessions. |
| **Settings** | Touchscreen controls for weather names/units/cards, dashboard behaviour, Plexamp/AirPlay values and alarm placeholders. |
| **Navigation and mode watcher** | Hidden bottom drawer plus browser-side mode polling, so kiosk mode does not depend on `xdotool`. |

## Visual system

The current interface uses a shared instrument-console design across Clock, Weather and AirPlay:

- reusable SVG fourteen-segment digits and letters;
- Oxanium for display headings and Atkinson Hyperlegible for general UI text;
- DejaVu/Arial fallbacks when the web fonts are unavailable;
- common segment sizing, unit alignment, decimal and colon spacing;
- illuminated Weather panels, compass, pressure console and dynamic rain gauges;
- production styles split by purpose:
  - `app/static/css/typography.css`
  - `app/static/css/clock-dashboard.css`
  - `app/static/css/weather-console.css`
  - `app/static/css/airplay-glance-tuning.css`

The editable segment geometry lives in `docs/airplay-segment-cell.svg`; the shared renderer is in `app/static/js/segment-display.js`.

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Default idle screen with the segmented clock/date and compact weather cards. |
| **Weather** | `/weather` | Detailed weather-station console. |
| **Plexamp** | `/plexamp` | Dashboard-hosted Plexamp iframe with the navigation handle. |
| **AirPlay** | `/airplay` | AirPlay Ready, paused and Now Playing states. |
| **Settings** | `/settings` | Touchscreen configuration page. |

## How the pieces fit together

```text
NFC tag
  └─> Plexamp-NFC-Listener
        ├─> Plexamp Headless playback on localhost:32500
        └─> A Clockwork Plex mode switch to /plexamp

Ecowitt custom upload
  └─> /api/weather/ecowitt
        └─> Clock and detailed Weather screens

AirPlay session
  └─> Shairport Sync hooks
        ├─> pause/stop Plexamp and release the DAC
        ├─> switch dashboard to /airplay
        ├─> publish artwork/metadata/progress
        └─> restart Plexamp and return to /clock when finished
```

## Repository layout

```text
A-Clockwork-Plex/
├── app/
│   ├── main.py
│   ├── templates/
│   │   ├── clock.html
│   │   ├── weather.html
│   │   ├── plexamp.html
│   │   ├── airplay.html
│   │   ├── settings.html
│   │   ├── base.html
│   │   └── _nav.html
│   └── static/
│       ├── css/
│       ├── generated/
│       └── js/
├── docs/
│   └── airplay-segment-cell.svg
├── scripts/
│   ├── airplay-metadata-listener.py
│   ├── display-mode.sh
│   ├── install-airplay-hooks.sh
│   ├── shairport-airplay-start.sh
│   ├── shairport-airplay-end.sh
│   └── nfc-plexamp-mode.sh
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
- an Ecowitt-compatible weather station when weather data is required;
- `Plexamp-NFC-Listener` and a supported NFC reader for tag-triggered playback.

The Flask service listens on port `8088` by default. It is intended as a trusted-LAN appliance; do not expose its control endpoints directly to the public internet without adding suitable authentication and a secure reverse proxy.

## Quick start

Clone the repository:

```bash
git clone https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy the example configuration:

```bash
cp config.example.json config.json
```

Review `config.json`, especially the dashboard port, Plexamp service/URLs, AirPlay display name, weather station names and unit choices.

Run manually:

```bash
source venv/bin/activate
python app/main.py
```

Open:

```text
http://localhost:8088
```

## Running as a service

Install the supplied systemd unit:

```bash
cd ~/A-Clockwork-Plex
sudo cp systemd/a-clockwork-plex.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now a-clockwork-plex.service
systemctl status a-clockwork-plex.service --no-pager
```

### Updating an existing installation

For a clean checkout tracking `main`:

```bash
cd ~/A-Clockwork-Plex
git switch main
git pull --ff-only
python3 -m py_compile app/main.py
chmod +x scripts/*.sh
sudo systemctl restart a-clockwork-plex.service
```

After CSS or JavaScript changes, hard-refresh Chromium once with `Ctrl+Shift+R`.

When an update changes the installed Shairport wrapper scripts, also run:

```bash
cd ~/A-Clockwork-Plex
sudo scripts/install-airplay-hooks.sh
sudo systemctl restart shairport-sync.service
```

## Kiosk browser

Point Chromium at the dashboard rather than directly at Plexamp:

```text
http://localhost:8088/clock
```

On current Raspberry Pi OS/labwc installations the kiosk command is commonly placed in:

```text
~/.config/labwc/autostart
```

Example:

```bash
sleep 10
chromium --kiosk --start-maximized --noerrdialogs --disable-infobars --no-first-run "http://localhost:8088/clock" &
```

## Navigation drawer

The navigation is hidden by default to maximise display space. A small handle remains at the bottom:

- tap the handle to show or hide navigation;
- swipe up from the handle to reveal it;
- the drawer auto-hides after a short delay;
- it remains available over the embedded Plexamp screen.

## Clock page

The Clock page is the default bedside display.

Current behaviour:

- large segmented hours, minutes and seconds;
- uppercase segmented weekday/date;
- 12-hour or 24-hour mode from Settings/local storage;
- live weather updates without reloading the page;
- four cards per row at the primary touchscreen layout;
- shared segment sizing and baseline-aligned units;
- configurable card selection and ordering.

Related readings are represented as combined Settings choices while still being stored as the underlying weather IDs in `config.json`:

- indoor and outdoor temperature;
- indoor and outdoor humidity;
- wind speed and gust;
- rain today and event rain;
- solar and UV.

The date is rendered manually, for example:

```text
MONDAY 13 JULY 2026
```

This avoids browser locale punctuation introducing characters unsupported by the segmented display.

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

The app stores the latest payload, daily indoor/outdoor temperature and humidity minima/maxima, and a rolling 24-hour pressure history.

Sensitive keys including `passkey`, `password`, `secret`, `token`, `api_key` and `apikey` are omitted from new stored uploads and redacted from status output when found in older state.

## Detailed Weather page

The Weather screen currently includes:

- indoor/outdoor temperature and humidity with daily lows and highs;
- solar radiation, UV and VPD readings;
- Shipping Forecast-inspired issued text;
- large compass rose with numeric bearing and a full 16-point direction name;
- aligned, zero-padded wind speed/gust readings and maximum gust;
- relative and absolute pressure cards;
- a compact barometer forecast with trend and explanatory text;
- automatically scaling rain gauges for current, hourly, event, weekly, monthly, yearly and total rain;
- station model, frequency, upload interval, timestamp and battery status;
- configurable automatic page refresh.

Pressure trend behaviour:

```text
0-30 minutes  -> gathering history
30+ minutes   -> early trend estimate
3+ hours      -> stronger barometer-style estimate
24 hours      -> retained pressure-history window
```

The forecast wording is dynamic, so Clock and AirPlay show the compact status while the detailed Weather page shows the status, trend and explanation.

## Settings page

Settings are written to `config.json`. Current controls include:

- Weather page title and reporting station name;
- automatic Weather-page refresh interval;
- metric/imperial-style temperature, pressure, rain and wind units;
- Clock weather-card selection and order;
- Clock format;
- default dashboard mode;
- idle timeout placeholder;
- day/night dimming time placeholders;
- Plexamp URL, pause URL and service name;
- AirPlay display name;
- alarm enabled/time/snooze placeholders.

Alarm playback, automatic idle return and scheduled display dimming are not yet implemented.

## Plexamp iframe mode

`/plexamp` embeds Plexamp Headless rather than sending Chromium directly to port `32500`.

This allows:

- the dashboard navigation handle to remain available;
- kiosk mode to stay locked to A Clockwork Plex;
- NFC scans to move the display to Plexamp without a keyboard or mouse.

Example configuration:

```json
"plexamp": {
  "url": "http://localhost:32500",
  "pause_url": "http://localhost:32500/player/playback/pause",
  "service_name": "plexamp.service"
}
```

## NFC integration

Install and run [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener) alongside this project.

After a successful scan:

```text
Read NFC tag
  -> trigger Plexamp Headless playback
  -> call A Clockwork Plex display helper
  -> dashboard moves to /plexamp
```

The helper is:

```text
scripts/nfc-plexamp-mode.sh
```

It calls:

```text
scripts/display-mode.sh plexamp
```

The browser-side mode watcher follows the API mode change even when `xdotool` is unavailable.

## Shairport Sync / AirPlay integration

The working handoff uses wrapper commands installed under `/usr/local/bin`. This avoids Shairport Sync/systemd permission and sandboxing problems that can occur when service hooks point directly into a user's home directory.

Install or refresh the wrappers:

```bash
cd ~/A-Clockwork-Plex
chmod +x scripts/*.sh
sudo scripts/install-airplay-hooks.sh
```

The installer creates:

```text
/usr/local/bin/a-clockwork-plex-airplay-start
/usr/local/bin/a-clockwork-plex-airplay-end
/etc/sudoers.d/a-clockwork-plex-airplay
```

The restricted sudoers entry permits the `shairport-sync` service user to run only the required Plexamp service start/stop commands.

Use the wrappers in `/etc/shairport-sync.conf`:

```conf
sessioncontrol =
{
    run_this_before_entering_active_state = "/usr/local/bin/a-clockwork-plex-airplay-start";
    run_this_after_exiting_active_state = "/usr/local/bin/a-clockwork-plex-airplay-end";
    active_state_timeout = 10;
    wait_for_completion = "yes";
};
```

Remove obsolete hook entries such as:

```conf
run_this_before_play_begins = "/usr/local/bin/plexamp-airplay-start";
run_this_after_play_ends = "/usr/local/bin/plexamp-airplay-stop";
```

Restart and inspect the service:

```bash
sudo systemctl restart shairport-sync.service
sudo systemctl status shairport-sync.service --no-pager
```

Some Shairport Sync builds use `-t` as a runtime timeout rather than a config-test option. Running `shairport-sync -t 0` while the service is active can therefore fail with a port `5000` conflict; restarting the service and checking its status is the safer test.

Useful logs:

```bash
journalctl -u shairport-sync -f
journalctl -t shairport-plexamp -f
```

Optional installer overrides:

```bash
DASHBOARD_BASE="http://localhost:8088" \
PLEXAMP_URL="http://localhost:32500" \
PLEXAMP_SERVICE="plexamp.service" \
SHAIRPORT_USER="shairport-sync" \
sudo ./scripts/install-airplay-hooks.sh
```

## AirPlay Ready and Now Playing

The `/airplay` screen has two principal live layouts:

- **Ready:** large AirPlay route graphic, the configured receiver name and connection instructions.
- **Now Playing:** artwork, title, artist/source, album/episode details, progress, volume and transport controls.

The receiver title shown on the Ready page removes a trailing `Plexamp` from the configured Shairport display name. For example, `Bedroom Plexamp` is presented as `Bedroom`, while the connection instructions remain tied to that receiver.

The lower glance row is shared by both states:

- segmented current time and date;
- segmented outdoor temperature and humidity;
- compact barometer forecast word.

Current controls:

| Control | Behaviour |
|---|---|
| Play/pause | Calls Shairport/MPRIS `PlayPause`. |
| Previous/next | Calls Shairport/MPRIS `Previous` and `Next`. |
| Volume | Calls Shairport/MPRIS volume control and shows dB-style labels. |
| Spoken-audio display | Changes the side-button artwork to 15-second rewind/forward when metadata resembles a podcast or audiobook. |

The commands behind the side buttons remain previous/next. Apps such as Prologue and Apple Podcasts commonly interpret them as short seek controls, while music apps interpret them as track changes.

## AirPlay metadata listener

`scripts/airplay-metadata-listener.py` reads Shairport Sync metadata from:

```text
/tmp/shairport-sync-metadata
```

It writes useful session data to `state.json`, including:

- title, artist, album and genre;
- source/player information when available;
- playback/session events;
- progress samples;
- artwork saved under `app/static/generated/`.

## AirPlay pause-hold behaviour

Pausing from the Pi screen does not immediately return the dashboard to Clock.

| Action | Expected result |
|---|---|
| Pause from Pi screen | Remain on the paused AirPlay screen. |
| Resume from Pi screen | Resume AirPlay playback. |
| Resume from iPhone | Return/update to live Now Playing. |
| Pause from iPhone | Treat as normal AirPlay idle/end and return to Clock. |
| Disconnect before hold is accepted | Return to Clock. |
| Leave the held session idle too long | Watchdog returns to Clock. |

Default watchdog timeout:

```text
600 seconds / 10 minutes
```

## Useful endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Redirect to Clock. |
| `/clock` | Clock and compact weather screen. |
| `/weather` | Detailed weather console. |
| `/plexamp` | Embedded Plexamp shell. |
| `/airplay` | AirPlay Ready/Now Playing screen. |
| `/settings` | Touchscreen Settings. |
| `/api/status` | Mode, AirPlay state, config diagnostics and redacted/latest weather data. |
| `/api/mode/clock` | Set Clock mode. |
| `/api/mode/weather` | Set Weather mode. |
| `/api/mode/plexamp` | Set Plexamp mode. |
| `/api/mode/airplay` | Display AirPlay without marking a real session active. |
| `/api/airplay/start` | Mark AirPlay active and switch to AirPlay. |
| `/api/airplay/end` | Mark AirPlay idle and switch to Clock. |
| `/api/airplay/control` | Send transport/volume actions. |
| `/api/weather/ecowitt` | Receive Ecowitt/custom weather uploads. |

## Roadmap

Likely future chapters include:

- real alarm scheduling and playback;
- snooze/dismiss controls;
- automatic return-to-Clock after inactivity;
- scheduled day/night brightness or dimming behaviour;
- optional local font packaging for fully offline typography;
- broader setup/installation automation.

## Troubleshooting

Dashboard logs:

```bash
journalctl -u a-clockwork-plex.service -f
```

Shairport handoff logs:

```bash
journalctl -t shairport-plexamp -f
```

Current dashboard status:

```bash
curl -s http://localhost:8088/api/status | python -m json.tool
```

Validate `config.json`:

```bash
python -m json.tool config.json >/dev/null && echo "config.json is valid"
```

Check the service:

```bash
systemctl status a-clockwork-plex.service --no-pager
```

Refresh helper permissions and AirPlay wrappers:

```bash
cd ~/A-Clockwork-Plex
chmod +x scripts/*.sh
sudo scripts/install-airplay-hooks.sh
sudo systemctl restart shairport-sync.service
```

## Design credits

- Custom clock/date/weather characters use the SVG segment geometry in `docs/airplay-segment-cell.svg`.
- AirPlay spoken-audio `15` icons use SVG paths derived from Wikimedia Commons:
  - `VK_icons_replay_15_36.svg`
  - `VK_icons_forward_15_28.svg`
- The UI is primarily tuned for Raspberry Pi landscape touchscreen/kiosk layouts, including the official 7-inch display and similar panels.

## Licence

This project is licensed under the [MIT License](LICENSE).
