# Stage C11 static transaction-policy operation programs — result

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Result

**PASS — automated static-policy review.**

Stage C11 binds the reviewed production transaction policy to the Stage C10 typed operation vocabulary through four immutable in-memory programs:

```text
install
automatic-exact-rollback
runtime-direct-failback
explicit-uninstall
```

The programs are defined in:

```text
scripts/stage_c_transaction/production_operation_programs.py
```

The focused safety coverage is defined in:

```text
tests/test_stage_c_production_operation_programs_safety.py
```

No program imports, constructs or invokes a production adapter. No CLI, wrapper, confirmation token, root command or Pi execution path exists in Stage C11.

Persistent Stage C activation remains blocked.

## Commits

```text
9ee0ff58b91106009f078b34f2b067afb3b8bbe0
  Design Stage C11 static operation programs

b1e130b5a2d85687f52369e185bbbed3da72d9b5
  Add Stage C11 immutable operation programs

0392c81cfc2f916eb753904c4e7465456eb0126b
  Test Stage C11 immutable operation programs

4eca2dd7ec7286c8690e5956dd068d3a176c3eee
  Pin Stage C11 action mapping explicitly

45016da0e3a5c54b0a595ec44a0e6430c383f157
  Model Stage C11 terminal success boundary

3386181601530a5f7790a738700865fac1404029
  Test Stage C11 terminal success boundary
```

## Authority boundary

Stage C11 does not create another transaction engine. It adds only immutable policy metadata mapping a `TransactionAction` to an ordered tuple of Stage C10 `AdapterOperation` values.

The module imports no adapter protocol or implementation, carries no callback or callable, performs no dynamic dispatch and has no method capable of executing a step.

## Exact policy mapping

The final mapping is deliberately ordered by policy role rather than by enum declaration order:

```text
install                  -> install
automatic-exact-rollback -> exact-rollback
runtime-direct-failback  -> runtime-failback
explicit-uninstall       -> explicit-uninstall
```

Every `TransactionAction` appears exactly once.

## Immutable program model

Each `OperationProgram` records:

- one program name and transaction action;
- entry lock state;
- snapshot source;
- failure disposition before managed-audio mutation;
- failure disposition after mutation but before terminal success;
- one terminal-success operation;
- failure disposition after terminal success;
- an ordered tuple of frozen steps.

Import-time validation requires:

- step numbers in exact increments of ten;
- one terminal-success operation exactly once;
- terminal success immediately before lock release;
- lock release as the final operation;
- one acquisition in every unheld-entry program;
- no lock-required step before acquisition;
- every later step to require the held lock;
- no reacquisition by automatic rollback.

## Three failure zones

Stage C11 now distinguishes three failure zones.

### Before managed-audio mutation

A failure before the first managed-audio mutation is a pre-mutation abort. It does not claim production rollback.

### After mutation but before terminal success

For install, this zone invokes automatic exact rollback while retaining the same production lock.

Rollback, runtime failback and explicit uninstall instead fail closed and retain the lock if their own recovery/removal sequence fails.

### After terminal success

Terminal success is:

```text
install                 write-commit-manifest
automatic rollback      verify-exact-rollback
runtime failback        write-commit-manifest
explicit uninstall      write-commit-manifest
```

It occurs immediately before lock release. A lock-release failure after terminal success is `fail-closed-retain-lock`; it must never re-enter rollback or undo a committed or exactly verified result.

This boundary was added after reviewing how a future C12 runner would classify a release failure after a successful install commit. The correction was made while C11 remained static metadata and before any adapter execution existed.

## Install program

The 28-step install program:

- inspects the host and lock boundary;
- acquires the one route lock;
- creates a fresh authoritative transaction;
- captures filesystem, service, mixer, loopback and DAC state;
- stages and validates all candidate families;
- stops only captured-active application services as its first managed-audio mutation;
- verifies DAC release;
- installs files, reloads systemd and selects split bus;
- starts Stage C services;
- verifies health and finite music/alarm probes;
- restores captured-active application services;
- re-verifies split-bus and dashboard health;
- writes the commit manifest;
- releases the lock.

