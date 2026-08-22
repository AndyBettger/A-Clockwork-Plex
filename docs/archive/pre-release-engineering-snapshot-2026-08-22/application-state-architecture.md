# Application state and authority architecture

## Purpose

A Clockwork Plex assigns each state transition and command to one explicit owner instead of asking browser scripts, shell callbacks and individual pages to negotiate among themselves.

The central rule is:

> Observe broadly, but assign each transition and command to one authority.

The current composition is assembled in `app/runner.py` around these production authorities:

```text
Runtime specialists
  ├── ActiveAlarmScheduler
  ├── ScheduledAlarmAudioManager
  ├── Weather observation/forecast/rainfall services
  └── audio EQ/mixer/route helpers

ApplicationStateHub
  ├── RetainedBidirectionalHandoffCoordinator
  ├── MixerController
  ├── ScreenProjectionController
  ├── LinuxInputActivityMonitor
  └── compact specialist providers

Configuration authorities
  ├── UnifiedSettingsService
  ├── MasterEqualizer
  └── ShairportNameManager

Presentation authorities
  ├── ACPTime
  └── ACPDisplayDimming
```

The accepted release supports both managed Direct and CamillaDSP EQ audio profiles. The EQ profile is physically accepted and uses the canonical `a-clockwork-plex-camilladsp.service`; the obsolete bare master-EQ/laboratory paths are retired.

## ApplicationStateHub

`ApplicationStateHub` provides versioned, failure-isolated snapshots for browser clients and diagnostics. Important properties include:

- unchanged domain state keeps the same revision;
- generated timestamps do not manufacture state revisions;
- a failing specialist provider is isolated rather than suppressing other domains;
- compact shared state does not replace specialist diagnostics;
- browser clients render authority state rather than inventing transport/audio truth.

Primary state/command surfaces include:

```text
GET  /api/state
GET  /api/playback/state
GET  /api/playback/events
POST /api/playback/events
POST /api/playback/command
GET  /api/audio/state
GET  /api/screen/state
```

## Final playback authority

The production playback authority is `RetainedBidirectionalHandoffCoordinator`, promoted exactly once through the playback-authority layer.

It owns:

- explicit AirPlay transport commands;
- previous/next navigation when the sender supports it;
- persisted paused-AirPlay hold state;
- AirPlay → Plexamp and Plexamp → AirPlay takeover;
- retained/ceded AirPlay sessions;
- rapid sender-resume evidence;
- alarm priority over both music sources;
- command diagnostics and independent-observation confirmation.

It does **not** stop/start Plexamp or Shairport Sync as a handoff mechanism and does not edit the ALSA/CamillaDSP graph.

### Source priority

```text
real sounding alarm
  > newest deliberate music playback transition
  > retained/held AirPlay session
  > idle policy
```

Screen ownership remains separate from audio ownership. A manual Settings/Clock/Weather lease can remain visible while background music continues, but a ringing alarm always interrupts the lease.

## AirPlay lifecycle and handoff

Shairport start/end callbacks publish lifecycle intent to PlaybackCoordinator. They are rendered from the current wrapper renderer and never directly manage Plexamp services.

A paused but connected AirPlay sender may remain retained for the configured hold period. The coordinator persists its hold phase/deadline so a dashboard restart does not silently restart the timer.

When AirPlay starts while Plexamp is playing, Plexamp receives one Pause command from the playback authority. When genuine Plexamp playback starts while AirPlay owns audio, the AirPlay sender receives one Pause command and may remain retained until its existing deadline. Fresh sender-resume evidence can become newer user intent and reclaim AirPlay. Merely browsing a surface does not manufacture a handoff.

Metadata observation is separate from command ownership; see `docs/airplay-metadata.md`.

## Alarm authority

Alarm responsibility is intentionally divided:

```text
ActiveAlarmScheduler
  clock, recurrence, DST, recovery, occurrence queue, Snooze, Dismiss

ScheduledAlarmAudioManager
  tone rendering through acp_alarm and scheduled-audio safety policy

PlaybackCoordinator
  pause Plexamp/AirPlay and hold alarm audio priority

ScreenProjectionController
  immediate Alarm surface
```

A real scheduled alarm is sounding only when an active non-test occurrence is ringing and scheduled playback is enabled. Public alarm payloads project the promoted audio manager and identify the playback owner as `scheduled-alarm-audio-manager`.

Releasing alarm priority never automatically resumes music; the resume policy remains **manual**.

## Audio ownership

### MixerController

`MixerController` owns live source/master/alarm volume state and compact audio APIs.

- Plexamp live volume uses the Plexamp player adapter.
- AirPlay live volume uses the sender adapter/confirmation model.
- Persistent trims use the restricted mixer helper.
- Latest-value-wins handling prevents stale confirmations from replacing newer requests.
- Browser faders render controller truth rather than assuming a write has succeeded.

### Managed EQ profile

The accepted EQ music lane is:

