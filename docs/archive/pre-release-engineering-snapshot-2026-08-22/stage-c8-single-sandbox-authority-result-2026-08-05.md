# Stage C8 single sandbox transaction authority — physical result

Date: 2026-08-05  
Host: `plexamp-bedroom`  
Branch: `feature/alarm-engine`  
Pre-review branch head: `a73ec1b8ac7713400f2bb6f4a24a56fa84f1d6d0`

## Result

**PASS**

Stage C8 physically confirmed that the Stage C4 sandbox transaction now has one executable transaction and rollback authority:

```text
scripts.stage_c_transaction.sandbox_transaction
```

The retired duplicate module was absent:

```text
scripts/stage_c_transaction/sandbox_transaction_runtime.py
```

The rehearsal remained sandbox-only. It used no `sudo`, opened no audio device or PCM, issued no service-manager, mixer, module, PCM-owner or CamillaDSP commands, wrote no production path and exposed no production activation, install, rollback or uninstall interface.

Persistent Stage C activation remains blocked.

## Inputs

```text
Stage C1 package:
/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY

Stage C3 evidence:
/var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F

Stage C8 physical sandbox:
/var/tmp/a-clockwork-plex-stage-c4-sandbox.8oBimg
```

The existing Stage C4 wrapper was deliberately retained so that the physical review exercised the same external interface while proving that it now resolves to one internal authority.

## Exact command boundary

The physical run used:

```bash
bash scripts/test-stage-c-sandbox-transaction.sh \
  --run-sandbox \
  --confirm STAGE-C4-SANDBOX-TRANSACTION \
  --package-root /var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY \
  --stage-c3-root /var/tmp/a-clockwork-plex-stage-c3-snapshot.TV218F \
  --sandbox-root /var/tmp/a-clockwork-plex-stage-c4-sandbox.8oBimg
```

The outer command was not prefixed with `sudo`.

## Result checks

All nine top-level checks passed in the expected order:

1. `input-replay`
2. `sandbox-scope`
3. `first-install-boundary`
4. `install-success`
5. `explicit-uninstall-rollback`
6. `failure-injection`
7. `automatic-rollback`
8. `exact-state-verification`
9. `production-boundary`

Recorded result details:

```text
input-replay                  PASS  Stage C1 package and complete Stage C3 evidence replayed
sandbox-scope                 PASS  all mutation paths constrained beneath the Stage C8 sandbox
first-install-boundary        PASS  all twelve managed files began absent in every scenario
install-success               PASS  twelve files and synthetic split route verified before uninstall
explicit-uninstall-rollback   PASS  successful sandbox install restored files, state and captured directory modes
failure-injection             PASS  three independent transaction failure points exercised
automatic-rollback            PASS  all injected failures invoked the exact rollback implementation
exact-state-verification      PASS  all four scenarios ended with zero baseline mismatches
production-boundary           PASS  input trees unchanged; no production path or command was used
```

## Scenario evidence

All four scenarios completed with zero rollback mismatches:

| Scenario | Injected failure | Install verified | Rollback reason | Mismatches |
|---|---|---:|---|---:|
| `success-explicit-uninstall` | none | true | `explicit-uninstall` | 0 |
| `failure-after-files-installed` | `after-files-installed` | false | `automatic:after-files-installed` | 0 |
| `failure-after-route-selected` | `after-route-selected` | false | `automatic:after-route-selected` | 0 |
| `failure-after-services-restored` | `after-services-restored` | false | `automatic:after-services-restored` | 0 |

This confirms that the successful uninstall path and all three injected failure paths use the same rollback implementation.

## Directory-mode regression

The original mode of the pre-existing synthetic `/etc/sudoers.d` directory was restored in every scenario:

```text
failure-after-files-installed    mode=750
failure-after-route-selected     mode=750
failure-after-services-restored  mode=750
success-explicit-uninstall       mode=750
```

This is the specific regression that motivated consolidation of the corrected runtime implementation into the surviving authority.

## Transaction report

The generated report recorded:

```text
Sandbox version: 3
Managed package files: 12
Scenarios: 4
Injected failure points: 3
Final rollback mismatches: 0
Transaction authority: scripts.stage_c_transaction.sandbox_transaction
```

It also recorded one executable transaction and rollback authority, unchanged Stage C1 and Stage C3 input trees, exact restoration of captured directory modes, and no production writes or command execution.

## What Stage C8 proves

Stage C8 proves that:

- the duplicate Stage C4 orchestration path has been retired;
- the wrapper invokes one transaction module;
- the sole module replays the exact Stage C1 package and complete Stage C3 evidence;
- all twelve managed package files begin absent in every synthetic first-install scenario;
- successful installation and explicit uninstall restore the exact baseline;
- each independent injected failure invokes the same rollback implementation;
- all four scenarios finish with zero baseline mismatches;
- pre-existing directory modes, including synthetic `sudoers.d` mode `0750`, are restored exactly;
- no production path, service, audio device, module or CamillaDSP process is touched.

## What Stage C8 does not prove

Stage C8 does not prove:

- real ALSA parsing or PCM availability;
- CamillaDSP startup or DSP health;
- real DAC ownership or audio output;
- real systemd ordering or service behaviour;
- real music and alarm lane probes;
- runtime direct alarm-bypass failback;
- persistent installation, activation, exact production rollback or uninstall.

Those boundaries remain intentionally outside this sandbox-only consolidation review.

## CI state

Before the physical Pi run, the consolidated authority passed the complete automated suite:

```text
Ran 590 tests in 3.670s
OK
```

The automated Stage C4 rehearsal also completed with nine passing checks, four scenarios, zero rollback mismatches and the surviving authority named in the generated report.

## Acceptance

Stage C8 physical Pi review is accepted as **PASS**.

The transaction foundation is now simpler and safer: one wrapper, one transaction authority and one exact rollback implementation. This removes the risk that a future production adapter could accidentally select the stale orchestration path.

No persistent installer or activation interface was introduced. The blocked `scripts/install-master-eq.sh` path was not run, and production EQ activation remains prohibited pending further reviewed stages and explicit approval.