Only failures after the first managed-audio mutation and before the commit manifest invoke automatic exact rollback.

## Automatic exact rollback program

The nine-step rollback program enters with the failed transaction's lock already held. It:

- stops captured application services;
- stops Stage C services;
- verifies DAC release;
- restores the exact authoritative snapshot;
- reloads systemd;
- restores mixer and service state;
- verifies zero exact-restoration mismatches;
- releases the lock.

It never reacquires the lock. Exact rollback verification is terminal success.

## Runtime direct failback program

The 18-step runtime failback program preserves the committed installation while selecting the physically proven direct alarm-bypass route.

It stops application and Stage C services, verifies DAC release, selects direct failback, restores live mixer and application-service state, runs finite music and alarm probes, verifies dashboard degraded-route health, records the transition and releases the lock.

It contains neither `restore-exact-snapshot` nor `select-split-bus-route`.

## Explicit uninstall program

The 17-step explicit-uninstall program is composed by transaction policy from small typed operations. It stops application and Stage C services, restores the committed installation's exact pre-install snapshot, reloads systemd, restores original mixer/service state, verifies exact restoration, records completion and releases the lock.

`TransactionAction.EXPLICIT_UNINSTALL` remains present, but Stage C10 contains no adapter-level `explicit_uninstall()` method or operation. This preserves one orchestration authority.

## CI corrections discovered

### Program-order assertion

The first Stage C11 CI run had one failing test because it compared policy program order with enum declaration order. All substantive ordering tests passed. The test was corrected to pin the exact name-to-action mapping and separately verify complete action coverage. No operation program changed for that correction.

### Terminal-success boundary

A subsequent commit-boundary review identified that a two-zone failure model could misclassify lock-release failure after a successful install commit. Stage C11 was corrected to record one terminal-success operation and a distinct post-terminal failure disposition.

Tests now require terminal success to be the penultimate step and require all four programs to use `fail-closed-retain-lock` after terminal success.

## Focused safety coverage

The 11 Stage C11 tests prove that:

1. the module is static metadata without execution imports;
2. exactly four immutable programs map every action once;
3. every step uses only Stage C10 operation enums;
4. unheld programs acquire before every lock-bound step;
5. install matches the reviewed order and first-mutation boundary;
6. install commits only after post-start and dashboard health;
7. rollback retains the existing lock and verifies before release;
8. runtime failback remains alarm-safe and distinct from uninstall;
9. explicit uninstall is policy composition, not an adapter shortcut;
10. static snapshots include terminal-success metadata;
11. structural guards reject unsafe sequence, lock and terminal shapes.

## Full CI result

The final terminal-success version passed the complete branch suite:

```text
Ran 612 tests
OK
```

The Stage C7 disposable-root transaction and consolidated Stage C4 sandbox transaction also completed successfully during the same run with exact rollback and no production writes.

## What Stage C11 proves

Stage C11 proves that:

- install, rollback, failback and uninstall have one explicit policy-owned order;
- lock ownership is consistent across all programs;
- rollback retains rather than reacquires the failed transaction's lock;
- runtime failback remains distinct from exact rollback and uninstall;
- explicit uninstall cannot be delegated to a broad adapter shortcut;
- committed or exactly verified results are not rolled back because lock release fails;
- every program consists only of fixed Stage C10 operation identities;
- no program can execute an adapter or touch the host.

## What Stage C11 does not prove

Stage C11 does not prove adapter dispatch, result handling, failure injection between operations, production lock behaviour or any real filesystem, service, mixer, loopback, DAC, ALSA or CamillaDSP behaviour.

It is immutable ordering metadata only.

## Acceptance

Stage C11 is accepted as **PASS** at the automated static-policy boundary.

No Pi command is generated. No persistent installer exists, the blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
