# Stage C21 exact approval-record plan result — 2026-08-05

## Outcome

**PASS — Stage C21 can now plan the exact canonical temporary and committed approval records before publication, classify observed approval bytes exactly, and resolve both indeterminate publication boundaries without blind rollback or unsafe retry.**

This phase remains pure/disposable. It did not introduce a production approval writer, production pathname, entrypoint, lock acquisition, service action, ALSA access or activation route.

## Added files

- `scripts/stage_c_transaction/approval_record_plan_v7.py`
- `tests/test_stage_c_approval_record_plan_v7.py`

Commits:

```text
e2d5593194fa681c619dcae8f922ab55432eb502
feat: plan and classify exact Stage C21 approval records

e3e38f8f8ae1e781afb0abd3474d062c46f6dfcf
test: prove exact Stage C21 approval record planning
```

## Canonical temporary record

`plan_temporary_approval_v7()` consumes one immutable `ApprovalAuthorityBindingV7` and an explicit canonical UTC timestamp.

It uses the existing top-level runtime-authority model and encoder to produce:

- one canonical `ActivationApprovalRecord` in temporary phase;
- exact canonical envelope bytes, including the trailing newline;
- record SHA-256;
- encoded-byte SHA-256;
- originating authority-binding SHA-256.

The record preserves the exact transaction, lease, package, selected route and reviewed hardware contract. It contains no commit fields and is not boot eligible.

## Canonical committed record

`plan_committed_approval_v7()` accepts only the exact temporary plan plus:

- a lowercase durable commit-manifest SHA-256;
- an explicit canonical commit timestamp.

It derives the committed record through the existing runtime model's `promote()` operation, preserving the original creation timestamp and every hardware/authority field. Promotion must change both record and encoded-byte identity.

## Exact observation classifier

`classify_approval_record_v7()` returns exactly one of:

- `absent`
- `exact-temporary`
- `exact-committed`
- `mismatched`
- `observation-failure`

Exact means the observed bytes equal the planned canonical bytes. Valid JSON that decodes to the same semantic record but uses different whitespace or ordering is still `mismatched`. This prevents a substituted or rewritten record from being accepted merely because it has equivalent fields.

Invalid JSON/checksum/schema is `mismatched`; inability to observe the store at all is separately `observation-failure`.

## Indeterminate temporary publication

After an exception during temporary publication:

- observed absent → exact rollback may proceed without approval removal;
- observed exact temporary → the held transaction may continue;
- exact committed, mismatched or observation failure → retain lock for manual reconciliation.

No blind retry is authorised.

## Indeterminate committed promotion

After an exception during committed promotion:

- observed exact temporary → exact rollback may remove that exact record;
- observed exact committed → forward recovery only;
- absent, mismatched or observation failure → retain lock for manual reconciliation.

No rollback is authorised after exact committed state is observed.

## Disposable ApprovalStore proof

The tests used the real existing `ApprovalStore` beneath fresh 0700 temporary roots.

They proved:

1. absent classification before publication;
2. `publish_new()` writes bytes exactly equal to the planned temporary bytes;
3. the classifier returns `exact-temporary`;
4. `replace_exact()` writes bytes exactly equal to the planned committed bytes;
5. the classifier returns `exact-committed`;
6. the same canonical top-level runtime model class is used by plan, store and tests.

## Validation

GitHub Actions run:

```text
31055168138
```

validated branch head:

```text
e3e38f8f8ae1e781afb0abd3474d062c46f6dfcf
```

Full result:

```text
Ran 1052 tests in 7.592s

OK
```

Coverage includes canonical schema/bytes, deterministic digests, timestamp and manifest validation, absent/temporary/committed classification, non-canonical valid JSON, different valid records, invalid bytes, observation errors, disposable atomic publish/promotion, every indeterminate resolution, immutable records and absence of any store-writing or host boundary in the planning module.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock or transaction was created;
- no production approval was written;
- no route, service or endpoint was touched;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next review gate

The first actual approval writer is now the next missing boundary, but it remains blocked pending a dedicated design review.

That review must define:

1. how the writer receives the already-held lock descriptor without transferring ownership;
2. how it re-verifies the borrowed-authority binding immediately before every write;
3. canonical production lease-file content and external-observer semantics;
4. exact no-follow root/path ownership and mode checks;
5. atomic temporary publication, exact rollback removal and atomic committed promotion;
6. post-exception observation and automatic use of the proved reconciliation classifier;
7. fail-closed lock retention whenever observation is mismatched or unavailable;
8. a disposable production-shaped adapter test before any appliance command exists.

No production writer, installer command or physical activation should be added until that design is reviewed as a separate milestone.
