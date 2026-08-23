# EQ audio route helper contract

**Status:** Phase 2 implementation checkpoint  
**Date:** 7 August 2026  
**Branch:** `feature/alarm-engine`  
**Production impact:** none; repository-only implementation

## Purpose

`a-clockwork-plex-audio-route` is the single privileged runtime writer of the active ALSA route and `route-state.json` for the EQ-capable audio profile. It replaces the former Stage C runtime-authority package with one fixed helper and a conventional three-unit systemd graph.

## Installed command

```text
/usr/local/bin/a-clockwork-plex-audio-route
```

Mode and owner:

```text
0755 root:root
```

The source file is `scripts/a-clockwork-plex-audio-route.py` and is installed without the `.py` suffix.

## Fixed actions

Read-only actions:

```text
status
validate
```

Restricted runtime transitions:

```text
activate-split-bus
activate-direct-failback
```

Systemd-only preparation:

```text
prepare-split-bus
```

`prepare-split-bus` is deliberately absent from the user sudoers template. No action accepts an arbitrary path, service name or command.

## Selected route versus active backend

`route-state.json` records the selected route:

- `split-bus-selected`;
- `direct-failback`;
- later uninstall may publish `direct-rollback`.

The route helper and EQ helper derive `split-bus-active` only when the selected route is split-bus and the managed CamillaDSP service is active with a non-zero PID. This avoids another privileged confirmation callback while keeping dashboard status truthful.

## Split-bus preparation

Preparation runs under the shared audio lock and:

1. validates the direct alarm-bypass route first;
2. validates the split-bus route in an isolated ALSA configuration;
3. verifies all five public PCM names;
4. verifies the CamillaDSP 4.1.3 executable and accepted SHA-256;
5. verifies the loaded `snd_aloop` index, ID, substreams and `pcm_notify` values;
6. loads the authoritative saved EQ JSON, or the neutral default when no state exists;
7. renders and validates a complete CamillaDSP candidate configuration;
8. atomically writes the active CamillaDSP YAML;
9. atomically selects the split-bus ALSA route;
10. publishes `split-bus-selected`.

If any split-bus preparation step fails, the helper attempts to select the already validated direct alarm-bypass route before returning an error. If direct failback also fails, both failures are reported.

## Runtime transitions

Application stop order:

1. `a-clockwork-plex.service`;
2. `shairport-sync.service`;
3. `plexamp.service`.

Application restore order:

1. `plexamp.service`;
2. `shairport-sync.service`;
3. `a-clockwork-plex.service`.

Only services that were active before a transition are restored. If application quiescence fails partway through, anything already stopped is restarted immediately before the failure is returned.

Before changing a live route, the helper stops the managed CamillaDSP service when active and requires the accepted DAC `hw_params` path to report `closed`. A missing or unreadable DAC state is an error, not proof of release.

## Direct failback

The direct transition:

1. captures application active states;
2. stops active applications in the fixed order;
3. stops CamillaDSP if active;
4. proves the DAC is released;
5. validates and atomically selects `direct-alarm-bypass.conf`;
6. publishes `direct-failback` with a reason and checksums;
7. restores the previously active applications.

The direct route retains the same public PCM names and keeps alarms outside Music Master. It does not provide EQ or the final CamillaDSP limiter.

## Status

Status reports:

- selected and effective mode;
- transition reason and timestamp;
- active, split and direct route checksums;
- whether the active file matches either managed route;
- CamillaDSP config checksum and PID;
- exact loopback parameter observations;
- active/enabled state of route, CamillaDSP, failback, Plexamp, AirPlay and dashboard services;
- installed-profile marker presence.

## Runtime assets

The conventional service graph is:

- `a-clockwork-plex-audio-route.service` — oneshot split-bus preparation;
- `a-clockwork-plex-camilladsp.service` — direct CamillaDSP process under `andy:audio`, bounded restart policy and `OnFailure=` failback;
- `a-clockwork-plex-audio-failback.service` — oneshot direct transition.

All three units use `/var/lib/a-clockwork-plex/split-bus/installed` as the simple installed-profile marker. The former `activation-approved` mechanism is not used.

## Sudo boundary

The route sudoers template delegates only:

- `status`;
- `validate`;
- `activate-split-bus`;
- `activate-direct-failback`.

The EQ sudoers template delegates only the existing `status`, `set`, `live`, `bypass` and `neutral` helper forms. Both helpers validate exact argument counts and fixed action names.

## Tests

Repository tests cover:

- split and direct route parsing contract;
- saved EQ rendering during preparation;
- forced candidate rejection selecting direct failback;
- effective active state derived from selected route plus service health;
- fixed application stop/start order;
- partial quiescence restoration;
- missing DAC state failing closed;
- loopback and public PCM validation;
- systemd ordering, bounded restart and failback relationships;
- restricted sudoers contents.

No production file, service, process, PCM, module or mixer was changed while implementing this helper.
