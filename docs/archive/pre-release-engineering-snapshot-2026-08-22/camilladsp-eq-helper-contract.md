# CamillaDSP EQ helper contract

**Status:** Phase 2 implementation checkpoint  
**Date:** 7 August 2026  
**Branch:** `feature/alarm-engine`  
**Production impact:** none; repository-only implementation

## Purpose

This document records the selected implementation contract for the dashboard EQ helper used by the EQ-capable split-bus audio profile. It replaces the old `alsaequal`/Eq10 implementation while preserving the command and JSON interface already used by `app/audio_eq.py` and the browser controls.

## Installed layout

| Destination | Mode | Owner | Purpose |
|---|---:|---|---|
| `/usr/local/bin/a-clockwork-plex-audio-eq` | `0755` | `root:root` | Stable restricted command launcher |
| `/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/__init__.py` | `0644` | `root:root` | Fixed package exports |
| `/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/model.py` | `0644` | `root:root` | State, validation, headroom and complete YAML rendering |
| `/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/runtime.py` | `0644` | `root:root` | Candidate validation, live reload, health proof and rollback |
| `/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/cli.py` | `0644` | `root:root` | Fixed command boundary and JSON output |

The source launcher also supports imports from the repository `scripts/` directory for tests. The installed launcher prefers the fixed runtime root above.

## State and configuration ownership

| Item | Selected path |
|---|---|
| Defaults | `/etc/default/a-clockwork-plex-split-bus` |
| Active CamillaDSP YAML | `/etc/a-clockwork-plex/camilladsp-split-bus.yml` |
| Authoritative saved EQ state | `/var/lib/a-clockwork-plex/split-bus/master-eq.json` |
| Route state | `/var/lib/a-clockwork-plex/split-bus/route-state.json` |
| Shared route/EQ lock | `/run/lock/a-clockwork-plex-audio-route.lock` |
| CamillaDSP service | `a-clockwork-plex-camilladsp.service` |

The JSON state is authoritative for the stored Bass, Mid, Treble and bypass values. The YAML file is a complete rendered runtime configuration and is never edited partially.

## Public command contract

The helper preserves the dashboard contract:

```text
status
set <bass|mid|treble> <dB>
live <bass|mid|treble> <dB>
bypass <on|off>
neutral
```

- `status` is read-only.
- `set` applies and persists one half-decibel value.
- `live` applies a temporary drag-preview value without replacing saved state.
- `bypass` preserves the saved curve and changes the rendered runtime state.
- `neutral` clears all three stored bands to `0 dB` and disables bypass.
- mutations require root and are intended to be exposed only through a restricted sudo rule.

## EQ range and automatic headroom

Each band is clamped to `-6 dB` through `+6 dB` in `0.5 dB` steps.

Automatic music headroom is:

```text
0 dB                                      when no band is boosted
-(largest positive band boost + 0.5 dB)  when any band is boosted
```

Therefore a largest boost of `+6 dB` renders `-6.5 dB` of music-only headroom, matching the accepted live-headroom laboratory profile.

## Bypass behavior

Bypass does not change ALSA routes, restart Plexamp, restart AirPlay or replace CamillaDSP.

When bypass is enabled:

1. the stored JSON curve remains unchanged;
2. the complete runtime YAML renders Bass, Mid, Treble and headroom at `0 dB`;
3. the music EQ/headroom pipeline step is explicitly marked `bypassed: true`;
4. the alarm combine step remains active;
5. the final `-1.0 dBFS` limiter remains active.

When bypass is disabled, the stored curve and calculated headroom are rendered again and the music step is marked `bypassed: false`.

## Live reload transaction

Each applied change follows one small transaction:

1. acquire the shared audio-route lock;
2. require route state `split-bus-active`;
3. require the managed CamillaDSP service to be active with a non-zero PID;
4. render a complete candidate YAML file;
5. validate the candidate using the installed CamillaDSP binary with `--check`;
6. atomically replace the active YAML;
7. send `SIGHUP` to the expected CamillaDSP PID;
8. verify that the service remains active with the same PID;
9. persist JSON state only after successful validation and reload.

If validation or health proof fails, the previous YAML and previous state are restored. A rollback failure is reported distinctly rather than hidden.

## Status contract

EQ is reported as available only when all of these agree:

- route mode is `split-bus-active`;
- the verified CamillaDSP binary exists;
- the active YAML exists;
- `a-clockwork-plex-camilladsp.service` is active;
- the service reports a non-zero PID.

Status distinguishes:

- `split-bus-active` — curve can be applied;
- `direct-failback` — saved curve retained but unavailable;
- `direct-rollback` — direct-audio profile active;
- `offline` — no usable EQ route state.

The helper returns native CamillaDSP state and an empty legacy `controls` list. It does not invent Eq10 control diagnostics.

## Boot and repair requirement

A transient `live` value deliberately does not replace authoritative JSON state. Therefore the route/startup path must render `/etc/a-clockwork-plex/camilladsp-split-bus.yml` from `master-eq.json` before starting CamillaDSP. Repair must do the same. This guarantees that a browser disconnect during a drag preview cannot become the next boot's persistent curve.

## Tests

Repository tests cover:

- dashboard command compatibility;
- half-decibel clamping;
- automatic headroom;
- alarm bypass and limiter ordering;
- native CamillaDSP pipeline bypass;
- saved-curve preservation while bypassed;
- persistent and transient changes;
- neutral reset;
- same-PID reload proof;
- exact config rollback after a forced PID change;
- direct-failback status.

No production path, process, service, PCM or mixer was changed while implementing this helper.
