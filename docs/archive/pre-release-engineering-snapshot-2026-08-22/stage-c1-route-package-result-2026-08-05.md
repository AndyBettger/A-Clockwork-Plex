# Stage C1 route-package result — 5 August 2026

Status: **PASS — prepare-only package validated on `plexamp-bedroom`; no production change was made.**

## Purpose

Stage C1 converted the physically proven Stage C split-bus and direct alarm-bypass
routes into a deterministic root-filesystem-shaped candidate package. The package
remained deliberately inert: its route helper rejected mutation actions, its
systemd units required an absent approval marker, and the preparation command had
no activation interface.

## Host and package

- host: `plexamp-bedroom`
- architecture: `aarch64`
- Stage C1 package version: `2`
- laboratory: `/var/tmp/a-clockwork-plex-stage-c1-review-v2.jvsNEY`
- verified CamillaDSP: `4.1.3 (05e9cfc)`
- verified CamillaDSP SHA-256:
  `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`
- verified pre-Stage-C ALSA SHA-256:
  `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`
- loopback contract: index `7`, ID `ACP_Loopback`, two substreams,
  `pcm_notify=1`
- DAC contract: `hw:CARD=Pro,DEV=0`
- audio format: `44100 Hz`, `S16_LE`, period `1024`, buffer `8192`
- regular package files: `12`

## Validation evidence

All package checks passed:

| Check | Result | Evidence |
|---|---|---|
| Split-bus ALSA parse | PASS | candidate parsed |
| Direct-failback ALSA parse | PASS | candidate parsed |
| Public PCM contract | PASS | all five public PCMs present in both routes |
| CamillaDSP configuration | PASS | verified 4.1.3 binary accepted the config |
| Route-helper syntax | PASS | compiled in memory |
| Sudoers candidate | PASS | `visudo` accepted the read-only rules |
| Package purity | PASS | 12 regular files; no cache, symlink or special objects |
| Systemd ordering | PASS | route authority precedes DSP and source services |
| Manifest contract | PASS | files/directories recorded; empty state directory retained |

The focused review also confirmed:

- `cache_artifacts=PASS`;
- the manifest contains
  `/var/lib/a-clockwork-plex/split-bus` as an empty root-owned `0755`
  directory;
- `file_count=12`;
- no `__pycache__` or `.pyc` object appears in the package.

## Manifest scope

The package contains candidates for:

- split-bus and direct alarm-bypass ALSA routes;
- CamillaDSP configuration;
- deterministic `snd_aloop` module load/options;
- route defaults;
- a verified CamillaDSP executable;
- an inert route helper;
- read-only sudoers rules;
- route-authority, CamillaDSP and failback systemd units;
- the empty persistent state directory.

The manifest records destination, mode, owner and checksum for every file and
records all required directories separately.

## Safety result

The preparation command:

- invoked no `sudo`;
- wrote no production path;
- loaded or unloaded no module;
- started, stopped, restarted, enabled or disabled no service;
- opened no PCM;
- changed no mixer value;
- created no approval marker;
- exposed no activation option;
- retained mutation actions at exit status `78`.

The live appliance therefore remained on the exact pre-Stage-C direct shared
mixer throughout the review.

## Decision

Stage C1 is closed as **physically host-validated prepare-only package PASS**.

The package is suitable as the immutable input to Stage C2 transaction planning.
It is not an installable release by itself. Persistent activation remains blocked
until activation-time snapshot/rollback code, transactional route mutation,
automatic failback, EQ migration, dashboard health integration and explicit
physical approval are complete.
