# Final release hygiene audit — 19 August 2026

**Status refreshed:** 22 August 2026

This document is the classification record for the final Phase 7 repository cleanup. The replacement-SD physical clean-room gate is complete through checkpoint #64, so deliberate post-clean-room cleanup is now active. Deletion remains evidence-driven: a file is removed only after repository/dependency/reference review proves that it is not required by installation, rollback, supported diagnostics, maintained regression coverage or useful release provenance.

## Principles

1. A file does **not** need to execute on the bedside Pi to deserve a place in the repository. Maintained tests, CI, architecture notes and supported diagnostics are release assets.
2. A file created solely for one temporary experiment, retired subsystem or historical rehearsal should not survive indefinitely merely because it once helped development.
3. The finished installer has two intentional roles: `setup.sh` is the human-facing one-command entry point; `appliance-installer.sh` is the guarded lower-level transactional engine.
4. Preserve useful historical evidence, but move completed chronology out of active authority when it obscures the current release state.
5. Cleanup happens in small logical batches, with full CI after each batch and a final dependency/tracked-file audit before owner approval.

## Keep — production/install/runtime authority

Retain:

- root `setup.sh` and `appliance-installer.sh`;
- `app/` production application code/templates/static assets;
- `installer/` transaction libraries, profiles, templates and `repository-dependencies.txt`;
- `systemd/` managed service definitions;
- `vendor/` pinned runtime material used by installation;
- `config.example.json`, requirements, licence and ignore contracts;
- the supported audio lifecycle under `scripts/audio/`: `preflight-eq.sh`, `install-direct.sh`, `install-eq.sh`, `repair-audio.sh`, `uninstall-eq.sh`, `verify-audio.sh`;
- helper/install/verifier scripts reached by the guarded installer or still required for supported diagnostics/recovery;
- Weather secret management and sanitized WU inspection tooling.

`scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate and is deliberately retained as a diagnostic/acceptance tool, not a production installation path.

## Keep — maintained development/release safety net

Retain:

- `.github/workflows/tests.yml`;
- maintained regression tests under `tests/` that protect current production/runtime/install contracts;
- current installer convergence, rollback, secret-boundary, playback ownership, Weather authority and UI regressions;
- durable architecture/safety documents that explain non-obvious release invariants;
- `scripts/prepare-plexamp-upgrade-rehearsal.sh`, which remains a separate read-only maintenance diagnostic with current safety coverage.

The fact that a fresh clone contains tests is not repository clutter. Cleanup targets historical coupling, not useful regression coverage.

## Completed cleanup batches

### Checkpoint #64 — clean tracked checkout — physical PASS

The exact physically tested runtime/source head `215bcedb43369844b5968ae24a7169e49636ef99` produced no `git status --porcelain` output after repeat public setup, the second formal verifier set and normal commissioned operation. This closes the physical clean-checkout gate; legitimate Weather/cache/audio/NFC runtime state does not dirty tracked source.

### Checkpoint #65 — Stage-C validation subsystem — PASS

- `da58f1586ca03827399f915af0301b9a104bf7e2` removed the obsolete Stage-C implementation, executable harness and fixtures.
- Tests #4073 correctly exposed 77 dedicated positive `tests/test_stage_c*.py` modules that still imported the intentionally deleted subsystem.
- `ea043030086fe4afb92e8ed682c62eb254c98ae3` removed those historical positive tests and added `tests/test_retired_stage_c_guard.py`.
- Tests #4075 / run `32541368986` passed compile, JavaScript/page wiring, shell syntax and **972/972 unit tests**.

Current regressions that assert Stage-C authority fields do not return were retained.

### Checkpoint #66 — pre-production audio laboratory/rehearsal layer — PASS

Repository-dependency and operator-path review proved that the laboratory-era scripts were not part of `installer/repository-dependencies.txt`, the public installer path or current supported diagnostics. Their dedicated test modules inspected only those historical scripts rather than current production behavior.

Cleanup commit `5fbc0a43f86b93132c3e132a9cd1cf0adad4b4f7` removed:

- the disabled bare `scripts/install-master-eq.sh` laboratory-era path;
- 13 additional ALSA/CamillaDSP/headroom/split-bus/physical-rehearsal scripts;
- 13 dedicated historical safety-test modules coupled only to that retired machinery.

`tests/test_retired_audio_lab_guard.py` now:

- pins all 14 retired script paths absent;
- pins all 13 dedicated historical test paths absent;
- requires the six supported `scripts/audio/` lifecycle files to remain present;
- requires CI to syntax-check the supported lifecycle instead of the retired labs.

Tests #4085 / run `32544751465` passed compile, JavaScript/page wiring, shell syntax and **900/900 unit tests**. The lower test count is expected: the retired 13 historical modules contained 72 tests, while the new guard contributes four current retirement checks.

## Documentation status

### Active roadmap

The oversized active roadmap through checkpoint #64 is preserved byte-for-byte as `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md`. `docs/eq-audio-installer-roadmap.md` is again the concise current acceptance/release authority. The consolidation itself passed Tests #4083 after CI forced restoration of the exact retained preflight and protected-production-SD contracts.

### README

README has now been proofread against the completed replacement-SD acceptance sequence. It describes the physical gate as complete and no longer presents the retired `scripts/install-master-eq.sh` laboratory-era path as a still-present blocked installer.

### INSTALL / advanced installer guide

Keep `docs/INSTALL.md` as the normal operator authority and `docs/appliance-installer.md` as the advanced lower-level engine guide. The public command remains `bash setup.sh`.

### Physical evidence

`docs/final-clean-room-physical-progress-2026-08-21.md` remains the final replacement-SD evidence record. Earlier focused physical documents remain useful provenance unless a later evidence consolidation proves them redundant.

## Fresh-install dependency audit

`installer/repository-dependencies.txt` remains the supported repository source closure. Both public and lower-level installer paths fail closed before installation if a required source file is missing or unsafe.

Checkpoint #66 deliberately removed only files outside that manifest and outside the supported operator/runtime path. A **final post-cleanup dependency/tracked-file audit** is still required after all remaining cleanup is complete.

## Branch/ref classification

Intentional refs to preserve:

- `main` — release base;
- `feature/alarm-engine` — active Draft PR #2 head;
- `feature/typography-weather-bridge` — preserve for now because it contains unique divergent history;
- `stage-c-terminal-install-20260806` — preserve for now as historical/provenance material because it contains unique commits not reachable from the active branch.

Known safe temporary-ref deletion candidates:

- `tmp-noop-annunciator-do-not-use`;
- `tmp-noop-annunciator-do-not-use-2`.

Both temporary refs were re-confirmed present on 22 August. Prior comparison established that they point at already-ancestral no-op history with no unique work. The available connector still exposes branch update but not branch-ref deletion, so they remain recorded rather than falsely claimed removed. Delete them with an authorised Git interface during the final ref-hygiene step, then re-list branches.

## Remaining review targets

The next cleanup work is deliberately narrower than the completed Stage-C/audio-lab retirements:

- inventory remaining one-off scripts/helpers not in the installer manifest and distinguish supported diagnostics from historical probes;
- classify the large `docs/` history, preserving architecture/safety/final evidence while archive-consolidating genuinely superseded stage documents where useful;
- proofread active operator/architecture documentation after each consolidation;
- remove the two proven temporary refs;
- rerun final tracked-file/install-dependency audit;
- run the complete validation suite on the final cleaned tree;
- obtain explicit owner approval before PR #2 leaves Draft or merges.

## Final deletion gate

Before another candidate is removed:

1. search current installer/runtime/operator paths and maintained tests for references;
2. confirm it is not copied or installed indirectly;
3. confirm it is not a current diagnostic, fixture or architecture contract;
4. preserve useful historical facts elsewhere before deleting evidence-only material;
5. delete in one small logical batch;
6. run compile/syntax checks and the complete unit suite;
7. update this audit and the active roadmap only after CI proves the batch.

## Current classification result

The broad physical/release boundary is now proven, and two large historical subsystems have been safely retired without touching accepted runtime behavior. The remaining target is **residual historical development/documentation/ref residue**, not the production application, supported audio lifecycle, installer payload or maintained regression suite.

PR #2 remains Draft/open/unmerged. Release hygiene is not complete until the remaining inventory/docs/ref work, final dependency audit, final full validation and explicit owner approval are complete.
