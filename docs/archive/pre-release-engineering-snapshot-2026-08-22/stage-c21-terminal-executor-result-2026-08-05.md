# Stage C21 pure terminal executor result — 2026-08-05

## Outcome

**PASS — the corrected Stage C21 terminal activation suffix and complete exact-rollback program now have one pure, typed executor with no host implementation or activation entrypoint.**

The executor is policy/orchestration code only. It cannot touch Linux, ALSA, systemd, the production lock, the approval store, CamillaDSP, or the Raspberry Pi unless a separately reviewed `ProductionAdapterV7` implementation is supplied.

## Added files

- `scripts/stage_c_transaction/activation_commit_executor_v7.py`
- `tests/test_stage_c_activation_commit_executor_v7.py`

Commits:

```text
85bafd6d25dbc8a985349eb7bb387a09aa8ef1e9
feat: add pure Stage C21 terminal executor

29000f8711a096108773239b1146d759c500e375
test: prove pure Stage C21 terminal execution
```

## Execution boundary

The executor accepts only:

- a supplied object satisfying the runtime-checkable `ProductionAdapterV7` protocol;
- an existing authoritative install transaction;
- its captured service snapshot;
- its captured mixer snapshot.

It does not acquire a lock, create a transaction, capture state, stage files, install files, select a route, expose a CLI, or construct an adapter. Those remain earlier transaction responsibilities and separately reviewed boundaries.

The authoritative transaction must use `TransactionAction.INSTALL`; rollback, uninstall and runtime-failback transactions are rejected.

## Fixed install suffix

The executor consumes the immutable Stage C21 suffix exactly:

1. `bind-production-lock-lease`
2. `publish-temporary-activation-approval`
3. `start-managed-stage-c-services`
4. `verify-split-bus-health`
5. `run-finite-music-probe`
6. `run-finite-alarm-probe`
7. `restore-captured-application-services`
8. `verify-split-bus-health`
9. `verify-dashboard-health`
10. `promote-committed-activation-approval`
11. `release-production-lock`

Every operation uses one explicit typed method call. There is no dynamic operation-to-method lookup, generic dispatcher, command string, method-name construction, `getattr`, `eval`, or `exec` path.

## Fixed exact rollback

Every reconciled pre-terminal failure invokes the complete Stage C21 rollback:

1. `stop-captured-application-services`
2. `stop-managed-stage-c-services`
3. `remove-temporary-activation-approval` when temporary approval is known to exist
4. `verify-dac-released`
5. `restore-exact-snapshot`
6. `reload-systemd`
7. `restore-mixer-state`
8. `restore-service-state`
9. `verify-exact-rollback`
10. `release-production-lock`

A rollback operation failure or exception stops rollback immediately and returns a fail-closed result with the production lock retained.

## Approval knowledge model

The executor records only four possible knowledge states:

- `absent`
- `temporary`
- `committed`
- `indeterminate`

This deliberately separates adapter failure results from adapter exceptions.

### Explicit FAIL or BLOCKED result

A typed failure result is treated as a reconciled, no-effect failure for that operation. Before terminal publication, exact rollback owns the failure.

### Exception while publishing temporary approval

The executor cannot know whether atomic publication completed before the exception. It therefore:

- marks approval state `indeterminate`;
- does not attempt blind approval removal or exact rollback;
- retains the production lock;
- returns `fail-closed-lock-retained`.

### Exception while promoting committed approval

The same conservative rule applies. The executor cannot safely choose between rollback and forward recovery without reconciling the approval store. It therefore retains the lock and reports indeterminate approval state rather than risking rollback of an authoritative committed install.

A future host adapter/orchestrator must add explicit durable reconciliation for this boundary before production activation.

## Terminal ownership

Successful committed approval promotion changes the known state to `committed`.

After that point:

- successful production-lock release returns `committed`;
- failed or exceptional lock release returns `forward-recovery-required`;
- exact rollback is never started after committed publication.

## Typed result validation

The executor rejects:

- a receipt whose operation identity differs from the requested operation;
- an approval operation returning an ordinary `AdapterResult`;
- an ordinary operation returning an approval result;
- a successful approval operation without its exact expected typed receipt;
- an ordinary receipt-only operation that invents a payload;
- a non-`ProductionAdapterV7` object;
- a non-install transaction context.

Results and execution records are frozen dataclasses.

## Validation

Before publication, 12 focused reconstructed-contract tests passed.

GitHub Actions run:

```text
31052885115
```

validated the exact branch head:

```text
29000f8711a096108773239b1146d759c500e375
```

Full result:

```text
Ran 1001 tests in 6.222s

OK
```

Coverage includes:

- successful exact suffix execution;
- every explicit pre-terminal failure;
- every exact-rollback failure boundary;
- ordinary adapter exceptions;
- mismatched operation receipts;
- temporary-publication uncertainty;
- committed-promotion uncertainty;
- post-commit forward recovery;
- blocked-adapter behaviour;
- transaction and adapter type gates;
- immutable result records;
- absence of host, CLI, command and generic-dispatch boundaries.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock was acquired;
- no production approval file was written;
- no service was started, stopped, enabled or reloaded;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next engineering boundary

The pure executor has no usable production adapter, which is intentional.

The next safe increment is a typed composition bridge that can combine:

- one supplied v1–v6 adapter for ordinary transaction operations; and
- one supplied v7 approval-lifecycle adapter;

while adding no filesystem, process, service, CLI or production path of its own.

The first proof should use only:

- a deterministic recording ordinary adapter; and
- the existing fresh-root disposable approval adapter.

That integration must demonstrate the complete executor against real approval-store filesystem semantics beneath a disposable laboratory root before any Linux production approval adapter is designed.
