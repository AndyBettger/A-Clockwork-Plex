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

## Live reload, headroom and limiter

`scripts/test-camilladsp-live-headroom-lab.sh` kept one CamillaDSP process running while atomically replacing the active YAML and sending seven `SIGHUP` reloads.

All checks passed:

| Profile | Frequency | Observed gain | Peak | Result |
|---|---:|---:|---:|---|
| Neutral start | 1 kHz | 0.000 dB | -27.959 dBFS | PASS |
| Bass live | 63 Hz | +4.740 dB | -23.040 dBFS | PASS |
| Mid live | 1 kHz | +6.000 dB | -21.957 dBFS | PASS |
| Treble live | 12 kHz | +5.572 dB | -22.380 dBFS | PASS |
| All boosts protected | 1 kHz | -0.039 dB | -27.892 dBFS | PASS |
| Neutral return | 1 kHz | 0.000 dB | -27.959 dBFS | PASS |
| Limiter threshold | overload signal | — | -1.000 dBFS | PASS |
| Single process survival | seven reloads | — | — | PASS |
| Physical DAC unchanged | — | — | — | PASS |

The provisional `-6.5 dB` automatic headroom offset cancelled the measured combined all-boost response at 1 kHz to within `0.039 dB` of neutral. The final hard limiter held a deliberately overloaded signal to exactly `-1.000 dBFS`, with 202,884 samples recorded at the threshold. CamillaDSP remained alive until the laboratory sent its normal shutdown signal.

The physical DAC remained byte-for-byte unchanged at 44.1 kHz / `S16_LE`, period 1024 and buffer 8192 throughout all loopback stages.

## Laboratory conclusion

The isolated evidence now proves that this Pi can support:

1. concurrent ALSA Loopback source transport;
2. CamillaDSP 48 kHz / `S32_LE` processing;
3. the intended Bass, Mid and Treble response;
4. repeated starts and clean shutdowns;
5. live in-process configuration reloads;
6. automatic boost headroom;
7. a final `-1 dBFS` safety ceiling;
8. complete isolation from the current physical DAC path.

This is enough to retire the failed `alsaequal` design and continue with CamillaDSP as the preferred post-mix backend candidate. It is not yet permission to install or activate that route in production.

## Next gate: controlled physical-audio rehearsal

The next meaningful test is the first one that will deliberately touch the physical audio path. It must therefore be separately approved and built as a reversible rehearsal with:

- an exact snapshot of the current ALSA files, mixer state and service state;
- no permanent module, package or startup changes during the first run;
- an automatically generated rollback command before any cutover;
- a very low-level finite test signal before ordinary music;
- verification that Plexamp and Shairport return to the known-good direct shared mixer;
- the dashboard EQ backend remaining offline until the rehearsal and rollback both pass.

Until that explicit approval, the production graph remains unchanged:

```text
Plexamp / AirPlay / Alarm → source trims → Master → dmix → hw:Pro,0
```
