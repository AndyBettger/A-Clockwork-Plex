# Production EQ Stage C guarded installation design

Status: design accepted for implementation preparation only. Stages A, A2 and B passed. No persistent DSP route is approved or active.

## Purpose

Stage C promotes the physically proven split-bus topology into a managed appliance route without sacrificing the exact rollback discipline that protected the bedroom Pi during the laboratories and rehearsal.

The production topology remains:

```text
Plexamp -> Plexamp trim --\
                          +-> Music Master -> music EQ/headroom --\
AirPlay -> AirPlay trim --/                                      +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume ----------------/
```

The installation must survive ordinary boot, service restart, invalid configuration and deliberate CamillaDSP failure without leaving Plexamp, AirPlay or scheduled alarms attached to a dead PCM.

## Critical failback finding

The current known-good direct shared mixer places `acp_alarm` beneath `acp_master`. It is suitable as an exact rollback to the pre-install state, but it is not an acceptable long-term automatic failback after Stage C because Music Master at 0% could then silence a scheduled alarm.

Stage C therefore needs two distinct recovery concepts:

1. **Exact uninstall rollback** — restore every pre-install file, service state and mixer level exactly as found.
2. **Managed runtime failback** — use a separately validated direct route where Plexamp and AirPlay remain beneath Music Master but alarm feeds the stereo `dmix` independently.

The managed failback route loses EQ and the final limiter, but it preserves the more important alarm-independence guarantee.

## Stage C0 prerequisite — direct failback proof

Before the persistent installer exists, a temporary mandatory-rollback rehearsal must prove this no-DSP route:

```text
Plexamp -> Plexamp trim --\
                          +-> Music Master -> stereo dmix -> DAC
AirPlay -> AirPlay trim --/
Alarm -> Maximum Alarm Volume -----------> stereo dmix -> DAC
```

Required checks:

- Plexamp and AirPlay sound normal;
- AirPlay still pauses Plexamp;
- Music Master at 0% silences Plexamp and AirPlay;
- a real scheduled alarm remains audible at Music Master 0%;
- alarm takeover, Snooze and Dismiss still work;
- restoring Music Master restores music;
- exact Ctrl-C/error rollback returns the original direct configuration and service states;
- no CamillaDSP process is involved.

This becomes the route used by runtime failback only after it passes physically.

## Managed files

The proposed persistent installation owns only an explicit set of files:

- `/etc/a-clockwork-plex/audio-routes/split-bus.conf`
- `/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf`
- `/etc/a-clockwork-plex/camilladsp-split-bus.yml`
- `/etc/default/a-clockwork-plex-split-bus`
- `/usr/local/bin/a-clockwork-plex-audio-route`
- `/usr/local/bin/a-clockwork-plex-audio-eq`
- `/etc/sudoers.d/a-clockwork-plex-audio-route`
- `/etc/sudoers.d/a-clockwork-plex-audio-eq`
- `/etc/systemd/system/a-clockwork-plex-audio-route.service`
- `/etc/systemd/system/a-clockwork-plex-camilladsp.service`
- `/etc/systemd/system/a-clockwork-plex-audio-failback.service`
- deterministic loopback-module configuration, only after the exact module parameters are validated on the Pi
- `/var/lib/a-clockwork-plex/split-bus/` for state, manifests and exact backups

The active ALSA file remains `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf`, installed atomically from one of the two validated route files.

The existing `scripts/install-shared-audio.sh` is not repurposed. The blocked `scripts/install-master-eq.sh` remains blocked.

## Route authority

One root-owned helper, `a-clockwork-plex-audio-route`, becomes the sole writer of the active ALSA route and route-state file. The dashboard may read status or request validated actions through restricted sudo rules, but it cannot write ALSA or systemd files itself.

Supported helper actions should be deliberately small:

- `status`
- `activate-split-bus`
- `activate-direct-failback`
- `validate`
- `restore-backup <transaction-id>`

No arbitrary file path, systemd unit or command argument is accepted.

## Boot ownership

`a-clockwork-plex-audio-route.service` runs before Plexamp, Shairport Sync and the dashboard audio authorities. It performs one decision:

1. validate the CamillaDSP binary, loopback card, split-bus ALSA route and CamillaDSP configuration;
2. start CamillaDSP and prove it owns the expected DAC format;
3. publish `split-bus-active` only after validation succeeds;
4. otherwise install the validated direct alarm-bypass route, stop CamillaDSP and publish `direct-failback`;
5. allow the three application services to start only after one usable route has been selected.

A partial state where the split-bus ALSA file is active but CamillaDSP is unavailable is forbidden.

## Runtime failure ownership

The CamillaDSP service uses an `OnFailure=` relationship to `a-clockwork-plex-audio-failback.service`.

The failback service must:

1. acquire the same route lock as the installer/helper;
2. stop only Plexamp, Shairport Sync and the dashboard service;
3. confirm the DAC and loopback endpoints are released;
4. stop any surviving CamillaDSP process;
5. atomically install the validated direct alarm-bypass route;
6. restore the prior live mixer values;
7. restart only services that were active before failback;
8. publish `direct-failback` with the failure reason and timestamp;
9. verify that Plexamp, AirPlay and alarm PCMs can open before declaring success.

