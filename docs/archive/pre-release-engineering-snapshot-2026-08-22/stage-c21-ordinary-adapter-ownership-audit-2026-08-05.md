# Stage C21 ordinary-adapter ownership audit — 2026-08-05

## Outcome

**PASS — every Stage C21 production-adapter operation now has one immutable evidence/ownership classification, and the audit confirms that no terminal activation or exact-rollback operation is production ready.**

This was a source, contract and result-document audit plus static metadata and unit tests. It did not execute a rehearsal, acquire the appliance production lock, create an appliance transaction, write an approval, start CamillaDSP, change ALSA, or touch any service.

## Added files

- `scripts/stage_c_transaction/ordinary_adapter_coverage_v7.py`
- `tests/test_stage_c_ordinary_adapter_coverage_v7.py`

Commits:

```text
9e43d861ba69bf0cd58f284b2faae566d3af0832
feat: freeze Stage C21 ordinary adapter coverage

9d53a876a265829a9d83d6afda37a32d8dcc1d8b
test: prove Stage C21 adapter ownership audit
```

## Exact operation partition

The Stage C21 `ProductionAdapterV7` surface contains 42 operations.

| Evidence class | Count | Meaning |
|---|---:|---|
| C20 mandatory-rollback rehearsal | 29 | Implemented in the `RouteSelectionRollbackRehearsalAdapterV2` lineage and physically exercised only as a temporary, mandatory-rollback rehearsal |
| Blocked ordinary contract | 9 | Present in the v1–v6 typed protocol but not implemented by the furthest ordinary host adapter |
| Disposable approval laboratory | 4 | Implemented and filesystem-proved only beneath fresh disposable roots |
| Production-terminal-ready | 0 | No operation is permitted to claim this state |

The audit asserts that these three evidence sets are disjoint, cover all 42 operations exactly once, and preserve the frozen enum order.

## Furthest ordinary host adapter

The furthest real-host ordinary adapter remains the Stage C20 route-selection rollback chain:

```text
ReadOnlyHostProductionAdapter
  → ProductionLockRehearsalAdapter
  → AuthoritativeSnapshotRehearsalAdapter
  → CandidateValidationRehearsalAdapter
  → ServiceQuiescenceRehearsalAdapter
  → ManagedFileRollbackRehearsalAdapter V1–V4
  → SystemdReloadRollbackRehearsalAdapter
  → RouteSelectionRollbackRehearsalAdapter
  → RouteSelectionRollbackRehearsalAdapterV2
```

The later managed-file versions do not broaden the activation boundary. They harden exact rollback around partial directory creation, temporary inodes, atomic no-overwrite publication and identity-only cleanup.

Stage C19 adds a temporary daemon reload plus exact systemd-manager restoration. Stage C20 adds temporary split-route selection plus exact active-route inode restoration. Both remain mandatory-rollback rehearsals.

## Twenty-nine rehearsal-backed operations

The C20 adapter implements 24 v1 operations:

- inspect host contract;
- inspect, acquire and release production lock;
- create authoritative transaction;
- capture filesystem, service, mixer, loopback and DAC state;
- stage candidate files;
- validate ALSA, sudoers, units and CamillaDSP candidate content;
- stop captured application services;
- verify DAC release;
- install reviewed managed files;
- reload systemd;
- select the split-bus route;
- restore captured application services;
- verify dashboard health;
- restore exact snapshot;
- verify exact rollback.

It also implements the five historical closure operations:

- abort uncommitted transaction;
- close restored rehearsal transaction;
- close exact-rollback rehearsal transaction;
- close systemd-reload rollback rehearsal transaction;
- close route-selection rollback rehearsal transaction.

These 29 operations are physically meaningful evidence, but they are not production terminal implementations. The C20 transaction deliberately records:

- managed Stage C services not started;
- no audio probe opened;
- no commit manifest written;
- installation not committed;
- original route restored before closure.

## Nine blocked ordinary operations

The furthest C20 adapter still blocks exactly:

