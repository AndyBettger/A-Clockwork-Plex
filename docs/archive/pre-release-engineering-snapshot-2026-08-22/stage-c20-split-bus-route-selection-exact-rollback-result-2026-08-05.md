# Stage C20 split-bus route selection and exact rollback rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C20 repeated the physically accepted Stage C19 lock, authoritative transaction, five-domain snapshot, candidate staging and validation, application-service quiescence, DAC release, twelve-file installation, first systemd reload and managed-unit visibility proof.

It then crossed the first production active-route mutation boundary. While Plexamp, Shairport Sync and the dashboard remained stopped and both the physical DAC and fixed loopback playback endpoints remained released, the adapter selected the reviewed split-bus ALSA route exactly once by atomic inode exchange. No service or PCM was started.

The selected active route was bound to the installed transaction candidate by path, type, device, inode, mode, ownership and SHA-256 digest. The exact original direct-route inode remained parked under the adapter-generated private rollback name. All nine later managed-service, audio, direct-failback, commit and restoration operations remained blocked after route selection.

Rollback atomically exchanged the original direct-route inode back into the active ALSA pathname and removed only the exact candidate inode. The twelve managed files and transaction-created directories were then restored to the authoritative filesystem snapshot. A second fixed `systemctl daemon-reload` restored systemd's manager view and proved all three managed units were `not-found`, inactive and dead.

Only after route, filesystem and manager restoration had been proved did the adapter restore Plexamp, Shairport Sync and the dashboard, wait for dashboard and strict DAC readiness, and verify zero filesystem, route, service, mixer, loopback or DAC mismatch.

The route-aware rollback transaction closed through the typed v6 lifecycle operation. The authoritative transaction was removed and the production lock was released only after every restoration domain had passed.

No managed Stage C service was started. No split-bus health check, music probe or alarm probe ran. No direct-failback route was selected. No mixer control changed. No install commit was written. Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c20-route-selection-rollback.JUiQ87
```

Retain this directory together with the complete Stage C evidence chain until final Stage C release review.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C19 result  /var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.knbfOY
```

Both input trees remained unchanged.

## Transaction identities

```text
Production lock lease  stage-c14-lock-facbb53afe917818325af32e
Transaction            stage-c15-install-a6a961c14758994574daaace
```

The lock, transaction, snapshot, package and action identities remained adapter-generated and bound for the complete rehearsal.

## Exact acceptance checks

All fifty checks passed in the required order:

```text
root-scope                        PASS
input-replay                      PASS
protocol-conformance              PASS
pre-lock-host-contract            PASS
pre-lock-boundary                 PASS
production-lock-acquired          PASS
authoritative-transaction-created PASS
transaction-identity-binding      PASS
filesystem-snapshot               PASS
service-snapshot                  PASS
mixer-snapshot                    PASS
loopback-snapshot                 PASS
dac-snapshot                      PASS
snapshot-integrity                PASS
candidate-staging                 PASS
candidate-manifest-binding        PASS
candidate-alsa-validation         PASS
candidate-sudoers-validation      PASS
candidate-unit-validation         PASS
candidate-camilladsp-validation   PASS
blocked-operation-boundary        PASS
route-selection-gate              PASS
service-quiescence                PASS
dac-release                       PASS
managed-file-installation         PASS
installed-manifest-binding        PASS
systemd-candidate-reload          PASS
managed-unit-visibility           PASS
split-bus-route-selection         PASS
selected-route-binding            PASS
post-route-boundary               PASS
active-route-restoration          PASS
exact-filesystem-rollback         PASS
systemd-manager-restoration       PASS
managed-unit-forgetting           PASS
application-service-restoration   PASS
dashboard-health                  PASS
exact-rollback-verification       PASS
exact-restoration-boundary        PASS
pre-mutation-abort-refusal        PASS
service-only-closure-refusal      PASS
file-only-closure-refusal         PASS
systemd-only-closure-refusal      PASS
candidate-evidence-copy           PASS
route-rollback-close-v6           PASS
exact-transaction-cleanup         PASS
production-lock-released          PASS
input-integrity                   PASS
evidence-integrity                PASS
activation-interface              PASS
```

