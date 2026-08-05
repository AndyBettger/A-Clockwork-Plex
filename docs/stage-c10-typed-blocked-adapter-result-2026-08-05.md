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

```text
fd0d0376abd900ffb1e7268240a8b6a5284be9ae
  Add Stage C10 typed blocked adapter contract

bedcac51d4c5eeaa490a5f3ef49d81d234ddd9ac
  Test Stage C10 blocked adapter contract
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

The `ProductionAdapter` protocol exposes exactly 33 named operations:

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
- DAC release verification;
- managed-file installation;
- systemd reload;
- split-bus and direct-failback route selection;
- managed Stage C service startup;
- split-bus health and finite lane probes;
- dashboard health;
- commit-manifest writing;
- exact snapshot, mixer and service restoration;
- exact rollback verification;
- explicit uninstall.

The interface uses frozen records and enums for package fingerprints, transaction and snapshot identities, service units and states, mixer state, routes and transaction actions.

Mixer snapshot values are bounded to integer percentages from 0 through 100.

## Deliberately blocked implementation

`BlockedProductionAdapter` implements the complete protocol but refuses every operation, including read-only inspection methods.

Every method raises:

```text
ProductionAdapterBlocked
```

The exception records the exact `AdapterOperation` that was refused. This proves that merely importing or constructing the Stage C10 adapter cannot inspect or alter the host.

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
7. all 33 operations are partitioned exactly once;
8. the protocol and blocked implementation expose the same 33 public methods;
9. every typed method fails closed with its exact operation identity;
10. contract records are frozen and mixer values are bounded;
11. public adapter methods accept no raw command, argument-vector, path, root, unit-name or control-name parameter.

## Full CI result

The complete branch suite passed:

```text
Ran 601 tests in 3.236s
OK
```

The existing Stage C7 disposable-root transaction and consolidated Stage C4 sandbox transaction also completed successfully during CI, preserving their exact rollback and production-boundary contracts.

## What Stage C10 proves

Stage C10 proves that:

- the future host-operation boundary has one explicit typed vocabulary;
- caller-supplied commands and production destinations are absent;
- service, mixer, loopback and DAC scope is fixed;
- transaction actions are enumerated;
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

Those methods are names and types only. Every attempted call remains blocked.

## Acceptance

Stage C10 is accepted as **PASS** at the automated contract boundary.

No Pi command is generated for this stage. No persistent installer exists, the blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
