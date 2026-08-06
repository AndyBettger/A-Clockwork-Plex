# Stage C21 disposable committed approval promotion design

## Status

**Design only — no production approval writer, no Pi action and no committed promotion capability exists until the disposable implementation and its failure matrix pass.**

This boundary follows the accepted disposable temporary publication and exact temporary removal proofs. It operates only beneath a fresh private laboratory root using the existing production-shaped relative layout:

```text
run/lock/a-clockwork-plex-audio-route.lock
var/lib/a-clockwork-plex/split-bus/activation-approved
```

No absolute production path, package installation, service operation, ALSA route, CamillaDSP process, device or physical rehearsal is in scope.

## Purpose

Promotion changes one exact canonical temporary approval into the exact committed approval derived from it. This is the first deliberately one-way approval transition.

The central rule is:

> Once exact committed bytes are publicly visible, every automatic action is forward recovery. No code path may exchange the temporary record back into the public name.

The historical shared `ApprovalStore.replace_exact()` is not suitable for this proof because its exception handler may reverse an exchange. The disposable promoter therefore owns a separate, narrower exchange state machine with no reverse-exchange call at all.

## Separate authorities

The proof retains three independent authorities:

```text
DisposableC20LockOwnerV7
    owns lock creation, exclusive flock, exact lock unlink, unlock and close

DisposableApprovalRootV7
    owns one no-follow approval-directory descriptor and bounded public observation

DisposableCommittedApprovalPromoterV7
    may create one private committed candidate, exchange it once with the fixed
    public approval name, remove only the parked exact temporary inode and fsync
    the already-held approval directory
```

The promoter cannot acquire, duplicate, unlock, unlink or close the owner-held lock. It cannot select or restore an audio route, run a command, manage a service, start a process or access a device.

## Fixed objects

Public name:

```text
activation-approved
```

Private candidate prefix:

```text
.activation-approved.stage-c21-commit-
```

The caller supplies no path, filename, bytes, phase or digest. The promoter receives only:

- one live `DisposableC20LockOwnerV7`;
- the `DisposableApprovalRootV7` owned by that same owner;
- one exact `TemporaryApprovalRecordPlanV7`;
- the exact `CommittedApprovalRecordPlanV7` derived from that temporary plan;
- an optional test-only fault hook.

## Preconditions

Before creating a candidate, the promoter must prove:

1. the owner still holds its original descriptor and exclusive lock;
2. lock pathname, device, inode, mode and owner are unchanged;
3. lock content is exactly the canonical `<lease-id>\n` bytes;
4. the lease equals the temporary and committed plans;
5. the approval-root descriptor and pathname remain the same real mode-`0700` directory;
6. the public approval is a real current-user mode-`0600` regular file;
7. public descriptor and pathname identify the same device/inode;
8. public raw bytes equal `TemporaryApprovalRecordPlanV7.encoded_bytes` exactly;
9. public SHA-256 equals the temporary encoded digest;
10. exact classification returns `EXACT_TEMPORARY`.

An absent, committed, mismatched, noncanonical, wrong-mode, symlinked or unavailable public approval is refused. Exact committed state at entry is not accepted as idempotent success because a new invocation cannot prove ownership of the earlier one-way transition.

## Candidate construction

The private committed candidate is created relative to the held approval-directory descriptor with:

```text
O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC
mode 0600
```

The promoter records its device/inode immediately. It then:

```text
pwrite exact committed bytes
→ ftruncate exact length
→ fsync candidate
→ verify descriptor/name identity, owner, mode and bounded size
→ verify exact committed bytes and encoded SHA-256
→ require exact-committed classification
```

Any failure before exchange removes only that tracked private candidate after proving its device/inode. The public temporary inode must remain unchanged. There is no blind retry.

## Descriptor-pinned exchange

Before exchange, both objects remain open:

- the public temporary descriptor pins the exact temporary inode;
- the private candidate descriptor pins the exact committed inode.

Immediately before the syscall, the promoter rechecks that:

- `activation-approved` maps to the pinned temporary descriptor;
- the private name maps to the pinned committed descriptor;
- both still have exact owner, mode, size, bytes and digest.

There is no callback between these final name checks and the exchange.

The only exchange operation is:

```text
renameat2(private-committed, activation-approved, RENAME_EXCHANGE)
```

After a successful exchange:

```text
activation-approved
    must identify the pinned committed inode and exact committed bytes

private candidate name
    must identify the pinned temporary inode and exact temporary bytes
```

The implementation contains exactly one forward exchange call site and no reverse-exchange call site.

## Successful state machine

```text
REVERIFY OWNER AND CANONICAL LEASE
→ require exact public temporary bytes and pin temporary descriptor/inode
→ create and pin exact private committed candidate
→ fsync candidate
→ reverify both descriptors and both names
→ atomic RENAME_EXCHANGE
→ verify public committed inode and parked temporary inode
→ fsync approval directory
→ classify public approval and require exact-committed
→ reverify parked private name is the pinned exact temporary inode
→ unlink only that private name
→ prove pinned temporary inode now has zero namespace links
→ fsync approval directory
→ prove private name absent
→ classify public approval and require exact-committed
→ prove public committed name still maps to the pinned committed inode
→ REVERIFY OWNER AND CANONICAL LEASE
→ COMMITTED PROMOTED
```

The owner lock remains held after every result. Lock release remains solely the owner/executor boundary.

## One-way reconciliation

Exception reconciliation always begins with owner re-verification and raw public classification. It never invokes the exchange again inside the same call and never exchanges records back.

### Public exact temporary

