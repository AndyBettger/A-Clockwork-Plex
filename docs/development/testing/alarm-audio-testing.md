# Scheduled alarm audio and regression testing

This document describes the accepted scheduled-alarm path on `feature/alarm-engine`. Real scheduled alarms can play local tones when both deliberate sound-safety controls are enabled, and the replacement-SD release candidate has physically validated the complete takeover/fade/Snooze/Dismiss path.

The accepted physical evidence includes:

- real **clock-triggered scheduled playback**;
- full-screen Alarm takeover;
- configured start volume, target volume and fade;
- Snooze, repeated ringing and Dismiss;
- **Plexamp pause during alarm priority**;
- **AirPlay pause during alarm priority**;
- no automatic music resume after Snooze or Dismiss;
- an alarm lane that bypasses Music Master and music EQ;
- Maximum Alarm Volume remaining the independent alarm ceiling.

## Ownership model

Alarm behaviour is deliberately split so each job has one authority:

```text
ActiveAlarmScheduler
  owns time, recurrence, DST, occurrence keys, recovery, Snooze and Dismiss

ScheduledAlarmAudioManager
  renders a real ringing occurrence into acp_alarm when both safety keys allow it

PlaybackCoordinator
  gives the sounding alarm audible priority by pausing Plexamp and AirPlay

ScreenProjectionController
  gives the ringing alarm immediate visual priority
```

The scheduler does not open the audio device. Public alarm status projects the promoted alarm-audio authority so API consumers see truthful scheduled-playback enablement without giving the scheduler a second player implementation.

## Safety model

Two independently persisted controls gate ordinary scheduled sound:

1. **Enable alarm sound** — master alarm-audio safety key.
2. **Enable scheduled alarm sound** — scheduled-occurrence safety key.

Turning off the master key also prevents scheduled sound from remaining latently armed.

Additional safeguards include:

- explicit preview/test playback remains finite and separately capped;
- scheduled playback cannot outlive its bounded ringing cycle;
- Snooze, Dismiss, emergency stop, leaving the ringing phase or disabling a sound-safety key stops the current alarm audio;
- visual-only tests do not pause Plexamp or AirPlay;
- alarm takeover applies only to a real sounding scheduled occurrence, not a configuration preview;
- releasing alarm priority never automatically resumes music.

## Accepted audio topology

### EQ profile

The release-candidate EQ route keeps music and alarm on separate lanes until after the music-only processing stage:

```text
Plexamp player volume -> Plexamp trim --\
                                         +-> Music Master -> fixed -6.5 dB reserve -> Bass/Mid/Treble --\
AirPlay sender volume -> AirPlay trim ---/                                                          \
                                                                                                      +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume ----------------------------------------------------/
```

The fixed `-6.5 dB` reserve is always present in the music lane. EQ bypass bypasses the Bass/Mid/Treble tone stage; it does **not** remove the fixed reserve. Scheduled alarms bypass Music Master, the fixed music reserve and music EQ, then join before the final limiter.

Therefore listening quietly to music cannot make the next alarm quiet, and changing/bypassing Bass, Mid or Treble cannot change alarm loudness or tone balance.

### Direct profile / failback

The supported Direct route preserves the same public source PCM names and keeps alarm outside Music Master. It has no CamillaDSP tone stage. Direct is used for the supported non-EQ profile and as the validated failback/rollback destination where appropriate.

## Volume ownership

Persistent controls have distinct jobs:

- **Music Master** — overall persistent music level for Plexamp and AirPlay only;
- **Plexamp trim** — downstream calibration of Plexamp;
- **AirPlay trim** — downstream calibration of the sender;
- **Maximum Alarm Volume** — independent ceiling for scheduled alarm output.

Each alarm additionally has its own starting volume, target volume and fade duration. The per-alarm start/target values are constrained by Maximum Alarm Volume; they are not multiplied by Music Master.

Live Plexamp and AirPlay volume remain source-owned through their respective adapters. Browser controls render controller state rather than pretending a requested value has already been confirmed.

## Alarm priority behaviour

When a real scheduled alarm enters its ringing phase:

1. ScreenProjectionController immediately selects the Alarm surface.
2. ScheduledAlarmAudioManager starts the configured local tone through `acp_alarm` using the saved start/target/fade policy.
3. PlaybackCoordinator gives the alarm priority over the music sources.
4. Any playing Plexamp or AirPlay source is paused through its transport owner, not by stopping its service.
5. If a music source is deliberately restarted while the same alarm is still sounding, alarm priority can pause it again.
6. Snooze or Dismiss releases alarm priority but leaves music paused; resume remains **manual**.

