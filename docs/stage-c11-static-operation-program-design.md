# Stage C11 static transaction-policy operation programs

Status: design and static binding only. No adapter execution, production lock acquisition, root entrypoint, confirmation token or production mutation interface exists in this stage.

## Purpose

Stage C10 fixed a typed vocabulary of 33 host operations while deliberately blocking every operation. It also established an important authority boundary:

- the adapter supplies small fixed host operations;
- transaction policy owns ordering, failure response, rollback, runtime failback and explicit uninstall;
- explicit uninstall remains a `TransactionAction` and is not an adapter method.

Stage C11 binds the reviewed Stage C5 transaction state machine and Stage C9/C10 adapter boundary into four immutable operation programs:

1. install;
2. automatic exact rollback;
3. runtime direct alarm-bypass failback;
4. explicit uninstall.

The programs contain operation identities and ordering metadata only. They do not hold an adapter object and cannot invoke a method, command, service, filesystem path, PCM or device.

Persistent Stage C activation remains blocked.

## Authority boundary

Stage C11 must not create another transaction engine.

The surviving authorities remain:

```text
Transaction and exact rollback mechanics:
  scripts.stage_c_transaction.sandbox_transaction

Root-owned disposable filesystem mechanics:
  scripts.stage_c_transaction.root_owned_transaction

Reviewed production state machine:
  scripts.stage_c_transaction.production_plan

Typed blocked host-operation vocabulary:
  scripts.stage_c_transaction.production_adapter_contract
```

Stage C11 adds only a static mapping from transaction-policy actions to ordered `AdapterOperation` values.

## Program model

Each immutable program records:

- one `TransactionAction`;
- whether the production route lock is unheld or already held on entry;
- the required snapshot source;
- the failure disposition before the first production mutation;
- the failure disposition after the first production mutation;
- an ordered tuple of typed operation steps.

Each step records:

- a fixed sequence number;
- a policy phase;
- one `AdapterOperation` enum value;
- whether the step changes production state;
- whether the production lock must already be held;
- a fixed explanatory detail.

There is no generic operation name, command string, argument vector, executable path, unit name, mixer control name or filesystem destination in a program.

## Install program

The install program must preserve the reviewed Stage C5 ordering:

1. inspect the exact host contract;
2. inspect the production lock boundary;
3. acquire the single production route lock;
4. create a fresh authoritative transaction identity;
5. capture filesystem, service, mixer, loopback and DAC state;
6. stage candidate files;
7. validate candidate ALSA, sudoers, units and CamillaDSP configuration;
8. stop only application services captured active;
9. verify the DAC is released;
10. install managed files atomically;
11. reload systemd;
12. select the split-bus route;
13. start managed Stage C services;
14. verify split-bus health;
15. run finite music and alarm lane probes;
16. restore only application services captured active;
17. re-verify split-bus health after application startup;
18. verify dashboard health agreement;
19. write the committed transaction manifest;
20. release the production route lock.

The first production mutation is stopping captured application services. Any earlier failure is a pre-mutation abort. Any failure from that point until commit invokes the automatic exact rollback program while retaining the same lock.

## Automatic exact rollback program

Automatic rollback begins with the production route lock already held by the failed transaction. It must not reacquire or replace the lock.

The ordered program is:

1. stop captured application services, including a case where they had already been restored before a late validation failure;
2. stop managed Stage C services;
3. verify the DAC and relevant endpoints are released;
4. restore the exact authoritative filesystem snapshot and absence markers;
5. reload systemd;
6. restore the exact mixer snapshot;
7. restore the exact service snapshot;
8. verify exact rollback with zero mismatches;
9. release the route lock.

A rollback failure does not switch to another rollback implementation. It fails closed and must not claim success or release the lock before exact verification.

## Runtime failback program

Runtime failback is distinct from exact rollback and explicit uninstall. It preserves the committed Stage C installation while selecting the physically proven direct no-DSP alarm-bypass route.

The ordered program is:

1. inspect the exact host and lock boundaries;
2. acquire the same production route lock;
3. create a fresh runtime-failback transaction record;
4. capture current service, mixer and DAC state;
5. stop captured application services;
6. stop managed Stage C services, including any surviving CamillaDSP service/process through the future fixed adapter;
7. verify the DAC is released;
8. select the direct alarm-bypass route;
9. restore the captured live mixer state;
10. restore only application services captured active;
11. run finite music and alarm probes against the direct route;
12. verify dashboard degraded-route health agreement;
13. write the completed failback transaction record;
14. release the route lock.

Runtime failback must not call `restore_exact_snapshot()` and must not remove the committed installation.

## Explicit uninstall program

Explicit uninstall remains transaction policy. There is no adapter-level `explicit_uninstall()` operation.

The ordered program is:

1. inspect the exact host and lock boundaries;
2. acquire the production route lock;
3. create a fresh explicit-uninstall transaction record bound to the committed installation snapshot;
4. capture current service, mixer and DAC observations for audit;
5. stop captured application services;
6. stop managed Stage C services;
7. verify the DAC is released;
8. restore the committed installation's exact authoritative snapshot and absence markers;
9. reload systemd;
10. restore the original pre-install mixer state;
11. restore the original pre-install service state;
12. verify exact restoration with zero mismatches;
13. write the completed uninstall transaction record;
14. release the route lock.

The uninstall program is therefore composed from small typed operations and cannot be delegated to a second orchestration authority.

## Static safety boundary

Stage C11 must not:

- import or construct `ProductionAdapter` or `BlockedProductionAdapter`;
- invoke any adapter method;
- use `getattr`, callbacks, callables or dynamic dispatch;
- import subprocess, shell, filesystem, lock, network, service or audio libraries;
- expose a CLI, wrapper, `main()` or confirmation token;
- open the production lock;
- create a transaction directory;
- write `/run`, `/etc`, `/usr/local` or `/var/lib`;
- execute service, mixer, module, ALSA, CamillaDSP or dashboard operations;
- create an activation or approval marker;
- provide install, rollback, failback or uninstall execution.

The only permitted behaviour is returning immutable in-memory program metadata.

## Acceptance

Stage C11 passes when automated tests prove that:

- exactly four immutable programs exist;
- each maps to one distinct `TransactionAction`;
- every step uses a valid Stage C10 `AdapterOperation`;
- all unheld-entry programs acquire the fixed lock before transaction identity, snapshot or mutation;
- install snapshots and validates before its first production mutation;
- install commits before releasing the lock;
- rollback starts with the lock held, does not reacquire it and releases only after exact verification;
- runtime failback selects the direct alarm-bypass route and never restores the uninstall snapshot;
- explicit uninstall has no adapter shortcut and composes exact restoration operations;
- no program can execute an adapter or host command;
- no Pi command is generated;
- persistent activation remains blocked.
