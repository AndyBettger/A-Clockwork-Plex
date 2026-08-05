# Stage C17 service-quiescence and exact-restoration rehearsal — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C17 crosses the first real appliance-mutation boundary in the immutable
install program, but stops before any managed-file, unit, route, mixer or audio
mutation.

It extends the physically accepted Stage C16 prefix with exactly four v1
operations:

```text
stop-captured-application-services
verify-dac-released
restore-captured-application-services
verify-dashboard-health
```

The stage then closes the transaction through a new versioned v3 lifecycle
operation:

```text
close-restored-rehearsal-transaction
```

That closure is deliberately distinct from the Stage C15A v2 operation:

```text
abort-uncommitted-transaction
```

The v2 abort is valid only before mutation. Once Stage C17 has stopped a service,
it must never claim `aborted-before-mutation`.

## Exact physical boundary

The guarded rehearsal may:

1. replay the Stage C1 package and successful corrected Stage C16 evidence;
2. inspect the fixed host and absent production-lock boundary;
3. acquire the one fixed production lock;
4. create a fresh generated authoritative install transaction;
5. capture the exact filesystem, service, mixer, loopback and DAC snapshot;
6. stage and validate all twelve package files only inside the transaction;
7. stop only application services captured active:
   - `a-clockwork-plex.service`;
   - `shairport-sync.service`;
   - `plexamp.service`;
8. prove the physical DAC and fixed loopback endpoints have no owners;
9. prove managed-file installation remains blocked at the released-DAC boundary;
10. restore exactly the captured application-service active and enablement state;
11. verify:
    - all six service observations equal the authoritative snapshot;
    - the accepted direct ALSA route remains active;
    - all four mixer controls remain unchanged;
    - the exact `snd_aloop` contract remains unchanged;
    - the physical DAC contract and ownership return;
    - the dashboard root returns healthy local HTTP;
12. retain non-authoritative candidate, validation, service-action and transaction
    evidence;
13. close and remove the exact restored rehearsal transaction;
14. release the production lock only after closure.

It may not:

- install a managed file;
- reload systemd;
- select split-bus or direct-failback ALSA;
- start or stop any managed Stage C service;
- change a mixer control;
- start CamillaDSP;
- open a PCM or run a music/alarm probe;
- write an install commit;
- restore a filesystem snapshot;
- claim automatic rollback, runtime failback or uninstall;
- create an activation marker;
- persist the split-bus graph.

## Versioned lifecycle closure

### Frozen history

The accepted contracts remain unchanged:

```text
v1  33 original operations
v2  34 operations, adding abort-uncommitted-transaction
```

Stage C17 defines a v3 view containing 35 operations by adding:

```text
close-restored-rehearsal-transaction
```

### Receipt contract

The v3 receipt must prove:

```text
state                    rehearsal-restored-and-closed
mutation_started         true
restored                 true
committed                false
transaction_path_absent  true
parents_restored         true
```

It also records only the adapter-owned audit evidence path and the exact
application services restored. The caller supplies only the adapter-generated
transaction identity.

The receipt cannot represent a production install, rollback, failback or
uninstall commit.

## Operation partition

Stage C17 exposes nineteen v1 operations:

1. inspect host contract;
2. inspect production lock;
3. acquire production lock;
4. release production lock;
5. create authoritative transaction;
6. capture filesystem state;
7. capture service state;
8. capture mixer state;
9. capture loopback state;
10. capture DAC state;
11. stage candidate files;
12. validate candidate ALSA;
13. validate candidate sudoers;
14. validate candidate units;
15. validate candidate CamillaDSP;
16. stop captured application services;
17. verify DAC released;
18. restore captured application services;
19. verify dashboard health.

It also exposes both versioned lifecycle methods:

20. v2 pre-mutation abort;
21. v3 restored-rehearsal closure.

The v2 abort remains available only before mutation. After the first service stop
it must return a typed failure directing the transaction to v3 closure.

