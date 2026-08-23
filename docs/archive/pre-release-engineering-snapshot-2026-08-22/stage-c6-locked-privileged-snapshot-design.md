# Stage C6 locked privileged snapshot rehearsal

Status: design and implementation may proceed. This stage is a privileged, read-only rehearsal of lock-before-snapshot ordering. It does not create the production route lock, production transaction directory or any activation interface.

## Purpose

Stage C5 fixed the future production transaction ordering:

1. replay the reviewed evidence contracts;
2. acquire one exclusive non-blocking route lock;
3. generate a fresh transaction identity;
4. capture and verify a fresh authoritative root-owned snapshot;
5. stage and validate candidates;
6. begin mutation only after all earlier gates pass.

Stage C6 proves the first four ordering properties against the live `plexamp-bedroom` host while retaining the no-production-mutation boundary.

It performs one constrained root-owned rehearsal which:

- replays the exact Stage C1, C3, C4 and C5 evidence;
- verifies the live pre-Stage-C route and physical host boundary;
- verifies the future production lock path is absent and its parent is suitable;
- acquires a real exclusive non-blocking `flock` on a root-owned rehearsal lock inside the fresh evidence directory;
- proves a second independent descriptor cannot acquire the same lock;
- creates a new rehearsal identity only after the lock is held;
- captures a new live privileged snapshot only while the lock remains held;
- verifies the snapshot and input evidence integrity;
- releases the rehearsal lock after the complete evidence manifest exists.

The rehearsal lock proves mechanism and ordering. It is deliberately not the production lock.

## Why the real production lock remains untouched

The future fixed lock is:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

Creating that file would introduce the first persistent production control-plane write. Stage C6 does not need that write to prove `flock` semantics or lock-before-snapshot ordering.

Instead Stage C6:

1. verifies `/run/lock` is a real root-owned directory;
2. verifies the candidate lock path is absent, not a symlink or conflict;
3. records that boundary in evidence;
4. uses `<stage-c6-root>/control/a-clockwork-plex-audio-route.lock` for the actual rehearsal lock.

The future root adapter must later use the fixed `/run/lock` path and will receive a separate explicit review and authorisation boundary.

## Interface

Prepare-only remains the default:

```bash
bash scripts/test-stage-c-locked-privileged-snapshot.sh \
  --package-root /var/tmp/<validated-stage-c1-package> \
  --stage-c3-root /var/tmp/<validated-stage-c3-snapshot> \
  --stage-c4-root /var/tmp/<validated-stage-c4-sandbox> \
  --stage-c5-root /var/tmp/<validated-stage-c5-review>
```

Prepare-only invokes no `sudo`, creates no Stage C6 evidence directory and performs no host inspection beyond resolving the supplied user-owned paths.

The guarded capture requires the exact token:

```text
STAGE-C6-LOCKED-PRIVILEGED-SNAPSHOT-READ-ONLY
```

and a fresh empty user-owned mode-0700 directory directly beneath `/var/tmp` named:

```text
a-clockwork-plex-stage-c6-snapshot.*
```

The wrapper contains exactly one `sudo` command. It invokes only the constrained Stage C6 Python entry module.

## Input replay

Before the root-owned capture begins, Stage C6 independently replays:

- the complete Stage C1 manifest, checksums, modes and PASS evidence;
- the complete Stage C3 twelve-check PASS snapshot and evidence manifest;
- the complete Stage C4 nine-check PASS sandbox result, four exact scenarios and zero mismatches;
- the complete Stage C5 ten-check PASS review, state machine, lock contract, snapshot contract, command contract, recovery classes, activation blockers and evidence manifest;
- unchanged fingerprints for all four input trees.

Stage C3, C4 and C5 remain review evidence only. Stage C6 does not convert any earlier directory into an activation-authoritative backup.

## Root scope

The root engine may write only inside the supplied Stage C6 evidence directory.

It may read:

- the four supplied evidence trees;
- the exact managed production destinations;
- the active ALSA route;
- systemd service state;
- the four reviewed mixer controls;
- loaded `snd_aloop` parameters;
- DAC ownership and hardware parameters;
- `/run/lock` and the candidate production lock path.

