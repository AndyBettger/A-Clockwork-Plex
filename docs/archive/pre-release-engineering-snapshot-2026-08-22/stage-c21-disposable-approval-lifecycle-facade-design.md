# Stage C21 disposable approval lifecycle facade design

## Status

**Design only — this facade introduces no production path, no new filesystem mutation and no Pi action.**

It composes only the already-proved disposable authorities beneath a fresh laboratory root:

```text
DisposableC20LockOwnerV7
DisposableCanonicalLeaseBinderV7
DisposableApprovalRootV7
DisposableTemporaryApprovalPublisherV7
DisposableTemporaryApprovalRemoverV7
DisposableCommittedApprovalPromoterV7
```

The facade is deliberately a typed coordinator rather than another writer.

## Purpose

The separate Stage C21 proofs now establish each approval operation independently:

```text
empty owner-held lock
→ exact canonical lease
→ exact public temporary approval
→ either exact removal for rollback
→ or one-way committed promotion
```

The lifecycle facade must prove that these authorities can be used in the required order without accidentally combining their capabilities, hiding recovery results, retrying a failed mutation or releasing the owner-held lock.

## Non-goals

The facade must not:

- create, open, write, truncate, link, unlink, rename, exchange or fsync a file;
- construct or close the lock owner;
- construct or close the approval root;
- expose a path, filename, raw bytes or generic operation argument;
- use a dictionary/string dispatch table;
- retry an operation automatically;
- translate a failed underlying result into success;
- infer committed or rollback completion from local memory alone;
- install software, invoke a CLI, manage a service, change ALSA, start CamillaDSP or touch a device;
- access fixed production paths.

## Inputs

Construction receives exactly:

- one live `DisposableC20LockOwnerV7`;
- the matching already-open `DisposableApprovalRootV7`;
- one immutable `TemporaryApprovalRecordPlanV7`;
- the exact `CommittedApprovalRecordPlanV7` derived from that temporary plan;
- optional component factories used only by tests to inject already-typed faulting authorities.

The constructor verifies:

- owner and approval root are the matching objects beneath the same disposable root;
- the owner lock remains held;
- the approval root remains open and verifies successfully;
- temporary and committed plans share the same binding;
- the committed plan derives from the supplied temporary record;
- both plans carry the owner lease ID.

The facade stores the exact plan objects, not merely equivalent decoded records.

## Fixed lifecycle operations

The public API contains only four explicit methods:

```text
bind_canonical_lease()
publish_temporary()
remove_temporary()
promote_committed()
```

There is no `dispatch()`, operation string or caller-selected component.

Each method creates exactly one already-proved disposable authority and invokes exactly one of its fixed methods:

```text
bind_canonical_lease
    → DisposableCanonicalLeaseBinderV7.bind

publish_temporary
    → DisposableTemporaryApprovalPublisherV7.publish

remove_temporary
    → DisposableTemporaryApprovalRemoverV7.remove

promote_committed
    → DisposableCommittedApprovalPromoterV7.promote
```

The facade itself performs no recovery. It returns the complete frozen underlying result unchanged inside a frozen lifecycle event.

## Lifecycle phase

The facade maintains an in-memory phase only to restrict which authority may be invoked next:

```text
OWNER_HELD_EMPTY
LEASE_BOUND
TEMPORARY_PUBLISHED
TEMPORARY_REMOVED
COMMITTED
RECOVERY_REQUIRED
```

The phase is not a filesystem fact and never overrides an underlying result.

Allowed transitions:

```text
OWNER_HELD_EMPTY
    bind PASS/CANONICAL_BOUND
        → LEASE_BOUND

LEASE_BOUND
    publish PASS/TEMPORARY_PUBLISHED
        → TEMPORARY_PUBLISHED

TEMPORARY_PUBLISHED
    remove PASS/TEMPORARY_REMOVED
        → TEMPORARY_REMOVED

TEMPORARY_PUBLISHED
    promote PASS/COMMITTED_PROMOTED
        → COMMITTED
```

Every failed underlying result moves the facade to `RECOVERY_REQUIRED`, even when the underlying result permits an ordinary rollback or separately reviewed retry. The facade does not exercise that permission automatically.

`TEMPORARY_REMOVED`, `COMMITTED` and `RECOVERY_REQUIRED` are terminal for that facade instance.

