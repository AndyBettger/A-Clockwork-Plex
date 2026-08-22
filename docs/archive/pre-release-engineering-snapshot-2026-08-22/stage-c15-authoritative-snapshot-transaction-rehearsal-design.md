# Stage C15 authoritative snapshot transaction rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C15 is the next isolated step in the reviewed install program after the physically proven Stage C14 production lock.

It rehearses only this prefix of the install policy:

```text
inspect host contract
inspect production lock
acquire production lock
create authoritative transaction identity and directory
capture exact filesystem state
capture exact service state
capture exact mixer state
capture exact loopback state
capture exact DAC state
verify and abort before mutation
remove the rehearsal transaction
release the production lock
```

No package staging, candidate validation, service stop, mixer write, route selection, managed-file installation, audio probe, CamillaDSP operation, commit, failback, rollback or uninstall action is implemented.

Persistent Stage C activation remains blocked.

## Roadmap position

```text
Stage C13  real typed read-only host observations
Stage C14  real production lock creation, contention and exact removal
Stage C15  real authoritative transaction root and fresh snapshot, then pre-mutation abort
Stage C16  later package staging and validation only
Later      separately guarded mutation, rollback, failback and persistence stages
```

Stage C15 is not an installation and does not leave an active transaction behind.

## Inputs

The guarded rehearsal accepts only:

```text
Stage C1 reviewed package root
Stage C14 physical evidence root
fresh Stage C15 evidence root
exact confirmation token
```

The package and Stage C14 roots must:

- be direct children of `/var/tmp`;
- use their exact expected prefixes;
- be real directories, not symlinks;
- remain owned by the invoking non-root user;
- retain mode `0700`;
- contain complete checksummed evidence;
- remain unchanged throughout the rehearsal.

The Stage C1 package is replayed and fingerprinted. The Stage C14 evidence must prove all fourteen checks, the exact root-owned mode-`0600` lock contract, contention, exact cleanup, twenty-five blocked operations and the final absent lock state.

## Fixed production paths

The only production paths Stage C15 may write are:

```text
/run/lock/a-clockwork-plex-audio-route.lock
/var/lib/a-clockwork-plex/split-bus/transactions/<generated-transaction-id>/...
```

No caller may supply or override either production path.

The transaction root is fixed by the Stage C10 contract:

```text
/var/lib/a-clockwork-plex/split-bus/transactions
```

## Parent-directory rules

The adapter records the pre-rehearsal existence, device, inode, type, mode, uid and gid of:

```text
/var/lib/a-clockwork-plex
/var/lib/a-clockwork-plex/split-bus
/var/lib/a-clockwork-plex/split-bus/transactions
```

Existing real directories are never rechmodded or rechowned.

Missing parents may be created only in fixed order with fixed root ownership and modes:

```text
/var/lib/a-clockwork-plex             root:root 0750
/var/lib/a-clockwork-plex/split-bus   root:root 0750
.../transactions                     root:root 0700
```

On normal pre-mutation abort, only directories created by this rehearsal may be removed, in reverse order, and only when empty. Existing directories must remain byte-for-byte and metadata-for-metadata unchanged.

Symlinks, non-directories, ownership changes, mode changes or path substitution are hard failures.

## Authoritative identity

After the real production lock is held, the adapter generates an identity with the form:

```text
stage-c15-install-<random-token>
```

The caller cannot provide or reuse it.

