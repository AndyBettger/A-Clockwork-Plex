# Scheduled alarm audio, shared mixing and regression testing

This document describes the completed Stage 9 alarm path on the
`feature/alarm-engine` branch. Real scheduled alarms can now play local tones,
provided both deliberate safety switches are enabled.

The bedroom Raspberry Pi has physically validated:

- clock-triggered scheduled playback;
- full-screen alarm takeover;
- Snooze, repeated ringing and Dismiss;
- Plexamp pause during alarm priority;
- AirPlay pause during alarm priority;
- no automatic music resume after Snooze or Dismiss;
- shared `acp_alarm` output without stopping audio services;
- alarm configuration persistence through the dedicated validated API.

## Ownership model

Alarm behaviour is split deliberately so there is only one owner for each job:

```text
ActiveAlarmScheduler
  owns time, recurrence, DST, occurrence keys, recovery, Snooze and Dismiss

ScheduledAlarmAudioManager
  mirrors a real ringing occurrence into acp_alarm when both safety keys allow it

PlaybackCoordinator
  gives the alarm audible priority by pausing Plexamp and AirPlay

ScreenProjectionController
  gives the alarm immediate visual priority
```

The scheduler does not open an audio device. Its internal playback flag therefore
remains false. User-facing alarm endpoints project the promoted audio manager's
truth onto the nested scheduler status so API consumers see one consistent
`playback_enabled` value.

## Safety model

Two independently saved controls are required for normal scheduled sound:

1. **Enable alarm sound** — the master safety key.
2. **Enable scheduled alarm sound** — the second safety key.

Turning off the master key also clears scheduled enablement, preventing a latent
scheduled alarm from becoming audible later.

Additional safeguards:

- explicit audio tests remain capped at 30 seconds;
- controlled tests remain capped at 25% output by the backend;
- scheduled playback is limited to the configured ring cycle, with a hard upper
  bound of 630 seconds;
- Snooze, Dismiss, Clear visual test, Stop alarm audio, leaving the ringing phase,
  or disabling either safety key stops alarm playback immediately;
- visual-only tests do not pause Plexamp or AirPlay;
- alarm audio takeover applies only to a real, non-test scheduled occurrence while
  scheduled sound is enabled;
- music sources remain paused after the alarm. Resuming them is a deliberate user
  action rather than an automatic guess.

## Shared audio path

```text
Plexamp  -> acp_plexamp --\
AirPlay  -> acp_airplay ---+-> acp_master -> acp_dmix -> physical DAC
Alarm    -> acp_alarm -----/
```

Each source PCM has its own ALSA `softvol` trim. All sources then pass through the
shared master control and common `dmix` output. Plexamp and Shairport Sync services
remain running; alarm priority is achieved with transport commands rather than
service stops or exclusive-DAC handovers.

## Alarm priority behaviour

When a real scheduled alarm enters its ringing phase:

1. the screen projection immediately selects the Alarm surface;
2. the scheduled audio manager starts the selected local tone through `acp_alarm`;
3. the final playback coordinator checks Plexamp and AirPlay;
4. any playing source is paused once;
5. if a source is deliberately restarted while the same alarm is still ringing,
   it is paused again;
6. Snooze or Dismiss releases alarm priority but does not automatically resume
   either music source.

Takeover diagnostics are exposed in the playback snapshot under:

```text
handoffs.alarm_takeover
```

The diagnostic includes the occurrence key, status, pause counts, last action,
last error and the explicit `manual` resume policy.

## Audio format

Generated alarm tones and the shared mixer use:

```text
16-bit PCM
44,100 Hz
2 channels
Dual mono: the complete tone is sent to left and right
```

## Persistent and live volume layers

### Persistent trims

The physical mixer stages are:

- **Master** — final output for every source;
- **Plexamp trim** — downstream of Plexamp's own player volume;
- **AirPlay trim** — downstream of the sender volume;
- **Alarm trim** — ceiling after the alarm fade and target volume.

They are managed through the shared mixer helper and survive restart.

### Live controls

The Audio drawer controls:

- current Master level;
- Plexamp's real player volume;
- AirPlay sender gain;
- current Alarm ceiling.

