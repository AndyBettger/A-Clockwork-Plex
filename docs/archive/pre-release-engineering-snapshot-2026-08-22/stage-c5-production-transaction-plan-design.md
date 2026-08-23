# Stage C5 production transaction plan review

Status: design and review-only implementation may proceed. This stage contains no root adapter, production mutation entrypoint or persistent activation authority.

## Purpose

Stage C4 proved the file transaction and exact rollback mechanics in four independent synthetic filesystems. Stage C5 now turns those mechanics into a deterministic production transaction state machine for review before any root-owned mutation implementation exists.

The stage consumes the validated Stage C1 package, Stage C3 privileged read-only evidence and Stage C4 sandbox evidence. It emits a complete lock, fresh-snapshot, state-transition, command and rollback contract inside a fresh user-owned review directory.

Stage C5 does **not** acquire the real route lock, create a production transaction directory, invoke sudo, stop services, install files, select a route, open a PCM or provide an activation command.

## Interface

Prepare-only remains the default:

```bash
bash scripts/prepare-stage-c-production-transaction-plan.sh \
  --package-root /var/tmp/<validated-stage-c1-package> \
  --stage-c3-root /var/tmp/<validated-stage-c3-snapshot> \
  --stage-c4-root /var/tmp/<validated-stage-c4-sandbox>
```

Prepare-only invokes no `sudo`, creates no review directory and prints the exact guarded review-generation command.

Review generation requires the exact token:

```text
STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW
```

and a fresh empty mode-0700 directory directly beneath `/var/tmp` named:

```text
a-clockwork-plex-stage-c5-review.*
```

The token authorises only generation of review evidence beneath that directory. It is not an installation or activation token.

## Input replay

Before generating a plan, Stage C5 independently replays:

1. the Stage C1 manifest, package checksums, modes and evidence;
2. the complete Stage C3 twelve-check PASS result and evidence manifest;
3. all twelve managed destinations recorded absent by root;
4. the exact pre-Stage-C ALSA checksum and rollback copy;
5. the complete Stage C4 evidence manifest;
6. all nine Stage C4 PASS checks;
7. the four exact Stage C4 scenarios;
8. successful install verification followed by explicit uninstall;
9. three automatic rollback outcomes using the same rollback implementation;
10. zero rollback mismatches in every scenario;
11. restoration of `/etc/sudoers.d` to the captured mode `0750` in every scenario.

Stage C3 and Stage C4 remain review evidence only. Neither may become an activation-authoritative backup.

## Single route lock

Every future production writer must use one lock:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

The future root-owned engine, route helper, runtime failback service and explicit uninstall path must all acquire this same exclusive lock.

The lock contract requires:

- exclusive non-blocking acquisition;
- acquisition before transaction identity or snapshot creation;
- ownership retained through commit or complete rollback;
- release only after final service/state verification;
- transaction identity, invoking action and PID recorded while held;
- no second route, installer or EQ lock that can create conflicting writers.

Stage C5 records this contract but does not open or create the real lock file.

## Fresh authoritative snapshot

