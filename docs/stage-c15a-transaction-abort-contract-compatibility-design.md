# Stage C15A transaction-abort contract compatibility — design

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Purpose

Stage C15 physically proved that an authoritative pre-mutation transaction must be explicitly aborted, evidenced and removed before the production lock may be released.

The original Stage C10 contract intentionally contained thirty-three operations and had no transaction-abort operation because the lifecycle had not yet been physically proved. Stages C10 through C14 and their result records must remain historically exact rather than being silently rewritten underneath accepted evidence.

Stage C15A therefore introduces a versioned compatibility view:

```text
Production adapter contract v1  33 accepted operations, unchanged
Production adapter contract v2  the same 33 operations plus abort-uncommitted-transaction
```

This is a contract-only stage. It performs no host access and provides no Pi command.

## Why a versioned view

Editing the original enum in place would make the already accepted C10, C13 and C14 operation counts false after the fact. A versioned view preserves those records while making the physically proved lifecycle available to later stages.

The v2 vocabulary contains exactly thirty-four operations:

```text
17 read-only or validation operations
17 potentially mutating or lifecycle operations
```

The single new operation is:

```text
abort-uncommitted-transaction
```

It is a transaction-lifecycle operation, not a whole uninstall or rollback shortcut.

## Production method shape

The production-facing method is fixed as:

```python
abort_uncommitted_transaction(transaction)
```

The caller supplies only the adapter-generated `TransactionIdentity`.

The caller cannot supply:

- a production transaction path;
- an evidence-copy path;
- a transaction root;
- a command or `argv`;
- a unit, mixer control or hardware endpoint;
- an arbitrary state string.

The production adapter owns its audit-evidence location internally.

This deliberately differs from the Stage C15 physical rehearsal helper, which accepted a fresh `/var/tmp` evidence-copy destination because that rehearsal had to return a reviewable copy to the invoking user. C16 will be the first adapter to bridge the rehearsal implementation to the production-facing v2 method shape.

## Typed receipt

A successful abort returns an immutable receipt proving:

```text
state                    aborted-before-mutation
mutation_started         false
committed                false
transaction_path_absent  true
parents_restored         true
audit_evidence           non-empty adapter-owned reference
```

A failed or blocked result cannot carry a receipt.

## Compatibility boundary counts

The v2 view changes only the blocked-operation accounting:

```text
Stage C13  6 permitted, 28 blocked
Stage C14  8 permitted, 26 blocked
Stage C15  11 permitted, 23 blocked
```

Stage C15 remains effectively eleven permitted lifecycle operations: its ten original `AdapterOperation` methods plus the explicitly proved abort.

The historical physical evidence remains correct:

- C13 physically proved the six observations and refused all twenty-seven operations in the then-current v1 vocabulary;
- C14 physically proved eight operations and refused all twenty-five remaining v1 operations;
- C15 physically proved ten v1 operations, refused twenty-three later v1 operations and separately proved the explicit abort lifecycle.

No physical result document is rewritten.

## Safety boundary

The Stage C15A module must contain:

- no filesystem, process, lock, service, mixer, audio or network imports;
- no CLI or confirmation token;
- no generic command or dynamic dispatch method;
- no activation interface;
- no implementation of transaction cleanup;
- no adapter-level explicit uninstall shortcut.

Its blocked v2 adapter must refuse the new abort operation with its exact identity while inheriting the original blocked adapter for all thirty-three v1 operations.

## Acceptance

Stage C15A passes when automated tests prove:

1. the v1 contract remains exactly thirty-three operations;
2. v2 adds exactly one non-duplicated operation;
3. v2 partitions exactly seventeen read-only and seventeen mutating/lifecycle operations;
4. abort is in the mutating/lifecycle partition;
5. the v2 protocol adds exactly one method;
6. the method accepts only the transaction identity;
7. the blocked v2 adapter refuses the exact abort identity;
8. the receipt and result are immutable and fail closed;
9. the C13/C14/C15 v2 boundary counts are exact;
10. explicit uninstall remains transaction policy rather than an adapter shortcut;
11. the module has no host-access or entrypoint boundary;
12. the original C10 contract and result remain unchanged.

## Roadmap

```text
Stage C15   physical authoritative snapshot and explicit pre-mutation abort
Stage C15A  versioned transaction-abort contract compatibility
Stage C16   package staging and candidate validation only, then explicit abort
Later       separately guarded service, installation, rollback and failback stages
```

Persistent Stage C activation remains blocked. The old master-EQ installer remains blocked. PR #2 must remain Draft, open and unmerged until explicit approval.