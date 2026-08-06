# Stage C23 current-package managed-file exact-rollback preparation result — 2026-08-06

## Result

Stage C23 repository preparation is complete. No Stage C23 command has run on `plexamp-bedroom` and no production file, service, route, mixer, approval record, CamillaDSP process, audio path or appliance checkout was changed by this preparation work.

The implementation head validated before this result record was:

`037be7cbcdac822e9ad32c8a52e223794ba31d49`

That head passed GitHub Actions workflow run `31075017147`, job `92531031272`, including Python compilation, JavaScript/page wiring, shell syntax and all `1,213` tests.

## Immutable target inputs

The guarded rehearsal is bound to the retained, accepted target objects:

- package: `/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo`
- package fingerprint: `dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5`
- package files: `28`
- fingerprinted payload files: `27`
- baseline: `/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac`
- Stage C21 evidence: `/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg`
- Stage C21 manifest SHA-256: `a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff`
- Stage C22 evidence: `/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL`
- Stage C22 manifest SHA-256: `4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb`
- Stage C22 manifest shape: `140` rows including header / `139` entries
- Stage C22 results: `41/41 PASS`

The package, baseline and both accepted evidence roots are validated before production-lock acquisition and checksummed again after lock release.

## Repository additions

- `scripts/stage_c_transaction/current_package_managed_file_rollback_adapter_v9.py`
- `scripts/stage_c_transaction/current_package_managed_file_rollback_rehearsal_v9.py`
- `scripts/test-stage-c23-current-package-managed-file-rollback.sh`
- `tests/test_stage_c23_current_package_managed_file_rollback_v9.py`
- `docs/stage-c23-current-package-managed-file-rollback-design.md`
- this preparation-result record

## Ownership and reuse

Stage C23 does not create another lock, transaction, candidate, service or rollback authority.

The new adapter extends the accepted Stage C22 current-package service-quiescence owner and reuses the physically exercised Stage C18 managed-file primitives by method identity. Those inherited primitives continue to own:

- rollback arming before the first filesystem write;
- private temporary inode creation;
- mode, owner, digest and durability establishment before publication;
- atomic no-overwrite hard-link publication;
- pending-publication, temporary-file and installed-inode ledgers;
- pathname-substitution and symlink refusal;
- exact installed-inode removal;
- removal of only transaction-created directories;
- exact filesystem and complete appliance rollback verification.

The current-package layer changes only the historical success count and typed closure boundary from 12 files to the accepted `28` files / `27` payload files.

Fresh transaction identities use:

- `stage-c23-managed-file-rollback-install-`
- `stage-c23-managed-file-rollback-snapshot-`

The target-proved parent contract remains root:root `0755`, root:root `0755`, root:root `0700` for the outer state directory, split-bus directory and transaction root respectively. Existing parents are never repaired or changed; any mismatch is a refusal.

## Guarded rehearsal sequence

The fixed Stage C23 program has 47 ordered checks. Its mutation-bearing prefix is deliberately narrow:

1. replay the exact package, baseline, Stage C21 evidence and immutable Stage C22 evidence;
2. re-observe the accepted complete live baseline;
3. acquire the canonical production lock and create one fresh authoritative transaction;
4. capture exact filesystem, service, mixer, loopback and DAC state;
5. stage and validate all 28 package files privately;
6. prove all non-C23 ordinary operations and all four approval operations blocked;
7. stop only captured-active dashboard, Shairport Sync and Plexamp services;
8. prove physical DAC and fixed loopback endpoints released;
9. atomically install all 28 fixed files with exact inode-ledger coverage;
10. verify every installed type, inode, mode, owner and digest;
11. prove daemon reload and route selection remain blocked after installation;
12. remove the exact installed inodes and only transaction-created directories;
13. prove exact filesystem restoration before restarting any application service;
14. restore Plexamp, Shairport Sync and dashboard in the fixed order;
15. prove dashboard HTTP health and bounded strict Plexamp DAC ownership;
16. prove zero filesystem, service, route, mixer, loopback or DAC mismatch;
17. refuse pre-mutation abort and service-only closure after file mutation;
18. retain non-authoritative candidate and transaction audit copies;
19. close and remove the exact restored transaction;
20. release the canonical production lock;
21. re-observe the accepted complete baseline and verify input/evidence integrity.

The final typed transaction state is:

`current-package-managed-files-rolled-back-and-closed`

## Failure semantics

Before service mutation, the existing pre-mutation abort remains available.

After service mutation begins, exact application-service restoration is mandatory.

After any managed-file write begins, mandatory filesystem rollback runs before inherited service restoration. This order is asserted by tests.

If exact filesystem rollback cannot be proved, the canonical production lock and authoritative transaction are deliberately retained. The process does not continue to service restoration, transaction deletion or lock release.

If filesystem rollback succeeds but exact service restoration cannot be proved, the service layer likewise retains the lock and transaction.

No cleanup or removal command should be issued until the retained lease, transaction state, managed-file ledger, snapshots and production destinations have been inspected.

## Wrapper boundary

`scripts/test-stage-c23-current-package-managed-file-rollback.sh` defaults to inert prepare-only mode.

Guarded mode requires:

- exact confirmation `STAGE-C23-CURRENT-PACKAGE-MANAGED-FILES-EXACT-ROLLBACK`;
- exact package, baseline, Stage C21 and Stage C22 roots;
- a fresh user-owned direct `/var/tmp` evidence root with mode `0700`;
- one constrained `sudo` execution of the fixed Stage C23 module.

The wrapper has no generic command, destination, route, service, mixer, approval, transaction-ID or lock-path selector. Its shell syntax is explicitly tested with `bash -n`.

## Deliberately blocked and not authorised

Stage C23 does not expose or authorise:

- `systemctl daemon-reload`;
- split-bus or direct-failback route selection;
- mixer writes;
- Stage C managed-service startup or shutdown;
- CamillaDSP startup;
- music or alarm probes;
- approval publication, removal or promotion;
- commit-manifest publication;
- installation commit;
- persistent activation or reboot persistence;
- the blocked bare `scripts/install-master-eq.sh`;
- making PR #2 ready or merging it.

## Approval gate

Repository preparation does not authorise target execution.

A Stage C23 target run requires a new explicit approval naming the final exact branch head, the brief interruption of Plexamp, AirPlay and the dashboard, and the temporary creation of all 28 fixed managed files before mandatory exact rollback.
