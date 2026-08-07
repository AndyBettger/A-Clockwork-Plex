# EQ-capable audio installation manifest

**Status:** Phase 1 working manifest  
**Created:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Production state while preparing this document:** known-good direct audio; EQ not installed

## Purpose

This document identifies the exact physically proven audio artefacts and runtime contracts that the new standalone EQ installer must reproduce. It deliberately separates the useful audio design from the abandoned Stage C transactional deployment framework.

The installer must reuse the accepted signal graph and host contract. It must not reintroduce the rejected `alsaequal` route, the numbered Stage C adapter hierarchy, borrowed authority, temporary approval records or retained-transaction machinery.

## Evidence basis

The inventory is derived from:

- `docs/production-eq-split-bus-design.md`;
- `docs/production-eq-stage-c-install-design.md`;
- `docs/split-bus-dsp-laboratory-result-2026-08-05.md`;
- `docs/split-bus-alsa-routing-result-2026-08-05.md`;
- `docs/split-bus-physical-rehearsal-result-2026-08-05.md`;
- `docs/direct-alarm-bypass-failback-result-2026-08-05.md`;
- `scripts/stage_c_package/templates.py`;
- `scripts/stage_c_package/runtime_templates.py`;
- `scripts/stage_c_activation_package/prepare.py`;
- the successful direct-route recovery on 7 August 2026.

Stages A, A2, B and C0 already proved the audio design. Phase 1 is inventory work, not a redesign or a request to repeat those physical tests.

## Fixed host and stream contract

| Item | Accepted value |
|---|---|
| Project user on bedroom Pi | `andy` |
| Architecture | `aarch64` |
| Physical DAC ALSA card | `Pro` |
| Physical DAC device | `0` |
| Playback device | `hw:CARD=Pro,DEV=0` |
| Sample rate | `44100` Hz |
| Sample format | `S16_LE` |
| Period size | `1024` |
| Buffer size | `8192` |
| CamillaDSP chunksize | `1024` |
| CamillaDSP target level | `2048` |
| Final limiter | `-1.0 dBFS` |
| Loopback card index | `7` |
| Loopback module ID | `ACP_Loopback` |
| ALSA card ID observed | `ACPLoopback` |
| Loopback substreams | `2` |
| Loopback `pcm_notify` | `1` |
| Accepted direct-route SHA-256 | `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` |

The new installer may make these values configurable for a future fresh-Pi profile, but the first bedroom-Pi implementation must validate this exact accepted contract before changing production audio.

## Public PCM contract

Both the EQ-capable split route and the managed direct failback route expose the same public names:

- `acp_dmix`
- `acp_master`
- `acp_plexamp`
- `acp_airplay`
- `acp_alarm`

Plexamp, Shairport Sync and the alarm application must not need device remapping when the installed route changes between split-bus and direct failback.

## Signal-lane contract

### EQ-capable split-bus route

The four-channel loopback bus is fixed as:

| Channel | Meaning |
|---|---|
| 0 | Music left |
| 1 | Music right |
| 2 | Alarm left |
| 3 | Alarm right |

The mandatory processing order is:

1. Plexamp and AirPlay enter channels 0/1 through their source trims and Music Master.
2. Bass, Mid, Treble and automatic headroom process only channels 0/1.
3. Alarm enters channels 2/3 through its independent maximum-volume control.
4. A 4-to-2 mixer combines music and alarm.
5. The final `-1.0 dBFS` limiter processes the combined stereo signal.
6. Stereo output is written to the physical DAC.

### Managed direct failback route

The direct failback route preserves the public PCM names and the independent alarm guarantee without CamillaDSP:

```text
Plexamp -> Plexamp trim --\
                          +-> Music Master -> stereo dmix -> DAC
AirPlay -> AirPlay trim --/
Alarm -> Maximum Alarm Volume -----------> stereo dmix -> DAC
```

This is the automatic runtime failback target. It is different from exact uninstall rollback, which returns the Pi to the pre-install direct-route checksum recorded above.

## CamillaDSP artefact

