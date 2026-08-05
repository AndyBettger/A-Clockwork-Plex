# Stage C21 terminal activation program correction result — 2026-08-05

## Outcome

**PASS — the Stage C21 terminal activation and exact-rollback metadata are again aligned with the frozen C1–C20 production operation vocabulary and the physically proved C20 transaction order.**

The correction is static and simulated only. It did not run an installer, open ALSA devices, change the shared mixer, start or stop services, publish an approval on `plexamp-bedroom`, or activate CamillaDSP.

## Trigger

GitHub Actions run `31050075464` failed at branch head:

```text
afa78bb3e6fafbc53612afaf4a3d76c1d14e871f
test: simulate every Stage C21 terminal failure boundary
```

The suite ran 969 tests and stopped with two import errors:

- `tests/test_stage_c_activation_commit_program_v7_safety.py`
- `tests/test_stage_c_activation_commit_simulation_v7.py`

The first rejected value was:

```text
open-music-probe
```

`production_adapter_lifecycle_v7.py` correctly refused that identity because the frozen production lifecycle contains no such operation.

## Root cause

`activation_commit_program_v7.py` had drifted away from the established production operation contract in two ways.

### 1. Unauthorised operation aliases

The terminal program introduced six new friendly names that were not part of the frozen lifecycle:

- `open-music-probe`
- `open-alarm-probe`
- `verify-post-start-health`
- `restore-application-services`
- `restore-previous-installation`
- `verify-exact-restoration`

The authoritative existing operations are:

- `run-finite-music-probe`
- `run-finite-alarm-probe`
- `verify-split-bus-health`
- `restore-captured-application-services`
- `restore-exact-snapshot`
- `verify-exact-rollback`

Stage C21 is permitted to extend the lifecycle only with the four approval/lease operations already frozen in the v7 contract:

- `bind-production-lock-lease`
- `publish-temporary-activation-approval`
- `remove-temporary-activation-approval`
- `promote-committed-activation-approval`

### 2. Loss of the proved transaction shape

The broken terminal program also reordered health and probe steps and represented exact restoration as one invented operation. That would have hidden the established C11 automatic exact-rollback sequence instead of extending it.

The physically proved rollback remains:

1. stop captured application services
2. stop managed Stage C services
3. verify the DAC is released
4. restore the exact snapshot
5. reload systemd
6. restore exact mixer state
7. restore exact service state
8. verify exact rollback
9. release the production lock

Stage C21 adds only one rollback operation: remove the temporary approval immediately after managed Stage C services have stopped and before DAC-release verification and restoration continue.

## Corrected activation suffix

The fixed Stage C21 terminal suffix is:

1. `bind-production-lock-lease`
2. `publish-temporary-activation-approval`
3. `start-managed-stage-c-services`
4. `verify-split-bus-health`
5. `run-finite-music-probe`
6. `run-finite-alarm-probe`
7. `restore-captured-application-services`
8. `verify-split-bus-health`
9. `verify-dashboard-health`
10. `promote-committed-activation-approval`
11. `release-production-lock`

The two split-bus health checks are deliberate:

- the first proves the managed route before either finite probe;
- the second proves the route again after captured application services return and before dashboard health and terminal publication.

## Commit boundary

`promote-committed-activation-approval` remains the sole externally authoritative commit marker.

The historical `write-commit-manifest` operation is not executed as a second independent marker. A future production implementation of committed approval promotion must durably prepare the manifest, bind its digest into the committed approval, and atomically publish the approval before returning success.

Failures are owned as follows:

- before committed approval publication: run complete exact rollback;
- while committed approval is being published: either publication succeeds atomically or exact rollback owns the failure;
- after committed approval publication: do not roll back an authoritative install; recover forward;
- during any exact-rollback step: fail closed and retain the production lock.

## Corrected exact rollback

The final Stage C21 exact rollback is:

1. `stop-captured-application-services`
2. `stop-managed-stage-c-services`
3. `remove-temporary-activation-approval`
4. `verify-dac-released`
5. `restore-exact-snapshot`
6. `reload-systemd`
7. `restore-mixer-state`
8. `restore-service-state`
9. `verify-exact-rollback`
10. `release-production-lock`

The simulator now tracks exact snapshot, mixer and service restoration independently. `exact_previous_installation_restored` becomes true only after the complete restoration has passed `verify-exact-rollback`.

## Files corrected

- `scripts/stage_c_transaction/activation_commit_program_v7.py`
- `scripts/stage_c_transaction/activation_commit_simulation_v7.py`
- `tests/test_stage_c_activation_commit_program_v7_safety.py`
- `tests/test_stage_c_activation_commit_simulation_v7.py`

## Validation

Focused local contract validation passed 22 tests before publication.

GitHub Actions run `31052096388` then passed at branch head:

```text
78894a08fcee36a4d4643e318980ba06f5c95f12
test: cover every corrected Stage C21 failure boundary
```

Full result:

```text
Ran 989 tests in 21.500s

OK
```

Coverage now includes:

- the exact corrected activation suffix;
- both health gates and their ordering;
- every pre-terminal install failure;
- every exact-rollback failure boundary;
- temporary approval absence before publication;
- temporary approval removal after publication;
- component-level restoration state;
- terminal publication as the sole commit marker;
- post-commit lock-release forward recovery;
- no host, CLI, command or generic-dispatch path in the static program or simulator.

## Safety state after validation

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- CamillaDSP was not started;
- no Stage C package was installed;
- no approval was published on the appliance;
- no production lock was acquired on the appliance;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next engineering boundary

The corrected program is still immutable policy metadata plus a pure simulator. The next phase must connect that fixed program to the typed installed transaction adapter without creating an unreviewed activation route.

Before any physical activation can be considered, that phase must prove:

1. one fixed operation-to-adapter mapping with no generic dispatcher;
2. production implementations for lease binding and approval lifecycle operations;
3. atomic committed-approval promotion including durable manifest preparation;
4. complete automatic exact rollback using the corrected ten-step sequence;
5. fail-closed lock retention on rollback failure;
6. forward recovery only after committed publication;
7. a prepare/review boundary that remains non-activating until an explicit physical gate is approved.
