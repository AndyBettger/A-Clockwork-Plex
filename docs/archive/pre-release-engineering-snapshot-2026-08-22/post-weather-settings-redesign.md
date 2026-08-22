# Unified iPad-style Settings

## Status

Weather was the final major subsystem and has been physically validated on the
bedroom Raspberry Pi. The post-weather Settings consolidation is implemented on
`feature/alarm-engine` and the core split-view, autosave, Alarm, AirPlay, Audio
and kiosk behaviours have been physically validated at 1024×600.

The current completion pass adds the remaining display and presentation
contracts before the separate guarded production-EQ rollout:

- scheduled visual display dimming;
- one dashboard-wide 12/24-hour formatting authority;
- truthful presentation of all 1–16 Open-Meteo forecast days;
- read-only Advanced audio diagnostics;
- refreshed About/build information.

## Layout

Settings uses an **iPad-style split view**:

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
├── Clock format
├── Night dimming
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
├── Audio diagnostics and alarm tests
├── Playback and screen authority
└── Service status

About
├── Build information
├── Current appliance status
└── Project links
```

## One configuration transaction and autosave owner

Configuration uses one revisioned contract:

```text
GET  /api/settings
POST /api/settings
```

The active page autosaves through **one validated transaction** owner. The
backend:

1. reads the current configuration and revision;
2. validates every submitted domain through its specialist normaliser;
3. rejects stale pages before they can overwrite newer settings;
4. applies managed system changes with rollback where required;
5. writes `config.json` once;
6. wakes or refreshes the affected runtime owners;
7. returns the fully normalised saved snapshot.

Alarm schedules continue to use the strict alarm validator. Forecast
configuration uses the forecast validator. Alarm-audio safety uses the promoted
two-key production normaliser. Display dimming is validated through the promoted
Settings service and persists with the rest of the Display model.

The old manual Save bar was retired after physical testing showed it obscured
controls, especially with the touch keyboard open. Dirty indicators remain at
category, subpage and individual-option level until the autosave succeeds.

## Configuration versus actions

The interface follows one rule:

> Configuration autosaves through one transaction. Live controls, tests and
> refreshes act immediately.

Autosaved configuration includes:

- startup screen, idle destination and timeout;
- Clock format, night dimming and transition preferences;
- Weather names, individual units, forecast configuration and Clock cards;
- the complete alarm model and both scheduled-audio safety keys;
- the managed AirPlay receiver name, starting volume and pause-hold duration;
- EQ enabled/bypass plus Bass, Mid and Treble values;
- Plexamp connection and service details.

Immediate actions remain separate:

- persistent ALSA output trims, clearly labelled **Applied immediately**;
- forecast refresh-now;
- alarm visual/audio tests and emergency stop;
- scheduler recalculation;
- playback, screen and service diagnostic refreshes.

## Display dimming

Night dimming is a browser-safe visual feature rather than a privileged display
or backlight command. It supports:

- enabled/disabled state;
- start and end times, including schedules that cross midnight;
- adjustable night brightness;
- configurable touch-to-wake duration;
- optional very-dark Clock presentation;
- subtle burn-in shifting;
- an eight-second preview.

The first interaction while dimmed wakes the display and is consumed, preventing
an accidental button press beneath it. The Alarm screen is always rendered at
full brightness. Outside the schedule the overlay is removed automatically.

No dimming path invokes `xrandr`, changes a Pi display driver, requests root or
touches the audio graph.

## Dashboard-wide clock format

`ACPTime` is the one client formatting authority. The configured 12/24-hour mode
is used by:

- the primary Clock;
- the AirPlay mini clock;
- the Alarm current-time display;
- Weather and forecast timestamps;
- Advanced alarm diagnostics;
- marked status timestamps.

The existing server-side timestamp hook is promoted to the same setting so
server-rendered Weather values agree with client-rendered values. Alarm
configuration fields remain stored and edited as unambiguous 24-hour `HH:MM`
values.

## Weather units and forecast length

Unit presets are optional shortcuts:

- UK mixed: °C, hPa, mm, mph;
- Metric: °C, hPa, mm, km/h;
- Imperial: °F, inHg, in, mph.

Each selector remains independently editable. Any combination that no longer
matches a preset is shown as **Custom**.

Open-Meteo supports up to 16 forecast days. Settings exposes 1, 3, 5, 7, 10, 14
and 16 days. The original Weather renderer creates the established first seven
cards; the completion renderer appends every additional daily object returned by
the cached API, so a 16-day response produces 16 horizontally scrollable daily
cards rather than silently discarding days 8–16.

## Managed AirPlay receiver name

The **Managed AirPlay receiver name** is one authoritative setting used by
Shairport Sync, the dashboard Ready/Now Playing surface and the iPhone
destination list.

A restricted root-owned helper:

- edits only `general.name` in `/etc/shairport-sync.conf`;
- validates the candidate on an isolated temporary identity and port;
- writes atomically;
- restarts only `shairport-sync.service`;
- verifies that the service returned active;
- restores the original configuration and restarts again if applying fails.

Changing the name requires explicit confirmation because an active AirPlay
session is briefly interrupted. The path has been physically validated through
rename, iPhone discovery, connection, screen takeover and audio playback.

## Audio configuration and diagnostics

Everyday Audio contains real configuration or direct controls:

- calibrated source/master/alarm output trims;
- Bass, Mid and Treble EQ staging;
- a read-only summary of the configured route.

Advanced Audio is diagnostic. The stale editable controls for shared-mixer
selection, Physical DAC and Alarm PCM are removed. The page reports current
mixer/DAC state and retains only deliberate test-duration and alarm-audio action
controls. Switching the live physical route remains a guarded maintenance
operation with validation and rollback, not an autosaved text field.

The Advanced alarm-status client refreshes only while its subpage is visible and
uses a slower passive interval, reducing unnecessary journal traffic.

## About

About now identifies the current unified appliance, build/release metadata,
validated dashboard/audio/Settings state and the guarded production-EQ phase as
next. The repository and NFC companion links remain available.

## Equaliser

The Audio category retains first-class EQ controls:

- enabled/bypassed;
- Bass;
- Mid;
- Treble;
- reset to flat;
- backend health.

The guarded CamillaDSP laboratory and physical-rehearsal assets remain in the
branch. The old bare master-EQ installer remains blocked and is not part of the
normal Settings rollout.

## Removed active scaffolding

The redesigned page no longer loads:

- `settings-tabs.js`;
- `settings-autosave.js`;
- `settings-dashboard-preferences.js`;
- `settings-alarm-workspace.js`;
- `settings-alarm-scheduled.js`;
- `settings-alarm-scheduler.js`.

Alarm diagnostics have an isolated Advanced client, while the alarm editor
registers its model with the unified autosave owner instead of submitting
independently.

## Remaining physical validation checklist

- Night dimming schedule, preview and touch-to-wake at 1024×600;
- Alarm screen remains fully bright during a dim period;
- optional dark Clock hides Weather/footer and restores them on wake/daytime;
- 12/24-hour format agrees across Clock, AirPlay, Alarm, Weather and Advanced;
- 16-day forecast shows all returned daily cards with a usable custom scrollbar;
- Advanced Audio contains no editable DAC/PCM/shared-mixer controls or false dirty
  indicators;
- About accurately reflects the current appliance and EQ-next phase.

After this focused pass, the next substantive work is the guarded production-EQ
rollout, followed by final release smoke testing and explicit approval before PR
#2 is made ready or merged.
