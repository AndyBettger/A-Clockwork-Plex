# Stage C5 production transaction plan review result — 5 August 2026

Status: **PASS on `plexamp-bedroom`**. This was an unprivileged review-only generation. No production route lock, transaction directory, service, audio device or persistent Stage C path was opened or changed.

## Run identity

- Host: `plexamp-bedroom`
- Invoking user: `andy`
- Repository head used for the physical review: `7d3980301fe4bba3f2fbb91e2c32c2e6376e4262`
- Stage C1 package: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- Stage C3 evidence: `/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F`
- Stage C4 evidence: `/var/tmp/a-clockwork-plex-stage-c4-sandbox.29DbuW`
- Stage C5 review: `/var/tmp/a-clockwork-plex-stage-c5-review.qKjJsF`
- Confirmation token: `STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW`

The outer wrapper ran as the normal project user. It invoked no `sudo` command and wrote only inside the fresh mode-0700 Stage C5 review directory.

## Result checks

All ten Stage C5 checks passed:

1. `input-replay`
2. `stage-c4-proof`
3. `review-scope`
4. `state-machine`
5. `single-lock`
6. `fresh-snapshot`
7. `command-contract`
8. `rollback-ownership`
9. `activation-blockers`
10. `input-integrity`

The generator reported:

```text
A Clockwork Plex Stage C5 production transaction plan review passed.
No production path was written or changed. Persistent activation remains blocked.
```

## Transaction state machine

The generated state machine contains twenty ordered states.

The safety-critical ordering is:

1. replay immutable Stage C1, C3 and C4 contracts;
2. acquire the one route lock;
3. create a new transaction identity;
4. capture and verify a fresh authoritative snapshot;
5. stage and validate candidates;
6. begin production mutation only at `stop-application-services`;
7. retain the lock through commit or verified rollback;
8. release the lock only after a committed transaction or zero-mismatch rollback.

The first state marked `production_mutation=true` is order 80, `stop-application-services`. Every earlier state is preflight, snapshot or staging only.

The proposed fixed lock remains:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

Its contract requires exclusive non-blocking `flock`, acquisition before transaction identity and snapshot, retention through commit or verified rollback, and no secondary installer, route or EQ writer lock.

Stage C5 documented this lock but did not open or create it.

## Fresh authoritative snapshot contract

A future authorised transaction must generate its own transaction identifier. The caller cannot supply or reuse one.

The future root-owned transaction directory is:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<transaction-id>
```

It must begin empty with mode `0700` and capture:

- content, SHA-256, mode, UID and GID or explicit absence for all twelve managed files;
- the exact active ALSA file and checksum;
- existence, mode, UID and GID for managed directories;
- load, active and enabled states for the three application and three Stage C services;
- exact raw and displayed values for all four mixer controls;
- loopback persistence and loaded parameters;
- structured DAC PID, user, command, descriptor and access evidence;
- exact DAC hardware parameters;
- package and transaction-engine checksums;
- action, invoking user and timestamp provenance.

Stage C3 and Stage C4 are explicitly forbidden as rollback sources. They remain review provenance only.

## Command contract

Stage C5 fixed the future command families and forbids caller-supplied production paths, dynamic unit names, arbitrary devices, unbounded values, arbitrary shell execution and network download during activation.

The fixed operation families cover:

- filesystem snapshot, atomic replacement and exact removal;
- one fixed lock path;
- six reviewed systemd units;
- four reviewed mixer controls;
- exact `snd_aloop` parameters;
- fixed DAC inspection;
- finite known ALSA probes;
- pinned CamillaDSP start, stop, reload and health operations;
- one local dashboard health request.

`shell=True`, `eval`, `exec`, arbitrary command strings and activation-time executable downloads are forbidden.

## Recovery ownership

Stage C5 deliberately separates four recovery classes:

1. **Pre-mutation abort** — close any uncommitted record and release the lock.
2. **Failed-install exact rollback** — restore the fresh authoritative snapshot and verify zero mismatches while retaining the lock.
3. **Explicit uninstall** — use the committed installation's own authoritative transaction snapshot.
4. **Runtime CamillaDSP failure** — select the alarm-safe direct alarm-bypass route; do not perform uninstall rollback.

This preserves the crucial distinction between returning the appliance to its exact pre-install state and keeping scheduled alarms audible during a runtime DSP failure.

## Activation blockers

All nine blockers remained intact:

- root adapter absent;
- root entrypoint absent;
- activation token absent;
- approval marker absent;
- real production lock not opened;
- production transaction directory not created;
- service and audio commands not executable;
- Stage C3 and C4 snapshot reuse forbidden;
- persistent activation blocked pending later review and explicit user authorisation.

## Evidence integrity

The review generated:

- `results.tsv`;
- `transaction-state-machine.tsv`;
- `lock-contract.tsv`;
- `authoritative-snapshot-contract.tsv`;
- `command-contract.tsv`;
- `rollback-entrypoints.tsv`;
- `activation-blockers.tsv`;
- `report.txt`;
- `evidence-manifest.tsv`.

The evidence manifest records every generated file with its mode and SHA-256 checksum. The input-integrity check proved the Stage C1, Stage C3 and Stage C4 trees remained unchanged.

## Safety conclusion

Stage C5 proves that the future production transaction has a deterministic ordering, one lock authority, a fresh-snapshot boundary and unambiguous rollback ownership before any root implementation exists.

It does not implement or authorise root execution, production installation, route selection, service changes, module changes, mixer changes, PCM access, CamillaDSP execution, runtime failback, rollback or uninstall.

Persistent Stage C activation remains blocked.
