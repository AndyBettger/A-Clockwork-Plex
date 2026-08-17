# Post-reboot host filesystem failure — 2026-08-17

Target: brand-new SanDisk Extreme A2 acceptance SD card on `plexamp-test`. The accepted production SD card remained removed and untouched.

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

## Second boot narrowed the fault

The previous boot could not be recovered because this image currently has no persistent journald store: `journalctl -b -1` reported `Specifying boot ID or boot offset has no effect, no persistent journal was found.`

On the next boot, the operator repeated Plexamp playback and live EQ adjustment before diagnosis commands were issued. This time the EQ mutation worked normally. Health evidence showed:

- `GET /api/audio/eq`: healthy `split-bus-active` state, no error, Bass `+2.0 dB`, Mid `0.0 dB`, Treble `+2.0 dB`;
- the restricted EQ helper reported the same healthy state;
- `a-clockwork-plex-camilladsp.service`: `MainPID=954`, `ActiveState=active`, `SubState=running`, `NRestarts=0`;
- route state remained `mode:"split-bus-selected"` with the canonical split-bus ALSA SHA;
- EQ state/config/route files retained expected root ownership and modes (`0600`, `0644`, `0644`).

The Settings data API remained healthy (`GET /api/settings` -> HTTP 200), while `GET /settings` reproducibly returned HTTP 500.

## Root cause boundary discovered from the current journal

The current-boot journal proves the HTTP 500 is **not a template/Jinja failure and not evidence of a CamillaDSP reload failure**. The host root filesystem has entered ext4 emergency read-only state after a real SD-card write failure.

The exact `/settings` failure chain is:

- `dashboard_core.settings()` calls `set_mode("settings")`;
- `set_mode()` calls `save_json(STATE_PATH, state)`;
- `save_json()` attempts to open `/home/andy/A-Clockwork-Plex/state.json.tmp` for writing;
- the filesystem returns `OSError: [Errno 30] Read-only file system`;
- Flask therefore returns HTTP 500 for `/settings`.

Independent corroboration exists in the same boot:

- repeated Ecowitt POSTs fail at the same `save_json()` write with `Errno 30` and return HTTP 500;
- an attempt to save the diagnostic journal into the Phase 7 evidence directory fails with `Read-only file system`, so `47-current-settings-500-journal.txt` is never created;
- read-only APIs and already-running audio services continue working, explaining why EQ status and Plexamp playback can appear healthy while state-changing dashboard operations fail.

## Kernel/MMC evidence

The second boot began normally. The kernel discovered the 128 GB SD card as `mmcblk0` / `SM128`, negotiated UHS-I SDR104, initially mounted the ext4 root read-only for recovery, then remounted it read/write normally.

At `2026-08-17 22:00:42` the storage path then failed during a write flush:

```text
mmc0: error -84 writing Cache Flush bit
I/O error, dev mmcblk0, sector 9846696 op 0x1:(WRITE)
Aborting journal on device mmcblk0p2-8.
EXT4-fs error (device mmcblk0p2): ext4_journal_check_start:87: ... Detected aborted journal
EXT4-fs (mmcblk0p2): Remounting filesystem read-only
```

After that point application writes repeatedly fail with `Errno 30`.

`findmnt` and `/proc/mounts` expose the ext4 mount as `rw,noatime,emergency_ro`; this is consistent with ext4 emergency-read-only handling rather than proof that normal writes are allowed. The write failures and kernel journal-abort evidence are authoritative for the acceptance result.

Power telemetry on this boot returned `vcgencmd get_throttled` -> `throttled=0x0`, and the searched journal showed no undervoltage messages. There is therefore no current evidence that an undervoltage event caused this specific failure.

The card is a **brand-new SanDisk Extreme A2**, so ordinary age/wear of an old spare is not a credible explanation. Remaining host-level candidates include a defective card/controller, counterfeit or faulty media, SD socket/contact/signal-integrity problems, or another MMC/host interaction. This evidence does not yet distinguish among them.

This reclassifies the observed failure as a **host/storage/filesystem durability failure on the acceptance SD appliance**, not an A Clockwork Plex EQ or Settings application regression at the current evidence boundary.

## Current diagnosis boundary

Section 12 reboot acceptance remains **BLOCKED**, now on host filesystem/storage health. Section 13 repeat whole-appliance installation must not run while ext4 is in emergency read-only state.

Do not attempt an in-place `mount -o remount,rw /` or run a repairing filesystem check against the mounted root merely to continue acceptance. Preserve the current card state and diagnose/repair the filesystem offline, then verify the media/SD path before trusting the card for the remaining durability tests.

After the acceptance-card filesystem/storage issue is repaired or the card is replaced, rerun the reboot checkpoint from a writable root and confirm `/settings`, Ecowitt state writes, NFC and Music Master/alarm isolation before proceeding to repeat-install acceptance.

PR #2 remains Draft, open and unmerged until explicit owner approval.
