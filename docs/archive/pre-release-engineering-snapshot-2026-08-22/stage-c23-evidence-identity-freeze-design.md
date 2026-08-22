# Stage C23 evidence identity-freeze design

## Purpose

Stage C24 will depend on the physically accepted Stage C23 managed-file install
and exact-rollback evidence. The Stage C23 run printed and accepted the exact
evidence-manifest SHA-256 and its 144-line shape, but the outer command did not
print the parsed manifest entry count. Stage C24 must not infer that missing
value.

This repository-only helper prepares one normal-user, read-only inspection of
the retained Stage C23 evidence tree. It validates the already frozen evidence
identity and prints the parsed entry count for a later immutable binding.

## Fixed accepted evidence

```text
/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG
```

```text
Evidence-manifest SHA-256:
e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a

Evidence-manifest rows:
144

Results:
47/47 PASS
```

## Inspector

```text
scripts/inspect-stage-c23-evidence-identity.sh
scripts/stage_c_transaction/stage_c23_evidence_identity.py
```

The wrapper:

- accepts no arguments;
- refuses root execution;
- invokes no `sudo` command;
- reads only the exact accepted Stage C23 root;
- uses `PYTHONDONTWRITEBYTECODE=1` and `python3 -B`;
- exposes no lock, transaction, service, systemd, route, mixer, DAC, audio,
  approval, cleanup or activation operation.

## Validation contract

The inspector requires:

- the exact retained evidence path directly beneath `/var/tmp`;
- invoking-user ownership and mode `0700`;
- one regular evidence tree with no symlink or special object;
- a valid evidence manifest whose SHA-256 and row count match the accepted run;
- the exact 47 ordered Stage C23 checks, all `PASS`;
- exact package, baseline, Stage C21 and Stage C22 input bindings;
- the accepted 28-file and 27-payload counts;
- an adapter-generated Stage C23 transaction, snapshot and canonical-lock lease;
- mutation, managed-file installation, filesystem restoration and service
  restoration recorded as true;
- systemd reload, route selection and commit recorded as false;
- activation and rollback reuse recorded as false;
- exactly 11 ordinary blocked operations and four blocked approval operations;
- the accepted closed transaction-state and persistent-activation boundary in
  the report;
- retained candidate-review and transaction-rehearsal copies.

On success it prints the exact root, manifest SHA-256, manifest rows, parsed
manifest entries, 47/47 result count, transaction, snapshot and lease identity.
It writes nothing.

## Relationship to Stage C24

A successful identity freeze will not authorise Stage C24. It will only supply
the missing immutable manifest-shape value.

Stage C24 is expected to require a separate explicit approval because its
physical rehearsal will briefly stop Plexamp, Shairport Sync and the dashboard,
install all 28 managed files, execute one `systemctl daemon-reload` while the
candidate units exist, remove the exact installed inodes, execute a final
`daemon-reload` after rollback, and restore the accepted appliance state.
Route selection, managed Stage C service startup, CamillaDSP, mixer mutation,
audio probes, approvals, commit, activation and merge must remain blocked.
