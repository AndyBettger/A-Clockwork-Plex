# A Clockwork Plex

A Raspberry Pi touchscreen dashboard for Plexamp Headless, NFC-triggered albums, AirPlay handoff, clock/weather display, and eventually alarms — hopefully with no toast-related incidents.

This project is intended as the next step beyond [`Plexamp-NFC-Listener`](https://github.com/AndyBettger/Plexamp-NFC-Listener). The original listener remains a focused NFC-to-Plexamp tool; this repository adds the touchscreen/dashboard layer around it.

## Planned screen modes

| Mode | Purpose |
|---|---|
| **Clock** | Default idle screen with time, date and compact weather station data. |
| **Weather** | Detailed weather station page with conditions, wind, rain, pressure and station status. |
| **Plexamp** | Normal Plexamp Headless UI for albums, NFC playback and touchscreen control. |
| **AirPlay** | Simple AirPlay active screen for podcast playback from an iPhone. |
| **Settings** | Future touchscreen settings for units, visible weather cards, idle timeout, day/night times and alarms. |

## Current first version

This first version provides a small local Flask dashboard with:

- a clock/weather idle page
- a detailed weather station page
- an AirPlay active page
- a settings placeholder
- simple mode/state API endpoints
- an Ecowitt/custom weather upload receiver endpoint
- helper scripts for Shairport Sync and NFC handoff
- a systemd service template

It deliberately starts simple. The first goal is to prove screen switching and mode control before adding richer weather, metadata or alarm features.

## Repository layout

```text
A-Clockwork-Plex/
├── app/
│   ├── main.py
│   ├── templates/
│   └── static/
├── scripts/
│   ├── display-mode.sh
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

Run the dashboard manually:

```bash
source venv/bin/activate
python app/main.py
```

Open on the Pi:

```text
http://localhost:8088
```

## Useful endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Main dashboard, defaults to clock mode. |
| `/clock` | Clock/weather screen. |
| `/weather` | Detailed weather station screen. |
| `/airplay` | AirPlay active screen. |
| `/settings` | Settings placeholder. |
| `/api/status` | Current mode, config diagnostics and redacted/latest weather data. |
| `/api/mode/clock` | Set mode to clock. |
| `/api/mode/weather` | Set mode to detailed weather. |
| `/api/mode/airplay` | Set mode to AirPlay. |
| `/api/mode/plexamp` | Set mode to Plexamp. |
| `/api/weather/ecowitt` | Receiver endpoint for Ecowitt/custom weather uploads. |

## Shairport Sync integration

The current office Pi AirPlay handoff works by stopping Plexamp while AirPlay owns the DAC, then starting Plexamp again after AirPlay ends.

The helper scripts in `scripts/` are intended to be adapted into Shairport Sync hooks:

```conf
sessioncontrol =
{
    run_this_before_entering_active_state = "/home/andy/A-Clockwork-Plex/scripts/shairport-airplay-start.sh";
    run_this_after_exiting_active_state = "/home/andy/A-Clockwork-Plex/scripts/shairport-airplay-end.sh";
    active_state_timeout = 10;
    wait_for_completion = "yes";
};
```

The start script switches the dashboard to AirPlay mode, pauses Plexamp, then stops `plexamp.service` so Shairport can use the DAC. The end script restarts Plexamp and returns the display to clock mode.
