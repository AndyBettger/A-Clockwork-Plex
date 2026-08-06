# Stage C21 production prepare-only evidence renderer and wrapper design

## Purpose

Turn the already-proved frozen `ProductionPrepareOnlyReportV7` into a small, durable human-review bundle and expose one fixed, unprivileged command that may later be run on `plexamp-bedroom` only after explicit approval.

This boundary remains a **read-only baseline review tool**. It is not an installer, transaction owner, production-lock owner, approval writer, service controller, audio tool or activation command.

## Deliberately narrow composition

```text
validated candidate package fingerprint
→ ReadOnlyHostProductionAdapter
→ ProductionPrepareOnlyInspectorV7
→ frozen ProductionPrepareOnlyReportV7
→ deterministic evidence renderer
→ fresh /var/tmp review bundle
```

The new layer does not duplicate any host observation or approval classification. It consumes the exact frozen report produced by the existing inspector.

## Candidate package identity

The fixed wrapper accepts one required value:

```text
--package-fingerprint <lowercase SHA-256>
```

This must be the fingerprint printed by the existing, separately validated Stage C21 activation-package generator.

The wrapper accepts the digest rather than a candidate-package path because:

- the generator deliberately creates fresh random laboratory roots;
- a caller-selected package path would add a new filesystem authority boundary;
- a `latest` symlink or mutable pointer would be weaker than an explicit reviewed digest;
- the prepare-only baseline inspector needs only immutable review identity, not package contents;
- later transaction preparation must independently validate the real package contents again.

The digest is evidence only. It is not an approval, lease, activation token, transaction identity or installation permission.

## No privileged fallback

The first-install baseline wrapper is entirely unprivileged and contains **no sudo command**.

The packaged Stage C state directories are root-owned mode `0755`, so an absent approval path can be observed safely by the normal project user. A present root-owned mode-`0600` approval may be unreadable; that is correctly classified as `OBSERVATION_FAILURE` and blocks first-install readiness.

The wrapper must not automatically escalate merely to explain an already-blocking unexpected approval object. If reconciliation evidence is ever required, it must be designed as a separate, explicitly reviewed read-only privileged tool.

## Fixed review root

The renderer creates exactly one fresh directory with:

```text
parent: /var/tmp
prefix: a-clockwork-plex-stage-c21-production-baseline.
mode:   0700
owner:  current unprivileged user
```

The caller cannot select the parent, prefix, directory name or file names.

The root is opened and pinned by directory descriptor. It must remain a real directory, not a symlink, and its device/inode, mode and owner must remain stable while evidence is published.

## Fixed evidence files

The bundle contains exactly:

```text
report.json
report.txt
manifest.json
```

Each file is created relative to the pinned directory descriptor with:

```text
O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC
mode 0600
```

Existing files are never opened, replaced, truncated, renamed or removed.

`manifest.json` is written last and is the completion marker. It records:

- schema identity;
- exact report disposition;
- candidate package fingerprint;
- SHA-256 and byte length of `report.json`;
- SHA-256 and byte length of `report.txt`;
- `complete: true`;
- all production and activation authority flags as false.

Every file is fsynced and the review-directory descriptor is fsynced after publication. If publication fails, the renderer does not delete or disguise the incomplete directory; the absence of `manifest.json` means it is not a complete review bundle.

## Canonical JSON report

`report.json` uses a fixed schema and canonical UTF-8 JSON:

```text
sort_keys=true
separators=(",", ":")
ensure_ascii=false
one final newline
```

The serializer is explicit for the known frozen report types. It does not use arbitrary object reflection, pickle, generic command dispatch or caller-provided encoders.

It records:

- schema identity;
- overall adapter status, disposition and detail;
- candidate package fingerprint;
- each exact typed host result, detail, evidence and payload;
- approval observation state, metadata and decoded record identity where available;
- every frozen no-authority boolean.

No timestamp, hostname-derived output name, activation token, future approval secret, command suggestion or mutable transaction identity is added. Equal frozen reports therefore produce equal `report.json` and `report.txt` bytes.

## Human-readable report

`report.txt` is a deterministic plain-text projection of the same frozen evidence.

Its header states prominently:

```text
REVIEW ONLY — NO INSTALLATION OR ACTIVATION AUTHORITY
```

It includes the disposition, package fingerprint, all six host-result summaries, approval classification, service state, mixer values, loopback/DAC observations and the fixed false authority flags.

It must not print an activation command, sudo command, mutation command or confirmation token.

## Fixed wrapper

The public wrapper is:

```text
scripts/prepare-stage-c21-production-baseline.sh
```

It:

- accepts only `--package-fingerprint` and `--help`;
- refuses execution as root;
- disables Python bytecode writes;
- invokes one fixed Python module;
- invokes no sudo;
- accepts no output path, package path, binary path, command, unit, transaction, lease, approval bytes, activation token or confirmation token;
- prints only the completed bundle directory and final disposition;
- returns zero only for `BASELINE_READY`;
- returns non-zero for every blocking or unavailable disposition after preserving the evidence bundle.

## Mutation boundary

The only writes in this slice are new review evidence beneath the fresh user-owned `/var/tmp` root.

There is no capability to:

- write, replace or remove a production approval;
- create, acquire, alter or release the production lock;
- create an authoritative transaction;
- install or remove package files;
- start, stop, restart, enable or disable a service;
- load or unload a module;
- alter ALSA routing or mixer state;
- open a PCM or physical DAC;
- start CamillaDSP;
- invoke `scripts/install-master-eq.sh`;
- approve Pi execution;
- activate or retain the split-bus route.

## Result type

The renderer returns one frozen `ProductionPrepareOnlyEvidenceBundleV7` containing only:

- fixed bundle root;
- fixed report/manifest paths;
- exact report disposition;
- file digests and lengths;
- `complete = true`;
- all authority flags fixed false.

It grants no capability over the open directory descriptor after publication; all descriptors are closed before return.

## Test contract

The implementation must prove:

- equal frozen reports render byte-identical JSON and text;
- explicit serialization of every exact payload type;
- canonical JSON and one final newline;
- fixed root parent/prefix and mode `0700`;
- current-user ownership;
- fixed file names, mode `0600` and exclusive no-follow creation;
- exact stable directory identity checks;
- file and directory fsync;
- manifest publication last;
- no overwrite, rename, replace, unlink or cleanup authority;
- incomplete publication cannot produce a completion manifest;
- report failure dispositions are still preserved;
- zero exit only for exact `BASELINE_READY`;
- fixed wrapper argument vocabulary;
- root execution refused;
- no sudo path;
- no caller-selected filesystem path;
- no production mutation, service, process, route, mixer, audio or device boundary;
- no activation or confirmation token;
- no reference to the blocked master-EQ installer;
- v7 remains exactly forty-two operations;
- all production approval mutations remain blocked.

## Pi gate

Passing local and CI tests for this wrapper does **not** authorise running it on the Pi.

After this slice is complete, the next checkpoint is to present the exact read-only command and request explicit approval before any `plexamp-bedroom` execution.
