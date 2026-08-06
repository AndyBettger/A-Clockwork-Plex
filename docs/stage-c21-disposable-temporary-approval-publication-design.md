# Stage C21 disposable temporary approval publication design

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Status: design reviewed; disposable implementation only may follow

## Purpose

The accepted Stage C21 chain now proves:

```text
immutable borrowed authority
→ non-owning lock capability
→ exact canonical lock-lease binding
```

The next separate boundary is publication of one temporary transaction-bound
activation approval. This document freezes that boundary before code is added.
It does not approve committed promotion, a production writer, an appliance
command, a package installation, a service action, an ALSA change or Pi work.

## Ownership split

Three authorities remain distinct:

```text
DisposableC20LockOwnerV7
    sole owner of lock create, flock, unlink, unlock and close

DisposableApprovalRootV7
    sole owner of one approval-root directory descriptor

DisposableTemporaryApprovalPublisherV7
    may create one private candidate, publish it without replacement,
    classify the public bytes and remove only its tracked private name
```

The publisher never creates, acquires, releases, duplicates or closes the lock.
The approval-root authority never owns the lock. The lock owner never publishes
an approval.

## Disposable filesystem layout

Every proof runs beneath one fresh, empty, real mode-`0700` laboratory root
owned by the current test UID/GID:

```text
<lab>/run/lock/a-clockwork-plex-audio-route.lock
<lab>/var/lib/a-clockwork-plex/split-bus/activation-approved
```

All created directory components are real mode-`0700` directories owned by the
current test UID/GID. The public approval and all private candidate objects are
regular mode-`0600` files with the same owner.

The implementation contains only relative disposable layout constants. It has
no `/run/lock`, `/var/lib`, `/etc`, systemd, process, ALSA, mixer, DAC or service
path and exposes no CLI or root override independent of the disposable owner.

## Authority prerequisites

Temporary publication requires:

1. one live `DisposableC20LockOwnerV7`;
2. exact canonical lease bytes already bound to that owner-held descriptor;
3. one `TemporaryApprovalRecordPlanV7`;
4. its exact derived `CommittedApprovalRecordPlanV7`, used only so the existing
   exact classifier can distinguish an unexpected committed record;
5. matching temporary/committed binding identity;
6. a plan lock lease equal to the disposable owner lease;
7. a live no-follow approval-root authority derived from the same laboratory
   root.

The owner is re-observed before publication, after publication and after every
exception. If the owner is unavailable, substituted, unlocked or no longer
contains the exact canonical lease, no approval mutation may begin or continue.

## Approval-root anchoring

