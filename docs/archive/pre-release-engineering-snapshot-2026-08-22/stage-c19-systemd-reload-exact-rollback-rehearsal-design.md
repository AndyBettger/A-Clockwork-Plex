# Stage C19 systemd reload and exact-manager rollback rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C19 crosses the first systemd-manager mutation boundary in the immutable
Stage C install program. It extends the physically accepted Stage C18 prefix
through the existing typed operation:

```text
reload-systemd
```

The rehearsal installs the twelve reviewed files while the three application
services and the DAC are quiesced, executes one fixed `systemctl daemon-reload`,
and proves that systemd recognises exactly the three managed Stage C units while
none of them is active or enabled.

It then stops before active-route selection or managed-service startup. The
rehearsal removes the exact installed inodes through the authoritative
filesystem snapshot, performs a second fixed daemon reload, proves that systemd
has forgotten all three managed units, restores the captured application
services, and verifies the complete accepted direct appliance state.

No Stage C unit is started or enabled. No audio route is selected. No PCM or
audio probe is opened. No install commit is written. Persistent Stage C
activation remains blocked.

## Replayed evidence

The guarded rehearsal accepts only:

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C18 result  /var/tmp/a-clockwork-plex-stage-c18-managed-file-rollback.H3P4Po
```

The Stage C18 evidence must contain its exact forty-check PASS contract, eleven
blocked v4 operations, twelve-file installation and rollback evidence, the v4
exact-rollback closure, bounded restoration-readiness evidence, and no systemd
reload, route selection or commit.

## Exact physical boundary

The guarded rehearsal may:

1. replay and fingerprint the Stage C1 package and successful Stage C18 evidence;
2. inspect the fixed host and absent production lock;
3. acquire the one fixed production lock;
4. create a fresh generated authoritative install transaction;
5. capture exact filesystem, service, mixer, loopback and DAC state;
6. stage and validate all twelve reviewed files inside the transaction;
7. stop only the captured-active dashboard, Shairport Sync and Plexamp services;
8. prove the physical DAC and fixed loopback endpoints have no owners;
9. atomically install and verify exactly twelve manifest files;
10. execute one fixed `systemctl daemon-reload`;
11. query five fixed machine-readable properties for exactly three managed units;
12. prove those units are loaded, inactive, dead and not enabled;
13. prove route selection, managed-service startup, audio probes and commit remain
    unavailable after the manager has observed the files;
14. remove only the exact device/inode objects installed by this transaction;
15. restore every managed destination and directory to the authoritative
    filesystem snapshot;
16. execute a second fixed `systemctl daemon-reload`;
17. prove the three managed units are `not-found`, inactive and dead;
18. restore exactly the captured application-service state;
19. wait boundedly for dashboard HTTP and the strict DAC runtime contract;
20. verify zero filesystem, service, route, mixer, loopback or DAC mismatch;
21. retain non-authoritative candidate, installation, rollback, service,
    systemd-manager and transaction evidence;
22. close and remove the exact systemd-reload rollback transaction;
23. release the production lock only after exact manager rollback closure.

It may not:

- select the split-bus route;
- select the direct alarm-bypass route;
- start or stop a managed Stage C service;
- enable, disable, mask or unmask any unit;
- change any mixer control;
- start CamillaDSP;
- open a PCM or run a music/alarm probe;
- write an install commit;
- invoke later production mixer or service restoration operations;
- create an activation marker;
- retain any Stage C file or systemd-manager state;
- use the blocked bare master-EQ installer.

## Fixed systemd command boundary

The only executable systemd mutation is the literal command:

```text
systemctl daemon-reload
```

It is invoked exactly twice on a successful rehearsal:

```text
reload 1  after all twelve files are installed and verified
reload 2  after exact filesystem rollback while application services remain stopped
```

The caller cannot supply a command, action, unit, property or path. There is no
generic dispatcher and no shell command boundary.

The only systemd observations are fixed `systemctl show` calls for:

```text
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

Each observation requests only:

```text
LoadState
ActiveState
SubState
UnitFileState
FragmentPath
```

## Installed-unit visibility contract

After the first daemon reload, the exact accepted state is:

| Unit | LoadState | ActiveState | SubState | UnitFileState | FragmentPath |
|---|---|---|---|---|---|
| `a-clockwork-plex-audio-route.service` | `loaded` | `inactive` | `dead` | `disabled` | `/etc/systemd/system/a-clockwork-plex-audio-route.service` |
| `a-clockwork-plex-camilladsp.service` | `loaded` | `inactive` | `dead` | `disabled` | `/etc/systemd/system/a-clockwork-plex-camilladsp.service` |
| `a-clockwork-plex-audio-failback.service` | `loaded` | `inactive` | `dead` | `static` | `/etc/systemd/system/a-clockwork-plex-audio-failback.service` |

The route-authority and CamillaDSP units contain `[Install]` sections but no
wants symlink is created, so they must remain disabled. The failback unit has no
`[Install]` section and must remain static.

