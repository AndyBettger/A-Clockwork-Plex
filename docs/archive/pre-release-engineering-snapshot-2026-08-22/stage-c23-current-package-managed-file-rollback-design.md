# Stage C23 current-package managed-file exact-rollback design

## Status

Repository implementation prepared only. No Stage C23 command has run on `plexamp-bedroom`.

The accepted direct shared ALSA route remains the production route. Stage C23 does not authorise persistent installation, daemon reload, route selection, CamillaDSP startup, audio, approval publication, activation, reboot persistence or merge.

## Immutable prerequisites

Stage C23 accepts only the retained objects already proved on the target:

- package: `/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo`
- package fingerprint: `dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5`
- package files: `28`
- fingerprinted payload files: `27`
- baseline: `/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac`
- Stage C21 evidence: `/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg`
- Stage C21 evidence manifest: `a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff`
- Stage C22 evidence: `/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL`
- Stage C22 evidence manifest: `4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb`
- Stage C22 manifest shape: `140` rows including header / `139` entries
- Stage C22 results: `41/41 PASS`

Every retained input is checksummed again before the production lock is acquired and checked again after lock release.

## Ownership composition

Stage C23 does not introduce another lock, transaction, service or candidate owner.

`CurrentPackageManagedFileRollbackAdapterV9` extends the accepted Stage C22 current-package service adapter. That existing composition continues to own:

- the canonical production lock;
- the authoritative transaction and five snapshots;
- the accepted 28-file package and candidate root;
- private ALSA, sudoers, unit/runtime and CamillaDSP validation;
- captured application-service stop and exact restoration;
- DAC release and bounded restored-DAC/dashboard readiness.

The new adapter reuses the physically exercised Stage C18 managed-file primitives by method identity:

- authoritative filesystem-row parsing;
- safe parent-directory opening;
- inode-ledger directory creation;
- private temporary-file creation;
- atomic no-overwrite hard-link publication;
- exact installed-object validation;
- pending-publication and temporary-file rollback;
- pathname-substitution refusal;
- exact installed-inode removal;
- removal of only transaction-created directories;
- exact filesystem and full appliance rollback verification.

Only two historical twelve-file assumptions are replaced:

1. successful installation requires exactly 28 files and 27 payload files;
2. the typed C23 closure receipt requires exactly those current-package counts.

## Fixed transaction identities

A fresh Stage C23 process binds the current-package owner to:

- transaction prefix: `stage-c23-managed-file-rollback-install-`
- snapshot prefix: `stage-c23-managed-file-rollback-snapshot-`

The target-proved parent contract remains:

- `/var/lib/a-clockwork-plex` — root:root `0755`
- `/var/lib/a-clockwork-plex/split-bus` — root:root `0755`
- `/var/lib/a-clockwork-plex/split-bus/transactions` — root:root `0700`

No existing parent is repaired or changed. A mismatch is a refusal.

## Ordered rehearsal boundary

The rehearsal has 47 fixed checks:

1. replay package, baseline, Stage C21 and immutable Stage C22 evidence;
2. re-observe the complete accepted live baseline;
3. acquire the canonical lock and create one fresh authoritative transaction;
4. capture exact filesystem, service, mixer, loopback and DAC state;
5. stage and validate all 28 package files privately;
6. prove all non-C23 ordinary operations and all four approval operations blocked;
7. stop only captured-active dashboard, Shairport Sync and Plexamp;
8. prove the physical DAC and fixed loopback endpoints released;
9. atomically install all 28 files while rollback is armed before the first write;
10. verify exact installed inode, type, mode, owner and digest identities;
11. prove daemon reload and split-bus route selection still blocked after installation;
12. remove the exact installed inodes and only transaction-created directories;
13. prove the authoritative filesystem snapshot restored before any service restart;
14. restore Plexamp, Shairport Sync and dashboard in the fixed order;
15. prove dashboard HTTP health and bounded strict Plexamp DAC ownership;
16. prove zero filesystem, service, route, mixer, loopback or DAC mismatch;
17. refuse the pre-mutation abort and service-only closure after file mutation;
18. retain candidate and transaction audit copies;
19. close and remove the exact restored transaction;
20. release the canonical lock;
21. re-observe the complete accepted baseline and checksum all inputs/evidence.

## Atomic publication and rollback

Each managed file is copied to a private temporary inode in the destination directory. Mode, owner, content digest and durability are established before publication.

Publication uses an atomic no-overwrite hard link. The destination inode is bound in the rollback ledger before publication and adopted immediately after successful linking. An existing destination is a refusal; Stage C23 never overwrites an unexpected object.

Rollback verifies device, inode and object type before every removal. A pathname substitution, symlink, missing required installed object or unprovable publication outcome is a hard failure. Stage C23 does not remove an object merely because it occupies an expected pathname.

Captured-present directories are preserved and revalidated. Only directories created by the current transaction and still matching their exact recorded identities may be removed.

## Mandatory failure behaviour

Before service mutation, the existing pre-mutation abort remains available.

After service mutation begins, exact service restoration is mandatory.

After any managed-file write begins, filesystem rollback runs before service restoration. If exact filesystem rollback cannot be proved, Stage C23 deliberately leaves the canonical lock and authoritative transaction retained for inspection. It does not continue to service restart, transaction deletion or lock release.

If filesystem rollback succeeds but service restoration cannot be proved, the service layer likewise retains the lock and transaction.

No cleanup command should be issued until the retained transaction, lock lease, managed-file ledger and production destinations have been inspected.

## Deliberately blocked throughout

Stage C23 has no executable path for:

- `systemctl daemon-reload`;
- split-bus or direct-failback route selection;
- mixer writes;
- Stage C managed-service startup or shutdown;
- CamillaDSP startup;
- music or alarm probes;
- approval publication, removal or promotion;
- commit-manifest publication;
- installation commit;
- activation or reboot persistence;
- the blocked bare `scripts/install-master-eq.sh`;
- making PR #2 ready or merging it.

## Wrapper

`scripts/test-stage-c23-current-package-managed-file-rollback.sh` defaults to inert prepare-only mode.

Guarded mode requires:

- the exact fixed confirmation token;
- the package, baseline, Stage C21 and Stage C22 roots;
- a fresh user-owned `0700` evidence root;
- one constrained `sudo` execution of the fixed module.

There are no generic command, destination, route, service, mixer, approval, transaction-ID or lock-path selectors.

## Approval boundary

Repository preparation does not authorise target execution.

A later Pi run requires explicit approval naming:

- Stage C23;
- the exact branch head;
- the temporary interruption of Plexamp, AirPlay and dashboard;
- the brief creation of all 28 fixed production files before mandatory exact rollback.
