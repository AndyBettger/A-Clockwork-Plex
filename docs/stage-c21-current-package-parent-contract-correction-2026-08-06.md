# Stage C21 current-package parent-contract correction — 2026-08-06

## Outcome

**SAFE FAIL — the first target-side stage/validate/abort rehearsal proved its pre-mutation safety boundary, then refused transaction creation because the repository expected the established appliance parent `/var/lib/a-clockwork-plex` to be root:root `0750` while the real target is root:root `0755`.**

The target state is accepted. The repository expectation was wrong and is corrected without changing the Pi's permissions.

## Reviewed target run

Host:

```text
plexamp-bedroom
```

Reviewed source commit:

```text
2c541ba2183d60b103c168cd0e5f45d3d5777739
```

Fresh package:

```text
/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.sZoouu
```

Accepted package fingerprint:

```text
dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5
```

Partial review evidence:

```text
/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.2OJwt8
```

## Passed boundary before refusal

The target run passed:

1. verified CamillaDSP binary digest;
2. accepted baseline evidence hashes;
3. preservation of the stale local checkout and modified kiosk launcher;
4. exact reviewed source export;
5. complete 28-file package generation and validation;
6. accepted 27-payload package fingerprint;
7. fresh read-only live-baseline comparison;
8. protocol conformance with no approval-capable v7 interface;
9. fixed host-contract observation;
10. pre-lock proof that the canonical lock was absent;
11. exact production-lock acquisition.

Transaction creation then failed closed with:

```text
existing current-package transaction parent differs from root:root 750:
/var/lib/a-clockwork-plex
```

No authoritative transaction was created.

## Post-failure safety result

The adapter's context cleanup removed the exact acquired lock. The post-run inspection proved:

```text
production lock
absent

transaction root
absent
```

The run did not:

- create an authoritative transaction;
- capture or alter an application service;
- release or open the DAC;
- stage a candidate under a transaction;
- install a file;
- reload systemd;
- select an ALSA route;
- change a mixer value;
- publish, remove or promote an approval;
- start CamillaDSP;
- play a music or alarm probe;
- run `scripts/install-master-eq.sh`;
- alter the existing checkout;
- merge PR #2.

The child-shell wrapper returned status `1` while leaving the interactive SSH shell open.

## Target parent evidence

A separate read-only inspection proved:

```text
/var/lib/a-clockwork-plex
owner root:root
mode 0755
```

Every ancestor from `/` through `/var/lib` is also root:root `0755`. This is an established, internally consistent appliance parent, not unsafe drift.

The current package generator also uses a `0755` directory convention for its package tree. There is no reason to mutate the established appliance parent to satisfy the historical Stage C15 `0750` assumption.

## Root cause

The Stage C21 adapter intentionally reused the historical Stage C15/C16 transaction mechanics. Its corrected package-specific contract had already changed:

```text
/var/lib/a-clockwork-plex/split-bus
0750 → 0755
```

but retained an equality assertion that froze the outer parent to the historical Stage C15 mode:

```text
/var/lib/a-clockwork-plex
0750
```

That mode had not been measured in the original read-only baseline because the `split-bus` child was absent. The first real transaction-shaped rehearsal exposed the mismatch before transaction creation.

## Correction

The target-proved current contract is:

```text
/var/lib/a-clockwork-plex                         root:root 0755
/var/lib/a-clockwork-plex/split-bus               root:root 0755
/var/lib/a-clockwork-plex/split-bus/transactions  root:root 0700
```

Implementation:

```text
scripts/stage_c_transaction/current_package_candidate_rehearsal_parent_contract_v8.py
commit 3736991c483ed01e8df362244cfdac33e6e6a026
```

The compatibility entrypoint:

- verifies the exact known v7 parent contract before applying anything;
- verifies that all inherited transaction paths remain exact;
- changes only the outer expected mode from `0750` to `0755`;
- delegates to the unchanged v7 rehearsal;
- performs no chmod, chown or appliance repair;
- fails closed if any other contract detail changes.

Wrapper routing:

```text
scripts/test-stage-c21-current-package-transaction-preparation.sh
commit 5c472ebb8025556ef9caf493e767abb6069e23ba
```

Focused tests:

```text
tests/test_stage_c21_target_parent_contract_v8.py
commit 3459575fa5212f125c6a73320777d66685a509a1
```

The tests prove:

- the exact `0755 / 0755 / 0700` target contract;
- only the outer mode differs from v7;
- the correction applies only to the exact reviewed v7 contract;
- unreviewed contract drift is refused;
- the wrapper invokes only the corrected entrypoint;
- the correction contains no permission repair or appliance mutation command;
- Python syntax remains valid.

## Approval state

The previous explicit Pi approval was consumed by the safe failed rehearsal. Repository correction and CI require no Pi authority.

A new explicit approval is required before rerunning the guarded stage/validate/abort rehearsal on `plexamp-bedroom` from the corrected branch head.

That rerun remains bounded to:

```text
replay package and accepted baseline
→ fresh read-only live comparison
→ acquire canonical lock
→ create one disposable authoritative transaction
→ capture five snapshot domains
→ stage and validate the package inside the transaction
→ retain review evidence
→ exact abort
→ release lock
```

It still does not authorise installation, service or audio mutation, approval operations, CamillaDSP startup, activation or PR merge.

## Roadmap

### Done

- first target-side rehearsal attempted under explicit approval;
- safe failure before transaction creation;
- exact lock cleanup proved;
- real parent ownership and mode measured;
- repository root cause identified;
- target-proved compatibility correction implemented;
- focused regression tests added.

### Current

GitHub Actions validation of the corrected entrypoint and wrapper.

### Next

After CI succeeds, request explicit approval for one corrected target-side stage/validate/abort rehearsal.

### Risks and gates

- the corrected rehearsal has not yet run on the Pi;
- the previous partial evidence root is incomplete by design and must not be treated as a successful rehearsal;
- no permission repair is authorised or required;
- no production approval writer is authorised;
- no activation entrypoint is authorised;
- `scripts/install-master-eq.sh` remains blocked;
- PR #2 must remain Draft, open and unmerged.
