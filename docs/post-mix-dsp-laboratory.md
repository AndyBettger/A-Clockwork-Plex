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
2. loads `snd_aloop` at the fixed card index `7` with ID `ACP_Loopback`;
3. performs finite 44.1/16, 48/32 and 96/32 loopback round trips;
4. performs concurrent 44.1/16 and 48/32 round trips on separate substreams;
5. confirms the physical DAC `hw_params` stayed unchanged;
6. attempts to unload a loopback module that it loaded.

Loading `snd_aloop` changes the running kernel for the current boot only. WirePlumber or another desktop-audio process may open the new control device and prevent immediate unloading; the script reports that explicitly. A reboot clears a non-persistent module load.

No CamillaDSP binary is downloaded or executed in this stage.

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