The root authority creates the fixed relative directory chain one component at
a time with `mkdirat`-equivalent `dir_fd` operations. Each component is opened
with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC` and validated by descriptor and
non-following pathname identity.

The final `split-bus` directory descriptor remains open for the publisher
operation. All candidate, public-name, observation and cleanup operations are
relative to that descriptor. No absolute pathname is used after the disposable
laboratory root is accepted.

The root authority may close only its own directory descriptors. Closing it has
no effect on the owner-held production-shaped lock.

## Public observation

The fixed public name is:

```text
activation-approved
```

Observation is bounded by the existing 64 KiB approval-record limit. A present
name must be a regular mode-`0600` file with exact expected owner and descriptor
identity equal to the non-following name identity. Raw bytes are retained and
passed directly to `classify_approval_record_v7()`.

Decoded semantic equality is never sufficient. Different whitespace, ordering,
trailing bytes or a different valid record is `mismatched`.

## Fixed publication sequence

Publication is permitted only when the public name is absent. An already exact
temporary public record is idempotent success without another candidate. Every
other pre-existing public state fails closed.

```text
REVERIFY owner and exact canonical lock lease
→ OPEN/VERIFY approval-root directory descriptor
→ OBSERVE public name
→ require absent OR exact-temporary
→ generate one private name internally
→ create private candidate O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC mode 0600
→ record candidate device and inode immediately
→ write exact planned temporary bytes with pwrite
→ truncate to exact planned length
→ fsync candidate file
→ verify candidate identity, owner, mode, bytes and SHA-256
→ atomically publish without replacement using hard-link creation
→ fsync approval-root directory
→ observe public raw bytes and require exact-temporary
→ verify public identity equals the tracked candidate inode
→ unlink only the tracked private name
→ fsync approval-root directory
→ prove the private name absent and public name exact-temporary
→ REVERIFY owner and exact canonical lock lease
→ TEMPORARY PUBLISHED
```

Hard-link publication is used because creating `activation-approved` with
`linkat` semantics is atomic and fails with `EEXIST`; it cannot replace a
pre-existing public object. The private and public names initially refer to the
same verified inode. Removing the private name leaves the public inode intact.

## Tracked private cleanup

The publisher records the private name and candidate device/inode immediately
after exclusive creation. Cleanup never uses a glob and never removes an
untracked name.

Before unlinking the private candidate, the publisher must prove:

- the name still resolves without following a symlink;
- it is a regular mode-`0600` file with the expected owner;
- its device and inode equal the tracked candidate identity;
- when public publication is visible, the public name is the same inode and its
  raw bytes exactly equal the temporary plan.

A substituted or unverifiable private name is never removed automatically.

## Exception reconciliation

After any exception, the publisher re-observes the lock owner, public approval
and tracked private object.

The existing exact classifier and indeterminate temporary-publication resolver
remain authoritative:

| public classification | permitted outcome |
| --- | --- |
| `absent` | remove only the tracked private inode; exact rollback may proceed |
| `exact-temporary` | remove only a verified private alias if present; continue without retry |
| `exact-committed` | retain owner lock for manual reconciliation |
| `mismatched` | retain owner lock for manual reconciliation |
| `observation-failure` | retain owner lock for manual reconciliation |

There is no blind publication retry. An exact temporary observation is recovery
of the completed publication, not a second publish attempt.

If public state is absent but tracked-private cleanup cannot be proved, the
result is manual reconciliation rather than rollback permission. If public state
is exact temporary but the private alias is substituted or cannot be removed,
publication is not reported as fully complete; the lock remains held.

## Durability

The candidate file is `fsync`ed before public link creation. Every public link
or private unlink namespace mutation is followed by `fsync` of the already-open
approval-root directory descriptor.

Success requires:

- exact temporary public raw bytes;
- exact candidate/public inode identity;
- successful directory durability after publication;
- private-name removal and directory durability after cleanup;
- final owner and canonical lease re-verification.

Visible bytes without the required durability boundary are not silently reported
as ordinary success. Post-exception exact classification governs recovery.

## Required failure injection

The disposable test suite must inject failures:

- before candidate creation;
- immediately after candidate creation;
- during a short/partial `pwrite`;
- after candidate write;
- after exact-length truncate;
- after candidate `fsync`;
- before public link creation;
- immediately after public link creation;
- after publication directory `fsync`;
- before private unlink;
- immediately after private unlink;
- after cleanup directory `fsync`;
- during public observation;
- during private cleanup;
- during final owner re-verification.

Every branch must prove the independent lock remains contended until the owner
explicitly closes it.

## Static safety gate

The implementation and tests must prove:

- no production absolute path or production constructor;
- no `flock`, lock unlink/unlock/close or descriptor duplication in the
  publisher;
- no `rename`, replacement or exchange operation;
- no caller-selected public or private name;
- no committed promotion or exchange-back path;
- no command, subprocess, service, ALSA, mixer, PCM or device access;
- no addition to the forty-two-operation v7 production adapter vocabulary;
- all four production approval operations remain blocked.

## Roadmap

### Done

- production writer design;
- non-owning borrowed-lock observation;
- disposable owner-controlled canonical lease binding.

### Current

Implement and failure-inject temporary approval publication without replacement
beneath disposable laboratory roots.

### Next

After a clean result, design exact temporary approval removal as its own rollback
boundary. Committed promotion remains later and one-way.

### Risks and gates

No production writer, route mutation, service start, package install, Pi command,
PR readiness change or merge is authorised by this design. The known-good direct
shared ALSA route remains the physical recovery truth and
`scripts/install-master-eq.sh` remains blocked.