The adapter creates exactly one root-owned mode-`0700` transaction directory:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<transaction-id>
```

The typed result is:

```text
AuthoritativeTransaction(
    transaction=<generated TransactionIdentity>,
    snapshot=<generated SnapshotIdentity bound to that transaction>,
    action=install,
    package=<replayed Stage C1 PackageFingerprint>,
)
```

The transaction is authoritative only while:

- the same adapter owns the same production-lock lease;
- the exact transaction directory inode is present;
- the transaction is still in the `snapshot-open` state;
- no pre-mutation abort has completed.

It is not committed installation state.

## Package fingerprint

Stage C15 computes one deterministic lowercase SHA-256 digest from the complete regular Stage C1 package tree.

The digest input is the ordered sequence of:

```text
relative path NUL type NUL mode NUL file sha256 NEWLINE
```

for every package directory and regular file except no special object or symlink is permitted.

The adapter is initialised with the validated package root and independently recomputes the same fingerprint before creating the transaction. A caller-supplied mismatching `PackageFingerprint` is rejected before the production transaction root is touched.

## Transaction layout

The exact transaction directory contains:

```text
transaction.tsv
state.tsv
package-fingerprint.tsv
snapshot/
```

`transaction.tsv` records:

```text
transaction identity
snapshot identity
action
package fingerprint
host
architecture
invoking user
root pid
created timestamp
production lock lease identity
production authoritative = true
committed = false
```

`state.tsv` begins as:

```text
state  snapshot-open
mutation_started  false
committed  false
```

No candidate or installation directory exists in Stage C15.

## Exact snapshot

The snapshot reuses the physically and synthetically proven Stage C3/C6 capture primitives rather than defining another backup format.

The `snapshot/` tree must contain:

```text
filesystem-state.tsv
filesystem-copy/...
service-state.tsv
mixer-state.tsv
mixer-raw/...
module-dac-state.tsv
dac-owners.tsv
package-fingerprint.tsv
rollback-ledger.tsv
evidence-manifest.tsv
```

The filesystem capture records:

- exact current ALSA content, checksum, mode, uid and gid;
- explicit absence for all twelve managed package files;
- existence, mode, uid and gid of managed directories;
- no destination conflicts;
- no symlink or special object.

The typed `FilesystemSnapshot` must return:

```text
identity = transaction.snapshot
managed_entries > 0
exact = true
```

The four state-capture methods accept only the adapter-generated authoritative transaction identity and return the existing immutable typed payloads.

## Snapshot verification

Before pre-mutation abort, Stage C15 requires:

- package fingerprint equality;
- exact transaction and snapshot identity binding;
- transaction directory root:root mode `0700`;
- all twelve managed files recorded absent;
- exact current ALSA checksum;
- exact six-service boundary;
- exact four mixer values;
- exact loaded loopback contract;
- exact DAC format and structured current owner;
- complete regular checksummed transaction tree;
- unchanged Stage C1 and Stage C14 input trees;
- production lock still held by the same adapter.

## Pre-mutation abort

After successful verification, Stage C15 deliberately stops before package staging.

The transaction state is changed atomically to:

```text
state  aborted-before-mutation
mutation_started  false
committed  false
```

A complete evidence copy of the verified transaction tree is written beneath the fresh user-visible Stage C15 evidence root and explicitly labelled:

```text
rehearsal_copy = true
production_authoritative = false
reusable_for_activation = false
```

The real transaction directory is then removed exactly while the production lock remains held.

The adapter must verify:

- the pathname still refers to the original transaction directory device/inode;
- the tree contains no symlink or special object;
- state is `aborted-before-mutation`;
- no `candidate`, `installed` or `committed` marker exists;
- every removed entry belongs beneath the exact generated transaction directory.

Only then may it remove any empty parent directories created by this rehearsal.

## Lock lifetime

The production lock remains held across:

```text
transaction identity generation
transaction-directory creation
all snapshot captures
snapshot verification
pre-mutation abort record
transaction evidence copy
exact transaction cleanup
parent restoration verification
```

The lock is released only after the real transaction pathname is absent and all pre-existing parent metadata has been verified unchanged.

A lock-release failure after successful cleanup fails closed and reports the retained lock state; it must not recreate the transaction.

## Typed operation boundary

Stage C15 permits exactly ten operations:

```text
inspect-host-contract
inspect-production-lock
acquire-production-lock
release-production-lock
create-authoritative-transaction
capture-filesystem-state
capture-service-state
capture-mixer-state
capture-loopback-state
capture-dac-state
```

The other twenty-three `AdapterOperation` values remain inherited as exact `ProductionAdapterBlocked` refusals.

No generic command runner, dynamic method dispatch, raw `argv`, caller-supplied production path, shell execution or network access exists.

## Guarded wrapper

The wrapper is prepare-only by default.

Prepare-only:

- runs no sudo;
- creates no evidence directory;
- creates no lock or transaction directory;
- performs no host observation;
- prints the exact guarded command.

The guarded mode requires:

```text
--rehearse-authoritative-snapshot
--confirm STAGE-C15-AUTHORITATIVE-SNAPSHOT-ABORT
```

It uses one constrained sudo command.

## Acceptance checks

The guarded rehearsal emits these checks in this exact order:

1. `root-scope`
2. `input-replay`
3. `protocol-conformance`
4. `pre-lock-host-contract`
5. `pre-lock-boundary`
6. `production-lock-acquired`
7. `transaction-parent-boundary`
8. `authoritative-transaction-created`
9. `transaction-identity-binding`
10. `filesystem-snapshot`
11. `service-snapshot`
12. `mixer-snapshot`
13. `loopback-snapshot`
14. `dac-snapshot`
15. `snapshot-integrity`
16. `blocked-operation-boundary`
17. `pre-mutation-abort`
18. `transaction-evidence-copy`
19. `exact-transaction-cleanup`
20. `production-lock-released`
21. `input-integrity`
22. `evidence-integrity`
23. `activation-interface`

Acceptance requires all twenty-three checks to pass.

## Evidence

A successful run writes only to the temporary production lock, the disposable real transaction tree and the fresh Stage C15 evidence root.

The retained evidence root contains:

```text
results.tsv
identity.tsv
parent-state.tsv
lock-events.tsv
typed-observations.json
blocked-operations.tsv
transaction-rehearsal-copy/
cleanup-state.tsv
report.txt
evidence-manifest.tsv
```

The copied transaction is review evidence only and must never be reused as an activation backup.

## Explicitly not proved

Stage C15 does not prove:

- candidate package staging;
- ALSA, sudoers, systemd-unit or CamillaDSP candidate validation;
- stopping application services;
- DAC release;
- managed-file installation;
- daemon reload;
- split-bus route selection;
- managed Stage C service startup;
- finite music or alarm probes;
- dashboard health;
- installation commit;
- automatic exact rollback after mutation;
- runtime direct failback;
- explicit uninstall;
- reboot persistence.

Those remain later, separately guarded stages.

## Safety conclusion

Stage C15 advances only from a physically proven production lock to a disposable authoritative snapshot transaction that is aborted and removed before any managed-audio mutation.

The stable direct audio graph remains active throughout. The old master-EQ installer remains blocked. PR #2 must stay Draft, open and unmerged until explicit approval.