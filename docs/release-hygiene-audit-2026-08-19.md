# Final release hygiene audit — 19 August 2026

**Status refreshed:** 21 August 2026

This document is the classification pass for the final Phase 7 repository cleanup. It deliberately makes **no broad historical deletions**. Deletion/archival comes only after the final clean-room `setup.sh` installation has passed and after a tracked-file dependency audit proves that a candidate is not required by installation, rollback, diagnostics or maintained regression coverage.

## Principles

1. A file does **not** need to execute on the bedside Pi to deserve a place in the repository. Maintained tests, CI, architecture notes and useful diagnostics are development/release assets.
2. A file that was created for one temporary physical experiment, one old stage, or one roadmap rewrite should not survive indefinitely merely because it once helped acceptance.
3. The finished installer has two intentionally separate roles with unambiguous names:
   - `setup.sh` is the human-facing one-command entry point, including CamillaDSP acquisition and the interactive Plexamp claim handoff;
   - `appliance-installer.sh` is the guarded lower-level transactional installer/recovery engine.
   The old root `install.sh` name duplicated that guarded engine and has been removed; it is not a third supported entry point.
4. Do not delete historical evidence until the final release README/INSTALL and final acceptance evidence contain enough durable information to understand the released appliance and its safety decisions.
5. Run the full validation suite after every cleanup batch and repeat the installer dependency audit before merge.

## Keep — production/install/runtime authority

The following classes are part of the finished appliance or its supported installation/recovery path and should remain:

- root `setup.sh` and `appliance-installer.sh`;
- `app/` production application code, templates and static assets;
- `installer/` transaction libraries, profiles and templates;
- `systemd/` managed service definitions;
- `vendor/` pinned vendored runtime material used by installation;
- `config.example.json`, `requirements.txt`, `LICENSE` and `.gitignore`;
- production audio lifecycle under `scripts/audio/`, including Direct/EQ install, repair, uninstall, preflight and verification;
- helper/install/verifier scripts reached by the guarded installer or required for supported diagnostics/recovery;
- Weather secret management and sanitized payload-inspection tooling where it remains the supported diagnostic path.

The fresh-install source closure is now additionally pinned in `installer/repository-dependencies.txt`. Both `setup.sh` and the lower-level appliance engine fail closed early when that supported repository payload is incomplete. This dependency manifest is a release-safety contract, not generated inventory.

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

- `scripts/dev/finalize_eq_phase2_roadmap.py` has already been removed. Maintained release-hygiene regression explicitly requires the obsolete Phase-2 roadmap mutator to stay absent.
- old `inspect-stage-c*` evidence-identity helpers whose only purpose was a completed Stage C checkpoint remain review candidates; do not remove them until their test/evidence references and clean-room relevance are proved unnecessary.

### Laboratory/rehearsal scripts

Review the old `test-*-lab.sh`, CamillaDSP laboratory and physical-rehearsal scripts. Some may still be useful engineering diagnostics, while others were temporary stepping stones superseded by `scripts/audio/install-eq.sh`, `repair-audio.sh`, `uninstall-eq.sh` and `verify-audio.sh`. Keep only those that still have a deliberate supported purpose.

### Superseded EQ/Stage-C documentation

The `docs/` directory contains many dated design/result documents from the journey to the accepted split-bus architecture, including Stage C design/result files and early DSP laboratory evidence. The final cleanup should decide between:

- retaining a small number of durable architecture/safety documents;
- consolidating historical evidence into one archive/history document; or
- deleting documents whose only useful facts are already preserved in the active roadmap and final acceptance record.

Do not leave dozens of stage-numbered documents in the finished project simply because the branch accumulated them during development. Equally, do not perform broad deletion before the final replacement-SD clean-room proof establishes the finished evidence/dependency boundary.

### Intermediate physical-acceptance records

The final repository should retain enough evidence to show what was physically validated, but it does not necessarily need every intermediate failed-attempt narrative as a first-class top-level document. Once the final wiped-SD acceptance is complete, consolidate where sensible and retain the final authoritative evidence plus any failure record that documents an important safety invariant.

### Segment-display design assets

