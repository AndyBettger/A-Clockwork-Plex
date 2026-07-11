# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, local weather, clock display and future alarms — hopefully with no toast-related incidents.

This project is the dashboard/appliance layer for [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The NFC listener reads album tags and triggers Plexamp playback; A Clockwork Plex provides the 7-inch touchscreen interface around it.

## Current feature set

| Area | Status |
|---|---|
| **Clock** | Large segmented digital clock, date, and compact live-updating weather cards. |
| **Weather** | Detailed Ecowitt weather dashboard with conditions, wind compass, pressure/barometer, dynamic rain gauges, station status and auto-refresh. |
| **Plexamp** | Plexamp Headless embedded inside the dashboard using an iframe shell. |
| **Navigation** | Hidden bottom nav drawer with a small touchscreen handle; tap or swipe up to show it. |
| **NFC handoff** | NFC scans can switch the display to the embedded Plexamp page while playback starts. |
| **AirPlay** | Shairport Sync wrapper hooks mark real AirPlay sessions active/idle, pause/stop Plexamp while AirPlay owns the DAC, then restart Plexamp and return to Clock. |
| **Settings** | Touchscreen settings page for weather names, units, ordered clock weather cards, dashboard behaviour, Plexamp/AirPlay values and alarm placeholders. |
| **Mode watcher** | Pages poll `/api/status` and move themselves when an external mode change happens, so kiosk setups do not require `xdotool`. |

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Default idle screen with time, date and compact weather station data. |
| **Weather** | `/weather` | Detailed weather station page. |
| **Plexamp** | `/plexamp` | Dashboard-hosted Plexamp iframe with the hidden nav handle. |
| **AirPlay** | `/airplay` | AirPlay ready/active handoff and status screen. |
| **Settings** | `/settings` | Touchscreen configuration page. |

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
│       └── js/
├── scripts/
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

## Quick start

Clone the repository on the Raspberry Pi:

```bash
git clone https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copy the example config:

```bash
cp config.example.json config.json
```

Run manually:

```bash
source venv/bin/activate
python app/main.py
```

Open on the Pi:

```text
http://localhost:8088
```

## Running as a service

Install the systemd service template:

```bash
cd ~/A-Clockwork-Plex
sudo cp systemd/a-clockwork-plex.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now a-clockwork-plex.service
systemctl status a-clockwork-plex.service --no-pager
```

After pulling updates:

```bash
cd ~/A-Clockwork-Plex
git pull
python -m py_compile app/main.py
chmod +x scripts/*.sh
sudo systemctl restart a-clockwork-plex.service
```

## Kiosk browser

Point Chromium kiosk mode at the dashboard, not directly at Plexamp:

```text
http://localhost:8088/clock
```

For current Raspberry Pi OS / labwc setups, that is usually in:

```text
~/.config/labwc/autostart
```

A typical entry is:

```bash
sleep 10
chromium --kiosk --start-maximized --noerrdialogs --disable-infobars --no-first-run "http://localhost:8088/clock" &
```

## Navigation drawer

The main navigation is hidden by default to maximise screen space. A small handle remains at the bottom of the screen.

- Tap the handle to show/hide navigation.
- Swipe up from the handle to show navigation.
- Navigation auto-hides after a few seconds.
- This remains available over the embedded Plexamp page, giving a touchscreen route back to Clock, Weather and Settings.

## Weather station setup

A Clockwork Plex includes an Ecowitt/custom upload receiver at:

```text
/api/weather/ecowitt
```

Typical Ecowitt custom upload settings:

| Setting | Value |
|---|---|
| Protocol | Ecowitt |
| Server IP / Hostname | Raspberry Pi IP address |
| Port | `8088` |
| Path | `/api/weather/ecowitt` |
| Upload interval | `60` seconds |

The app stores the most recent weather payload, daily min/max values for indoor/outdoor temperature and humidity, and 24 hours of pressure history for the barometer estimate.

Sensitive weather keys such as `passkey`, `password`, `secret`, `token`, `api_key` and `apikey` are not stored from new uploads and are redacted from status output if present in older state.

## Weather page features

The detailed weather page currently includes:

- Main conditions table for indoor/outdoor temperature and humidity.
- Daily low/high tracking for those readings.
- Shipping Forecast-inspired issued text.
- Wind compass and speed/gust readings.
- Pressure/barometer panel with relative and absolute pressure, a prominent barometer forecast and a simple forecast graphic.
- Dynamic rain gauges that scale automatically.
- Station status table.
- Auto-refresh, configurable from Settings.

Pressure trend behaviour:

```text
0-30 minutes  → gathering history
30+ minutes   → early trend estimate
3+ hours      → better barometer-style estimate
24 hours      → retained pressure history window
```

## Settings page

The Settings screen writes to `config.json`. It currently supports:

- Weather page title.
- Reporting station name.
- Weather auto-refresh seconds.
- Weather units: temperature, pressure, rain and wind.
- Ordered clock page weather cards, including optional barometer forecast card.
- Default dashboard mode.
- Idle timeout placeholder.
- Day/night dimming time placeholders.
- Plexamp URL, pause URL and service name.
- AirPlay display name.
- Alarm placeholder values.

Some settings are stored before the corresponding runtime feature exists. This keeps the UI and config shape ready for later alarm/dimming work.

## Plexamp iframe mode

`/plexamp` now renders Plexamp Headless inside A Clockwork Plex instead of redirecting the browser directly to port `32500`.

This means:

- The hidden nav handle remains available.
- Kiosk mode can stay locked to the dashboard.
- NFC-triggered albums can switch the display to Plexamp without needing a keyboard or mouse.

The Plexamp URL is configured in `config.json`:

```json
"plexamp": {
  "url": "http://localhost:32500",
  "pause_url": "http://localhost:32500/player/playback/pause",
  "service_name": "plexamp.service"
}
```

## NFC integration

Install and run [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener) alongside this project.

When updated, the NFC listener does this after a successful album tag scan:

```text
Read NFC tag
  ↓
Trigger Plexamp Headless playback
  ↓
Call A Clockwork Plex mode/display switch helper
  ↓
Dashboard moves to /plexamp
```

The helper script in this repo is:

```text
scripts/nfc-plexamp-mode.sh
```

It calls:

```text
scripts/display-mode.sh plexamp
```

The dashboard also includes a browser-side mode watcher, so even if `xdotool` is not installed, pages can still navigate themselves when `/api/mode/plexamp` is set.

## Shairport Sync / AirPlay integration

The working AirPlay handoff path uses small wrapper scripts in `/usr/local/bin`, rather than pointing Shairport Sync directly at scripts inside `/home`. This avoids permission and systemd sandboxing issues where Shairport can see the hook command but cannot execute files under a user's home directory.

The wrappers do this when AirPlay starts:

```text
Call /api/airplay/start to mark the real AirPlay session active
Switch dashboard to /airplay
Pause Plexamp
Stop plexamp.service so Shairport can own the DAC
```

When AirPlay ends, they do this:

```text
Start plexamp.service
Wait briefly
Call /api/airplay/end to mark the AirPlay session idle
Switch dashboard back to /clock
```

Install or refresh the wrapper hooks:

```bash
cd ~/A-Clockwork-Plex
git pull
chmod +x scripts/*.sh
./scripts/install-airplay-hooks.sh
```

The installer creates:

```text
/usr/local/bin/a-clockwork-plex-airplay-start
/usr/local/bin/a-clockwork-plex-airplay-end
/etc/sudoers.d/a-clockwork-plex-airplay
```

The sudoers rule allows the `shairport-sync` service user to run only these commands without a password:

```text
/usr/bin/systemctl stop plexamp.service
/usr/bin/systemctl start plexamp.service
```

Use this in `/etc/shairport-sync.conf`:

```conf
sessioncontrol =
{
    run_this_before_entering_active_state = "/usr/local/bin/a-clockwork-plex-airplay-start";
    run_this_after_exiting_active_state = "/usr/local/bin/a-clockwork-plex-airplay-end";
    active_state_timeout = 10;
    wait_for_completion = "yes";
};
```

Remove older hook entries such as:

```conf
run_this_before_play_begins = "/usr/local/bin/plexamp-airplay-start";
run_this_after_play_ends = "/usr/local/bin/plexamp-airplay-stop";
```

Validate and restart Shairport Sync:

```bash
shairport-sync -t
sudo systemctl restart shairport-sync
```

Watch the handoff logs:

```bash
journalctl -u shairport-sync -f
```

and in another terminal:

```bash
journalctl -t shairport-plexamp -f
```

Expected helper log sequence:

```text
AirPlay starting - switching display to AirPlay
AirPlay starting - pausing Plexamp playback
AirPlay starting - stopping Plexamp service
Plexamp service stopped - DAC should be free
AirPlay ended - starting Plexamp service
Plexamp service start requested
AirPlay ended - switching display to clock
```

Optional installer overrides:

```bash
DASHBOARD_BASE="http://localhost:8088" \
PLEXAMP_URL="http://localhost:32500" \
PLEXAMP_SERVICE="plexamp.service" \
SHAIRPORT_USER="shairport-sync" \
./scripts/install-airplay-hooks.sh
```

## Useful endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Redirects to clock mode. |
| `/clock` | Clock/weather screen. |
| `/weather` | Detailed weather station screen. |
| `/plexamp` | Embedded Plexamp shell. |
| `/airplay` | AirPlay ready/active screen. |
| `/settings` | Touchscreen settings page. |
| `/api/status` | Current mode, real AirPlay session state, config diagnostics and redacted/latest weather data. |
| `/api/mode/clock` | Set display mode to clock. |
| `/api/mode/weather` | Set display mode to detailed weather. |
| `/api/mode/plexamp` | Set display mode to Plexamp. |
| `/api/mode/airplay` | Set display mode to AirPlay without marking a real AirPlay session active. |
| `/api/airplay/start` | Mark AirPlay active and switch display mode to AirPlay. |
| `/api/airplay/end` | Mark AirPlay idle and switch display mode to Clock. |
| `/api/weather/ecowitt` | Receiver endpoint for Ecowitt/custom weather uploads. |

## Troubleshooting

Check service logs:

```bash
journalctl -u a-clockwork-plex.service -f
```

Check current status:

```bash
curl -s http://localhost:8088/api/status | python -m json.tool
```

Validate JSON config:

```bash
python -m json.tool config.json >/dev/null && echo "config.json is valid"
```

Make helper scripts executable:

```bash
chmod +x scripts/*.sh
```

## Licence

This project is licensed under the [MIT License](LICENSE).
