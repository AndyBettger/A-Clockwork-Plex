# Stage C19 systemd reload and exact-manager rollback rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C19 repeated the physically accepted Stage C18 lock, authoritative transaction, snapshot, candidate staging, validation, service-quiescence, DAC-release, twelve-file installation and installed-manifest verification prefix. It then crossed the first production systemd-manager mutation boundary while the three captured-active application services and the physical DAC remained quiesced.

The first fixed `systemctl daemon-reload` completed with all twelve candidate files installed. Machine-readable `systemctl show` observations proved that exactly the three managed Stage C units were visible to systemd and were loaded, inactive, dead and not enabled. All route-selection, managed-service, audio, commit and later-restoration operations remained blocked after that reload.

The adapter then removed only the exact managed inodes created by the transaction and restored all transaction-created directory state to the authoritative filesystem snapshot while the application services remained stopped. A second fixed `systemctl daemon-reload` completed with those files absent. Machine-readable observations then proved that all three temporary units were `not-found`, inactive and dead before any application service was restarted.

Only after exact filesystem and systemd-manager rollback had been proved did the adapter restore Plexamp, Shairport Sync and the dashboard, wait for dashboard and strict DAC readiness, and verify zero filesystem, service, route, mixer, loopback or DAC mismatch.

The systemd-aware rollback transaction closed through the typed v5 lifecycle operation, the authoritative transaction was removed, and the production lock was released only after exact filesystem, manager and appliance restoration had been proved.

No split-bus or direct-failback route was selected. No managed Stage C service was started, enabled, disabled, masked or unmasked. No mixer control changed. No PCM or audio probe was opened. No install commit was written. Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c19-systemd-reload-rollback.knbfOY
```

Retain this directory together with the complete Stage C evidence chain until final Stage C release review.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C18 result  /var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.H3P4Po
```

Both input trees remained unchanged.

## Transaction identities

```text
Production lock lease  stage-c14-lock-50d702698334bdb122933057
Transaction            stage-c15-install-f60583ca0433d2dc6fad4a38
```

The lock, transaction, snapshot, package and action identities remained adapter-generated and bound for the complete rehearsal.

## Exact acceptance checks

All forty-five checks passed in the required order:

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
service-quiescence                PASS
dac-release                       PASS
managed-file-installation         PASS
installed-manifest-binding        PASS
systemd-candidate-reload          PASS
managed-unit-visibility           PASS
post-reload-boundary              PASS
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
candidate-evidence-copy           PASS
systemd-rollback-close-v5         PASS
exact-transaction-cleanup         PASS
production-lock-released          PASS
input-integrity                   PASS
evidence-integrity                PASS
activation-interface              PASS
```

## Operation boundary

The adapter exposed twenty-three permitted v1 operations together with the typed v2, v3, v4 and v5 lifecycle methods.

The ten later operations remained blocked both before and after the first daemon reload:

```text
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

The blocked-operation proof was retained twice:

```text
blocked-operations.tsv
post-reload-blocked-operations.tsv
```

No generic command, arbitrary unit name, arbitrary property, route override or keep-active interface existed.

## Systemd-manager mutation and rollback

Exactly two fixed daemon reloads were permitted:

1. candidate files installed, application services stopped and DAC released;
2. exact filesystem rollback complete, application services still stopped.

The first reload established candidate visibility. The second reload restored the manager view after the files were removed.

The retained manager evidence is:

```text
systemd-reload-actions.tsv
systemd-unit-observations.tsv
```

After the first reload, each managed unit was proved:

```text
LoadState      loaded
ActiveState    inactive
SubState       dead
UnitFileState  disabled or static according to the reviewed unit
FragmentPath   exact reviewed /etc/systemd/system destination
```

After exact filesystem rollback and the second reload, each managed unit was proved:

```text
LoadState      not-found
ActiveState    inactive
SubState       dead
UnitFileState  empty
FragmentPath   empty
```

Application-service restoration was gated on this second proof. Plexamp, Shairport Sync and the dashboard could not restart while the temporary Stage C units remained visible to the manager.

## Exact restoration proof

The rehearsal ended with zero mismatch across all authoritative domains:

- all twelve managed destinations and transaction-created directories matched the filesystem snapshot;
- the three captured-active application services were active again;
- the accepted direct ALSA route was restored unchanged;
- the exact four-control mixer state matched the snapshot;
- the fixed `snd_aloop` state matched the snapshot;
- the physical DAC returned with the strict accepted runtime contract and one structured owner;
- the dashboard HTTP endpoint returned healthy after restoration.

The v2 pre-mutation abort, v3 service-only closure and v4 file-only closure all correctly refused the later mutation history. Only the v5 systemd-aware exact-rollback closure accepted the transaction.

Final typed state:

```text
state                 systemd-reload-rolled-back-and-closed
mutation_started      true
managed_files_installed true
filesystem_restored   true
systemd_reloaded      true
systemd_manager_restored true
services_restored     true
route_selected        false
committed              false
daemon_reload_count    2
reusable_for_activation false
reusable_for_rollback   false
```

## Retained evidence

```text
results.tsv
identity.tsv
service-actions.tsv
managed-file-actions.tsv
systemd-reload-actions.tsv
systemd-unit-observations.tsv
restoration-readiness.tsv
typed-operations.json
blocked-operations.tsv
post-reload-blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
evidence-manifest.tsv
report.txt
```

The candidate and transaction copies are non-authoritative review evidence and must not be reused for activation or rollback.

## Production state after Stage C19

The accepted direct appliance state remains authoritative:

```text
Plexamp -> acp_plexamp --\
AirPlay -> acp_airplay ---+-> acp_master -> acp_dmix -> DAC
Alarm   -> acp_alarm -----/
```

The temporary managed files are absent. The three managed Stage C units are absent from systemd's manager view. The application services are restored. The production lock and authoritative transaction are absent.

Persistent Stage C activation remains blocked. The blocked bare installer must not be run, and PR #2 must remain Draft, open and unmerged without explicit approval.
