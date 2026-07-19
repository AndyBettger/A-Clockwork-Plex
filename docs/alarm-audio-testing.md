# Controlled alarm audio testing

This development pass permits **explicit local-audio tests only**. Ordinary scheduled alarms still cannot start audio, even when the master test switch is enabled.

## Safety model

- `alarm_audio.master_enabled` unlocks deliberate tests from Settings.
- `alarm_audio.scheduled_enabled` is forced to `false` by the backend.
- Full-screen audio works only for a unique visual-test occurrence explicitly armed by the audio endpoint.
- Restarting the dashboard clears in-memory audio arming, so a pending test cannot unexpectedly resume sound after a service restart.
- Every test has a maximum duration of 30 seconds.
- Every controlled test is capped at **25% output** by the backend, regardless of the alarm's saved start and target volume.
- Snooze, Dismiss, Clear visual test and Stop alarm audio terminate playback immediately.
- A player that ignores termination is killed before service restoration continues.

## Audio format

Generated alarm tones use:

```text
16-bit PCM
44,100 Hz
2 channels
Dual mono: the same complete alarm signal is sent to left and right
```

This avoids a mono stream being routed to only one side of a stereo DAC and gives ALSA a conventional hi-fi format to present to the hardware.

## Raspberry Pi prerequisites

Install ALSA utilities when `aplay` is unavailable:

```bash
sudo apt-get update
sudo apt-get install -y alsa-utils
```

Install the restricted audio-ownership helper:

```bash
cd ~/A-Clockwork-Plex
sudo bash scripts/install-alarm-audio-helper.sh
```

The installer creates:

```text
/usr/local/bin/a-clockwork-plex-alarm-audio
/etc/sudoers.d/a-clockwork-plex-alarm-audio
```

The helper has only three fixed operations:

```text
status
release
restore <plexamp-was-active 0|1> <shairport-was-active 0|1>
```

It cannot execute arbitrary services or commands.

## First controlled test

1. Open **Settings → Alarms → Controlled alarm audio**.
2. Confirm `aplay ready` and `Installed` are shown.
3. Set the ALSA output device. On the bedroom Pi with the RPi DAC Pro, use `plughw:CARD=Pro,DEV=0`.
4. Save with either **Save audio safety settings** or the main sticky **Save settings** button. Both routes persist the audio card.
5. Reload Settings and confirm the device remains selected.
6. Choose a 5-second test duration.
7. Enable **Enable alarm audio tests** and save.
8. Use **Test tone now**. The backend caps both the starting and target volume at 25% for this pass.
9. Confirm the tone stops automatically and the previous services return.
10. Use **Stop alarm audio** during a second test and confirm it stops immediately.
11. Use **Test full alarm in 10 sec** to validate screen takeover, Snooze and Dismiss with real test audio.
12. Disable the master test switch and save after testing.

Stopping Shairport Sync ends any live AirPlay session. The service can be restored, but the originating phone must start or reconnect its stream again.

## Diagnostics

```bash
curl -s http://localhost:8088/api/alarms/audio \
  | venv/bin/python -m json.tool

cat alarm-audio-runtime.json \
  | venv/bin/python -m json.tool

journalctl -u a-clockwork-plex.service -n 100 --no-pager
```

Useful ALSA checks:

```bash
aplay -l
aplay -L
```

When `default` is not the correct output, use a device name reported by `aplay -L` in the audio Settings card. `plughw:` is preferred for a hardware DAC because ALSA may adapt the stream format when the device requires it.

## Emergency rollback

Stop any alarm test and relock audio:

```bash
curl -fsS -X POST http://localhost:8088/api/alarms/audio/stop
```

Then disable **Enable alarm audio tests** in Settings.

Remove the privileged helper and policy completely:

```bash
sudo rm -f /usr/local/bin/a-clockwork-plex-alarm-audio
sudo rm -f /etc/sudoers.d/a-clockwork-plex-alarm-audio
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
```
