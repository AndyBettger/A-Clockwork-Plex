# Stage C21 production prepare-only inspector result — 2026-08-06

## Outcome

**PASS — the repository now has a production-shaped but strictly read-only Stage C21 baseline inspector that can classify the untouched appliance without creating a transaction, acquiring a lock, writing an approval, persisting an evidence bundle or authorising Pi execution.**

This slice did not run on the Pi and did not access or alter the production appliance.

## Design

```text
82294cab625cce29a1af8773d35ae80e80425d7d
docs: design Stage C21 production prepare-only inspector

9b421cc98e0532d6e653ae27bd543df8e3a8c228
fix: align prepare-only inspector with packaged state permissions
```

The design deliberately separates two read-only contexts:

```text
baseline appliance observation
→ ReadOnlyHostProductionAdapter

already-held production transaction observation
→ BorrowedProductionAuthorityViewV7
```

The first prepare-only inspector uses only the baseline context. It does not invent a transaction, lease or approval plan for an appliance on which Stage C has not yet been installed.

During design review, an initial assumption that the Stage C state directories should be mode `0700` was corrected. The reviewed activation package manifest specifies the fixed production state directory as root-owned mode `0755`; the public approval record remains root-owned mode `0600`.

## Implementation

```text
scripts/stage_c_transaction/production_prepare_only_inspector_v7.py

772cf882ea55a7e07aba229840e07d7f27777797
feat: add Stage C21 production prepare-only inspector
```

The implementation accepts only:

```text
one exact ReadOnlyHostProductionAdapter
one immutable PackageFingerprint
```

It accepts no caller-selected path, filename, command, unit, operation string, transaction identity, lease, raw approval bytes, activation token or confirmation token.

## Fixed host observations

Each existing read-only host observation is attempted exactly once:

```text
inspect_host_contract()
inspect_production_lock()
capture_service_state(observation_transaction)
capture_mixer_state(observation_transaction)
capture_loopback_state(observation_transaction)
capture_dac_state(observation_transaction)
```

An unexpected exception in one domain becomes the exact typed failed `AdapterResult` for that operation. The remaining domains are still observed, and no operation is retried.

## Fixed approval observation

The only approval path is:

```text
/var/lib/a-clockwork-plex/split-bus/activation-approved
```

The observer:

- traverses only the fixed path;
- opens each directory with `O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`;
- opens the approval with `O_RDONLY | O_NOFOLLOW | O_CLOEXEC`;
- validates descriptor/path identity;
- requires root ownership;
- requires the packaged state-directory mode `0755`;
- requires an approval regular file of mode `0600` and link count one;
- reads at most 64 KiB using a descriptor-pinned bounded read;
- verifies stable identity before and after the read;
- creates, changes and removes nothing.

The observer has no create, write, truncate, fsync, link, unlink, rename, replace, chmod, chown or directory-creation capability.

## Strict approval classification

The runtime approval record is parsed without constructing the mutable runtime `ApprovalStore`.

Validation includes:

- UTF-8 decoding;
- duplicate JSON field rejection;
- exact envelope fields;
- exact record field set;
- exact field types, including rejection of booleans as integers;
- runtime schema and phase invariants;
- embedded record checksum;
- canonical JSON bytes;
- exactly one final newline.

The resulting baseline states are:

```text
ABSENT
VALID_TEMPORARY_UNBOUND
VALID_COMMITTED
MISMATCHED
OBSERVATION_FAILURE
```

A canonical temporary record remains unbound evidence because the baseline inspector has no held transaction authority. A canonical committed record indicates an existing installed or reconciliation state. Both block the first-install baseline path.

A safely observed but malformed object is `MISMATCHED`. A path that could not be observed safely is `OBSERVATION_FAILURE`; absence is never inferred from an observation error.

## Frozen prepare-only report

The report preserves the exact six host result objects, exact approval observation and candidate package fingerprint.

Its dispositions are:

```text
BASELINE_READY
EXISTING_APPROVAL_REQUIRES_REVIEW
PRODUCTION_LOCK_PRESENT
HOST_OBSERVATION_FAILED
APPROVAL_OBSERVATION_UNAVAILABLE
```

Fail-closed precedence is:

1. approval observation unavailable;
2. any present approval object;
3. failed lock observation;
4. present production lock;
5. another failed host observation;
6. exact baseline ready.

