# Split-bus DSP laboratory result — 5 August 2026

This records the isolated four-channel CamillaDSP split-bus laboratory run on the bedroom appliance.

## Environment

- Host: `plexamp-bedroom`
- Branch: `feature/alarm-engine`
- CamillaDSP: `4.1.3 (05e9cfc)`
- CamillaDSP binary: temporary verified official aarch64 release under `/tmp`
- ALSA Loopback: card 7, ID `ACPLoopback`
- Audio endpoints: `snd_aloop` only
- Physical DAC opened: no
- Production files, services, PCM definitions and mixer levels changed: no

Before the DSP run, the loopback transport passed at 44.1 kHz `S16_LE`, 48 kHz `S32_LE`, 96 kHz `S32_LE`, and concurrent 44.1/48 kHz operation. The physical DAC state remained unchanged.

The official CamillaDSP release digest, binary version and generated configuration all passed validation.

## Split-bus result

| Profile | Music gain | Alarm gain | Output peak | Result |
|---|---:|---:|---:|---|
| Neutral | +0.005 dB | +0.005 dB | −21.938 dBFS | PASS |
| Music Master isolation | −19.984 dB | 0.000 dB | −27.131 dBFS | PASS |
| Music EQ isolation | +6.002 dB | +0.008 dB | −18.430 dBFS | PASS |
| Final limiter stress | +5.883 dB | −11.372 dB | −1.000 dBFS | PASS |
| Physical DAC unchanged | — | — | — | PASS |
| Single-process survival | — | — | — | PASS |

Failures: **0**

## Interpretation

The measurements confirm the required processing order:

1. Music Master and music EQ affect only the music lane.
2. The alarm lane bypasses Music Master and music EQ.
3. Music and alarm combine only after music-only processing.
4. The final safety limiter protects the combined output.

The limiter stress profile deliberately overdrives the combined signal. Its alarm attenuation is therefore expected final-stage protection and is not evidence that Music Master or music EQ has leaked onto the alarm lane.

## Promotion decision

Stage A — isolated split-bus DSP proof: **PASS**

The project may proceed to Stage B: a time-limited, mandatory-rollback real-service rehearsal that temporarily routes Plexamp and AirPlay through the music lane and scheduled alarm playback through the alarm lane.

Stage B must still prove:

- Plexamp and AirPlay use the music lane;
- a real scheduled alarm uses the independent alarm lane;
- Music Master at zero silences music without reducing the alarm;
- music EQ, EQ bypass and automatic music headroom do not alter alarm level;
- alarm takeover, Snooze and Dismiss remain correct;
- paused AirPlay retains its ten-minute hold;
- Plexamp reclaim still pauses AirPlay;
- exact ALSA files, mixer values and prior service states are restored;
- the direct shared mixer is audible after rollback;
- no CamillaDSP process remains after rollback.

Production DSP activation remains blocked. The existing direct shared ALSA mixer remains the known-good route, the bare `scripts/install-master-eq.sh` installer remains blocked, and PR #2 remains Draft and unmerged pending explicit approval.