| Item | Accepted value |
|---|---|
| Version | `4.1.3` |
| SHA-256 | `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| Installation destination | `/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp` |
| Mode | `0755` |
| Owner | `root:root` |
| Acquisition policy | supplied and verified locally; no network download during activation |

The installer must verify both version output and SHA-256 before using or installing the executable.

## Canonical audio configuration artefacts

The accepted route and DSP contents currently exist as deterministic templates in `scripts/stage_c_package/templates.py`. The new implementation should materialise reviewed static profile files in the repository rather than regenerate them through the old Stage C package machinery.

| Destination | Mode | Owner | Canonical source | Decision |
|---|---:|---|---|---|
| `/etc/a-clockwork-plex/audio-routes/split-bus.conf` | `0644` | `root:root` | `split_route()` | Reuse exact tested content as a static EQ profile |
| `/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf` | `0644` | `root:root` | `direct_route()` | Reuse exact physically validated failback content |
| `/etc/a-clockwork-plex/camilladsp-split-bus.yml` | `0644` | `root:root` | `camilladsp_config()` | Reuse exact tested neutral configuration as the render base |
| `/etc/default/a-clockwork-plex-split-bus` | `0644` | `root:root` | Stage C defaults template | Replace Stage C phase fields with installer/runtime settings only |
| `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf` | preserve current metadata | normally `root:root` | atomic copy from selected route | Active route; always backed up before first install |

### CamillaDSP filter definitions

The neutral render base uses:

- Bass: low shelf, 125 Hz, 0 dB, slope 6;
- Mid: peaking, 1000 Hz, 0 dB, Q 0.7;
- Treble: high shelf, 4000 Hz, 0 dB, slope 6;
- Headroom: gain filter, initially 0 dB;
- Final limiter: hard limiter at `-1.0 dBFS`.

The future EQ helper changes only the music filters and headroom. It must not move the alarm combine point or final limiter.

## Persistent loopback artefacts

| Destination | Required content | Mode | Owner |
|---|---|---:|---|
| `/etc/modules-load.d/a-clockwork-plex-aloop.conf` | `snd_aloop` | `0644` | `root:root` |
| `/etc/modprobe.d/a-clockwork-plex-aloop.conf` | `options snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1` | `0644` | `root:root` |

The installer must distinguish three cases:

1. matching module already loaded/configured — accept and continue;
2. module absent — install persistence and load it during the controlled audio stop;
3. module present with different parameters — stop and report the mismatch rather than silently replacing an active ALSA card identity.

## Runtime helper inventory

### Route helper

Intended destination:

```text
/usr/local/bin/a-clockwork-plex-audio-route
```

Mode and owner:

```text
0755 root:root
```

The old Stage C activation package wrapped 15 runtime-authority Python modules behind this command. Those modules are deployment machinery and are not part of the new installer.

The replacement route helper should be small and expose only fixed actions needed by the supported appliance:

- `status`
- `validate`
- `activate-split-bus`
- `activate-direct-failback`

Installer-owned backup restoration belongs to `uninstall-eq.sh` or a fixed internal installer function, not a caller-selectable arbitrary path action.

The helper remains the sole runtime writer of the active ALSA route and route-state file.

### EQ helper

Intended destination:

```text
/usr/local/bin/a-clockwork-plex-audio-eq
```

Mode and owner:

```text
0755 root:root
```

The dashboard already expects the command contract:

- `status`
- `set <bass|mid|treble> <dB>`
- `live <bass|mid|treble> <dB>`
- `bypass <on|off>`
- `neutral`

**Important:** the current source file `scripts/a-clockwork-plex-audio-eq.py` controls the rejected `alsaequal`/Eq10 backend. It must not be installed for the split-bus design.

A new CamillaDSP-backed implementation is required. It must:

- preserve the existing command and JSON response contract used by `app/audio_eq.py`;
- store Bass, Mid, Treble and bypass state atomically;
- preserve stored values while bypassed;
- clamp values to `-6 dB` through `+6 dB` in `0.5 dB` steps;
- calculate music headroom from the largest positive boost;
- render and validate a complete CamillaDSP candidate configuration;
- request one controlled live reload without replacing the healthy CamillaDSP process;
- roll back the state/config pair if validation or reload fails;
- report active, bypassed, direct-failback and unavailable states distinctly.

The precise managed state filename will be selected during Phase 2. It should live beneath `/var/lib/a-clockwork-plex/split-bus/` so the EQ state and route state have one clear ownership boundary.

## Sudo rules

The old activation package exposed only read-only route actions. The new installer needs two narrowly scoped sudoers files:

| Destination | Mode | Owner | Required allowance |
|---|---:|---|---|
| `/etc/sudoers.d/a-clockwork-plex-audio-route` | `0440` | `root:root` | fixed route status/validation and approved fixed route transitions only |
| `/etc/sudoers.d/a-clockwork-plex-audio-eq` | `0440` | `root:root` | fixed EQ `status`, `set`, `live`, `bypass` and `neutral` actions only |

No wildcard path, arbitrary systemd unit or arbitrary shell command is permitted.

## Systemd unit inventory

| Destination | Mode | Owner | Responsibility |
|---|---:|---|---|
| `/etc/systemd/system/a-clockwork-plex-audio-route.service` | `0644` | `root:root` | select and validate one usable route before audio applications start |
| `/etc/systemd/system/a-clockwork-plex-camilladsp.service` | `0644` | `root:root` | own supervised CamillaDSP processing and trigger failback on failure |
| `/etc/systemd/system/a-clockwork-plex-audio-failback.service` | `0644` | `root:root` | select the validated direct alarm-bypass route after genuine DSP failure |

The old unit ordering is accepted as the starting contract:

- route service after module loading and `sound.target`;
- route service before CamillaDSP, Plexamp, Shairport Sync and the dashboard;
- CamillaDSP requires the route service and `sound.target`;
- CamillaDSP starts before Plexamp, Shairport Sync and the dashboard;
- CamillaDSP failure triggers the failback unit;
- restart policy is bounded (`Restart=on-failure`, two-second delay, three starts per 60 seconds in the reviewed design).

The old `ConditionPathExists=.../activation-approved` mechanism belongs to the retired transaction framework. The new units should instead use a simple installed-profile marker or validated configuration presence, selected during Phase 2.

## Service mutation order

### Controlled installation stop order

1. `a-clockwork-plex.service`
2. `shairport-sync.service`
3. `plexamp.service`

This order removes the dashboard/control layer first, then AirPlay, then Plexamp, before verifying that the DAC and loopback endpoints are released.

### Managed audio start order

1. load/verify `snd_aloop`;
2. select the split-bus ALSA route;
3. start `a-clockwork-plex-audio-route.service`;
4. start `a-clockwork-plex-camilladsp.service` and prove DAC ownership/health;
5. start `plexamp.service` if it was previously active;
6. start `shairport-sync.service` if it was previously active;
7. start `a-clockwork-plex.service` if it was previously active;
8. verify dashboard health and public PCMs.

### Rollback/failback order

1. stop the three application services in the controlled stop order;
2. stop CamillaDSP;
3. select either the exact pre-install backup (install rollback/uninstall) or managed direct alarm-bypass route (runtime failback);
4. reload ALSA consumers as needed;
5. restore application services in Plexamp, AirPlay, dashboard order;
6. verify public PCM availability and audible-route health.

The new scripts should capture the original active/enabled state and restore only services that were active before the operation.

## State and backup inventory

Proposed simple ownership root:

```text
/var/lib/a-clockwork-plex/split-bus/
```

Mode and owner:

```text
0755 root:root
```

Expected contents after a successful install should be small and understandable, for example:

- `install-manifest.json` — installed paths, checksums and installer version;
- `pre-eq-active-route.conf` — exact first-install backup;
- `pre-eq-active-route.json` — original checksum, mode and owner;
- `route-state.json` — split-bus/direct-failback mode and reason;
- `eq-state.json` — stored bands and bypass state;
- `last-operation.log` — concise install/repair/failback result.

This is a proposed Phase 2 layout, not permission to recreate the previous transaction directory hierarchy.

## Required installation files: first implementation

The first installer is expected to own these audio files:

1. split-bus ALSA route;
2. direct alarm-bypass ALSA route;
3. CamillaDSP configuration;
4. split-bus defaults;
5. modules-load entry;
6. modprobe options entry;
7. CamillaDSP binary;
8. route helper;
9. CamillaDSP-backed EQ helper;
10. route sudoers file;
11. EQ sudoers file;
12. route systemd unit;
13. CamillaDSP systemd unit;
14. failback systemd unit;
15. small state/manifest files created by installation.

The 15 Python runtime-authority modules and package-contract file from the 28-file Stage C21 package are explicitly excluded.

## Source-controlled versus generated

### Store as reviewed source-controlled files

- split-bus ALSA profile;
- direct alarm-bypass ALSA profile;
- neutral CamillaDSP render template;
- loopback module files;
- systemd units;
- route helper;
- new CamillaDSP EQ helper;
- sudoers templates;
- install, uninstall, verify and repair scripts.

### Generate at install/runtime

- host-specific defaults file;
- exact pre-install route backup and metadata;
- install manifest/checksums;
- route status;
- EQ state;
- rendered active CamillaDSP configuration when bands/bypass change;
- concise operation reports.

### Preserve only as historical evidence

- Stage C transaction adapters and numbered subclasses;
- runtime-authority package modules;
- approval records and borrowed-authority views;
- retained-transaction recovery programs;
- `stage-c-terminal-install-20260806` branch after Phase 1 retirement.

## Phase 1 open points

The following implementation choices remain for Phase 2 and do not require another audio-topology experiment:

1. final static repository directory names for profiles and unit templates;
2. exact simple installed-profile marker used by systemd;
3. exact EQ state filename beneath the state root;
4. CamillaDSP live reload mechanism and health acknowledgement;
5. whether the supervised service runs CamillaDSP directly or through a small fixed supervisor;
6. how the future full installer supplies or verifies the CamillaDSP binary on a fresh Pi.

## Phase 1 conclusion

The physically accepted audio artefacts, destinations, host contract, public PCMs, loopback settings and service ordering are now identified. The main newly exposed implementation requirement is the CamillaDSP-backed replacement for the old `alsaequal` EQ helper.

Phase 2 can begin by materialising the reviewed static profile files and building the small helper/installer layer around them. No production Pi mutation is authorised by this manifest.
