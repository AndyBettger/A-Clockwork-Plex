# Production EQ split-bus design

Status: Stage A isolated split-bus proof passed on the bedroom Pi; guarded Stage B real-service rehearsal remains pending and production activation remains blocked.

## User requirement

Listening quietly in the evening must never make the next scheduled alarm quiet. The persistent alarm control is therefore an independent ceiling, not another source trim under the music master.

The Settings labels become:

- **Music master volume** — persistent overall level for Plexamp and AirPlay only.
- **Plexamp trim** — downstream calibration after Plexamp's own player volume.
- **AirPlay trim** — downstream calibration after the AirPlay sender volume.
- **Maximum alarm volume** — independent ceiling for scheduled alarm playback.

Each alarm keeps its own starting volume, target volume and fade. Those values shape the alarm within the independent maximum; they are not multiplied by Music Master.

## Target signal graph

```text
Plexamp player volume -> Plexamp trim --\
                                         +-> Music Master -> music EQ/headroom --\
AirPlay sender volume -> AirPlay trim ---/                                      \
                                                                                  +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume -------------------------------/
```

The final limiter is the only processing deliberately shared by music and alarm.

## CamillaDSP channel plan

The guarded DSP route uses a four-channel loopback capture stream:

| Capture channel | Meaning |
|---|---|
| 0 | Music left |
| 1 | Music right |
| 2 | Alarm left |
| 3 | Alarm right |

CamillaDSP applies Music Master, Bass, Mid, Treble and automatic music headroom only to channels 0 and 1. A 4-to-2 mixer then adds channel 0 to 2 and channel 1 to 3. The resulting stereo pair passes through the final safety limiter and then reaches the DAC.

This ordering is mandatory:

1. Music-only processing on channels 0/1.
2. Alarm bypass on channels 2/3.
3. Music and alarm combine into stereo.
4. Final limiter.
5. Physical DAC.

Moving the limiter before the mixer would leave alarm outside the final safety protection. Moving the alarm combine before Music Master or EQ would recreate the original problem.

## Volume ownership

### Music

Normal music loudness is the product of the source's own live volume, its persistent source trim and Music Master. EQ headroom may add attenuation when a positive EQ boost requires it.

### Alarm

Alarm loudness is determined by:

1. the selected tone's normalised internal level;
2. the configured alarm start and target values;
3. the configured fade time;
4. Maximum Alarm Volume;
5. the final limiter only when necessary.

Music Master, music EQ, EQ bypass and automatic music headroom must not alter alarm loudness.

The existing `scheduled_volume_cap_percent` must not remain as a second user-facing maximum. During migration it should either be retired or fixed internally at 100%, while browser previews keep their separate deliberately quiet safety cap.

## Required settings descriptions

**Music master volume**

> Persistent overall level for Plexamp and AirPlay. Does not affect scheduled alarms.

**Maximum alarm volume**

> Independent output ceiling for alarm playback. Alarm starting and target volumes cannot exceed this level, and it is not affected by Music Master.

## Rollback rule

The current direct shared ALSA mixer remains the known-good rollback route until the guarded split-bus installation passes all rehearsals. `scripts/install-shared-audio.sh` is not repurposed into the DSP installer.

The blocked bare installer remains blocked:

```text
sudo bash scripts/install-master-eq.sh
```

No persistent DSP activation may rely on that installer or the rejected `alsaequal` graph.

## Laboratory stages

### Stage A — isolated split-bus DSP proof

`scripts/test-camilladsp-split-bus-lab.sh` uses `snd_aloop` only. It verifies:

- neutral music and alarm both pass at approximately unity gain;
- Music Master at -20 dB attenuates music while alarm remains approximately unchanged;
- a +6 dB music EQ adjustment changes music while alarm remains approximately unchanged;
- the final limiter catches a deliberately excessive combined signal;
- one CamillaDSP process survives all live reloads;
- physical DAC state remains unchanged.

Stage A passed on `plexamp-bedroom` on 5 August 2026 with CamillaDSP 4.1.3. Music Master measured −19.984 dB on music and 0.000 dB on alarm; music EQ measured +6.002 dB on music and +0.008 dB on alarm; the final limiter held the combined stress signal at −1.000 dBFS. See `docs/split-bus-dsp-laboratory-result-2026-08-05.md`.

### Stage B — temporary real-service route

After Stage A passes on the Pi, a mandatory-rollback rehearsal may temporarily route Plexamp, AirPlay and alarm into their separate loopback lanes. It must prove:

- Plexamp and AirPlay use the music lane;
- scheduled alarm uses the alarm lane;
- Music Master at 0% silences music but not alarm;
- the ten-minute paused-AirPlay hold still works;
- alarm takeover, Snooze and Dismiss still work;
- rollback restores exact files, controls, services and direct-mixer audio.

### Stage C — guarded persistent install

Persistent activation requires:

- exact-state backups;
- a managed CamillaDSP service;
- neutral or bypass-safe startup;
- health reporting that distinguishes direct rollback mode from active split-bus DSP mode;
- automatic failback to the direct mixer when validation or startup fails;
- no silent partial state where music works but AirPlay or alarm cannot open its PCM.

## Acceptance criteria

The production route is not approved until all of the following are true:

1. Music Master at 0% silences Plexamp and AirPlay.
2. Music Master at 0% does not reduce a real scheduled alarm.
3. Bass, Mid and Treble changes do not alter alarm level or tone balance.
4. EQ bypass and automatic headroom do not alter alarm level.
5. Maximum Alarm Volume caps scheduled alarms across reboot.
6. Per-alarm target values above the maximum are audibly and measurably capped.
7. Preview volume remains separately limited and cannot be mistaken for scheduled alarm loudness.
8. The final limiter protects a combined music-plus-alarm signal.
9. NFC playback, AirPlay handoff, rapid iPhone resume, ten-minute hold and alarm takeover still pass.
10. Forced CamillaDSP failure returns the appliance to the direct shared mixer without manual ALSA repair.

## Production activation status

Stage A passed. Production activation remains blocked pending the mandatory-rollback Stage B real-service rehearsal and the later guarded persistent installation design. PR #2 remains Draft and must not be merged without explicit approval.
