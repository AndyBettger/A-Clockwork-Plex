# Stage C21 disposable temporary approval removal result — 2026-08-06

## Outcome

**PASS — one exact canonical temporary approval can now be removed for rollback by unlinking only the verified public inode beneath a disposable no-follow approval root, while the separate C20-shaped owner retains exclusive lock lifetime.**

This proof ran exclusively beneath fresh temporary laboratory roots. It contains no production approval path, committed promotion, installer command, service action, ALSA access, CamillaDSP process, device access or Pi operation.

## Design

```text
c486279eedfb8a41597adf6c75bbcc162592301d
docs: design disposable Stage C21 temporary removal
```

The removal design preserves three independent authorities:

```text
DisposableC20LockOwnerV7
    owns lock creation, flock, exact lock unlink, unlock and close

DisposableApprovalRootV7
    owns one no-follow approval-root directory descriptor

DisposableTemporaryApprovalRemoverV7
    may verify and unlink only the exact fixed public temporary approval,
    then fsync the already-held approval directory
```

The remover cannot acquire, release, duplicate or close the owner-held lock. It cannot create an approval candidate, write or truncate record bytes, rename or exchange records, promote a committed approval, run commands, manage services or access audio.

## Implementation

Disposable exact temporary remover:

```text
scripts/stage_c_transaction/disposable_temporary_approval_remover_v7.py

c71bebd11056ad586408b1f203b980c476119d70
feat: remove disposable Stage C21 temporary approval
```

Real Linux filesystem and failure-injection suite:

```text
tests/test_stage_c_disposable_temporary_approval_removal_v7.py

1204562d86d6e0d0a3abf343158ff3e9f7971231
test: failure-inject disposable Stage C21 temporary removal
```

## Exact removal sequence

The successful sequence is:

```text
reverify owner-held lock and exact canonical lease
→ classify public approval and require exact-temporary
→ open activation-approved with O_NOFOLLOW and O_CLOEXEC
→ verify regular mode-0600 file, owner, bounded size and path/descriptor identity
→ read and verify exact canonical temporary bytes and SHA-256
→ retain the exact descriptor and device/inode identity
→ re-check the public name maps to that same descriptor immediately before unlink
→ unlink only activation-approved relative to the held approval-directory descriptor
→ prove the still-open descriptor remains the exact temporary inode and bytes
→ prove that inode now has zero namespace links
→ fsync the held approval-directory descriptor
→ classify the public name and require absent
→ reverify owner-held lock and canonical lease
→ TEMPORARY REMOVED
```

Keeping the exact file descriptor open across `unlink` proves that the inode removed from the namespace is the same inode whose canonical bytes, digest, metadata and public-name identity were verified before deletion.

The final injectable boundary occurs before the last name-to-descriptor identity check. There is no callback between that identity check and `unlink`.

## Mutation boundary

The remover contains only two filesystem mutations:

```text
unlink("activation-approved", dir_fd=held_approval_directory)
fsync(held_approval_directory)
```

It has no `O_CREAT`, write, pwrite, truncate, chmod, chown, link, rename, replace, exchange, mkdir, flock, subprocess, service or audio boundary.

No path, filename or payload is supplied by a caller.

## Exact preconditions

Automatic removal is refused unless:

- the original disposable owner still holds its exact descriptor and exclusive lock;
- lock pathname, device, inode, mode and owner are unchanged;
- lock content equals the canonical `<lease-id>\n` bytes;
- the lease equals the temporary approval plan;
- the approval-root descriptor and pathname remain the same real mode-`0700` directory;
- the public approval is a real mode-`0600` regular file with expected ownership;
- descriptor and public pathname identify the same device/inode;
- raw bytes exactly equal the canonical temporary plan;
- the byte digest equals the planned encoded SHA-256;
- exact classification returns `exact-temporary`.

Decoded semantic record equality is never sufficient.

An already absent approval is not treated as idempotent success. It is refused because this operation must prove that it owns the exact rollback deletion event.

