# Stage C16 transaction candidate staging and validation rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C16 extends the physically proved Stage C15 transaction prefix by exactly five v1 operations:

```text
stage-candidate-files
validate-candidate-alsa
validate-candidate-sudoers
validate-candidate-units
validate-candidate-camilladsp
```

It then uses the Stage C15A v2 `abort-uncommitted-transaction` lifecycle operation to retain non-authoritative evidence, remove the staged candidate and authoritative transaction, and release the production lock.

The stage ends before the first managed-audio mutation. It cannot stop Plexamp, Shairport Sync or the dashboard, cannot release the DAC, and cannot install or activate anything.

## Exact operation boundary

Stage C16 permits sixteen v2 operations:

1. inspect host contract;
2. inspect production lock;
3. acquire production lock;
4. release production lock;
5. create authoritative transaction;
6. capture filesystem state;
7. capture service state;
8. capture mixer state;
9. capture loopback state;
10. capture DAC state;
11. stage candidate files;
12. validate candidate ALSA;
13. validate candidate sudoers;
14. validate candidate units;
15. validate candidate CamillaDSP;
16. abort uncommitted transaction.

The remaining eighteen v2 operations stay blocked.

The first blocked operation is:

```text
stop-captured-application-services
```

That is the first real appliance-mutation boundary in the install program.

## Inputs

The guarded rehearsal replays:

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.*
Stage C15 result  /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.*
```

The Stage C15 input must contain the exact twenty-three PASS checks, a removed authoritative transaction, a released production lock and a non-authoritative transaction review copy.

Both input trees must remain unchanged.

## Transaction staging

After the production lock, authoritative transaction and five-domain snapshot exist, the adapter creates exactly one private candidate root beneath the transaction:

```text
<transaction>/candidate-rootfs
```

The candidate root:

- is mode `0700`, root-owned and not caller-selectable;
- remains beneath the exact transaction device/inode boundary;
- is populated only from the replayed Stage C1 `rootfs` tree;
- contains only directories and regular files;
- rejects symlinks, hard-link count changes and special objects;
- copies each file through a temporary file in the candidate destination directory;
- hashes the source before and after copy;
- verifies the staged digest, mode, owner and final manifest mapping;
- contains exactly the twelve manifest files and required directories;
- never maps to a production destination.

The original package fingerprint, manifest rows and staged tree fingerprint are recorded.

## Candidate validation

Every validator accepts only the adapter-generated transaction identity. Candidate paths are resolved internally from the bound transaction.

### ALSA

The two candidate routes are validated in isolated private ALSA roots made from `/usr/share/alsa/alsa.conf` with its global preload hook removed:

```text
split-bus.conf
direct-alarm-bypass.conf
```

`aplay -L` is run with a fixed private `ALSA_CONFIG_PATH`. No PCM is opened. Both candidates must expose:

```text
acp_dmix
acp_master
acp_plexamp
acp_airplay
acp_alarm
```

### Sudoers

The staged fixed sudoers candidate is validated with:

```text
visudo -cf <staged-candidate>
```

The binary path is discovered once from the fixed command name. The candidate path is transaction-owned and not caller-controlled.

### Systemd units and route helper

The three staged units are checked with fixed `systemd-analyze verify` arguments inside a private temporary unit search path containing only staged copies plus the host vendor unit directories required for dependency resolution.

The adapter also performs deterministic text-contract checks for:

- one route authority;
- route before CamillaDSP and source services;
- CamillaDSP requiring the route and sound target;
- CamillaDSP failure invoking the fixed failback unit;
- all three generated units retaining the absent activation-approved marker.

The staged Python route helper is compiled in memory and never executed.

### CamillaDSP

The staged, digest-pinned CamillaDSP binary validates the staged fixed configuration using:

```text
<staged-binary> --check <staged-config>
```

No audio endpoint is opened. The command is fixed and the binary/config paths are transaction-owned.

## Evidence and abort

Before cleanup, the adapter copies the complete staged candidate and validation artefacts to:

```text
<Stage C16 evidence>/candidate-review-copy
```

This review copy is explicitly non-authoritative and cannot become an installation source.

The production-shaped v2 abort method accepts only the authoritative transaction identity:

```python
abort_uncommitted_transaction(transaction)
```

Internally the adapter:

1. verifies the same held lock and transaction identity;
2. requires all five snapshot and five validation domains to be complete;
3. verifies the candidate root device/inode;
4. copies the candidate review evidence outward;
5. removes the exact candidate root;
6. invokes the physically proved Stage C15 transaction abort;
7. maps the result to the immutable Stage C15A receipt;
8. permits lock release only afterward.

## Prohibited behaviour

Stage C16 contains no path for:

- stopping, starting, restarting, enabling or disabling any service;
- `systemctl` service mutation or daemon reload;
- mixer writes;
- module loading or unloading;
- production file installation;
- active ALSA route selection;
- PCM or DAC opening;
- CamillaDSP startup;
- finite audio probes;
- commit, rollback, failback or uninstall;
- activation marker creation;
- persistent activation.

`systemd-analyze verify` is syntax/dependency validation only; it does not contact the service manager or mutate unit state.

## Expected acceptance checks

The physical rehearsal emits exactly twenty-nine PASS checks:

```text
root-scope
input-replay
protocol-conformance
pre-lock-host-contract
pre-lock-boundary
production-lock-acquired
authoritative-transaction-created
transaction-identity-binding
filesystem-snapshot
service-snapshot
mixer-snapshot
loopback-snapshot
dac-snapshot
snapshot-integrity
candidate-staging
candidate-manifest-binding
candidate-alsa-validation
candidate-sudoers-validation
candidate-unit-validation
candidate-camilladsp-validation
blocked-operation-boundary
pre-mutation-boundary
candidate-evidence-copy
transaction-abort-v2
exact-transaction-cleanup
production-lock-released
input-integrity
evidence-integrity
activation-interface
```

## Automated gate

Before a Pi command is accepted, focused tests must prove:

- exact sixteen/eighteen v2 operation partition;
- exact candidate-root confinement and inode binding;
- double-hashed atomic file staging;
- no production destination write;
- fixed read-only validator command shapes;
- no service-manager, mixer, module or audio mutation command;
- v2 abort takes only the transaction identity;
- candidate evidence is retained before exact cleanup;
- the engine cannot call blocked operations outside its blocked-proof function;
- prepare-only exits before the single constrained sudo command;
- no activation, install, rollback, failback or uninstall option exists.

Persistent Stage C activation remains blocked. The old master-EQ installer remains blocked. PR #2 remains Draft, open and unmerged.