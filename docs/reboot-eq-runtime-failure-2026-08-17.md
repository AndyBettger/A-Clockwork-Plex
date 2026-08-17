# Post-reboot Settings/runtime failure — 2026-08-17

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

## First physical symptom

The reboot checkpoint is **not accepted** despite the green static verifiers.

After Plexamp playback was started successfully, the Audio surface initially reported **EQ Active**. During the first post-reboot attempt to adjust EQ, error text was seen on the Audio surface. Opening Settings afterwards returned **Internal Server Error**. Plexamp itself continued playing, but dashboard control was no longer usable to stop playback; the operator rebooted the Pi to recover/stop playback.

Because the failure occurred before the remaining reboot smoke checks, NFC playback and Music Master `0%` plus real scheduled-alarm isolation were deliberately not run.

## Second boot narrows the fault

The previous boot could not be recovered because this image currently has no persistent journald store: `journalctl -b -1` reported `Specifying boot ID or boot offset has no effect, no persistent journal was found.`

On the next boot, the operator repeated Plexamp playback and live EQ adjustment before diagnosis commands were issued. This time the EQ mutation worked normally. The resulting health evidence was:

- `GET /api/audio/eq`: HTTP-success JSON with `available:true`, `backend_state:"split-bus-active"`, no error, Bass `+2.0 dB`, Mid `0.0 dB`, Treble `+2.0 dB`;
- restricted helper `sudo -n /usr/local/bin/a-clockwork-plex-audio-eq status`: the same healthy EQ state;
- `a-clockwork-plex-camilladsp.service`: `MainPID=954`, `ActiveState=active`, `SubState=running`, `NRestarts=0`;
- route state remained `mode:"split-bus-selected"` with the canonical split-bus ALSA SHA;
- EQ state/config/route files retained expected root ownership and modes (`0600`, `0644`, `0644`).

Most importantly, the fault is independently reproducible without an EQ mutation:

- `GET /api/settings` returns HTTP `200`;
- `GET /settings` returns HTTP `500`.

This separates the currently reproducible failure from the unified Settings data API and from the healthy CamillaDSP process. The first observed EQ error may have coincided with, or been secondary to, the Settings/render failure; there is not yet evidence that CamillaDSP reload itself caused the HTTP 500.

## Current diagnosis boundary

Section 12 reboot acceptance remains **BLOCKED**. Section 13 repeat whole-appliance installation must not run yet.

The next diagnostic step is to trigger `GET /settings` on the **current boot** and immediately capture `a-clockwork-plex.service` journal output so the Flask/Jinja traceback for the reproducible HTTP 500 is preserved before another reboot. Because journald is volatile on this image, current-boot evidence must be copied into the Phase 7 evidence directory before rebooting.

Do not repeat NFC/alarm/repeat-install acceptance until `/settings` is restored to HTTP 200 and the reboot smoke is rerun.

PR #2 remains Draft, open and unmerged until explicit owner approval.
