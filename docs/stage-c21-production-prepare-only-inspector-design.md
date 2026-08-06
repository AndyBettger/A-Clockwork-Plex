# Stage C21 guarded production prepare-only inspector design

## Purpose

Define the first production-shaped Stage C21 integration boundary without granting any production mutation authority.

This boundary is a **baseline inspector and in-memory evidence report**, not an installer, transaction owner, approval writer, activation command or Pi execution entrypoint.

Its first responsibility is to answer one narrow question:

> Does the currently untouched appliance still match the physically accepted pre-Stage-C baseline closely enough for a later, separately approved read-only Pi inspection command to be designed?

It must not pretend that an install transaction, production lock lease or transaction-bound approval plan already exists.

## Two read-only authority contexts

The repository now contains two deliberately different observation contexts.

### Baseline appliance observation

`ReadOnlyHostProductionAdapter` observes the appliance before a production transaction exists. It can inspect only:

- the fixed host contract;
- the production lock pathname;
- the exact six service states;
- the exact four mixer values;
- the fixed loopback contract;
- the fixed physical DAC contract and current owners.

This is the only context used by the first prepare-only inspector.

### Held transaction observation

`BorrowedProductionAuthorityViewV7` observes an already-created authoritative transaction beneath an already-held C20 production lock.

It requires exact lock, transaction, route, package and snapshot identities and therefore cannot be used to manufacture evidence for an untouched baseline appliance.

A future held-transaction inspector may compose that view with transaction-specific temporary and committed approval plans. It is outside this slice.

## Fixed production paths

The baseline inspector has no caller-selected path.

```text
production lock
/run/lock/a-clockwork-plex-audio-route.lock

activation approval
/var/lib/a-clockwork-plex/split-bus/activation-approved
```

The approval observer traverses the fixed directory chain from `/` using directory descriptors opened with:

```text
O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC
```

The public approval object is opened relative to the pinned final directory descriptor with:

```text
O_RDONLY | O_NOFOLLOW | O_CLOEXEC
```

It performs no create, write, truncate, link, unlink, rename, exchange, chmod, chown, mkdir or fsync operation.

## Approval-root validation

The observer validates descriptor and pathname identity at every present directory component.

System ancestors `/`, `/var` and `/var/lib` must be:

- real directories;
- not symlinks;
- root-owned;
- not group- or world-writable.

If present, the private Stage C directories:

```text
/var/lib/a-clockwork-plex
/var/lib/a-clockwork-plex/split-bus
```

must additionally be mode `0700`.

A missing component means the fixed public approval object is absent. It does not create the missing directory.

## Public approval observation

A present public approval must be:

- a regular file, not a symlink;
- root-owned;
- mode `0600`;
- exactly one link;
- non-empty and no larger than 64 KiB;
- stable by descriptor/path identity before and after the bounded read.

The observer parses the existing runtime approval schema without importing or constructing `ApprovalStore`.

It validates:

- exact envelope fields;
- exact record field types and schema;
- embedded record checksum;
- canonical JSON encoding plus the required final newline;
- temporary versus committed phase invariants.

Semantically valid but non-canonical bytes are not accepted as an approval.

## Baseline approval states

```text
ABSENT
VALID_TEMPORARY_UNBOUND
VALID_COMMITTED
MISMATCHED
OBSERVATION_FAILURE
```

### ABSENT

No public approval object exists beneath a valid observed prefix. This is the expected first-install baseline.

### VALID_TEMPORARY_UNBOUND

A canonical temporary approval exists, but the baseline inspector has no held transaction authority with which to prove it belongs to a currently live install transaction.

It is evidence only and blocks first-install readiness.

### VALID_COMMITTED

A canonical committed approval exists. This indicates an installed or partially reconciled Stage C state and blocks the first-install baseline path.

The inspector records its transaction, lease, package and record identities but does not accept them as current authority.

### MISMATCHED

A public object is present but has wrong metadata, invalid bytes, a bad checksum, non-canonical encoding, an unsupported schema or another record mismatch.

