# Stage C22 current-package service-quiescence rehearsal accepted — 2026-08-06

## Acceptance

Stage C22 passed on `plexamp-bedroom` from exact approved branch head:

```text
6ade2a42e99ce1491f4fcc00632669ee26259cfb
```

The approved scope was limited to the current-package service-quiescence and exact-restoration rehearsal. It authorised a brief interruption of Plexamp, Shairport Sync and the dashboard, but did not authorise managed-file installation, systemd reload, route or mixer mutation, approval publication, CamillaDSP startup, audio probes, activation, reboot persistence, PR readiness or merge.

The rehearsal generated its report at:

```text
2026-08-06T05:54:43+01:00
```

## Fixed accepted inputs

```text
Package:
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo

Package fingerprint:
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

Baseline:
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac

Stage C21 evidence:
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg

Stage C21 evidence-manifest SHA-256:
a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff

CamillaDSP:
/tmp/a-clockwork-plex-camilladsp-4.1.3/bin/camilladsp

CamillaDSP version:
CamillaDSP 4.1.3 (05e9cfc)

CamillaDSP SHA-256:
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

All baseline report, report JSON and manifest hashes matched the accepted C21 values before guarded execution.

## Accepted Stage C22 evidence

```text
Evidence root:
/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL

Console log:
/var/tmp/a-clockwork-plex-stage-c22-console.3Kru2L

Exact exported source:
/var/tmp/a-clockwork-plex-stage-c22-source.0ALFFq

Fetch root:
/var/tmp/a-clockwork-plex-stage-c22-fetch.xeflSZ

Transaction identity:
stage-c22-service-rehearsal-install-909864154268c552f10903b6

Snapshot identity:
stage-c22-service-rehearsal-snapshot-909864154268c552f10903b6

Production-lock lease:
stage-c14-lock-f0079b99b5a0ea2bef31b575
```

The evidence root contains the results, identity, input binding, service actions, restoration timing, candidate review copy, transaction rehearsal copy, checksummed evidence manifest and final report.

The command output did not print the Stage C22 evidence-manifest digest or row count. That is not a Stage C22 acceptance failure because `evidence-integrity` passed inside the guarded process, but any later stage that binds directly to this evidence must first capture and freeze that exact digest rather than infer it.

## Result

All 41 ordered checks passed.

The rehearsal proved:

- the exact accepted 28-file package and 27-payload fingerprint;
- the accepted baseline and accepted 32-check Stage C21 evidence;
- a fresh pre-lock live appliance state matching the accepted baseline;
- one real canonical production lock and one fresh authoritative transaction;
- exact filesystem, service, mixer, loopback and DAC snapshots;
- all 28 files staged and validated only inside the disposable transaction;
- all 14 later ordinary operations blocked;
- all four production approval operations blocked and absent;
- only captured-active Plexamp, Shairport Sync and dashboard services stopped;
- physical DAC and fixed loopback endpoints released;
- managed-file installation still blocked after DAC release;
- exact captured application-service state restored;
- dashboard health and strict restored DAC ownership proved;
- pre-mutation abort refused after the service-mutation boundary;
- typed restored-transaction closure accepted and removed the transaction;
- production lock released only after exact restored closure;
- full accepted live baseline re-observed after lock release;
- package, baseline and Stage C21 evidence inputs unchanged;
- complete evidence tree regular and checksummed;
- no activation interface exposed.

The final transaction state was:

```text
service-rehearsal-restored-and-closed
```

Restored services:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
```

## Final observed state

```text
guarded_run_status=0
transaction_root=absent
plexamp.service=active,enabled
shairport-sync.service=active,enabled
a-clockwork-plex.service=active,enabled
checkout_unchanged=true
```

The local Pi checkout remained deliberately stale and dirty at:

```text
b83bf347a215c38d002ab3273097787d5e6de68b
```

Its status fingerprint was unchanged:

```text
f8fee5a892fdb9f30a3b14e57c4fa941d49296ee93048f4d856cfe91b9132212
```

## Diagnostic-command qualification

The ad-hoc outer diagnostic command checked:

```text
/run/lock/a-clockwork-plex-stage-c.lock
```

That was an old/non-authoritative pathname. Therefore its printed `production_lock=absent` line is not used as acceptance evidence.

The guarded Stage C22 rehearsal itself used the real canonical lock:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

It proved that lock absent before acquisition, acquired it, refused premature release, released it after exact restored transaction closure, and then passed the full `post-lock-live-baseline` check. Those internal typed checks are authoritative.

Similarly, the outer non-privileged convenience line:

```text
dac_owners=
```

is not used as proof of DAC state. The guarded `dashboard-health` operation proved the strict restored Plexamp DAC-owner contract and `post-lock-live-baseline` independently revalidated the accepted DAC state.

The first incorrect sudo-password entry was harmless. Privileged execution began only after successful authentication.

## Boundary retained

This accepted rehearsal did not prove or authorise:

- managed-file installation;
- `systemctl daemon-reload`;
- split-bus or direct route selection;
- mixer mutation;
- Stage C service startup;
- approval publication, removal or promotion;
- CamillaDSP startup;
- finite music or alarm probes;
- transaction commit;
- automatic rollback after file mutation;
- activation or reboot persistence;
- use of the blocked bare `scripts/install-master-eq.sh` path;
- making PR #2 ready or merging it.

Stage C22 is accepted as the first mutation-bearing reversible transaction prefix: captured application services can be quiesced, DAC release can be proved, and the exact accepted appliance state can be restored before the authoritative transaction and canonical lock are removed.
