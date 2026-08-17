# Post-reboot EQ runtime failure — 2026-08-17

Target: spare SD card on `plexamp-test`. The accepted production SD card remained removed and untouched.

## Reboot verification before the failure

The first real reboot after persistent EQ promotion reconstructed the appliance sufficiently for all static/read-only verification gates to pass:

- source checkout remained clean at `79094daac4e71358ccda900b63fa7245ed369ee8`;
- `FRESH_BOOTSTRAP_VERIFY=PASS` with zero failures/warnings;
- `APPLIANCE_VERIFY=PASS` with zero failures/warnings;
- `scripts/audio/verify-audio.sh` reported EQ-capable audio verification passed;
- active ALSA route SHA-256 remained `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`;
- `/var/lib/a-clockwork-plex/split-bus/installed` remained present;
- `a-clockwork-plex-camilladsp.service` reported `active` and `enabled`;
- the kiosk/dashboard returned automatically after reboot.

Evidence paths:

- `/home/andy/acp-phase7-spare-sd-20260815-171112/40-bootstrap-after-reboot.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/41-appliance-after-reboot.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/42-audio-after-reboot.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/43-eq-route-after-reboot.sha256`

## Physical runtime failure

The reboot checkpoint is **not accepted** despite the green static verifiers.

After Plexamp playback was started successfully, the Audio page initially reported **EQ Active**. When the physical EQ controls were adjusted, error text appeared on the Audio surface. Opening Settings afterwards returned **Internal Server Error**. Plexamp itself continued playing, but dashboard control was no longer usable to stop playback; the operator rebooted the Pi to recover/stop playback.

Because the failure occurred before the remaining reboot smoke checks, the following were deliberately not run:

- NFC playback after reboot;
- Music Master `0%` plus real scheduled-alarm isolation after reboot.

The repeat whole-appliance installer gate is blocked until this post-boot runtime failure is understood and repaired.

## Current diagnosis boundary

The failure is narrower than a boot-time EQ construction failure:

- the managed CamillaDSP unit was active/enabled;
- the canonical split-bus route and installed marker were intact;
- all three independent verifiers passed before live EQ mutation;
- failure appeared only when the running post-boot EQ backend was mutated and was followed by an HTTP 500 on Settings.

The next diagnostic step is read-only recovery of the **previous boot** dashboard/Camilla/route/failback journals plus a current-boot EQ/API health snapshot. Do not repeat NFC/alarm/repeat-install acceptance until that evidence is reviewed.

PR #2 remains Draft, open and unmerged until explicit owner approval.
