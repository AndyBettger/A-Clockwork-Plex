# Stage C22 accepted-evidence identity freeze — design

Date: 2026-08-06  
Branch: `feature/alarm-engine`

## Purpose

The accepted Stage C22 service-quiescence rehearsal completed forty-one ordered
PASS checks and restored the exact accepted appliance state, but the outer
terminal command did not print the retained `evidence-manifest.tsv` SHA-256 or
row count.

A later current-package managed-file installation and exact-rollback rehearsal
must bind to the retained Stage C22 evidence itself, not to copied terminal text
or an unfrozen directory name. This stage therefore adds one deliberately
read-only identity inspector.

It does not advance the production mutation boundary.

## Fixed accepted evidence

The inspector accepts only:

```text
/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL
```

No command-line path, alternate evidence root, destination, unit, service,
endpoint, lock or transaction argument exists.

The evidence must remain a mode `0700` directory owned by the invoking normal
user directly beneath `/var/tmp`.

## Read-only validation contract

The inspector:

1. resolves the fixed accepted evidence root;
2. rejects any different path;
3. verifies directory type, owner and mode;
4. rejects symlinks and special objects throughout the tree;
5. replays every row of `evidence-manifest.tsv` and verifies every listed file,
   directory, mode and SHA-256 digest;
6. requires the exact forty-one Stage C22 checks in their original order;
7. requires all forty-one results to remain `PASS`;
8. requires the exact accepted package, baseline and Stage C21 input bindings;
9. requires the restored, non-committed, non-reusable Stage C22 transaction
   identity;
10. requires fourteen blocked ordinary operations and four blocked approval
    operations;
11. requires the restored-and-closed report markers and the absence of an
    installation or activation interface;
12. requires the retained candidate and transaction review copies;
13. prints the manifest SHA-256, total row count, manifest-entry count, result
    count, transaction identity, snapshot identity and production-lock lease.

## Explicit non-capabilities

The inspector contains no interface to:

- invoke `sudo`;
- inspect or acquire the production lock;
- create, alter or remove a transaction;
- stop, start or query a systemd service;
- inspect or open the DAC;
- change ALSA, mixer or route state;
- install, replace, rename, chmod, chown or remove a file;
- create an evidence directory or write an output file;
- start CamillaDSP or play audio;
- publish or remove approval;
- run the blocked bare `scripts/install-master-eq.sh`;
- activate, commit, uninstall or merge anything.

The shell wrapper accepts no arguments, refuses execution as root and directly
executes the read-only Python inspector without `sudo`.

## Expected output

A successful read prints:

```text
STAGE_C22_EVIDENCE_IDENTITY=PASS
root=...
manifest_sha256=<64 lowercase hexadecimal characters>
manifest_rows=<positive integer>
manifest_entries=<positive integer>
results_checks=41
results_pass=41
transaction=stage-c22-service-rehearsal-install-...
snapshot=stage-c22-service-rehearsal-snapshot-...
lease_id=...
```

No persistent output is produced. The terminal output will be reviewed and the
manifest identity will then be committed before Stage C23 can be completed or
submitted for physical approval.

## Next boundary

After the manifest identity is frozen, Stage C23 may adapt the already
physically exercised Stage C18 managed-file installation and exact-rollback
owner to the accepted twenty-eight-file current package.

That future rehearsal will require a separate design, automated gate and new
explicit approval. It must end after exact filesystem rollback and exact service
restoration, before systemd daemon reload, route selection, CamillaDSP startup,
audio testing, approval publication, transaction commit or activation.

PR #2 remains Draft, open and unmerged.
