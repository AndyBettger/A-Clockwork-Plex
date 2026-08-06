# Stage C21 disposable temporary approval removal design

## Purpose

Prove the exact rollback deletion boundary for one canonical temporary activation
approval beneath a fresh disposable laboratory root.

This slice removes only the temporary record already published by the preceding
disposable proof. It does not implement committed promotion, production paths,
package installation, service actions, route changes, ALSA access, CamillaDSP,
device access or Pi execution.

## Existing authorities

The removal proof reuses three already-reviewed objects without transferring
their ownership:

```text
DisposableC20LockOwnerV7
    sole owner of lock creation, flock, exact lock unlink, unlock and close

DisposableApprovalRootV7
    owner of the no-follow split-bus approval-directory descriptor

TemporaryApprovalRecordPlanV7 / CommittedApprovalRecordPlanV7
    canonical bytes and exact raw-byte classification authority
```

The remover may borrow the approval directory descriptor. It may not acquire,
release, duplicate or close the transaction lock, create another approval root,
or release either existing authority.

## Preconditions

Automatic removal is allowed only when all of the following are proved in the
same call:

- the disposable C20 owner still holds its original descriptor and exclusive
  flock;
- the lock pathname, device, inode, owner and mode are unchanged;
- the lock contains exactly `<lease-id>\n`;
- the lease ID equals the temporary plan lease;
- the approval-root descriptor and pathname still identify the same real mode
  `0700` directory owned by the test UID/GID;
- `activation-approved` opens with `O_NOFOLLOW|O_CLOEXEC`;
- descriptor and pathname identify the same regular mode `0600` inode;
- owner UID/GID match the disposable approval root;
- size is bounded by 64 KiB;
- raw bytes exactly equal the canonical temporary plan bytes;
- raw-byte SHA-256 equals the temporary plan encoded digest;
- the existing exact classifier returns `exact-temporary`.

Decoded-record equality is not sufficient.

An absent, exact-committed, mismatched or unobservable record is a failed
precondition and must not be treated as successful idempotent removal.

## Exact removal sequence

```text
REVERIFY OWNER-HELD LOCK AND CANONICAL LEASE
→ classify public record and require exact-temporary
→ open activation-approved relative to the held directory descriptor
→ verify type, mode, owner, bounded size, raw bytes and SHA-256
→ record descriptor device/inode
→ re-check public name-to-descriptor identity immediately before unlink
→ unlink only activation-approved relative to the held directory descriptor
→ prove the still-open descriptor remains the exact temporary inode and bytes
→ require the unlinked descriptor link count to be zero
→ fsync the held approval-directory descriptor
→ classify the public name and require absent
→ REVERIFY OWNER-HELD LOCK AND CANONICAL LEASE
→ TEMPORARY REMOVED
```

The descriptor remains open through unlink and post-unlink verification. This
proves that the inode removed from the public namespace is the exact inode whose
canonical bytes were verified before deletion.

No caller-supplied filename, path or payload is accepted.

## Mutation boundary

The remover may perform exactly two filesystem mutations:

1. `unlink("activation-approved", dir_fd=held_approval_directory)`;
2. `fsync(held_approval_directory)`.

It has no create, write, truncate, chmod, chown, link, rename, replace, exchange,
lock, service, command or audio capability.

The final name-to-descriptor identity check occurs immediately before `unlink`,
with no injected callback between the check and deletion. A substitution made at
the last injectable pre-unlink boundary must therefore be detected before the
unlink call.

## Fault boundaries

The disposable implementation must inject failures around each meaningful
observation and mutation boundary:

```text
before-public-open
after-public-open
after-public-read
before-final-name-recheck
after-public-unlink
after-unlinked-descriptor-verification
before-removal-directory-fsync
after-removal-directory-fsync
before-absence-observation
after-absence-observation
before-final-owner-verification
after-final-owner-verification
```

There is deliberately no fault callback between the final identity check and
`unlink`.

## Post-exception reconciliation

Reconciliation starts by re-verifying owner authority and classifying the public
raw bytes. It never blindly retries `unlink`.

| observed public state | required result |
| --- | --- |
| absent | require the retained open descriptor to prove the exact temporary inode; re-fsync the directory, re-prove absence and return removed |
| exact-temporary | removal did not complete; retain the lock and permit only a separately reviewed recovery invocation |
| exact-committed | manual reconciliation; never remove |
| mismatched | manual reconciliation; never remove |
| observation-failure | manual reconciliation; never remove |

If `exact-temporary` is observed after an exception and an exact descriptor had
already been captured, its device/inode must still match the public name.
Otherwise the result is manual reconciliation rather than retry permission.

An absent public name is not enough by itself. Reconciled success also requires:

- an exact temporary descriptor captured before the exception;
- unchanged descriptor identity and canonical bytes;
- zero remaining hard links after removal;
- a successful recovery directory `fsync`;
- repeated absent classification;
- repeated owner-held lock and lease verification.

If any of those proofs are unavailable, the owner lock remains held for manual
reconciliation.

## Typed outcomes

The remover returns one of three dispositions:

```text
TEMPORARY_REMOVED
    PASS; public approval absent; namespace durability proved; owner lock held

TEMPORARY_RETAINED_RECOVERY
    FAIL; exact temporary approval remains; no mutation retry occurred;
    a separately reviewed recovery invocation may be attempted

MANUAL_RECONCILIATION
    FAIL; no automatic removal or recovery permission
```

Every result records the observed classifier state, whether reconciliation
followed an exception, whether reviewed recovery is permitted, whether manual
reconciliation is required, whether the owner lock remains held, and whether the
public approval is proved absent.

## Required tests

The real Linux filesystem suite must prove:

- normal exact removal and directory durability;
- the public inode opened before unlink is the inode removed;
- all twelve fault boundaries;
- failures before unlink leave the same exact temporary inode and allow only
  reviewed recovery;
- failures after unlink reconcile to exact durable absence without another
  unlink;
- absence before the operation is refused;
- committed, mismatched, non-canonical, wrong-mode and symlink records are never
  removed;
- a public-name substitution at the final injectable boundary is detected and
  not unlinked;
- observation failure after unlink does not invent success;
- directory `fsync` failure must be repaired before success is reported;
- lost owner authority prevents both removal and reconciled success;
- independent acquisition remains blocked for every live-owner outcome;
- the remover contains no create/write/replacement/command/audio boundary;
- all four v7 production approval operations remain blocked;
- the operation vocabulary remains exactly forty-two entries.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock or approval directory is opened;
- no committed approval is created;
- no package, service, process, route, mixer or device is touched;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Roadmap

### Done

- exact canonical record planning and classification;
- disposable owner-held lock and lease binding;
- no-follow approval-root authority;
- atomic no-replace temporary publication;
- this separate exact-removal design.

### Current

Implement and failure-inject disposable exact temporary removal beneath fresh
laboratory roots.

### Next

After a result document and clean CI checkpoint, design committed promotion as a
one-way exchange with forward-recovery-only behaviour once exact committed bytes
are visible.

### Risks and gates

Committed promotion remains out of scope. Production integration remains
blocked until removal is independently proved and reviewed.