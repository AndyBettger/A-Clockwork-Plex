# Stage C21 current-package pre-mutation transaction preparation — result

Date: 2026-08-06  
Branch: `feature/alarm-engine`  
Result: **PASS — repository implementation and automated validation complete; Pi execution remains separately gated**

## Outcome

The accepted `plexamp-bedroom` baseline and current Stage C21 package v2 are now bound to one guarded, current-package pre-mutation transaction rehearsal.

The implementation reuses the physically proved Stage C16 production-lock, authoritative-transaction, five-domain snapshot and exact-abort mechanics. It does not create another production authority stack.

The new rehearsal is intentionally bounded to:

```text
replay accepted package and baseline
→ fresh read-only live baseline comparison
→ acquire canonical production lock
→ create one fresh authoritative transaction
→ capture all five authoritative snapshot domains
→ stage all 28 current package files inside the transaction
→ validate ALSA, sudoers, units/runtime and CamillaDSP privately
→ retain non-authoritative review evidence
→ exact typed abort
→ remove the transaction
→ release the production lock
```

It stops before:

```text
stop-captured-application-services
```

No Pi execution occurred during this repository slice.

## Accepted target identities

### Reviewed source baseline

```text
accepted source commit
273290f5e77ae98d24cb5af368ab90c76744be60
```

### Current package v2

```text
package fingerprint
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5

package phase
stage-c21-activation-capable-review-v2

regular package files
28

fingerprinted payload files
27

CamillaDSP SHA-256
e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

### Accepted baseline evidence

```text
baseline root
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac

report.txt
350ae99ee63911cb524f7220e4629e5da669f3c79f8e409d2f9fdf4652c16a85

report.json
3c6dcd3c17a3ce363ddf3f5bdd9d93c8891a2a006c0c154905a3a809b79348e0

manifest.json
4995bdf85cb06995a9b26c164fdc28991d755631e9c4dbe527eddc005253c1dc
```

The target baseline remains:

- production lock absent;
- activation approval absent;
- Plexamp, Shairport Sync and A-Clockwork-Plex active and enabled;
- all three Stage C services absent;
- mixer values `94 / 100 / 100 / 100` for `Plexamp Output`, `AirPlay Output`, `Music Master` and `Maximum Alarm Volume`;
- loaded `snd_aloop` card 7 / `ACP_Loopback`, two substreams, `pcm_notify=1`;
- S16_LE, two-channel, 44100 Hz, period-1024, buffer-8192 DAC contract;
- at least one `andy` / `node` / read-write DAC owner;
- all authority flags false.

The DAC owner PID is evidence rather than a persistent identity. The live rehearsal accepts PID changes only when the complete Plexamp owner contract remains exact.

## Design records

### Baseline acceptance

```text
docs/stage-c21-production-baseline-accepted-2026-08-06.md
commit e2976c640ac50e668ea35ca12202b6e748fb7fc0
```

### Current-package preparation design

```text
docs/stage-c21-current-package-transaction-preparation-design.md
commit ab0b462623f133c26eabba87ae9de3fa807848c5
```

### Design correction

```text
docs/stage-c21-current-package-transaction-preparation-design-correction.md
commit 0453623a6888631e2f92efe1dd5fdc3fa3d3a42a
```

The correction froze:

```text
/var/lib/a-clockwork-plex                         root:root 0750
/var/lib/a-clockwork-plex/split-bus               root:root 0755
/var/lib/a-clockwork-plex/split-bus/transactions  root:root 0700
```

A pre-existing incompatible parent is a hard pre-mutation failure. The rehearsal does not chmod an existing parent as a repair action.

## Implementation

### Fixed package and baseline contract

```text
scripts/stage_c_transaction/current_package_contract_v7.py
commit cee045087050b4132dbeb196a73996025cce939f
```

It validates:

- the exact current package manifest, report, results and package contract;
- all 28 regular files and 27 canonical payload rows;
- the exact accepted package fingerprint;
- the exact accepted baseline report and manifest hashes;
- the fixed service, mixer, loopback and DAC baseline;
- PID-flexible but owner-contract-strict DAC state;
- fresh prepare-only reports and authoritative snapshots against the accepted target state.

It has no mutation capability.

### Current package transaction adapter

```text
scripts/stage_c_transaction/current_package_candidate_rehearsal_adapter_v7.py
initial commit 6107379861e39920fb30136af96b5df6c02c9456
staged-root fix 8c997c04bb5ea63d36e2bab6a245242a8d43e5f6
```

The adapter subclasses the historical Stage C16 candidate-validation owner. It reuses inherited:

- canonical production-lock ownership;
- fixed read-only host observations;
- authoritative transaction identity;
- five-domain snapshot capture;
- transaction-confined staging mechanics;
- exact pre-mutation abort;
- lock release ordering.

It overrides only the current package-bound contract:

- corrected parent modes;
- current transaction and snapshot identities;
- 28-file managed-destination boundary;
- 28-file transaction-private staging;
- current package-contract fingerprint replay;
- current readiness units, launcher and 15 runtime modules;
- exact two-action read-only sudoers contract.

The staged package-contract replay is rooted at the transaction-private `candidate-rootfs`; it cannot escape to the transaction or production root.

### Guarded rehearsal

```text
scripts/stage_c_transaction/current_package_candidate_rehearsal_v7.py
commit d3e2dbb5f636d0fb85723c0bd66f71f19c3e719f
```

The exact confirmation token is:

```text
STAGE-C21-CURRENT-PACKAGE-STAGE-VALIDATE-ABORT
```

The rehearsal:

1. validates direct user-owned fixed-prefix `/var/tmp` package, baseline and evidence roots;
2. replays the exact accepted package and baseline before privilege is used;
3. performs a fresh fixed read-only live baseline observation before lock acquisition;
4. proves the adapter conforms to `ProductionAdapterV2` and does not conform to approval-capable `ProductionAdapterV7`;
5. acquires the canonical lock;
6. creates one fresh transaction;
7. captures filesystem, service, mixer, loopback and DAC state;
8. compares the authoritative snapshot to the accepted target state;
9. stages and validates the complete current package beneath the transaction only;
10. proves all later ordinary operations blocked;
11. proves all four production approval operations blocked and absent from the rehearsal adapter;
12. retains typed and human-review evidence;
13. performs the typed v2 abort;
14. verifies exact transaction cleanup;
15. releases the production lock only after abort;
16. verifies package and baseline inputs remained unchanged.

### Fixed wrapper

```text
scripts/test-stage-c21-current-package-transaction-preparation.sh
commit afd4fdf05abcf57e647e4f2c6d27950afb96d68e
```

The default invocation is inert prepare-only mode:

- no sudo;
- no host observation;
- no evidence root;
- no production lock;
- no transaction;
- no approval object.

The guarded mode accepts only:

```text
--rehearse-current-package
--confirm <exact fixed token>
--package-root <direct fixed-prefix /var/tmp package>
--baseline-root <direct fixed-prefix /var/tmp baseline>
--evidence-root <fresh direct fixed-prefix /var/tmp evidence root>
```

It invokes one fixed `sudo env ... python3 -m ...` command and exposes no install, activation, service, route, mixer, approval, transaction-ID, lock-path or arbitrary-command selector.

## Automated validation

Test file:

```text
tests/test_stage_c21_current_package_preparation_v7.py
commit ec506b12b7711f5fe67b68265a81fbc304d6661a
```

The 20 new tests cover:

- exact package phase, counts and accepted fingerprint;
- exact accepted evidence hashes;
- exact target service, mixer, loopback and DAC state;
- PID-flexible Plexamp DAC ownership;
- rejection of owner or mixer drift;
- prepare-only report package binding;
- corrected parent modes;
- staged-root binding regression;
- current runtime actions replacing obsolete Stage C1 actions;
- exact runtime and sudoers boundary;
- all four approval operations blocked;
- exact abort-before-lock-release result ordering;
- fixed roots and confirmation token;
- inert wrapper default;
- absence of install, activation and authority selectors;
- absence of any `scripts/install-master-eq.sh` reference;
- Python parsing;
- absence of direct service, mixer, module or PCM mutation commands.

GitHub Actions validation:

```text
run
31067768817