The dashboard must show a prominent degraded-audio warning. EQ controls remain visible but unavailable; alarm independence remains intact.

## Installation transaction

The persistent installer must default to `--prepare-only`. Physical installation requires an exact confirmation token and runs as the normal project user, invoking sudo only for guarded writes.

### Prepare-only

Prepare-only may:

- generate candidate ALSA, CamillaDSP, systemd, defaults, helper and sudoers files inside a private laboratory directory;
- validate shell and Python syntax;
- validate the ALSA candidate through an isolated root configuration;
- validate the CamillaDSP configuration with the verified 4.1.3 binary;
- validate sudoers with `visudo -cf` against the candidate file;
- print a complete change manifest and exact activation command.

Prepare-only must not:

- invoke sudo;
- open the physical DAC;
- load `snd_aloop`;
- write `/etc`, `/usr/local`, `/var/lib` or systemd;
- stop or restart any service;
- enable any unit.

### Activated install

The activated transaction must:

1. refuse an unexpected current audio graph or unrecognised existing CamillaDSP process;
2. snapshot file contents, modes, owners, absence markers, checksums, service active/enabled states, mixer levels, loopback-module state and DAC owners;
3. stage and revalidate every candidate file before stopping audio;
4. stop only Plexamp, Shairport Sync and the dashboard;
5. confirm the physical DAC is released;
6. install files atomically;
7. run `systemctl daemon-reload`;
8. start the route authority and prove split-bus health;
9. run finite low-level music and alarm lane probes;
10. restore previously active application services;
11. verify CamillaDSP survives their startup;
12. verify the dashboard health API reports the same route state as the root helper;
13. commit the transaction manifest only after all checks pass.

Any error before commit invokes exact rollback automatically.

## Exact rollback

Each installation receives a transaction directory containing:

- original file or explicit absence marker for every managed path;
- original SHA-256, mode, owner and group;
- original service active and enabled states;
- original mixer status and restore values;
- original loopback loaded/configured state;
- original DAC owner and `hw_params` snapshots;
- installer version and candidate checksums.

Rollback stops the managed audio services, restores files and absence markers exactly, reloads systemd, restores module state, restores mixer values, restores original service states and verifies the final checksums.

Rollback success is not inferred from command exit alone. Every restored item must be compared with its snapshot.

## CamillaDSP service

The persistent service uses the previously verified CamillaDSP 4.1.3 binary copied from a user-supplied path. The installer does not fetch an executable from the network during activation.

The service must:

- run under a dedicated unprivileged account where practical;
- have access only to the loopback capture and physical DAC devices it needs;
- use a fixed 44.1 kHz / S16_LE four-channel capture and stereo playback configuration;
- start with flat EQ and automatic headroom derived from managed state;
- combine alarm only after music-only processing;
- apply the final −1.0 dBFS limiter last;
- restart only within a bounded policy so repeated failure reaches failback rather than an endless restart loop.

## EQ helper migration

The public dashboard API and `MasterEqualizer` client can remain stable. The root helper implementation changes from `alsaequal` controls to managed CamillaDSP state.

The new helper should:

- preserve the current `status`, `set`, `live`, `bypass` and `neutral` command contract;
- store authoritative Bass, Mid, Treble and bypass state atomically;
- clamp values to the existing −6 dB to +6 dB half-decibel range;
- calculate automatic music headroom from the largest positive boost;
- render a complete candidate CamillaDSP configuration under a lock;
- validate it before replacing the active configuration;
- request one controlled live reload;
- verify that the same CamillaDSP process remains healthy;
- roll back the state/config pair if reload validation fails;
- report `split-bus-active`, `direct-failback`, `direct-rollback` or `offline` distinctly.

In direct failback mode, stored EQ values remain intact but no EQ is applied.

## Health contract

The root route helper and dashboard diagnostics expose:

- selected route mode;
- route reason and last transition time;
- active ALSA configuration checksum;
- expected and observed CamillaDSP PID;
- expected and observed DAC format;
- loopback card identity;
- CamillaDSP configuration checksum;
- EQ stored/applied/bypassed state and calculated headroom;
- final limiter setting;
- direct-failback availability;
- latest transaction/rollback identifier;
- degraded or failed component details.

The dashboard is not allowed to report EQ as active merely because the helper file exists.

## Promotion sequence

1. Build and statically test the Stage C0 direct-failback rehearsal.
2. Run prepare-only on the Pi.
3. Physically activate the temporary direct-failback route and prove alarm independence plus exact rollback.
4. Build the Stage C persistent installer in prepare-only form.
5. Review every generated file and transaction rule.
6. Run activated installation with mandatory automatic rollback available.
7. Test normal Plexamp, AirPlay, NFC, alarm, Snooze, Dismiss and EQ behaviour.
8. Deliberately kill CamillaDSP and prove automatic direct alarm-bypass failback.
9. Reboot and prove deterministic route selection.
10. Test explicit uninstall rollback to the exact pre-install direct mixer.
11. Keep PR #2 Draft until the user explicitly approves readiness and merge.

## Current decision

Stage C implementation may proceed only through prepare-only assets and the Stage C0 temporary failback proof. Persistent activation remains blocked.
