# Stage C2 prepare-only transaction review result — 5 August 2026

Status: **PASS on `plexamp-bedroom`**. No persistent installation or activation
occurred.

## Reviewed build

- Branch: `feature/alarm-engine`
- Stage C2 implementation at the start of the successful run: `c78f031`
- Host: `plexamp-bedroom`
- Architecture: `aarch64`
- Review directory:
  `/var/tmp/a-clockwork-plex-stage-c2-review-v2.530S0n`
- Stage C1 package:
  `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Generated: `2026-08-05T04:36:03+01:00`
- Planner version: `2`

## Result summary

All eleven Stage C2 checks passed:

1. Stage C1 package evidence replay;
2. manifest replay;
3. exact current pre-Stage-C audio graph;
4. package inertness;
5. destination conflict gate;
6. review snapshot;
7. service-state boundary;
8. mixer-state capture;
9. module/DAC capture;
10. rollback contract generation;
11. confirmation that no activation interface exists.

The review verified eleven managed file destinations as absent and found zero
known destination conflicts. The normal project user could not traverse
`/etc/sudoers.d`, so the proposed sudoers destination was correctly recorded as
`privileged-check-required` rather than falsely recorded as absent:

```text
/etc/sudoers.d/a-clockwork-plex-audio-route
```

The review snapshot contains a distinct `.privileged-check-required` marker for
that path. A future activated installer must resolve it in a new root-owned
snapshot immediately before any privileged write.

## Exact live boundary captured

### Current ALSA route

The physically validated pre-Stage-C route remained exact:

```text
/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
sha256=08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
mode=644
owner=root:root
```

### Services

The three application services were loaded, active and enabled:

- `plexamp.service`
- `shairport-sync.service`
- `a-clockwork-plex.service`

The three proposed Stage C services remained not found and inactive:

- `a-clockwork-plex-audio-route.service`
- `a-clockwork-plex-camilladsp.service`
- `a-clockwork-plex-audio-failback.service`

### Mixer controls

The read-only snapshot captured:

- `A Clockwork Master`: 100%
- `A Clockwork Plexamp`: 94%
- `A Clockwork AirPlay`: 100%
- `A Clockwork Alarm`: 100%

### Loopback module

`snd_aloop` remained loaded with the discovered contract:

- index `7`
- ID `ACP_Loopback`
- two substreams
- `pcm_notify=1`
- enabled `Y`

### Physical DAC

The physical DAC remained present at `/dev/snd/pcmC2D0p` and in use by the
existing Plexamp Node process. Captured hardware parameters were:

```text
access: MMAP_INTERLEAVED
format: S16_LE
channels: 2
rate: 44100
period_size: 1024
buffer_size: 8192
```

## Rollback contract

Stage C2 generated a 22-step rollback-obligation ledger covering:

- one route transaction lock;
- exact application-service stop/restore boundaries;
- managed CamillaDSP shutdown;
- atomic restoration of the exact pre-Stage-C ALSA checksum;
- restoration of every managed file from a fresh privileged snapshot or exact
  verified absence marker;
- conservative removal of only newly created empty directories;
- exact systemd load/enabled-state restoration;
- exact `snd_aloop` loaded/options/persistence restoration;
- restoration of all four mixer controls;
- final zero-mismatch verification.

## Safety result

The successful Stage C2 review:

- invoked no `sudo`;
- wrote no production path;
- started, stopped, restarted, enabled or disabled no service;
- loaded or unloaded no kernel module;
- opened no PCM;
- changed no mixer value;
- created no approval marker;
- provided no `--activate` or `--confirm` interface.

The generated snapshot is review evidence only and is not authoritative for a
future install. Persistent activation remains blocked.

## Promotion decision

Stage C2 closes the unprivileged transaction-review boundary. The next safe
step is a separate read-only rehearsal of the fresh root-owned activation-time
snapshot and rollback ledger. That rehearsal must resolve protected paths but
must still contain no installation, route swap, service mutation, module
mutation, mixer write or activation path.