1. `start-managed-stage-c-services`
2. `stop-managed-stage-c-services`
3. `verify-split-bus-health`
4. `run-finite-music-probe`
5. `run-finite-alarm-probe`
6. `write-commit-manifest`
7. `select-direct-failback-route`
8. `restore-mixer-state`
9. `restore-service-state`

These gaps affect both the corrected terminal install suffix and exact rollback.

### Related runtime mechanics are not ordinary adapter implementations

The installed runtime-authority package has real Linux mechanics for:

- borrowed-lock temporary first start;
- CamillaDSP child start and stop;
- strict split-health checks;
- ordinary boot route selection;
- direct-route/failback handling.

Those mechanics use the runtime-authority protocol, not `ProductionAdapterV6`. The audit therefore records them only as related evidence for:

- `start-managed-stage-c-services`
- `stop-managed-stage-c-services`
- `verify-split-bus-health`
- `select-direct-failback-route`

They remain blocked ordinary operations until one explicit typed transaction adapter owns them.

Finite music/alarm probes, component mixer/service restoration and the historical commit-manifest operation have no corresponding ordinary terminal implementation.

## Four disposable-only approval operations

The four Stage C21 operations are:

- `bind-production-lock-lease`
- `publish-temporary-activation-approval`
- `remove-temporary-activation-approval`
- `promote-committed-activation-approval`

They have passed real filesystem, atomic publication, digest, rollback and lock-inode tests beneath fresh disposable roots. They have no production pathname, no appliance entrypoint and no production lock binding implementation.

## One lock and transaction authority

The existing real-host rehearsal lineage already owns the canonical authority:

```text
production lock:
/run/lock/a-clockwork-plex-audio-route.lock

authoritative transaction root:
/var/lib/a-clockwork-plex/split-bus/transactions
```

`ProductionLockRehearsalAdapter` creates, opens, flocks and verifies the exact production lock inode, then releases and unlinks that same inode.

`AuthoritativeSnapshotRehearsalAdapter` extends that owner with the authoritative transaction, package identity, snapshot identity and captured state.

Therefore:

- future approval code must bind to this already-held exact lock inode;
- future approval code must use this authoritative transaction identity;
- a second production lock adapter is forbidden;
- a production approval writer must not independently acquire or reconstruct ownership.

## Terminal readiness

### Corrected activation suffix

The 11-step suffix combines:

- rehearsal-only operations;
- blocked ordinary operations;
- disposable-only approval operations.

It is not production ready.

### Corrected exact rollback

The 10-step rollback likewise combines:

- rehearsal-only restoration operations;
- blocked managed-service, mixer and service restoration operations;
- disposable-only temporary approval removal.

It is not production ready.

The metadata rejects any attempt to mark even one operation `production_terminal_ready=True` at this stage.

## Validation

GitHub Actions run:

```text
31054204640
```

validated branch head:

```text
9d53a876a265829a9d83d6afda37a32d8dcc1d8b
```

Full result:

```text
Ran 1019 tests in 6.307s

OK
```

The new tests prove:

- exact 42-operation coverage;
- exact 29/9/4 partition;
- exact nine-operation blocked set;
- exact four-operation approval set;
- exact runtime-mechanics relationship set;
- no production-ready suffix or rollback operation;
- canonical single lock and transaction authority;
- frozen audit records;
- no host, command, CLI or generic-dispatch boundary in the audit module.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock was acquired;
- no production transaction was created;
- no approval was written on the appliance;
- no service or ALSA endpoint was touched;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Smallest safe next increment

Before any production approval writer is designed, the existing authoritative owner needs one immutable read-only typed view exposing only:

- exact held production lock path, device and inode;
- authoritative transaction identity;
- package fingerprint;
- snapshot identity;
- authoritative transaction path identity;
- proof that the caller still owns the exact lock.

That view must:

- be produced by the existing `AuthoritativeSnapshotRehearsalAdapter` lineage;
- expose no file descriptor and no mutation method;
- perform no filesystem write;
- never acquire a second lock;
- fail unless the exact existing lock and transaction identities still match;
- be independently testable with disposable roots before any production approval adapter consumes it.

Only after that read-only ownership boundary is proved should a production approval adapter design begin.
