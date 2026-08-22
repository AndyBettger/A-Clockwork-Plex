# Stage C21 guarded production approval writer design

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Status: design reviewed; disposable implementation only may follow; production writer remains blocked

## Purpose

Stage C20 physically proved the reversible production mutation prefix through
one temporary split-bus route selection and exact rollback. The later Stage C21
work has remained automated and disposable. It now provides:

- a read-only view of the exact C20 authority owner;
- an immutable approval-authority binding;
- canonical temporary and committed approval-record plans;
- exact raw-byte observation classification;
- explicit recovery decisions for indeterminate publication and promotion;
- a disposable approval lifecycle and terminal transaction simulation.

The next missing boundary is the first writer that can publish the planned
approval beneath the fixed production state root while the existing C20 owner
still owns the production lock and authoritative transaction.

This document freezes that writer boundary before implementation. It adds no
writer, command, entrypoint, installer, package file, service action, ALSA
access, lock acquisition or Pi rehearsal.

## Review decision

The existing `stage_c_runtime_authority.approval_store.ApprovalStore` remains a
useful runtime/disposable primitive, but it must not simply be connected to the
production transaction as the Stage C21 writer.

The current store deliberately accepts only a Boolean `lock_held` assertion. It
does not prove the exact borrowed C20 lock, lease, transaction, selected route
or authority-binding identity before each mutation. Several of its comparisons
also use decoded record equality rather than the exact canonical bytes required
by the Stage C21 classifier. Its exchange failure handler may try to restore the
temporary record after a committed replacement became visible; the accepted
Stage C21 rule is instead forward recovery only after exact committed state is
observed.

The production transaction therefore requires a separate, narrower writer. It
may reuse reviewed encoding and carefully reviewed low-level ideas, but it may
not inherit the store's Boolean authority assertion or its rollback semantics.

## Explicit non-goals

This design does not approve:

- acquiring, releasing, unlinking or closing the production lock;
- creating a second transaction or snapshot;
- selecting or restoring an ALSA route;
- installing the Stage C21 package;
- starting CamillaDSP or any managed service;
- exposing a CLI, generic path argument or service-helper operation;
- changing the active Pi;
- persistent activation, reboot testing, merge or deployment.

## Fixed production objects

The writer has no caller-supplied production paths.

```text
production lock
/run/lock/a-clockwork-plex-audio-route.lock

approval root
/var/lib/a-clockwork-plex/split-bus

published approval
/var/lib/a-clockwork-plex/split-bus/activation-approved
```

The published approval and all private transaction-owned approval objects use
mode `0600`. The approval root uses mode `0700`. Both are `root:root` in
production. Every ancestor must be a real directory, root-owned and not writable
by group or other. No path component may be a symlink.

A disposable implementation maps the same relative layout beneath one
caller-created, empty, real `0700` laboratory root owned by the test user. The
production implementation accepts no root override.

## Accepted authority chain

The writer may be constructed only from one already-live C20 owner lineage and
all of the following mutually matching objects:

1. the existing `RouteSelectionRollbackRehearsalAdapterV2` owner;
2. one `ApprovalAuthorityBindingV7` derived from that owner;
3. the exact temporary `TemporaryApprovalRecordPlanV7`;
4. the exact committed `CommittedApprovalRecordPlanV7` when promotion is due;
5. a non-owning borrowed-lock capability produced by the same owner.

The temporary and committed plans must carry the binding SHA-256. The
transaction, snapshot, package, lock lease, lock device/inode, authoritative
transaction device/inode, selected-route device/inode/SHA-256 and complete
hardware contract must all match the binding exactly.

No individual string, Boolean `lock_held` flag or reconstructed pathname is
sufficient authority.

## Non-owning borrowed-lock capability

The C20 owner remains the sole owner of lock lifetime. The writer receives:

- the already-open descriptor number as a borrowed reference;
- the expected lock device and inode;
- the expected lease ID;
- an owner-controlled re-verification operation that returns a fresh
  `BorrowedAuthorityViewV7` without transferring ownership.

