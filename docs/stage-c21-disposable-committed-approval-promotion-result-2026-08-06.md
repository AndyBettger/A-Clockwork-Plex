# Stage C21 disposable committed approval promotion result — 2026-08-06

## Outcome

**PASS — one exact canonical temporary approval can now be atomically promoted to its exact derived committed approval beneath a disposable no-follow approval root, with the original temporary inode cleaned only in the forward direction and no reverse-exchange path.**

This proof ran exclusively beneath fresh temporary laboratory roots. It contains no production approval path, installer, service operation, ALSA route, CamillaDSP process, device access or Pi action.

## Design

```text
1d1fef92f21ed2899e9a9e47a0866b12e84d1379
docs: design disposable Stage C21 committed promotion
```

The design preserves three independent authorities:

```text
DisposableC20LockOwnerV7
    owns lock creation, exclusive flock, exact lock unlink, unlock and close

DisposableApprovalRootV7
    owns one no-follow approval-directory descriptor and bounded public observation

DisposableCommittedApprovalPromoterV7
    may create one private committed candidate, exchange it once with the fixed
    public temporary approval, remove only the parked exact temporary inode and
    fsync the already-held approval directory
```

The promoter cannot acquire, duplicate, release or close the owner-held lock. It cannot select or restore an audio route, run a command, manage a service, start a process or access a device.

## Implementation history

Initial one-way promoter:

```text
scripts/stage_c_transaction/disposable_committed_approval_promoter_v7.py

8e6deedcd93606f22e6f720aa5df776601bc1ac1
feat: promote disposable Stage C21 committed approval
```

Two implementation issues were found during the staged review before the failure matrix was accepted.

### Authority tracked before fault injection

```text
b167f1fe60f9e9465f3c6457873c95c711e9a29d
fix: track committed promotion authority before faults
```

The preflight public inode, open temporary descriptor, private candidate name and open candidate descriptor now become part of the reconciliation state before their respective injectable boundaries. A fault immediately after open or create therefore cannot orphan an object while the result incorrectly claims that no object was tracked.

### Partial candidate cleanup bound to owned inode

```text
9dce39e48a90be64f885af966b937282cbb5bb52
fix: clean partial committed candidates by tracked inode
```

Before exchange, a candidate created by this invocation may be empty or partially written. Cleanup therefore requires exact proof of the created device/inode, owner, mode, bounded size, link count and private-name identity, but does not falsely require already-complete committed bytes. A substituted pathname or inode remains forbidden.

After exchange, parked cleanup is stricter: the private name must identify the original pinned public temporary inode and its raw bytes and digest must still be the exact canonical temporary plan.

## Failure-injection suite

```text
tests/test_stage_c_disposable_committed_approval_promotion_v7.py

9147fea251be86ba6267749c148d28cf9e1404b7
test: failure-inject disposable Stage C21 committed promotion
```

## Exact successful sequence

```text
reverify owner-held lock and exact canonical lease
→ classify public approval and require exact-temporary
→ open and pin the public temporary descriptor/device/inode
→ create and pin one private committed candidate
→ write exact committed bytes and truncate to exact length
→ fsync the candidate
→ verify exact committed bytes, encoded SHA-256, owner, mode and private-name identity
→ reverify public temporary and private committed names against both open descriptors
→ renameat2(private, activation-approved, RENAME_EXCHANGE)
→ prove activation-approved is the pinned committed candidate inode
→ prove the private name is the pinned original temporary inode
→ fsync the approval directory
→ classify public approval and require exact-committed
→ unlink only the parked exact temporary private name
→ prove its pinned descriptor now has zero links
→ fsync the approval directory again
→ prove the private name is absent
→ prove stable exact-committed public bytes and candidate inode
→ reverify owner-held lock and canonical lease
→ COMMITTED PROMOTED
```

Both records remain descriptor-pinned across the exchange. This proves that the public committed inode is the exact candidate inode created by this invocation and that the parked object removed during cleanup is the exact original temporary inode.

## One-way boundary

The implementation contains exactly one forward `_rename_exchange()` invocation in the promotion state machine and no reverse-exchange call.

Once exact committed bytes are observed on the tracked candidate inode:

- no code path exchanges the temporary inode back;
- no code path removes or replaces the public committed record;
- directory durability is repaired forward;
- only the parked exact temporary inode may be removed;
- owner authority remains held until a separate executor/owner boundary releases it.

A fresh invocation that merely finds exact committed bytes at entry is refused. It cannot claim success because it did not create, track or own the earlier one-way transition.

## Exception reconciliation

### Before exchange

If the original public temporary inode remains exact:

- remove only the candidate inode created and still held by this invocation;
- permit partial-candidate cleanup by exact owned inode identity;
- fsync the approval directory;
- prove the candidate name absent;
- prove the same original temporary inode remains public;
- reverify owner authority;
- return `TEMPORARY_RETAINED_RECOVERY`.

This is a failed result. It permits only a separately reviewed retry invocation and performs no same-call retry.

