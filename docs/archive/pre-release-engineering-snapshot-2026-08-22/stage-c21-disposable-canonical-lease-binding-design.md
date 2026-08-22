# Stage C21 disposable canonical lock-lease binding design

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Status: design approved for disposable implementation only

## Purpose

The guarded writer design and non-owning borrowed-lock capability now prove that
Stage C21 can repeatedly identify the exact C20 authority without taking over
lock lifetime. The next isolated mutation is to write the canonical lease bytes
into that already-held lock.

This slice proves only lease binding. It does not create an approval root or
approval record, install a package, expose a command, use a production path or
touch the Pi.

## Disposable authority split

Two separate objects are required beneath one fresh, empty, real `0700`
laboratory root:

```text
DisposableC20LockOwnerV7
    owns create → flock → exact unlink → unlock → close

DisposableCanonicalLeaseBinderV7
    borrows the owner's existing descriptor
    owns only canonical truncate/write/fsync and post-exception classification
```

The binder must have no `open`, `flock`, `dup`, `close`, `unlink`, `rename`,
context-manager or destructor boundary. Destroying or discarding the binder must
not alter the owner's lock.

## Laboratory layout

```text
<fresh-root>/run/lock/a-clockwork-plex-audio-route.lock
```

The root and created directories are real, non-symlinked, mode `0700`, and owned
by the current test UID/GID. The lock is a real regular file, mode `0600`, with
an exact descriptor/path device and inode identity.

No absolute production path is accepted or constructed.

## Canonical bytes

The only permitted payload is:

```text
<lease-id>\n
```

encoded as ASCII. The lease ID is generated and retained by the disposable
owner. The binder accepts no replacement payload.

Before binding, lock content must be either:

- empty; or
- already exactly canonical, which is treated as a reconciled success.

Any other content fails closed before mutation.

## Mutation sequence

```text
owner re-verification
→ require empty or exact canonical bytes
→ if already exact: reconciled PASS
→ fault boundary: before truncate
→ ftruncate(fd, 0)
→ fault boundary: after truncate
→ pwrite all canonical bytes from offset zero
→ fault boundary: after write
→ ftruncate(fd, exact payload length)
→ fault boundary: after exact truncate
→ fsync(fd)
→ fault boundary: after fsync
→ owner re-verification
→ require exact canonical bytes
→ PASS
```

The binder never changes mode or ownership and never mutates the pathname.

## Post-exception classification

After any exception, the owner remains responsible for the descriptor and the
binder observes through the owner:

| observed content | disposition |
| --- | --- |
| exact canonical | binding completed; reconciled PASS |
| empty | binding absent; ordinary exact rollback permitted |
| partial or different | manual reconciliation; owner retains lock |
| observation unavailable | manual reconciliation; owner retains lock |

There is no blind retry and no attempt to repair unexplained content.

## Failure injection

Tests must cover every named fault boundary plus:

- short `pwrite` followed by failure, leaving partial content;
- descriptor/path substitution;
- owner closure before binding;
- malformed pre-existing content;
- mode and owner mismatch;
- failed post-write observation;
- idempotent exact-canonical reconciliation.

Every scenario must prove that the binder never releases the lock. A second
independent descriptor must remain unable to acquire it until the owner performs
its exact close operation.

## Static boundary

The binder module must contain no:

```text
argparse
subprocess
systemd or shell command
ALSA, CamillaDSP or /dev/snd access
absolute /run/lock or /var/lib path
approval publication primitive
open, flock, dup, close, unlink, rename, chmod or chown call
CLI or generic dispatch
```

The v7 production adapter remains blocked and its forty-two-operation vocabulary
remains unchanged.

## Exit gate

The slice passes only when real Linux filesystem tests beneath temporary roots,
all fault-injection tests, static boundary tests and the full GitHub Actions suite
pass. The result is then recorded separately before temporary approval
publication is designed.
