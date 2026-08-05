# Stage C0 direct alarm-bypass failback result — 5 August 2026

Status: **PASS**. The temporary direct no-DSP failback route was physically validated on `plexamp-bedroom` and then rolled back exactly. No route was retained.

## Purpose

Stage C0 proves the route that a future CamillaDSP watchdog can select after a DSP failure:

```text
Plexamp -> Plexamp trim --\
                          +-> Music Master -> stereo dmix -> DAC
AirPlay -> AirPlay trim --/
Alarm -> Maximum Alarm Volume -----------> stereo dmix -> DAC
```

The route deliberately loses music EQ, automatic headroom and the final DSP limiter, but it preserves the critical guarantee that Music Master cannot silence a scheduled alarm.

## Preparation

The prepare-only run used:

- laboratory directory: `/var/tmp/a-clockwork-plex-direct-failback.dygMWN`
- candidate ALSA file: `/var/tmp/a-clockwork-plex-direct-failback.dygMWN/99-a-clockwork-plex-direct-alarm-bypass.conf`
- format: 44.1 kHz / S16_LE / stereo
- maximum rehearsal duration: 900 seconds

The isolated ALSA configuration parsed successfully. Prepare-only changed no production file, service, mixer level or route and did not open the physical DAC.

## Automated activation gates

Every automated gate passed:

| Gate | Result | Observation |
|---|---:|---|
| ALSA configuration parse | PASS | Temporary direct failback fragment parsed |
| Rollback snapshot | PASS | Exact state captured before activation |
| Physical DAC released | PASS | No playback owner remained after guarded service stop |
| Temporary direct failback route | PASS | Alarm bypassed Music Master |
| Music PCM finite probe | PASS | Low-level signal opened the music route |
| Physical DAC format | PASS | 44.1 kHz / S16_LE |
| Alarm PCM finite probe | PASS | Low-level signal opened the independent alarm route |
| Plexamp service restoration | PASS | Active through the temporary route |
| Shairport Sync restoration | PASS | Active through the temporary route |
| Dashboard service restoration | PASS | Active through the temporary route |

The original Music Master was 100%.

## Manual acceptance

| Check | Result | Observation |
|---|---:|---|
| Plexamp playback | PASS | Sounded normal |
| AirPlay takeover | PASS | Started normally and paused Plexamp |
| Music Master at 0% | PASS | Music became silent — “silence is golden” |
| Plexamp/AirPlay silence | PASS | Confirmed |
| Real scheduled alarm at Music Master 0% | PASS | Alarm remained clearly audible |
| Alarm screen takeover | PASS | Confirmed |
| Snooze, repeated ring and Dismiss | PASS | All confirmed |
| Restore Music Master | PASS | Returned to the original value |
| Music after restore | PASS | Audible again |

The central failback requirement is therefore physically proven: a no-DSP route can preserve normal Plexamp/AirPlay behaviour and Music Master while keeping scheduled alarm audio independent.

## Exact rollback

Pressing Enter invoked the normal rollback path. Every rollback check passed:

| Rollback check | Result |
|---|---:|
| Original ALSA checksum restored | PASS |
| Plexamp service state restored | PASS |
| Shairport Sync service state restored | PASS |
| Dashboard service state restored | PASS |
| Original displayed mixer levels restored | PASS |
| Rollback failures | **0** |

The exact original direct shared mixer became active again and no Stage C0 route remained installed.

## Promotion decision

- Stage A isolated split-bus DSP: **PASS**
- Stage A2 isolated source-lane routing: **PASS**
- Stage B temporary split-bus real-service/DAC route: **PASS**
- Stage C0 temporary direct alarm-bypass failback route: **PASS**
- Persistent Stage C split-bus installation: **not yet approved**
- Automatic CamillaDSP failure failback: **not yet tested**
- Reboot route selection: **not yet tested**
- Exact uninstall rollback: **not yet tested**
- PR #2: remains Draft, open and unmerged

The next engineering step is the Stage C persistent installer in prepare-only form, using the validated Stage C0 graph as its managed runtime failback target.
