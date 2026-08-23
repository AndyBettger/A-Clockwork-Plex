# Stage C14 production-lock-only rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C14 proves the next single boundary in the Stage C install program: exclusive acquisition and exact release of the one fixed production audio-route lock.

It does not create a production transaction, capture an activation-time filesystem snapshot, stage or install files, change services or mixer controls, open audio devices, select a route, or expose activation.

The only production-path mutation permitted by Stage C14 is the temporary lock file:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

That file must be created as a root-owned regular file with mode `0600`, held with an exclusive non-blocking `flock`, proven contended from a second independent descriptor, then unlinked while the exact original inode remains locked and finally closed.

## Roadmap position

```text
Stages A, A2, B   physical split-bus DSP, ALSA and real-DAC proof
Stage C0          physical alarm-safe direct-failback proof
Stages C1-C7      package, snapshot and root-owned rollback foundations
Stages C8-C9      one transaction authority and stronger evidence replay
Stage C10         typed host-operation contract; all operations blocked
Stage C11         immutable install, rollback, failback and uninstall programs
Stage C12         complete in-memory policy and failure simulation
Stage C13         six typed read-only real-host observations
Stage C14         real production-lock acquisition/release only
```

Persistent Stage C installation remains blocked after Stage C14.

## Fixed operation boundary

Stage C14 extends the Stage C13 read-only adapter with exactly two typed operations:

```text
acquire-production-lock
release-production-lock
```

The permitted operation set is therefore exactly eight operations:

```text
inspect-host-contract
inspect-production-lock
acquire-production-lock
release-production-lock
capture-service-state
capture-mixer-state
capture-loopback-state
capture-dac-state
```

The remaining 25 `AdapterOperation` values must continue to raise `ProductionAdapterBlocked` with their exact operation identity.

## Precondition

Before acquisition:

- the process must be root through one constrained sudo command;
- `/run/lock` must be a real root-owned directory;
- the fixed lock path must be absent;
- the current host contract must match Stage C13;
- the authoritative transaction root must not be created or written;
- no caller-supplied lock path, mode, owner, lease ID or timeout is accepted.

Any pre-existing object at the lock path is a hard failure. Stage C14 never deletes or replaces an object it did not create.

## Acquisition contract

The adapter must:

1. open the exact fixed pathname using `O_RDWR | O_CREAT | O_EXCL`;
2. add `O_CLOEXEC` and `O_NOFOLLOW` where available;
3. create the file with mode `0600`;
4. enforce owner `root:root` and mode `0600` through the opened descriptor;
5. acquire `LOCK_EX | LOCK_NB` on that descriptor;
6. record the descriptor inode;
7. verify the pathname still resolves to that same regular-file inode;
8. prove a second independently opened descriptor cannot obtain `LOCK_EX | LOCK_NB`;
9. generate the lease identity only after successful acquisition and contention proof;
10. return a typed `ProductionLockLease` for the exact fixed path.

The lease is adapter-generated and is not caller supplied.

## Held-lock observation contract

While the production lock is held:

- `inspect-production-lock` must report `exists=true` and `held_by_caller=true`;
- the observed owner must be UID/GID `0:0`;
- the observed mode must be `0600`;
- the observed inode must match the adapter-held descriptor evidence;
- the six Stage C13 typed observations must still match the stable host;
- no service, mixer, module, PCM, DAC or route state may change.

The Stage C13 observation identity remains non-authoritative. Holding the lock does not turn it into a production transaction identity.

## Release contract

Release must be exact and fail closed.

The adapter must:

1. require a currently held adapter-generated lease;
2. verify the descriptor is still open and locked;
3. verify the lock pathname is a regular file with the same inode, owner and mode;
4. unlink the pathname while the exact original inode remains locked;
5. release the flock and close the descriptor;
6. clear the adapter-held lease state;
7. require the pathname to be absent after release;
8. return a typed PASS receipt only after exact cleanup.

It must never unlink a pathname whose inode differs from the adapter-held descriptor.

A context-manager finalizer provides best-effort cleanup if the rehearsal exits unexpectedly, but successful acceptance requires the normal typed release operation.

## Explicitly forbidden

Stage C14 must not implement or invoke:

```text
create-authoritative-transaction
capture-filesystem-state
stage-candidate-files
candidate ALSA/sudoers/unit/CamillaDSP validation
service start/stop/restart/enable/disable
systemd daemon-reload
mixer writes
module load/unload
PCM or DAC open
music or alarm probes
route selection
commit manifest
failback
exact rollback
uninstall
transaction-root creation
approval marker creation or consumption
```

There is no generic command runner, raw caller-supplied argv, path override, callback dispatch table or dynamic method invocation.

## Rehearsal wrapper

The wrapper is prepare-only by default.

Prepare-only:

- invokes no sudo;
- creates no lock file;
- performs no host observation;
- creates no evidence directory;
- prints the exact guarded command.

The guarded mode requires:

```text
--rehearse-production-lock
--confirm STAGE-C14-PRODUCTION-LOCK-ONLY
```

It uses one constrained sudo command and a fresh evidence directory directly beneath `/var/tmp`:

```text
/var/tmp/a-clockwork-plex-stage-c14-production-lock.<suffix>
```

Root may write only to that evidence directory and the single temporary lock pathname.

## Acceptance checks

The guarded rehearsal must emit these checks in exact order:

1. `root-scope`
2. `protocol-conformance`
3. `pre-lock-host-contract`
4. `pre-lock-boundary`
5. `production-lock-acquired`
6. `lock-file-contract`
7. `lock-contention`
8. `held-lock-observation`
9. `read-only-host-observations`
10. `blocked-operation-boundary`
11. `production-lock-released`
12. `exact-lock-cleanup`
13. `evidence-integrity`
14. `activation-interface`

Acceptance requires:

- all fourteen checks are `PASS`;
- one adapter-generated lease is returned;
- the exact production lock is root-owned mode `0600` while held;
- independent contention is proved;
- the six typed real-host observations remain exact while held;
- exactly 25 other operations refuse with exact identities;
- normal typed release succeeds;
- the lock pathname is absent afterward;
- no authoritative transaction or transaction directory exists;
- no audio-appliance state changes;
- no activation interface exists.

## Evidence

A successful run writes only these evidence files beneath the fresh evidence root:

```text
results.tsv
lease.tsv
typed-observations.json
blocked-operations.tsv
lock-events.tsv
report.txt
evidence-manifest.tsv
```

The lease and observations are rehearsal evidence only. They are not an activation snapshot or approval marker.

## What Stage C14 does not prove

Stage C14 does not prove:

- authoritative transaction creation;
- transaction-directory ownership or persistence;
- exact activation-time filesystem snapshot;
- candidate validation or package staging;
- any service, mixer, module, PCM, DAC or route mutation;
- split-bus startup or health;
- runtime failback;
- exact rollback or explicit uninstall;
- reboot persistence.

Those remain later, separately guarded stages.

## Safety conclusion

Stage C14 is a lock-only escalation. It proves the coordination primitive required by every future policy program without granting access to the transaction or audio mutation layers.

Persistent Stage C activation remains blocked, and the old bare master-EQ installer remains prohibited.