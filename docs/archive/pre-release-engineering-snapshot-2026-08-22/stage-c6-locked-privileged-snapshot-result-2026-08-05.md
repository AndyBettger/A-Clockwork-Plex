# Stage C6 locked privileged snapshot result — 2026-08-05

## Result

**PASS** on `plexamp-bedroom`.

Stage C6 exercised the future transaction ordering boundary on the real appliance while remaining read-only. A root-owned disposable rehearsal lock was acquired inside a fresh `/var/tmp/a-clockwork-plex-stage-c6-snapshot.*` evidence directory before the fresh identity and live snapshot. A second independent file descriptor failed closed, the snapshot completed while the lock remained held, and the lock was released only after snapshot verification and evidence-manifest generation.

The fixed production lock path `/run/lock/a-clockwork-plex-audio-route.lock` remained absent and was never opened or created.

This evidence is rehearsal-only and must never be reused as an activation-authoritative snapshot.

## Invocation

- Stage C1 package: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Stage C3 evidence: `/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F`
- Stage C4 evidence: `/var/tmp/a-clockwork-plex-stage-c4-sandbox.29DbuW`
- Stage C5 evidence: `/var/tmp/a-clockwork-plex-stage-c5-review.qKjJsF`
- Stage C6 evidence: `/var/tmp/a-clockwork-plex-stage-c6-snapshot.zFiLqI`
- Rehearsal identity: `stage-c6-13956784787abcd366a28f78`
- Generated: `2026-08-05T06:31:47+01:00`
- Host: `plexamp-bedroom`
- Architecture: `aarch64`
- Invoking user: `andy`

## Automated checks

All seventeen checks passed:

1. `root-scope`
2. `input-replay`
3. `current-host-boundary`
4. `production-lock-boundary`
5. `rehearsal-lock-acquired`
6. `lock-contention`
7. `fresh-identity`
8. `privileged-destination-resolution`
9. `filesystem-snapshot`
10. `service-state-boundary`
11. `mixer-state-capture`
12. `module-dac-capture`
13. `rollback-ledger`
14. `input-integrity`
15. `snapshot-integrity`
16. `rehearsal-lock-released`
17. `activation-interface`

## Ordered lock and snapshot evidence

The monotonic event ledger recorded this exact order:

| Order | Event |
|---:|---|
| 10 | production lock boundary inspected; fixed path absent and not opened |
| 20 | disposable exclusive rehearsal lock acquired |
| 30 | independent contention attempt rejected |
| 40 | fresh non-caller-supplied identity created |
| 50 | root-owned live snapshot started while locked |
| 60 | snapshot and immutable inputs verified |
| 70 | checksummed evidence manifest generated while locked |
| 80 | rehearsal lock released |

The rehearsal lock was mode `0600`, was recorded acquired and released, and lived only at:

`/var/tmp/a-clockwork-plex-stage-c6-snapshot.zFiLqI/control/a-clockwork-plex-audio-route.lock`

The fixed future production path remained:

- state: absent
- parent mode: `1777`
- opened: `false`

## Verified host boundary

The accepted pre-Stage-C ALSA file remained present with SHA-256:

`08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`

All twelve managed first-install file destinations were verified absent with zero conflicts. The protected sudoers destination was resolved by the root capture and remained absent.

Captured existing managed-directory state included `/etc/sudoers.d` as `root:root` mode `0750`, preserving the rollback requirement discovered during Stage C4.

## Services

The existing application services remained loaded, active and enabled:

- `plexamp.service`
- `shairport-sync.service`
- `a-clockwork-plex.service`

The future Stage C services remained absent:

- `a-clockwork-plex-audio-route.service`
- `a-clockwork-plex-camilladsp.service`
- `a-clockwork-plex-audio-failback.service`

## Mixer state

Read-only capture recorded:

| Control | Percent |
|---|---:|
| A Clockwork Master | 100 |
| A Clockwork Plexamp | 94 |
| A Clockwork AirPlay | 100 |
| A Clockwork Alarm | 100 |

No mixer value was changed.

## Loopback and DAC evidence

The live loopback contract remained exact:

- loaded: `true`
- index: `7`
- id: `ACP_Loopback`
- `pcm_substreams=2`
- `pcm_notify=1`
- enabled: `Y`

The DAC playback node `/dev/snd/pcmC2D0p` existed. The corrected structured owner evidence recorded:

- owner count: `1`
- PID: `466057`
- user: `andy`
- command: `node`
- descriptor: `41:read-write`

This closes the non-blocking Stage C3 evidence-formatting follow-up; the old concatenated `fuser` stderr label is no longer present.

## Rollback obligations

A fresh 23-row rollback ledger was generated. It continues to require:

- one future production transaction lock;
- a new root-owned activation snapshot generated after that lock is held;
- no reuse of Stage C3, C4, C5 or C6 rehearsal evidence as an activation backup;
- exact ALSA, file/absence, directory, systemd, loopback, mixer and service restoration;
- final zero-mismatch verification.

## Safety conclusion

Stage C6 proved the real-host lock-before-snapshot ordering and lock contention semantics without creating the production lock or transaction directory and without modifying the audio appliance.

It did **not** install package files, select a route, stop or start a service, run `daemon-reload`, load a module, open a PCM or DAC, change a mixer, start CamillaDSP, create an approval marker, or expose an activation interface.

Persistent Stage C activation remains blocked.