If exact temporary bytes appear on a different inode, cleanup and retry permission are refused.

### After exchange

If exact committed bytes are public on the tracked candidate inode:

- repeat the approval-directory `fsync`;
- require the private name to identify the pinned exact temporary inode, or prove that inode already has zero links;
- remove only that parked temporary name when necessary;
- repeat directory `fsync` after cleanup;
- prove stable exact committed public bytes and inode;
- reverify owner authority;
- return `COMMITTED_PROMOTED` with `reconciled_after_exception=True`.

The test exchange helper performs the real syscall and then raises. The classifier still discovers the tracked committed public inode, completes forward cleanup and returns success with exactly one exchange invocation.

If exact committed bytes are attached to a different inode, the result is `COMMITTED_FORWARD_RECOVERY_REQUIRED`. No automatic cleanup, retry or rollback is granted.

### Persistent observation loss refinement

The original design proposed classifying persistent post-exchange observation loss directly as committed forward recovery. The implementation deliberately uses the more conservative result `MANUAL_RECONCILIATION` when public bytes cannot be observed at all.

This avoids claiming exact committed state without evidence. The safety response is still one-way and fail-closed:

- retain owner authority and the exclusive lock;
- do not retry exchange;
- do not remove or replace the public approval;
- do not exchange a temporary record back;
- require explicit reconciliation after public observation is restored.

Transient observation loss was fault-injected and successfully reconciles forward once exact public evidence becomes available again.

## Typed outcomes

```text
COMMITTED_PROMOTED
    PASS; exact committed candidate inode is public, parked temporary inode is
    durably removed and owner lock remains held

TEMPORARY_RETAINED_RECOVERY
    FAIL; the same original temporary inode remains public, the owned candidate
    is absent and only a separately reviewed retry invocation is permitted

COMMITTED_FORWARD_RECOVERY_REQUIRED
    FAIL; exact committed bytes are public but not on the tracked candidate inode;
    rollback is forbidden and owner authority must remain held

MANUAL_RECONCILIATION
    FAIL; public state or identity cannot safely authorise automatic action
```

Every result records classifier state, both encoded SHA-256 values, exception-reconciliation status, retry permission, forward-recovery requirement, manual-reconciliation requirement, owner-lock state, private-name absence and proved public temporary/committed identity.

## Tests proved

The real Linux filesystem suite covers:

- normal exact committed promotion;
- committed public inode equals the original candidate inode;
- parked private inode equals the original public temporary inode;
- parked temporary cleanup and private-name absence;
- every named pre-exchange and post-exchange fault boundary;
- partial candidate write cleanup by tracked inode;
- all pre-exchange failures retain the same original temporary inode;
- all post-exchange faults reconcile forward with exactly one exchange;
- exchange syscall success followed immediately by an exception;
- failed first approval-directory `fsync` repaired before success;
- transient post-exchange observation failure;
- exact committed state at entry refused rather than accepted idempotently;
- absent, committed, mismatched, noncanonical, wrong-mode and symlink preconditions untouched;
- public temporary substitution before exchange detected and not unlinked;
- private candidate substitution before exchange detected and not unlinked;
- exact committed bytes recreated on another inode receive no tracked authority;
- lost owner authority blocks mutation;
- independent lock acquisition remains blocked after every live-owner result;
- result records are frozen and reject inconsistent authority flags;
- exactly one forward exchange call site and no reverse exchange;
- no production path, CLI, subprocess, service, audio or device boundary;
- the v7 operation vocabulary remains exactly forty-two;
- all four production approval operations remain blocked.

## Validation

GitHub Actions run:

```text
31061607692
```

validated branch head:

```text
9147fea251be86ba6267749c148d28cf9e1404b7
```

Full result:

```text
Ran 1114 tests in 6.972s

OK
```

Compilation, JavaScript/page wiring, shell validation and all inherited application, transaction, runtime, sandbox and safety suites also passed.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock was opened or changed;
- no production approval root or approval record was created, exchanged or removed;
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
- one-way descriptor-pinned committed promotion;
- forward-only exception reconciliation;
- full real-filesystem failure matrix.

### Current

Design a disposable approval lifecycle facade that composes the separate binder, publisher, remover and promoter authorities without granting any component another component's mutation or lock-lifetime authority.

### Next

The facade proof must:

- introduce no new filesystem mutation primitive;
- preserve the existing owner as the sole lock-lifetime authority;
- select only fixed typed lifecycle operations;
- carry one immutable temporary/committed plan pair through the full lifecycle;
- prove successful publish → remove rollback and publish → promote paths;
- prove every failure retains the exact typed recovery state;
- remain entirely beneath fresh disposable roots;
- leave fixed production paths and executor integration blocked.

### Risks and gates

- no production approval writer;
- no production transaction-executor integration;
- no production fixed path;
- no Pi or physical action;
- no reverse exchange;
- all production approval operations remain blocked;
- PR #2 remains Draft, open and unmerged.
