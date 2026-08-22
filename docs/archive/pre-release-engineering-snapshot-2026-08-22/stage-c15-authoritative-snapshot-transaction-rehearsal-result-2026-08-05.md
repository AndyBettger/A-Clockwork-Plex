# Stage C15 authoritative snapshot transaction rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C15 created one fresh authoritative transaction beneath the fixed production transaction root while the real production route lock was held, captured all five exact snapshot domains, proved every later staging and mutation operation remained blocked, copied the verified transaction outward as non-authoritative evidence, explicitly aborted it before mutation, removed the exact transaction and only then released the production lock.

No package staging, candidate validation, service stop, DAC release, managed-file installation, route selection, audio probe, CamillaDSP operation, commit, failback, rollback or uninstall action was available.

Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB
```

Retain this directory with the prior Stage C evidence chain until final Stage C release review.

## Replayed inputs

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C14 result  /var/tmp/a-clockwork-plex-stage-c14-production-lock.qiZvzh
```

Both input trees remained unchanged.

## Exact acceptance checks

All twenty-three checks passed in the required order:

```text
root-scope                       PASS
input-replay                     PASS
protocol-conformance             PASS
pre-lock-host-contract           PASS
pre-lock-boundary                PASS
production-lock-acquired         PASS
transaction-parent-boundary      PASS
authoritative-transaction-created PASS
transaction-identity-binding     PASS
filesystem-snapshot              PASS
service-snapshot                 PASS
mixer-snapshot                   PASS
loopback-snapshot                PASS
dac-snapshot                     PASS
snapshot-integrity               PASS
blocked-operation-boundary       PASS
pre-mutation-abort               PASS
transaction-evidence-copy        PASS
exact-transaction-cleanup        PASS
production-lock-released         PASS
input-integrity                  PASS
evidence-integrity               PASS
activation-interface             PASS
```

## Authoritative identities

The adapter generated and bound these identities while it held the production lock:

```text
production-lock lease  stage-c14-lock-8160755e25138772435ca277
transaction            stage-c15-install-f32ae7f46896fda9c1a81ed8
action                 install
```

The caller supplied none of these identities.

The transaction was authoritative only while the same adapter held the same lock lease and the exact transaction directory device/inode remained present in the `snapshot-open` state.

## Production paths used

The only production write boundaries were:

```text
/run/lock/a-clockwork-plex-audio-route.lock
/var/lib/a-clockwork-plex/split-bus/transactions/stage-c15-install-f32ae7f46896fda9c1a81ed8
```

The transaction parent boundary was recorded before creation. Missing fixed parents were created only with their reviewed root ownership and modes; existing parent metadata was preserved. At completion the generated transaction was absent and all pre-existing parent metadata was restored exactly.

## Exact snapshot proof

All five authoritative snapshot domains completed under one transaction/snapshot identity:

1. filesystem state;
2. six-service state;
3. four-control mixer state;
4. exact `snd_aloop` state;
5. exact DAC format and structured ownership.

The filesystem capture included the active ALSA route and every managed file/directory state. All twelve future managed files remained absent and no destination conflict, symlink or special object was accepted.

The live observations remained consistent with the accepted direct route:

```text
ALSA route SHA-256  08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
Loopback            snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1
DAC                 S16_LE, stereo, 44100 Hz, period 1024, buffer 8192
DAC owners          1 structured owner
```

## Blocked-operation proof

All twenty-three operations after the snapshot prefix refused with their exact typed identities. The blocked set covered:

- package staging;
- ALSA, sudoers, systemd-unit and CamillaDSP candidate validation;
- captured-application service stop;
- DAC release verification;
- managed-file installation;
- systemd reload;
- split-bus route selection;
- managed Stage C service start/stop;
- split-bus health and finite audio probes;
- captured-service restoration and dashboard health;
- commit-manifest writing;
- direct failback;
- exact snapshot, mixer and service restoration;
- exact rollback verification.

## Explicit pre-mutation abort

Stage C15 proved that lock release is not allowed to hide transaction cleanup.

The adapter first attempted release while the uncommitted transaction still existed. Release refused as required. The explicit typed abort then:

1. required the same held production-lock lease;
2. required all five snapshot domains to be complete;
3. verified the transaction pathname still referred to its original device/inode;
4. atomically recorded `aborted-before-mutation`;
5. retained a complete non-authoritative evidence copy;
6. removed only entries beneath the exact generated transaction directory;
7. removed only empty parent directories created by this rehearsal;
8. verified the real transaction pathname was absent;
9. verified all pre-existing parent metadata was restored;
10. allowed production-lock release only after cleanup completed.

The retained review copy is:

```text
/var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB/transaction-rehearsal-copy
```

It is explicitly non-authoritative and must never be reused as an activation or rollback snapshot.

## Evidence integrity

The evidence root contains:

```text
results.tsv
identity.tsv
parent-state.tsv
typed-observations.json
blocked-operations.tsv
transaction-rehearsal-copy/
lock-events.tsv
evidence-manifest.tsv
report.txt
```

The complete evidence tree was checksummed and contained no symlink or special object.

## What Stage C15 proved

Stage C15 proved the real pre-mutation transaction lifecycle:

- fixed production lock held across the entire transaction;
- adapter-generated authoritative transaction and snapshot identities;
- exact root-owned transaction-directory creation;
- exact five-domain activation-time snapshot;
- package and identity binding;
- refusal of all staging and mutation operations;
- lock-release refusal while the transaction remained open;
- explicit typed pre-mutation abort;
- non-authoritative outward evidence copy;
- exact inode-bound transaction cleanup;
- exact parent restoration;
- lock release only after cleanup;
- no persistent activation interface.

## What Stage C15 did not prove

Stage C15 did not prove:

- package staging;
- candidate validation;
- any service, mixer, filesystem-route or audio mutation;
- managed-file installation;
- split-bus startup or health;
- commit;
- automatic exact rollback after mutation;
- runtime direct failback;
- explicit uninstall;
- reboot persistence.

Those remain separately guarded roadmap stages.

## Safety conclusion

The authoritative rehearsal transaction was aborted before package staging or managed-audio mutation and removed. The production lock was released. The stable direct audio graph remained active throughout.

The old master-EQ installer was not run. PR #2 must remain Draft, open and unmerged until explicit approval.