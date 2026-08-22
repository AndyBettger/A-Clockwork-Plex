# Stage C24 current-package systemd daemon-reload exact-rollback preparation result — 2026-08-06

## Result

**Prepared in the repository; not authorised or run on `plexamp-bedroom`.**

The Stage C24 boundary is ready for a separately approved physical rehearsal. It extends accepted Stage C23 only far enough to make the exact accepted current-package unit files visible to the real systemd manager and then restore both filesystem and manager state before the accepted direct appliance services restart.

No production path, service, mixer, route, DAC, lock, transaction, approval state or retained Pi evidence was changed during this repository preparation.

## Prepared implementation head

`1fd51034b142a215977431aca85371ce29ed7824`

GitHub Actions for that exact implementation head:

- workflow: `Tests`
- run: `31079287710`
- job: `92544169447`
- conclusion: `success`
- compilation: PASS
- JavaScript/page/shell checks: PASS
- unit tests: `Ran 1250 tests in 7.241s`
- result: `OK`

The first integrated C24 test run at `a4ab1b8c0d3b396c66dc79be4ec4f100d58e4831` reported four false-negative static assertions. All four were test-only expectations that searched raw source text across Python’s adjacent split string literals or expected an imported manifest hash to be repeated literally. The implementation compiled and 1,237 other tests passed. Commit `a4e9641b6f2952391fafe36b6146da5ce306ecf4` replaced those fragile text assertions with constant, AST-literal and typed receipt assertions; its 1,241-test run passed.

A subsequent safety review found one genuine edge case before physical preparation was accepted: after a failed second reload or failed rollback-unit observation, historical cleanup could attempt another daemon reload. The final v11 guard now counts command attempts, including failures, delegates the two permitted attempts to the physically exercised C19 primitive and refuses an unapproved third attempt before `systemctl` is called. Typed C24 closure also refuses unless the attempt count is exactly two. The final 1,250-test implementation head includes this hardening.

## Repository components

- `scripts/stage_c_transaction/current_package_systemd_reload_rollback_adapter_v10.py`
  - current 28-file transaction and rollback owner
  - fresh C24 transaction/snapshot identities
  - two-phase systemd-manager state
  - typed 28-file/27-payload/two-successful-reload closure
  - refusal of C23 file-only closure after manager mutation
- `scripts/stage_c_transaction/current_package_systemd_reload_rollback_adapter_v11.py`
  - hard maximum of two attempted daemon-reload commands, including failures
  - no second host-command implementation
  - successful closure requires exactly two attempts
- `scripts/stage_c_transaction/current_package_systemd_reload_rollback_rehearsal_v10.py`
  - complete 54-check physical orchestrator
  - exact C23 evidence replay at 144 rows / 143 entries
- `scripts/stage_c_transaction/current_package_systemd_reload_rollback_rehearsal_v11.py`
  - final bounded-attempt entry point
- `scripts/test-stage-c24-current-package-systemd-reload-rollback.sh`
  - inert prepare-only default
  - one fixed guarded sudo invocation
  - no generic command, service, route, mixer, approval, lock or transaction selector
- `tests/test_stage_c24_current_package_systemd_reload_rollback_v10.py`
- `tests/test_stage_c24_daemon_reload_attempt_guard_v11.py`
- `tests/test_stage_c24_attempt_guard_closure_v11.py`
- `docs/stage-c24-current-package-systemd-reload-exact-rollback-design.md`

## Exact bound inputs

- package root: `/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo`
- package fingerprint: `dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5`
- package files: `28`
- package payload files: `27`
- baseline root: `/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac`
- Stage C21 root: `/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg`
- Stage C22 root: `/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL`
  - manifest SHA-256: `4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb`
  - rows / entries: `140 / 139`
  - results: `41 / 41 PASS`
- Stage C23 root: `/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG`
  - manifest SHA-256: `e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a`
  - rows / entries: `144 / 143`
  - results: `47 / 47 PASS`
  - transaction: `stage-c23-managed-file-rollback-install-7e309a9bbce196b09f3f79d4`
  - snapshot: `stage-c23-managed-file-rollback-snapshot-7e309a9bbce196b09f3f79d4`
  - lease: `stage-c14-lock-fa53845becd969695d720a75`

## Fresh C24 identities

- transaction prefix: `stage-c24-systemd-reload-rollback-install-`
- snapshot prefix: `stage-c24-systemd-reload-rollback-snapshot-`
- evidence prefix: `a-clockwork-plex-stage-c24-current-package-systemd-reload-rollback.`
- confirmation token: `STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK`
- final state: `current-package-systemd-reload-rolled-back-and-closed`

## Prepared successful sequence

1. Validate all five retained inputs before lock acquisition.
2. Re-observe the accepted live direct-appliance baseline.
3. Acquire the canonical production lock and create one fresh authoritative transaction.
4. Capture exact filesystem, service, mixer, loopback and DAC state.
5. Stage and privately validate all 28 files.
6. Prove ordinary and approval boundaries remain blocked.
7. Stop dashboard, Shairport Sync and Plexamp if captured active.
8. Prove physical DAC and fixed loopback endpoints are released.
9. Atomically install and verify all 28 fixed files.
10. Keep active route selection blocked.
11. Use daemon-reload attempt one and prove exactly three loaded but inactive managed units.
12. Remove exact installed inodes and transaction-created directories.
13. Refuse service restoration while manager rollback is pending.
14. Use daemon-reload attempt two and prove all three managed units are not-found.
15. Restore Plexamp, Shairport Sync and dashboard.
16. Verify exact filesystem, manager, service, route, mixer, loopback, DAC and dashboard restoration.
17. Refuse older lifecycle closures.
18. Close through the typed C24 closure, remove the transaction, restore parent state and release the lock.
19. Re-observe the accepted live baseline and re-fingerprint all retained inputs.
20. Seal the complete 54-check evidence tree.

## Failure contract

The total `systemctl daemon-reload` command budget is **two attempts**, including failures.

If the first command or candidate-unit observation fails, exact file rollback may use the remaining second attempt to restore manager state. If the second command or rollback-unit observation fails, no third command is issued. The canonical production lock, authoritative transaction, snapshots, ledgers and evidence are retained for inspection.

After any mutation, restoration ordering is fixed:

1. exact installed-inode and created-directory rollback
2. systemd-manager rollback, only if an attempt remains
3. captured application-service restoration
4. exact baseline verification and transaction cleanup

No rerun or manual cleanup is permitted after retained authority state without inspection.

## Deliberately unproved and unauthorised

Stage C24 does not authorise or prove:

- split-bus or direct-failback route selection
- mixer writes
- CamillaDSP startup
- managed Stage C service startup
- split-bus runtime health
- finite music or alarm probes
- approval publication or promotion
- installation commit
- activation or reboot persistence
- cleanup of retained accepted evidence
- making PR #2 ready
- merging PR #2
- use of `scripts/install-master-eq.sh`

## Approval required before physical use

A new explicit approval must bind the final repository head and acknowledge:

- brief interruption of Plexamp, AirPlay and the dashboard
- temporary creation of all 28 fixed managed files
- a hard maximum of exactly two `systemctl daemon-reload` attempts, including failures
- mandatory exact filesystem, systemd-manager and application-service rollback

Until that approval is given, Stage C24 remains repository-only and unexecuted.
