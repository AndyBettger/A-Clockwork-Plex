# Stage C20 split-bus route selection and exact rollback rehearsal design

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: designed and automated only; physical rehearsal not yet approved

## Purpose

Stage C20 advances one deliberate production boundary beyond the physically
accepted Stage C19 systemd-manager rehearsal.

Stage C19 proved that the twelve reviewed files can be installed, exposed to
systemd through one daemon reload, removed exactly, forgotten through a second
daemon reload, and followed by exact application and audio-state restoration.
It did not change the active ALSA route.

Stage C20 adds exactly one temporary route-selection mutation:

```text
/etc/a-clockwork-plex/audio-routes/split-bus.conf
        ↓ one atomic exchange
/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
```

The application services remain stopped and the physical DAC and fixed loopback
playback endpoints remain released throughout route selection and rollback. No
PCM is opened. No managed Stage C service starts. The selected route is restored
before the twelve files are removed, before the second daemon reload, and before
any application service restarts.

Persistent Stage C activation remains blocked.

## Accepted input chain

The guarded rehearsal accepts only:

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C19 result  /var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.knbfOY
```

The Stage C19 input must contain the exact forty-five PASS checks, both ten-row
blocked-operation files, the successful v5 closed state, two daemon reloads,
exact filesystem and manager restoration, restored application services,
`route_selected=false`, `committed=false`, and non-reusable evidence labels.

Neither retained input is activation-authoritative. Both must remain unchanged.

## Exact operation boundary

The v6 contract contains thirty-eight operations in total.

```text
permitted  29
blocked     9
```

The twenty-four permitted v1 operations are the accepted C19 set plus:

```text
select-split-bus-route
```

The five permitted lifecycle operations are the inherited v2 through v5 methods
plus the new v6 closure. The inherited v2, v3, v4 and v5 closure methods must
refuse after route mutation. Only this v6 operation may close the successful
transaction:

```text
close-route-selection-rollback-rehearsal-transaction
```

The nine blocked operations are:

```text
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

The route-selection method is also state-gated before the first daemon reload.
Being permitted by the adapter vocabulary does not make it executable out of
order.

## Fixed success sequence

```text
1. replay Stage C1 and successful Stage C19 evidence
2. verify the stable direct host contract
3. acquire the fixed production lock
4. create one authoritative transaction and five-domain snapshot
5. stage and validate all twelve candidate files privately
6. prove the nine later operations remain blocked
7. prove split-bus route selection refuses before its prerequisites
8. stop only captured-active Plexamp, Shairport Sync and dashboard services
9. prove the DAC and fixed loopback playback endpoints are released
10. install and verify exactly twelve managed files
11. perform the first fixed systemctl daemon-reload
12. prove exactly three managed units are loaded but inactive
13. atomically exchange the reviewed split-bus route into the active pathname
14. prove the selected active inode and digest match the transaction candidate
15. prove all nine later operations remain blocked after route selection
16. atomically exchange the original active-route inode back
17. remove only the parked candidate inode
18. remove the twelve managed files and restore created directories exactly
19. perform the second fixed systemctl daemon-reload
20. prove all three managed units are not-found
21. restore captured application-service state
22. wait for dashboard and strict physical-DAC readiness
23. prove zero filesystem, route, service, mixer, loopback or DAC mismatch
24. prove v2, v3, v4 and v5 closures refuse the later mutation history
25. retain non-authoritative candidate and transaction review copies
26. close through the typed v6 lifecycle
27. remove the authoritative transaction
28. release the exact production lock
```

## Active-route exchange mechanism

A normal replacement would unlink the original active route and create a new
inode during rollback. Stage C20 instead uses Linux `renameat2` with
`RENAME_EXCHANGE` inside one already-open, non-symlinked parent directory.

Before the exchange:

```text
99-a-clockwork-plex-shared.conf              original direct-route inode
.99-a-clockwork-plex-shared.conf.stage-c20-<random>.rollback
                                              prepared split-bus candidate inode
```

After the first atomic exchange:

```text
99-a-clockwork-plex-shared.conf              split-bus candidate inode
private .rollback name                       original direct-route inode
```

Rollback performs the same atomic exchange in reverse. It then verifies that the
private name contains the exact candidate device/inode before unlinking it.
The original active route therefore returns with the same bytes, SHA-256, mode,
ownership, device and inode captured immediately before selection.

The private name does not end in `.conf`, so ALSA's ordinary configuration hook
does not treat it as another active fragment.

No interval exists in which the active route pathname is absent.

## Route source and destination

The route source and destination are constants, not caller inputs:

```text
source       /etc/a-clockwork-plex/audio-routes/split-bus.conf
destination  /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
```

The source must be the exact installed object already bound to the transaction
candidate by path, type, device, inode, mode, owner and SHA-256 digest.

The destination must still match the authoritative snapshot's mode, owner and
SHA-256 digest before route preparation. The authoritative snapshot copy must
remain a regular file beneath the transaction's `snapshot/rootfs` tree.

## Failure ownership

### Failure before candidate creation

No route object exists. The inherited C19 rollback owns managed files, systemd
manager state and application services.

### Failure while preparing the private candidate

The adapter records the candidate device and inode immediately after exclusive,
non-following creation. Any partial candidate is removed only after exact
identity verification. The active route must still match the original identity.

### Failure after atomic exchange

The route adapter must first exchange the original route back and remove the
exact parked candidate inode. Only then may inherited cleanup remove managed
files, reload systemd with those files absent and restore application services.

### Route rollback failure

The production lock and authoritative transaction are intentionally retained.
No application service restart is attempted. Manual recovery must inspect the
recorded route ledger and both names; no pathname is removed by assumption.

### Later failure

Once exact route restoration has passed, inherited C19 cleanup owns:

```text
managed-file rollback
→ systemd-manager rollback
→ application-service restoration
```

## Evidence

The new route audit is:

```text
route-selection-actions.tsv
```

It records ordered preparation, selection, rollback and cleanup actions with the
original and candidate inode and digest identities.

The transaction also records:

```text
route-selection-rollback.tsv
lifecycle-v6.tsv
```

The final v6 receipt requires:

```text
state                    split-bus-route-rolled-back-and-closed
mutation_started         true
managed_files_installed  true
systemd_reloaded         true
split_bus_route_selected true
active_route_restored    true
filesystem_restored      true
systemd_manager_restored true
services_restored        true
committed                 false
transaction_path_absent   true
parents_restored          true
installed_file_count      12
daemon_reload_count       2
route_selection_count     1
```

## Explicitly not proved

Stage C20 does not prove:

- starting the route-authority service;
- starting CamillaDSP;
- the split-bus route with a live source service;
- split-bus runtime health;
- finite music or alarm probes;
- direct-failback route selection;
- automatic CamillaDSP failure handling;
- a commit manifest;
- persistent installation, reboot behaviour, rollback or uninstall.

## Prepare-only and physical gate

The wrapper defaults to prepare-only. Prepare-only must use no `sudo`, perform no
host observation, stop no service, write no managed or route file, reload no
systemd manager, and create no evidence directory, lock or transaction.

A later guarded physical rehearsal must require the exact token:

```text
STAGE-C20-SPLIT-BUS-ROUTE-EXACT-ROLLBACK
```

There is no keep-active mode.

The blocked bare installer must not be run. PR #2 must remain Draft, open and
unmerged until explicit approval is given.