`docs/airplay-segment-cell.svg` is now the editable companion to the selected Version 3 runtime geometry in `app/static/js/segment-display.js`. Keep it through final visual acceptance; if later cleanup changes its status, preserve enough provenance to reconstruct or adjust the runtime geometry rather than treating it as an unexplained scratch asset.

## Documentation status

### README.md

The release-candidate README has been rewritten for the actual appliance. After the final wiped-SD run, perform one last proofread against the observed installation and update experience rather than redesigning it from assumptions.

### INSTALL.md

Keep `docs/INSTALL.md` as the operator authority. The public command remains `bash setup.sh`; `appliance-installer.sh` is the guarded lower-level engine invoked by setup and is not a second normal-user installation procedure. After the final wiped-SD run, edit only what the actual clean-room experience proves needs changing. Avoid duplicating the full engineering runbook into README.

### PR #2 description — completed 21 August

The stale Stage-C/future-EQ body has been replaced with the current integrated appliance scope, the supported `setup.sh`/`appliance-installer.sh` path, the current 1,762-test baseline and the remaining replacement-SD/release gates. The metadata update did **not** change review readiness: GitHub confirmed PR #2 remains Draft, open and unmerged.

## `.gitignore` and runtime-state review

The source-side runtime/generated-state audit is complete for the known state classes. The ignore file covers the important local/runtime state classes, including:

- `config.json` and runtime JSON state, including atomic-save `*.json.tmp` leftovers;
- forecast/rainfall caches;
- generated static runtime assets;
- Python/test/cache/build/editor outputs.

Maintained release-hygiene regression checks Git's tracked-file contract rather than treating a legitimate ignored runtime file created by another test as committed source. This source/CI closure passed at code head `ae2497450b5b9d106c2eb4d86301bd1bc32c455b` in Tests #4012 / run `32430838605`.

The **physical clean-checkout proof remains pending**. After the final replacement-SD clean-room install, run `git status --porcelain` after normal operation, Weather refreshes, alarm use and reboot. Any legitimate runtime file that still dirties the checkout should be ignored or moved to the proper runtime-state location rather than committed.

## Fresh-install dependency audit — completed initial closure

The previously shallow top-level source check has been expanded into an explicit supported repository closure in `installer/repository-dependencies.txt`. It protects direct and transitive fresh-install inputs including installer libraries, EQ repair/profile/template assets, NFC requirements/checker/runtime, `config.example.json` and the dashboard unit source.

Both the public `setup.sh` route and direct lower-level engine route validate the manifest and fail closed before installation if a required source is missing or unsafe. Dedicated regression pins the exact closure and validates each entry as a regular repository file. Tests #4012 / run `32430838605` passed Python compile, JavaScript/page wiring, shell syntax and **1,762/1,762 unit tests**.

This does not remove the need for a **final post-cleanup dependency audit**. Any later safe deletion batch must be followed by the same closure check, and the replacement-SD clean-room run remains the physical proof that the retained source set is sufficient.

## Final deletion gate

Before deleting any remaining candidate:

1. search `setup.sh`, `appliance-installer.sh`, `installer/`, `scripts/`, systemd units, tests and docs for references;
2. confirm it is not copied/installed indirectly by a directory-level operation;
3. confirm no maintained test relies on it as a fixture or contract;
4. delete in small logical batches;
5. run compile/syntax checks and the complete unit suite;
6. run the final installer dependency audit again;
7. keep PR #2 Draft until the cleaned repository and final physical install are both accepted.

## Current classification result

The repository still needs a deliberate final cleanup, but the correct target is **historical development residue**, not the core test suite or the two intentional installer roles. The unambiguous installer naming cleanup, known runtime/generated-state audit, initial fresh-install dependency closure and PR-description refresh are complete.

Broad destructive cleanup remains deliberately deferred until the replacement-SD `setup.sh` run proves the final appliance from a clean checkout. Safe cleanup before that proof should be limited to items whose obsolete status is already certain; uncertain Stage-C/provenance files stay put. After clean-room acceptance, finish historical consolidation/ref cleanup, repeat the dependency audit and full CI, and only then consider PR #2 ready for owner review.