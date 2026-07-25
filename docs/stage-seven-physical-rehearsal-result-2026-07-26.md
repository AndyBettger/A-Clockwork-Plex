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

## Control-plane issues exposed

The rehearsal is not yet promoted because it exposed two dashboard recovery defects:

1. On the first run, Plexamp audio recovered before its embedded web interface. The persistent iframe remained disconnected long enough that the Now Playing screen was not usable during most of the 180-second window.
2. On the second run, AirPlay audio played and Plexamp paused, but the dashboard did not switch to the AirPlay screen.

The AirPlay-screen failure was traced to `mode-watch.js`. Its protection against a stale AirPlay-end event reasserted Plexamp mode whenever the Plexamp overlay was open and the live snapshot still briefly said `playing`. During AirPlay START that stale playback state could overwrite the new `airplay` mode before the pause became visible.

The fix restricts that repair to `requestedMode === "clock"` while no AirPlay session is active. It therefore still protects the completed AirPlay-to-Plexamp handoff but cannot override AirPlay START.

The first-run iframe problem is addressed by remembering dashboard API outages and reloading the persistent Plexamp iframe shortly after `/api/status` becomes available again. This gives the restarted Plexamp service a fresh embedded client instead of relying on a disconnected iframe to recover itself.

## Current decision

- Physical CamillaDSP audio route: **PASS**
- Automatic rollback: **PASS**
- Plexamp/AirPlay audio and pause handoff: **PASS**
- Dashboard control-plane recovery: **fix committed; regression test still required on the appliance**
- Production DSP activation: **still blocked**
- Draft PR #2: **remain draft and unmerged**

The next step is a normal direct-mixer dashboard regression after pulling the JavaScript fix. A further physical rehearsal should happen only after AirPlay reliably selects the AirPlay screen and the Plexamp iframe recovers after a controlled service restart.