```text
Plexamp/AirPlay
  → source trims
  → Music Master
  → fixed -6.5 dB music reserve
  → Bass/Mid/Treble tone stage
  → music/alarm combine
  → final limiter
  → DAC
```

The alarm lane is:

```text
per-alarm start/target/fade
  → Maximum Alarm Volume
  → join after Music Master/reserve/EQ
  → final limiter
  → DAC
```

Consequences:

- scheduled alarms bypass Music Master and music EQ;
- the fixed `-6.5 dB` reserve remains present when the EQ tone stage is bypassed;
- EQ bypass changes the tone stage, not alarm level or the fixed music reserve;
- the final limiter remains after music/alarm combination.

`MasterEqualizer` owns persisted Bass/Mid/Treble/bypass state through the restricted CamillaDSP-backed helper. The canonical service is `a-clockwork-plex-camilladsp.service`.

### Direct profile

The supported Direct profile preserves the same public source PCM contract and keeps alarm outside Music Master without CamillaDSP. It is also the validated failback/rollback destination where the audio lifecycle requires it.

Route installation/repair/removal belongs to the guarded audio lifecycle under `scripts/audio/`, not Settings or browser code.

## Screen projection authority

`ScreenProjectionController` owns the recommended visible surface using playback state, playback generation, manual navigation leases, configured startup/idle policy, Linux input activity and alarm priority.

Important rules:

- Alarm interrupts every manual lease immediately.
- A genuine new playback generation may interrupt a background/manual page.
- Ordinary track progression within one Plexamp queue does not.
- Manual pages remain visible until their inactivity lease expires unless a higher-priority event occurs.
- Browser navigation is acknowledged before transition so stale projection responses cannot undo the user's action.

The kiosk launcher waits for the dashboard, uses its dedicated Chromium profile and opens the dashboard shell rather than making the browser a playback authority.

## Unified Settings authority

`UnifiedSettingsService` owns revisioned appliance configuration through:

```text
GET  /api/settings
POST /api/settings
```

The browser uses one autosave transaction owner. The backend validates specialist domains, rejects stale revisions, performs guarded specialist changes, writes `config.json` once, and refreshes affected runtime owners.

Runtime actions remain separate from configuration: mixer movement, alarm tests/stop, forecast refresh, scheduler recalculation and diagnostics are immediate actions rather than fake settings.

## Display presentation authorities

### ACPTime

`ACPTime` owns dashboard-wide 12/24-hour presentation for Clock, AirPlay, Alarm, Weather/forecast and marked diagnostic timestamps. Alarm schedule values remain stored as unambiguous 24-hour `HH:MM` configuration data.

### ACPDisplayDimming

`ACPDisplayDimming` owns scheduled visual night treatment, preview and touch-wake behavior. It is browser presentation logic, not a root/backlight/audio authority. The Alarm surface always escapes dimming.

## Weather authority

Open-Meteo supplies cached forecast data. Live observations may be owned by **Ecowitt Push** or **Weather Underground PWS**, according to the selected provider.

When Weather Underground is the selected outdoor source, a fresh Ecowitt push may supplement indoor temperature/humidity only. It may not overwrite WU outdoor state, and stale supplementary indoor values expire.

Weather Underground credentials remain outside public `config.json` in the managed root-owned environment file. Retaining a WU credential while Ecowitt is selected is valid because WU can continue to supply historical-rainfall data.

Rainfall-history refresh is serialized so background refresh, Settings actions and connection tests cannot concurrently corrupt the cache transaction.

## Managed Shairport receiver name

`ShairportNameManager` is an unprivileged client of the fixed root-owned Shairport-name helper. The helper is restricted to the managed configuration/validation/restart boundary and rolls back a failed rename. An active AirPlay session requires explicit confirmation before a receiver-name change.

## Browser boundary

Browser clients may:

- autosave normalized configuration through the unified transaction;
- request explicit runtime actions;
- report genuine interaction activity;
- acknowledge visible surfaces;
- render server state.

They must not:

- restart audio services directly;
- edit system configuration directly;
- infer transport truth from an icon;
- arbitrate Plexamp versus AirPlay;
- own the AirPlay hold timer;
- decide whether scheduled alarm audio may sound;
- rewrite the audio route.

## Current acceptance state

The replacement-SD clean-room release candidate has physically validated:

- dashboard/kiosk reboot and commissioned startup;
- Plexamp and NFC playback;
- bidirectional Plexamp/AirPlay handoff;
- managed AirPlay receiver naming and metadata presentation;
- EQ and bypass behavior through the accepted CamillaDSP service;
- real scheduled alarm fade, takeover, Snooze and Dismiss while bypassing Music Master;
- Ecowitt/WU observation behavior and WU rainfall-history workflows;
- unified touchscreen Settings and accepted theme/presentation closure;
- repeat public `setup.sh`, formal verifiers and final clean tracked checkout.

No additional physical release gate is outstanding. Remaining Phase 7 work is repository/document/ref hygiene, the final dependency/tracked-file audit, final complete CI validation and explicit owner approval.

PR #2 remains draft, open and unmerged until that explicit approval.