The dashboard uses an amplitude-style human scale:

```text
100% =   0.00 dB
 50% ≈  -6.02 dB
 25% ≈ -12.04 dB
 10% = -20.00 dB
```

Raw ALSA percentages are expected to differ and are exposed separately for
diagnostics.

## Installation and update

For ordinary application updates:

```bash
cd ~/A-Clockwork-Plex
git switch feature/alarm-engine
git pull --ff-only
bash scripts/run-tests.sh
sudo systemctl restart a-clockwork-plex.service
```

Hard-refresh Chromium after browser asset changes:

```text
Ctrl+Shift+R
```

Only install or refresh the shared ALSA path when its managed configuration or
helper has actually changed:

```bash
sudo bash scripts/install-shared-audio.sh
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Do not run the production master-EQ installer. Production EQ integration remains
blocked and is outside this alarm procedure.

Plexamp should explicitly use:

```text
A Clockwork Plex - Plexamp
```

## Configuration workflow

Everyday alarm editing lives under **Settings → Alarms**.

- Alarm cards use a dedicated JavaScript model and validated JSON API.
- **Save alarms** persists the complete alarm model.
- The save card remains sticky during normal editing but returns to document flow
  while the on-screen keyboard is open.
- The two scheduled-sound safety keys remain in the Alarms workspace.

Testing, hardware details and runtime diagnostics live under
**Settings → Advanced**.

## Physical regression procedure

### 1. Configuration persistence

1. Create or edit a temporary alarm several minutes ahead.
2. Select the current weekday and enable it.
3. Press **Save alarms**.
4. Reload Settings and confirm the enabled state, time and day remain.
5. Confirm `/api/alarms/config` reports the same values.

### 2. Scheduled alarm while idle

1. Enable both alarm-sound safety keys.
2. Wait for the real scheduled time; do not use a test button.
3. Confirm the Alarm screen appears and the local tone fades in.
4. Press Snooze and confirm sound stops immediately.
5. Confirm the alarm returns after the configured snooze period.
6. Dismiss and confirm it does not return for that occurrence.

### 3. Plexamp takeover

1. Start Plexamp playback.
2. Let a real scheduled alarm trigger.
3. Confirm Plexamp pauses and only the alarm remains audible.
4. Confirm Plexamp remains paused after Snooze and Dismiss.

### 4. AirPlay takeover

1. Start an AirPlay sender.
2. Let a real scheduled alarm trigger.
3. Confirm the sender is paused and only the alarm remains audible.
4. Confirm AirPlay remains paused after Snooze and Dismiss.

### 5. Visual and controlled tests

- A visual-only alarm test must not pause music.
- A controlled tone test remains finite and capped.
- **Stop alarm audio** must always terminate the controlled player.

## API diagnostics

```bash
curl -s http://localhost:8088/api/alarms/config \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/alarms/audio \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/alarms/scheduler \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/alarms/active \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/playback/state \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/audio/mixer \
  | venv/bin/python -m json.tool
```

Authoritative scheduled-sound fields are:

```text
/api/alarms/audio.scheduled_playback_enabled
/api/alarms/scheduler.playback_enabled
/api/alarms/scheduler.scheduler.playback_enabled
/api/alarms/active.playback_enabled
/api/alarms/active.scheduler.playback_enabled
```

All five should agree after the promoted status projection.

Service logs:

```bash
journalctl \
  -u a-clockwork-plex.service \
  -u plexamp.service \
  -u shairport-sync.service \
  -n 160 --no-pager
```

Useful ALSA checks:

```bash
aplay -l
aplay -L
amixer -c Pro scontrols
sudo fuser -v /dev/snd/*
```

## Emergency stop and relock

Stop alarm audio immediately:

```bash
curl -fsS -X POST http://localhost:8088/api/alarms/audio/stop
```

Then disable **Enable scheduled alarm sound**. Disable the master key as well when
all alarm sound should be locked.

The shared-mixer installer creates timestamped backups of managed ALSA and
Shairport files. Rollback of those files is only needed for an actual shared-path
failure; ordinary alarm configuration and application changes do not require it.
