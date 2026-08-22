# Stage C21 current-package transaction preparation — design correction

Date: 2026-08-06  
Applies to: `docs/stage-c21-current-package-transaction-preparation-design.md`

## Correction 1 — exact package phase

The immutable package phase is the value produced by the reviewed package generator:

```text
stage-c21-activation-capable-review-v2
```

The phrase `activation-capable-runtime-authority-v2` in the initial design is descriptive text, not the package-contract value. Implementations and tests must require the exact value above from `stage_c_activation_package.runtime_templates.PACKAGE_PHASE` and must not duplicate a second literal.

## Correction 2 — production state-root mode

The historical Stage C15/C16 parent contract creates:

```text
/var/lib/a-clockwork-plex/split-bus
```

as mode `0750`.

The reviewed current Stage C21 package manifest, production approval observer and accepted prepare-only contract require the fixed state root to be:

```text
root:root 0755
```

The current-package rehearsal must therefore override only the parent-contract tuple used by the inherited authoritative transaction owner:

```text
/var/lib/a-clockwork-plex                         root:root 0750
/var/lib/a-clockwork-plex/split-bus               root:root 0755
/var/lib/a-clockwork-plex/split-bus/transactions  root:root 0700
```

This does not create a second owner or transaction engine. The current-package adapter remains a subclass of the existing physically proved owner and reuses its lock, identity, snapshot and abort mechanics.

When `split-bus` and `transactions` were absent before the rehearsal, exact abort removes the transaction and both newly created empty parents, restoring absence. When a parent pre-exists, its exact device, inode, owner and mode must already match the corrected contract and must remain unchanged.

A pre-existing `split-bus` directory at historical mode `0750` is a hard pre-mutation mismatch. The rehearsal must not chmod it as a repair action.

## Implementation consequence

The new adapter may override only the package-bound methods and fixed parent-contract creation required by these two corrections:

- current package validation and fingerprint binding;
- current 28-file filesystem absence boundary;
- current 28-file candidate staging;
- current unit/runtime contract validation;
- corrected parent-contract creation.

All inherited read-only observation, production-lock ownership, transaction identity, service/mixer/loopback/DAC capture and exact-abort behaviour remains authoritative.

## Safety state

Unchanged:

- no Pi command is authorised by this correction;
- no production state was changed;
- all approval mutations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 remains Draft, open and unmerged.