The writer may perform only these descriptor operations:

```text
fstat
pread
one guarded canonical lease binding through ftruncate/pwrite/fsync
```

The lease binding is the first Stage C21 mutation because C14 through C20 hold
the correct lock inode but do not publish the lease in the lock-file content.
The canonical content is exactly:

```text
<lock-lease-id>\n
```

encoded as ASCII, with no leading/trailing spaces and no additional fields.
Before binding, the descriptor content must be empty or already equal to those
exact bytes. After binding, it must equal those bytes exactly.

The writer must never call any of the following on the borrowed descriptor or
pathname:

```text
open a replacement lock
flock or otherwise acquire/unlock it
dup or transfer it
close it
unlink or rename it
change owner or mode
write any non-canonical content
release transaction ownership
```

The C20 owner alone decides whether the descriptor is eventually unlinked,
unlocked and closed.

## Mandatory re-verification gate

The owner-controlled authority re-verification runs:

- before canonical lease binding;
- after canonical lease binding;
- immediately before temporary publication;
- immediately after temporary publication;
- immediately before exact temporary removal;
- immediately after exact temporary removal;
- immediately before committed promotion;
- immediately after committed promotion;
- after any exception before recovery is classified.

Each gate must prove all of the following at the same logical boundary:

1. the owner still holds the original production-lock descriptor;
2. the descriptor is a regular `root:root` `0600` file;
3. the lock pathname still resolves to the same device and inode;
4. independent contention is still proved by the owner;
5. the lease identity still matches the authority binding;
6. after binding, the descriptor bytes equal the canonical lease content;
7. the authoritative install transaction directory is still the fixed path,
   real `root:root` `0700`, and the same device/inode;
8. all five authoritative snapshot domains remain captured;
9. the split-bus route remains selected exactly once and unrestored;
10. the active route path still has the bound device, inode and SHA-256;
11. transaction, snapshot, package and hardware identities still equal the
    immutable authority binding;
12. the approval root and ancestor contract is exact.

Any mismatch is a hard failure. No write may follow a failed gate.

## Filesystem anchoring

The writer opens and retains one no-follow directory descriptor for the exact
approval root during each operation. Every approval and private name is accessed
relative to that descriptor through `dir_fd`/`*at` operations. Absolute path
resolution is used only to establish the fixed root contract before opening the
directory descriptor.

Published and private objects must be regular files with exact owner, group and
mode. Reads are bounded by the existing 64 KiB approval-record limit. Observation
returns raw bytes and metadata; it must not discard byte ordering, whitespace or
trailing-newline differences by decoding too early.

Private names are generated exclusively by the writer, created with
`O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`, and recorded with device, inode, exact
bytes and SHA-256. Cleanup never uses a glob and never removes an untracked name.

## Canonical lease-binding state machine

```text
REVERIFY BORROWED AUTHORITY
→ OBSERVE DESCRIPTOR CONTENT
→ require empty OR exact canonical lease
→ if empty: truncate, write all canonical bytes, truncate to exact length, fsync
→ REVERIFY BORROWED AUTHORITY
→ require exact canonical lease bytes
→ BOUND
```

If an exception occurs after lease mutation begins, the writer re-verifies the
owner and re-observes the descriptor:

- exact canonical bytes: treat binding as completed;
- empty bytes with approval proved absent: the transaction may fail into its
  ordinary exact rollback; the writer performs no retry;
- partial, different or unavailable bytes: retain the production lock and
  authoritative transaction for manual reconciliation.

The writer never repairs unexplained lock content and never releases the lock.

## Temporary publication state machine

Temporary publication starts only when the canonical lock lease is bound and
the published approval is absent or already equals the exact planned temporary
bytes.

