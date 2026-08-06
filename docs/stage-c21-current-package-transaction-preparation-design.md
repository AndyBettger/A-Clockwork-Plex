# Stage C21 current-package pre-mutation transaction preparation — design

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Status: implementation and automated tests may proceed; Pi execution remains blocked

## Purpose

The target-side Stage C21 baseline has now been observed and accepted. The current activation-capable package v2 contains 28 regular files, 27 fingerprinted payload files and the complete guarded runtime-authority package. The next bounded checkpoint is to prove that this exact current package can enter the existing production transaction prefix, be captured and validated only beneath a fresh authoritative transaction, and then be removed by exact pre-mutation abort.

This is a direct current-package replacement for the physically proved Stage C16 shape. It is not a new activation architecture and it must reuse the existing canonical production-lock and authoritative-transaction owner lineage.

The checkpoint ends before:

```text
stop-captured-application-services
```

That remains the first appliance/audio mutation boundary.

## Accepted target inputs

The rehearsal accepts exactly two review inputs.

### Current package v2

The supplied package root must be a direct real mode-0700 directory beneath `/var/tmp` and contain:

```text
rootfs/
manifest.tsv
results.tsv
report.txt
package-contract evidence inside rootfs
```

It must independently prove:

```text
package version                     2
package phase                       activation-capable-runtime-authority-v2
regular package files               28
fingerprinted payload files         27
package fingerprint                 dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5
CamillaDSP SHA-256                  e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

The fingerprint is derived from the canonical ordered `files` array inside:

```text
/usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json
```

It is not the historical whole-evidence-tree digest used by Stage C1.

### Accepted production baseline

The baseline root must be the fixed completed evidence bundle:

```text
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
```

or a byte-identical separately reviewed copy beneath the same fixed prefix. It must contain exactly:

```text
report.txt
report.json
manifest.json
```

The manifest must prove `complete: true`, `disposition: baseline-ready`, the exact package fingerprint and the exact report hashes. The report must preserve:

- production lock absent;
- activation approval absent;
- the three existing application services loaded, active and enabled;
- all three Stage C services not found and inactive;
- mixer values `94 / 100 / 100 / 100` for the current canonical controls;
- loaded `snd_aloop` card 7 / `ACP_Loopback`, two substreams, `pcm_notify=1`;
- the fixed S16_LE, two-channel, 44100 Hz, period-1024, buffer-8192 DAC contract;
- one existing Plexamp Node DAC owner;
- every authority flag false.

The accepted evidence is a precondition and review identity only. It is never copied into the authoritative transaction as rollback data. The rehearsal captures a fresh live authoritative snapshot after acquiring the production lock.

## Reused authority lineage

The implementation must reuse the existing physically proved chain:

```text
ReadOnlyHostProductionAdapter
→ ProductionLockRehearsalAdapter
→ AuthoritativeSnapshotRehearsalAdapter
→ CandidateValidationRehearsalAdapter mechanics
```

It must not:

- create another lock class or lock path;
- independently reconstruct transaction authority;
- use an approval adapter;
- add another generic production adapter;
- copy the old Stage C1 transaction engine into a parallel implementation.

The existing classes may be narrowly parameterised so the historical Stage C1 tests retain their exact defaults while the new current-package adapter supplies a different immutable package contract.

## Exact operation boundary

The permitted pre-mutation operation set remains the same fifteen ordinary operations plus the typed v2 abort:

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
14. validate candidate units and runtime package;
15. validate candidate CamillaDSP;
16. abort uncommitted transaction.

Every later ordinary operation remains blocked. All four Stage C21 production approval operations also remain blocked and are never composed into this rehearsal.

## Minimal refactor boundary

Historical Stage C1 and Stage C16 behaviour must remain the default. The shared parser/adapter may gain immutable constructor policy only for:

- package label;
- expected regular file count;
- package validator;
- transaction-bound package fingerprint builder;
- transaction fingerprint evidence label;
- staged unit/runtime contract validator.

No caller-supplied callable, file count, label or validator is exposed through a CLI. The new fixed current-package adapter chooses those values internally.

The existing Stage C16 wrapper and tests must continue to prove the original 12-file inert candidate without modification to their public interface.

## Current-package manifest contract

The current manifest uses the same fixed columns:

```text
type	destination	mode	owner	sha256
```

The parser must require:

- absolute canonical destinations;
- no `..`, duplicate path or root destination;
- only directories and regular files;
- no symlink, special object, Python cache or hard-linked file;
- exact rootfs object type, mode and SHA-256;
- owner text exactly `root:root`;
- exactly 28 file rows;
- required empty state directory `/var/lib/a-clockwork-plex/split-bus` mode `0755`;
- no caller-selected destination.

The staged candidate must reproduce every manifest directory and all 28 files beneath:

```text
<authoritative transaction>/candidate-rootfs
```

with root ownership, exact modes, single-link regular files and exact digests.

## Current package fingerprint binding

The package validator must read the staged/replayed package contract and require:

```text
schema_version: 1
package_phase: activation-capable-runtime-authority-v2
host_mutation_available: true
files: exactly 27 canonical payload rows
package_fingerprint: exact SHA-256 of those rows
```

Every contract path and digest must match the corresponding package rootfs file. The contract file itself is the 28th package file and is excluded from its own payload fingerprint.

The authoritative transaction identity is bound to the accepted package-contract fingerprint:

```text
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5
```

It must not substitute a whole-evidence-tree fingerprint as the transaction package identity.

## Fresh authoritative snapshot

After exact baseline replay and live pre-lock inspection, the adapter acquires:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

and creates one fresh transaction beneath:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<generated-id>
```