## Exception reconciliation

Every observation and mutation boundary was fault-injected. Reconciliation never blindly retries `unlink`.

| observed public state | result |
| --- | --- |
| absent with exact retained descriptor, zero links and repaired directory durability | removed; PASS reconciled without another unlink |
| absent without exact retained descriptor proof | manual reconciliation |
| exact temporary on the original tracked inode | retained; FAIL with separately reviewed recovery invocation permitted |
| exact temporary on a different inode | manual reconciliation |
| exact committed | manual reconciliation; never remove |
| mismatched | manual reconciliation; never remove |
| observation failure | manual reconciliation |

A directory `fsync` failure after unlink is not accepted merely because the public name currently appears absent. Reconciliation must successfully repeat the directory `fsync`, prove stable absence again and reverify owner authority before returning PASS.

An exact temporary record that reappears with identical canonical bytes but a different inode does not inherit recovery permission. Byte equality cannot replace namespace identity.

## Typed outcomes

The remover returns one of three frozen dispositions:

```text
TEMPORARY_REMOVED
    PASS; exact public inode removed, directory durability proved,
    public approval absent and owner lock still held

TEMPORARY_RETAINED_RECOVERY
    FAIL; exact temporary approval remains on the same verified inode;
    no retry occurred and only a separately reviewed recovery invocation is permitted

MANUAL_RECONCILIATION
    FAIL; no automatic deletion or recovery permission
```

Every result records exact classifier state, temporary encoded digest, exception-reconciliation status, recovery permission, manual-reconciliation requirement, current owner-lock state and proved public absence.

## Tests

The real Linux filesystem tests prove:

- normal exact removal;
- the inode opened before unlink is exactly the inode removed;
- descriptor-pinned raw bytes and SHA-256 remain exact after unlink;
- removed inode link count is zero;
- approval-directory durability is required;
- all twelve named fault boundaries;
- pre-unlink faults retain the same exact inode and grant only reviewed-recovery permission;
- post-unlink faults reconcile exact durable absence without another unlink;
- a failed first directory `fsync` is repaired before success;
- absent precondition is refused rather than accepted idempotently;
- committed, mismatched, noncanonical, wrong-mode and symlink records are never removed;
- final-boundary public-name substitution is detected and the replacement is not unlinked;
- identical temporary bytes recreated on another inode do not gain recovery permission;
- unavailable post-unlink observation retains manual authority;
- lost owner or canonical-lease authority prevents removal;
- wrong-lease and different-root authorities are rejected;
- every live-owner outcome leaves independent lock acquisition blocked;
- result records are frozen and reject inconsistent permissions;
- the module contains exactly one `unlink` call and no create/write/promotion boundary;
- the v7 adapter vocabulary remains exactly forty-two operations;
- all four production approval operations remain blocked.

## Validation

GitHub Actions run:

```text
31060373426
```

validated branch head:

```text
1204562d86d6e0d0a3abf343158ff3e9f7971231
```

Full result:

```text
Ran 1099 tests in 6.527s

OK
```

Compilation, JavaScript/page wiring, shell validation and all inherited safety, runtime, transaction and sandbox suites also passed.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock was opened or changed;
- no production approval root or approval record was created or removed;
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
- descriptor-pinned exact temporary removal;
- exact inode, bytes, digest and directory-durability verification;
- failure-injected removal reconciliation;
- 1,099-test CI pass.

### Current

Design committed approval promotion as a separate one-way authority boundary.

### Next

The committed-promotion design must require the exact temporary public record, create and fsync one exact private committed candidate, atomically exchange it with `activation-approved`, fsync the directory, classify the public name as exact-committed, and track the parked temporary inode for exact cleanup.

Once exact committed bytes become visible, recovery must be forward-only. The implementation must never exchange the committed record back to temporary state.

### Risks and gates

Committed promotion has not been implemented. The next step remains design-first and disposable-only. Production paths, production adapter integration, appliance commands, package installation, service actions, audio access, Pi access and lock release remain blocked.