# Stage C21 disposable approval lifecycle facade result — 2026-08-06

## Outcome

**PASS — the separately proved disposable Stage C21 approval authorities now compose into one strict lifecycle coordinator without adding filesystem mutation, lock-lifetime authority, hidden retry or production access.**

The two complete laboratory lifecycles are now proved:

```text
owner-held empty lock
→ canonical lease bound
→ exact temporary approval published
→ exact temporary approval removed
```

and:

```text
owner-held empty lock
→ canonical lease bound
→ exact temporary approval published
→ exact committed approval promoted one-way
```

This proof ran only beneath fresh temporary roots. It did not access a production approval path, install software, alter ALSA, start CamillaDSP, manage a service, open an audio device or run on the Pi.

## Design

```text
a597d04ca148c8735cc5762c618d2cfea083a2b3
docs: design disposable Stage C21 approval lifecycle facade
```

The facade is a typed order coordinator, not another approval writer. It composes only these already-reviewed authorities:

```text
DisposableC20LockOwnerV7
DisposableCanonicalLeaseBinderV7
DisposableApprovalRootV7
DisposableTemporaryApprovalPublisherV7
DisposableTemporaryApprovalRemoverV7
DisposableCommittedApprovalPromoterV7
```

It cannot create, open, write, truncate, link, unlink, rename, exchange or fsync a file. It cannot construct, close, unlock or release the owner-held lock.

## Implementation

```text
scripts/stage_c_transaction/disposable_approval_lifecycle_facade_v7.py

e34ebfda9d968e85d43f45f212f8243e312b4daf
feat: compose disposable Stage C21 approval lifecycle
```

The public API is deliberately fixed:

```text
bind_canonical_lease()
publish_temporary()
remove_temporary()
promote_committed()
```

There is no caller-selected path, filename, raw payload, operation string, generic dispatch method or retry loop.

Each public method performs exactly three actions:

```text
verify its one permitted lifecycle phase
→ construct one already-proved typed authority
→ invoke that authority exactly once
```

The exact underlying frozen result object is then stored unchanged in a frozen `DisposableApprovalLifecycleEventV7`.

## Lifecycle phases

```text
OWNER_HELD_EMPTY
LEASE_BOUND
TEMPORARY_PUBLISHED
TEMPORARY_REMOVED
COMMITTED
RECOVERY_REQUIRED
```

Successful transitions are limited to:

```text
OWNER_HELD_EMPTY
    → bind canonical lease
    → LEASE_BOUND

LEASE_BOUND
    → publish temporary approval
    → TEMPORARY_PUBLISHED

TEMPORARY_PUBLISHED
    → remove exact temporary approval
    → TEMPORARY_REMOVED

TEMPORARY_PUBLISHED
    → promote exact committed approval
    → COMMITTED
```

`TEMPORARY_REMOVED` and `COMMITTED` are successful terminal states.

## Recovery rule

Every failed delegated result moves that facade instance to terminal:

```text
RECOVERY_REQUIRED
```

This applies even where the lower-level result reports that a separately reviewed retry or rollback may be possible.

The facade preserves that permission as evidence but never acts on it. It does not:

- invoke a second component;
- retry the same component;
- remove an approval automatically;
- promote an approval automatically;
- reinterpret failure as success;
- construct a new owner or approval root;
- release the retained lock.

Once `RECOVERY_REQUIRED` is entered, all four lifecycle methods reject further calls before constructing another component.

## Invalid ordering

`DisposableApprovalLifecycleOrderError` is raised before component construction for, among other cases:

- publication before canonical binding;
- removal or promotion before publication;
- binding twice;
- publication twice;
- removal after commitment;
- promotion after removal;
- any operation after a failed delegated result;
- any operation after successful terminal completion.

The tests prove that invalid calls do not instantiate any underlying authority.

## Preserved typed results

The facade preserves all reviewed lower-level dispositions as their original objects.

### Canonical binding

```text
CANONICAL_BOUND
EMPTY_ROLLBACK_PERMITTED
MANUAL_RECONCILIATION
```

### Temporary publication

```text
TEMPORARY_PUBLISHED
APPROVAL_ABSENT_ROLLBACK
MANUAL_RECONCILIATION
```

### Temporary removal

