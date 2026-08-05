# Stage C21 activation-capable runtime package v2 — automated result

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: **PASS — disposable package review only**

## Roadmap position

Stages C17 through C20 physically proved the reversible production mutation prefix through temporary split-bus route selection and exact restoration. The first Stage C21 slices then implemented and tested:

```text
structured activation authority
→ supervised Type=notify readiness gate
→ committed boot/runtime lane
→ temporary transaction-held first-start lane
→ child lifetime and commit-boundary failback policy
→ guarded installed fixed-action entrypoint
```

This result promotes those reviewed pieces into one separately versioned package candidate. It does not install or activate that package.

## Package identity

```text
package version:       2
package phase:         stage-c21-activation-capable-review-v2
total package files:   28
fingerprinted payload: 27 files
runtime modules:       15
recording test adapter: absent
```

The package fingerprint is deterministically calculated from the ordered destination path and SHA-256 digest of every payload file except the package contract that carries the fingerprint.

Stage C1 remains immutable historical candidate-only evidence. No Stage C1 file was edited or relabelled as activation-capable.

## Runtime contents

The v2 package contains:

- structured temporary and committed activation approval records;
- atomic approval publication and exact promotion primitives;
- separate install hand-off and ordinary boot state machines;
- a fixed typed runtime executor;
- one fixed Linux filesystem authority;
- one fixed CamillaDSP child and systemd notification authority;
- ordinary committed runtime composition;
- temporary transaction-held first-start composition;
- supervisor lifetime and commit-boundary policy;
- one installed fixed-action entrypoint;
- the split-bus and direct alarm-safe ALSA candidates;
- the pinned CamillaDSP 4.1.3 binary and configuration;
- the corrected three-unit systemd graph;
- read-only project-user sudo rules for `status` and `validate-runtime` only.

The production package excludes `recording_runtime_adapter.py` and all other test doubles.

## Application readiness contract

The three managed units remain:

```text
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

The route unit prepares either the committed split route or the direct alarm-safe route. The CamillaDSP unit is `Type=notify` and does not release Plexamp, Shairport Sync or the dashboard until one of these conditions is complete:

```text
strictly healthy split-bus CamillaDSP
OR
completed direct alarm-safe failback
```

A split route without a healthy CamillaDSP owner can therefore never be treated as application-ready.

## Temporary install lane

A first service start occurs while the authoritative install transaction already owns the production lock.

The packaged temporary lane:

- requires a temporary approval bound to the exact transaction and package;
- proves an external process holds the exact 0600 production-lock inode;
- requires the canonical lock-file lease to match the approval lease;
- refuses an unlocked, substituted, malformed or wrong-lease lock;
- validates the transaction-selected split route without reselecting it;
- starts the one pinned CamillaDSP child;
- verifies exact DAC and loopback ownership and format health;
- publishes readiness only after strict health and after closing its borrowed lock assertion;
- stops the child and withholds readiness on failure;
- never performs runtime direct failback before commit;
- returns pre-commit failure ownership to the authoritative exact-rollback transaction.

The existing C14–C20 physical evidence remains historically exact. A later Stage C21 transaction version must add the new rule that the already-held lock file contains its canonical lease ID before the temporary service process starts.

## Committed runtime lane

At ordinary boot or after installation commit, the packaged authority:

- acquires and owns the fixed production lock itself;
- validates the committed package, approval, routes, binary, loopback and DAC;
- prepares split-bus when DSP preflight is valid;
- otherwise completes direct alarm-safe failback before application readiness;
- starts one fixed CamillaDSP child with exact argv and a restricted environment;
- drops that child to the configured project user and audio group;
- requires that one child PID exclusively owns both the DAC playback endpoint and fixed loopback capture endpoint;
- requires the exact proved DAC contract;
- requires MMAP, S16_LE, four-channel, 44.1 kHz loopback capture with valid integral period/buffer geometry;
- polls readiness for at most 30 seconds at 0.25-second intervals;
- publishes `READY=1` only after the final usable route is complete;
- switches to direct failback if the committed CamillaDSP child later exits;
- remains alive as the application readiness gate in direct mode.

## Installed entrypoint boundary

The helper exposes exactly:

```text
status
validate-runtime
boot-prepare
supervise
emergency-direct-failback
accept-install-handoff
promote-committed-approval
```

Operational execution is refused unless:

- the module runs from the exact installed runtime directory;
- the package phase is exactly `stage-c21-activation-capable-review-v2`;
- the package contract explicitly enables the reviewed host authority;
- every installed payload file matches its contract;
- the mutating action is running as root.

`accept-install-handoff` and `promote-committed-approval` are fixed identities reserved for the authoritative transaction. They remain deliberately unavailable through the service helper.

The repository copy cannot operate as the production runtime.

## Automated result

GitHub Actions run `31048099397` completed successfully at head:

```text
86b88b604ad6816850ca2cd49c847cd401f909d4
```

Result:

```text
Ran 938 tests in 6.249s
OK
```

The package-specific proof includes:

- exact 28-file package count;
- exact 15-module production runtime set;
- exclusion of recording/test adapters;
- deterministic 27-file package fingerprint;
- both ALSA route candidates parsing with all five public PCM names;
- pinned CamillaDSP binary and configuration validation;
- all runtime Python candidates compiling in memory;
- read-only sudoers validation;
- Type=notify application-readiness ordering;
- installed-image and root guards;
- fixed action vocabulary;
- transaction-only approval-operation refusal;
- no generator install, activation or confirmation interface;
- no generator sudo, systemd, module, process, PCM or mixer mutation.

## What this result does not approve

This result does not approve:

- installing the v2 package on `plexamp-bedroom`;
- changing the production ALSA route;
- writing a production lock or approval record;
- starting any managed Stage C unit;
- starting CamillaDSP;
- opening a music or alarm PCM;
- enabling any unit;
- committing a Stage C installation;
- reboot testing;
- persistent activation.

## Next stage

The next Stage C21 slice must extend the authoritative install transaction with three exact approval operations:

```text
write canonical lease into the already-held lock
→ publish temporary transaction-bound approval before managed startup
→ remove it during exact rollback OR promote it after health and commit
```

Those operations must be disposable and failure-injected before any Pi package review exists.

Persistent activation remains blocked. The bare `scripts/install-master-eq.sh` path must not be run. PR #2 must remain Draft, open and unmerged until explicit approval.