Plexamp, Shairport Sync and CamillaDSP are not restarted as an alarm-handoff mechanism.

## Normal installation and convergence

Do not install an alarm/shared-audio path separately. The supported appliance entry point is:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

The guarded installer owns the selected Direct/EQ route, application helpers and final verification transaction. The retired standalone shared-audio/helper installers and the old bare master-EQ laboratory installer must not be reintroduced.

For release/source validation before a change is accepted:

```bash
bash scripts/run-tests.sh
```

The formal installed audio verifier is:

```bash
bash scripts/audio/verify-audio.sh --help
```

Use the profile/options matching the appliance under test rather than guessing at a route.

Plexamp should be commissioned to use the managed output presented as:

```text
A Clockwork Plex - Plexamp
```

## Configuration workflow

Everyday alarm editing lives under **Settings → Alarms** and participates in the unified revisioned Settings transaction. Alarm cards do not own a second independent save path.

Testing and runtime diagnostics live under **Settings → Advanced**. The ordinary configuration UI is not a route installer or service-control console.

## Physical regression procedure

### 1. Configuration persistence

1. Create or edit a temporary alarm several minutes ahead.
2. Select the required weekday and enable the alarm.
3. Allow the unified Settings transaction to persist it.
4. Reload Settings and confirm enabled state, time, day, start volume, target and fade remain correct.
5. Confirm `/api/alarms/config` reports the same normalised model.

### 2. Scheduled alarm while idle

1. Enable both alarm-sound safety keys.
2. Wait for the real scheduled time; do not substitute a test button.
3. Confirm the Alarm screen appears and the tone begins at the configured start level and fades toward the capped target.
4. Press Snooze and confirm sound stops immediately.
5. Confirm the alarm rings again after the configured snooze period.
6. Dismiss and confirm it does not return for that occurrence.

### 3. Music Master independence

1. Set Music Master to a deliberately low value or 0% while keeping Maximum Alarm Volume at a safe test level.
2. Let a real scheduled alarm trigger.
3. Confirm the alarm remains audible at its configured/capped level.
4. Restore Music Master after the test.

This is the direct product proof that alarm output is not downstream of Music Master.

### 4. EQ independence

1. With the EQ profile healthy, choose a clearly non-neutral Bass/Mid/Treble curve at a safe music level.
2. Let a real scheduled alarm trigger and confirm the alarm tone is not coloured by the music EQ.
3. Repeat with EQ bypassed if required; alarm level/tone must remain unchanged.
4. Return the saved EQ curve to the intended listening state.

### 5. Plexamp takeover

1. Start Plexamp playback.
2. Let a real scheduled alarm trigger.
3. Confirm Plexamp pauses and the alarm owns audible priority.
4. Confirm Plexamp remains paused after Snooze/Dismiss until the user deliberately resumes it.

### 6. AirPlay takeover

1. Start an AirPlay sender.
2. Let a real scheduled alarm trigger.
3. Confirm the sender is paused and the alarm owns audible priority.
4. Confirm AirPlay remains paused after Snooze/Dismiss until deliberately resumed or the retained session expires/disconnects according to PlaybackCoordinator policy.

### 7. Visual and controlled tests

- A visual-only alarm test must not pause music.
- A controlled tone/preview test remains finite and deliberately quieter than normal scheduled playback.
- **Stop alarm audio** must always terminate controlled/current alarm audio.

## Read-only diagnostics

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

curl -s http://localhost:8088/api/audio/state \
  | venv/bin/python -m json.tool
```

Useful service logs:

```bash
journalctl \
  -u a-clockwork-plex.service \
  -u plexamp.service \
  -u shairport-sync.service \
  -u a-clockwork-plex-camilladsp.service \
  -n 160 --no-pager
```

Useful ALSA checks:

```bash
aplay -l
aplay -L
amixer -c Pro scontrols
sudo fuser -v /dev/snd/*
```

For the complete read-only playback decision snapshot:

```bash
bash scripts/inspect-playback-coordinator.sh
```

## Emergency stop and relock

Stop alarm audio immediately:

```bash
curl -fsS -X POST http://localhost:8088/api/alarms/audio/stop
```

Then disable **Enable scheduled alarm sound**. Disable the master alarm-sound key as well when all alarm audio should be locked.

A route/configuration failure should be handled through the guarded installer/audio lifecycle with its captured rollback state, not by copying old ALSA files or invoking retired standalone installers.
