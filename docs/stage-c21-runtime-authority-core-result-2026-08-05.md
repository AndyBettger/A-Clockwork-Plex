# Stage C21 activation-capable runtime authority core — automated result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: **PASS — non-physical core only**

## Roadmap position

Stages C17 through C20 physically proved the reversible production mutation prefix:

```text
service quiescence
→ managed-file installation
→ systemd daemon reload
→ temporary split-bus route selection
→ exact route, file, manager and service rollback
```

Stage C20 is the last physical rehearsal that can honestly use the immutable Stage C1 candidate-only package. That package deliberately blocks `boot-select` and every route-changing helper action, and its units require an approval record that no accepted rehearsal creates.

Stage C21 therefore begins the activation-capable runtime implementation. This result covers only the pure authority core and disposable approval storage. It does not approve a new package, Pi host review, managed-service startup, CamillaDSP startup, audio probes or persistent activation.

## Implemented boundary

The new `scripts/stage_c_runtime_authority/` package contains:

- an immutable typed runtime-action vocabulary;
- exact hardware and package contracts;
- structured temporary and committed activation-approval records;
- canonical JSON and SHA-256 record envelopes;
- separate installation hand-off and ordinary-boot state machines;
- atomic no-overwrite approval publication;
- exact approval promotion using `renameat2(RENAME_EXCHANGE)`;
- interruption recovery that restores the temporary approval;
- a disposable review runner using only a supplied laboratory root.

No arbitrary command, path, service, route or transaction dispatcher exists.

## Installation hand-off

The hand-off accepts only an already-held production transaction. It refuses unless:

- the production lock is already held;
- the candidate is validated;
- package fingerprint and selected split-bus route match exactly;
- exactly twelve managed files are installed;
- exactly the three fixed managed units are loaded, inactive and dead;
- the DAC and loopback playback endpoints remain released.

Its fixed decision is only:

```text
accept-install-transaction-handoff
publish-temporary-activation-approval
```

It cannot reacquire the lock, reselect the route, start CamillaDSP or publish boot eligibility.

## Structured approval

The checksummed record binds schema and phase, transaction and lease identities, package fingerprint, route/config/binary digests, loopback and DAC contracts, canonical UTC timestamps and—after promotion—the commit-manifest digest.

Temporary approval is transaction-bound and not boot eligible. Promotion requires the same transaction and lease, the held lock, successful install commit, exact selected route and passed split-bus health.

## Ordinary boot decision

A healthy exact observation produces:

```text
acquire-production-lock
→ validate-committed-stage-c-state
→ select-split-bus-route
→ start-camilladsp
→ verify-split-bus-health
→ publish-split-bus-active
→ release-production-lock
```

If the split route, loopback, CamillaDSP binary/configuration, startup or strict health fails—but the committed package, direct route and DAC remain valid—the fixed decision is the alarm-safe failback sequence:

```text
acquire-production-lock
→ validate-committed-stage-c-state
→ stop-camilladsp
→ select-direct-failback-route
→ publish-direct-failback
→ release-production-lock
```

This preserves the physically accepted alarm-independent route rather than leaving the appliance without usable audio because a DSP-specific prerequisite failed.

## Approval storage

The store is constrained beneath a caller-supplied real directory and uses:

- `O_NOFOLLOW` file and directory access;
- `O_CREAT|O_EXCL` private creation;
- hard-link no-overwrite publication;
- file and directory `fsync` boundaries;
- canonical reread after publication;
- `RENAME_EXCHANGE` promotion;
- exact expected/replacement record verification;
- exchange-back recovery after injected interruption.

Publication, promotion and removal require an explicit held-lock assertion.

## Automated proof

Twenty focused tests passed locally before publication, covering:

- fixed action vocabulary;
- hand-off success and every critical refusal gate;
- temporary-to-committed promotion;
- healthy split-bus boot;
- CamillaDSP, loopback or binary failure to direct failback;
- temporary approval and package mismatch refusal;
- canonical UTC timestamps;
- record checksum and unknown-field rejection;
- no-overwrite/no-follow publication;
- exact exchange promotion and removal;
- injected interruption after link and after exchange;
- compilation, shell syntax and disposable-root execution;
- absence of host mutation, network and arbitrary dispatch boundaries.

The disposable review produced seven PASS rows and invoked no `sudo`, `systemctl`, ALSA, PCM, mixer, CamillaDSP process, network access or production path.

## Next stage

```text
runtime authority core                    PASS
→ versioned activation-capable package    NEXT
→ disposable package validation
→ prepare-only Pi package review
→ managed-service startup + exact rollback
→ split-bus health and finite probes
→ install commit
→ deliberate runtime direct failback
→ reboot selection
→ explicit uninstall
```

Persistent Stage C activation remains blocked. The bare `scripts/install-master-eq.sh` path must not be run. PR #2 must remain Draft, open and unmerged until explicit approval.
