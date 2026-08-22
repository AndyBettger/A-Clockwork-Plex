# Stage C21 disposable activation-approval lifecycle — automated result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: **PASS — disposable transaction bridge only**

## Roadmap position

The Stage C21 activation-capable runtime package v2 passed its disposable package review, but no authoritative install transaction could yet create the temporary approval that permits its managed units to enter the first-start path.

This result proves the missing approval lifecycle entirely beneath a fresh sandbox root:

```text
held transaction lock
→ bind canonical lease to the exact lock inode
→ publish temporary transaction-bound approval
→ remove that exact approval during rollback
OR
→ promote it atomically after commit
```

No production adapter or Pi entrypoint is enabled by this result.

## Versioned transaction contract

`production_adapter_lifecycle_v7.py` preserves the exact 38-operation v1 through v6 history and appends only four transaction-owned operations:

```text
bind-production-lock-lease
publish-temporary-activation-approval
remove-temporary-activation-approval
promote-committed-activation-approval
```

The v7 partition is:

```text
total operations:    42
read-only operations: 17
mutating operations:  25
```

At the contract gate all four new operations remain blocked. Typed immutable receipts require:

- exact transaction and fixed path identities;
- canonical lease content on the exact held lock inode;
- a temporary approval that is never boot eligible;
- rollback removal of the exact expected temporary record;
- committed promotion to a different exact record identity;
- a bound commit-manifest SHA-256;
- atomic publication or promotion followed by exact reread verification.

The service helper still has no approval-creation or approval-promotion interface.

## Disposable implementation boundary

`DisposableActivationApprovalLifecycleAdapter` subclasses the blocked v7 adapter and overrides exactly the four new operations.

All v1 through v6 production operations remain blocked, including host observation, file installation, systemd reload, route selection, service startup and commit-manifest writing.

The adapter requires one caller-supplied laboratory root that is:

- absolute;
- already present;
- a real directory rather than a symlink;
- owned by the current rehearsal user;
- mode `0700`;
- empty before construction.

Every file and directory it creates remains beneath that root. It has no production path mapping.

## Real disposable lock proof

The adapter creates one sandbox lock file corresponding to the production contract path:

```text
<root>/run/lock/a-clockwork-plex-audio-route.lock
```

It proves:

- `O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC` creation;
- mode `0600`;
- exact descriptor/path device and inode identity;
- a real exclusive non-blocking `flock`;
- contention from a separately opened descriptor;
- an initially empty file before lease binding;
- canonical `<lease-id>\n` content after binding;
- unchanged inode across binding;
- refusal after pathname substitution, owner change, mode change or content replacement;
- exact-inode unlink only when the disposable transaction closes.

A temporary approval may not be left behind when the lock is released.

## Temporary approval publication

The adapter uses the same `ApprovalStore` implementation packaged for production runtime.

Normal publication requires:

- the exact transaction identity;
- a live bound lock lease;
- an absent approval path;
- a temporary record whose transaction, package and lease match the adapter;
- atomic no-overwrite hard-link publication;
- exact canonical reread.

The resulting receipt explicitly records `boot_eligible=False`.

### Publication interruption handling

Two publication boundaries were injected:

```text
new-temp-fsynced
new-linked
```

Results:

- interruption after the private temporary file is fsynced leaves the public approval absent and permits a clean retry;
- interruption after the public hard link exists reconciles the exact public temporary record and returns a successful typed receipt;
- no temporary helper file remains after either path.

## Exact rollback removal

Rollback removal requires the currently published approval to equal the exact expected temporary record.

It refuses:

- an already absent record;
- malformed or checksum-invalid content;
- a different valid record;
- a substituted approval inode.

Injected boundaries:

```text
before-temporary-removal
after-temporary-removal
```

Results:

- interruption before unlink preserves the exact record and permits retry;
- interruption after unlink reconciles exact absence and returns a successful rollback receipt.

## Committed promotion

Promotion remains unavailable until the disposable rehearsal records one immutable commit-manifest digest for the same transaction.

The adapter then constructs the committed record through `ActivationApprovalRecord.promote()` and uses exact atomic exchange promotion.

Acceptance requires:

- the exact temporary record still present;
- unchanged transaction, lease, package, route, binary, loopback and DAC identities;
- one valid lowercase commit-manifest SHA-256;
- a canonical committed UTC timestamp;
- a changed record SHA-256;
- `boot_eligible=True`;
- exact committed reread.

Injected boundaries:

```text
replacement-temp-fsynced
replacement-exchanged
```

Both paths restore the exact temporary record after interruption, allowing a clean retry. No partially committed state is accepted.

## Automated result

GitHub Actions run `31049067405` completed successfully at head:

```text
c46cf34cdf1934bda0d9bcbb5bda7877548f6716
```

Result:

```text
Ran 967 tests in 6.250s
OK
```

The new focused proof covers:

- fresh-root, ownership, mode and symlink rejection;
- actual `flock` contention;
- exact lease binding and reconciliation;
- all prior production operations remaining blocked;
- temporary publication, idempotent reconciliation and both injected publication failures;
- exact rollback removal and both injected removal failures;
- immutable commit-manifest recording;
- exact temporary-to-committed promotion and both exchange failures;
- tampered-record refusal;
- exact lock closure and substituted-lock preservation;
- absence of subprocess, systemd, ALSA, PCM, mixer, network or generic dispatch boundaries.

## What this result does not approve

This result does not approve:

- writing the real production lock or approval path;
- installing package v2 on `plexamp-bedroom`;
- starting any managed Stage C unit;
- starting CamillaDSP;
- changing the production ALSA route;
- enabling a service;
- committing an installation;
- persistent activation.

## Next stage

The four v7 operations must now be placed into one static install/rollback program with unambiguous failure ownership.

The next design must resolve the terminal boundary explicitly:

```text
temporary approval publication
→ managed first-start and health
→ commit-manifest publication
→ committed approval promotion
→ final transaction close
```

A promotion failure must not be mistaken for an ordinary pre-commit rollback if the commit manifest has already become externally authoritative. The program must therefore define one exact terminal publication policy before any production implementation exists.

Persistent activation remains blocked. The bare `scripts/install-master-eq.sh` path must not be run. PR #2 must remain Draft, open and unmerged until explicit approval.
