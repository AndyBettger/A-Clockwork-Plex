# Stage C3 privileged snapshot rehearsal result — 5 August 2026

Status: **PASS on `plexamp-bedroom`**. This was a read-only privileged snapshot rehearsal. No persistent Stage C installation or activation was performed.

## Run identity

- Host: `plexamp-bedroom`
- Architecture: `aarch64`
- Invoking user: `andy`
- Repository head used for the physical run: `6ef32716147054f41f595eb7764891923147191a`
- Generated: `2026-08-05T05:00:57+01:00`
- Stage C1 package: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Stage C2 review: `/var/tmp/a-clockwork-plex-stage-c2-review-v2.530S0n`
- Stage C3 evidence directory: `/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F`
- Confirmation token: `STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY`

The outer wrapper was launched as the normal project user. It invoked exactly one constrained `sudo` command for the read-only Python snapshot engine.

No password prompt appeared. The evidence proves that `sudo` did execute as root on behalf of `andy`; the absence of a prompt therefore indicates either an already-valid sudo timestamp or a broader host-level `NOPASSWD` rule. The project-specific proposed sudoers destination was itself verified absent, so Stage C did not install or rely upon that rule.

## Result checks

All twelve Stage C3 checks passed:

1. `root-scope`
2. `stage-c1-package-replay`
3. `stage-c2-review-replay`
4. `current-host-boundary`
5. `privileged-destination-resolution`
6. `filesystem-snapshot`
7. `service-state-boundary`
8. `mixer-state-capture`
9. `module-dac-capture`
10. `rollback-ledger`
11. `activation-interface`
12. `snapshot-integrity`

The engine reported:

```text
A Clockwork Plex Stage C3 privileged snapshot rehearsal passed.
No production path was written or changed.
```

## Privileged destination resolution

Root resolved every managed file destination directly:

- managed package files: 12;
- verified absent managed files: 12;
- existing managed files: 0;
- managed destination conflicts: 0;
- protected sudoers destination: verified absent.

In particular:

```text
/etc/sudoers.d/a-clockwork-plex-audio-route  absent
```

A true `.absent` marker was generated for every managed file destination. No protected path remained unverified.

The current production ALSA route was copied outward into the evidence tree and retained the physically validated checksum:

```text
08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
```

The current route remained the pre-Stage-C alarm-under-Music-Master graph.

## Directory boundary

The snapshot recorded the exact pre-install directory state. Important first-install absences included:

- `/etc/a-clockwork-plex`
- `/etc/a-clockwork-plex/audio-routes`
- `/usr/local/lib/a-clockwork-plex`
- `/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3`
- `/var/lib/a-clockwork-plex/split-bus`

Existing protected parent directories were recorded with their real modes and owners, including:

```text
/etc/sudoers.d  0750  root:root
```

This gives a future exact rollback enough information to remove only directories created by the authorised transaction and only when they are empty.

## Service boundary

The three application services remained loaded, active and enabled:

- `plexamp.service`
- `shairport-sync.service`
- `a-clockwork-plex.service`

The three proposed Stage C units remained absent:

- `a-clockwork-plex-audio-route.service`
- `a-clockwork-plex-camilladsp.service`
- `a-clockwork-plex-audio-failback.service`

No service was started, stopped, restarted, enabled or disabled, and no `daemon-reload` occurred.

## Mixer boundary

The read-only snapshot captured:

```text
A Clockwork Master    100%
A Clockwork Plexamp    94%
A Clockwork AirPlay   100%
A Clockwork Alarm     100%
```

No mixer value was changed.

## Loopback and DAC boundary

The loaded loopback contract remained exact:

```text
snd_aloop.loaded         true
snd_aloop.index          7
snd_aloop.id             ACP_Loopback
snd_aloop.pcm_substreams 2
snd_aloop.pcm_notify     1
snd_aloop.enable         Y
```

The physical playback device remained `/dev/snd/pcmC2D0p`, and the exact DAC hardware contract remained the already validated 44.1 kHz, S16_LE, stereo, period-size 1024 and buffer-size 8192 boundary.

The original `fuser` evidence joined stdout and stderr, producing a visually malformed owner value containing PID `466057` and access marker `m`. This did not affect the read-only safety proof, route proof or destination proof, but it was not clean enough for a future authoritative activation snapshot. A follow-up code change now records DAC ownership as separate PID, user, command and matching file-descriptor access fields. A future root-owned activation snapshot must use that corrected format.

## Rollback ledger

The generated ledger contains 23 ordered obligations. It requires a future authorised transaction to:

- use a new transaction identifier and never reuse this rehearsal snapshot;
- acquire the single route lock before taking its fresh authoritative snapshot;
- stop only services recorded active in that future snapshot;
- restore the exact active ALSA checksum;
- restore each managed file or its exact verified absence;
- remove only newly created empty directories;
- restore systemd load/enabled state;
- restore loopback persistence and loaded state;
- restore all four mixer percentages;
- restore exact application-service states;
- finish only after zero rollback mismatches.

## Evidence integrity

The evidence tree contained no symlink or special object. `evidence-manifest.tsv` recorded modes and SHA-256 checksums for all generated evidence files, copied originals and absence markers.

The rehearsal directory was returned to `andy` after the root-owned capture completed.

## Safety conclusion

Stage C3 proves that the exact root-owned pre-mutation snapshot and rollback ledger can be captured safely and completely on the real appliance.

It does **not** authorise installation. The snapshot at `/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F` is review evidence only and must never be reused for activation or rollback.

No production path was written, no route was changed, no PCM was opened, no service or module state changed, no mixer value changed and no approval marker was created.

Persistent Stage C activation remains blocked.
