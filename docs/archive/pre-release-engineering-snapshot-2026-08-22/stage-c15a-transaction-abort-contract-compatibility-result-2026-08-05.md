# Stage C15A transaction-abort contract compatibility — result

Date: 2026-08-05  
Branch: `feature/alarm-engine`

## Result

**PASS**

Stage C15A introduced a versioned v2 production-adapter contract view containing the physically proved `abort-uncommitted-transaction` lifecycle operation while preserving the original Stage C10 v1 contract and all earlier physical result records unchanged.

This was an automated contract-only stage. It performed no host access and provided no Pi command.

## Commits

```text
c7795b3b38c223406867c496af687ae65e92277c  design
23300ecba58e0167517baca7c7e6da9503af1f18  lifecycle contract
c7083f44b451a096c0c85db8710c44015b0c417a  focused safety tests
```

## Final automated result

```text
Ran 675 tests in 4.368s
OK
```

The full appliance suite, Stage C7 root-owned transaction rehearsal and consolidated Stage C4 sandbox rehearsal all remained green.

## Contract result

The compatibility view now records:

```text
v1 operations          33, unchanged
v2 operations          34
v2 read-only            17
v2 mutating/lifecycle   17
new operation           abort-uncommitted-transaction
activation interface    absent
```

The original `AdapterOperation` enum was not edited. Historical C10–C14 operation counts therefore remain exact.

## Production abort shape

The v2 production protocol adds exactly one method:

```python
abort_uncommitted_transaction(transaction)
```

It accepts only the adapter-generated `TransactionIdentity`.

It does not accept:

- a production path;
- an evidence-copy path;
- a transaction root;
- a command or `argv`;
- a unit, mixer control or endpoint override.

The adapter owns its audit-evidence location internally.

## Typed receipt

The immutable successful receipt requires:

```text
state                    aborted-before-mutation
mutation_started         false
committed                false
transaction_path_absent  true
parents_restored         true
audit_evidence           non-empty adapter-owned reference
```

A failed or blocked lifecycle result cannot carry a receipt.

## Versioned boundary accounting

The v2 compatibility counts are:

```text
Stage C13  6 permitted, 28 blocked
Stage C14  8 permitted, 26 blocked
Stage C15  11 permitted, 23 blocked
```

This does not alter what the physical runs proved under the v1 vocabulary. C15 separately proved its explicit abort lifecycle before v2 was defined.

## Safety proof

The focused tests proved:

- v1 remains exactly thirty-three operations;
- v2 adds one unique lifecycle operation;
- the v2 partitions are exactly seventeen and seventeen;
- abort is mutating/lifecycle, not read-only;
- the v2 protocol adds only the typed abort method;
- the blocked v2 adapter refuses the exact abort identity;
- the receipt and result are frozen and fail closed;
- explicit uninstall remains transaction policy, not an adapter shortcut;
- the module contains no filesystem, process, lock, service, mixer, audio or network access;
- no CLI, confirmation token, activation interface, generic command or dynamic dispatch exists.

## Roadmap conclusion

Stage C15A closes the lifecycle vocabulary gap discovered and physically proved by Stage C15.

Stage C16 may now bridge the rehearsal transaction to the v2 method shape while adding only package staging and candidate validation. Service stop, DAC release, managed-file installation, route selection and audio mutation remain blocked.

Persistent Stage C activation remains blocked. The old master-EQ installer remains blocked. PR #2 must remain Draft, open and unmerged until explicit approval.