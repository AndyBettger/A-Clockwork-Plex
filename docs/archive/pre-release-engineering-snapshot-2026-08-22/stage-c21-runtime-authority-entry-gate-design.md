# Stage C21 activation-capable runtime authority — entry gate design

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: design gate only; no physical rehearsal exists or is approved

## Why Stage C21 is not a service-start rehearsal yet

Stage C20 physically proved the complete install, daemon-reload and temporary split-bus route-selection prefix with exact rollback. The next operation in the reviewed production install program is:

```text
start-managed-stage-c-services
```

The retained Stage C1 package is deliberately candidate-only and cannot honestly execute that operation:

- `/etc/systemd/system/a-clockwork-plex-audio-route.service` has `ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved`;
- `/etc/systemd/system/a-clockwork-plex-camilladsp.service` has the same condition;
- `/etc/systemd/system/a-clockwork-plex-audio-failback.service` has the same condition;
- the activation marker is not part of the Stage C1 package and has never been created by any accepted rehearsal;
- the route unit calls `/usr/local/bin/a-clockwork-plex-audio-route boot-select`;
- the Stage C1 helper deliberately blocks `boot-select`, `activate-split-bus`, `activate-direct-failback` and `restore-backup` with exit status 78;
- the Stage C1 sudoers candidate authorises only `status` and `validate-package`.

Starting these units now would therefore prove only that the candidate-only lockout works. Bypassing the condition or replacing `ExecStart` for a rehearsal would test a different unit graph from the reviewed production candidate and is not acceptable.

Stage C20 is consequently the final physical transaction rehearsal possible with the Stage C1 runtime package unchanged.

## Purpose of Stage C21

Stage C21 must define and statically prove the first activation-capable runtime authority before any managed unit is started on `plexamp-bedroom`.

It must produce a new, separately versioned review package. The accepted Stage C1 package and all physical evidence remain immutable historical inputs and must not be edited in place or relabelled as activation-capable.

Stage C21 itself remains prepare-only and non-physical.

## Required runtime authority responsibilities

One route authority must own every persistent or runtime active-route transition. It must have a fixed operation vocabulary and no caller-supplied paths, units or commands.

The activation-capable authority must cover:

```text
status
validate-runtime
install-transaction-preselected-split-bus
boot-select
activate-direct-failback
```

A later exact-uninstall restoration remains transaction policy, not a casual dashboard action.

The precise public vocabulary may be narrower after implementation review, but it must not expose arbitrary file paths, shell commands, service names, transaction roots or route names.

## Installation hand-off contract

The Stage C install transaction already owns:

- the production lock;
- the authoritative pre-install snapshot;
- candidate staging and validation;
- application-service quiescence;
- managed-file installation;
- the first systemd daemon reload;
- temporary split-bus route selection.

The runtime authority must not race or deadlock that held transaction.

Before managed service startup, Stage C21 must define one explicit hand-off. It must prove all of the following:

1. the active route is the exact transaction-selected split-bus candidate;
2. all twelve managed files match the transaction candidate;
3. the three managed units are loaded but inactive;
4. the physical DAC and fixed loopback playback endpoints remain released;
5. the transaction identity and held production-lock lease are exact;
6. an activation approval record is created only for that transaction and candidate fingerprint;
7. the route unit cannot reinterpret or replace the transaction-selected route during this first startup;
8. CamillaDSP may start only after the route authority has accepted the transaction hand-off;
9. failure before commit remains owned by the authoritative exact-rollback transaction.

A bare marker file with no identity, candidate digest or transaction binding is insufficient.

## Boot contract

Boot is a different entry condition from installation.

At ordinary boot there is no held install transaction and no fresh pre-install snapshot. The route authority must use only committed Stage C state and must choose one usable route before Plexamp, Shairport Sync or the dashboard start.

The boot path must:

1. validate the committed manifest, managed files, binary, loopback contract and both route candidates;
2. attempt the committed split-bus route and CamillaDSP startup;
3. publish `split-bus-active` only after strict DAC and loopback health passes;
4. otherwise select the physically accepted direct alarm-bypass route;
5. publish `direct-failback` with a reason and timestamp;
6. never expose application services to a selected split-bus route with no functioning CamillaDSP owner.

Installation hand-off and ordinary boot must not be conflated behind an ambiguous `boot-select` implementation.

## Failure and lock ownership

The single fixed route lock remains:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

Rules:

- an install-transaction hand-off operates under the already-held lease and must not reacquire the lock;
- ordinary boot or runtime failback must acquire the lock itself;
- runtime failure while an install transaction is uncommitted must defer to the install transaction's exact rollback authority;
- no helper may silently remove or replace a lock it did not create;
- any uncertain route identity, transaction identity or lock identity fails closed.

## Activation approval record

The existing unit condition names this path:

```text
/var/lib/a-clockwork-plex/split-bus/activation-approved
```

Stage C21 must define it as a structured, atomically written and checksummed record rather than a content-free flag.

At minimum it must bind:

```text
schema version
transaction identity
package fingerprint
commit state
active route digest
CamillaDSP config digest
CamillaDSP binary version and digest
loopback identity and parameters
DAC identity and fixed format
creation timestamp
```

Before transaction commit, the record must be explicitly temporary and transaction-bound. It must be removed by exact rollback. A boot-eligible committed record may exist only after every install health check and commit operation has succeeded.

## Managed unit model

The managed units remain exactly:

```text
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

Expected first-start states after a successful installation hand-off:

```text
a-clockwork-plex-audio-route.service      active/exited
a-clockwork-plex-camilladsp.service       active/running
a-clockwork-plex-audio-failback.service   inactive/dead
```

The failback unit must not run during a healthy startup. It is invoked only by the bounded CamillaDSP failure policy.

No unit is enabled during the first service-start rehearsal. Enablement and reboot behaviour require later dedicated stages.

## Required non-physical proof before service startup

Stage C21 must provide automated evidence for:

- immutable versioned runtime-operation vocabulary;
- exact install-hand-off and boot state machines;
- lock-held versus lock-unheld entry rules;
- structured activation approval parsing and validation;
- candidate and committed manifest binding;
- fail-closed route identity checks;
- atomic state publication;
- no-overwrite and no-follow filesystem operations;
- simulated split-bus startup success;
- simulated CamillaDSP startup failure leading to direct failback;
- simulated interruption at every route/state publication boundary;
- exact rollback ownership while the install transaction is uncommitted;
- no generic command, path, service or transaction dispatch;
- no network download;
- no physical PCM access in the tests;
- no persistent activation command or keep-active mode.

## Explicitly not approved by this design

This entry-gate document does not approve:

- changing the active ALSA route;
- creating `activation-approved` on the Pi;
- starting any managed Stage C unit;
- starting CamillaDSP;
- opening a music or alarm PCM;
- running finite audio probes;
- selecting direct failback through the new authority;
- enabling any unit;
- committing an installation;
- reboot testing;
- persistent activation.

## Next implementation sequence

```text
1. freeze Stage C1 as historical candidate-only evidence
2. implement a separately versioned activation-capable runtime authority core
3. implement structured temporary and committed activation records
4. implement fixed installation-hand-off and boot entry points
5. exercise both paths entirely in disposable roots with injected failures
6. generate and review a new runtime package without installing it
7. add a dedicated prepare-only Pi review gate
8. only then design the first managed-service startup and exact-rollback rehearsal
```

The blocked bare installer must not be run. PR #2 must remain Draft, open and unmerged until explicit approval is given.
