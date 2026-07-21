# Master EQ installation and controlled testing

The master EQ pass adds a restrained three-band curve to the shared audio path:

```text
Plexamp player → Plexamp trim ┐
AirPlay sender → AirPlay trim ├→ identical Eq10 curve → Master → dmix → DAC
Alarm fade     → Alarm trim   ┘
```

The same linear curve is applied to every source immediately before the existing Master stage. This preserves the proven shared `dmix` design while producing the same frequency response for the summed output.

## Safety limits

- Bass, Mid and Treble are limited to `−6 dB` through `+6 dB`.
- Controls move in `0.5 dB` steps.
- A double-click on a drawer knob returns that band to `0 dB`.
- **Neutral** resets all bands to `0 dB` and leaves EQ active.
- **Bypass** temporarily applies a neutral response while remembering the previous curve.
- Bypass is a neutral-response bypass; the ALSA equalizer plugin remains in the signal path.
- Scheduled alarm playback remains disabled.

A positive EQ setting consumes headroom. Begin testing with Master below its normal maximum and avoid starting with several boosted bands.

## Install

Run the shared-audio installer first when the shared path has not already been configured:

```bash
cd ~/A-Clockwork-Plex
sudo bash scripts/install-shared-audio.sh
```

Then install the EQ stage:

```bash
sudo bash scripts/install-master-eq.sh
```

The installer:

1. installs `libasound2-plugin-equal` and the CAPS plugins when required;
2. backs up the existing shared ALSA, helper, sudoers and dashboard-service files;
3. creates the `acp_equal` control and PCM;
4. routes Plexamp, AirPlay and alarm source trims through that curve before Master;
5. installs the restricted EQ helper and sudoers rules;
6. starts with a neutral `0 / 0 / 0 dB` curve;
7. updates the dashboard service to use the EQ-aware runner.

Restart the audio services and dashboard:

```bash
sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Fully close and reopen Chromium after installation so the new Audio controls are loaded cleanly.

## Command-line diagnostics

Check the restricted helper directly:

```bash
sudo /usr/local/bin/a-clockwork-plex-audio-eq status | python3 -m json.tool
```

Check through the dashboard API:

```bash
curl -s http://localhost:8088/api/audio/eq | venv/bin/python -m json.tool
```

The healthy neutral state reports:

```text
available: true
bypassed: false
bass:     0 dB
mid:      0 dB
treble:   0 dB
```

## Controlled listening test

### 1. Neutral baseline

1. Open the bottom drawer and select **Audio**.
2. Confirm Master EQ says **Active**.
3. Confirm Bass, Mid and Treble all show `0 dB`.
4. Keep Master below its normal ceiling for the first test.
5. Play a familiar, well-recorded Plexamp track.
6. Press **Neutral** once and confirm the sound does not jump unexpectedly.

### 2. Individual bands

Change only one control at a time:

```text
Bass:    +2 dB → 0 dB → −2 dB → 0 dB
Mid:     +2 dB → 0 dB → −2 dB → 0 dB
Treble:  +2 dB → 0 dB → −2 dB → 0 dB
```

Confirm:

- changes are audible without clicks, stalls or service restarts;
- the untouched bands remain at their previous values;
- a drawer knob remains where it was left after the next status refresh;
- Settings → Audio shows the same values.

### 3. Neutral and bypass

Try a modest curve such as:

```text
Bass:    +2 dB
Mid:      0 dB
Treble:  +1 dB
```

Then:

1. select **Bypass** and confirm the response becomes neutral;
2. select **Restore EQ** and confirm the saved curve returns;
3. select **Neutral** and confirm all controls return to `0 dB`;
4. restart the dashboard and confirm the neutral state persists;
5. save the modest curve again, restart the Pi later, and confirm it persists.

### 4. Source regression

Repeat a small `+2 dB Bass` change with:

- Plexamp playing;
- AirPlay playing;
- a controlled alarm-tone test at its existing safety-capped volume.

All three should follow the same curve. Plexamp/AirPlay pause handoff and the alarm overlay must continue to work normally.

Do not enable scheduled alarm playback during this EQ pass.

### 5. Headroom check

With a familiar loud track:

1. keep all bands neutral and note the clean baseline;
2. apply the most boosted curve you realistically expect to use;
3. listen for harshness, crackling or obvious clipping;
4. reduce Master when necessary rather than compensating with negative source trims.

The dashboard deliberately limits each band to `+6 dB`, but three simultaneous boosts can still increase peak level.

## Rollback

The installer records its most recent backup at:

```text
/var/lib/a-clockwork-plex/eq-last-backup
```

Restore that snapshot with:

```bash
cd ~/A-Clockwork-Plex
sudo bash scripts/install-master-eq.sh --rollback

sudo systemctl restart plexamp.service
sudo systemctl restart shairport-sync.service
sudo systemctl restart a-clockwork-plex.service
```

Rollback restores the ALSA shared path, prior EQ configuration, helper, sudoers and dashboard service file from the last installation snapshot.

## Useful troubleshooting

```bash
aplay -L | grep -A2 -E 'acp_(equal|master|plexamp|airplay|alarm)'
amixer -D acp_equal scontrols
amixer -D acp_equal scontents
systemctl status a-clockwork-plex.service plexamp.service shairport-sync.service --no-pager
journalctl -u a-clockwork-plex.service -n 100 --no-pager
```

When `amixer -D acp_equal scontrols` does not list ten controls, leave the curve neutral or use rollback rather than modifying the generated ALSA files by hand.
