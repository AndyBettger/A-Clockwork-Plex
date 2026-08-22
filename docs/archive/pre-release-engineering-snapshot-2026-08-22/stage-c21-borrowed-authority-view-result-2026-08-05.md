# Stage C21 borrowed-authority view result — 2026-08-05

## Outcome

**PASS — future Stage C21 approval work can now receive one immutable read-only view of the exact existing C20 authority owner without acquiring a second lock, exposing the lock descriptor or adding another production-adapter operation.**

This phase added only an inspection function, frozen identity/result records and unit tests. It did not run on `plexamp-bedroom`, acquire a production lock, create a transaction, select a route, write an approval, start CamillaDSP or touch ALSA/systemd/services.

## Added files

- `scripts/stage_c_transaction/borrowed_authority_view_v7.py`
- `tests/test_stage_c_borrowed_authority_view_v7.py`

Commits:

```text
bdb3e648c60225eb7df21ef4e0cf17f299053ed7
feat: add read-only Stage C21 borrowed authority view

267f7ea4eba5eb01fef8713f470f5c139cd37845
test: prove read-only Stage C21 authority view
```

## Existing owner only

`inspect_borrowed_authority_v7()` accepts only an already-created instance from the exact C20 owner lineage:

```text
RouteSelectionRollbackRehearsalAdapterV2
```

It does not construct an adapter or acquire any authority. A different object is rejected before observation.

The view therefore extends the ownership boundary identified by the ordinary-adapter audit:

- `ProductionLockRehearsalAdapter` owns the exact production lock descriptor and inode;
- `AuthoritativeSnapshotRehearsalAdapter` owns the transaction, package and snapshot;
- the Stage C20 route adapter owns the currently selected split-route identity;
- Stage C21 receives identities only and does not become another owner.

## Preconditions

The view refuses to exist unless all of the following remain true at inspection time.

### Exact production lock

- the existing adapter still holds its descriptor;
- the existing lease is present and still names the canonical lock path;
- descriptor and pathname still identify the same regular-file device/inode;
- current lock evidence exactly matches the evidence captured at acquisition;
- the existing lease identifier is retained.

### Exact authoritative transaction

- the existing install transaction is present;
- package identity still matches the owner package;
- transaction path is exactly:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<transaction-id>
```

- transaction directory remains the captured device/inode;
- directory remains a real root-owned 0700 directory;
- action remains `install`.

### Complete snapshot boundary

All five captured domains must be complete:

- filesystem;
- service;
- mixer;
- loopback;
- DAC.

### Current split-bus route

- route is currently selected;
- route was selected exactly once;
- route has not already been restored;
- current active-route device, inode, mode, ownership and SHA-256 still match the transaction-recorded candidate.

## Returned view

A successful `BorrowedAuthorityViewV7` contains only immutable values:

- canonical production lock path;
- existing lock lease ID;
- lock device and inode;
- transaction identity;
- snapshot identity;
- package fingerprint;
- authoritative transaction path;
- transaction-directory device and inode;
- selected route path;
- selected route device, inode and SHA-256;
- explicit complete-snapshot, selected-route, exact-lock and exact-transaction proofs.

It deliberately contains no:

- file descriptor;
- open file object;
- adapter reference;
- mutation callback;
- pathname writer;
- command;
- service or route action.

The result and payload are frozen dataclasses.

## No 43rd operation

The view is not part of `ProductionAdapterV7` and does not add an `inspect-borrowed-authority` operation.

The production-adapter surface remains exactly 42 operations. This avoids turning an internal ownership handoff into another dispatchable host action.

## Failure behaviour

Every identity or readiness problem returns a typed failure with no payload, including:

- missing held lock;
- missing transaction;
- non-install transaction;
- package mismatch;
- non-canonical transaction path;
- incomplete transaction device/inode;
- any incomplete snapshot domain;
- route absent, restored or selected more than once;
- changed lock evidence;
- substituted transaction directory;
- changed selected route;
- lock or route observation error.

No failure path writes, repairs, reacquires or releases anything.

## Validation

GitHub Actions push run:

```text
31054528150
```

validated branch head:

```text
267f7ea4eba5eb01fef8713f470f5c139cd37845
```

Full result:

```text
Ran 1029 tests in 6.384s

OK
```

The new tests prove:

- exact successful identity projection;
- no descriptor/file-descriptor field;
- frozen view and result records;
- exact C20 owner type gate;
- missing lock/transaction failure;
- five-domain snapshot requirement;
- current exactly-once route requirement;
- transaction action, package and path authority;
- changed lock, transaction or route identity failure;
- typed observation failures;
- result payload invariants;
- unchanged 42-operation adapter surface;
- absence of filesystem writes, commands, CLI and generic dispatch in the view module.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock was acquired;
- no production transaction was created;
- no approval was written on the appliance;
- no route, service or endpoint was touched;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next engineering boundary

The view has no consumer, which is intentional.

The next safe increment is a pure approval-authority binding contract that consumes a `BorrowedAuthorityViewV7` and produces immutable approval-binding metadata only. It must:

1. preserve the exact lock lease, device and inode;
2. preserve transaction, package and snapshot identities;
3. preserve the selected-route digest;
4. contain no production pathname writer or file operation;
5. provide the typed input needed by a future approval adapter;
6. define explicit reconciliation states for uncertain temporary or committed publication;
7. remain unusable as an activation entrypoint.

A production approval writer should not be implemented until that binding and reconciliation policy has passed pure and disposable tests.