## Frozen lifecycle event

Every method returns a frozen `DisposableApprovalLifecycleEventV7` containing:

- operation;
- phase before invocation;
- phase after invocation;
- exact underlying typed result object;
- whether the facade reached a successful terminal state;
- whether manual reconciliation is required;
- whether a separately reviewed follow-up is permitted by the underlying result;
- whether the owner lock remains held.

The event validates that:

- operation and underlying result type match exactly;
- only the four allowed successful transitions exist;
- a failed result always ends in `RECOVERY_REQUIRED`;
- successful terminal state is true only for `TEMPORARY_REMOVED` or `COMMITTED`;
- manual/reviewed-follow-up flags are derived from the underlying typed result and cannot be invented;
- owner-lock state exactly matches the underlying result.

## Invalid order

Calling an operation outside its allowed phase raises `DisposableApprovalLifecycleOrderError` before constructing or invoking any component.

Examples:

- publication before binding;
- removal before publication;
- promotion before publication;
- binding twice;
- promotion after removal;
- removal after commitment;
- any operation after `RECOVERY_REQUIRED`.

Order errors are programmer errors in the disposable coordinator, not filesystem recovery results.

## Recovery preservation

The facade must preserve, without reinterpretation, at least these underlying states:

### Binder

```text
CANONICAL_BOUND
EMPTY_ROLLBACK_PERMITTED
MANUAL_RECONCILIATION
```

### Publisher

```text
TEMPORARY_PUBLISHED
APPROVAL_ABSENT_ROLLBACK
MANUAL_RECONCILIATION
```

### Remover

```text
TEMPORARY_REMOVED
TEMPORARY_RETAINED_RECOVERY
MANUAL_RECONCILIATION
```

### Promoter

```text
COMMITTED_PROMOTED
TEMPORARY_RETAINED_RECOVERY
COMMITTED_FORWARD_RECOVERY_REQUIRED
MANUAL_RECONCILIATION
```

A reviewed retry or rollback permission remains documentary only. A new facade instance or a later production executor design must explicitly decide whether that follow-up is authorised.

## Required tests

The disposable suite must prove:

- successful bind → publish → remove lifecycle;
- successful bind → publish → promote lifecycle;
- public approval absent after remove;
- exact committed public bytes after promote;
- owner lock remains held after every event;
- independent lock acquisition remains blocked after both successful terminal paths;
- every invalid operation order is rejected before any component invocation;
- no operation is invoked twice by one method;
- every underlying failed disposition is preserved as the same object;
- every failure moves the facade to `RECOVERY_REQUIRED`;
- no method is callable after `RECOVERY_REQUIRED`;
- reviewed retry/rollback permission is reported but never acted upon;
- manual and forward-recovery requirements remain visible;
- constructor rejects different roots, closed approval roots, wrong leases and unrelated committed plans;
- the exact temporary and committed plan object identities remain stable;
- lifecycle events are frozen and reject inconsistent transitions;
- component factories are fixed typed callables and cannot select paths or operations;
- facade source contains no `os`, `pathlib`, `ctypes`, `fcntl`, `subprocess`, CLI, service, audio or device imports;
- facade source contains no filesystem mutation calls;
- facade source contains no generic dispatch function;
- the v7 operation vocabulary remains exactly forty-two;
- all four production approval operations remain blocked.

## Gate after this proof

Passing the facade proof closes the disposable approval lifecycle. The next boundary is a **production prepare-only integration design**.

That design may inspect and report the fixed production prerequisites, but it must initially keep all four production approval mutations blocked. It must produce a reviewable plan for the first Pi-side prepare-only run before any activation command exists.

## Roadmap

### Done

- canonical lease binding;
- no-follow approval root;
- no-replace temporary publication;
- descriptor-pinned temporary removal;
- one-way committed promotion;
- this lifecycle-facade design.

### Current

Implement and fault-inject the thin disposable lifecycle facade.

### Next

Design guarded production prepare-only integration and the exact evidence bundle required before asking for approval to run it on the Pi.

### Risks and gates

- no production writer;
- no production lifecycle constructor;
- no fixed production path;
- no transaction-executor integration;
- no installer or Pi action;
- all production approval operations remain blocked;
- PR #2 remains Draft, open and unmerged.
