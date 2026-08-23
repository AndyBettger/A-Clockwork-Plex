# Stage C21 production prepare-only evidence renderer and wrapper result — 2026-08-06

## Outcome

**PASS — the repository now has a fixed, unprivileged Stage C21 production-baseline wrapper that performs the already-proved read-only observations and publishes a deterministic human-review bundle without gaining any installation, activation, lock, approval, service, route, mixer, audio or device authority.**

This slice did not run on either Pi and did not access or alter the production appliance.

## Design

```text
7d8e68af7c8ec51526309ae64120b6992a5fc707
docs: design Stage C21 prepare-only evidence wrapper
```

The reviewed composition is:

```text
reviewed candidate package fingerprint
→ ReadOnlyHostProductionAdapter
→ ProductionPrepareOnlyInspectorV7
→ frozen ProductionPrepareOnlyReportV7
→ deterministic evidence renderer
→ fresh /var/tmp review bundle
```

The renderer consumes the exact frozen report. It does not repeat, reinterpret or broaden the host observations.

## Package-fingerprint boundary

The public wrapper accepts exactly one required value:

```text
--package-fingerprint <lowercase SHA-256>
```

The value is copied from the separately validated Stage C21 activation-package generator.

It is deliberately only a review identity. It is not:

- proof that package contents are currently present;
- package-content validation;
- an activation approval;
- a lock lease;
- a transaction identity;
- an activation or confirmation token;
- permission to install or run anything.

A later production transaction must independently open, validate and bind the real package contents again. The baseline wrapper accepts a digest rather than a caller-selected package path, mutable `latest` pointer or second package-builder implementation.

## Implementation

```text
scripts/stage_c_transaction/production_prepare_only_evidence_v7.py

2a3ae5643558f3ce4dc481b29641442df47822bc
feat: add Stage C21 prepare-only evidence renderer
```

The renderer explicitly serialises only the known frozen types:

- package fingerprint;
- host-contract result and payload;
- production-lock result and payload;
- service-state result and payload;
- mixer-state result and payload;
- loopback result and payload;
- DAC result, contract and owner evidence;
- approval observation;
- every fixed no-authority flag.

It uses no arbitrary object reflection, pickle, generic encoder, command dispatch or caller-provided path.

## Fixed wrapper

```text
scripts/prepare-stage-c21-production-baseline.sh

348b9654331150dcf8c666df805533bd170464c2
feat: add fixed Stage C21 baseline wrapper
```

The wrapper:

- accepts only `--package-fingerprint` and `--help`;
- requires one lowercase 64-character SHA-256;
- refuses execution as root;
- disables Python bytecode writes;
- invokes one fixed Python module;
- invokes no sudo;
- accepts no output path, package path, binary path, command, service unit, transaction, lease, approval bytes, activation token or confirmation token;
- exits zero only for the exact `BASELINE_READY` disposition;
- exits non-zero for every existing lock, existing or unreadable approval, failed observation or host mismatch after preserving its evidence.

## No privileged fallback

The first-install baseline path needs no sudo.

The packaged state-directory contract is root-owned mode `0755`, so an absent approval path can be observed by the normal project user. If an unexpected root-owned mode-`0600` approval exists and cannot be read, that becomes the typed `OBSERVATION_FAILURE` disposition and blocks first-install readiness.

The wrapper does not escalate merely to investigate a state that is already unsafe for first install. Any future reconciliation inspector would require a separate design and review.

## Fixed evidence root

The only writes are new review evidence beneath:

```text
/var/tmp/a-clockwork-plex-stage-c21-production-baseline.*
```

The root is:

- created fresh by `mkdtemp`;
- current-user owned;
- mode `0700`;
- opened with `O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`;
- pinned by device and inode;
- rechecked for stable identity, ownership and mode throughout publication.

The caller cannot choose the parent, prefix or root name.

## Fixed evidence files

A complete bundle contains exactly:

```text
report.json
report.txt
manifest.json
```

Each is current-user owned mode `0600` and created relative to the pinned directory descriptor with:

```text
O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC
```

No existing file is opened, replaced, truncated, renamed or removed.

Each file is fsynced. The directory is fsynced after publication. `manifest.json` is published last and is the sole completion marker.

If publication fails, the incomplete directory is retained for diagnosis. The renderer has no unlink, rename, replace or cleanup authority, and the absent completion manifest prevents an incomplete bundle from being mistaken for a completed one.

## Canonical JSON

`report.json` uses a fixed schema and canonical UTF-8 JSON:

```text
sort_keys=true
separators=(",", ":")
ensure_ascii=false
one final newline
```

It contains no timestamp, random report identity, activation command, sudo command, confirmation token, future approval secret or mutable transaction identity. Equal frozen reports therefore render byte-identical JSON.

