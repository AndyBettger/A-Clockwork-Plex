# Master EQ laboratory and controlled testing

The **Master EQ feature remains part of A Clockwork Plex**. Its Bass, Mid and Treble controls, restricted API, neutral response, bypass behaviour and saved-curve design are being preserved.

The first ALSA `alsaequal` backend was rolled back after its modified source PCMs could fail hardware-parameter negotiation. Plexamp could sometimes open the path, while Shairport Sync could fail to open `acp_airplay`, causing the iPhone to report that it could not connect.

Production installation is therefore deliberately blocked while the plugin order and sample-format boundaries are diagnosed.

## Current production audio path

The known-good shared path is:

```text
Plexamp player → acp_plexamp trim ┐
AirPlay sender → acp_airplay trim ├→ acp_master → acp_dmix → DAC
Alarm fade     → acp_alarm trim   ┘
```

The current `acp_dmix` base format is fixed at:

```text
44,100 Hz · S16_LE · stereo
```

Each source-facing `plug` PCM converts incoming material to that shared format. This means higher-rate or higher-bit-depth Plexamp material is currently converted before reaching the DAC; that is a separate design decision to revisit after the EQ backend is stable.

## What is blocked

This command no longer installs anything:

```bash
sudo bash scripts/install-master-eq.sh
```

A bare invocation exits with an explanation. It does not install packages, rewrite `/etc/alsa`, modify Shairport Sync or restart services.

Rollback remains available:

```bash
sudo bash scripts/install-master-eq.sh --rollback
```

Do not run rollback on an already healthy rolled-back installation unless a later experiment has actually changed the production files.

## Isolated laboratory harness

The laboratory harness creates a temporary ALSA configuration beneath `/tmp`. It does **not** edit:

- `/etc/alsa`;
- `/etc/shairport-sync.conf`;
- systemd services;
- `config.json`;
- dashboard runtime state;
- Plexamp or AirPlay settings.

Prepare the laboratory without opening the DAC:

```bash
cd ~/A-Clockwork-Plex
bash scripts/install-master-eq.sh --experimental-lab
```

This is equivalent to:

```bash
bash scripts/test-master-eq-lab.sh --prepare-only
```

The command prints the temporary directory and generated `asound.conf`. Nothing is played and no service is restarted.

## Finite silent tests

Only run this stage while ordinary Plexamp and AirPlay playback are paused:

```bash
cd ~/A-Clockwork-Plex
bash scripts/install-master-eq.sh --experimental-lab --run
```

The test uses digital silence and finite one-second `aplay` opens. It still opens the existing shared Master PCM and physical DAC, so it is deliberately opt-in.

The harness tests four plugin orders:

```text
A. input plug → equal → existing Master
B. input plug → equal → output plug → existing Master
C. input plug → softvol → equal → output plug → existing Master
D. input plug → equal → softvol → existing Master
```

Each path is tested with:

| Rate | ALSA format |
|---:|---|
| 44.1 kHz | `S16_LE` |
| 48 kHz | `S16_LE` |
| 48 kHz | `S24_LE` |
| 48 kHz | `S32_LE` |
| 96 kHz | `S24_LE` |
| 96 kHz | `S32_LE` |

A final concurrency test opens one temporary path at 44.1 kHz and another at 48 kHz through the existing shared mixer at the same time.

## Results

The harness prints and preserves a directory such as:

```text
/tmp/a-clockwork-plex-eq-lab.A1b2C3
```

Important files are:

```text
asound.conf    generated temporary ALSA graph
results.tsv    pass/fail matrix
report.txt     environment, controls and full summary
*.log          stderr/stdout for each PCM-format test
```

A clean result is not yet permission to install the backend. It only proves that a particular temporary PCM arrangement can negotiate finite silent streams on that Pi.

## How to interpret failures

### Every variant fails

Likely areas include:

- `alsaequal` or CAPS plugin availability;
- the floating-point format expected by `alsaequal`;
- incompatibility between the equalizer and the downstream Master/dmix path;
- the temporary control file failing to initialise.

Check `report.txt` and the first failing log before changing the graph.

### A passes but B, C or D fails

The additional conversion or `softvol` stage is introducing an incompatible hardware-parameter interval. Keep the successful path as the next candidate and reduce the graph rather than adding more `plug` layers blindly.

### 44.1 kHz passes but 48/96 kHz fails

The source-side `plug` is not successfully converting that format before the equalizer, or the equalizer is exposing constraints that prevent conversion.

### Single streams pass but concurrency fails

The EQ graph can open the shared output alone but is not safe for simultaneous Plexamp, AirPlay and alarm sources. It must not be promoted to production.

## Useful manual diagnostics

Use the generated config path printed by the harness:

```bash
export ALSA_CONFIG_PATH=/tmp/a-clockwork-plex-eq-lab.EXAMPLE/asound.conf

aplay -L | grep -A2 acp_lab
amixer -D acp_lab_equal scontrols
amixer -D acp_lab_equal scontents
```

A single finite test can then be repeated with its errors visible:

```bash
timeout 4 aplay -D acp_lab_b -f S16_LE -r 48000 -c 2 -d 1 /dev/zero
```

Unset the temporary configuration afterwards:

```bash
unset ALSA_CONFIG_PATH
```

## Safety limits retained for the eventual backend

The user-facing feature still targets:

- Bass, Mid and Treble limited to `−6 dB` through `+6 dB`;
- `0.5 dB` steps;
- per-band centre reset;
- full **Neutral** action;
- **Bypass** that remembers the previous curve;
- reduced Master level during positive-gain testing;
- scheduled alarm playback remaining locked.

## Promotion criteria

An EQ backend should not return to the production graph until all of the following are true:

1. every required source format passes finite negotiation;
2. at least two temporary source paths pass concurrently;
3. Shairport Sync connects repeatedly without sender rejection or immediate pause;
4. Plexamp plays 44.1, 48 and higher-rate library material without stalls;
5. neutral, boosted, cut and bypass responses work without clicks or service restarts;
6. the working graph survives service and Pi restarts;
7. rollback is retested from a fresh backup;
8. complete Plexamp/AirPlay/alarm handoff regression tests pass.

Until then, the dashboard should report **Backend offline** and retain disabled EQ controls rather than suggesting production installation.
