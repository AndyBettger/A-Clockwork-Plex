# Stage C14 production-lock-only rehearsal — physical result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Result

**PASS**

Stage C14 temporarily created, exclusively held, contention-tested and removed the single fixed production route-lock path:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

No authoritative transaction, activation-time snapshot, package operation, service change, mixer write, ALSA-route change, PCM/DAC access, CamillaDSP operation, failback, rollback or uninstall action was available.

Persistent Stage C activation remains blocked.

## Evidence root

```text
/var/tmp/a-clockwork-plex-stage-c14-production-lock.qiZvzh
```

Retain this directory with the prior Stage C evidence chain until final Stage C release review.

## Exact acceptance checks

All fourteen checks passed in the required order:

```text
root-scope                     PASS
protocol-conformance           PASS
pre-lock-host-contract         PASS
pre-lock-boundary              PASS
production-lock-acquired       PASS
lock-file-contract             PASS
lock-contention                PASS
held-lock-observation          PASS
read-only-host-observations    PASS
blocked-operation-boundary     PASS
production-lock-released       PASS
exact-lock-cleanup             PASS
evidence-integrity             PASS
activation-interface           PASS
```

## Lock evidence

The adapter generated this non-authoritative rehearsal lease:

```text
lease_id                  stage-c14-lock-4dc535de05d62aed9d645acf
path                      /run/lock/a-clockwork-plex-audio-route.lock
held                      true
inode                     8
mode                      600
owner_uid                 0
owner_gid                 0
contention_proved         true
production_authoritative  false
transaction_created       false
```

The lock file was therefore:

- a regular file at the exact fixed path;
- root-owned and root-group-owned;
- mode `0600`;
- held through an exclusive non-blocking `flock`;
- unavailable to an independent competing descriptor;
- tied to the adapter-generated lease;
- not treated as an authoritative production transaction.

## Event ordering and duration

The event evidence recorded:

```text
10  pre-lock-boundary          fixed path absent
20  production-lock-acquired  lease=stage-c14-lock-4dc535de05d62aed9d645acf inode=8
30  production-lock-released  lease=stage-c14-lock-4dc535de05d62aed9d645acf inode=8
```

Wall-clock timestamps were:

```text
pre-lock boundary  2026-08-05T13:59:36.682461+01:00
lock acquired      2026-08-05T13:59:36.683041+01:00
lock released      2026-08-05T13:59:36.855202+01:00
```

The lock was held for approximately **172 milliseconds**.

## Read-only host observations while locked

The six inherited Stage C13 observations remained exact while the real production lock was held.

### Host contract

```text
ALSA route SHA-256  08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
Loopback            snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1
DAC                 S16_LE, stereo, 44100 Hz, period 1024, buffer 8192
```

### Services

```text
plexamp.service                         loaded, active, enabled
shairport-sync.service                  loaded, active, enabled
a-clockwork-plex.service                loaded, active, enabled
a-clockwork-plex-audio-route.service    not found
a-clockwork-plex-camilladsp.service     not found
a-clockwork-plex-audio-failback.service not found
```

### Mixer

```text
Plexamp Output        94%
AirPlay Output       100%
Music Master         100%
Maximum Alarm Volume 100%
```

### DAC ownership

```text
PID      466057
User     andy
Command  node
Access   read-write
Released false
```

## Blocked-operation proof

All twenty-five operations outside the eight-operation Stage C14 boundary refused with their exact typed identities:

```text
create-authoritative-transaction
capture-filesystem-state
stage-candidate-files
validate-candidate-alsa
validate-candidate-sudoers
validate-candidate-units
validate-candidate-camilladsp
stop-captured-application-services
verify-dac-released
install-managed-files
reload-systemd
select-split-bus-route
start-managed-stage-c-services
stop-managed-stage-c-services
verify-split-bus-health
run-finite-music-probe
run-finite-alarm-probe
restore-captured-application-services
verify-dashboard-health
write-commit-manifest
select-direct-failback-route
restore-exact-snapshot
restore-mixer-state
restore-service-state
verify-exact-rollback
```

## Exact cleanup proof

Normal typed release:

1. verified the pathname still referred to the exact original device/inode;
2. unlinked the lock pathname while the descriptor still held the lock;
3. unlocked the descriptor;
4. closed the descriptor;
5. verified the lock pathname was absent;
6. verified no authoritative transaction root had appeared.

The final independent shell check reported:

```text
PASS: production lock path is absent
```

## Evidence integrity

The evidence tree contained only regular files beneath the fresh Stage C14 root. Its manifest recorded checksums for:

```text
blocked-operations.tsv
lease.tsv
lock-events.tsv
report.txt
results.tsv
typed-observations.json
```

No symlink or special object was present.

## What Stage C14 proved

Stage C14 proved the real production lock boundary in isolation:

- exact fixed pathname;
- exclusive root-owned mode-`0600` creation;
- non-blocking lock acquisition;
- genuine contention;
- typed held-lock inspection;
- unchanged read-only host observations while held;
- exact inode-bound release and cleanup;
- no authoritative transaction root;
- no executable production or audio mutation path.

## What Stage C14 did not prove

Stage C14 did not prove:

- authoritative transaction creation;
- fresh activation-time filesystem snapshot;
- package staging or validation;
- managed-file installation;
- service or mixer mutation;
- split-bus startup;
- runtime failback;
- exact rollback or uninstall;
- reboot persistence.

Those remain separately guarded roadmap stages.

## Safety conclusion

The single genuine future-production pathname used by this rehearsal was the temporary route lock itself. It was present only while held by the adapter and was absent at completion.

The stable direct audio graph, live services, mixer values, loopback configuration and DAC ownership were unchanged. The old master-EQ installer was not run. PR #2 must remain Draft, open and unmerged until explicit approval.