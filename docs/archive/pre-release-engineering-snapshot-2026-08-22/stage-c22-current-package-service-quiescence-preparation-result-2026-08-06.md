# Stage C22 current-package service-quiescence preparation — result

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Result: **PASS — repository implementation and automated validation complete; Pi execution remains separately gated**

## Outcome

The first reversible current-package mutation prefix is prepared without running
another command on `plexamp-bedroom`.

Stage C22 binds the accepted Stage C21 package, baseline and 32-check evidence to
the physically exercised Stage C17 service-quiescence and exact-restoration
mechanism. It does not create a second service-control owner or a second
transaction stack.

The guarded rehearsal is bounded to:

```text
replay accepted package, baseline and Stage C21 evidence
→ fresh full read-only baseline observation
→ acquire canonical production lock
→ create one fresh authoritative transaction
→ capture all five authoritative snapshot domains
→ stage and validate all 28 current package files privately
→ prove later ordinary and approval operations blocked
→ stop only captured-active Plexamp, Shairport Sync and dashboard
→ prove DAC and fixed loopback endpoints released
→ prove installation remains blocked
→ restore exact captured application state
→ verify dashboard and bounded DAC readiness
→ close and remove the restored rehearsal transaction
→ release the production lock
→ re-observe the complete accepted baseline
```

It stops before managed-file installation.

## Accepted inputs

```text
package root
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo

package fingerprint
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

baseline root
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac

accepted Stage C21 root
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg

Stage C21 checks
32 / 32 PASS

Stage C21 evidence-manifest rows
139

Stage C21 evidence-manifest SHA-256
a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff
```

## Architecture

### Current-package transaction owner

```text
scripts/stage_c_transaction/current_package_candidate_rehearsal_adapter_v7.py
```

It continues to own:

- the canonical production lock;
- the authoritative transaction and five snapshots;
- the accepted current package and 28-file destination boundary;
- transaction-private staging and current candidate validation.

### Physically exercised service owner

```text
scripts/stage_c_transaction/service_quiescence_rehearsal_adapter.py
scripts/stage_c_transaction/service_quiescence_rehearsal_adapter_v2.py
```

It continues to own:

- the fixed service stop/start boundary;
- DAC and loopback release proof;
- mandatory exact restoration;
- dashboard health and bounded DAC readiness;
- typed restored-rehearsal closure.

### Current-package composition

```text
scripts/stage_c_transaction/current_package_service_quiescence_adapter_v8.py
commit b23578659931f9bdc62d370d1d66520480036262
```

The narrow multiple-inheritance adapter places the corrected Stage C17 v2
service layer above the accepted current-package adapter. No new `systemctl`,
DAC, package-copy or transaction implementation was added.

It binds distinct rehearsal identities:

```text
stage-c22-service-rehearsal-install-
stage-c22-service-rehearsal-snapshot-
```

### Guarded orchestration

```text
scripts/stage_c_transaction/current_package_service_quiescence_rehearsal_v8.py
commit ba713e8e55a5fffe5dfeb9c759ba085726084366
```

The orchestration requires the exact accepted Stage C21 manifest digest and
replays:

- the exact 32-check order and PASS results;
- package and baseline root binding;
- package fingerprint;
- pre-mutation identity flags;
- all 18 blocked ordinary operations;
- all four blocked approval operations;
- final report markers;
- retained candidate and transaction review copies.

It emits 41 ordered checks and requires a complete post-lock accepted baseline.

After DAC release it calls managed-file installation only through the blocked
adapter and requires refusal before restoration proceeds.

### Fixed wrapper

```text
scripts/test-stage-c22-current-package-service-quiescence.sh
commit 3c74722c102ccf1119c175811e1b017609207abb
```

The wrapper:

- defaults to inert prepare-only mode;
- invokes no sudo or host observation in default mode;
- accepts only four fixed roots and the exact confirmation token;
- uses one constrained `sudo env ... python3 -m ...` guarded command;
- exposes no arbitrary service, route, mixer, command, transaction or lock path;
- explicitly warns that dashboard and playback will be temporarily unavailable;
- states that SSH remains outside the stopped application boundary;
- states that restoration failure retains lock and transaction for review.

The exact confirmation token is:

```text
STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE
```

## Automated validation

Test file:

```text
tests/test_stage_c22_current_package_service_quiescence_v8.py
commit e173d05319747d227a3a9a2773d597fcb7f9f9cc
```

The 16 focused tests cover:

- exact multiple-inheritance order;
- current-package ownership of transaction and staging operations;
- historical C17 ownership of stop, restore and readiness operations;
- `ProductionAdapterV3` conformance;
- fixed Stage C22 identities;
- exact accepted Stage C21 manifest binding;
- complete 41-check order;
- fixed confirmation and evidence prefix;
- inert wrapper default and one constrained sudo boundary;
- absence of install, activation and arbitrary authority selectors;
- absence of direct systemctl, mixer, ALSA, CamillaDSP or audio commands in the new layer;
- blocked managed-file installation after DAC release;
- absent approval interface;
- complete baseline re-observation after lock release;
- absence of the bare master-EQ installer;
- explicit temporary-outage and retained-failure warning.

GitHub Actions validation:

```text
run
31071770724

job
92520996162

result
success

suite
Ran 1190 tests in 7.371s
OK
```

The workflow also passed Python compilation, JavaScript checks and shell syntax
validation.

## Safety result

This repository slice did not:

- execute Stage C22 on `plexamp-bedroom`;
- acquire or create the production lock;
- create an authoritative transaction;
- stop or start an appliance service;
- release or open the DAC;
- install, remove or replace a managed file;
- run `systemctl daemon-reload`;
- select an ALSA route;
- change a mixer value;
- publish or promote an approval record;
- start CamillaDSP;
- play music, alarm or test audio;
- commit or activate a production transaction;
- run `scripts/install-master-eq.sh`;
- make PR #2 ready or merge it.

## Failure contract

Before the first service stop, ordinary pre-mutation cleanup remains available.
After the service mutation boundary, pre-mutation abort must refuse and the
service owner must restore the exact captured state first.

If exact restoration fails, the lock and transaction are deliberately retained
for human review. No automatic or manual cleanup should be performed before the
retained state is inspected.

A successful run must restore the complete accepted live baseline after the
transaction is removed and the lock is released.

## Current gate

Repository implementation is complete. Pi execution remains unapproved.

A separate explicit approval must name the exact final branch head and authorise
only the Stage C22 current-package service-quiescence/exact-restoration rehearsal
on `plexamp-bedroom`, including the brief interruption of Plexamp, AirPlay and
the dashboard.

That approval will not authorise:

- managed-file installation;
- systemd daemon reload;
- ALSA route or mixer mutation;
- approval publication;
- CamillaDSP startup;
- audio testing;
- activation or merge.

## Next after accepted Pi evidence

Only after Stage C22 succeeds and its evidence is accepted should the first
managed-file installation plus mandatory exact rollback slice be rebound to the
accepted current package. That later slice requires another design review and a
new explicit approval.
