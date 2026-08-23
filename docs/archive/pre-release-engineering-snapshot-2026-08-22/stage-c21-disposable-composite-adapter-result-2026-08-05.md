# Stage C21 disposable composite-adapter result — 2026-08-05

## Outcome

**PASS — the pure Stage C21 terminal executor now runs end to end through one explicit 42-method composite adapter, including real approval-store and lock-inode semantics beneath a disposable laboratory root.**

This remains a sandbox proof only. The composition bridge contains no Linux implementation, filesystem access, process execution, service helper, audio access, CLI or generic dispatch path. The only real filesystem activity occurred inside fresh temporary directories created by the unit tests.

## Added files

- `scripts/stage_c_transaction/composite_production_adapter_v7.py`
- `tests/test_stage_c_composite_production_adapter_v7.py`

Commits:

```text
23d0e95a3133a4e84bbf241f91d87ca9e51217fe
feat: add explicit Stage C21 adapter composition

6e03c64a89647f40caf46335bd59913410bf58af
test: prove disposable Stage C21 adapter composition

352073de9805dee3b7d7c88919063fc321bfb246
fix: use canonical runtime authority model in composite tests
```

## Composition boundary

`CompositeProductionAdapterV7` accepts exactly two supplied authorities:

- `ordinary`: a `ProductionAdapterV6` implementing the frozen v1–v6 transaction operations;
- `approval`: a `ProductionAdapterV7` supplying the four Stage C21 approval/lease operations.

The bridge exposes the exact 42-operation v7 surface:

- 33 original Stage C10 operations;
- five versioned transaction-closure operations from v2 through v6;
- four Stage C21 approval/lease operations.

Every method delegates explicitly. There is no:

- `__getattr__` or reflective forwarding;
- method-name construction;
- generic dispatcher;
- operation-string lookup;
- `eval`, `exec`, `getattr` or `setattr`;
- host command, path or process boundary.

Runtime protocol checks reject an ordinary delegate that does not satisfy `ProductionAdapterV6` and an approval delegate that does not satisfy `ProductionAdapterV7`.

## Disposable integration proof

The end-to-end tests combine:

- the pure Stage C21 terminal executor;
- the explicit composite adapter;
- a receipt-only recording ordinary adapter;
- the existing `DisposableActivationApprovalLifecycleAdapter`;
- the real `ApprovalStore` and activation-approval record model.

The disposable approval adapter creates and owns one exact 0600 flocked lock inode beneath a fresh owned 0700 temporary root. The recording ordinary adapter releases that same inode by invoking the approval adapter's exact disposable transaction closure. It does not simulate lock release with an unrelated flag.

## Successful commit path

The complete corrected suffix was executed:

1. bind the exact disposable lock lease;
2. atomically publish and verify a non-bootable temporary approval;
3. run receipt-only managed-service, health and finite-probe operations;
4. restore captured applications;
5. re-verify split health and dashboard health;
6. record a fixed rehearsal commit-manifest digest;
7. atomically promote the exact temporary approval to committed state;
8. release and unlink the exact disposable lock inode.

The test then proved:

- executor outcome `committed`;
- lock no longer held;
- exact disposable lock pathname absent;
- approval adapter closed;
- stored approval phase `committed`;
- exact transaction and package identities retained;
- expected commit-manifest SHA-256 retained;
- expected committed timestamp retained;
- historical `write-commit-manifest` was not executed as a second terminal marker.

## Exact rollback path

An explicit ordinary-adapter failure was injected at `run-finite-music-probe` after temporary approval publication.

The executor then ran the full corrected rollback:

1. stop captured application services;
2. stop managed Stage C services;
3. remove the exact temporary approval;
4. verify DAC release;
5. restore exact snapshot;
6. reload systemd;
7. restore mixer state;
8. restore service state;
9. verify exact rollback;
10. release and unlink the exact disposable lock inode.

The test proved:

- executor outcome `exactly-rolled-back`;
- exact rollback verified;
- temporary approval absent;
- exact lock pathname absent;
- approval adapter closed;
- lock release remained the final ordinary operation.

## Blocked approval proof

A composite using `BlockedProductionAdapterV7` as its approval authority cannot invent a hidden Stage C21 path.

The first lease-binding operation fails, the supplied ordinary laboratory adapter performs complete exact rollback, and the exact disposable lock is released without any approval record being created.

## Initial CI failure and correction

GitHub Actions run `31053475003` compiled all modules and passed static checks, but six new integration tests failed while constructing the disposable adapter.

Root cause: the test imported `ApprovalPhase` through the package name:

```text
scripts.stage_c_runtime_authority.model
```

while the established disposable adapter imports the same source through:

```text
stage_c_runtime_authority.model
```

Python therefore created two distinct enum class identities from the same file. The record displayed `TEMPORARY`, but identity comparison against the adapter's canonical `TEMPORARY` member failed.

The test was corrected to use the same canonical top-level runtime-authority import as the adapter. No production or orchestration code changed.

## Final validation

GitHub Actions run:

```text
31053623598
```

validated branch head:

```text
352073de9805dee3b7d7c88919063fc321bfb246
```

Full result:

```text
Ran 1009 tests in 5.733s

OK
```

The new coverage proves:

- the exact 42-method bridge surface;
- runtime protocol gates;
- strict ordinary-versus-approval delegation;
- frozen bridge configuration;
- successful real disposable approval commitment;
- complete real disposable approval rollback;
- one exact lock inode across approval and release ownership;
- blocked approval behaviour;
- no host, CLI, reflection or generic dispatch boundary in the bridge.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock was acquired;
- no production approval path was written;
- no real service was started, stopped, enabled or reloaded;
- no ALSA endpoint or DAC was opened;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next engineering boundary

The terminal executor and composition boundary are now proved. Before designing any production approval adapter or activation entrypoint, the repository must be audited for existing v1–v6 ordinary host-adapter implementations and their physically proved operation coverage.

That audit must identify:

1. which of the corrected terminal suffix and rollback operations already have one existing typed Linux implementation;
2. which methods remain blocked or rehearsal-only;
3. whether one adapter already owns the exact production lock and transaction state;
4. whether approval operations can safely extend that same owner instead of creating a second lock authority;
5. what explicit reconciliation is still required for indeterminate temporary or committed approval publication;
6. the smallest next non-activating implementation increment.

No Linux production approval adapter or activation entrypoint should be introduced until that ownership audit is complete.
