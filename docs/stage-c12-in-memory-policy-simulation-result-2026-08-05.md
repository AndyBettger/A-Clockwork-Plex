# Stage C12 typed adapter results and in-memory policy simulation — result

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Result

**PASS — automated in-memory policy simulation.**

Stage C12 refines the blocked Stage C adapter contract with immutable typed result payloads and then executes the four Stage C11 policy programs only against a deterministic in-memory recording adapter.

The Stage C12 implementation is contained in:

```text
scripts/stage_c_transaction/production_policy_simulation.py
```

The refined typed contract remains in:

```text
scripts/stage_c_transaction/production_adapter_contract.py
```

The focused safety coverage is contained in:

```text
tests/test_stage_c_production_adapter_contract_safety.py
tests/test_stage_c_production_policy_simulation_safety.py
```

No production adapter, CLI, wrapper, confirmation token, root command or Pi-facing execution path exists. The simulator imports no filesystem, process, lock, service, network or audio library and cannot inspect or modify the host.

Persistent Stage C activation remains blocked.

## Commits

```text
01d86cc03ed26784cf26cf836a9987994c9feb04
  Design Stage C12 in-memory policy simulation

54a0087a5b177194ac566ebc1c7ece99acdb0da2
  Add typed Stage C adapter result payloads

da2549efe672f184b883552f24ffc2fafbb11a7b
  Test typed Stage C adapter result payloads

503c3e2e367b20b323157a9ed6d6ac3d621bcb27
  Add Stage C12 in-memory policy simulator

1cb94a9115cb65421b9c21b12797e86ecaecc256
  Bind C12 simulation to adapter-generated identities

d2dc3657917ef3b27d4ae9df0eac2eb435675b94
  Test Stage C12 in-memory policy simulation

24da695ba4f8c3bed5754fdcb52da33deb6ca105
  Keep C12 terminal success scoped to primary action
```

## Typed adapter-result boundary

`AdapterResult` is now a frozen generic record:

```text
AdapterResult[T]
```

It records:

- the exact `AdapterOperation`;
- `PASS`, `FAIL` or `BLOCKED` status;
- human-readable detail;
- immutable structured evidence;
- an optional typed payload.

Failed or blocked results are forbidden from carrying a success payload.

The nine payload-producing operations return exact immutable types:

| Operation | Payload |
|---|---|
| `inspect-host-contract` | `HostContractSnapshot` |
| `inspect-production-lock` | `ProductionLockObservation` |
| `acquire-production-lock` | `ProductionLockLease` |
| `create-authoritative-transaction` | `AuthoritativeTransaction` |
| `capture-filesystem-state` | `FilesystemSnapshot` |
| `capture-service-state` | `ServiceSnapshot` |
| `capture-mixer-state` | `MixerSnapshot` |
| `capture-loopback-state` | `LoopbackSnapshot` |
| `capture-dac-state` | `DacSnapshot` |

The remaining 24 operations return receipt-only `AdapterResult[None]` values.

`AuthoritativeTransaction` binds together:

```text
adapter-generated TransactionIdentity
adapter-generated SnapshotIdentity
TransactionAction
PackageFingerprint
```

A normal unheld-entry transaction therefore cannot receive a caller-supplied transaction or snapshot identity.

The contract also validates:

- lowercase 64-character SHA-256 package fingerprints;
- non-empty identities without whitespace;
- the exact six service units;
- the exact four mixer controls;
- the fixed loopback and DAC contracts;
- complete structured DAC-owner evidence;
- mixer values from 0 through 100;
- a released DAC observation containing no owners.

The original `BlockedProductionAdapter` still refuses all 33 host operations.

## In-memory recording adapter

`RecordingProductionAdapter` is a protocol-conforming simulation object. It:

- stores no real path or file handle;
- models the production lock as an in-memory Boolean;
- produces deterministic synthetic identities and typed snapshots;
- records every attempted operation in order;
- can fail one exact occurrence of one exact operation;
- exposes no CLI or production entrypoint.

The adapter stores the authoritative transaction that it generated. Later methods reject:

- a substituted transaction identity;
- a substituted snapshot identity;
- a substituted package fingerprint;
- an operation attempted without the simulated held lock;
- an operation attempted before an authoritative transaction exists.

The synthetic filesystem capture returns the same `SnapshotIdentity` contained in the authoritative transaction rather than creating an unrelated or parse-derived identity.

## Explicit operation dispatch

The policy simulator has one explicit `match` branch for every one of the 33 `AdapterOperation` values.

It contains no:

```text
getattr
callback table
caller-supplied method name
generic execute/run command
raw argv
shell execution
```

The dispatcher may pass only values already present in the validated in-memory context:

- package fingerprint;
- transaction action;
- adapter-generated transaction and snapshot identities;
- captured service snapshot;
- captured mixer snapshot.

## Successful policy simulations

The simulator executes all four Stage C11 programs successfully and records operation sequences that match their immutable definitions exactly:

```text
install
automatic-exact-rollback
runtime-direct-failback
explicit-uninstall
```

Successful simulations prove the policy-level lock model:

- install, failback and uninstall acquire and release the simulated lock;
- standalone exact rollback enters with the lock already held;
- exact rollback never reacquires the lock;
- terminal success occurs before the final release operation;
- all successful actions finish with the simulated lock released.

These are in-memory policy proofs only and do not prove the behaviour of a future real lock or host adapter.

## Install failure matrix

### Failure before lock acquisition

