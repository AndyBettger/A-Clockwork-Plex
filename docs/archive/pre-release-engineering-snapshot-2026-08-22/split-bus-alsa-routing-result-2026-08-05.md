# Split-bus ALSA source-lane routing result — 5 August 2026

This records the isolated ALSA source-routing laboratory run on the bedroom appliance after the CamillaDSP split-bus processing proof.

## Environment

- Host: `plexamp-bedroom`
- Branch head before the result record: `ea55daf9fcd11ac3975673dbe19cd158d795ed4c`
- ALSA Loopback: card 7, ID `ACPLoopback`
- Source format: 44,100 Hz, `S16_LE`, stereo
- Shared laboratory bus: 44,100 Hz, `S16_LE`, four channels
- Temporary music PCM: `acp_split_lab_music`
- Temporary alarm PCM: `acp_split_lab_alarm`
- Audio endpoints: `snd_aloop` only
- Physical DAC opened: no
- Production files, services, PCM definitions and mixer levels changed: no

## Measured result

| Profile | Channel 0 RMS | Channel 1 RMS | Channel 2 RMS | Channel 3 RMS | Result |
|---|---:|---:|---:|---:|---|
| Music lane | 1337.159 | 1337.159 | 0.000 | 0.000 | PASS |
| Alarm lane | 0.000 | 0.000 | 1337.159 | 1337.159 | PASS |
| Concurrent lanes | 1337.159 | 1337.159 | 1337.159 | 1337.159 | PASS |
| Physical DAC unchanged | — | — | — | — | PASS |

Failures: **0**

## Interpretation

The source-side arrangement required for the production topology is now proven:

1. An ordinary stereo music source maps only to four-channel bus lanes 0/1.
2. An ordinary stereo alarm source maps only to bus lanes 2/3.
3. The inactive lane remains digitally silent; no measurable cross-lane leakage occurred.
4. Music and alarm source PCMs can remain open concurrently through one four-channel `dmix` bus.
5. The physical DAC remained byte-for-byte unchanged throughout the laboratory.

Together with the preceding CamillaDSP result, both isolated halves of the design have passed:

```text
stereo source PCMs -> correct four-channel lanes       PASS
four-channel lanes -> isolated DSP, combine, limiter   PASS
```

## Promotion decision

Stage A2 — isolated ALSA source-lane routing: **PASS**

The project may proceed to the guarded Stage B real-service rehearsal. That rehearsal must remain time-limited and mandatory-rollback, retain the public `acp_plexamp`, `acp_airplay` and `acp_alarm` PCM names, make the existing Master control music-only, route alarm around Music Master and music EQ, combine both lanes before the final limiter, and restore the exact direct-mixer file, mixer levels and prior service states.

Production DSP activation remains blocked. The established direct shared mixer remains the rollback route, `scripts/install-master-eq.sh` remains blocked, and PR #2 remains Draft and unmerged pending explicit approval.
