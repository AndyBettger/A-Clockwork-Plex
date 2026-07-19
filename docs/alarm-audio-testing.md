# Controlled alarm audio, shared mixing and live-volume testing

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

Each source PCM has its own ALSA `softvol` trim. All three then pass through the shared master control and the `dmix` PCM. This removes the service-stop, DAC-release and service-restart timing problem.

## Two distinct volume layers

The interface deliberately separates calibration from everyday control.

### Persistent output trims — Settings → Audio

These are real ALSA stages and survive restart through `alsactl`:

- **Master** — final persistent level for every source;
- **Plexamp trim** — downstream of Plexamp's own player volume;
- **AirPlay trim** — downstream of the AirPlay sender/iPhone volume;
- **Alarm trim** — output ceiling after the alarm's own fade and target.

Changing a trim does not move Plexamp's or the iPhone's on-screen volume control, because it happens later in the audio path.

### Live mixer — bottom navigation drawer → Audio

These changes take effect immediately and do not wait for the Settings save button:

- **Master** — immediate shared-output level;
- **Plexamp** — calls Plexamp's own player-volume endpoint, so its Now Playing control should follow;
- **AirPlay** — uses Shairport's remote volume, so the AirPlay dashboard follows and compatible senders may follow;
- **Alarm** — immediate alarm output ceiling.

Live Master and Alarm changes are not written with `alsactl`; persistent defaults remain under Settings → Audio.

## Perceptual fader scale

The dashboard no longer exposes ALSA's raw linear control position as though it were loudness.

```text
Dashboard 100% ->   0.00 dB
Dashboard  50% ->  -6.02 dB
Dashboard  25% -> -12.04 dB
Dashboard  10% -> -20.00 dB
```

The mixer API also reports `raw_percent` and `db` for comparison with `alsamixer`. Therefore the percentage shown by `alsamixer` is expected to differ from the human-facing dashboard percentage.

## AirPlay volume separation and starting level

Shairport Sync outputs through `acp_airplay`, but it no longer uses the `A Clockwork AirPlay` ALSA trim as its sender-volume control. Sender volume stays inside Shairport, while `acp_airplay` remains a stable downstream calibration stage.

Settings → Audio includes:

- **Starting sender volume**;
- **Apply at the start of each session**.

When enabled, the dashboard retries the configured volume briefly while the new AirPlay remote session becomes available. The default is 60%.

## Audio format

Generated alarm tones and the shared mixer use:

```text
16-bit PCM
44,100 Hz
2 channels
Dual mono for alarm tones: the same complete signal is sent left and right
```

## Raspberry Pi installation or update

Install ALSA utilities when required:

```bash
sudo apt-get update
sudo apt-get install -y alsa-utils
```

Pull the feature branch, run the tests and install or refresh the shared mixer:

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
- creates four `softvol` controls on card `Pro`;
- installs the perceptual mixer helper and restricted sudo policy;
- routes the project user's default output through `acp_plexamp` when no unmanaged default exists;
- updates Shairport Sync to use `acp_airplay` without binding sender volume to the output trim;
- replaces AirPlay hooks so they pause Plexamp but never stop its service;
- migrates `config.json` to shared mode and adds the AirPlay starting-volume defaults;
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

Plexamp should explicitly use:

```text
A Clockwork Plex - Plexamp
```

The project-user ALSA default also points to `acp_plexamp` when no pre-existing unmanaged default prevents the installer from doing so, but explicit selection has proved more reliable on the bedroom Pi.

## Verify the installation

```bash
aplay -L | grep -A1 '^acp_'

/usr/local/bin/a-clockwork-plex-audio-mixer status \
  | python3 -m json.tool
```

The helper should report all four channels as available, including human `percent`, ALSA `raw_percent` and `db` values.

Open **Settings → Audio**. The persistent trim card should report **Shared and ready** and show four vertical faders.

## Staged tests

### 1. Persistent trims

Move each Settings → Audio fader and reload the page. The displayed values should survive. Fifty percent should remain clearly audible rather than behaving like the old near-mute raw ALSA value.

### 2. Live Plexamp volume

1. Start Plexamp playback.
2. Open the bottom drawer and press **Audio**.
3. Move the Plexamp live fader.
4. Confirm the Plexamp Now Playing volume changes and audio follows immediately.
5. Confirm the persistent Plexamp trim in Settings → Audio remains unchanged.

### 3. Live AirPlay volume and starting level

1. Set an AirPlay starting sender volume under Settings → Audio and save it.
2. Start a new AirPlay session.
3. Confirm the session becomes audible near that configured level.
4. Open the bottom Audio drawer and move the AirPlay fader.
5. Confirm the dashboard AirPlay volume changes; check whether the sender also reflects the remote change.
6. Confirm the persistent AirPlay trim remains unchanged.

The live AirPlay fader is disabled while no remote sender is available.

### 4. Plexamp plus alarm

1. Start music in Plexamp.
2. Open **Settings → Alarms → Controlled alarm audio**.
3. Confirm **Use shared ALSA mixer** is enabled and the alarm PCM is `acp_alarm`.
4. Set a five-second test duration.
5. Enable and save **Enable alarm audio tests**.
6. Press **Test tone now**.

The alarm should mix over the currently playing track. Plexamp must remain connected and its service must remain active. No stop, restart or DAC handover occurs.

### 5. Full alarm controls

Use **Test full alarm in 10 sec** and validate screen takeover, Snooze, the repeated cycle and Dismiss. Plexamp remains available throughout.

### 6. AirPlay handoff

Start AirPlay while Plexamp is playing. The shared AirPlay start hook pauses Plexamp and changes the dashboard mode, but leaves `plexamp.service` running. Ending AirPlay returns the screen without restarting Plexamp.

## Diagnostics

```bash
curl -s http://localhost:8088/api/audio/mixer \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/audio/live \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/audio/defaults \
  | venv/bin/python -m json.tool

curl -s http://localhost:8088/api/alarms/audio \
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
