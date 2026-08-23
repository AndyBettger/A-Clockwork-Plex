# Stage C2 prepare-only installation transaction review

Status: implementation prepared for Pi-side review; no persistent installation
or activation path exists.

## Purpose

Stage C1 proves that the route package itself is deterministic and valid. Stage
C2 independently replays that package against the current Pi and prepares the
evidence an activated transaction would need:

- destination conflict checks;
- filesystem content, absence and protected-path markers;
- service active/enabled/load states;
- live mixer readback;
- `snd_aloop` parameters;
- DAC owner and hardware parameters;
- exact rollback obligations;
- reviewed install and rollback ordering;
- explicit blockers that still prevent activation.

Stage C2 does not install the package and does not turn the inert Stage C1 route
helper into a writer.

## Interface

```bash
bash scripts/prepare-stage-c-install-transaction.sh \
  --package-root /var/tmp/<validated-stage-c1-lab> \
  --transaction-root /var/tmp/<new-empty-stage-c2-review>
```

There is deliberately no `--activate`, `--confirm`, install or rollback action.

## Replayed gates

Before producing a transaction review, Stage C2 must verify:

1. it is running as the normal user on `aarch64`;
2. the Stage C1 manifest has the exact header and 12 regular files;
3. every candidate checksum and mode matches the package rootfs;
4. every Stage C1 result is `PASS`;
5. the Stage C1 report is package version 2 and retains all inertness promises;
6. no Python cache, symlink or special object is present;
7. the empty `/var/lib/a-clockwork-plex/split-bus` directory remains in the
   manifest;
8. the current production ALSA file is still the exact physically validated
   pre-Stage-C checksum, owner, mode and alarm-under-Master graph;
9. `snd_aloop` is still index 7, ID `ACP_Loopback`, two substreams and
   `pcm_notify=1`;
10. no CamillaDSP process or activation marker exists;
11. the generated helper still rejects mutations with exit 78;
12. every generated unit still requires the absent approval marker;
13. every unprivilegedly inspectable managed file destination is absent and no
    visible managed destination conflicts with the package;
14. any destination hidden by a protected parent directory is recorded as
    `privileged-check-required`, never inferred to be absent;
15. the three application services remain loaded, active and enabled;
16. the three proposed Stage C services remain not found.

Any visible mismatch stops the review. Stage C2 never treats an unexpected
existing destination as an upgrade candidate.

## Protected destination boundary

The normal `andy` account cannot traverse `/etc/sudoers.d`, so an unprivileged
`lstat()` of `/etc/sudoers.d/a-clockwork-plex-audio-route` returns
`PermissionError` even when the named file is absent.

Stage C2 deliberately does not use `sudo` to resolve that ambiguity. Instead it:

- records the destination as `unverified` in `destination-state.tsv`;
- creates a `.privileged-check-required` marker containing `UNVERIFIED`;
- does not create an `.absent` marker;
- carries the exact path into `activation-blockers.txt` and the future install
  ordering;
- requires a new root-owned activation-time snapshot to resolve the file or
  exact-absence state before any privileged write.

A protected destination is therefore an explicit activation blocker, not a
Stage C2 crash and not evidence of absence.

## Review snapshot

Stage C2 writes only inside its private review directory. It copies the current
active ALSA file, creates explicit absence markers for genuinely observed absent
managed files, creates protected-path markers where the normal account cannot
inspect a destination, and records directory existence, modes and owners.

This is evidence for reviewing the transaction design. It is deliberately not an
activation-authoritative backup: any future approved installer must repeat the
entire snapshot immediately before its first privileged write.

## Generated review outputs

- `results.tsv`
- `destination-state.tsv`
- `review-snapshot/filesystem-state.tsv`
- `review-snapshot/rootfs/...`
- `review-snapshot/absence-markers/...`
- `service-state.tsv`
- `mixer-state.tsv` and raw control outputs
- `module-dac-state.tsv`
- `dac-hw-params.txt`
- `rollback-obligations.tsv`
- `package-fingerprint.tsv`
- `install-command-plan.txt`
- `rollback-command-plan.txt`
- `activation-blockers.txt`
- `report.txt`

The command-plan files are prose review artefacts, not executable shell scripts.

## Safety boundary

Stage C2:

- invokes no `sudo`;
- writes no `/etc`, `/usr/local`, `/var/lib` or systemd path;
- performs only `systemctl show`, `is-active` and `is-enabled` reads;
- performs only `amixer ... sget` reads;
- uses `fuser` only to record the current DAC owner;
- does not open any PCM;
- does not load or unload a module;
- does not change a mixer;
- does not start, stop, restart, enable or disable a service;
- creates no activation marker;
- never converts a permission failure into a claimed absence.

## Promotion boundary

A successful Stage C2 review closes transaction planning, not installation.
Persistent activation remains blocked until every protected path is resolved by
a fresh root-owned activation snapshot, the inert route helper is replaced by
reviewed transactional logic, exact activation-time rollback is implemented,
automatic direct failback is proven, the EQ helper migrates to CamillaDSP,
dashboard health/degraded reporting is connected, failure injection and exact
uninstall pass, and the user explicitly approves the physical install.
