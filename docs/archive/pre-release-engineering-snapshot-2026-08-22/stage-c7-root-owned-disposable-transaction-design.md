# Stage C7 root-owned disposable transaction design

## Purpose

Stage C7 bridges the remaining filesystem-mechanics gap between the unprivileged Stage C4 sandbox and the read-only real-host Stage C6 lock/snapshot rehearsal.

It exercises root-owned installation, ownership and mode verification, failure injection, exact rollback and explicit uninstall inside a disposable synthetic system root beneath `/var/tmp`.

Stage C7 is **not** a production installer and has no production activation interface.

## Inputs

The rehearsal requires:

- the immutable Stage C1 candidate package;
- the complete Stage C6 locked-snapshot evidence;
- a fresh user-created mode-`0700` directory directly beneath `/var/tmp` with prefix `a-clockwork-plex-stage-c7-root-transaction.`;
- the exact review token `STAGE-C7-ROOT-OWNED-DISPOSABLE-TRANSACTION`.

The Stage C6 snapshot is used only as a read-only source of the accepted pre-install filesystem shape. It remains non-authoritative and is never reused as a production activation backup.

## Root boundary

The outer wrapper:

- defaults to prepare-only;
- rejects being invoked as root;
- has exactly one constrained `sudo` command;
- invokes only `python3 -B -m stage_c_transaction.root_owned_transaction`;
- passes the Stage C1 path, Stage C6 path, fresh rehearsal root and exact token;
- exposes no install, activate, keep, failback, rollback or uninstall production mode.

The root engine:

- requires effective UID zero;
- validates the invoking user from `SUDO_USER`;
- requires a fresh, empty, user-owned, non-symlink mode-`0700` rehearsal root directly beneath `/var/tmp`;
- writes only inside that rehearsal root;
- returns the complete evidence tree to the invoking user after completion or failure.

## Destination confinement

Every package destination remains an absolute production-style path in the Stage C1 manifest, but Stage C7 maps it mechanically to:

`<rehearsal-root>/scenarios/<scenario>/system-root/<destination-without-leading-slash>`

The mapper rejects:

- `/`;
- relative destinations;
- `..` components;
- symlinked ancestors;
- any resolved path outside the scenario system root.

No production destination is opened for writing.

## Existing-directory rule

Stage C7 permanently corrects the permission wobble discovered by Stage C4.

For a managed directory that already exists in the captured baseline:

- its existing mode and ownership are authoritative;
- installation must not chmod or chown it to the package candidate mode;
- verification must prove it remained unchanged throughout the installed state;
- rollback still restores the captured mode and ownership defensively.

For a managed directory absent in the captured baseline:

- installation may create it with the manifest mode and `root:root` ownership;
- rollback removes it only after managed files are removed and only when empty.

In particular, synthetic `/etc/sudoers.d` must remain `root:root` mode `0750` during installation and after rollback.

## Atomic file installation

Each candidate file is installed using one root-owned atomic primitive:

1. verify the source is a regular non-symlink file;
2. hash the source before copying;
3. create a unique temporary file in the mapped destination directory with exclusive creation;
4. copy bytes and `fsync` the temporary file;
5. set the exact candidate mode and `root:root` ownership;
6. verify the temporary checksum;
7. hash the source again and reject source drift;
8. atomically replace the mapped destination;
9. `fsync` the parent directory;
10. verify final checksum, mode and ownership.

All twelve candidate files begin absent in every scenario.

## Synthetic active route

The accepted pre-Stage-C ALSA file from Stage C6 is copied into each scenario baseline.

Route selection is rehearsed only inside the disposable system root by atomically copying the installed split-bus route candidate onto the mapped active ALSA destination.

No ALSA parser, PCM, device or service is opened.

## Transaction lock

Each scenario acquires one exclusive non-blocking `flock` inside its own control directory before creating the transaction identity or mutating the synthetic system root.

A second independent descriptor must fail closed.

The lock is released only after installed-state verification and exact rollback verification are complete.

The real production path `/run/lock/a-clockwork-plex-audio-route.lock` is never opened or created.

## Scenarios

Stage C7 runs four root-owned scenarios:

1. successful install, installed-state verification and explicit uninstall;
2. injected failure after all package files are installed;
3. injected failure after the synthetic split-bus route is selected;
4. injected failure after the synthetic transaction-state record is written.

The successful path and all three failure paths invoke the same rollback implementation.

## Exact rollback

Rollback must:

1. remove all newly installed candidate files;
2. atomically restore the exact captured active ALSA file;
3. remove the synthetic transaction-state record;
4. remove only managed directories that were absent before installation and are empty after file rollback;
5. restore captured mode and ownership for every pre-existing managed directory;
6. verify a complete baseline fingerprint including type, mode, UID, GID and file checksum;
7. report zero mismatches.

## Evidence

Stage C7 writes:

- `results.tsv`;
- `scenario-state.tsv`;
- `file-plan.tsv`;
- per-scenario ordered journals;
- per-scenario baseline, installed and post-rollback fingerprints;
- per-scenario lock state and transaction identity;
- `report.txt`;
- `evidence-manifest.tsv`.

Expected top-level checks:

1. `root-scope`
2. `input-replay`
3. `disposable-mapping`
4. `first-install-boundary`
5. `existing-directory-preservation`
6. `atomic-install`
7. `synthetic-route-selection`
8. `failure-injection`
9. `shared-rollback`
10. `exact-state-verification`
11. `production-boundary`
12. `activation-interface`

## Explicitly not proved

Stage C7 does not prove:

- the real production lock path;
- mutation of `/etc`, `/usr/local`, `/var/lib` or `/run`;
- systemd daemon reload or service ordering;
- CamillaDSP startup or health;
- ALSA parsing or PCM availability;
- DAC ownership transfer;
- music/alarm lane probes;
- runtime direct alarm-bypass failback;
- EQ helper migration;
- reboot behaviour.

## Promotion boundary

Stage C7 may pass only when all four scenarios finish with zero rollback mismatches, existing synthetic system directories remain unchanged during installation, all inputs remain immutable, the evidence tree contains no symlink or special object, and no production path or command adapter exists.

Passing Stage C7 still does not authorise persistent installation or activation.