## Operation boundary

The adapter exposed twenty-four permitted v1 operations together with the typed v2, v3, v4, v5 and v6 lifecycle methods.

The nine later operations remained blocked both before and after route selection:

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

The route operation itself was also proved state-gated before service quiescence, installation and the first daemon reload.

The blocked-operation proof was retained twice:

```text
blocked-operations.tsv
post-route-blocked-operations.tsv
```

No generic command, arbitrary route path, arbitrary unit name, keep-active mode or activation interface existed.

## Atomic route selection and rollback

The route source and active destination were fixed:

```text
source       /etc/a-clockwork-plex/audio-routes/split-bus.conf
destination  /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
```

The selected split-bus route used Linux `renameat2(RENAME_EXCHANGE)` inside one already-open, non-symlinked parent directory. The original direct-route inode was never unlinked or reconstructed.

The retained audit is:

```text
route-selection-actions.tsv
```

It records:

1. preparation of the private candidate route inode;
2. the single forward atomic exchange;
3. active-route candidate binding;
4. the reverse atomic exchange;
5. exact candidate-inode removal;
6. proof that the original active inode returned.

The corrected rollback derived the exchange phase from the two exact on-disk device/inode identities rather than trusting only an in-memory flag written after the exchange syscall. This covered interruption immediately after either exchange.

## Systemd-manager rollback

Exactly two fixed daemon reloads ran:

1. after all twelve candidate files were installed;
2. after active-route and managed-file rollback completed.

After the first reload, exactly three managed units were proved loaded, inactive, dead and not enabled. After the second reload, all three were proved `not-found`, inactive and dead.

The retained manager evidence is:

```text
systemd-reload-actions.tsv
systemd-unit-observations.tsv
```

Application services could not restart until the active route, managed files and manager view were all restored.

## Exact restoration proof

The rehearsal ended with zero mismatch across every authoritative domain:

- the original active ALSA route returned with the exact captured device, inode, bytes, SHA-256 digest, mode and ownership;
- the split-bus candidate inode was absent;
- all twelve managed destinations and transaction-created directories matched the filesystem snapshot;
- all three managed units were absent from systemd's manager view;
- the three captured-active application services were active again;
- the exact four-control mixer state matched the snapshot;
- the fixed `snd_aloop` state matched the snapshot;
- the physical DAC returned with the strict accepted runtime contract and one structured owner;
- the dashboard HTTP endpoint returned healthy after restoration.

The v2 pre-mutation abort, v3 service-only closure, v4 file-only closure and v5 systemd-only closure all correctly refused the later route-mutation history. Only the v6 route-aware exact-rollback closure accepted the transaction.

Final typed state:

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
reusable_for_activation   false
reusable_for_rollback     false
```

## Retained evidence

```text
results.tsv
identity.tsv
service-actions.tsv
managed-file-actions.tsv
systemd-reload-actions.tsv
systemd-unit-observations.tsv
route-selection-actions.tsv
restoration-readiness.tsv
typed-operations.json
blocked-operations.tsv
post-route-blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
evidence-manifest.tsv
report.txt
```

The candidate and transaction copies are non-authoritative review evidence and must not be reused for activation or rollback.

## Production state after Stage C20

The accepted direct appliance state remains authoritative:

```text
Plexamp -> acp_plexamp --\
AirPlay -> acp_airplay ---+-> acp_master -> acp_dmix -> DAC
Alarm   -> acp_alarm -----/
```

The temporary managed files are absent. The original direct-route inode is active. The three managed Stage C units are absent from systemd's manager view. The application services are restored. The production lock and authoritative transaction are absent.

Persistent Stage C activation remains blocked. The blocked bare installer must not be run, and PR #2 must remain Draft, open and unmerged without explicit approval.
