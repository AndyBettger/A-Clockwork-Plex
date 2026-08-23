# Stage C9 production adapter boundary design

Status: design-only. No production adapter, activation token, production lock acquisition or production mutation entrypoint exists in this stage.

## Purpose

Stages C4, C7 and C8 now establish one exact file transaction and rollback foundation:

- Stage C4 proved install, explicit uninstall and three automatic rollback paths in unprivileged synthetic filesystems;
- Stage C7 proved root-owned atomic copy, ownership, mode preservation and exact rollback in disposable root-owned synthetic filesystems;
- Stage C8 retired the duplicate Stage C4 runtime path and physically confirmed one executable transaction and rollback authority.

Stage C9 defines the boundary between that proven transaction policy and the future fixed-command adapter required to interact with the real host.

The design deliberately does **not** implement that adapter. Its purpose is to prevent service, mixer, module, DAC and CamillaDSP operations from becoming scattered through the transaction engine or duplicated among helpers.

Persistent Stage C activation remains blocked.

## Existing authorities

The following authorities are retained:

```text
Transaction and exact rollback policy:
  scripts.stage_c_transaction.sandbox_transaction

Root-owned disposable filesystem primitives:
  scripts.stage_c_transaction.root_owned_transaction

Reviewed production state-machine contract:
  scripts.stage_c_transaction.production_plan

Privileged snapshot primitives:
  scripts.stage_c_transaction.snapshot_core
  scripts.stage_c_transaction.privileged_snapshot
```

Stage C9 must not create another transaction or rollback implementation.

The future production adapter will provide fixed host operations to the reviewed state machine. It will not decide ordering, failure ownership, rollback policy or activation eligibility.

## Architectural split

The future implementation is divided into four explicit layers.

### 1. Transaction policy

The transaction policy owns:

- the immutable state-machine order;
- the distinction between pre-mutation abort and post-mutation rollback;
- the single rollback entrypoint;
- commit eligibility;
- exact uninstall eligibility;
- fail-closed handling of any incomplete verification.

This layer must not call `subprocess`, construct shell commands or accept arbitrary operation names.

### 2. Filesystem transaction core

The filesystem core owns:

- safe absolute-destination validation;
- authoritative snapshot copies and absence markers;
- double-hashed atomic file installation;
- exact mode, UID and GID verification;
- parent-directory state preservation;
- exact restoration or verified removal;
- fsync ordering;
- transaction manifests and mismatch reporting.

The surviving Stage C4 authority and Stage C7 root-owned primitives are the source for this layer. A production implementation must consolidate reusable primitives rather than copy their orchestration again.

### 3. Fixed production command adapter

The future command adapter owns only fixed, reviewed host operations:

- exclusive route-lock acquisition and release;
- fixed service inspection and fixed service actions;
- fixed mixer reads and writes;
- fixed loopback inspection, load and unload operations;
- fixed DAC owner and `hw_params` inspection;
- fixed ALSA parse and finite PCM probes;
- fixed CamillaDSP start, stop and health checks;
- fixed local dashboard health request.

It returns structured results to transaction policy. It must not perform rollback, commit, activation approval or route-policy decisions by itself.

### 4. Guarded entrypoint

The future guarded entrypoint may eventually:

- validate one exact action token;
- validate one exact package and host contract;
- launch the transaction policy through the production adapter;
- expose only explicitly reviewed actions.

No such entrypoint exists in Stage C9.

## Single production writer lock

Every future production writer must acquire:

```text
/run/lock/a-clockwork-plex-audio-route.lock
```

The lock remains unopened by Stage C9.

The eventual adapter contract requires:

- fixed path with no caller override;
- root ownership;
- mode `0600`;
- exclusive non-blocking `flock`;
- acquisition before transaction identity or snapshot creation;
- contention failure before any mutation;
- retention through commit or complete rollback verification;
- release only after final state verification;
- the same lock for install, route selection, runtime failback and explicit uninstall.

There must be no secondary installer, EQ, failback or uninstall lock.

## Fresh authoritative transaction directory

Every future authorised mutation must generate a new identity after acquiring the route lock and create:

```text
/var/lib/a-clockwork-plex/split-bus/transactions/<generated-identity>/
```

The identity and directory may not be caller supplied.

The directory must:

- begin absent;
- be created mode `0700`, owner `root:root`;
- remain bound to one action and one package fingerprint;
- contain the complete authoritative snapshot before mutation;
- contain a monotonic journal and explicit current state;
- contain the final commit or rollback result;
- never reuse Stage C3, C6 or other rehearsal evidence as rollback content.

## Fixed production service boundary

Only the reviewed units may be addressed:

