# Stage C18 managed-file installation and exact-rollback rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C18 crosses the first production-filesystem mutation boundary in the
immutable install program. It extends the physically accepted Stage C17 prefix
through one operation:

```text
install-managed-files
```

It then deliberately stops before:

```text
reload-systemd
```

The twelve reviewed package files are installed atomically while the application
services and DAC remain quiesced, verified against the transaction-bound Stage C1
manifest, and then removed through the authoritative filesystem snapshot before
any daemon reload, active-route selection, managed Stage C service startup,
audio probe or install commit can occur.

The exact direct appliance state is restored and proved before the transaction
is closed and the production lock is released.

Persistent Stage C activation remains blocked.

## Replayed evidence

The guarded rehearsal accepts only:

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C17 result  /var/tmp/a-clockwork-plex-stage-c17-service-quiescence.3ySKhd
```

The successful C17 evidence must contain the exact thirty-five-check PASS
contract, a completed v3 restored-service closure, retained candidate and
transaction review copies, and no activation or rollback authority.

The failed-safe C17 evidence directory is rejected.

## Exact physical boundary

The guarded rehearsal may:

1. replay and fingerprint the Stage C1 package and successful C17 evidence;
2. inspect the fixed host and absent production lock;
3. acquire the one fixed production lock;
4. create a fresh generated authoritative install transaction;
5. capture exact filesystem, service, mixer, loopback and DAC state;
6. stage and validate all twelve reviewed files inside the transaction;
7. stop only the captured-active dashboard, Shairport Sync and Plexamp services;
8. prove the physical DAC and fixed loopback endpoints have no owners;
9. create only manifest directories captured absent, preserving existing
   directory mode and ownership;
10. atomically install exactly twelve files from the transaction-private
    candidate;
11. verify every installed file's path, type, single-link state, device, inode,
    mode, root ownership and SHA-256 digest;
12. prove the active ALSA route remains the accepted direct route;
13. prove all post-install operations from `reload-systemd` onward remain
    unavailable;
14. remove only the exact device/inode objects created by this rehearsal;
15. restore every managed destination and directory to the authoritative
    filesystem snapshot;
16. restore exactly the captured application-service state;
17. wait boundedly for dashboard HTTP and the strict DAC runtime contract;
18. verify zero filesystem, service, route, mixer, loopback and DAC mismatch;
19. retain non-authoritative candidate, installation, rollback, service and
    transaction evidence;
20. close and remove the exact rolled-back rehearsal transaction;
21. release the production lock only after exact rollback closure.

It may not:

- reload systemd;
- select the split-bus route;
- select the direct-failback route;
- start or stop any managed Stage C service;
- change any mixer control;
- start CamillaDSP;
- open a PCM or run a music/alarm probe;
- write an install commit;
- restore mixer or service state through the later production rollback
  operations;
- create an activation marker;
- persist any Stage C file or route;
- use the blocked bare master-EQ installer.

## Production write contract

### Fixed destination set

The caller cannot supply any destination. Every target comes from the validated
Stage C1 manifest and is re-bound to the authoritative snapshot.

All twelve managed file destinations must be captured absent. Managed directory
states may be captured present or absent, but any type conflict, symlink,
ownership drift or mode drift fails before installation.

The active direct ALSA file is not a managed package destination and must remain
bit-for-bit identical throughout Stage C18.

### Atomic file installation

Each file install uses:

1. a fixed manifest destination;
2. verified real, non-symlink ancestors;
3. an opened parent directory whose device/inode matches the pre-open
   observation;
4. a fresh unpredictable temporary name created with `O_EXCL`, `O_CLOEXEC` and
   `O_NOFOLLOW` where available;
5. transaction-private source digest verification before and after copy;
6. `fchmod`, `fchown` and file `fsync` before rename;
7. atomic rename within the opened parent directory;
8. immediate rollback-ledger adoption of the renamed device/inode;
9. parent-directory `fsync`;
10. final type, link-count, device, inode, mode, owner and digest verification.

A failure before rename removes the private temporary file. A failure at or after
rename enters mandatory exact rollback.

### Directory creation

A captured-absent managed directory is created only through its opened real
parent. Its device/inode enters the rollback ledger immediately after creation
and opening, before later metadata or `fsync` operations may fail.

Captured-present directories are never re-chmodded or re-owned. They are checked
before install and again after rollback.

## Mandatory partial-install rollback

Rollback is armed before the first production filesystem write.

For removal, the adapter distinguishes:

- **installation acceptance**, which requires exact type, mode, owner and digest;
- **rollback identity**, which requires the exact device/inode and object type
  recorded immediately at `mkdir` or atomic rename.

This distinction permits safe removal of the adapter's own partial object when a
later metadata or verification operation fails, while still refusing to unlink a
substituted pathname.

Rollback proceeds in fixed reverse order:

1. remove installed file inodes;
2. remove only directories created by the transaction, deepest first;
3. prove every managed file destination is absent;
4. prove every captured-present directory retains exact mode and ownership;
5. prove every captured-absent directory is absent;
6. prove the active direct ALSA route remains unchanged;
7. write the transaction rollback state.

If exact filesystem rollback cannot be proved, the adapter fails closed and
intentionally retains the production lock and authoritative transaction for
manual recovery evidence. It must not start application services over an
unproven filesystem state.

## Service restoration and health

After exact filesystem rollback, the captured application services are restored
in the physically accepted C17 order:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
```

