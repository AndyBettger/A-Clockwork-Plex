# Controlled alarm audio and shared-mixer testing

This development pass permits **explicit local-audio tests only**. Ordinary scheduled alarms still cannot start audio, even when the master test switch is enabled.

## Safety model

- `alarm_audio.master_enabled` unlocks deliberate tests from Settings.
- `alarm_audio.scheduled_enabled` is forced to `false` by the backend.
- Full-screen audio works only for a unique visual-test occurrence explicitly armed by the audio endpoint.
- Restarting the dashboard clears in-memory audio arming, so a pending test cannot unexpectedly resume sound after a service restart.
- Every test has a maximum duration of 30 seconds.
- Every controlled test is capped at **25% output** by the backend, regardless of the alarm's saved start and target volume.
- Snooze, Dismiss, Clear visual test and Stop alarm audio terminate playback immediately.
- Shared mode never stops Plexamp or Shairport Sync to acquire the DAC.

## Shared audio design

```text
Plexamp  -> acp_plexamp --\
AirPlay  -> acp_airplay ---+-> acp_master -> acp_dmix -> RPi DAC Pro
Alarm    -> acp_alarm -----/
```

Each source PCM has its own ALSA `softvol` control. All three then pass through the shared master control and the `dmix` PCM. This removes the service-stop, DAC-release and service-restart timing problem.

The Settings mixer controls real ALSA levels:

- **Master output** — final level for every source;
- **Plexamp** — additional gain after Plexamp's own player volume;
- **AirPlay** — the same source control used by Shairport Sync and the sender;
- **Alarm** — an output ceiling after the alarm's own fade and target volume.

## Audio format

Generated alarm tones and the shared mixer use:

```text
16-bit PCM
44,100 Hz
2 channels
Dual mono for alarm tones: the same complete signal is sent left and right
```

## One-time Raspberry Pi installation

Install ALSA utilities when required:

```bash
sudo apt-get update
sudo apt-get install -y alsa-utils
```

Pull the feature branch, run the tests and install the shared mixer:

```bash
cd ~/A-Clockwork-Plex
git switch feature/alarm-engine
git pull --ff-only
bash scripts/run-tests.sh
sudo bash scripts/install-shared-audio.sh
```

The installer:

- writes `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`;
- registers `acp_master`, `acp_plexamp`, `acp_airplay` and `acp_alarm`;
- creates four persistent `softvol` controls on card `Pro`;
- routes the project user's default ALSA output through `acp_plexamp` when no unmanaged default already exists;
- updates Shairport Sync to use `acp_airplay` and the AirPlay soft-volume control;
- replaces AirPlay hooks so they pause Plexamp but never stop its service;
- installs `/usr/local/bin/a-clockwork-plex-audio-mixer` and its restricted sudo policy;
- migrates `config.json` to `shared_mixer_enabled: true` and `alsa_device: acp_alarm`;
- keeps scheduled alarm audio disabled.

The bedroom Pi defaults are:

```text
ALSA_CARD=Pro
ALSA_DEVICE=0
```

For different hardware:

```bash
sudo ALSA_CARD=YourCard ALSA_DEVICE=0 \
  bash scripts/install-shared-audio.sh
```

Restart the audio services and dashboard:

```bash
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Plexamp should use its default ALSA output. When Plexamp has an explicitly selected hardware device, change it once to `acp_plexamp` or **A Clockwork Plex - Plexamp**.

## Verify the installation

```bash
aplay -L | grep -A1 '^acp_'

/usr/local/bin/a-clockwork-plex-audio-mixer status \
  | python3 -m json.tool
```

The helper should report all four channels as available.

Open **Settings → General → Shared audio mixer**. The card should report **Shared and ready** and display live values for all four controls.

## Staged tests

### 1. Mixer controls

Move each slider and confirm the percentage survives a page reload. The `−` and `＋` buttons change the selected source in five-percent steps.

### 2. Plexamp plus alarm

1. Start music in Plexamp.
2. Open **Settings → Alarms → Controlled alarm audio**.
3. Confirm **Use shared ALSA mixer** is enabled and the alarm PCM is `acp_alarm`.
4. Set a five-second test duration.
5. Enable and save **Enable alarm audio tests**.
6. Press **Test tone now**.

The alarm should mix over the currently playing track. Plexamp must remain connected and its service must remain active. No stop, restart or DAC handover occurs.

### 3. Full alarm controls

Use **Test full alarm in 10 sec** and validate screen takeover, Snooze, the repeated cycle and Dismiss. Plexamp remains available throughout.

### 4. AirPlay handoff

Start AirPlay while Plexamp is playing. The shared AirPlay start hook pauses Plexamp and changes the dashboard mode, but leaves `plexamp.service` running. Ending AirPlay returns the screen without restarting Plexamp.

## Diagnostics

```bash
curl -s http://localhost:8088/api/audio/mixer \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/alarms/audio \
  | venv/bin/python -m json.tool

cat alarm-audio-runtime.json \
  | venv/bin/python -m json.tool

journalctl \
  -u a-clockwork-plex.service \
  -u plexamp.service \
  -u shairport-sync.service \
  -n 120 --no-pager
```

Useful ALSA checks:

```bash
aplay -l
aplay -L
amixer -c Pro scontrols
sudo fuser -v /dev/snd/*
```

With `dmix`, the DAC PCM may be owned by an ALSA client while several source streams remain usable. That is expected; source sharing happens through the common dmix PCM rather than by repeatedly opening the hardware directly.

## Emergency rollback

Stop and relock alarm tests:

```bash
curl -fsS -X POST http://localhost:8088/api/alarms/audio/stop
```

Then disable **Enable alarm audio tests** in Settings.

The installer creates timestamped backups of the managed ALSA and Shairport files. To remove the shared mixer itself:

```bash
sudo rm -f /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
sudo rm -f /usr/local/bin/a-clockwork-plex-audio-mixer
sudo rm -f /etc/sudoers.d/a-clockwork-plex-audio-mixer
sudo rm -f /etc/default/a-clockwork-plex-audio
```

Restore the most recent `/etc/shairport-sync.conf.<timestamp>.bak` and `.asoundrc` backup when required, then restart Plexamp and Shairport Sync.
