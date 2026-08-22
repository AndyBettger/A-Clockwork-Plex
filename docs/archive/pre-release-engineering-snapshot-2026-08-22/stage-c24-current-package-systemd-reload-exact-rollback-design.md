# Stage C24 current-package systemd daemon-reload exact-rollback design

## Status

Repository implementation prepared. No Stage C24 appliance rehearsal has been authorised or run.

Stage C24 is the next deliberately narrow boundary after accepted Stage C23. It proves that the exact accepted 28-file current package can be made visible to the real systemd manager and then removed from both the filesystem and manager state before the accepted direct appliance state is restored.

It does **not** select an audio route, alter mixer values, start CamillaDSP or any managed Stage C service, open a playback PCM, run music or alarm probes, publish approval state, commit an installation or activate persistent Stage C.

## Accepted immutable inputs

Stage C24 accepts only:

- package: `/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo`
  - 28 files
  - 27 payload files
  - fingerprint `dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5`
- baseline: `/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac`
- Stage C21 evidence: `/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg`
- Stage C22 evidence: `/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL`
  - manifest SHA-256 `4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb`
  - 140 rows / 139 entries
  - 41 ordered PASS results
- Stage C23 evidence: `/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG`
  - manifest SHA-256 `e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a`
  - 144 rows / 143 entries
  - 47 ordered PASS results
  - transaction `stage-c23-managed-file-rollback-install-7e309a9bbce196b09f3f79d4`
  - snapshot `stage-c23-managed-file-rollback-snapshot-7e309a9bbce196b09f3f79d4`
  - production-lock lease `stage-c14-lock-fa53845becd969695d720a75`

The retained input trees are validated before lock acquisition and fingerprinted again after lock release.

## Repository components

### Current-package transaction owner

`scripts/stage_c_transaction/current_package_systemd_reload_rollback_adapter_v10.py`

`CurrentPackageSystemdReloadRollbackAdapterV10` extends the accepted Stage C23 `CurrentPackageManagedFileRollbackAdapterV9`. It therefore retains the current 28-file package contract, current parent-state handling, atomic no-overwrite publication, installed-inode ledger, exact file/directory rollback, application-service quiescence and typed current-package closure behavior.

It directly reuses the physically exercised Stage C19 systemd primitives for:

- fixed `systemctl daemon-reload`
- fixed `systemctl show` observation of the three managed units
- exact property parsing
- append-only systemd action evidence

No second subprocess or generic host-command owner is introduced.

Fresh transaction identities are:

- `stage-c24-systemd-reload-rollback-install-…`
- `stage-c24-systemd-reload-rollback-snapshot-…`

The final typed closure state is:

`current-package-systemd-reload-rolled-back-and-closed`

Its receipt requires:

- mutation began
- all 28 files were installed
- 27 payload files were bound
- systemd was reloaded successfully twice
- the exact filesystem was restored
- the systemd manager was restored
- captured application services were restored
- the transaction path is absent
- transaction-created parents are restored
- no installation commit occurred

The older C23 file-only closure explicitly refuses after systemd-manager mutation.

### Hard daemon-reload attempt budget

`scripts/stage_c_transaction/current_package_systemd_reload_rollback_adapter_v11.py`

A successful-path count of two reloads is not sufficient by itself: a failed command or failed post-reload unit observation must not permit cleanup to issue an unapproved third command.

`CurrentPackageSystemdReloadRollbackAdapterV11` therefore places a hard budget of **two attempted daemon-reload commands**, including failures. It delegates each allowed attempt to the exact Stage C19 host primitive. Once the budget is exhausted, a further attempt is rejected before `systemctl` is called.

Consequences:

- first reload command fails: it consumes attempt one; rollback may use attempt two
- first reload succeeds but candidate-unit observation fails: rollback may use attempt two
- second reload command fails: no third command is issued; authority state is retained
- second reload succeeds but rollback-unit observation fails: no third command is issued; authority state is retained
- successful rehearsal: two attempts and two successful reloads

### Final guarded entry point

`scripts/stage_c_transaction/current_package_systemd_reload_rollback_rehearsal_v11.py`

The final entry point binds the v11 attempt guard into the complete v10 rehearsal for one process invocation, verifies the expected base binding and restores the module binding afterward.

### Guarded shell wrapper

`scripts/test-stage-c24-current-package-systemd-reload-rollback.sh`

Default invocation is inert prepare-only mode. It performs no sudo, host observation, lock operation, transaction creation, service change, file write or systemctl command.

Guarded mode requires the exact token:

`STAGE-C24-CURRENT-PACKAGE-SYSTEMD-RELOAD-EXACT-ROLLBACK`

The wrapper exposes only:

- the five fixed retained input roots
- one fresh Stage C24 evidence root
- the fixed confirmation token

It contains exactly one fixed `exec sudo env … python3 -m …v11` path. It exposes no arbitrary command, destination, service, route, mixer, approval, lock or transaction selector.

## Successful physical sequence