All three units contain the retained activation-marker condition. The marker
remains absent, but Stage C19 does not rely on the condition as its primary
safety boundary: no start command is available at all.

Any loaded, active, enabled, generated, masked, linked, aliased or substituted
state outside the exact table fails the rehearsal.

## Rolled-back systemd-manager contract

After the exact files and transaction-created directories have been removed, the
second daemon reload must produce this state for all three managed units:

```text
LoadState      not-found
ActiveState    inactive
SubState       dead
UnitFileState  not-found (an empty property is normalised to not-found)
FragmentPath   empty
```

Application services remain stopped throughout this proof. They may not restart
while systemd still remembers the temporary managed units.

## Mandatory failure recovery

Once the first daemon reload begins, every later failure owns both filesystem and
systemd-manager rollback.

The mandatory fixed recovery order is:

```text
remove exact managed file inodes
remove transaction-created directories
prove the authoritative filesystem snapshot
systemctl daemon-reload with managed files absent
prove all three managed units are not-found
restore Plexamp
restore Shairport Sync
restore the dashboard
verify dashboard and strict DAC readiness
```

If filesystem rollback fails, the application services are not restarted. If the
second daemon reload fails, or if any managed unit remains visible afterward,
the production lock and authoritative transaction are intentionally retained for
manual recovery evidence.

The inherited service-restoration cleanup is allowed to run only after the
adapter has proved exact systemd-manager restoration.

## Evidence

The evidence root adds:

```text
systemd-reload-actions.tsv
systemd-unit-observations.tsv
```

`systemd-reload-actions.tsv` records every daemon reload, its phase, monotonic
time and result. A successful run contains exactly two PASS reload rows.

`systemd-unit-observations.tsv` records the exact five-property state of each
managed unit after each reload. A successful run contains exactly six unit rows:
three installed/visible rows and three rolled-back/not-found rows.

The ordinary Stage C candidate, managed-file, service, readiness, typed-operation,
transaction-copy and evidence-manifest artefacts remain present.

## Operation boundary

The frozen histories remain unchanged:

```text
v1  33 original adapter operations
v2  34 operations, adding pre-mutation abort
v3  35 operations, adding restored-service rehearsal closure
v4  36 operations, adding exact-file-rollback rehearsal closure
```

Stage C19 defines a v5 view containing 37 operations by adding only:

```text
close-systemd-reload-rollback-rehearsal-transaction
```

Within the v5 view, Stage C19 permits:

- twenty-three v1 operations, adding only `reload-systemd` to the C18 set;
- the v2, v3, v4 and v5 lifecycle methods.

This gives:

```text
permitted  27
blocked    10
```

The ten blocked v1 operations remain:

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

## Versioned lifecycle closure

The v2 pre-mutation abort must refuse after service mutation. The v3
service-only closure must refuse after managed-file mutation. The v4 file-only
closure must refuse after systemd-manager mutation.

Only the v5 operation may close a successful Stage C19 transaction:

```text
close-systemd-reload-rollback-rehearsal-transaction
```

Its receipt must prove:

```text
state                       systemd-reload-rolled-back-and-closed
mutation_started            true
managed_files_installed     true
systemd_reloaded            true
filesystem_restored         true
systemd_manager_restored    true
services_restored           true
daemon_reload_count         2
route_selected              false
committed                   false
transaction_path_absent     true
parents_restored            true
installed_file_count        12
```

The v5 implementation may reuse the physically accepted v3 transaction-copy and
exact-cleanup mechanics internally, but it must write only the systemd-aware v5
final state. The public v4 closure remains a typed refusal.

## Success criteria

Stage C19 passes only if:

- the exact successful Stage C18 evidence is replayed;
- all candidate validation domains pass;
- application services stop and the DAC is released;
- exactly twelve files install and bind to the manifest;
- the first daemon reload succeeds;
- all three managed units are loaded but inactive and not enabled;
- all ten later v1 operations remain blocked;
- route selection and managed-service startup remain blocked after reload;
- exact filesystem rollback succeeds;
- the second daemon reload succeeds;
- all three managed units become not-found;
- application services restore only after manager restoration;
- dashboard, direct route, mixer, loopback and DAC state match the snapshot;
- v2, v3 and v4 closures refuse;
- v5 closure succeeds;
- the authoritative transaction and production lock are removed exactly;
- both input trees remain unchanged;
- the evidence tree is complete and checksummed;
- no activation or persistence interface exists.

## Deliberately deferred work

Stage C19 does not prove:

- split-bus or direct-failback route selection;
- managed route-authority or CamillaDSP service startup;
- split-bus runtime health;
- music or alarm audio probes;
- install commit;
- automatic failback after a running CamillaDSP failure;
- explicit uninstall;
- reboot persistence.

Those remain separate guarded stages. PR #2 must remain Draft, open and unmerged
until explicit approval.
