# Unified iPad-style Settings

## Status

Weather was the final major subsystem and has been physically validated on the
bedroom Raspberry Pi. The post-weather Settings consolidation is now implemented
on `feature/alarm-engine` and is awaiting focused 1024×600 physical validation.

This pass is a substantial interface and ownership cleanup rather than another
appliance subsystem.

## Layout

Settings now uses an **iPad-style split view**:

```text
┌──────────────────┬─────────────────────────────────┐
│ Settings         │ Selected category               │
│                  │                                 │
│ General          │ Overview or short subpage       │
│ Display          │                                 │
│ Weather          │                                 │
│ Alarms           │                                 │
│ AirPlay          │                                 │
│ Audio            │                                 │
│ Plexamp          │                                 │
│ Advanced         │                                 │
│ About            │                                 │
└──────────────────┴─────────────────────────────────┘
```

The category list remains visible on the left. Larger categories use short
subpages in the right pane with a Back control, reducing long vertical pages
without hiding the main navigation.

## Category structure

```text
General
└── Startup and idle

Display
├── Clock
└── Motion

Weather
├── Station
├── Units
├── Online forecast
└── Clock weather cards

Alarms
├── Alarm schedule
├── Defaults
└── Sound

AirPlay
├── Receiver
├── Starting volume
└── Handoff

Audio
├── Output trims
├── Equaliser
└── Hardware status

Plexamp
├── Connection
└── Service details

Advanced
├── Alarm diagnostics
├── Audio hardware
├── Playback and screen authority
└── Service status
```

## One configuration transaction

Configuration now uses one revisioned contract:

```text
GET  /api/settings
POST /api/settings
```

The right-pane Save bar stages and commits configuration as one validated transaction. The backend:

1. reads the current configuration and revision;
2. validates every submitted domain through its specialist normaliser;
3. rejects stale pages before they can overwrite newer settings;
4. applies managed system changes with rollback where required;
5. writes `config.json` once;
6. wakes or refreshes the affected runtime owners;
7. returns the fully normalised saved snapshot.

Alarm schedules continue to use the established strict alarm validator. Forecast
configuration uses the established forecast validator. Alarm-audio safety uses
the existing audio normaliser. The unified service orchestrates those owners
rather than duplicating their rules.

The old form autosave, separate Save alarms card, separate forecast save,
separate AirPlay-default save and multi-script form-submit handover have been
retired from the active page.

## Configuration versus actions

The interface follows one rule:

> Configuration is staged and saved together. Live controls, tests and refreshes
> act immediately.

**Save Changes** owns:

- startup screen, idle destination and timeout;
- Clock format and transition preferences;
- Weather names, individual units, forecast configuration and Clock cards;
- the complete alarm model and both scheduled-audio safety keys;
- the AirPlay receiver name, starting volume and pause-hold duration;
- EQ enabled/bypass plus Bass, Mid and Treble values;
- Plexamp connection and service details.

Immediate actions remain separate:

- persistent ALSA output trims, clearly labelled **Applied immediately**;
- forecast refresh-now;
- alarm visual/audio tests and emergency stop;
- scheduler recalculation;
- playback, screen and service diagnostic refreshes.

## Weather units

The unit page provides optional shortcut presets:

- UK mixed: °C, hPa, mm, mph;
- Metric: °C, hPa, mm, km/h;
- Imperial: °F, inHg, in, mph.

Each selector remains independently editable. Any combination that no longer
matches a preset is shown as **Custom**.

## Managed AirPlay receiver name

The AirPlay receiver name is one authoritative setting used by Shairport Sync and
the dashboard Ready/Now Playing surfaces.

A restricted root-owned helper:

- edits only `general.name` in `/etc/shairport-sync.conf`;
- validates the candidate with Shairport Sync before replacing the file;
- writes atomically;
- restarts only `shairport-sync.service`;
- verifies that the service returned active;
- restores the original configuration and restarts again if applying fails.

Changing the name requires an explicit confirmation because an active AirPlay
session will be interrupted briefly. Duplicate form submissions are blocked
throughout the confirmed retry.

The helper is installed deliberately with:

```bash
sudo bash scripts/install-shairport-name-helper.sh
```

It is not installed or invoked by a normal `git pull`.

## Equaliser

The Audio category retains first-class EQ controls:

- enabled/bypassed;
- Bass;
- Mid;
- Treble;
- staged reset to flat;
- backend health.

The Settings transaction uses the existing master-EQ authority and rolls back
applied band values if the configuration transaction fails. The old bare master
EQ installer remains blocked; it is not part of the Settings rollout.

## Removed active scaffolding

The redesigned page no longer loads:

- `settings-tabs.js`;
- `settings-autosave.js`;
- `settings-dashboard-preferences.js`;
- `settings-alarm-workspace.js`;
- `settings-alarm-scheduled.js`;
- `settings-alarm-scheduler.js`.

Alarm diagnostics now have an isolated Advanced client, while the alarm editor
registers its staged model with the unified Settings owner instead of submitting
independently.

## Physical validation checklist

- left sidebar remains visible and usable at 1024×600;
- right-pane category and subpage scrolling;
- touch keyboard and sticky Save bar coexist correctly;
- dirty dots, Discard and one transactional Save;
- UK/Metric/Imperial presets and Custom unit combinations;
- alarm schedule/default/safety changes save together;
- Clock weather-card order saves and Discard restores it;
- AirPlay rename confirmation, iOS receiver name and dashboard name consistency;
- EQ health and staged controls;
- live output trims remain immediate;
- Advanced diagnostics and deliberate actions remain separate from Save.

After this focused validation, remaining work is small compatibility cleanup,
release documentation and explicit approval before PR #2 is made ready or
merged.