Failure at `inspect-host-contract` records no release attempt because no lock was acquired.

Expected outcome:

```text
failed-before-lock
lock_held=false
rollback_started=false
```

### Failure after lock acquisition but before mutation

Failure during capture, staging or candidate validation uses the Stage C11 `abort-release-lock` disposition.

The simulator releases the acquired lock and does not invoke automatic rollback.

Expected outcome:

```text
aborted
lock_held=false
rollback_started=false
```

### Failure at the first managed-audio mutation

Failure at `stop-captured-application-services` is classified as post-mutation because the failed step itself is a managed-audio mutation.

The simulator immediately enters the exact Stage C11 rollback program while retaining the same lock. The complete rollback sequence runs without a second acquisition.

Expected outcome:

```text
rolled-back
rollback_started=true
rollback_completed=true
lock_held=false
```

### Failure later in installation

Failure at `install-managed-files` or the second occurrence of `verify-split-bus-health` likewise invokes the exact rollback program and retains the same lock through zero-mismatch verification.

### Commit failure

Failure of `write-commit-manifest` occurs before install terminal success and therefore invokes exact automatic rollback.

The requested install correctly reports:

```text
terminal_success=false
rollback_completed=true
```

### Lock-release failure after commit

Failure of `release-production-lock` occurs after the install commit manifest has succeeded.

The simulator therefore reports:

```text
outcome=fail-closed
terminal_success=true
lock_held=true
rollback_started=false
failure_disposition=fail-closed-retain-lock
```

It does not roll back a valid committed installation merely because final lock release failed.

## Rollback failure behaviour

A failure inside automatic exact rollback:

- stops rollback immediately;
- retains the simulated lock;
- records `fail-closed-retain-lock`;
- reports no rollback completion;
- never starts a nested second rollback implementation;
- never reacquires the lock.

The focused test injects an install failure followed by a failure at `restore-exact-snapshot`. The rollback record stops at that exact failing operation and the lock remains held.

## Runtime failback and explicit uninstall failures

Runtime failback and explicit uninstall do not borrow install's automatic rollback policy.

A post-mutation failure during either action:

- reports `fail-closed`;
- retains the lock;
- does not launch automatic exact rollback;
- preserves the distinction between committed-install runtime failback, exact rollback and explicit uninstall.

## Defect discovered and corrected during CI

The first complete C12 run executed all substantive policy behaviours correctly but failed one result-semantics assertion.

A failed install commit successfully completed automatic exact rollback. The simulator then returned:

```text
terminal_success=true
```

because the rollback program had reached its own terminal operation, `verify-exact-rollback`.

That field is intended to answer whether the **requested primary action** reached terminal success, not whether a recovery program did. The simulator was corrected to capture the primary action's terminal-success state before entering recovery.

The corrected reporting is:

```text
failed install + successful rollback:
  terminal_success=false
  rollback_completed=true
```

No Stage C11 sequence, failure disposition or adapter operation changed as part of this correction.

## Focused safety coverage

The 14 Stage C12 simulation tests prove that:

1. the simulator has no host-access or entrypoint imports;
2. the recording adapter satisfies the typed protocol and has one explicit branch for every operation;
3. transaction, snapshot and package substitution are rejected;
4. all four success paths match the Stage C11 programs exactly;
5. pre-lock failure never attempts release;
6. pre-mutation failure after acquisition releases without rollback;
7. first-mutation failure invokes exact rollback without reacquisition;
8. commit failure invokes rollback before terminal success;
9. release failure after commit never invokes rollback;
10. rollback failure retains the lock without nesting recovery;
11. standalone rollback uses the already-held lock and exact sequence;
12. the second split-bus-health occurrence can fail deterministically and invoke rollback;
13. failback and uninstall post-mutation failures fail closed without install rollback;
14. duplicate failure injections are rejected.

The typed adapter contract tests separately verify specific payload annotations, frozen records and the prohibition on failed results carrying success payloads.

## Final CI result

The corrected C12 branch passed the complete suite:

```text
Ran 626 tests in 5.282s
OK
```

The same run also completed:

- the Stage C7 root-owned disposable transaction with all 12 checks passing and zero rollback mismatches;
- the consolidated Stage C4 sandbox transaction with all nine checks passing and zero rollback mismatches.

No production path or audio command was used by those existing synthetic rehearsals.

## What Stage C12 proves

Stage C12 proves that:

- later policy steps can consume typed adapter-produced values without parsing strings;
- transaction and snapshot identity ownership remains with the adapter boundary;
- all 33 host operations have one explicit policy dispatch branch;
- the four Stage C11 programs can be recorded exactly in memory;
- install failure classification changes correctly at lock, mutation, commit and post-commit boundaries;
- exact rollback retains the original lock and cannot nest itself;
- a committed installation is not undone because final release fails;
- runtime failback and explicit uninstall retain their distinct policies;
- all of this can be tested without touching the host.

## What Stage C12 does not prove

Stage C12 does not prove:

- real production-lock creation, contention or release;
- authoritative transaction-directory creation;
- filesystem snapshot or installation behaviour;
- systemd, mixer, module, ALSA, PCM, DAC or CamillaDSP behaviour;
- dashboard health behaviour;
- real automatic rollback, runtime failback or uninstall;
- reboot persistence.

Every operation remains either blocked or represented by an in-memory recording result.

## Acceptance

Stage C12 is accepted as **PASS** at the automated typed-result and in-memory policy-simulation boundary.

No Pi command is generated for this stage. No persistent installer exists, the blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