It is never repaired, removed or replaced by this boundary.

### OBSERVATION_FAILURE

The fixed path could not be observed safely or consistently. This includes unavailable ancestors, descriptor/path substitution and unexpected read failures.

No state is inferred from absence of evidence.

## Inspector inputs

`ProductionPrepareOnlyInspectorV7` accepts only:

- one exact `ReadOnlyHostProductionAdapter` instance;
- one immutable `PackageFingerprint` identifying the candidate package under review.

It accepts no:

- path;
- filename;
- unit name;
- command;
- operation string;
- raw approval bytes;
- transaction identity;
- lock lease;
- activation token;
- confirmation token;
- fault or component factory.

The package fingerprint is review evidence only. It is not treated as an installed or transaction-bound package.

## Fixed observation sequence

The inspector explicitly invokes each permitted read-only adapter operation once:

```text
inspect_host_contract()
inspect_production_lock()
capture_service_state(observation_transaction)
capture_mixer_state(observation_transaction)
capture_loopback_state(observation_transaction)
capture_dac_state(observation_transaction)
observe fixed production approval
```

There is no generic dispatch loop and no automatic retry.

All observations are attempted so that one failed domain does not erase evidence from the others.

Unexpected exceptions are converted to the exact typed failed `AdapterResult` for that one read-only operation. They never trigger a second call.

## Prepare-only dispositions

```text
BASELINE_READY
EXISTING_APPROVAL_REQUIRES_REVIEW
PRODUCTION_LOCK_PRESENT
HOST_OBSERVATION_FAILED
APPROVAL_OBSERVATION_UNAVAILABLE
```

Precedence is fail-closed:

1. unsafe or unavailable approval observation;
2. any present approval state;
3. failed production-lock observation;
4. observed production lock present;
5. any other failed host observation;
6. exact baseline ready.

`BASELINE_READY` means only that the report is suitable for later human review. It does not authorise installation, activation or Pi execution.

## Frozen report

`ProductionPrepareOnlyReportV7` preserves the exact six underlying adapter result objects, the exact approval observation and the candidate package fingerprint.

It also fixes these safety facts:

```text
production_mutation_authorised = false
activation_authorised = false
pi_execution_authorised = false
review_bundle_persisted = false
production_lock_acquired = false
transaction_created = false
```

No caller may change those values.

## Deliberate omissions

This slice contains no:

- CLI or `main()`;
- shell wrapper;
- sudo command;
- output directory;
- JSON or text evidence writer;
- production adapter implementation beyond the existing six read-only observations;
- production approval writer;
- production lifecycle facade;
- transaction executor integration;
- lock acquisition or release;
- service, process, mixer, route, ALSA or device mutation;
- CamillaDSP start;
- installer invocation;
- activation command.

In particular, it does not use `scripts/install-master-eq.sh`.

## Test contract

The implementation tests must prove:

- exact baseline-ready report from six successful observations, absent lock and absent approval;
- every observation is invoked exactly once;
- all observations are attempted even when one fails;
- exact disposition precedence;
- a present lock blocks baseline readiness;
- temporary, committed and mismatched approvals all block first-install readiness;
- approval observation failure is distinct from a mismatched present object;
- valid temporary and committed runtime records are decoded and canonicality checked;
- invalid JSON, checksum, schema, envelope and non-canonical bytes are mismatched;
- frozen report and observation invariants;
- no caller-selected path or command input;
- no filesystem mutation primitive;
- no process, service, audio or device command boundary;
- no CLI, generic dispatch or automatic retry;
- v7 remains exactly forty-two operations;
- all four production approval operations remain blocked.

## Next boundary

Only after this in-memory inspector passes may the project design a separate evidence renderer and wrapper that:

- persists the already-frozen report beneath a fresh user-owned `/var/tmp` review directory;
- contains no activation token or mutation command;
- requires no sudo;
- performs no production write;
- is separately reviewed before any request to run it on the Pi.
