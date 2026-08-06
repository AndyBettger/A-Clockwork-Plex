# Stage C21 current-package transaction rehearsal — accepted Pi result

Date: 2026-08-06  
Host: `plexamp-bedroom`  
Branch: `feature/alarm-engine`  
Reviewed source commit: `9621771f69df5c8a8246819d971aeb0cc4bc32f9`  
Result: **PASS — 32/32 checks complete; exact abort and cleanup confirmed; no production mutation occurred**

## Accepted evidence

```text
evidence root
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg

package root
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo

package log
/tmp/acp-stage-c21-final-20260806T052025+0100-package.txt

rehearsal log
/tmp/acp-stage-c21-final-20260806T052025+0100-rehearsal.txt

package fingerprint
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

evidence-manifest rows
139

evidence-manifest SHA-256
a630c6ff399c2c7081a4da8a74af79615d72497727ce302a6261ae0449bbedff

checks
32/32 PASS

final check
activation-interface
```

The retained report was generated at `2026-08-06T05:20:44+01:00` on `aarch64`.

## Result

The final corrected rehearsal completed one full production-shaped, pre-mutation transaction lifecycle:

```text
replay accepted current package and baseline
→ fresh read-only live baseline comparison
→ acquire canonical production lock
→ create one fresh authoritative transaction
→ capture filesystem, service, mixer, loopback and DAC state
→ stage all 28 current package files inside the transaction-private candidate root
→ validate package manifest, ALSA routes, sudoers, units/runtime and CamillaDSP privately
→ prove all later ordinary operations blocked
→ prove all four approval operations blocked and absent
→ retain candidate and transaction review evidence
→ typed abort before mutation
→ exact transaction removal
→ release canonical production lock
→ checksum complete evidence tree
```

All 32 ordered checks passed:

- root scope;
- exact package and baseline replay;
- fresh pre-lock live-baseline match;
- protocol and host-contract conformance;
- absent pre-existing production lock;
- production-lock acquisition;
- fresh authoritative transaction creation and identity binding;
- exact filesystem, service, mixer, loopback and DAC snapshots;
- five-domain snapshot integrity;
- 28-file candidate staging;
- path, mode, root ownership, single-link and digest binding;
- private ALSA, sudoers, unit/runtime and CamillaDSP validation;
- refusal of all 18 later ordinary operations;
- refusal and non-exposure of all four approval operations;
- no-mutation boundary;
- retained candidate evidence;
- typed v2 abort;
- exact transaction cleanup;
- production-lock release;
- unchanged package and baseline inputs;
- complete regular-object evidence tree and checksum manifest;
- absent activation interface.

## Final production state

Post-run inspection proved:

```text
PRODUCTION_LOCK=absent
TRANSACTION_ROOT=absent
LOCAL_CHECKOUT_PRESERVED=true
```

The Pi's existing stale checkout and modified `scripts/launch-dashboard-kiosk.sh` remained unchanged.

The fresh package contained 28 regular files and 27 fingerprinted payload files. Its deterministic fingerprint matched the accepted package exactly. The verified CamillaDSP identity remained:

```text
CamillaDSP 4.1.3 (05e9cfc)
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

## What was not done

This accepted result did not:

- stop, start, restart, enable or disable Plexamp, Shairport Sync or the dashboard;
- release or reopen the DAC;
- install, replace or remove any production file;
- reload systemd;
- load or unload a module;
- select an ALSA route;
- change a mixer value;
- create, publish, remove or promote an approval record;
- start CamillaDSP;
- open an audio PCM;
- play music, alarm or test audio;
- run `scripts/install-master-eq.sh`;
- activate Stage C;
- merge PR #2.

The report's final transaction disposition is:

```text
aborted-before-mutation and removed
```

## Corrections proved on the real target

Two fail-closed compatibility corrections preceded the accepted run:

1. the established appliance parent `/var/lib/a-clockwork-plex` is safely `root:root 0755`, not the historical inherited `0750` expectation;
2. the shared regular-tree checker requires the fixed Stage C21 evidence label.

The final `current_package_candidate_rehearsal_parent_contract_v8.py` entrypoint applies only those two reviewed compatibility bindings and delegates to the otherwise unchanged v7 rehearsal. It performs no permission repair and exposes no additional production operation.

## Acceptance

The Stage C21 current-package **stage/validate/abort preparation gate is now accepted on `plexamp-bedroom`**.

This proves that the exact current package can be bound to the accepted appliance state, staged and validated inside one authoritative transaction, and then aborted and removed without crossing the first mutation boundary.

It does not grant installation or activation authority.

## Next gate

The next engineering step may design the first mutation-bearing transaction slice, beginning with captured application-service quiescence and exact rollback ownership.

Before any such Pi execution, a new explicit approval must define the exact mutation scope. In particular, no approval presently exists for:

- stopping services;
- releasing the DAC;
- installing files;
- reloading systemd;
- changing routes or mixers;
- starting CamillaDSP;
- publishing activation approval;
- physical audio rehearsal;
- persistent activation.

PR #2 must remain Draft, open and unmerged until separately approved.