If the public name still identifies the original pinned temporary inode:

- the exchange did not become the visible public state;
- remove only the exact tracked committed candidate if it still identifies the pinned committed inode;
- fsync the directory;
- prove private absence, exact public temporary identity and owner authority;
- return a typed failed result permitting only a separately reviewed retry invocation.

If exact temporary bytes are attached to a different inode, automatic cleanup and retry permission are forbidden.

### Public exact committed

Exact committed state starts forward recovery permanently. The promoter must:

- require the public name to identify the pinned committed candidate inode;
- require exact committed raw bytes and digest;
- repeat the approval-directory `fsync`;
- if the private name exists, require it to identify the pinned exact temporary inode before unlinking it;
- if the private name is already absent, require the pinned temporary descriptor to have zero links;
- fsync the directory after any cleanup;
- prove private absence and stable exact committed public identity;
- reverify owner authority.

If all proofs succeed, return `COMMITTED_PROMOTED` with `reconciled_after_exception=True`.

If exact committed bytes are public but private cleanup, durability, inode identity or owner authority cannot be proved, return `COMMITTED_FORWARD_RECOVERY_REQUIRED`. The public committed record is never replaced or removed.

### Other public states

| observed state | result |
| --- | --- |
| absent | manual reconciliation; never recreate automatically |
| exact temporary on different inode | manual reconciliation |
| exact committed on different inode | committed forward recovery required; never exchange back |
| mismatched | manual reconciliation |
| observation failure | manual reconciliation |

No state permits reverse exchange.

## Typed outcomes

```text
COMMITTED_PROMOTED
    PASS; exact committed candidate inode is public, parked temporary inode is
    durably removed, public classification is exact-committed and owner lock remains held

TEMPORARY_RETAINED_RECOVERY
    FAIL; exact original temporary inode remains public, exact committed candidate
    is absent, no same-call retry occurred and only a separately reviewed retry is permitted

COMMITTED_FORWARD_RECOVERY_REQUIRED
    FAIL; exact committed bytes are public or the one-way boundary may have been crossed,
    automatic rollback is forbidden and owner authority must remain held

MANUAL_RECONCILIATION
    FAIL; no automatic retry, cleanup or state transition is authorised
```

Results record:

- observed classifier state;
- temporary and committed encoded SHA-256 values;
- whether the exception was reconciled;
- whether reviewed retry is permitted;
- whether committed forward recovery is required;
- whether manual reconciliation is required;
- whether the owner lock remains held;
- whether the private name is proved absent;
- whether public exact committed identity is proved.

## Fault boundaries

The disposable suite must inject at least:

```text
before-public-temporary-open
after-public-temporary-open
after-public-temporary-read
before-candidate-create
after-candidate-create
after-candidate-write
after-candidate-truncate
after-candidate-fsync
before-final-exchange-name-recheck
after-exchange
before-exchange-directory-fsync
after-exchange-directory-fsync
before-committed-observation
after-committed-observation
before-parked-temporary-unlink
after-parked-temporary-unlink
before-cleanup-directory-fsync
after-cleanup-directory-fsync
before-final-committed-observation
after-final-committed-observation
before-final-owner-verification
after-final-owner-verification
```

The suite must also simulate an exchange helper that performs the real exchange and then raises, proving classification—not a local Boolean—controls forward recovery.

## Required tests

Real Linux filesystem tests beneath fresh temporary directories must prove:

- exact normal promotion;
- public committed inode equals the original candidate inode;
- parked temporary inode equals the original public inode;
- parked temporary descriptor reaches zero links after cleanup;
- candidate and both namespace mutations are durably fsynced;
- every named fault boundary;
- all pre-exchange failures leave the same public temporary inode and no private candidate;
- all post-exchange failures reconcile forward without another exchange;
- a failed first directory `fsync` is repaired before success;
- a helper that exchanges then raises still reconciles exact committed state forward;
- exact committed entry state is refused rather than idempotently accepted;
- absent, mismatched, noncanonical, wrong-mode and symlink states are untouched;
- public or private last-boundary substitution is detected and never unlinked;
- identical temporary or committed bytes on different inodes do not inherit authority;
- unavailable observation after exchange requires committed forward recovery;
- no committed public record is ever removed or exchanged back;
- owner loss or canonical-lease mismatch blocks mutation;
- independent lock acquisition remains blocked after every result;
- the promoter has exactly one exchange call site and no reverse call;
- no production path, CLI, subprocess, systemd, ALSA, CamillaDSP or device capability exists;
- the v7 operation vocabulary remains exactly forty-two;
- all four production approval operations remain blocked.

## Gate after this proof

Passing this disposable proof does not authorise a production writer. The next reviewed boundary would be integration of the already-proved disposable lease, publication, removal and promotion authorities into one disposable approval lifecycle facade. Fixed production paths, transaction-executor integration and Pi execution remain separately gated.

## Roadmap

### Done

- guarded production-writer design;
- borrowed lock authority and canonical lease binding;
- no-follow disposable approval root;
- atomic temporary publication without replacement;
- descriptor-pinned exact temporary removal;
- this committed-promotion design.

### Current

Implement and failure-inject `DisposableCommittedApprovalPromoterV7` beneath fresh laboratory roots.

### Next

After a successful result document and CI run, design a disposable lifecycle facade that composes the four separate approval operations without granting any component another component's authority.

### Risks and gates

- no production approval writer;
- no committed promotion outside disposable roots;
- no reverse exchange;
- no production path;
- no installer or Pi action;
- all production approval operations remain blocked;
- PR #2 remains Draft, open and unmerged.