```text
REVERIFY BORROWED AUTHORITY
→ OBSERVE published name as raw bytes
→ require absent OR exact temporary
→ create one private temporary file exclusively
→ write exact planned temporary bytes
→ fsync private file
→ verify private inode, owner, mode, bytes and SHA-256
→ atomically publish without replacement
→ fsync approval directory
→ observe and classify published raw bytes
→ require exact-temporary
→ remove only the exact tracked private name, if still present
→ fsync approval directory
→ REVERIFY BORROWED AUTHORITY
→ TEMPORARY PUBLISHED
```

Publication without replacement may use `linkat` followed by exact private-name
unlink, or `renameat2(RENAME_NOREPLACE)` if the implementation proves equivalent
identity and failure behaviour. A pre-existing published name is never replaced
by temporary publication.

After any indeterminate publication exception, the existing
`classify_approval_record_v7()` and
`resolve_indeterminate_approval_v7()` decisions are authoritative:

| observed state | permitted outcome |
| --- | --- |
| absent | exact rollback; remove only a proved private temporary object |
| exact-temporary | held transaction may continue |
| exact-committed | retain lock for manual reconciliation |
| mismatched | retain lock for manual reconciliation |
| observation-failure | retain lock for manual reconciliation |

There is no blind publication retry.

## Exact temporary removal state machine

Rollback removal is permitted only while the owner still holds exact authority,
the active route is still the selected split route, and the published raw bytes
exactly equal the planned temporary bytes.

```text
REVERIFY BORROWED AUTHORITY
→ open published approval with O_NOFOLLOW
→ verify regular file, root:root, 0600, bounded size and exact temporary bytes
→ re-check name-to-descriptor device/inode identity
→ unlink only activation-approved relative to the held approval-root descriptor
→ fsync approval directory
→ prove published name absent
→ REVERIFY BORROWED AUTHORITY
→ TEMPORARY REMOVED
```

No decoded-record equality is sufficient. If the name, inode, bytes, owner,
mode or root contract differs, automatic removal is forbidden.

If unlink outcome is indeterminate, post-exception observation decides:

- absent: exact removal completed;
- exact-temporary: removal did not complete and the caller may attempt ordinary
  transaction rollback only through an explicitly reviewed recovery step;
- exact-committed, mismatched or observation failure: retain lock for manual
  reconciliation.

The writer never removes a committed record.

## Committed promotion state machine

Promotion is a one-way authority boundary. It requires the exact planned
temporary bytes already published and the exact committed plan derived from that
temporary plan and durable commit-manifest SHA-256.

```text
REVERIFY BORROWED AUTHORITY
→ require published bytes exactly equal planned temporary bytes
→ create private committed candidate exclusively
→ write exact planned committed bytes
→ fsync candidate
→ verify candidate inode, owner, mode, bytes and SHA-256
→ atomically exchange candidate with activation-approved
→ fsync approval directory
→ observe and classify activation-approved
→ require exact-committed
→ retain or remove only the parked exact temporary object according to
  forward-recovery state
→ fsync approval directory after cleanup
→ REVERIFY BORROWED AUTHORITY
→ COMMITTED
```

The exchange uses Linux `renameat2(RENAME_EXCHANGE)` inside the already-open
approval-root directory. The private name then contains the former exact
temporary record and is tracked by exact device/inode and bytes.

After the exchange begins, the writer must never automatically exchange the
records back. Post-exception classification is authoritative:

| observed state | permitted outcome |
| --- | --- |
| exact-temporary | exact rollback may remove that exact temporary record |
| exact-committed | forward recovery only; never restore temporary state |
| absent | retain lock for manual reconciliation |
| mismatched | retain lock for manual reconciliation |
| observation-failure | retain lock for manual reconciliation |

When exact committed bytes are visible but directory durability or parked-file
cleanup is incomplete, forward recovery may re-fsync and remove only the parked
object proved to be the exact planned temporary inode and bytes. Failure to
prove either object retains the lock.

## Durability contract

Every created candidate is `fsync`ed before publication or exchange. Every
namespace mutation is followed by `fsync` of the already-open approval-root
directory. A successful receipt is issued only after:

- the final published raw bytes classify exactly;
- the namespace durability step succeeds;
- required private cleanup is complete or is explicitly represented by a typed
  forward-recovery state;
