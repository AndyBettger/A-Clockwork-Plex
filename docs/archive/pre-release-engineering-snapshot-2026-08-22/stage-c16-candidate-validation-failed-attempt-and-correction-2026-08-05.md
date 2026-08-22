# Stage C16 candidate validation rehearsal — failed-safe attempt and correction

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Host: `plexamp-bedroom`  
Architecture: `aarch64`

## Status

**FAILED SAFELY, CLEANED UP EXACTLY, CORRECTED IN AUTOMATION**

The first physical Stage C16 candidate-staging and validation rehearsal stopped during private systemd-unit validation. It stopped after transaction-private staging, ALSA validation and sudoers validation, and before CamillaDSP validation or any service, DAC, production-file, route or audio mutation.

The disposable authoritative transaction and production lock were subsequently confirmed absent. Plexamp, Shairport Sync and the dashboard remained active. The active ALSA route checksum matched the exact Stage C15 authoritative snapshot.

The failed evidence directory must be retained:

```text
/var/tmp/a-clockwork-plex-stage-c16-candidate-validation.JNfPeg
```

It must not be reused for the corrected retry.

## First physical attempt

The guarded rehearsal used:

```text
Stage C1 package  /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY
Stage C15 result  /var/tmp/a-clockwork-plex-stage-c15-authoritative-snapshot.wg3sxB
Stage C16 output  /var/tmp/a-clockwork-plex-stage-c16-candidate-validation.JNfPeg
```

The rehearsal passed these boundaries before stopping:

```text
root-scope
input-replay
protocol-conformance
pre-lock-host-contract
pre-lock-boundary
production-lock-acquired
authoritative-transaction-created
transaction-identity-binding
filesystem-snapshot
service-snapshot
mixer-snapshot
loopback-snapshot
dac-snapshot
snapshot-integrity
candidate-staging
candidate-manifest-binding
candidate-alsa-validation
candidate-sudoers-validation
```

It then failed closed with:

```text
validate-candidate-units failed: staged systemd candidates failed verification
```

The run did not reach CamillaDSP validation. The later appliance-mutation operations remained unavailable.

## Root cause

The candidate systemd units were not defective.

The Stage C16 verifier deliberately set `SYSTEMD_UNIT_PATH` to a transaction-private directory so that `systemd-analyze verify` could not inspect or depend on the host's live systemd unit tree. The private model supplied the three candidate services and their explicit dependencies, but omitted three default targets that systemd implicitly resolves for ordinary services:

```text
sysinit.target
basic.target
shutdown.target
```

Because those inert dependency targets were absent from the deliberately isolated model, `systemd-analyze verify` returned failure.

## Corrective change

The private verifier now creates inert transaction-local copies of:

```text
sysinit.target
basic.target
shutdown.target
```

It still does not append or expose the host systemd unit search path.

The correction also retains any future failed fixed-validator output beneath the external Stage C16 evidence directory:

```text
failed-validation/
```

This preserves the command return code, stdout and stderr even though the real disposable transaction is still removed by fail-closed cleanup.

Relevant commits:

```text
f5c882e25a1136e4f10b2edec03266bb54e34480  fix private systemd verification and retain failure evidence
7532f15acb8225453257b1d508b6f90e5458a68e  add live private systemd regression tests
d4641b69097896388ccc648679b23c999e02bbc9  correct the pinned host-contract test fixture
```

## Automated proof

The corrected suite passed:

```text
Ran 693 tests in 4.286s
OK
```

The new regression test invokes the real `systemd-analyze verify` executable against the exact candidate unit templates, private service stubs and private target stubs while `SYSTEMD_UNIT_PATH` contains only the temporary validation directory.

## Independent cleanup proof

After the failed physical attempt, the host was checked independently.

### Production lock

```text
PASS: production lock path is absent
```

The fixed path was absent:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

### Authoritative transaction root

```text
PASS: transaction root is absent
```

The fixed root was absent:

```text
/var/lib/a-clockwork-plex/split-bus/transactions
```

### Stable services

```text
plexamp.service                  active
shairport-sync.service          active
a-clockwork-plex.service        active
```

### Stable ALSA route

The active direct-route checksum was:

```text
08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
```

This exactly matches the authoritative filesystem snapshot recorded by Stage C15. An earlier review message incorrectly stated a different expected checksum; that expectation was wrong and did not come from the accepted Stage C15 evidence.

## Safety conclusion

The first Stage C16 run demonstrated the intended fail-closed behaviour:

- candidate files existed only in the disposable transaction;
- the validator stopped at the first failed domain;
- no service or audio-appliance mutation began;
- automatic cleanup removed the exact transaction and production lock;
- stable services remained active;
- the active direct ALSA route remained byte-for-byte unchanged;
- the failed evidence directory was retained for review;
- the validator model was corrected without weakening its isolation boundary.

The old master-EQ installer was not run. Persistent Stage C activation remains blocked. PR #2 must remain Draft, open and unmerged until explicit approval.