## Human-readable report

`report.txt` is a deterministic projection of the same evidence and begins with:

```text
REVIEW ONLY — NO INSTALLATION OR ACTIVATION AUTHORITY
```

It includes the disposition, candidate digest, all six typed host-result summaries, service state, mixer values, loopback and DAC evidence, approval classification and every no-authority flag.

It contains no install, activation, sudo, service-management or audio command.

## Completion manifest

`manifest.json` records:

- fixed schema identity;
- `complete: true`;
- exact report disposition;
- candidate package digest;
- SHA-256 and byte length of `report.json`;
- SHA-256 and byte length of `report.txt`;
- all production, activation, Pi-execution, lock and transaction flags as false.

It is written only after both report files have been durably published.

## Frozen result

A successful publication returns one frozen `ProductionPrepareOnlyEvidenceBundleV7` containing only:

- fixed bundle root;
- fixed evidence paths;
- exact disposition;
- candidate package fingerprint;
- file digests and byte lengths;
- `complete = true`;
- all authority flags fixed false.

All file and directory descriptors are closed before return.

## Tests

```text
tests/test_stage_c_production_prepare_only_evidence_v7.py

031f43bfd5c1790567a37897618431ae3db42945
test: cover Stage C21 prepare-only evidence wrapper
```

The test suite proves:

- deterministic byte-identical JSON and text for equal reports;
- explicit serialisation of every exact payload type;
- canonical JSON and one final newline;
- fixed review parent and prefix;
- root mode `0700` and current-user ownership;
- fixed filenames, mode `0600` and current-user ownership;
- exclusive no-follow creation;
- stable root and evidence inode identity;
- file and directory fsync;
- manifest publication last;
- no overwrite of existing evidence;
- no rename, replace, unlink or automatic cleanup authority;
- interrupted publication retains an incomplete root without a manifest;
- blocking reports remain preserved without becoming ready;
- zero exit only for exact `BASELINE_READY`;
- root execution is refused;
- invalid digest and unknown arguments are refused;
- no sudo, output-path, package-path or binary-path interface;
- no activation or confirmation token;
- no production lock, transaction, approval, service, route, mixer, PCM, DAC or CamillaDSP mutation boundary;
- no reference to `scripts/install-master-eq.sh`;
- v7 remains exactly forty-two operations;
- all four production approval operations remain blocked.

## Validation

```text
GitHub Actions run 31064993161
job 92500756603

Ran 1142 tests in 7.445s
OK
```

Compilation, JavaScript and page wiring, shell syntax and every inherited application, transaction, runtime, filesystem, sandbox, rehearsal and safety suite passed.

## Safety state

Unchanged:

- no Pi command was run;
- no production path was written;
- no production lock was created, acquired, altered or released;
- no production transaction was created;
- no activation approval was created, changed, promoted or removed;
- no package was installed or removed;
- no service or process was managed;
- no ALSA route or configuration was changed;
- no mixer control was changed;
- no PCM or physical DAC was opened;
- CamillaDSP was not started;
- no activation command exists in this slice;
- all four production approval mutations remain blocked;
- `scripts/install-master-eq.sh` remains blocked;
- the accepted direct shared ALSA route remains authoritative;
- PR #2 must remain Draft, open and unmerged.

## Roadmap

### Done

- disposable Stage C21 approval lifecycle proofs;
- thin disposable lifecycle facade;
- production baseline inspector;
- deterministic canonical evidence renderer;
- fixed unprivileged wrapper;
- exclusive durable review-bundle publication;
- fail-closed exit semantics;
- 1,142-test validation.

### Current

The software has reached the **explicit Pi baseline-inspection gate**.

No additional abstraction is required before the first read-only appliance observation. The exact package-generation and baseline-inspection commands must now be reviewed together before execution.

### Next

After explicit approval:

1. update the reviewed branch on `plexamp-bedroom`;
2. generate the fresh validated Stage C21 package and record its printed fingerprint;
3. run the fixed unprivileged production-baseline wrapper with that fingerprint;
4. return the generated `report.txt`, `report.json` and `manifest.json` for review;
5. make no installation or activation change.

Only after the baseline evidence is accepted should production transaction preparation continue.

### Risks and gates

- the wrapper has not been run on the Pi;
- the candidate package must be freshly generated and validated on the target appliance;
- its digest remains evidence, not authority;
- any lock, approval object, inaccessible approval or failed observation blocks readiness;
- no production lifecycle facade or executor integration is authorised;
- no activation command exists;
- all production approval operations remain blocked;
- explicit approval is required before any `plexamp-bedroom` command;
- PR #2 must remain Draft, open and unmerged.
