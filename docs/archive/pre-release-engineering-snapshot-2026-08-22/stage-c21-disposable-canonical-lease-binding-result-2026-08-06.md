# Stage C21 disposable canonical lock-lease binding result — 2026-08-06

## Outcome

**PASS — a separate disposable C20-shaped owner can retain exclusive lock lifetime while a non-owning Stage C21 binder writes and reconciles only the exact canonical lease bytes.**

This proof ran exclusively beneath fresh temporary laboratory roots. It contains no production path, approval publication, command, package installation, service action, ALSA access or Pi operation.

## Design

```text
669fd299e9cfc80f57a45641fb082aa5014d8969
docs: design disposable Stage C21 lease binding
```

The design separates:

```text
DisposableC20LockOwnerV7
    owns create, flock, exact unlink, unlock and close

DisposableCanonicalLeaseBinderV7
    borrows the already-held descriptor
    owns only canonical truncate, pwrite, fsync and observation classification
```

## Implementation

Disposable owner:

```text
scripts/stage_c_transaction/disposable_c20_lock_owner_v7.py

a89f0ebfc6ba82e5e22c9660c5f206316e3816a5
feat: add disposable C20-shaped lock owner
```

Disposable binder:

```text
scripts/stage_c_transaction/disposable_canonical_lease_binder_v7.py

26b0aa3c024026b4c992e8e9b76469c519603401
feat: bind disposable Stage C21 canonical lease
```

A pre-test review tightened the result contract so a stale binder retained after
its owner closes reports unavailable authority rather than claiming that the
lock remains held:

```text
b28f41a97e7c2bc2334f2ab6d3251425a3ff42e5
fix: report unavailable disposable owner authority
```

## Laboratory contract

Each test creates one fresh, empty, real mode-`0700` root owned by the current test UID/GID and reproduces only this relative layout:

```text
run/lock/a-clockwork-plex-audio-route.lock
```

The owner creates one real mode-`0600` lock, proves descriptor/path device and inode identity, obtains an exclusive non-blocking `flock`, proves contention through a second independent descriptor and keeps the lock until its exact close operation.

The binder accepts no caller payload. Its only permitted bytes are:

```text
<owner-generated-lease-id>\n
```

encoded as ASCII.

## Binding sequence

```text
owner observation and contention proof
→ require empty or exact canonical content
→ ftruncate(fd, 0)
→ pwrite all canonical bytes from offset zero
→ ftruncate(fd, exact payload length)
→ fsync(fd)
→ owner observation and contention proof
→ require exact canonical content
```

An already exact lease is accepted idempotently without another truncate, write or fsync.

## Exception reconciliation

Every mutation boundary is failure-injected and then classified from a fresh owner observation:

| observed state | result |
| --- | --- |
| exact canonical bytes | reconciled PASS without retry |
| empty bytes | ordinary exact rollback permitted |
| partial or different bytes | manual reconciliation; owner retains lock |
| observation unavailable | manual reconciliation; owner retains lock |

There is no blind retry and no repair of unexplained content.

## Tests

```text
tests/test_stage_c_disposable_canonical_lease_binding_v7.py

b25233fea2c1df8d72a22a88200cd0ad91a1dbbf
test: failure-inject disposable Stage C21 lease binding
```

The real Linux filesystem tests prove:

- successful exact binding;
- independent contention before and after binding;
- owner-only release and exact lock-path removal;
- idempotent exact-canonical reconciliation with zero further writes;
- failure before truncate and after truncate leaves an empty rollback-permitted state;
- failure after write, exact truncate or fsync reconciles exact canonical completion;
- short `pwrite` followed by failure leaves partial bytes and requires manual reconciliation;
- malformed pre-existing content is never replaced;
- a binder retained after owner closure cannot mutate and reports unavailable authority;
- substituted pathname, wrong mode and wrong owner metadata fail before mutation;
- unavailable post-write and post-exception observation never assumes success;
- every binder outcome that starts beneath a live owner leaves independent lock acquisition blocked;
- binder static analysis forbids lock acquisition/release, descriptor duplication/close, pathname mutation, production paths, commands, services, audio and approval publication;
- the v7 adapter vocabulary remains exactly forty-two operations.

## Validation

GitHub Actions run:

```text
31058918810
```

validated head:

```text
b25233fea2c1df8d72a22a88200cd0ad91a1dbbf
```

Full result:

```text
Ran 1075 tests in 6.594s

OK
```

Compilation, JavaScript/page/shell validation and all inherited safety and sandbox suites also passed.

## Safety state

Unchanged:

- the Pi remains at the accepted C20 physical checkpoint;
- the known-good direct shared ALSA route remains authoritative;
- no production lock was opened or changed;
- no approval root or approval record exists in this slice;
- no package was installed;
- no service, route, mixer, process, endpoint or device was touched;
- all four v7 production approval operations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Roadmap

### Done

- guarded writer design;
- non-owning production-authority observation capability;
- disposable owner/binder separation;
- exact canonical lease binding and post-exception reconciliation;
- 1,075-test CI pass.

### Current

Design the next separate boundary: disposable temporary approval publication without replacement beneath the same owner-held authority.

### Next

The publication slice must add a no-follow `0700` approval root, exact canonical temporary bytes, exclusive private candidate creation, candidate fsync, atomic no-replace publication, directory fsync, exact raw-byte classification and exact tracked-private cleanup.

### Risks and gates

The next slice remains disposable-only. It may not promote a committed record, expose production paths or commands, install anything, touch the Pi or alter the production adapter operation boundary. Committed promotion remains a later one-way state transition with its own review.
