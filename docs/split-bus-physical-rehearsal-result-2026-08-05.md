# Split-bus physical rehearsal result — 5 August 2026

Status: **PASS**. The temporary route was fully rolled back. Persistent production activation remains blocked pending the guarded Stage C installation, forced-failure and reboot checks.

## Environment

- Host: `plexamp-bedroom`
- CamillaDSP: 4.1.3 (`05e9cfc`)
- Rehearsal window: 1500 seconds maximum
- Capture: four channels at 44.1 kHz / S16_LE
- Bus lanes: music L/R on channels 0/1; alarm L/R on channels 2/3
- Output: stereo through the final −1.0 dBFS safety limiter
- Laboratory root: `/var/tmp/a-clockwork-plex-split-bus-physical.VnxZJH`

## Automated activation gates

Every automated gate passed:

| Gate | Result | Observation |
|---|---:|---|
| ALSA configuration parse | PASS | Temporary split-bus fragment parsed |
| CamillaDSP configuration check | PASS | Verified CamillaDSP 4.1.3 |
| Rollback snapshot | PASS | Exact state captured before activation |
| Physical DAC released | PASS | No playback owner remained after guarded service stop |
| Temporary ALSA route | PASS | Four-channel split bus installed |
| CamillaDSP physical start | PASS | One DSP process opened the real DAC |
| Loopback rate adjustment | PASS | Capture clock tuning available |
| Physical DAC format | PASS | 44.1 kHz / S16_LE |
| Music-lane finite tone | PASS | Low-level signal reached the music route |
| Alarm-lane finite tone | PASS | Low-level signal reached the independent alarm route |
| Plexamp service restoration | PASS | Active through the temporary route |
| Shairport Sync restoration | PASS | Active through the temporary route |
| Dashboard service restoration | PASS | Active through the temporary route |
| Route survival | PASS | CamillaDSP survived real-service startup |

## Manual acceptance

| Check | Result |
|---|---:|
| Plexamp started and sounded normal | PASS |
| AirPlay started normally and paused Plexamp | PASS |
| Paused AirPlay was retained while its sender remained connected | PASS |
| Music Master at 0% silenced music | PASS |
| A real scheduled alarm remained audible at Music Master 0% | PASS |
| Alarm takeover screen and music priority worked | PASS |
| Snooze stopped the alarm and the alarm returned after the configured minute | PASS |
| Dismiss ended the occurrence | PASS |
| Restoring Music Master restored audible music | PASS |

The central architecture requirement is therefore physically proven: Plexamp and AirPlay pass through Music Master and music processing, while scheduled alarm audio bypasses those controls and rejoins only before the final limiter.

## AirPlay pause-hold observation

The Shairport exit hook recorded a paused sender as available at approximately 01:39:54. The persisted playback runtime later recorded:

```json
{
  "last_reason": "sender-disconnected-during-hold",
  "phase": "disconnected",
  "updated_at": "2026-08-05T01:47:46.765+01:00"
}
```

The dashboard opened `/clock` immediately afterwards at 01:47:47. The sender therefore remained available for approximately 7 minutes 53 seconds after the pause event, then genuinely disconnected. The coordinator correctly ended the hold immediately rather than retaining a dead session until its former ten-minute ceiling.

The agreed product policy is now:

> Retain paused AirPlay for up to seven minutes while the sender remains connected. Release immediately after a genuine sender disconnect.

The default is 420 seconds. No artificial Play, Pause or volume commands are sent as keepalives because they are real user-visible controls and could interfere with playback arbitration or alarm priority.

## Mandatory rollback

Ctrl-C invoked the normal rollback path. Every recorded rollback check passed:

| Rollback check | Result |
|---|---:|
| CamillaDSP stopped | PASS |
| Original ALSA checksum restored | PASS |
| Plexamp service state restored | PASS |
| Shairport Sync service state restored | PASS |
| Dashboard service state restored | PASS |
| Original displayed mixer levels restored | PASS |

No CamillaDSP process remained and the known-good direct shared mixer was active again.

The rehearsal prompted for the sudo password again during Ctrl-C rollback because the background credential refresher received the same interrupt as the foreground script. The follow-up script change makes that refresher ignore SIGINT until rollback explicitly terminates it. The prepare-only activation example is also changed to print the selected duration instead of a hard-coded 1200 seconds.

## Promotion decision

- Stage A isolated DSP processing: **PASS**
- Stage A2 isolated ALSA source routing: **PASS**
- Stage B real-service/DAC rehearsal: **PASS**
- Exact mandatory rollback: **PASS**
- Persistent split-bus production activation: **not yet approved**
- Draft PR #2: remains Draft, open and unmerged

The next engineering stage is a guarded persistent installer with exact-state backup, managed CamillaDSP service ownership, automatic failback and deliberate forced-failure/reboot validation.
