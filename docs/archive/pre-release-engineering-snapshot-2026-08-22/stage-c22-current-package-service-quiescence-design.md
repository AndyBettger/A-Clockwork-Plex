# Stage C22 current-package service-quiescence and exact-restoration design

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Status: **repository design frozen; Pi execution separately gated**

## Purpose

Stage C22 is the first current-package rehearsal that deliberately crosses a
production mutation boundary. Its sole mutation is a brief, reversible stop and
exact restoration of the three application services already captured as active:

```text
a-clockwork-plex.service
shairport-sync.service
plexamp.service
```

It does not install the Stage C21 package and does not select either Stage C
route. The purpose is to prove that the accepted current package, accepted live
baseline and accepted Stage C21 transaction evidence can enter and leave the
service-quiescence boundary without changing the appliance.

## Accepted inputs

### Current package

```text
package root
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo

package fingerprint
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

regular files
28

fingerprinted payload files
27
```

### Accepted production baseline

```text
baseline root
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac
```

### Accepted Stage C21 evidence

```text
evidence root
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg

checks
32 / 32 PASS

evidence-manifest rows
139

evidence-manifest SHA-256
a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff
```

The Stage C21 bundle is replayed as an immutable input. Its manifest, exact
ordered checks, input binding, identity flags, blocked ordinary operations,
blocked approval operations, report markers and retained candidate/transaction
review copies must all match before Stage C22 may proceed.

## One authority stack

Stage C22 deliberately composes existing, separately proved owners rather than
adding another service-control or transaction framework.

### Current-package owner

`CurrentPackageCandidateValidationAdapterV7` remains responsible for:

- the canonical production lock;
- the authoritative transaction and snapshot identities;
- the target-proved transaction-parent contract;
- the five authoritative snapshot domains;
- the accepted 28-file package and fingerprint;
- transaction-private current-package staging;
- ALSA, sudoers, unit/runtime and CamillaDSP validation.

### Reversible service owner

`ServiceQuiescenceRehearsalAdapterV2` remains responsible for:

- the fixed application stop order;
- fixed `systemctl start` and `systemctl stop` boundaries only;
- the fixed application start order;
- physical DAC and fixed loopback endpoint release proof;
- mandatory exact service restoration;
- dashboard readiness and bounded DAC-owner return observation;
- restored-rehearsal transaction closure.

The Stage C22 adapter is a narrow multiple-inheritance composition:

```text
ServiceQuiescenceRehearsalAdapterV2
→ ServiceQuiescenceRehearsalAdapter
→ CurrentPackageCandidateValidationAdapterV7
```

This ordering lets the physically exercised Stage C17 service layer call into
the current-package transaction, snapshot and candidate implementation through
normal cooperative `super()` dispatch. Stage C22 contains no second
`systemctl`, DAC, package-copy or transaction implementation.

## Fixed identity and entrypoint

The rehearsal uses distinct non-production identities:

```text
transaction prefix
stage-c22-service-rehearsal-install-

snapshot prefix
stage-c22-service-rehearsal-snapshot-
```

The exact confirmation token is:

```text
STAGE-C22-CURRENT-PACKAGE-SERVICE-QUIESCE-RESTORE
```

The fixed wrapper is:

```text
scripts/test-stage-c22-current-package-service-quiescence.sh
```

Its default mode is inert prepare-only. Guarded mode accepts only the package,
baseline, accepted Stage C21 evidence and one fresh Stage C22 evidence root.
There is no arbitrary service, route, mixer, transaction, lock, command,
installer or activation selector.

## Guarded operation order

```text
replay exact package, baseline and Stage C21 evidence
→ fresh read-only full baseline inspection
→ acquire canonical production lock
→ create one fresh authoritative transaction
→ capture filesystem, services, mixer, loopback and DAC
→ stage all 28 package files only inside the transaction
→ validate ALSA, sudoers, units/runtime and CamillaDSP privately
→ prove all later ordinary operations blocked
→ prove all four approval operations blocked and absent
→ cross the mutation boundary by stopping the captured-active applications
→ prove physical DAC and fixed loopback endpoints are released
→ prove managed-file installation remains blocked after DAC release
→ restore the exact captured application-service state
→ verify dashboard HTTP health and bounded DAC-owner return
→ prove the pre-mutation abort is unavailable after mutation
→ close the restored rehearsal transaction through typed v3 closure
→ remove the transaction
→ release the production lock
→ repeat the complete accepted live-baseline inspection
→ checksum and retain non-authoritative evidence
```

