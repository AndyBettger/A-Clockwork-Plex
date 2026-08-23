# Stage C21 approval-authority binding result — 2026-08-05

## Outcome

**PASS — the exact borrowed C20 authority and one reviewed Stage C21 hardware contract can now be combined into immutable, deterministic pre-write binding metadata, with a complete fail-closed publication-reconciliation policy.**

This remains pure policy/data code. It does not create a lease-binding receipt, build or write an activation approval record, inspect an approval pathname, mutate the filesystem, construct an adapter, expose a CLI or activate Stage C.

## Added files

- `scripts/stage_c_transaction/approval_authority_binding_v7.py`
- `tests/test_stage_c_approval_authority_binding_v7.py`

Commits:

```text
a54d2bfcceb8ea849bef1ecb79abe0d9fe8868da
feat: bind Stage C21 approval authority metadata

9ed22c2e2a8223f853dc3b04deabcc74471e82db
test: prove Stage C21 approval authority binding
```

## Why this is pre-write metadata

The v7 host receipts make strong claims:

- the canonical lock-lease content was durably written;
- the exact inode was verified;
- an external service can observe it;
- an approval was atomically published or promoted;
- the exact published record was verified.

The pure binding layer cannot truthfully make those claims. It therefore creates neither:

- `ProductionLockLeaseBindingReceipt`;
- `TemporaryActivationApprovalReceipt`;
- `CommittedActivationApprovalReceipt`;
- `ActivationApprovalRecord`.

Those types remain reserved for a future host adapter after the relevant durable operation has really completed.

## Approval hardware contract

`ApprovalHardwareContractV7` freezes the reviewed runtime identity needed by the existing approval schema:

- package fingerprint;
- split-route SHA-256;
- direct-route SHA-256;
- CamillaDSP configuration SHA-256;
- CamillaDSP binary version and SHA-256;
- loopback index, ID, substream count and notify mode;
- DAC card/device;
- sample rate and format;
- period and buffer sizes.

It applies the same bounded token, lowercase SHA-256 and numeric geometry rules required by the runtime authority model. Booleans are rejected where integers are required.

## Authority binding

`bind_approval_authority_v7()` requires exactly:

- one `BorrowedAuthorityViewV7`;
- one `ApprovalHardwareContractV7`.

It rejects the binding unless:

- hardware package equals the authoritative transaction package;
- hardware split-route digest equals the currently selected route digest;
- every source proof remains true;
- all inode/device identities are positive and typed;
- every digest and lease token is canonical.

A successful `ApprovalAuthorityBindingV7` preserves:

- transaction and snapshot identities;
- package fingerprint;
- canonical production lock path;
- existing lock lease ID, device and inode;
- authoritative transaction path, device and inode;
- selected route path, device, inode and digest;
- complete hardware contract;
- complete-snapshot, selected-route, exact-lock and exact-transaction proof flags.

It exposes no:

- descriptor or file descriptor;
- adapter or owner reference;
- callback;
- mutation operation;
- approval pathname;
- timestamp;
- host receipt.

## Deterministic binding digest

The complete binding serialises to sorted compact ASCII JSON and produces one deterministic SHA-256.

The digest changes when any bound identity changes, including reviewed direct-route or hardware metadata. It can later be incorporated into a durable approval/manifest design, but this phase does not publish it anywhere.

## Publication-knowledge model

The pure policy freezes five states:

1. `absent-confirmed`
2. `temporary-confirmed`
3. `committed-confirmed`
4. `temporary-publication-indeterminate`
5. `committed-promotion-indeterminate`

Every state begins while the existing production lock remains held. Blind approval rollback is never permitted.

### Confirmed absence

Only one action is allowed:

```text
publish-temporary
```

### Confirmed temporary approval

Two actions are allowed:

```text
continue-temporary-install
remove-exact-temporary-during-rollback
```

Removal means the exact already-verified temporary record, not pathname-only deletion.

### Confirmed committed approval

Only one action is allowed:

```text
forward-recovery-only
```

Exact install rollback is forbidden after committed publication is authoritative.

### Indeterminate temporary publication

Only one action is allowed:

```text
reconcile-exact-record-retain-lock
```

No retry, rollback or forward recovery is permitted until the exact record state is observed.

### Indeterminate committed promotion

The same single fail-closed action applies. Reconciliation must distinguish:

- exact temporary record still present;
- exact committed record present;
- approval absent;
- substituted or mismatched record;
- observation failure.

Only after that classification may the transaction choose exact rollback or forward recovery.

## Validation

GitHub Actions push run:

```text
31054782914
```

validated branch head:

```text
9ed22c2e2a8223f853dc3b04deabcc74471e82db
```

Full result:

```text
Ran 1040 tests in 6.279s

OK
```

The new tests prove:

- exact authority/hardware projection;
- no descriptor, adapter or owner field;
- deterministic canonical binding SHA-256;
- digest sensitivity to reviewed metadata;
- package and selected-route mismatch rejection;
- hardware digest, token and geometry validation;
- frozen binding and hardware records;
- exact type and result-payload invariants;
- complete five-state reconciliation coverage;
- distinct confirmed-absence, temporary and committed actions;
- one fail-closed action for both indeterminate states;
- no host receipts, approval records or approval pathname;
- unchanged 42-operation adapter surface;
- absence of filesystem writes, commands, CLI and generic dispatch.

## Safety state

Unchanged:

- the known-good direct shared ALSA mixer remains active;
- no Stage C package was installed;
- CamillaDSP was not started;
- no production lock was acquired;
- no production transaction was created;
- no lock lease or approval was written on the appliance;
- no route, service or endpoint was touched;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.

## Next architectural gate

The next missing boundary is exact-record planning and reconciliation, not a production writer.

Before any host adapter writes the production approval pathname, the project must define and prove:

1. one canonical temporary approval record derived from the binding and an explicit timestamp;
2. its exact canonical byte digest before publication;
3. one canonical committed record derived only from that exact temporary record plus a durable commit-manifest digest and commit timestamp;
4. a pure classifier for absent, exact temporary, exact committed and mismatched observed records;
5. deterministic resolution from both indeterminate publication states;
6. compatibility with the existing runtime `ActivationApprovalRecord` schema without duplicate Python module identities;
7. disposable ApprovalStore tests covering every reconciliation outcome.

That work should remain pure/disposable. A production approval writer and activation entrypoint remain blocked until the record plan and reconciliation classifier are complete and reviewed.
