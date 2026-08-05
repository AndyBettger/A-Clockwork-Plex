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

No program can import, construct or invoke a production adapter. No CLI, wrapper, confirmation token, root command or Pi execution path exists in Stage C11.

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
```

## Authority boundary

Stage C11 does not create another transaction engine.

The existing authorities remain:

```text
Transaction and exact rollback mechanics:
  scripts.stage_c_transaction.sandbox_transaction

Root-owned disposable filesystem mechanics:
  scripts.stage_c_transaction.root_owned_transaction

Reviewed production state-machine contract:
  scripts.stage_c_transaction.production_plan

Typed blocked host-operation vocabulary:
  scripts.stage_c_transaction.production_adapter_contract
```

Stage C11 adds only immutable policy metadata that maps a `TransactionAction` to an ordered tuple of Stage C10 `AdapterOperation` values.

The module imports no adapter protocol or implementation, carries no callback or callable, performs no dynamic dispatch and has no method capable of executing a step.

## Immutable program model

Each `OperationProgram` records:

- one `ProgramName`;
- one `TransactionAction`;
- whether the production lock is unheld or already held on entry;
- the required snapshot source;
- the failure disposition before the first mutation;
- the failure disposition after the first mutation;
- an ordered tuple of frozen `OperationStep` records.

Each step records:

- a fixed sequence number in increments of ten;
- a fixed policy phase;
- one Stage C10 `AdapterOperation` enum value;
- whether it changes managed audio state;
- whether the production lock must already be held;
- fixed explanatory text.

Import-time structural validation requires:

- strictly sequential step numbers;
- production-lock release as the final operation;
- exactly one acquisition in an unheld-entry program;
- no lock-required step before acquisition;
- every step after acquisition to require the held lock;
- no reacquisition in a held-entry program;
- every step in a held-entry program to require the existing lock.

## Exact policy mapping

The final mapping is deliberately ordered by policy role rather than by the declaration order of the `TransactionAction` enum:

```text
install                  -> install
automatic-exact-rollback -> exact-rollback
runtime-direct-failback  -> runtime-failback
explicit-uninstall       -> explicit-uninstall
```

Every `TransactionAction` appears exactly once.

## Install program

The install program contains 28 ordered operations.

Its sequence is:

```text
inspect host contract
inspect production lock
acquire production lock
create fresh authoritative transaction
capture filesystem state
capture service state
capture mixer state
capture loopback state
capture DAC state
stage candidate files
validate candidate ALSA
validate candidate sudoers
validate candidate units
validate candidate CamillaDSP
stop captured application services
verify DAC released
install managed files
reload systemd
select split-bus route
start managed Stage C services
verify split-bus health
run finite music probe
run finite alarm probe
restore captured application services
verify split-bus health again
verify dashboard health
write commit manifest
release production lock
```

The first managed-audio mutation is stopping the captured application services. Every earlier failure is classified as a pre-mutation abort. Every failure from that point until commit is classified for automatic exact rollback.

The commit manifest is written only after application-service restoration, post-start split-bus health and dashboard health have passed. The lock is released only after commit.

## Automatic exact rollback program

Automatic rollback contains nine operations and enters with the production lock already held by the failed transaction:

```text
stop captured application services
stop managed Stage C services
verify DAC released
restore exact authoritative snapshot
reload systemd
restore exact mixer state
restore exact service state
verify exact rollback
release production lock
```

It does not reacquire the lock. Both pre- and post-mutation failures inside rollback are classified `fail-closed-retain-lock`; the program cannot claim success or release the lock before exact verification.

## Runtime direct failback program

Runtime failback contains 18 operations. It acquires the same production lock, records current live service/mixer/DAC state, stops application and Stage C services, selects the physically proven direct alarm-bypass route, restores live mixer values and application services, runs finite music and alarm probes, verifies dashboard degraded-route health, records the transition and then releases the lock.

It contains:

```text
select-direct-failback-route
```

and deliberately contains neither:

```text
restore-exact-snapshot
select-split-bus-route
```

Runtime failback therefore preserves the committed installation rather than pretending to be uninstall or exact rollback.

## Explicit uninstall program

Explicit uninstall contains 17 operations. It is composed by transaction policy from small typed operations:

```text
inspect host and lock boundaries
acquire lock
create uninstall transaction record
capture current service/mixer/DAC observations
stop application services
stop managed Stage C services
verify DAC released
restore committed installation's exact pre-install snapshot
reload systemd
restore original mixer state
restore original service state
verify exact restoration
write completed uninstall record
release lock
```

`TransactionAction.EXPLICIT_UNINSTALL` remains present, but Stage C10 contains no adapter-level `explicit_uninstall()` method or `AdapterOperation.EXPLICIT_UNINSTALL`. This keeps uninstall ordering and rollback ownership under the single transaction-policy authority.

## Test correction discovered during CI

The first Stage C11 CI run reported one failure in:

```text
test_exactly_four_immutable_programs_map_each_action_once
```

The test compared the policy program order directly with the declaration order of the `TransactionAction` enum. All four actions were present exactly once and every substantive sequence test passed; only the ordering assumption was incorrect.

The test was corrected to assert the exact intended name-to-action mapping shown above and separately prove complete set coverage. No production-operation program or runtime module changed as part of this correction.

This retained the useful policy order—install beside its automatic rollback—without assigning accidental meaning to enum declaration order.

## Focused safety coverage

The 11 Stage C11 tests prove that:

1. the module is static metadata with no execution or entrypoint imports;
2. exactly four immutable programs map every action once;
3. every step uses only a valid Stage C10 operation enum;
4. unheld programs acquire the lock before identity, snapshot or mutation;
5. install matches the reviewed order and first-mutation boundary;
6. install commits only after post-start and dashboard health;
7. automatic rollback retains the existing lock and verifies before release;
8. runtime failback is alarm-safe and never performs uninstall restoration;
9. explicit uninstall is composed policy rather than an adapter shortcut;
10. the static program snapshot is complete;
11. structural guards reject unsafe lock and sequence shapes.

## Full CI result

The corrected Stage C11 branch passed the complete suite:

```text
Ran 612 tests in 3.885s
OK
```

All Stage C10 and Stage C11 focused tests passed. The Stage C7 disposable-root transaction and consolidated Stage C4 sandbox transaction also completed successfully during the same run with exact rollback and no production writes.

## What Stage C11 proves

Stage C11 proves that:

- install, automatic rollback, runtime failback and explicit uninstall have one explicit policy-owned order;
- the production lock boundary is encoded consistently across all four programs;
- rollback retains rather than reacquires the failed transaction's lock;
- runtime failback remains distinct from uninstall and exact rollback;
- explicit uninstall cannot be delegated to a broad adapter shortcut;
- every program consists only of fixed Stage C10 operation identities;
- no program can execute an adapter or touch the host.

## What Stage C11 does not prove

Stage C11 does not prove:

- adapter dispatch;
- operation result handling;
- failure injection between production operations;
- production lock behaviour;
- authoritative snapshot creation;
- service, mixer, loopback, DAC, ALSA or CamillaDSP behaviour;
- real rollback, failback or uninstall.

It is immutable ordering metadata only.

## Acceptance

Stage C11 is accepted as **PASS** at the automated static-policy boundary.

No Pi command is generated. No persistent installer exists, the blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