```text
TEMPORARY_REMOVED
TEMPORARY_RETAINED_RECOVERY
MANUAL_RECONCILIATION
```

### Committed promotion

```text
COMMITTED_PROMOTED
TEMPORARY_RETAINED_RECOVERY
COMMITTED_FORWARD_RECOVERY_REQUIRED
MANUAL_RECONCILIATION
```

The facade event derives and validates:

- successful terminal state;
- separately reviewed follow-up permission;
- committed forward-recovery requirement;
- manual-reconciliation requirement;
- retained owner-lock state.

None of those flags can be invented independently of the underlying result.

## Tests

Initial suite:

```text
tests/test_stage_c_disposable_approval_lifecycle_facade_v7.py

ef422c5bc5d14858b726d0d6488bc5ef51e6ae17
test: compose disposable Stage C21 approval lifecycle
```

A test-harness loop that would have deliberately failed its second binder case was found during review before acceptance. The corrected recovery matrix was committed as:

```text
ad7cc34551397766a2616d4aca7fa4a8115f4f19
fix: correct disposable lifecycle recovery matrix
```

The final suite proves:

- successful bind → publish → remove;
- successful bind → publish → promote;
- exact approval absence after removal;
- exact committed bytes after promotion;
- owner lock remains held after every event;
- independent lock acquisition remains blocked after both successful terminal paths;
- exact temporary and committed plan object identities are preserved;
- invalid ordering constructs no component;
- each public method delegates exactly once;
- no method contains an operation retry loop;
- every failed binder disposition remains unchanged;
- every failed publisher disposition remains unchanged;
- every failed remover disposition remains unchanged;
- every failed promoter disposition remains unchanged;
- every failure enters terminal `RECOVERY_REQUIRED`;
- reviewed follow-up permission is visible but never exercised;
- manual and committed-forward recovery requirements remain visible;
- mismatched owners, roots, leases and unrelated plans are rejected;
- a closed approval root is rejected;
- lifecycle events are frozen and reject invalid transitions;
- the facade imports no filesystem, process, command, service, audio or device module;
- the facade contains no filesystem mutation call;
- no generic dispatch or factory boundary exists;
- the v7 operation vocabulary remains exactly forty-two;
- all four production approval operations remain blocked.

## Validation

GitHub Actions run:

```text
31062713603
```

Job:

```text
92493830915
```

Validated branch head:

```text
ad7cc34551397766a2616d4aca7fa4a8115f4f19
```

Full result:

```text
Ran 1124 tests in 7.196s

OK
```

Compilation, JavaScript/page wiring, shell syntax and all inherited application, Stage C transaction, runtime, filesystem, sandbox and safety suites passed.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock or approval record was created, changed or removed;
- no production route was selected;
- no package was installed;
- no service, process, mixer, endpoint or device was touched;
- no CamillaDSP process was started;
- all four v7 production approval operations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains required to stay Draft, open and unmerged.

## Roadmap

### Done

- borrowed C20 authority and canonical lease binding;
- no-follow disposable approval root;
- exact temporary publication without replacement;
- descriptor-pinned exact temporary removal;
- descriptor-pinned one-way committed promotion;
- complete disposable lifecycle composition;
- exact recovery-result preservation;
- successful rollback and committed lifecycle branches;
- 1,124-test validation.

### Current

Design guarded **production prepare-only integration**.

This next boundary is an inspector and evidence-plan boundary, not a production writer. It must keep all four approval mutations blocked while defining exactly what a first Pi-side prepare-only run may observe and report.

### Next

The prepare-only design must specify:

- the existing production owner and transaction lineage that may be observed;
- fixed no-follow production approval-root inspection;
- read-only classification of absent, temporary, committed, mismatched and unavailable states;
- exact package, route, lock, transaction and hardware evidence required;
- a review bundle containing no activation token or mutation command;
- one explicit future approval gate before any Pi command that can alter state exists;
- no use of the blocked master-EQ installer.

Only after the prepare-only implementation and local safety tests pass should the project ask for approval to run that inspector on the Pi.

### Risks and gates

- no production approval writer exists;
- no production lifecycle facade exists;
- no production transaction-executor integration exists;
- no activation command exists at this boundary;
- no Pi action has been taken;
- no reverse exchange exists in committed promotion;
- all production approval operations remain blocked;
- PR #2 must remain Draft, open and unmerged.