Every future authorised mutation must create a new root-owned transaction directory only after acquiring the route lock:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<transaction-id>/
```

The transaction identifier must be newly generated for that invocation. The directory must begin empty, mode `0700`, owner `root:root`, and may not be supplied by the caller.

The authoritative snapshot must capture immediately before mutation:

- original or explicit absence state for every managed file;
- exact file content, SHA-256, mode, uid and gid;
- active ALSA file content and checksum;
- managed parent-directory existence, mode, uid and gid;
- application and Stage C service load, active and enabled state;
- all four mixer controls and exact restore values;
- deterministic loopback persistence files and loaded module parameters;
- DAC owner PID/user/command/file-descriptor access and exact `hw_params`;
- candidate package and engine checksums;
- transaction action, invoking user and timestamps.

The Stage C3 rehearsal directory must never be copied or referenced as a rollback source.

## Production transaction state machine

The reviewed ordering is:

1. replay immutable package and host contracts;
2. acquire the single route lock;
3. generate a fresh transaction identity and root-owned directory;
4. capture the authoritative snapshot;
5. verify snapshot completeness and checksums;
6. stage candidate files inside the transaction directory;
7. validate staged candidates without changing production;
8. stop only application services captured active;
9. prove the physical DAC and route endpoints are released;
10. atomically install managed files;
11. reload systemd once;
12. start the route authority and select split-bus only as one bounded operation;
13. verify CamillaDSP, loopback and physical DAC ownership/format;
14. run finite music-lane and alarm-lane probes;
15. restore only application services captured active;
16. verify CamillaDSP survives application startup;
17. verify dashboard and root-helper health agree;
18. write the commit manifest atomically;
19. release the route lock.

No state may be skipped or reordered by caller arguments.

## Failure and rollback ownership

Failures before application services are stopped are pre-mutation aborts. They must close the uncommitted transaction record and release the lock without claiming rollback of production state.

Every failure after application services begin stopping and before commit must invoke one exact rollback implementation. Rollback must:

1. retain the same route lock;
2. stop only services involved in the failed transaction;
3. release DAC/loopback endpoints;
4. restore every managed file or verified absence exactly;
5. restore the exact active ALSA file;
6. restore captured parent-directory modes/ownership and remove only newly created empty directories;
7. reload systemd when unit files changed;
8. restore loopback persistence and loaded state;
9. restore all four mixer values;
10. restore original service load/enabled/active states;
11. verify every restored checksum, mode, owner and state;
12. record zero or explicit rollback mismatches;
13. release the lock only after final verification.

A committed installation is removed only through explicit uninstall using that installation's authoritative transaction snapshot. Runtime CamillaDSP failure instead selects the physically proven direct alarm-bypass failback route and does not perform exact uninstall rollback.

## Command contract

The future production adapter must use fixed executable paths and fixed argument builders. It must not use `shell=True`, `eval`, dynamic unit names, caller-supplied filesystem destinations or arbitrary helper actions.

The state machine may request only these operation families:

- exact filesystem snapshot/copy/replace/fsync/chmod/chown/unlink/rmdir;
- exclusive `flock` on the single route lock;
- fixed `systemctl` operations for the six reviewed units;
- fixed `amixer` reads/writes for the four reviewed controls;
- fixed loopback-module inspection/load/unload operations;
- fixed DAC owner and `hw_params` inspection;
- finite ALSA parse and PCM probes;
- fixed CamillaDSP start/stop/health operations;
- fixed dashboard health request to the local appliance endpoint.

No network download, package installation or arbitrary command execution belongs to activation.

## Stage C5 outputs

A successful review generation produces:

- `results.tsv`;
- `transaction-state-machine.tsv`;
- `lock-contract.tsv`;
- `authoritative-snapshot-contract.tsv`;
- `command-contract.tsv`;
- `rollback-entrypoints.tsv`;
- `activation-blockers.tsv`;
- `report.txt`;
- `evidence-manifest.tsv`.

Both input evidence trees are fingerprinted before and after generation. Any change is a hard failure.

## Safety boundary

Stage C5 must not:

- invoke `sudo` or require root;
- write `/run`, `/etc`, `/usr/local`, `/var/lib` or any production path;
- acquire the real route lock;
- create a production transaction directory;
- execute `systemctl`, `amixer`, `modprobe`, `aplay`, `fuser` or CamillaDSP;
- open a device or PCM;
- create an approval marker;
- provide a root adapter, activation, installation, rollback-to-production or uninstall-from-production interface.

## Promotion boundary

A successful Stage C5 review permits implementation of the root-owned adapter behind the reviewed state machine, still default-blocked and without physical activation authorisation.

Before persistent activation can be considered, the project still requires:

- reviewed root adapter and exact backup implementation;
- guarded production entrypoint and single explicit activation token;
- candidate ALSA, sudoers, systemd and CamillaDSP validation under root;
- real finite route probes;
- bounded CamillaDSP service orchestration;
- automatic direct alarm-bypass failback;
- EQ state/render/reload migration;
- dashboard degraded-mode health;
- deliberate physical failure injection;
- exact uninstall proof;
- explicit user authorisation.