```text
plexamp.service
shairport-sync.service
a-clockwork-plex.service
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

The adapter must reject:

- caller-supplied unit names;
- wildcard operations;
- system-wide service sweeps;
- dynamic command fragments;
- actions outside the reviewed state-machine request.

Application services are restored only when captured active before the transaction. Stage C units are restored according to the authoritative snapshot and the committed or rolled-back route state.

## Fixed mixer boundary

Only the four reviewed ALSA controls may be read or restored:

```text
Plexamp Output
AirPlay Output
Music Master
Maximum Alarm Volume
```

The adapter must use fixed card/control mappings. It must not accept a caller-supplied card, control name, raw command or percentage outside the validated range.

Mixer writes are rollback-owned operations and must be followed by exact readback verification.

## Fixed loopback boundary

The persistent loopback contract remains:

```text
module: snd_aloop
card index: 7
card id: ACP_Loopback
pcm_substreams: 2
pcm_notify: 1
```

The adapter must distinguish:

- persistence files;
- currently loaded state;
- exact module parameters;
- whether transaction policy permits a load or unload at the current state.

It must not accept arbitrary module names or options.

## Fixed DAC boundary

The physical DAC contract remains:

```text
format: S16_LE
channels: 2
rate: 44100
period_size: 1024
buffer_size: 8192
```

The adapter must provide structured DAC ownership and `hw_params` observations. It must not parse unstructured stderr into policy decisions.

Production mutation may proceed only after the state machine has proved that the expected application owners released the DAC.

## Fixed ALSA and CamillaDSP boundary

The future adapter may expose only bounded operations for:

- parsing the selected ALSA configuration;
- opening finite, named music and alarm probe PCMs;
- starting the pinned CamillaDSP executable with the managed configuration;
- stopping only the managed CamillaDSP process/service;
- verifying expected loopback capture, playback and DAC ownership;
- verifying the final limiter and expected channel count;
- verifying that CamillaDSP survives application-service restoration.

No network download, package installation, unpinned executable or arbitrary configuration path belongs to activation.

## Structured operation interface

The future adapter should expose typed operations rather than a generic command runner. The reviewed logical interface is:

```text
inspect_host_contract()
inspect_production_lock()
acquire_production_lock()
release_production_lock()
create_authoritative_transaction()
capture_filesystem_state()
capture_service_state()
capture_mixer_state()
capture_loopback_state()
capture_dac_state()
stage_candidate_files()
validate_candidate_alsa()
validate_candidate_sudoers()
validate_candidate_units()
validate_candidate_camilladsp()
stop_captured_application_services()
verify_dac_released()
install_managed_files()
reload_systemd()
select_split_bus_route()
start_managed_stage_c_services()
verify_split_bus_health()
run_finite_music_probe()
run_finite_alarm_probe()
restore_captured_application_services()
verify_dashboard_health()
write_commit_manifest()
select_direct_alarm_bypass_failback()
restore_authoritative_snapshot()
verify_exact_restoration()
```

Each operation must have fixed inputs defined by the package, authoritative snapshot and transaction state. No operation accepts an executable path, unit name, filesystem destination or shell fragment from the caller.

## Command execution requirements

When implementation is eventually permitted, the adapter must:

- use argument arrays only;
- use fixed absolute executable paths;
- never use `shell=True`, `eval`, `exec`, command interpolation or shell pipelines;
- set explicit timeouts;
- capture stdout and stderr separately;
- return exit status and structured parsed values;
- terminate bounded probes on timeout;
- record every requested and completed operation in the transaction journal;
- reject output that cannot be parsed exactly;
- fail closed on missing executables, changed checksums or unexpected owners.

The adapter must not perform network access.

## Failure ownership

The adapter reports failure; transaction policy owns the response.

Failures before application services begin stopping are pre-mutation aborts. They close the incomplete transaction record and release the lock without claiming production rollback.

Failures after service stopping begins and before commit invoke the single exact rollback policy. The adapter performs only the fixed operations requested by that rollback policy.

Runtime CamillaDSP failure after a committed installation is not exact uninstall. It requests the physically proven direct alarm-bypass failback route under the same production lock.

Exact uninstall uses the committed installation's authoritative snapshot and the same transaction/rollback authority.

## Blocked review implementation

The next implementation stage may add:

- a typed adapter protocol;
- a review-only adapter inventory;
- fixed unit, control, module, DAC and executable constants;
- static request/result data structures;
- a blocked adapter whose mutating methods terminate with the deliberate unavailable status;
- tests proving no generic command runner, production lock open, root entrypoint or activation token exists.

That implementation must still provide no working production command execution.

## Stage C9 safety boundary

Stage C9 must not:

- invoke or require `sudo`;
- run as root;
- acquire or create the production lock;
- create a production transaction directory;
- write `/etc`, `/usr/local`, `/var/lib` or `/run`;
- execute `systemctl`, `amixer`, `modprobe`, `aplay`, `fuser` or CamillaDSP;
- open a device or PCM;
- create an approval marker;
- expose install, activate, failback, rollback or uninstall actions;
- modify the known-good direct shared ALSA graph;
- run `scripts/install-master-eq.sh`.

## Promotion boundary

A reviewed Stage C9 design permits implementation of the typed, blocked production-adapter contract only.

It does not permit a working root adapter or persistent activation.

Before a production adapter can gain executable host operations, the project still requires:

1. a blocked adapter implementation and static safety review;
2. exact executable-path and argument allowlists;
3. root-owned authoritative snapshot implementation using a fresh transaction identity;
4. production-lock acquisition rehearsal without filesystem or service mutation;
5. candidate ALSA, sudoers, unit and CamillaDSP validation under root;
6. fixed service/mixer/module/DAC command adapter review;
7. deliberate failure-injection rehearsal while still unable to commit;
8. exact production rollback and explicit uninstall proof;
9. runtime direct alarm-bypass failback proof;
10. EQ state/reload and dashboard degraded-mode completion;
11. explicit user authorisation before any persistent activation action is exposed.
