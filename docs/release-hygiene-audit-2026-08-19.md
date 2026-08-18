# Final release hygiene audit — 19 August 2026

This document is the classification pass for the final Phase 7 repository cleanup. It deliberately makes **no deletions**. Deletion/archival comes only after the final clean-room `setup.sh` installation has passed and after a tracked-file dependency audit proves that the candidate is not required by installation, rollback, diagnostics or maintained regression coverage.

## Principles

1. A file does **not** need to execute on the bedside Pi to deserve a place in the repository. Maintained tests, CI, architecture notes and useful diagnostics are development/release assets.
2. A file that was created for one temporary physical experiment, one old stage, or one roadmap rewrite should not survive indefinitely merely because it once helped acceptance.
3. `setup.sh` and `install.sh` are intentionally separate and should remain unless the final dependency audit disproves their distinct roles:
   - `setup.sh` is the human-facing one-command entry point, including CamillaDSP acquisition and the interactive Plexamp claim handoff;
   - `install.sh` is the guarded lower-level transactional installer/recovery engine.
4. Do not delete historical evidence until the final release README/INSTALL and final acceptance evidence contain enough durable information to understand the released appliance and its safety decisions.
5. Run the full validation suite after every cleanup batch and repeat the installer dependency audit before merge.

## Keep — production/install/runtime authority

The following classes are part of the finished appliance or its supported installation/recovery path and should remain:

- root `setup.sh` and `install.sh`;
- `app/` production application code, templates and static assets;
- `installer/` transaction libraries, profiles and templates;
- `systemd/` managed service definitions;
- `vendor/` pinned vendored runtime material used by installation;
- `config.example.json`, `requirements.txt`, `LICENSE` and `.gitignore`;
- production audio lifecycle under `scripts/audio/`, including Direct/EQ install, repair, uninstall, preflight and verification;
- helper/install/verifier scripts reached by the guarded installer or required for supported diagnostics/recovery;
- Weather secret management and sanitized payload-inspection tooling where it remains the supported diagnostic path.

## Keep — maintained development/release safety net

These are not normal runtime inputs, but they should remain in the source repository:

- `.github/workflows/tests.yml`;
- maintained regression tests under `tests/`;
- tests specifically covering real production launch/import paths, installer convergence, rollback, secret boundaries, alarm ownership, Weather source authority and Clock/UI contracts;
- durable architecture/contract documents that explain invariants which are not obvious from user documentation.

The fact that a fresh Git clone contains `tests/` is not, by itself, repository clutter. They are not run by normal `setup.sh`, and deleting useful tests merely to make the appliance checkout visually smaller would weaken the project for negligible benefit.

## Review carefully — likely historical/archive candidates

These need a reference/dependency check before any removal, but are the main cleanup targets:

### One-off development helpers

- `scripts/dev/finalize_eq_phase2_roadmap.py` — a phase-specific roadmap mutator and strong deletion candidate once confirmed unreferenced.
- old `inspect-stage-c*` evidence-identity helpers whose only purpose was a completed Stage C checkpoint.

### Laboratory/rehearsal scripts

Review the old `test-*-lab.sh`, CamillaDSP laboratory and physical-rehearsal scripts. Some may still be useful engineering diagnostics, while others were temporary stepping stones superseded by `scripts/audio/install-eq.sh`, `repair-audio.sh`, `uninstall-eq.sh` and `verify-audio.sh`. Keep only those that still have a deliberate supported purpose.

### Superseded EQ/Stage-C documentation

The `docs/` directory contains many dated design/result documents from the journey to the accepted split-bus architecture, including Stage C design/result files and early DSP laboratory evidence. The final cleanup should decide between:

- retaining a small number of durable architecture/safety documents;
- consolidating historical evidence into one archive/history document; or
- deleting documents whose only useful facts are already preserved in the active roadmap and final acceptance record.

Do not leave dozens of stage-numbered documents in the finished project simply because the branch accumulated them during development.

### Intermediate physical-acceptance records

The final repository should retain enough evidence to show what was physically validated, but it does not necessarily need every intermediate failed-attempt narrative as a first-class top-level document. Once the final wiped-SD acceptance is complete, consolidate where sensible and retain the final authoritative evidence plus any failure record that documents an important safety invariant.

### Segment-display design assets

`docs/airplay-segment-cell.svg` and any replacement/refined segment artwork must be reviewed after the current 14-segment SVG tidy-up is integrated. Do **not** delete the artwork merely because it lives under `docs/`: determine whether it is the editable source-of-truth for generated/runtime segment geometry or only an obsolete design scratch file.

## Documentation work still required

### README.md

The current README substantially predates the finished appliance. It still describes production EQ as future work and presents the older Weather model. Rewrite it for the released appliance with:

- what A Clockwork Plex is;
- validated hardware;
- the normal `bash setup.sh` installation path;
- Plexamp claim plus first GUI sign-in/library/output commissioning;
- Plexamp, AirPlay, NFC and alarm behaviour;
- split-bus EQ/Music Master/Maximum Alarm Volume behaviour;
- Ecowitt versus Weather Underground, including the one-custom-destination limitation and supplementary indoor readings;
- Clock/Weather display features and alarm annunciator;
- updating and supported diagnostics;
- a link to `docs/INSTALL.md` for full commissioning instructions.

### INSTALL.md

Keep `docs/INSTALL.md` as the operator authority. After the final wiped-SD run, edit only what the actual clean-room experience proves needs changing. Avoid duplicating the full engineering runbook into README.

### PR #2 description

The PR description is stale and still describes persistent EQ as future work. Before the PR leaves Draft, replace it with a concise current summary of the finished appliance, final physical evidence, validation status and any intentionally deferred non-blocking checks.

## `.gitignore` review

The current ignore file already covers the important local/runtime state classes, including:

- `config.json` and runtime JSON state;
- forecast/rainfall caches;
- generated static runtime assets;
- Python/test/cache/build/editor outputs.

After the final clean-room install, run `git status --porcelain` on the installed Pi after normal operation, Weather refreshes, alarm use and reboot. Any legitimate runtime file that dirties the checkout should be ignored or moved to the proper runtime-state location rather than committed.

## Final deletion gate

Before deleting any candidate:

1. search `setup.sh`, `install.sh`, `installer/`, `scripts/`, systemd units, tests and docs for references;
2. confirm it is not copied/installed indirectly by a directory-level operation;
3. confirm no maintained test relies on it as a fixture or contract;
4. delete in small logical batches;
5. run compile/syntax checks and the complete unit suite;
6. run the final installer dependency audit again;
7. keep PR #2 Draft until the cleaned repository and final physical install are both accepted.

## Initial classification result

The repository does need a cleanup, but the correct target is **historical development residue**, not the core test suite or the two root installer entry points. The final wiped-SD `setup.sh` run should happen before destructive cleanup; the clean-room evidence then tells us exactly which installer/runtime files are indispensable. Cleanup follows that acceptance, and a final dependency/CI pass proves that the tidied tree still represents a buildable appliance.