The corrected C17 readiness observer waits for dashboard HTTP first and then
polls the complete DAC contract for up to thirty seconds. No fixed sleep is used.

Exact rollback verification requires:

- every managed file absent;
- exact managed directory state;
- unchanged direct ALSA route;
- exact six-service observation;
- exact four-control mixer snapshot;
- exact `snd_aloop` snapshot;
- valid physical DAC format and owner;
- healthy dashboard HTTP.

## Versioned lifecycle closure

### Frozen history

The accepted histories remain unchanged:

```text
v1  33 original adapter operations
v2  34 operations, adding abort-uncommitted-transaction
v3  35 operations, adding close-restored-rehearsal-transaction
```

Stage C18 defines a v4 view containing 36 operations by adding:

```text
close-exact-rollback-rehearsal-transaction
```

The v2 pre-mutation abort must refuse after the first service stop. The v3
service-only closure must refuse after managed-file mutation. Only the v4
closure can represent the completed C18 state.

### Receipt contract

The v4 receipt must prove:

```text
state                    managed-files-rolled-back-and-closed
mutation_started         true
managed_files_installed  true
filesystem_restored      true
services_restored        true
committed                false
transaction_path_absent  true
parents_restored         true
installed_file_count     12
```

It records only adapter-owned audit evidence and cannot represent installation,
activation, failback, uninstall or commit authority.

## Operation partition

Stage C18 exposes twenty-two v1 operations:

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
16. stop captured application services;
17. verify DAC released;
18. install managed files;
19. restore captured application services;
20. verify dashboard health;
21. restore exact snapshot;
22. verify exact rollback.

It also exposes three versioned lifecycle methods:

23. v2 pre-mutation abort;
24. v3 restored-service closure;
25. v4 exact-rollback rehearsal closure.

The remaining eleven v1 operations stay blocked:

```text
reload-systemd
select-split-bus-route
start-managed-stage-c-services
stop-managed-stage-c-services
verify-split-bus-health
run-finite-music-probe
run-finite-alarm-probe
write-commit-manifest
select-direct-failback-route
restore-mixer-state
restore-service-state
```

## Expected physical acceptance checks

The rehearsal emits exactly forty PASS checks:

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
service-quiescence
dac-release
managed-file-installation
installed-manifest-binding
post-install-boundary
exact-filesystem-rollback
application-service-restoration
dashboard-health
exact-rollback-verification
exact-restoration-boundary
pre-mutation-abort-refusal
service-only-closure-refusal
candidate-evidence-copy
exact-rollback-close-v4
exact-transaction-cleanup
production-lock-released
input-integrity
evidence-integrity
activation-interface
```

## Evidence

The guarded rehearsal retains:

```text
results.tsv
identity.tsv
parent-state.tsv
service-actions.tsv
managed-file-actions.tsv
restoration-readiness.tsv
managed-install-review.tsv
typed-operations.json
blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
lock-events.tsv
evidence-manifest.tsv
report.txt
```

Every outward copy is explicitly non-authoritative and unusable for activation
or rollback.

## Automated gate

Before any Pi command is accepted, focused tests must prove:

- v1, v2 and v3 history remain unchanged;
- v4 adds exactly one unique lifecycle operation;
- exact 25/11 C18 operation partition;
- the v4 receipt rejects pre-mutation, non-installed, unrestored, committed,
  transaction-present or wrong-file-count states;
- no caller-supplied destination, unit, command, endpoint or evidence path;
- installation requires candidate validation, service quiescence and DAC release;
- every production write is covered by rollback before it occurs;
- a renamed file and created directory enter the rollback ledger before any
  later operation may fail;
- rollback deletes only exact adapter-recorded device/inode objects;
- successful installation still requires exact metadata and digest;
- captured-present directories are not modified;
- active ALSA is never overwritten;
- systemd reload, route selection, managed service operations, audio probes and
  commit remain unavailable;
- filesystem rollback precedes application-service restoration;
- v2 and v3 closure methods refuse after managed-file mutation;
- prepare-only exits before the single constrained sudo command;
- no install persistence, activation, failback, uninstall or keep-active option.

Persistent Stage C activation remains blocked. The old master-EQ installer
remains blocked. PR #2 remains Draft, open and unmerged.
