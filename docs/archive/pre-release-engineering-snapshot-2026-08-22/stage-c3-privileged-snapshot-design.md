# Stage C3 read-only privileged activation-snapshot rehearsal

Status: design and implementation may proceed; no persistent installation or
activation path is approved.

## Purpose

Stage C2 proved the unprivileged transaction-review boundary. It verified eleven
managed file destinations as absent and correctly recorded
`/etc/sudoers.d/a-clockwork-plex-audio-route` as unresolved because the normal
project user cannot traverse `/etc/sudoers.d`.

Stage C3 rehearses only the fresh root-owned snapshot that an authorised
installer would have to take immediately before its first privileged write. It
resolves protected paths and produces an exact rollback ledger, but it performs
no install and changes no production state.

## Interface

Prepare-only is the default:

```bash
bash scripts/test-stage-c-privileged-snapshot.sh \
  --package-root /var/tmp/<validated-stage-c1-package> \
  --stage-c2-root /var/tmp/<validated-stage-c2-review>
```

The prepare step invokes no `sudo` and prints the exact read-only capture
command.

The capture requires a fresh empty review directory and this exact token:

```text
STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY
```

The capture action is deliberately named `--capture-read-only`; there is no
`--activate`, install, apply, route, rollback or uninstall action.

## Root scope

The privileged Python process must:

- run only through `sudo` from a non-root invoking user;
- receive the exact confirmation token itself, not rely only on the wrapper;
- accept only a validated Stage C1 package, validated Stage C2 review and fresh
  Stage C3 snapshot directory;
- require the Stage C3 directory to be a real non-symlinked directory directly
  beneath `/var/tmp`, named `a-clockwork-plex-stage-c3-snapshot.*`, owned by the
  invoking user, mode `0700` and empty;
- write only beneath that Stage C3 directory;
- return the completed evidence tree to the invoking user after capture.

The root process must not create a production lock, because Stage C3 is not an
activation transaction. A future installer must acquire the real route lock
before taking its own new authoritative snapshot.

## Replayed gates

Before capture, Stage C3 must replay rather than trust:

1. the Stage C1 manifest, candidate checksums, modes, directory contract and PASS
   results;
2. the Stage C2 eleven-check PASS result;
3. the Stage C2 package fingerprint against the supplied Stage C1 package;
4. the exact physically validated pre-Stage-C ALSA checksum, owner, mode and
   alarm-under-Master graph;
5. `snd_aloop` index 7, ID `ACP_Loopback`, two substreams and `pcm_notify=1`;
6. absence of an activation marker and any CamillaDSP process;
7. the three application services loaded, active and enabled;
8. the three proposed Stage C services not found.

## Filesystem snapshot

The privileged capture resolves every managed file destination with `lstat`.
For each path it records exactly one of:

- a copied regular file with checksum, mode and owner;
- a verified absence marker;
- a hard failure for a symlink or conflicting non-regular object.

For this first-install boundary, any existing managed file is a hard conflict,
even if its contents happen to match the candidate.

The current production ALSA file is copied separately and must retain this exact
checksum:

```text
08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9
```

Success requires all 12 managed file destinations—including the protected
sudoers path—to be verified absent and zero destination conflicts.

## Other captured state

The root-owned snapshot also records:

- all six service load/active/enabled states;
- all four live mixer-control percentages and raw `amixer sget` output;
- loaded `snd_aloop` parameters;
- physical DAC device existence and owner;
- physical DAC `hw_params`;
- the Stage C1 package fingerprint;
- a rollback ledger tied to the fresh Stage C3 snapshot;
- a checksum inventory of every generated evidence file.

## Safety boundary

Stage C3 may invoke `sudo` only for the single read-only snapshot engine. It
must not:

- write `/etc`, `/usr/local`, `/var/lib`, `/run`, systemd or any production path;
- copy a candidate file into production;
- create an activation marker;
- start, stop, restart, enable or disable a service;
- run `systemctl daemon-reload`;
- load or unload `snd_aloop`;
- open the DAC or a loopback PCM;
- run `aplay` or CamillaDSP;
- change a mixer value;
- alter file ownership or mode outside the Stage C3 evidence directory.

The only permitted writes are evidence files and ownership restoration inside
the fresh Stage C3 directory.

## Evidence outputs

A successful capture produces:

- `results.tsv`
- `filesystem-state.tsv`
- `rootfs/...` copied originals
- `absence-markers/...`
- `service-state.tsv`
- `mixer-state.tsv` and `mixer-raw/...`
- `module-dac-state.tsv`
- `dac-hw-params.txt`
- `package-fingerprint.tsv`
- `rollback-ledger.tsv`
- `evidence-manifest.tsv`
- `report.txt`

## Promotion boundary

A successful Stage C3 rehearsal proves only that the root-owned snapshot and
rollback ledger can be captured safely and completely. It does not authorise an
install and its evidence must not be reused as the future activation snapshot.
The activated installer must repeat the same capture under the real transaction
lock immediately before its first privileged write.

Persistent activation remains blocked until transactional mutation code,
automatic rollback, route authority, direct failback, EQ migration, health
reporting, finite route probes and explicit user approval are all complete.