## Fixed stop and restoration order

The historical service owner stops applications in dependency-safe order:

```text
a-clockwork-plex.service
→ shairport-sync.service
→ plexamp.service
```

It restores them in source-first order:

```text
plexamp.service
→ shairport-sync.service
→ a-clockwork-plex.service
```

The dashboard and playback surfaces will therefore be temporarily unavailable.
SSH is outside the application-service boundary and is not stopped by the
rehearsal.

## Permitted mutation

Only these existing typed operations may cross the mutation boundary:

```text
STOP_CAPTURED_APPLICATION_SERVICES
VERIFY_DAC_RELEASED
RESTORE_CAPTURED_APPLICATION_SERVICES
VERIFY_DASHBOARD_HEALTH
CLOSE_RESTORED_REHEARSAL_TRANSACTION
```

No production file is installed or changed. No Stage C unit is started. No
route or mixer value is changed.

## Explicit exclusions

Stage C22 has no authority to perform:

- managed-file installation or removal;
- `systemctl daemon-reload`;
- split-bus or direct-route selection;
- mixer mutation;
- kernel-module mutation;
- temporary or committed approval publication;
- CamillaDSP startup;
- music, alarm or test audio;
- transaction commit;
- production activation;
- uninstall or reboot-persistence testing;
- `scripts/install-master-eq.sh` execution;
- PR merge.

Managed-file installation is deliberately called through the blocked adapter
after DAC release. A PASS requires that it still refuses execution at that
later boundary.

## Failure ownership

### Before the service mutation boundary

A failure before the first service stop remains a pre-mutation transaction
failure. The inherited transaction owner may abort the disposable transaction
and release the lock only after exact cleanup.

### After the service mutation boundary

Once any application service has been stopped, the ordinary pre-mutation abort
must refuse execution. The service owner must first restore the exact captured
service state.

The adapter context manager owns mandatory restoration on every exception path.
It attempts restoration before inherited transaction or lock cleanup.

### Restoration failure

If exact restoration cannot be proved, the failure is deliberately visible:

- the production lock is retained;
- the authoritative transaction is retained;
- evidence is retained for review;
- the run must not claim success;
- no manual cleanup should be attempted before the retained state is reviewed.

This is preferable to releasing authority while the appliance state is
uncertain.

### Successful restoration

A successful run requires:

- all captured application states restored exactly;
- Stage C services still absent/inactive as captured;
- mixer and loopback unchanged;
- dashboard HTTP health restored;
- the physical DAC contract and Plexamp owner returned within the bounded poll;
- typed restored-rehearsal closure removed the transaction;
- the lock released only after transaction closure;
- the complete accepted live baseline passed again after lock release.

## Evidence contract

Stage C22 emits 41 ordered PASS checks. The final checks require:

```text
production-lock-released
post-lock-live-baseline
input-integrity
evidence-integrity
activation-interface
```

The evidence records service actions, DAC restoration readiness, typed
operations, candidate and transaction review copies, input binding, identities,
blocked operations, approval refusals, complete manifest and human report.

The evidence is review material only. It is not an activation approval and
cannot be reused as a rollback or production transaction.

## Approval gate

Repository preparation does not authorise Pi execution. A separate explicit
approval must name:

- `plexamp-bedroom`;
- the exact reviewed branch head;
- the Stage C22 service-quiescence/exact-restoration rehearsal;
- acceptance of the brief Plexamp, AirPlay and dashboard interruption.

That approval does not extend to installation, daemon reload, route selection,
mixer mutation, approval publication, CamillaDSP startup, audio testing,
activation or merge.
