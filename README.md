# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, local weather, clock display and future alarms — hopefully with no toast-related incidents.

This project is the dashboard/appliance layer for [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The NFC listener reads album tags and triggers Plexamp playback; A Clockwork Plex provides the touchscreen interface around it.

## Current feature set

| Area | Status |
|---|---|
| **Clock** | Large custom segmented SVG clock, uppercase segmented date, clock-format setting, and compact live-updating weather cards. |
| **Weather** | Detailed Ecowitt weather dashboard with conditions, wind compass, pressure/barometer, dynamic rain gauges, station status and auto-refresh. |
| **Plexamp** | Plexamp Headless embedded inside the dashboard using an iframe shell, keeping the dashboard nav handle available. |
| **Navigation** | Hidden bottom nav drawer with a small touchscreen handle; tap or swipe up to show it. |
| **NFC handoff** | NFC scans can switch the display to the embedded Plexamp page while playback starts. |
| **AirPlay handoff** | Shairport Sync hooks pause/stop Plexamp while AirPlay owns the DAC, then restart Plexamp and return to Clock when the AirPlay session ends. |
| **AirPlay Now Playing** | Artwork, title/artist/album/source metadata, progress, volume, play/pause, previous/next, and spoken-audio 15-second skip button visuals. |
| **AirPlay pause hold** | Pausing from the Pi screen keeps the AirPlay Now Playing screen alive for resume, with a watchdog timeout to avoid stale sessions. |
| **Settings** | Touchscreen settings page for weather names, units, ordered clock weather cards, dashboard behaviour, Plexamp/AirPlay values and alarm placeholders. |
| **Mode watcher** | Pages poll `/api/status` and move themselves when an external mode change happens, so kiosk setups do not require `xdotool`. |

## Screen modes

| Mode | URL | Purpose |
|---|---|---|
| **Clock** | `/clock` | Default idle screen with the large segmented clock/date and compact weather station data. |
| **Weather** | `/weather` | Detailed weather station page. |
| **Plexamp** | `/plexamp` | Dashboard-hosted Plexamp iframe with the hidden nav handle. |
| **AirPlay** | `/airplay` | AirPlay ready/active handoff and Now Playing screen. |
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

After pulling dashboard updates:

```bash
cd ~/A-Clockwork-Plex
git pull --rebase --autostash
python3 -m py_compile app/main.py
chmod +x scripts/*.sh
sudo systemctl restart a-clockwork-plex.service
```

If a change affects the installed Shairport wrappers, also run:

```bash
sudo scripts/install-airplay-hooks.sh
sudo systemctl restart shairport-sync.service
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

## Clock page

The Clock page is the idle/default display.

Current behaviour:

- Large custom segmented SVG time display.
- Uppercase segmented date display.
- 12/24-hour mode from Settings/local storage.
- Compact weather card panel below the clock.
- Live weather card refresh without a full page reload.
- Configurable clock weather card order from Settings.

The date is rendered manually as uppercase text, for example:

```text
MONDAY 13 JULY 2026
```

That avoids browser locale punctuation producing invisible/unsupported characters in the segmented display.

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
- Clock format: 12-hour or 24-hour.
- Default dashboard mode.
- Idle timeout placeholder.
- Day/night dimming time placeholders.
- Plexamp URL, pause URL and service name.
- AirPlay display name.
- Alarm placeholder values.

Some settings are stored before the corresponding runtime feature exists. This keeps the UI and config shape ready for later alarm/dimming work.

## Plexamp iframe mode

`/plexamp` renders Plexamp Headless inside A Clockwork Plex instead of redirecting the browser directly to port `32500`.

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

The working AirPlay handoff path uses wrapper scripts in `/usr/local/bin`, rather than pointing Shairport Sync directly at scripts inside `/home`. This avoids permission and systemd sandboxing issues where Shairport can see the hook command but cannot execute files under a user's home directory.

Install or refresh the wrapper hooks:

```bash
cd ~/A-Clockwork-Plex
git pull --rebase --autostash
chmod +x scripts/*.sh
sudo scripts/install-airplay-hooks.sh
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

Restart Shairport Sync:

```bash
sudo systemctl restart shairport-sync.service
sudo systemctl status shairport-sync.service --no-pager
```

Note: some Shairport Sync builds use `-t` as a runtime timeout option rather than a config-test flag. Running `shairport-sync -t 0` while the service is already active can fail with a port 5000 conflict. For normal dashboard updates, restarting the service and checking `systemctl status` is the safer test.

Watch the handoff logs:

```bash
journalctl -u shairport-sync -f
```

and in another terminal:

```bash
journalctl -t shairport-plexamp -f
```

Expected helper log sequence for a normal AirPlay start/end:

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
sudo ./scripts/install-airplay-hooks.sh
```

## AirPlay Now Playing

The `/airplay` screen has two states:

- **Idle/ready:** displays a large AirPlay-style artwork panel and connection prompt.
- **Active/Now Playing:** displays source artwork, title, artist, album/source line, progress, volume and transport controls.

Current controls:

| Control | Behaviour |
|---|---|
| Play/pause | Calls Shairport/MPRIS `PlayPause` for the current AirPlay source. |
| Previous/next | Calls Shairport/MPRIS `Previous` and `Next`. |
| Volume | Calls Shairport/MPRIS volume control and shows dB-style labels. |
| Spoken-audio mode | Automatically swaps previous/next icons to 15-second rewind/forward visuals when metadata looks like podcasts/audiobooks. |

The app deliberately keeps the underlying previous/next commands for the side buttons. Apps such as Prologue and Apple Podcasts interpret those as short seek controls, while music apps such as Plexamp and Apple Music interpret them as track skip controls.

Spoken-audio detection uses metadata clues such as app/source names, genre/format text, chapter/episode wording, and long duration where the source is not clearly a music app.

## AirPlay metadata listener

`scripts/airplay-metadata-listener.py` reads Shairport Sync metadata from:

```text
/tmp/shairport-sync-metadata
```

It decodes useful metadata into `state.json`, including:

- title, artist, album and genre
- source/player information when present
- playback/session events
- progress samples
- artwork payloads saved under `app/static/generated/`

This is how the AirPlay Now Playing screen gets its artwork and metadata without scraping generic web/image sources.

## AirPlay pause-hold behaviour

The AirPlay end hook includes a dashboard pause-hold path so a pause from the Pi screen does not immediately hand the dashboard back to Clock.

Current behaviour:

| Action | Expected result |
|---|---|
| Pause from Pi screen | Stay on AirPlay Now Playing/paused screen. |
| Resume from Pi screen | Resume AirPlay playback. |
| Resume from iPhone | Return/update to live Now Playing state. |
| Pause from iPhone | Treat as normal AirPlay idle/end and return to Clock. |
| Disconnect before hold is accepted | Return to Clock. |
| Leave Pi-paused AirPlay idle too long | Watchdog returns to Clock after the configured timeout. |

Default watchdog timeout:

```text
600 seconds / 10 minutes
```

The end hook logs useful state under the `shairport-plexamp` journal tag, for example:

```text
AirPlay ended after dashboard pause - staying on AirPlay screen (...)
AirPlay dashboard pause watchdog armed for 600s
AirPlay dashboard pause watchdog exiting because playback resumed
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
| `/api/airplay/control` | Send AirPlay transport commands such as play/pause, previous, next and volume-backed control actions. |
| `/api/weather/ecowitt` | Receiver endpoint for Ecowitt/custom weather uploads. |

## Design notes and credits

- The custom segmented clock/date display uses SVG segment geometry from `docs/airplay-segment-cell.svg`.
- The AirPlay spoken-audio `15` skip icons use SVG paths from Wikimedia Commons:
  - `VK_icons_replay_15_36.svg`
  - `VK_icons_forward_15_28.svg`
- The UI is tuned primarily for Raspberry Pi touchscreen/kiosk use, including the official 7-inch display and similar landscape dashboard layouts.

## Troubleshooting

Check dashboard service logs:

```bash
journalctl -u a-clockwork-plex.service -f
```

Check Shairport handoff logs:

```bash
journalctl -t shairport-plexamp -f
```

Check current dashboard status:

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

Refresh AirPlay hooks after script changes:

```bash
cd ~/A-Clockwork-Plex
sudo scripts/install-airplay-hooks.sh
sudo systemctl restart shairport-sync.service
```

## Licence

This project is licensed under the [MIT License](LICENSE).