1. Validate exact package, baseline, C21, C22 and frozen C23 inputs.
2. Observe the accepted live appliance baseline read-only.
3. Acquire the canonical production lock.
4. Create one fresh authoritative transaction and five-domain snapshot.
5. Stage and privately validate all 28 candidate files.
6. Re-prove ordinary and approval operation boundaries.
7. Stop only captured-active application services in order:
   - dashboard
   - Shairport Sync
   - Plexamp
8. Prove physical DAC and fixed loopback endpoints are released.
9. Atomically install all 28 files and verify path, inode, type, mode, owner and digest binding.
10. Re-prove active route selection remains blocked.
11. Perform daemon-reload attempt one.
12. Observe exactly three managed units as:
    - loaded
    - inactive
    - dead
    - expected disabled/static unit-file state
    - exact `/etc/systemd/system/…` fragment path
13. Remove every exact installed inode and only transaction-created directories.
14. Refuse application-service restoration while systemd manager rollback remains pending.
15. Perform daemon-reload attempt two.
16. Observe all three managed units as:
    - not-found
    - inactive
    - dead
    - no fragment path
17. Restore captured application services in order:
    - Plexamp
    - Shairport Sync
    - dashboard
18. Verify dashboard health and exact filesystem, service, route, mixer, loopback and DAC restoration.
19. Refuse older lifecycle closures.
20. Close through the typed C24 closure.
21. Remove the authoritative transaction and restore parent state.
22. Release the canonical production lock.
23. Re-observe the full accepted live baseline.
24. Re-fingerprint all retained inputs and seal the evidence tree.

## Exact 54-check evidence contract

1. `root-scope`
2. `package-replay`
3. `baseline-replay`
4. `stage-c21-evidence-replay`
5. `stage-c22-evidence-replay`
6. `stage-c23-evidence-replay`
7. `pre-lock-live-baseline`
8. `protocol-conformance`
9. `pre-lock-host-contract`
10. `pre-lock-boundary`
11. `production-lock-acquired`
12. `authoritative-transaction-created`
13. `transaction-identity-binding`
14. `filesystem-snapshot`
15. `service-snapshot`
16. `mixer-snapshot`
17. `loopback-snapshot`
18. `dac-snapshot`
19. `snapshot-integrity`
20. `candidate-staging`
21. `candidate-manifest-binding`
22. `candidate-alsa-validation`
23. `candidate-sudoers-validation`
24. `candidate-unit-validation`
25. `candidate-camilladsp-validation`
26. `blocked-operation-boundary`
27. `approval-operation-boundary`
28. `pre-mutation-boundary`
29. `service-quiescence`
30. `dac-release`
31. `managed-file-installation`
32. `installed-manifest-binding`
33. `post-install-route-boundary`
34. `systemd-candidate-reload`
35. `systemd-candidate-unit-visibility`
36. `exact-filesystem-rollback`
37. `pre-manager-rollback-service-refusal`
38. `systemd-manager-rollback`
39. `systemd-rollback-unit-absence`
40. `application-service-restoration`
41. `dashboard-health`
42. `exact-rollback-verification`
43. `exact-restoration-boundary`
44. `pre-mutation-abort-refusal`
45. `service-only-closure-refusal`
46. `c23-closure-refusal`
47. `candidate-evidence-copy`
48. `exact-rollback-close-c24`
49. `exact-transaction-cleanup`
50. `production-lock-released`
51. `post-lock-live-baseline`
52. `input-integrity`
53. `evidence-integrity`
54. `activation-interface`

## Failure behavior

After any managed-file or systemd-manager mutation, exception cleanup must attempt restoration in this order:

1. exact managed-file and created-directory rollback
2. systemd-manager rollback, if one attempt remains
3. captured application-service restoration
4. inherited exact baseline verification and transaction cleanup

If exact filesystem rollback, systemd-manager rollback or required restoration cannot be proved, the adapter raises before inherited cleanup and deliberately retains:

- the canonical production lock
- the authoritative transaction
- snapshots and ledgers
- the Stage C24 evidence root

No manual cleanup, rerun or third daemon-reload is permitted before inspection.

## Explicitly blocked or absent

Stage C24 has no authority to:

- select split-bus or direct-failback routes
- write mixer values
- start or stop managed Stage C services
- start CamillaDSP
- verify split-bus runtime health
- run finite music or alarm probes
- write a commit manifest
- publish, promote or revoke approval
- activate persistent Stage C
- prove reboot persistence
- make PR #2 ready
- merge PR #2
- invoke `scripts/install-master-eq.sh`

## Approval boundary

Repository preparation does not authorise the physical Stage C24 rehearsal. A new explicit approval must bind the final prepared branch head and acknowledge:

- brief Plexamp, AirPlay and dashboard interruption
- temporary creation of all 28 fixed managed files
- a hard budget of exactly two daemon-reload attempts
- mandatory exact filesystem, manager and service rollback

That approval does not extend to route selection, mixer mutation, CamillaDSP, audio probes, approval publication, installation commit, activation, reboot persistence, PR readiness or merge.
