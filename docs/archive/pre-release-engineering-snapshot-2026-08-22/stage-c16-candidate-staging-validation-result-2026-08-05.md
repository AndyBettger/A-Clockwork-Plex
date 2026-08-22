# Stage C16 transaction candidate staging and validation rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

The corrected Stage C16 rehearsal created one fresh authoritative transaction while holding the fixed production route lock, captured all five exact snapshot domains, staged all twelve reviewed package files only beneath the transaction, validated the staged ALSA, sudoers, systemd and CamillaDSP candidates without opening audio or contacting the live service manager, retained non-authoritative evidence, explicitly aborted the transaction and removed it before releasing the lock.

No application service was stopped. The DAC was not released. No managed file, active route, mixer value, module, service state or audio endpoint was changed. Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq
```

Retain this directory together with the prior Stage C evidence chain until final Stage C release review.

The earlier failed-safe attempt remains separately retained at:

```text
/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.JNfPeg
```

That earlier attempt failed inside the private systemd validation model, cleaned up its lock and transaction exactly, and did not alter the stable appliance. Its diagnosis and correction are recorded in `docs/stage-c16-candidate-validation-failed-attempt-and-correction-2026-08-05.md`.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C15 result  /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB
```

Both input trees remained unchanged.

## Exact acceptance checks

All twenty-nine checks passed in the required order:

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
pre-mutation-boundary             PASS
candidate-evidence-copy           PASS
transaction-abort-v2              PASS
exact-transaction-cleanup         PASS
production-lock-released          PASS
input-integrity                   PASS
evidence-integrity                PASS
activation-interface              PASS
```

## Authoritative identities

The adapter generated and bound these identities while it held the production lock:

```text
production-lock lease  stage-c14-lock-b85befb87954d05781b78056
transaction            stage-c15-install-1689fe3fb7c042f01da2616f
action                 install
```

The caller supplied none of these identities.

## Snapshot proof

All five authoritative snapshot domains completed under one transaction identity:

1. current ALSA and managed filesystem destination state;
2. exact six-service state;
3. exact four-control mixer state;
4. exact `snd_aloop` state;
5. exact DAC format and one structured owner.

The stable direct route and all managed destinations were observed before staging. Snapshot completion was mandatory before the candidate operation became available.

## Candidate staging proof

The adapter created the fixed private candidate root only beneath the authoritative transaction and copied the reviewed Stage C1 package into it.

The staged candidate contained exactly twelve files. Every path, file mode, root ownership and digest matched the Stage C1 manifest. Atomic staging remained double-hashed and transaction-confined. No production destination was used as a staging path.

## Validation proof

### ALSA

Both staged route candidates parsed through private ALSA configuration roots. The required public PCM names were present and no PCM was opened.

### Sudoers

The staged restricted sudoers rules were accepted by `visudo`.

### Systemd and route helper

All three staged units passed `systemd-analyze verify` inside the corrected private unit model. The route helper compiled but was not executed. The live systemd manager was not contacted.

### CamillaDSP

The staged digest-pinned CamillaDSP binary accepted the staged configuration with `--check`. No audio endpoint was opened.

## Blocked-operation proof

All eighteen remaining v2 operations refused with their exact typed identities. The blocked set covered:

- stopping captured application services;
- DAC release verification;
- managed-file installation;
- systemd reload;
- active split-bus or direct-failback route selection;
- managed Stage C service start/stop;
- split-bus health and finite audio probes;
- application-service restoration;
- dashboard health verification;
- commit-manifest writing;
- exact snapshot, mixer and service restoration;
- exact rollback verification.

The first appliance mutation, `stop-captured-application-services`, remained blocked. No service, mixer, route or audio state changed.

## Evidence and explicit abort

The validated candidate and private validation artefacts were copied to:

```text
/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq/candidate-review-copy
```

The complete transaction review copy was retained at:

```text
/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.FFT4Rq/transaction-rehearsal-copy
```

Both copies are explicitly non-authoritative and must never become installation or rollback inputs.

The v2 abort accepted only the adapter-generated transaction identity. It removed the candidate root, private validation root and exact authoritative transaction, restored transaction-parent state, and only then allowed the exact production lock to be released.

## Evidence integrity

The evidence root contains:

```text
results.tsv
identity.tsv
typed-operations.json
blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
evidence-manifest.tsv
report.txt
```

The complete evidence tree was checksummed and contained no symlink or special object.

## What Stage C16 proved

Stage C16 proved:

- the complete physically accepted C15 lock, transaction and snapshot prefix;
- transaction-confined staging of all twelve reviewed package files;
- exact manifest, digest, mode and ownership binding;
- isolated ALSA validation without PCM access;
- sudoers validation;
- private systemd unit validation and inert route-helper compilation;
- digest-pinned CamillaDSP configuration validation without audio;
- refusal of the first and every later appliance mutation;
- non-authoritative candidate evidence retention;
- typed v2 transaction abort after validation;
- exact transaction and parent cleanup;
- production-lock release only after cleanup;
- no persistent activation interface.

## What Stage C16 did not prove

Stage C16 did not prove:

- stopping or restoring application services;
- DAC release;
- managed-file installation;
- systemd reload;
- active route selection;
- CamillaDSP startup or managed Stage C service state;
- split-bus health or finite audio probes;
- commit;
- automatic exact rollback after mutation;
- runtime direct failback;
- explicit uninstall;
- reboot persistence.

Those remain separately guarded roadmap stages.

## Safety conclusion

The candidate was staged and validated only inside the authoritative transaction. The transaction was explicitly aborted and removed before the first appliance mutation, and the production lock was released afterward. The stable direct audio graph remained active throughout.

The old master-EQ installer was not run. PR #2 must remain Draft, open and unmerged until explicit approval.