`BASELINE_READY` means only that the frozen observations are suitable for human review. It grants no installation or activation authority.

Every report permanently fixes these values to false:

```text
production_mutation_authorised
activation_authorised
pi_execution_authorised
review_bundle_persisted
production_lock_acquired
transaction_created
```

## Tests

Primary suite:

```text
tests/test_stage_c_production_prepare_only_inspector_v7.py

7c1a26dde18081b07762689855f7d70d46719267
test: cover Stage C21 production prepare-only inspector
```

After the first successful CI run, the low-level observer's fail-closed exception contract was made explicit with:

```text
tests/test_stage_c_production_prepare_only_approval_observer_v7.py

2a134d10d3ace0e7029d6736e1df8dbe302f0f46
test: prove prepare-only approval observer fails closed
```

No production implementation change was needed: the observer already converts unexpected low-level exceptions into typed `OBSERVATION_FAILURE`. The additional test now makes that guarantee non-regressable.

The complete tests prove:

- exact baseline-ready reporting;
- exact underlying result identity preservation;
- every observation called once;
- all observations attempted despite a domain failure;
- no automatic retry;
- fail-closed disposition precedence;
- present production lock blocks baseline readiness;
- temporary, committed and mismatched approvals block baseline readiness;
- observation failure remains distinct from a mismatched object;
- exact temporary and committed runtime record parsing;
- invalid JSON, duplicate fields, wrong checksums, wrong types and unsupported schema fail closed;
- non-canonical whitespace and newline forms fail closed;
- wrong file mode, owner, link count or size fail closed;
- unexpected low-level observation exceptions return typed failure;
- report and observation records are frozen;
- no authority flag can become true;
- no caller-selected path or command exists;
- no filesystem mutation primitive exists;
- no CLI, process, service, audio or device command exists;
- `scripts/install-master-eq.sh` is not referenced;
- the v7 operation vocabulary remains exactly forty-two;
- all four production approval operations remain blocked.

## Validation

Initial implementation run:

```text
GitHub Actions run 31063883063
job 92497408748

Ran 1132 tests in 8.673s
OK
```

Final fail-closed observer proof run:

```text
GitHub Actions run 31064050104
job 92497910270

Ran 1133 tests in 11.006s
OK
```

Compilation, JavaScript/page wiring, shell syntax and every inherited application, transaction, runtime, filesystem, sandbox, rehearsal and safety suite passed.

## Safety state

Unchanged:

- no Pi command was run;
- no production path was written;
- no production lock was acquired or created;
- no production transaction was created;
- no approval was created, changed or removed;
- no package was installed;
- no service or process was managed;
- no mixer, route, ALSA configuration or device was touched;
- no CamillaDSP process was started;
- no activation command exists in this slice;
- all four production approval mutations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- the accepted direct shared ALSA route remains authoritative;
- PR #2 remains required to stay Draft, open and unmerged.

## Roadmap

### Done

- disposable Stage C21 lock and approval mutation proofs;
- disposable lifecycle facade;
- production baseline observer design;
- fixed no-follow approval observation;
- strict runtime-record classification;
- frozen in-memory prepare-only report;
- typed fail-closed observation handling;
- 1,133-test validation.

### Current

Design a separate **prepare-only evidence renderer and fixed wrapper**.

The renderer must accept only an already-frozen `ProductionPrepareOnlyReportV7` and may write only beneath one fresh user-owned mode-`0700` review directory in `/var/tmp`.

### Next

The next slice must specify and prove:

- deterministic human-readable and canonical JSON evidence from the frozen report;
- no activation token, mutation command or future approval secret in the bundle;
- exact output file names and mode `0600`;
- no overwrite of an existing review directory or file;
- an unprivileged wrapper by default;
- at most one separately reviewed, tightly constrained read-only sudo invocation where root-readable production evidence is required;
- no production write, lock, transaction, service, route, mixer, audio or device authority;
- no Pi execution until that wrapper passes local safety tests and explicit approval is requested.

### Risks and gates

- the current inspector is not yet a public command;
- no evidence bundle is persisted yet;
- no production approval writer exists;
- no production lifecycle facade exists;
- no production executor integration exists;
- no activation command exists;
- no Pi action has been taken;
- all production approval operations remain blocked;
- PR #2 must remain Draft, open and unmerged.