The remaining fourteen v1 operations stay blocked.

## Service-mutation boundary

### Pre-stop drift check

Immediately before the first stop command, the adapter re-observes the exact six
service states. Any difference from the authoritative snapshot aborts before a
service command.

Stage C17 requires all three application services to begin loaded and active. All
three managed Stage C services must remain inactive or absent.

### Fixed stop order

The adapter uses one fixed command shape and stop order:

```text
systemctl stop a-clockwork-plex.service
systemctl stop shairport-sync.service
systemctl stop plexamp.service
```

No unit name, command or action is caller-controlled.

Each unit must reach inactive state. Every completed action is written to the
external evidence tree so a failed disposable transaction cannot erase the
service-action record.

### Mandatory restoration

Any exception after the mutation boundary enters mandatory restoration before
transaction or lock cleanup.

The fixed start order is:

```text
systemctl start plexamp.service
systemctl start shairport-sync.service
systemctl start a-clockwork-plex.service
```

Only services captured active are started. Enablement is never changed.

If exact restoration cannot be proved, cleanup must fail closed: the adapter
must not silently release the production lock and pretend the appliance is safe.
The retained lock and transaction then become explicit recovery evidence.

## DAC-release proof

After all three captured-active services stop, the adapter checks fixed device
paths only:

```text
physical DAC resolved from /proc/asound/Pro
/dev/snd/pcmC7D0p
/dev/snd/pcmC7D1c
```

`fuser` must report no owner for each endpoint.

No PCM is opened and no module is loaded or unloaded.

## Exact restoration proof

After starting the captured application services, the adapter requires:

- exact application and Stage C service load/active/enable observations;
- the accepted direct route host contract;
- unchanged four-control mixer snapshot;
- unchanged `snd_aloop` snapshot;
- valid physical DAC format and at least one structured owner;
- local `http://127.0.0.1:8088/` returning HTTP 200 HTML.

The adapter does not require the restarted process PID to equal the pre-stop PID.

## Evidence

The guarded rehearsal retains:

```text
results.tsv
identity.tsv
parent-state.tsv
service-actions.tsv
typed-operations.json
blocked-operations.tsv
candidate-review-copy/
transaction-rehearsal-copy/
lock-events.tsv
evidence-manifest.tsv
report.txt
```

All outward copies are non-authoritative and unusable for activation or rollback.

The Stage C1 and Stage C16 input trees must remain unchanged.

## Expected acceptance checks

The physical rehearsal emits exactly thirty-five PASS checks:

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
candidate-unit-validation
candidate-camilladsp-validation
blocked-operation-boundary
service-quiescence
dac-release
pre-install-boundary
application-service-restoration
dashboard-health
exact-restoration-boundary
pre-mutation-abort-refusal
candidate-evidence-copy
restored-transaction-close-v3
exact-transaction-cleanup
production-lock-released
input-integrity
evidence-integrity
activation-interface
```

## Automated gate

Before a Pi command is accepted, focused tests must prove:

- v1 and v2 history remain unchanged;
- v3 adds exactly one unique operation;
- exact 21/14 Stage C17 operation partition;
- the restored receipt rejects pre-mutation, unrestored, committed or
  transaction-present states;
- no caller-supplied command, unit, endpoint, URL or evidence path;
- exact three-unit stop and start order;
- no service enable/disable/restart command;
- mandatory restoration precedes inherited lock cleanup;
- DAC release uses fixed physical and loopback endpoints;
- no managed-file, route, mixer, module, CamillaDSP or audio command exists in
  the adapter;
- pre-mutation abort refuses after mutation;
- v3 closure requires validation, release and exact restoration;
- prepare-only exits before the single constrained sudo command;
- no install, activation, rollback, failback, uninstall or keep-active option.

Persistent Stage C activation remains blocked. The old master-EQ installer
remains blocked. PR #2 remains Draft, open and unmerged.
