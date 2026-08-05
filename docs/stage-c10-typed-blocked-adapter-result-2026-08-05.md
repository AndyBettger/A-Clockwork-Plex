# Stage C10 typed blocked production-adapter contract — result

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Result

**PASS — automated contract review.**

Stage C10 introduces a typed production-adapter contract while deliberately providing no production adapter implementation, CLI, wrapper, confirmation token or host mutation entrypoint.

The contract is defined in:

```text
scripts/stage_c_transaction/production_adapter_contract.py
```

The focused safety coverage is defined in:

```text
tests/test_stage_c_production_adapter_contract_safety.py
```

No physical Pi execution is required or appropriate for this stage. The absence of an executable host boundary is part of the acceptance contract.

Persistent Stage C activation remains blocked.

## Commits

The contract was developed and corrected through these commits:

```text
fd0d0376abd900ffb1e7268240a8b6a5284be9ae
  Add Stage C10 typed blocked adapter contract

bedcac51d4c5eeaa490a5f3ef49d81d234ddd9ac
  Test Stage C10 blocked adapter contract

f9be4a88a27698aaef94e388548fa281f78ede62
  Add blocked Stage C service stop operation

fa0d5d3e02777b3c1553e6394664ed0a56f917b5
  Cover blocked Stage C service stop operation

b503b60b21242a84dd6768b9fe7405cd2d7e5867
  Keep uninstall orchestration out of the adapter

8974aefa1d36886952265daa785e31b0004dc83e
  Keep uninstall under transaction policy
```

## Fixed production boundaries

The contract fixes the only future production lock path:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

and the only future authoritative transaction root:

```text
/var/lib/a-clockwork-plex/split-bus/transactions
```

Neither path is opened, inspected or written by Stage C10.

The six fixed service units are:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

The four fixed mixer controls are:

```text
Plexamp Output
AirPlay Output
Music Master
Maximum Alarm Volume
```

The loopback contract is fixed to:

```text
module: snd_aloop
card index: 7
card id: ACP_Loopback
pcm_substreams: 2
pcm_notify: 1
```

The DAC contract is fixed to:

```text
format: S16_LE
channels: 2
rate: 44100
period_size: 1024
buffer_size: 8192
```

None of these names, paths or values may be supplied by a caller through the Stage C10 public contract.

## Typed operation vocabulary

The `ProductionAdapter` protocol exposes exactly 33 named host operations:

- 17 observation or validation operations;
- 16 potentially state-changing operations.

Each operation has its own named method. There is no generic `execute`, `run`, `command`, `argv`, `shell` or arbitrary dispatch interface.

The operation vocabulary covers:

- host and production-lock inspection;
- production-lock acquisition and release;
- authoritative transaction creation;
- filesystem, service, mixer, loopback and DAC capture;
- candidate staging and validation;
- captured application-service stop and restoration;
- managed Stage C service start and stop;
- DAC release verification;
- managed-file installation;
- systemd reload;
- split-bus and direct-failback route selection;
- split-bus health and finite lane probes;
- dashboard health;
- commit-manifest writing;
- exact snapshot, mixer and service restoration;
- exact rollback verification.

The interface uses frozen records and enums for package fingerprints, transaction and snapshot identities, service units and states, mixer state, routes and transaction actions.

Mixer snapshot values are bounded to integer percentages from 0 through 100.

## Contract corrections discovered before implementation

### Managed Stage C service shutdown

The first vocabulary contained `start_managed_stage_c_services()` but lacked the matching typed stop operation required by rollback and runtime failback preparation.

The correction added:

```text
stop_managed_stage_c_services()
```

as a distinct potentially mutating operation. It remains fully blocked and has no service-manager implementation.

### Explicit uninstall ownership

The first vocabulary also exposed `explicit_uninstall()` as an adapter method. Binding the vocabulary against the reviewed transaction design showed that this would be too broad: uninstall is an ordered transaction-policy action, not one host operation.

The final contract therefore keeps:

```text
TransactionAction.EXPLICIT_UNINSTALL
```

but contains no:

```text
AdapterOperation.EXPLICIT_UNINSTALL
explicit_uninstall()
```

A future explicit uninstall must be composed by the single transaction-policy authority from fixed operations such as lock acquisition, service stopping, exact snapshot restoration, systemd reload, mixer and service restoration, exact verification and lock release.

This prevents the adapter from becoming a second transaction or rollback authority.

These corrections demonstrate the intended value of a blocked contract stage: operation-level gaps and over-broad responsibilities are found while they are still names and tests rather than privileged behaviour.

## Deliberately blocked implementation

`BlockedProductionAdapter` implements the complete protocol but refuses every operation, including read-only inspection methods.

Every method raises:

```text
ProductionAdapterBlocked
```

The exception records the exact `AdapterOperation` that was refused. Merely importing or constructing the Stage C10 adapter therefore cannot inspect or alter the host.

The only successful function is `contract_snapshot()`. It returns static in-memory contract metadata and explicitly records:

```text
status: blocked
activation_interface: absent
```

It performs no filesystem, process, service, mixer, module, PCM, DAC, network or lock access.

## Safety tests

The 11 focused Stage C10 tests prove that:

1. the module imports no host-execution or entrypoint libraries;
2. no CLI, `main()`, confirmation token or shell execution path exists;
3. no generic command or dispatch escape hatch exists;
4. production paths are fixed constants with no caller override fields;
5. service and mixer boundaries are exact enums;
6. loopback and DAC contracts match physical discovery;
7. all 33 host operations are partitioned exactly once;
8. the protocol and blocked implementation expose the same 33 public methods;
9. every typed method fails closed with its exact operation identity;
10. contract records are frozen and mixer values are bounded;
11. public adapter methods accept no raw command, argument-vector, path, root, unit-name or control-name parameter.

The tests additionally require `TransactionAction.EXPLICIT_UNINSTALL` to remain available while proving that no adapter-level `explicit_uninstall()` method exists.

## CI state

The first complete Stage C10 version passed:

```text
Ran 601 tests in 3.236s
OK
```

Final acceptance requires the same complete branch suite to pass after the service-stop addition and removal of adapter-owned uninstall orchestration.

The existing Stage C7 disposable-root transaction and consolidated Stage C4 sandbox transaction also execute during CI, preserving their exact rollback and production-boundary contracts.

## What Stage C10 proves

Stage C10 proves that:

- the future host-operation boundary has one explicit typed vocabulary;
- caller-supplied commands and production destinations are absent;
- service, mixer, loopback and DAC scope is fixed;
- transaction actions are enumerated;
- both managed-service startup and shutdown are represented explicitly;
- explicit uninstall remains owned by transaction policy rather than the adapter;
- the placeholder implementation cannot inspect or mutate the host;
- no production activation or installation entrypoint exists;
- later adapter work can be tested against one stable protocol rather than scattering host calls through transaction policy.

## What Stage C10 does not prove

Stage C10 does not prove:

- production lock behaviour;
- authoritative snapshot creation;
- real filesystem installation;
- service-manager behaviour;
- mixer restoration;
- loopback loading or persistence;
- DAC release or ownership;
- ALSA parsing or finite PCM probes;
- CamillaDSP startup or health;
- direct failback;
- exact production rollback or uninstall.

Those methods are names and types only. Every attempted host operation remains blocked.

## Acceptance

Stage C10 is accepted as **PASS** at the automated contract boundary once the final 33-operation branch run is green.

No Pi command is generated for this stage. No persistent installer exists, the blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
