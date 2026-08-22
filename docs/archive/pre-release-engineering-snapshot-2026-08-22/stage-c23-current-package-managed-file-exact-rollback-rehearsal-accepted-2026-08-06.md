# Stage C23 current-package managed-file exact-rollback rehearsal accepted — 2026-08-06

## Acceptance

Stage C23 passed on `plexamp-bedroom` from exact approved branch head:

```text
9b1e5612c62bb66c3a0939b3b3ad90897b6bcbc3
```

The approval authorised one current-package managed-file installation and mandatory exact-rollback rehearsal. It authorised the temporary creation of all 28 fixed managed files and a brief interruption of Plexamp, Shairport Sync and the dashboard. It did not authorise systemd daemon reload, route selection, mixer mutation, CamillaDSP startup, audio probes, approval publication, installation commit, activation, reboot persistence, PR readiness or merge.

The rehearsal generated its report at:

```text
2026-08-06T07:07:52+01:00
```

## Fixed accepted inputs

```text
Package:
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo

Package fingerprint:
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

Package files:
28

Fingerprinted payload files:
27

Baseline:
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac

Baseline report.txt SHA-256:
350ae99ee63911cb524f7220e4629e5da669f3c79f8e409d2f9fdf4652c16a85

Baseline report.json SHA-256:
3c6dcd3c17a3ce363ddf3f5bdd9d93c8891a2a006c0c154905a3a809b79348e0

Baseline manifest.json SHA-256:
4995bdf85cb06995a9b26c164fdc28991d755631e9c4dbe527eddc005253c1dc

Stage C21 evidence:
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg

Stage C21 evidence-manifest SHA-256:
a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff

Stage C22 evidence:
/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL

Stage C22 evidence-manifest SHA-256:
4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb

Stage C22 evidence-manifest rows:
140

Stage C22 evidence-manifest entries:
139
```

All retained hashes, exact package identity and prior evidence contracts passed before the canonical production lock was acquired.

## Accepted Stage C23 evidence

```text
Evidence root:
/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG

Console log:
/tmp/acp-stage-c23-20260806T070746+0100-console.txt

Exact exported source:
/var/tmp/a-clockwork-plex-stage-c23-source.z5zoTH

Fetch root:
/var/tmp/a-clockwork-plex-stage-c23-git.17blT0

Transaction identity:
stage-c23-managed-file-rollback-install-7e309a9bbce196b09f3f79d4

Snapshot identity:
stage-c23-managed-file-rollback-snapshot-7e309a9bbce196b09f3f79d4

Production-lock lease:
stage-c14-lock-fa53845becd969695d720a75

Evidence-manifest SHA-256:
e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a

Evidence-manifest rows:
144
```

The evidence tree contains the ordered results, identity and input binding, service actions, managed-file actions, restoration readiness, candidate review copy, transaction rehearsal copy, checksummed evidence manifest and final report.

## Result

All 47 ordered checks passed.

The rehearsal proved:

- exact replay of the accepted package, baseline, 32-check Stage C21 evidence and immutable 41-check Stage C22 evidence;
- a fresh pre-lock live appliance state matching the accepted baseline;
- one canonical production lock and one fresh authoritative five-domain transaction snapshot;
- all 28 files staged and validated privately before any service or filesystem mutation;
- all 11 later non-C23 ordinary operations refused exactly;
- all four production approval operations blocked and absent;
- only captured-active Plexamp, Shairport Sync and dashboard services stopped;
- physical DAC and fixed loopback endpoints released;
- all 28 managed files atomically installed while services and DAC were quiesced;
- every installed type, inode, mode, owner and digest matched the transaction candidate;
- systemd reload and route selection remained blocked after installation;
- every installed inode and only transaction-created directories removed through the exact rollback ledger;
- filesystem rollback completed before service restoration;
- exact captured application-service state restored;
- dashboard HTTP health and the accepted direct route, mixer, loopback and DAC contract restored;
- zero filesystem, service, route, mixer, loopback or DAC mismatch remained;
- invalid pre-mutation and service-only closure paths refused after file mutation;
- typed C23 closure accepted only the adapter-generated 28-file exact-rollback transaction;
- transaction and transaction-created parent directories removed before lock release;
- full accepted live baseline re-observed after lock release;
- package, baseline, Stage C21 and Stage C22 evidence trees unchanged;
- complete evidence tree regular and checksummed;
- no activation interface exposed.

The final transaction state was:

```text
current-package-managed-files-rolled-back-and-closed
```

The identity record confirms:

```text
mutation_started=true
managed_files_installed=true
filesystem_restored=true
services_restored=true
systemd_reloaded=false
route_selected=false
committed=false
reusable_for_activation=false
reusable_for_rollback=false
```

## Final observed state

```text
guarded_run_status=0
production_lock=absent
transaction_root=absent
split_bus_root=absent
plexamp.service=active,enabled
shairport-sync.service=active,enabled
a-clockwork-plex.service=active,enabled
checkout_unchanged=true
evidence_results=47/47_PASS
Stage C23 guarded_status=0
Stage C23 child_status=0
```

The local Pi checkout remained deliberately stale and dirty at:

```text
b83bf347a215c38d002ab3273097787d5e6de68b
```

Its before/after status fingerprint remained exactly:

```text
df90c816beda953409f306a46789ba34649541e3339215d3e7d552c0f6857f91
```

The retained modification remained:

```text
 M scripts/launch-dashboard-kiosk.sh
```

## Preflight qualification

The first attempted command stopped before guarded execution because its external convenience preflight incorrectly required these transaction-owned paths to pre-exist:

```text
/var/lib/a-clockwork-plex/split-bus
/var/lib/a-clockwork-plex/split-bus/transactions
```

That first attempt did not reach the guarded wrapper, acquire the production lock, create a transaction, stop a service or install a managed file. A subsequent read-only diagnostic proved both paths correctly absent, the canonical lock absent and all application services active and enabled.

The corrected preflight then treated those paths according to the adapter contract: they may begin absent, are created only after lock acquisition, and are removed during exact rollback when the authoritative snapshot records them as absent. The successful guarded rehearsal proved both paths absent again at completion.

The first failed sudo-password entry during the stopped preflight was harmless. Privileged execution began only after successful authentication.

The outer post-run `fuser` convenience display printed no DAC-owner row. It is not used as acceptance proof. The guarded `dashboard-health`, `exact-rollback-verification` and `post-lock-live-baseline` checks independently proved the accepted restored DAC contract.

## Boundary retained

This accepted rehearsal did not prove or authorise:

- `systemctl daemon-reload` with installed units;
- split-bus or direct-failback route selection;
- mixer mutation;
- startup or runtime health of managed Stage C services;
- CamillaDSP startup;
- finite music or alarm probes;
- approval publication, removal or promotion;
- transaction commit;
- persistent installation or activation;
- reboot persistence;
- use of the blocked bare `scripts/install-master-eq.sh` path;
- making PR #2 ready or merging it.

Stage C23 is accepted as the first physically exercised current-package filesystem mutation and exact rollback boundary: all 28 reviewed files can be atomically installed under service and DAC quiescence, verified by exact identity, removed through the authoritative inode ledger, and followed by complete appliance restoration before transaction and lock release.