job
92509049352

result
success

suite
Ran 1162 tests in 6.909s
OK
```

The workflow also passed Python compilation and shell syntax validation.

## Authority and safety result

The repository slice did not:

- run another command on `plexamp-bedroom`;
- create or acquire a production lock;
- create a production transaction;
- write a production path;
- install or remove a package;
- stop, start, restart, enable, disable or reload a service;
- change ALSA configuration or route selection;
- change a mixer value;
- load or unload a module;
- open a PCM or DAC;
- start CamillaDSP;
- create, replace, promote or remove an approval record;
- run `scripts/install-master-eq.sh`;
- merge PR #2.

The rehearsal grants no installation or activation authority. All four production approval operations remain blocked.

## Next explicit approval gate

A separate explicit approval is required before the guarded rehearsal is run on `plexamp-bedroom`.

That approval will cover only:

```text
generate one fresh direct validated current package if required
→ replay accepted baseline
→ acquire canonical production lock
→ create one fresh authoritative transaction
→ capture the five authoritative snapshot domains
→ stage and validate the 28-file package inside the transaction
→ retain review evidence
→ exact abort
→ release lock
```

It will not cover:

- stopping an application service;
- releasing or reopening the DAC;
- installation or systemd reload;
- ALSA route selection or mixer change;
- approval publication, removal or promotion;
- CamillaDSP startup;
- music, alarm or physical EQ audio probes;
- commit or activation;
- PR merge.

## Roadmap

### Done

- target-side read-only baseline inspection and acceptance;
- exact current package and baseline replay contracts;
- corrected Stage C21 production parent contract;
- current-package authoritative transaction adapter;
- guarded pre-mutation stage/validate/abort rehearsal;
- fixed inert-by-default wrapper;
- 20 focused tests;
- full 1,162-test GitHub Actions success.

### Current

Explicit approval gate for the first current-package production-shaped pre-mutation rehearsal on `plexamp-bedroom`.

### Next

After explicit approval:

1. update/export the reviewed branch without altering the Pi's local kiosk modification;
2. generate one fresh direct fixed-prefix package root;
3. verify its accepted fingerprint;
4. run the guarded stage/validate/abort rehearsal;
5. return all evidence for human review;
6. make no installation, activation or audio change.

Only after that evidence is accepted should the first mutation-bearing transaction prefix be designed or authorised.

### Risks and gates

- the guarded rehearsal has not yet run on the Pi;
- the accepted package is currently nested beneath an earlier disposable inspection workspace, so a fresh direct fixed-prefix package root is required;
- a stale or incompatible production parent fails closed rather than being repaired;
- any target drift in services, mixer, loopback, DAC owner contract, lock or approval blocks before mutation;
- no production approval writer is authorised;
- no production activation entrypoint is authorised;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 must remain Draft, open and unmerged.
