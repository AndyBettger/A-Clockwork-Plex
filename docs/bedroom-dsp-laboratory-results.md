# Bedroom post-mix DSP laboratory results

This file records the physical Raspberry Pi results gathered during the guarded Master EQ investigation. It is evidence for the laboratory branch only; it does not enable or install a production DSP route.

## Appliance

- Architecture: `aarch64`
- OS: Debian 13 (`trixie`)
- DAC: Raspberry Pi DAC Pro, ALSA card ID `Pro`
- Production DAC stream: 44,100 Hz, `S16_LE`, stereo
- Production period / buffer: 1024 / 8192 frames
- Loopback card: ALSA index 7, exposed as `ACPLoopback`
- CamillaDSP binary: official `v4.1.3` Linux aarch64 build

## Alsaequal root cause

The simple graph passed at 44.1 and 48 kHz and survived repeated and concurrent opens:

```text
client plug → alsaequal → existing Master
```

The exact rolled-back production graph failed at every tested rate and format:

```text
client plug → source softvol → alsaequal → existing Master
```

This isolated the AirPlay-breaking failure to the `softvol` immediately before `alsaequal`, not to AirPlay itself, simultaneous playback or 48 kHz / 24-bit source material.

## ALSA Loopback transport

All isolated transport tests passed:

| Test | Result |
|---|---|
| 44.1 kHz / `S16_LE` round trip | PASS |
| 48 kHz / `S32_LE` round trip | PASS |
| 96 kHz / `S32_LE` round trip | PASS |
| Concurrent 44.1/16 and 48/32 substreams | PASS |
| Physical DAC unchanged | PASS |

## CamillaDSP processing

The official archive digest matched GitHub's release metadata. The binary reported `CamillaDSP 4.1.3 (05e9cfc)` and accepted the generated 48 kHz / `S32_LE` loopback configuration.

A fixed `-6.0 dB` Gain filter produced a measured change of exactly `-6.000 dB`. CamillaDSP shut down normally and the physical DAC parameters were unchanged.

## Three-band response

The provisional three-band model is:

- Bass: 125 Hz low shelf, slope 6
- Mid: 1 kHz peaking filter, Q 0.7
- Treble: 4 kHz high shelf, slope 6

Measured with tones at 63 Hz, 1 kHz and 12 kHz:

| Profile | Bass | Mid | Treble | Result |
|---|---:|---:|---:|---|
| Neutral start | -0.000 dB | 0.000 dB | 0.000 dB | PASS |
| Bass +6 dB | +4.740 dB | +0.099 dB | 0.000 dB | PASS |
| Mid +6 dB | +0.052 dB | +6.000 dB | +0.057 dB | PASS |
| Treble +6 dB | +0.002 dB | +0.361 dB | +5.572 dB | PASS |
| Bass -6 dB | -4.740 dB | -0.099 dB | -0.000 dB | PASS |
| Mid -6 dB | -0.052 dB | -6.000 dB | -0.057 dB | PASS |
| Treble -6 dB | -0.002 dB | -0.361 dB | -5.572 dB | PASS |
| Neutral return | -0.000 dB | 0.000 dB | 0.000 dB | PASS |
| Physical DAC unchanged | — | — | — | PASS |

Eight finite CamillaDSP starts completed successfully. These values are normal shelf and peaking-filter responses: a shelf approaches its requested gain progressively rather than producing the full gain at every frequency below or above its corner.

## Next isolated gate

`scripts/test-camilladsp-live-headroom-lab.sh` keeps one CamillaDSP process running while it atomically replaces the active configuration and sends `SIGHUP` reloads. It tests:

1. Neutral, Bass, Mid and Treble response after live reloads;
2. return to Neutral;
3. all three bands at `+6 dB` with `-6.5 dB` automatic headroom;
4. a deliberately overloaded signal caught by a final hard limiter at `-1 dBFS`;
5. survival of one DSP process across every reload;
6. unchanged physical DAC parameters.

The script remains loopback-only and performs no production installation or routing change.
