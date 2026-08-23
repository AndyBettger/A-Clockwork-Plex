# Stage-seven physical DSP rehearsal result — 26 July 2026

This records the first guarded physical-DAC rehearsal on the bedroom appliance. The rehearsal was run twice because the first 180-second window was largely consumed by Plexamp interface recovery. Both runs automatically restored the original direct shared mixer with zero rollback failures.

## Physical audio route

All automated route and rollback checks passed:

| Check | Result |
|---|---|
| Rollback snapshot created before cutover | PASS |
| Physical DAC released after service stop | PASS |
| Temporary Loopback `dmix` route installed | PASS |
| CamillaDSP opened the physical DAC | PASS |
| Loopback capture supported rate adjustment | PASS |
| Physical route format | PASS — 44.1 kHz / `S16_LE` |
| Finite `-36 dBFS` tone route | PASS — tone was audible |
| Plexamp service restored on rehearsal route | PASS |
| Shairport Sync restored on rehearsal route | PASS |
| Dashboard restored on rehearsal route | PASS |
| CamillaDSP survived source-service startup | PASS |
| CamillaDSP stopped during rollback | PASS |
| Original ALSA checksum restored | PASS |
| Original service states restored | PASS |
| Mixer controls unchanged | PASS |
| Rollback failures | 0 |

During the rehearsal CamillaDSP negotiated the DAC as 44.1 kHz, `S16_LE`, stereo, `RW_INTERLEAVED`, period 512 and buffer 4096. After rollback the established direct mixer returned byte-for-byte to 44.1 kHz, `S16_LE`, stereo, `MMAP_INTERLEAVED`, period 1024 and buffer 8192.

## Manual audio observations

- The low-level 997 Hz route tone was audible.
- Plexamp playback was audible through CamillaDSP.
- AirPlay connected and audio was audible through CamillaDSP.
- AirPlay correctly paused Plexamp.
- No CamillaDSP process remained after either rollback.

These observations prove the physical post-mix route itself works for both primary sources and that the audio handoff action still reaches Plexamp.

## Control-plane issues exposed and resolved

The first rehearsal exposed two dashboard/restart issues:

1. Plexamp's embedded interface did not recover promptly after the service restart.
2. AirPlay audio played and Plexamp paused, but the dashboard did not initially switch to the AirPlay screen.

The AirPlay-screen race was fixed by preventing stale Plexamp playback state from overwriting an active AirPlay mode. Direct-mixer regression now confirms:

- AirPlay starts, pauses Plexamp and selects the AirPlay page;
- AirPlay disconnect returns to Clock;
- starting Plexamp playback while AirPlay is active pauses AirPlay.

The remaining silent-after-restart behaviour was traced to Plexamp Headless 4.12.4 rather than the dashboard, shared mixer or CamillaDSP. A temporary ALSA control-alias experiment was rejected and completely rolled back. After upgrading Plexamp through its bundled upgrade script, repeated `plexamp.service` restarts produced normal audio immediately without toggling the output device.

## Current decision

- Physical CamillaDSP audio route: **PASS**
- Automatic rollback: **PASS**
- Plexamp/AirPlay audio and bidirectional pause handoff on direct mixer: **PASS**
- Plexamp restart recovery after upgrade: **PASS**
- Temporary ALSA control aliases: **rejected and removed**
- Production DSP activation: **still blocked pending extended rehearsal**
- Draft PR #2: **remain draft and unmerged**

## Final stage-seven gate

Run one extended, mandatory-rollback physical rehearsal long enough to verify:

1. Plexamp starts and plays through CamillaDSP immediately after the controlled restart.
2. AirPlay starts, pauses Plexamp, selects the AirPlay page and plays through CamillaDSP.
3. Paused AirPlay retains the AirPlay page for the full ten-minute hold.
4. Starting Plexamp during an active AirPlay session pauses AirPlay and returns to Plexamp.
5. CamillaDSP remains alive with rate adjustment throughout the complete window.
6. The exact original ALSA checksum, mixer values and service states are restored with zero rollback failures.

A successful extended rehearsal is the promotion gate for designing the persistent restart-free CamillaDSP service and installer.