The fresh snapshot captures:

1. current ALSA and every managed package destination;
2. all six service states;
3. the four canonical mixer controls;
4. the exact loopback state;
5. the exact DAC contract and owners.

The snapshot must accept the baseline state in which the three application services are active, the Stage C services are absent and Plexamp owns the DAC. It must require every current package file destination to be absent. Existing real parent directories are captured rather than treated as package-file conflicts.

Any difference from the accepted baseline is a hard pre-mutation failure. Cleanup may abort the newly created transaction and release the lock, but no later operation may run.

## Candidate staging

Staging uses the existing transaction-confined atomic copy mechanics:

- source hashed before and after copy;
- new destination created through an exclusive no-follow temporary file;
- exact mode and root ownership applied;
- file and directory identities constrained beneath the authoritative transaction;
- staged digest compared with the manifest;
- complete regular-tree validation;
- no production destination write;
- no rename or link crossing the transaction boundary.

The staged tree inventory must record exactly 28 files.

## Candidate validation

### ALSA

The staged split and direct route files are parsed through private ALSA roots using fixed `aplay -L`. No PCM is opened. Both must expose the five reviewed public PCMs.

### Sudoers

The staged fixed sudoers file is checked with fixed `visudo -cf`. The current rules must expose only the reviewed read-only status/validation actions to the project user and must not expose approval publication, promotion, installation or activation.

### Units and runtime package

The current three units must pass private `systemd-analyze verify` after execution lines are rewritten only in the disposable validation copies. The staged originals must retain the exact current readiness contract:

```text
route unit:      boot-prepare
CamillaDSP unit: Type=notify / NotifyAccess=main / supervise
failback unit:   emergency-direct-failback
applications:    ordered after the route and supervisor
```

The old Stage C1 requirements for `boot-select`, `activate-direct-failback`, an inert helper and exit 78 are explicitly obsolete for this package and must not be reused.

The route helper and all 15 runtime-authority Python modules must compile in memory. The package must not contain `recording_runtime_adapter.py`, `__pycache__`, `.pyc`, a symlink or a special object.

The fixed installed entrypoint must preserve exactly seven public action identities:

```text
status
validate-runtime
accept-install-handoff
promote-committed-approval
boot-prepare
supervise
emergency-direct-failback
```

Transaction-only approval publication/removal must remain unexposed through the service helper.

### CamillaDSP

The staged digest-pinned binary runs only:

```text
<staged binary> --check <staged configuration>
```

No audio endpoint is opened.

## Baseline re-verification

The root rehearsal must perform a fresh fixed read-only host observation before lock acquisition and compare it with the accepted baseline contract. After snapshot capture it must compare the typed snapshot to the same accepted state.

At minimum it must prove:

- production lock begins absent;
- approval remains absent;
- service states remain exact;
- mixer values remain exact;
- loopback contract remains exact and loaded;
- DAC contract remains exact;
- the live DAC remains owned by at least one complete structured owner;
- no Stage C service became installed between baseline acceptance and rehearsal.

