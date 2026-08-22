# Stage seven: rollback-first physical DSP rehearsal

This stage is the first A Clockwork Plex DSP test that deliberately opens the physical Raspberry Pi DAC Pro. It is a temporary maintenance rehearsal, not a production installer.

## Safety boundary

The default invocation is prepare-only. It writes only to a private directory under `/var/tmp`, generates the temporary ALSA and CamillaDSP configurations, creates a one-second `-36 dBFS` test signal, and validates both configurations. It does not use `sudo`, stop services, open audio or alter mixer controls.

Physical activation requires all of the following:

- `--activate`;
- the literal confirmation token `--confirm STAGE-SEVEN-REAL-DAC`;
- an explicit verified CamillaDSP 4.1.3 aarch64 binary path;
- an existing ALSA Loopback card at the already-tested index 7;
- the known-good direct shared mixer still present at `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`.

There is deliberately no keep-active or no-rollback option.

## Temporary route

The public application PCMs and all four existing softvol controls retain their names and ranges:

```text
Plexamp → A Clockwork Plexamp ┐
AirPlay → A Clockwork AirPlay ├→ A Clockwork Master → rehearsal dmix
Alarm   → A Clockwork Alarm   ┘
```

Only the final dmix sink changes during the rehearsal:

```text
rehearsal dmix
  → hw:7,0,0
  → ALSA Loopback paired capture hw:7,1,0
  → CamillaDSP neutral Bass/Mid/Treble + headroom + -1 dBFS limiter
  → hw:CARD=Pro,DEV=0
```

The rehearsal stays at the known-good physical format:

```text
44,100 Hz · S16_LE · stereo
period 1024 · buffer 8192
```

CamillaDSP uses `chunksize: 1024`, `target_level: 2048`, `adjust_period: 1` and `enable_rate_adjust: true`. ALSA Loopback capture clock tuning is preferred for matching the virtual capture clock to the physical DAC clock without an asynchronous resampler.

The rehearsal dmix uses IPC key `1094932536`, separate from production key `1094931536`, so no stale production dmix server can retain the old hardware sink.

## Snapshot and rollback

Before changing the live ALSA fragment, the activation path records:

- whether `plexamp.service`, `shairport-sync.service` and `a-clockwork-plex.service` were active and enabled;
- an exact `cp -a` snapshot and SHA-256 of the live ALSA fragment;
- mixer-helper status JSON;
- current physical DAC `hw_params`;
- current physical DAC owners.

The services are stopped in reverse order, the physical DAC must become owner-free, and only then is the temporary ALSA fragment installed. CamillaDSP must start successfully and open the DAC at exactly 44.1 kHz / `S16_LE` before a finite low-level signal is sent through `acp_plexamp`.

On normal completion, timeout, Ctrl-C, TERM or any error after the snapshot, the exit trap:

1. stops the three managed services;
2. stops CamillaDSP;
3. restores the exact original ALSA fragment;
4. restarts only services that were active before the rehearsal;
5. verifies the original ALSA checksum;
6. verifies CamillaDSP is no longer running;
7. records mixer state and restored DAC parameters.

A background `sudo -n true` keepalive preserves the already-authorised sudo timestamp during an extended test window; it grants no new command permissions.

## Prepare-only command

```bash
cd ~/A-Clockwork-Plex

git pull --ff-only
bash scripts/run-tests.sh

CAM=/tmp/a-clockwork-plex-camilladsp.E5FBfN/bin/camilladsp

bash scripts/test-camilladsp-physical-rehearsal.sh \
  --prepare-only \
  --binary "$CAM"
```

Inspect the directory printed by the script before activation:

```bash
PHYSICAL_LAB="$(find /var/tmp -maxdepth 1 -type d \
  -name 'a-clockwork-plex-dsp-physical.*' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"

cat "$PHYSICAL_LAB/results.tsv"
cat "$PHYSICAL_LAB/report.txt"
cat "$PHYSICAL_LAB/99-a-clockwork-plex-rehearsal.conf"
cat "$PHYSICAL_LAB/camilladsp-physical.yml"
```

## Activation command

Do not run this until the generated prepare-only output has been reviewed:

```bash
bash scripts/test-camilladsp-physical-rehearsal.sh \
  --activate \
  --confirm STAGE-SEVEN-REAL-DAC \
  --binary "$CAM" \
  --lab-root "$PHYSICAL_LAB" \
  --duration 180
```

The active window accepts Enter for immediate rollback and always times out. A duration from 30 to 900 seconds is allowed. A window of at least 660 seconds is required to observe the complete ten-minute paused-AirPlay dashboard hold; the first physical rehearsal should remain shorter and focus on basic Plexamp, AirPlay, service and rollback behaviour.

## Promotion remains blocked

Passing stage seven would demonstrate a reversible physical route at the current format. It would not install CamillaDSP, persist `snd_aloop`, add a systemd DSP service, enable the dashboard EQ backend or merge PR #2. Those remain later, separately approved gates.
