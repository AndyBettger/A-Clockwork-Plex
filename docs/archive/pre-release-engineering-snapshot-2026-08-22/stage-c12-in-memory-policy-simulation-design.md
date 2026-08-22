# Stage C12 typed adapter results and in-memory policy simulation

Status: in-memory simulation only. No production adapter, root entrypoint, confirmation token, production lock acquisition, filesystem mutation, service command or audio access exists in this stage.

## Purpose

Stage C10 defined 33 fixed adapter operations and blocked every operation. Stage C11 bound install, automatic exact rollback, runtime direct failback and explicit uninstall to immutable ordered operation programs.

Attempting to design an in-memory runner exposed a typed-result gap in the Stage C10 protocol: every method returned a generic `AdapterResult`, while later policy steps require concrete values produced by earlier operations, including:

- a generated transaction identity;
- the authoritative snapshot identity;
- captured service state;
- captured mixer state;
- captured loopback state;
- structured DAC state;
- a held production-lock lease.

A runner must not recover those values by parsing human-readable `detail` or string evidence.

Stage C12 therefore has two linked objectives:

1. refine the adapter contract with typed immutable result payloads;
2. execute the four Stage C11 programs only against an in-memory recording adapter with deterministic failure injection.

Persistent Stage C activation remains blocked.

## Typed result boundary

`AdapterResult` becomes a generic frozen record:

```text
AdapterResult[T]
```

It retains:

- exact `AdapterOperation` identity;
- `PASS`, `FAIL` or `BLOCKED` status;
- human-readable detail;
- immutable structured evidence;
- a typed payload `T | None`.

The protocol returns specific payload types rather than forcing policy to interpret strings.

### Observation payloads

The required immutable payloads are:

```text
HostContractSnapshot
ProductionLockObservation
ProductionLockLease
AuthoritativeTransaction
FilesystemSnapshot
ServiceSnapshot
MixerSnapshot
LoopbackSnapshot
DacSnapshot
```

`AuthoritativeTransaction` contains both the generated `TransactionIdentity` and its generated `SnapshotIdentity`, bound to one `TransactionAction` and package fingerprint.

### Receipt-only operations

Validation and mutation methods that do not produce later policy input return:

```text
AdapterResult[None]
```

Their status and evidence remain structured, but no invented payload is required.

### Fail-closed payload rules

A successful operation that promises a typed payload must provide one. A failed or blocked result must not provide a success payload.

The in-memory simulation tests must reject:

- a passing transaction-creation result without an `AuthoritativeTransaction`;
- a passing capture result with the wrong payload type;
- a failed result that carries a misleading success payload;
- transaction or snapshot identities supplied by the caller rather than produced by the adapter result.

## In-memory recording adapter

Stage C12 adds one adapter implementation that is deliberately not a production adapter:

```text
RecordingProductionAdapter
```

It:

- imports no filesystem, process, shell, service, lock, network or audio library;
- never opens the real production lock path;
- creates only deterministic in-memory identities and snapshots;
- records every typed operation in order;
- models lock-held state as a Boolean in memory;
- returns fixed synthetic host, service, mixer, loopback and DAC payloads;
- can fail one exact operation occurrence for deterministic policy testing;
- cannot be selected by a CLI or production entrypoint.

The class exists only in the Stage C transaction package and automated tests. It must be named and documented as simulation-only.

## Explicit operation dispatch

The policy simulator must not use `getattr`, caller-supplied method names, callbacks or a generic command runner.

Each of the 33 `AdapterOperation` values is dispatched through one explicit `match` branch to the corresponding typed adapter method.

The dispatcher may pass only values already present in the immutable simulation context:

- package fingerprint;
- transaction action;
- adapter-generated transaction and snapshot identities;
- captured service snapshot;
- captured mixer snapshot.

No raw command, path, unit name or mixer control name belongs to the runner.

## Simulation state

The runner maintains an immutable or tightly validated in-memory context containing:

- selected Stage C11 program;
- package fingerprint;
- current transaction record, when created;
- captured service and mixer snapshots, when available;
- whether the simulated production lock is held;
- whether managed-audio mutation has begun;
- whether terminal success has occurred;
- ordered operation results;
- selected failure disposition;
- optional automatic rollback result.

The runner must not fabricate required context. An operation that needs a transaction, snapshot, service snapshot or mixer snapshot before it has been produced fails the simulation contract.

## Success simulations

The simulator must prove successful ordered execution for:

1. install;
2. automatic exact rollback entered with a simulated held lock and authoritative transaction context;
3. runtime direct failback;
4. explicit uninstall.

The recorded operations must match each Stage C11 program exactly.

## Install failure simulations

Install receives the most detailed failure testing.

### Before lock acquisition

A failure in host or lock inspection records no release attempt because no lock was acquired.

### After lock acquisition but before managed-audio mutation

A failure during transaction creation, capture, staging or candidate validation uses `abort-release-lock`. The simulator performs only the fixed lock-release cleanup when the lock was acquired. It must not invoke automatic rollback.

### After managed-audio mutation but before commit

A failure from `stop-captured-application-services` through pre-commit health verification switches to the Stage C11 automatic exact rollback program while retaining the same simulated lock.

The rollback recording must begin with:

```text
stop-captured-application-services
```

and must not reacquire the lock.

### At commit

Failure of `write-commit-manifest` occurs before terminal success and therefore invokes automatic exact rollback.

### After commit

Failure of `release-production-lock` occurs after terminal success. It must produce `fail-closed-retain-lock`, must not invoke automatic rollback and must leave the simulated lock marked held.

This is the commit-boundary distinction added to Stage C11 before Stage C12 implementation.

## Rollback failure simulation

A failure at any automatic rollback operation must:

- record `fail-closed-retain-lock`;
- stop executing rollback immediately;
- retain the simulated lock;
- report no exact rollback success;
- never invoke another rollback implementation.

A failure of lock release after successful exact rollback is also fail-closed and must not repeat restoration.

## Runtime failback and uninstall failures

Runtime failback and explicit uninstall must use their Stage C11 failure dispositions:

- pre-mutation abort with lock release when safe;
- fail-closed/retain-lock after managed-audio mutation;
- fail-closed/retain-lock after terminal success;
- no automatic exact rollback substitution.

This preserves the reviewed distinction between installation rollback, runtime failback and explicit uninstall.

## Safety boundary

Stage C12 must not:

- import `os`, `pathlib`, `fcntl`, `subprocess`, `shutil`, `socket`, `requests` or `urllib` in the simulator;
- read or write any file;
- open or inspect `/run/lock/a-clockwork-plex-audio-route.lock`;
- create `/var/lib/a-clockwork-plex/split-bus/transactions`;
- execute systemd, mixer, module, ALSA, CamillaDSP or dashboard operations;
- expose a CLI, wrapper, `main()` or confirmation token;
- use dynamic method lookup;
- accept a caller-supplied transaction or snapshot identity for a normal unheld-entry program;
- provide persistent install, rollback, failback or uninstall execution.

No Pi command is generated.

## Acceptance

Stage C12 passes when automated tests prove that:

- typed adapter payloads are immutable and correctly bound to method signatures;
- the recording adapter satisfies the typed protocol without host imports;
- all 33 operations have one explicit dispatch branch;
- successful recordings exactly match all four Stage C11 programs;
- pre-lock failure does not release an unheld lock;
- pre-mutation failure after acquisition releases without rollback;
- post-mutation and pre-commit install failure invokes the exact rollback program without reacquiring the lock;
- commit failure invokes rollback;
- release failure after terminal success never invokes rollback;
- rollback failure retains the lock and never nests rollback;
- failback and uninstall never borrow install's automatic rollback policy;
- no host, filesystem, service or audio access exists;
- the complete branch suite remains green;
- persistent activation remains blocked.
