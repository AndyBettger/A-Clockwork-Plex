# Stage C21 runtime supervisor readiness gate

Date: 2026-08-05  
Branch: `feature/alarm-engine`  
Status: non-physical design and pure state-machine proof

## Roadmap position

Stages C17 through C20 proved the reversible production transaction prefix through temporary split-bus route selection and exact restoration. The first Stage C21 slice then added the structured runtime-authority core and approval record.

Before generating the activation-capable package, the three-unit startup graph needs one explicit application-service readiness gate. Merely ordering Plexamp, Shairport Sync and the dashboard after a route-selection oneshot does not prove that CamillaDSP passed strict health or that direct failback completed before those applications start.

This design resolves that gap without adding another managed unit.

## Retained managed units

The fixed managed set remains:

```text
a-clockwork-plex-audio-route.service
a-clockwork-plex-camilladsp.service
a-clockwork-plex-audio-failback.service
```

The route unit remains a oneshot preparation authority. The CamillaDSP unit becomes a `Type=notify` runtime supervisor that owns the CamillaDSP child and does not signal readiness until one complete usable route exists. The failback unit remains the last-resort systemd failure path if the supervisor itself cannot stay alive.

## Boot preparation phase

The route authority reads only committed Stage C state and validates the exact package, direct route and DAC contract.

If split-bus preflight passes:

```text
acquire production lock
→ validate committed state
→ select split-bus route
→ publish split-bus-pending-health
→ release production lock
```

This phase does not start CamillaDSP and does not release application services.

If a DSP-specific prerequisite fails but the committed package, direct route and DAC remain valid:

```text
acquire production lock
→ validate committed state
→ select direct alarm-bypass route
→ publish direct-failback
→ release production lock
```

The direct route is therefore complete before the supervisor or application services continue.

## Supervisor startup phase

The CamillaDSP service starts a small fixed-purpose supervisor rather than making the CamillaDSP binary the systemd main process directly.

For a prepared split-bus route:

```text
acquire production lock
→ validate committed state and pending route identity
→ start pinned CamillaDSP child
→ verify strict DAC, loopback and child health
→ publish split-bus-active
→ release production lock
→ sd_notify READY=1
→ remain alive as the runtime supervisor
```

If child startup or strict health fails:

```text
stop/reap CamillaDSP child
→ select direct alarm-bypass route
→ publish direct-failback
→ release production lock
→ sd_notify READY=1
→ remain alive as the runtime supervisor
```

The service is considered ready only after the direct route has replaced the unusable split route.

For an already prepared direct route, the supervisor validates that state, signals readiness and remains alive without starting a CamillaDSP child.

## Runtime child failure

After a healthy split-bus startup, the supervisor owns and watches the child process. If it exits:

```text
acquire production lock
→ stop/reap any remaining child state
→ select direct alarm-bypass route
→ publish direct-failback
→ release production lock
→ remain active
```

The application services are not deliberately restarted. Their public PCM names remain unchanged and the direct route retains Music Master while the alarm continues to bypass it.

## Why `Type=notify` matters

Systemd `Before=` and `After=` express ordering, not successful audio health. The supervisor's `READY=1` becomes the concrete boundary that application services wait behind.

The package design must require:

```text
Type=notify
NotifyAccess=main
Before=plexamp.service shairport-sync.service a-clockwork-plex.service
```

The supervisor must never notify readiness while the selected split-bus route lacks a healthy CamillaDSP owner.

## Failure ownership

During the first installation rehearsal, the authoritative install transaction still owns exact rollback. A temporary transaction-bound approval is not boot eligible.

At ordinary boot or after commit, the runtime supervisor owns route failback under the fixed production lock. It may select only the committed split route or the committed direct alarm-safe route. It may not restore the pre-Stage-C uninstall route.

If the supervisor itself fails before it can complete a usable route, `a-clockwork-plex-audio-failback.service` is the bounded last-resort route authority. That unit must use the same fixed direct-route transition and state publication code, not a second shell implementation.

## Automated proof in this slice

The pure `supervisor_model.py` proves:

- boot preparation cannot start CamillaDSP or notify readiness;
- a split-specific preflight failure prepares direct failback;
- healthy startup publishes split-bus health before readiness;
- failed startup completes direct failback before readiness;
- a prepared direct route never starts a CamillaDSP child;
- a post-readiness child failure retains the supervisor and selects direct failback;
- every supervisor transition requires the production lock;
- no host command, systemd, ALSA, PCM or notification boundary exists in the pure model.

## Next implementation

```text
pure supervisor/readiness model            current
→ package the core and supervisor model
→ implement fixed production host adapter
→ implement Type=notify supervisor entry
→ disposable package and injected-failure validation
→ prepare-only Pi package review
→ managed-service startup and exact rollback rehearsal
```

No Pi service, route, approval record or production file is changed by this design. Persistent activation remains blocked. The bare `scripts/install-master-eq.sh` path must not be run. PR #2 remains Draft, open and unmerged.
