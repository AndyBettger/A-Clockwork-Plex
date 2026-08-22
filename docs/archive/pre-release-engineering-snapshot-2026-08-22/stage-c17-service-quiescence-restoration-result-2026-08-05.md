# Stage C17 service-quiescence and exact-restoration rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

The corrected Stage C17 rehearsal repeated the physically accepted Stage C16 lock, transaction, snapshot, staging and validation prefix, briefly stopped only the three captured-active application services, proved the physical DAC and fixed loopback endpoints released, proved managed-file installation still blocked, restored the exact captured application-service state, waited for dashboard and strict DAC runtime readiness, verified the accepted direct appliance state, closed the restored rehearsal transaction through the typed v3 lifecycle operation, removed the exact transaction and released the production lock.

No managed file was installed. Systemd was not reloaded. The active ALSA route, mixer values and loopback configuration were not changed. No managed Stage C service or audio probe was available. Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c17-service-quiescence.3ySKhd
```

Retain this directory together with the complete Stage C evidence chain until final Stage C release review.

The earlier failed-safe Stage C17 attempt remains separately retained at:

```text
/var/tmp/a-clockwork-plex-stage-c17-service-quiescence.Pc6VUK
```

That earlier attempt restored all three application services and cleaned up its transaction and lock, but sampled the strict DAC runtime contract before Plexamp had finished reopening ALSA. The diagnosis, appliance cleanup proof and bounded-readiness correction are recorded in `docs/stage-c17-service-quiescence-failed-attempt-and-readiness-correction-2026-08-05.md`.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C16 result  /var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq
```

Both input trees remained unchanged.

## Exact acceptance checks

All thirty-five checks passed in the required order:

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
pre-install-boundary              PASS
application-service-restoration   PASS
dashboard-health                  PASS
exact-restoration-boundary        PASS
pre-mutation-abort-refusal        PASS
candidate-evidence-copy           PASS
restored-transaction-close-v3     PASS
exact-transaction-cleanup         PASS
production-lock-released          PASS
input-integrity                   PASS
evidence-integrity                PASS
activation-interface              PASS
```

## Authoritative identities

The adapter generated and bound these identities while it held the production lock:

```text
production-lock lease  stage-c14-lock-97f73b8c1340ac92276675ef
transaction            stage-c15-install-8272ed4d475dc19d2f0bb274
action                 install
```

The caller supplied none of these identities.

## Snapshot and validation proof

All five authoritative snapshot domains completed under one transaction identity:

1. current ALSA and managed filesystem destination state;
2. exact six-service state;
3. exact four-control mixer state;
4. exact `snd_aloop` state;
5. exact DAC format and one structured owner.

All twelve reviewed Stage C1 package files were staged only inside the authoritative transaction and matched the manifest path, mode, root ownership and digest contract. ALSA, sudoers, private systemd and digest-pinned CamillaDSP candidate validation all passed without opening a PCM or contacting the live systemd manager.

## Blocked-operation proof

All fourteen later operations refused with their exact typed identities. The blocked set covered:

- managed-file installation;
- systemd reload;
- split-bus and direct-failback route selection;
- managed Stage C service start and stop;
- split-bus health;
- finite music and alarm probes;
- commit-manifest writing;
- exact filesystem, mixer and service restoration;
- exact rollback verification.

After DAC release, `install-managed-files` remained blocked and no production path was written.

## Service-quiescence proof

The adapter stopped only the three services captured loaded and active, in the fixed order:

```text
a-clockwork-plex.service
shairport-sync.service
plexamp.service
```

No service enablement changed. The managed Stage C units remained inactive or absent.

With those services stopped, the physical DAC and both fixed loopback endpoints had no owners. No PCM was opened and no module was loaded or unloaded.

## Exact restoration and readiness proof

The adapter restored the captured-active application services in the fixed reverse order:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
```

It then proved:

- the exact six-service observation returned;
- the accepted direct ALSA host contract remained active;
- all four mixer values were unchanged;
- the exact loopback snapshot was unchanged;
- the dashboard followed its root redirect and returned HTTP 200 HTML;
- the full strict physical DAC runtime contract and one structured owner returned.

The corrected readiness boundary waited for the dashboard first and then polled the strict DAC observer for up to thirty seconds. It used no blind delay.

The accepted restored DAC contract remained:

```text
sample format  S16_LE
channels       2
rate           44100
period size    1024
buffer size    8192
released       false
owner count    1
```

A restarted process PID was not required to equal the pre-stop PID.

## Versioned transaction closure

Because Stage C17 crossed the first mutation boundary, the v2 pre-mutation abort correctly refused. The transaction instead closed through the typed v3 operation:

```text
close-restored-rehearsal-transaction
```

The closure recorded:

```text
state             rehearsal-restored-and-closed
mutation_started  true
restored          true
committed         false
```

The exact candidate, validation root and authoritative transaction were removed; transaction-parent state was restored; and only then was the exact production lock released.

The retained candidate and transaction copies are explicitly non-authoritative and unusable for activation or rollback.

## Evidence integrity

The successful evidence root contains the expected Stage C17 audit artefacts, including:

```text
results.tsv
identity.tsv
service-actions.tsv
restoration-readiness.tsv
typed-operations.json
blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
evidence-manifest.tsv
report.txt
```

The complete evidence tree was checksummed and contained no symlink or special object.

## Automated correction gate

Before the corrected physical retry, the complete branch suite passed:

```text
Ran 725 tests
OK
```

Focused readiness regression coverage proved:

- a temporarily closed DAC observation can become ready without a fixed sleep;
- the dashboard is awaited before strict DAC polling;
- readiness polling is bounded and evidenced;
- the corrected adapter is a narrow subclass;
- the corrected layer adds no appliance mutation command;
- wrapper entry-point selection is explicit;
- every pre-existing Stage C17 safety boundary remains intact.

## What Stage C17 proved

Stage C17 proved:

- the complete physically accepted C16 prefix;
- exact service-state capture immediately before mutation;
- fixed application-service stop order;
- physical DAC and loopback release;
- refusal of managed-file installation after release;
- mandatory exact application-service restoration;
- bounded post-start dashboard and DAC readiness;
- exact direct-route, mixer, loopback and service-state restoration;
- v2 abort refusal after mutation;
- typed v3 restored-rehearsal closure;
- exact transaction and parent cleanup;
- production-lock release only after restored closure;
- no persistent activation interface.

## What Stage C17 did not prove

Stage C17 did not prove:

- managed-file installation;
- systemd reload after installing units;
- active split-bus or direct-failback route selection;
- CamillaDSP startup or managed Stage C service state;
- split-bus health or finite music/alarm probes;
- install commit;
- automatic exact rollback after managed-file mutation;
- runtime direct failback;
- explicit uninstall;
- reboot persistence.

Those remain separately guarded roadmap stages.

## Safety conclusion

The first live service-mutation boundary has now been physically exercised with exact restoration. The DAC was deliberately released and regained its full known-good runtime contract, while every file, route, mixer, managed Stage C service, audio-probe and commit operation remained blocked.

The old master-EQ installer was not run. PR #2 must remain Draft, open and unmerged until explicit approval.