- borrowed authority re-verifies again.

A failed `fsync` is not reported as success merely because expected bytes are
currently visible.

## Recovery ownership

The writer returns typed state, not a Boolean success/failure assertion. Every
failure identifies:

- the operation and last completed boundary;
- publication knowledge;
- observed classifier state;
- whether exact rollback is permitted;
- whether forward recovery is permitted;
- whether the production lock must remain held;
- tracked private-name device/inode and byte identity, when one exists.

The terminal transaction executor remains responsible for sequencing inherited
C20 rollback. The writer cannot release authority. On any mismatch or unavailable
observation, the executor must stop automatic cleanup and leave the production
lock and authoritative transaction in place.

## Threat and failure table

| event | required response |
| --- | --- |
| borrowed descriptor closed or reused | identity gate fails; no write |
| lock pathname substituted | identity gate fails; retain owner authority |
| wrong or malformed lock lease | no approval write; fail closed |
| transaction directory replaced | no write; retain lock |
| selected route replaced or restored | no write; retain lock |
| approval ancestor symlinked | no write; retain lock |
| approval root owner/mode changed | no write; retain lock |
| published approval pre-exists with different bytes | never replace; manual reconciliation |
| short/partial candidate write | remove only exact tracked private inode; published name unchanged |
| ENOSPC before publication | exact private cleanup; ordinary rollback allowed only if approval absent |
| exception after temporary publication | classify raw published bytes; no blind retry |
| exception after committed exchange | exact committed means forward recovery only |
| directory `fsync` failure | no success receipt; retain lock until classified recovery |
| private parked name substituted | do not unlink it; retain lock |
| observation decode succeeds but raw bytes differ | `mismatched`; retain lock |
| observation unavailable | retain lock; manual reconciliation |
| process crash | next recovery must possess the same held owner authority; no independent writer restart |

## Disposable production-shaped implementation gate

The first implementation after this design must remain incapable of touching
production. It must:

1. operate only beneath a fresh, empty, real `0700` laboratory root;
2. reproduce the fixed `run/lock` and `var/lib/a-clockwork-plex/split-bus`
   relative layout;
3. use the test user's UID/GID in place of `root:root` while preserving exact
   mode and no-follow checks;
4. borrow a lock from a separate disposable C20-shaped owner rather than create
   or release that lock itself;
5. use the real canonical record plans and exact classifier;
6. inject failures before and after every lock write, candidate write, file
   `fsync`, publication, exchange, unlink, observation and directory `fsync`;
7. prove every classifier/recovery branch and exact private cleanup rule;
8. prove that exact committed observation can never trigger exchange-back;
9. prove the borrowed descriptor remains open, locked and owner-controlled after
   writer close or failure;
10. contain no `/var/lib`, `/run/lock`, `/etc`, systemd, subprocess, ALSA,
    CamillaDSP, DAC or service access outside the disposable root;
11. expose no CLI, installer or production constructor;
12. leave all four v7 production operations blocked.

The automated suite must include static AST/path checks and real Linux
filesystem tests beneath temporary directories. A result document and successful
GitHub Actions run are required before a fixed-path production implementation is
even designed.

## Roadmap

### Done

- C20 physical route-selection and exact-rollback checkpoint;
- C21 runtime authority and package review;
- disposable activation-approval lifecycle;
- borrowed authority view and immutable binding;
- exact canonical approval planning and reconciliation;
- this production-writer design review.

### Current

Implement and failure-inject the non-owning disposable production-shaped writer
beneath a fresh laboratory root.

### Next

Review the disposable result and then design the fixed-path production
filesystem adapter. No appliance command is part of either step.

### Risks and gates

- the Pi remains at the accepted C20 physical state;
- the known-good direct shared ALSA route remains the recovery truth;
- no Stage C21 production approval writer exists yet;
- no package is installed or activated;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged;
- physical Stage C21 work requires a fresh non-mutating Pi baseline and explicit
  review after all disposable and fixed-path code gates pass.
