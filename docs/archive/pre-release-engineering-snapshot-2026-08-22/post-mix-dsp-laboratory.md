# Post-mix DSP laboratory

The first A Clockwork Plex `alsaequal` backend was rolled back because the source `softvol` immediately before the equalizer made ALSA hardware-parameter negotiation fail. The EQ feature itself remains part of the project; only that backend arrangement is rejected.

## Confirmed bedroom appliance state

The physical Raspberry Pi DAC Pro currently runs at:

```text
44,100 Hz · S16_LE · stereo
period size 1024 · buffer size 8192
```

Plexamp Headless owns the physical DAC file descriptor through the shared `dmix` server. Shairport Sync and alarm playback join that shared mixer instead of opening the hardware device exclusively.

The production graph remains:

```text
Plexamp → source softvol ┐
AirPlay → source softvol ├→ Master softvol → dmix → hw:Pro,0
Alarm   → source softvol ┘
```

The DAC's `Digital` control is at `0 dB`, `Analogue Playback Boost` is disabled, and the A Clockwork Master control currently supplies the final software attenuation.

## EQ laboratory conclusion

The simple temporary route passed at 44.1 and 48 kHz, including 24- and 32-bit 48 kHz input:

```text
client plug → alsaequal → existing Master
```

It also survived twelve repeated opens and two concurrent source paths.

The exact rolled-back production order failed at every tested rate and format:

```text
client plug → source softvol → alsaequal → existing Master
```

This isolates the reproducible failure to the `softvol`/`alsaequal` ordering rather than AirPlay, concurrency or 48 kHz/24-bit library material.

The 96 kHz reference path failed separately with no negotiated rate. That remains a format-boundary question, not the cause of the original AirPlay connection failure.

## Temporary ALSA controls created by the tests

The EQ tests created these temporary user controls on the DAC card:

```text
A Clockwork EQ Lab C
A Clockwork EQ Lab D
A Clockwork EQ Lab Stage2
```

They are at `0 dB`, are not referenced by the production PCM graph and do not change the live source or Master levels. They may remain visible for the current boot, and ALSA state tools can preserve user controls if a state store occurs. Do not run `alsactl store` merely to clean them up. Leave them untouched until a deliberate cleanup procedure has been tested.

Future laboratories should place temporary controls on the loopback card rather than the physical DAC card.

## Why post-mix DSP is the preferred direction

Removing source trims would make the simple EQ route usable, but those trims are an intentional part of the mixer. Continuing to stack ALSA conversion plugins would reproduce the fragility we are trying to remove.

The preferred design is therefore:

```text
Plexamp source trim ┐
AirPlay source trim ├→ shared loopback mix → one DSP/EQ process → DAC
Alarm source trim   ┘
```

This preserves independent source calibration while providing one genuine Master EQ after the mix.

## Stage three: loopback-only transport probe

`scripts/test-dsp-loopback-lab.sh` tests the kernel ALSA Loopback transport without changing the production PCM graph or opening `hw:Pro,0`.

Prepare-only mode is the default:

```bash
bash scripts/test-dsp-loopback-lab.sh
```

The opt-in run:

```bash
bash scripts/test-dsp-loopback-lab.sh --run
```

The run:

1. records the physical DAC's live `hw_params`;
2. loads or reuses `snd_aloop` at fixed card index `7`;
3. performs finite 44.1/16, 48/32 and 96/32 loopback round trips;
4. performs concurrent 44.1/16 and 48/32 round trips on separate substreams;
5. confirms the physical DAC `hw_params` stayed unchanged;
6. attempts to unload only a loopback module that it loaded itself.

Loading `snd_aloop` changes the running kernel for the current boot only. WirePlumber or another desktop-audio process may open the new control device and prevent immediate unloading; the script reports that explicitly. A reboot clears a non-persistent module load.

### Confirmed stage-three result

The bedroom appliance exposed the requested module ID `ACP_Loopback` as ALSA card ID `ACPLoopback` at index `7`. The corrected probe discovered and used the actual card by numeric index.

All transport checks passed:

| Test | Result |
|---|---|
| 44.1 kHz / `S16_LE` round trip | PASS |
| 48 kHz / `S32_LE` round trip | PASS |
| 96 kHz / `S32_LE` round trip | PASS |
| Concurrent 44.1/16 and 48/32 substreams | PASS |
| Physical DAC unchanged | PASS |

The physical DAC remained at 44.1 kHz / `S16_LE` with period size 1024 and buffer size 8192 throughout. This proves the loopback transport needed for an isolated post-mix DSP path is available without disturbing production playback.

## Stage four: CamillaDSP loopback-only processing

`scripts/test-camilladsp-loopback-lab.sh` introduces an actual DSP engine while keeping both its input and output on separate `snd_aloop` substreams.

The laboratory is pinned to the official CamillaDSP `v4.1.3` Linux aarch64 ALSA build. It never installs the binary system-wide. The archive, executable, generated YAML, test signal and results remain under a temporary `/tmp/a-clockwork-plex-camilladsp.*` directory.

### Prepare only

```bash
bash scripts/test-camilladsp-loopback-lab.sh
```

This creates a 48 kHz / `S32_LE` stereo configuration and finite 997 Hz test signal. It performs no download and opens no audio device.

### Fetch and validate

```bash
bash scripts/test-camilladsp-loopback-lab.sh --fetch --lab-root /tmp/a-clockwork-plex-camilladsp.EXAMPLE
```

This stage:

1. fetches release metadata from the official `HEnquist/camilladsp` GitHub API;
2. selects `camilladsp-linux-aarch64.tar.gz` from release `v4.1.3`;
3. verifies the downloaded SHA-256 against GitHub's release-asset digest;
4. checks the reported binary version;
5. runs CamillaDSP's configuration checker;
6. opens no audio device.

### Finite DSP run

```bash
bash scripts/test-camilladsp-loopback-lab.sh --run --lab-root /tmp/a-clockwork-plex-camilladsp.EXAMPLE
```

The loopback route is:

```text
aplay test signal
  → hw:7,0,0
  → CamillaDSP capture hw:7,1,0
  → fixed −6 dB Gain filter
  → CamillaDSP playback hw:7,0,1
  → arecord capture hw:7,1,1
```

The output peak is measured against the generated input peak. The test passes only when the observed change is close to `−6 dB`, enough non-silent samples are captured, and the physical DAC's live `hw_params` are byte-for-byte unchanged.

This stage deliberately does not test the DAC, production source PCMs, Shairport or Plexamp. Its purpose is to prove that the selected CamillaDSP binary can parse the intended configuration, open the loopback endpoints and perform measurable processing.

## Promotion gates for a DSP backend

A post-mix backend must remain laboratory-only until it passes:

1. loopback transport at the chosen mix rate and format;
2. repeated DSP process starts and clean stops;
3. simultaneous Plexamp, AirPlay and alarm source input;
4. repeated Shairport connection, pause, resume and disconnect cycles;
5. Plexamp 44.1, 48 and 96 kHz source material;
6. neutral, boosted, cut and bypass EQ changes without clicks or stalls;
7. limiter and headroom validation;
8. service restart and reboot recovery;
9. a tested rollback to the current direct shared mixer.
