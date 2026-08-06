# Stage C21 borrowed production-lock capability result — 2026-08-06

## Outcome

**PASS — Stage C21 can now borrow the already-held C20 production-lock descriptor as a non-owning, repeatedly re-verifiable capability without acquiring, releasing, duplicating, closing or mutating that descriptor.**

This milestone remains read-only and repository/CI-only. It does not bind the lease, write an approval, create a production object, expose a command or touch the Pi.

## Design checkpoint

The preceding design review was committed as:

```text
d704dbfa2e28fc4ce2475bcc0015684b35abc32a
docs: design guarded Stage C21 approval writer
```

The design rejected direct production wiring of the existing runtime `ApprovalStore`. That store accepts a Boolean `lock_held` assertion, compares decoded records at several mutation boundaries and may exchange a committed replacement back after an exception. The guarded transaction writer instead requires exact borrowed authority, exact canonical bytes and forward recovery only once exact committed state is visible.

GitHub Actions run `31058192640` passed for the design commit.

## Added implementation

```text
scripts/stage_c_transaction/borrowed_lock_capability_v7.py
```

Commit:

```text
128b62b4590d9b271c3399cb4c0b139d434528a1
feat: add non-owning Stage C21 lock capability
```

The factory accepts only:

- the existing `RouteSelectionRollbackRehearsalAdapterV2` C20 owner lineage;
- one immutable `ApprovalAuthorityBindingV7` derived from that owner.

It captures the owner's current descriptor number as a private borrowed reference. Construction is factory-token protected; there is no public descriptor property, context-manager ownership, destructor, close method or release method.

## Re-verification gate

Every `reverify()` call proves:

1. the C20 owner still exposes the same descriptor number;
2. `inspect_borrowed_authority_v7()` still passes;
3. transaction, snapshot, package, lease, lock, transaction directory and selected-route identities still equal the immutable binding;
4. the descriptor remains a regular `root:root` `0600` file;
5. descriptor device and inode still equal the binding;
6. content is bounded to 512 bytes;
7. content is either empty or exactly the canonical ASCII lease bytes:

```text
<lock-lease-id>\n
```

A caller may require the canonical lease to be already bound. Empty content then fails closed.

No semantically similar, padded, partial, differently terminated or otherwise malformed lease content is accepted.

## Explicit capability boundary

The implementation uses only these host-facing operations:

```text
os.fstat
os.pread
```

It contains no operation capable of:

```text
open or replace the lock
flock, unlock or acquire it
dup or transfer the descriptor
close it
truncate or write it
unlink or rename it
change owner or mode
create an approval
run a command
access systemd, ALSA, CamillaDSP or /dev/snd
```

The v7 adapter vocabulary remains exactly forty-two operations. No new generic adapter operation or production dispatch route was added.

## Tests

```text
tests/test_stage_c_borrowed_lock_capability_v7.py
```

Commit:

```text
cd86223fede5eab2c0fd94736ed381ad3ea123be
test: prove non-owning Stage C21 lock capability
```

Coverage proves:

- successful borrowing with the C20 lock file still empty;
- successful required-bound verification with exact canonical lease bytes;
- refusal when a bound lease is required but content remains empty;
- refusal of malformed or concurrently changing content;
- refusal after owner descriptor loss or replacement;
- refusal when any borrowed-authority or descriptor identity changes;
- typed owner-inspection and operating-system failures;
- exact factory/type restrictions;
- immutable proof/result objects;
- absence of close, release, duplication, mutation, command, audio and generic dispatch boundaries through static AST/source checks.

## Validation

GitHub Actions run:

```text
31058415270
```

validated branch head:

```text
cd86223fede5eab2c0fd94736ed381ad3ea123be
```

Full result:

```text
Ran 1062 tests in 6.335s

OK
```

The workflow also passed application compilation, JavaScript/page/shell checks and the existing sandbox/rehearsal safety suites.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no Stage C package was installed;
- no production lock, transaction or approval was created by this milestone;
- no existing lock content was changed;
- no service, route, mixer, process, endpoint or device was touched;
- all four v7 production approval operations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Roadmap

### Done

- guarded production approval-writer design review;
- non-owning borrowed-lock capability;
- repeated exact authority and canonical lease observation;
- 1,062-test CI pass.

### Current

Design and implement the first disposable mutation: bind the canonical lease bytes into a separate disposable C20-shaped owner's already-held lock descriptor.

### Next

Failure-inject every lease-write boundary and prove:

- the writer never acquires or releases the lock;
- exact canonical completion can be reconciled after an exception;
- empty/absent state may return to ordinary exact rollback;
- partial, different or unobservable content retains owner authority for manual reconciliation;
- no approval publication occurs in the lease-binding slice.

### Risks and gates

No production writer, fixed production path, CLI, installer or Pi command may be added in the next slice. Approval publication remains a later, separately reviewed boundary.