PID identity may change; the required owner contract is user `andy`, command `node`, read-write access and at least one owner. The accepted baseline PID is evidence, not a persistent identity.

## Evidence and exact abort

Before cleanup, the implementation retains non-authoritative copies of:

```text
candidate-rootfs/
candidate-validation/
transaction-rehearsal-copy/
```

The evidence records:

- accepted baseline manifest and report digests;
- current package contract and fingerprint;
- exact generated lock lease, transaction and snapshot identities;
- all typed observations;
- all 28 staged paths and digests;
- each fixed validation command and result;
- every blocked ordinary and approval operation;
- explicit `mutation_started=false` and `committed=false`.

The v2 abort then:

1. verifies the same transaction and lock identity;
2. requires all five snapshot and four validation domains complete;
3. retains the non-authoritative evidence;
4. removes the exact staged candidate and validation roots;
5. aborts and removes the authoritative transaction;
6. restores only transaction-parent state created by this invocation;
7. releases and removes the exact production lock.

The evidence copies must never become an installation or rollback source.

## Failure ownership

Any failure before lock acquisition leaves the appliance untouched.

Any failure after lock acquisition but before transaction creation releases only the exact newly acquired lock.

Any failure after transaction creation must attempt only the existing exact pre-mutation abort. If exact identity or cleanup cannot be proved, the lock is retained and the failure evidence identifies manual reconciliation as required.

There is no automatic service, route, mixer, module, PCM, approval or installation recovery because none of those mutations is permitted to begin.

## Fixed wrapper

A new fixed wrapper may expose only:

```text
prepare-only default
--rehearse-current-package
--confirm <one exact token>
--package-root <direct /var/tmp current package>
--baseline-root <direct /var/tmp completed baseline bundle>
--evidence-root <fresh direct /var/tmp evidence directory>
```

The wrapper may invoke one constrained `sudo env ... python3 -m ...` command only in the guarded rehearsal mode. It exposes no package destination, transaction ID, lock path, service, route, mixer, approval bytes, activation token or arbitrary command.

The explicit token authorises only this pre-mutation create/capture/stage/validate/abort rehearsal. It is not installation or activation approval.

## Automated acceptance gate

Before another Pi command is requested, tests must prove:

- historical Stage C1/Stage C16 defaults remain exact;
- exact 28-file and 27-payload package contract;
- exact accepted package fingerprint binding;
- exact baseline-manifest replay and report hash checks;
- exact canonical service, mixer, loopback and DAC baseline comparison;
- PID-flexible but owner-contract-strict DAC comparison;
- the same 15 ordinary plus one v2-abort operation boundary;
- all remaining ordinary operations blocked;
- all four production approval operations blocked;
- transaction-confined 28-file staging;
- package-contract path/digest replay;
- current unit/readiness/runtime-entry contract;
- compile-in-memory coverage for all 16 Python candidates including the route helper;
- fixed read-only command shapes;
- no service manager mutation, mixer write, module mutation, route selection or audio open;
- exact abort and lock release ordering;
- no production destination write;
- no use or reference to `scripts/install-master-eq.sh`;
- no activation or installation mode;
- full repository test suite and GitHub Actions success.

## Roadmap

### Done

- C20 physical mandatory-rollback route checkpoint;
- current Stage C21 package v2 validation;
- target-side read-only baseline observation;
- accepted baseline evidence and package fingerprint;
- historical Stage C16 pre-mutation mechanics;
- this current-package replacement design.

### Current

Implement the narrow shared-package parameterisation, fixed current-package adapter/rehearsal, wrapper and automated tests.

### Next

After tests and GitHub Actions pass, request one explicit Pi approval for the bounded current-package pre-mutation rehearsal.

That approval will cover only:

```text
acquire canonical lock
→ create fresh authoritative transaction
→ capture fresh snapshot
→ stage and validate current package inside transaction
→ retain review evidence
→ exact abort
→ release lock
```

It will not cover service stop, DAC release, installation, route selection, approval publication, CamillaDSP startup, physical audio probes or activation.

### Risks and gates

- the current package has not yet entered a production-shaped authoritative transaction;
- the historical C16 code cannot be used unchanged;
- any stale historical mixer name is forbidden from the new target contract;
- no production approval writer exists;
- no production activation entrypoint exists;
- all four production approval operations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 must remain Draft, open and unmerged;
- explicit approval is required before the new rehearsal is run on `plexamp-bedroom`.