It must not write `/run`, `/etc`, `/usr/local`, `/var/lib`, systemd, ALSA, mixer, module or device state.

The evidence directory is temporarily changed to root ownership during capture and returned recursively to the invoking user before exit.

## Rehearsal lock contract

After all immutable evidence and live-host preflight checks pass:

1. create `control/` beneath the root-owned Stage C6 evidence directory;
2. create the rehearsal lock as root-owned mode `0600`;
3. open it with one fixed path and acquire `LOCK_EX | LOCK_NB`;
4. write lock identity only to `lock-state.tsv`, not to the lock file;
5. independently open the same lock file a second time and require `LOCK_EX | LOCK_NB` to fail with contention;
6. retain the first lock through fresh identity generation, live snapshot capture, verification and manifest generation;
7. record ordered events with monotonic and wall-clock timestamps;
8. release the lock only after all snapshot checks pass;
9. retain the rehearsal lock file only inside the evidence directory as checksummed evidence.

No secondary route, installer or EQ lock is created.

## Fresh rehearsal identity and snapshot

The rehearsal identity is generated after the lock is held. It includes a random identifier, host, invoking user, root PID and timestamps.

While the lock remains held, Stage C6 captures:

- content, SHA-256, mode and owner or explicit absence for all twelve managed files;
- the exact active ALSA file and checksum;
- managed-directory existence, modes and owners;
- service load, active and enabled states;
- all four live mixer controls and raw output;
- loaded loopback parameters including `enable=Y`;
- structured DAC PID, user, command, file descriptor and access evidence;
- exact DAC hardware parameters;
- Stage C1 package and Stage C5 engine-plan fingerprints;
- a fresh rollback ledger which explicitly forbids using this rehearsal as an activation backup.

The same strict 44.1 kHz, S16_LE, stereo, period-size 1024 and buffer-size 8192 physical boundary used by Stage C3 remains mandatory.

## Expected checks

A successful Stage C6 capture produces these PASS checks in order:

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

The ordered event evidence must show:

```text
production-lock-boundary
rehearsal-lock-acquired
lock-contention-proved
fresh-identity-created
snapshot-started
snapshot-verified
manifest-generated
rehearsal-lock-released
```

No snapshot event may precede lock acquisition.

## Safety boundary

Stage C6 must not:

- create or open `/run/lock/a-clockwork-plex-audio-route.lock` for writing;
- create `/var/lib/a-clockwork-plex/split-bus/transactions`;
- write any managed production destination;
- install a package file or active ALSA route;
- stop, start, restart, enable or disable a service;
- execute `systemctl daemon-reload`;
- load or unload a module;
- change a mixer value;
- open a PCM or device node;
- start, stop or signal CamillaDSP;
- create or consume an approval marker;
- expose install, activation, failback, rollback or uninstall actions.

Only read-only inspection commands already used by Stage C3 are permitted.

## Evidence outputs

A successful Stage C6 run produces:

- `results.tsv`;
- `ordered-events.tsv`;
- `lock-state.tsv`;
- `identity.tsv`;
- `filesystem-state.tsv`;
- `rootfs/` copied originals;
- `absence-markers/`;
- `service-state.tsv`;
- `mixer-state.tsv` and `mixer-raw/`;
- `module-dac-state.tsv`;
- `dac-owners.tsv`;
- `dac-hw-params.txt`;
- `package-fingerprint.tsv`;
- `stage-c5-fingerprint.tsv`;
- `rollback-ledger.tsv`;
- `report.txt`;
- `evidence-manifest.tsv`.

## Promotion boundary

A successful Stage C6 rehearsal proves the root-owned lock-before-snapshot mechanics on the real appliance without creating a production writer.

It permits implementation review of the blocked production adapter and transaction command allowlist. It does not permit persistent installation or creation of the real production lock.

Persistent Stage C activation remains blocked until the production adapter, exact install/rollback implementation, runtime direct failback, EQ migration and physical failure tests are separately reviewed and explicitly authorised.
