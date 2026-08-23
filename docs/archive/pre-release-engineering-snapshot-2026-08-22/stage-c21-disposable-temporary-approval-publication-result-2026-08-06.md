# Stage C21 disposable temporary approval publication result — 2026-08-06

## Outcome

**PASS — one exact canonical temporary approval can now be published without replacement beneath a no-follow disposable approval root while a separate C20-shaped owner retains exclusive lock lifetime.**

This proof ran exclusively beneath fresh temporary laboratory roots. It contains no production approval path, committed promotion, installer command, service action, ALSA access, CamillaDSP process, device access or Pi operation.

## Design

```text
2e0acc01a366e5b614e8de8a04de98aa0835f8a5
docs: design disposable Stage C21 temporary approval publication
```

The design preserves three separate authorities:

```text
DisposableC20LockOwnerV7
    owns lock creation, flock, exact unlink, unlock and close

DisposableApprovalRootV7
    owns one no-follow approval-root directory descriptor

DisposableTemporaryApprovalPublisherV7
    owns only one tracked private candidate, no-replace publication,
    exact classification and removal of its private alias
```

The publisher cannot acquire, release, duplicate or close the owner-held lock. The lock owner cannot publish an approval. The approval-root authority owns no lock operation.

## Implementation

Disposable approval-root authority:

```text
scripts/stage_c_transaction/disposable_approval_root_v7.py

48b43a0afb696dc81329f8fba85e4139adc75e73
feat: add disposable Stage C21 approval root authority
```

Disposable temporary publisher:

```text
scripts/stage_c_transaction/disposable_temporary_approval_publisher_v7.py

e90bd75ac61787063f61428f5252aa0a162e6a8d
feat: publish disposable Stage C21 temporary approval
```

Real Linux filesystem and failure-injection suite:

```text
tests/test_stage_c_disposable_temporary_approval_publication_v7.py

c95c3c58be9e90d7b61f724aec8f0f20acea67c3
test: failure-inject disposable Stage C21 temporary publication
```

## Disposable layout

Each test uses one fresh, empty, real mode-`0700` laboratory root owned by the test UID/GID and reproduces only this relative layout:

```text
run/lock/a-clockwork-plex-audio-route.lock
var/lib/a-clockwork-plex/split-bus/activation-approved
```

The approval directory chain is created and opened component by component with directory descriptors and no-follow flags. Every directory is mode `0700`. Public and private approval objects are regular mode-`0600` files.

The new modules contain no production absolute path, root-mode constructor, command, subprocess, service, systemd, ALSA, mixer, PCM, DAC or CamillaDSP boundary.

## Publication sequence

The successful sequence is:

```text
reverify owner-held lock and exact canonical lease
→ observe public approval as absent
→ create one internal private candidate exclusively
→ record candidate device and inode
→ pwrite exact planned temporary bytes
→ truncate to exact length
→ fsync candidate
→ verify candidate metadata, bytes and SHA-256
→ hard-link candidate to activation-approved without replacement
→ fsync approval-root directory
→ prove public bytes exactly match the temporary plan
→ prove public and private names are the same inode
→ unlink only the tracked private alias
→ fsync approval-root directory
→ prove private alias absent
→ classify public bytes as exact-temporary
→ reverify owner-held lock and canonical lease
```

Hard-link publication provides atomic no-replace behaviour. A pre-existing `activation-approved` name causes publication to fail rather than replacing it.

An already exact temporary public record is accepted idempotently without creating or writing another candidate.

## Exact observation

Public observation is bounded to 64 KiB and requires:

- no-follow open;
- regular file type;
- mode `0600`;
- expected UID/GID;
- descriptor/path device and inode identity;
- stable size and identity while raw bytes are read.

Raw bytes are passed directly to the existing exact classifier. Semantically equivalent but differently encoded JSON remains `mismatched`.

## Exception reconciliation

Every publication boundary was fault-injected and reconciled by exact post-exception observation:

| public state | result |
| --- | --- |
| absent | remove only the tracked private inode; exact rollback may proceed |
| exact temporary | remove only the verified private alias; continue without retry |
| exact committed | manual reconciliation; retain lock |
| mismatched | manual reconciliation; retain lock |
| observation failure | manual reconciliation; retain lock |

There is no blind publication retry. Exact temporary observation after an exception is treated as completed publication, not permission to publish again.

If private cleanup cannot prove the tracked inode, automatic unlink is refused and the owner-held lock remains retained for manual reconciliation.

## Tests

The real Linux filesystem tests prove:

- exact successful publication and raw-byte identity;
- public/private inode identity during hard-link publication;
- no-replace behaviour for pre-existing mismatched and committed records;
- unchanged pre-existing public inode and bytes after refusal;
- idempotent exact-temporary success with no second candidate;
- cleanup and rollback permission for failures before public link creation;
- same-call reconciliation for failures after public link creation;
- candidate and directory durability boundaries;
- partial `pwrite` cleanup while the public name remains absent;
- observation failure after publication retains manual authority;
- a substituted private symlink is never unlinked automatically;
- symlinked or wrong-mode approval ancestors are rejected;
- closed-owner, wrong-lease and different-root authorities are rejected;
- every publisher outcome leaves independent lock acquisition blocked until the owner explicitly closes;
- static absence of production paths, commands, audio access, replacement, rename, exchange, lock acquisition and descriptor duplication;
- the v7 adapter vocabulary remains exactly forty-two operations;
- all four production approval operations remain blocked.

## Validation

GitHub Actions run:

```text
31059657364
```

validated branch head:

```text
c95c3c58be9e90d7b61f724aec8f0f20acea67c3
```

Full result:

```text
Ran 1086 tests in 5.178s

OK
```

Compilation, JavaScript/page wiring, shell validation and all inherited safety and sandbox suites also passed.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock was opened or changed;
- no production approval root or approval record was created;
- no committed approval was produced;
- no package was installed;
- no service, route, mixer, process, endpoint or device was touched;
- all four v7 production approval operations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Roadmap

### Done

- guarded production-writer design;
- non-owning borrowed-lock observation;
- disposable canonical lock-lease binding;
- no-follow disposable approval-root authority;
- atomic no-replace temporary publication;
- exact raw-byte and inode verification;
- failure-injected publication reconciliation;
- 1,086-test CI pass.

### Current

Design exact temporary approval removal as a separate rollback boundary.

### Next

The removal slice must require exact owner authority, canonical lease, exact temporary raw bytes, no-follow descriptor/name identity, one fixed public name, exact unlink, approval-directory `fsync`, proved absence and post-exception classification.

### Risks and gates

Removal may delete only an exact planned temporary record while the same owner retains authority. It must refuse an absent, committed, mismatched, substituted or unobservable record. It remains disposable-only and may not add committed promotion, production paths, appliance commands, package installation, service actions, Pi access or a production adapter implementation.
