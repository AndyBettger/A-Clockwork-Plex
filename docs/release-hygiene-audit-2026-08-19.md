# Final release hygiene audit — 19 August 2026

**Status refreshed:** 22 August 2026  
**Current result:** release hygiene complete through checkpoint #72; explicit owner approval remains.

This document is the classification record for the final Phase 7 repository cleanup. The replacement-SD physical clean-room gate completed at checkpoint #64. Post-clean-room cleanup was deliberately evidence-driven: files were removed only after installer/runtime/reference/test review proved they were not required by installation, rollback, supported diagnostics, maintained regression coverage or useful release provenance.

## Retained repository authorities

Keep:

- `setup.sh` as the human-facing installer and `appliance-installer.sh` as the guarded lower-level transactional engine;
- `app/`, `installer/`, `systemd/` and the pinned `vendor/` runtime material;
- `config.example.json`, requirements, licence and ignore contracts;
- the supported audio lifecycle under `scripts/audio/`: `preflight-eq.sh`, `install-direct.sh`, `install-eq.sh`, `repair-audio.sh`, `uninstall-eq.sh`, `verify-audio.sh`;
- helper/install/verifier sources reached by the supported installer/runtime or retained as deliberate diagnostics/recovery tooling;
- `.github/workflows/tests.yml` and maintained regression tests;
- current operator/architecture documentation, physical evidence and deliberately classified historical provenance.

`scripts/audio/preflight-eq.sh` remains the historical read-only bedroom-Pi validation gate and is intentionally retained as a diagnostic/acceptance tool, not a production installation path.

## Completed cleanup checkpoints

### #64 — clean tracked checkout — physical PASS

Exact physically tested source `215bcedb43369844b5968ae24a7169e49636ef99` produced no `git status --porcelain` output after repeat public setup, formal verifiers and normal commissioned operation. This proves legitimate Weather/cache/audio/NFC runtime state does not dirty tracked source.

### #65 — Stage-C validation subsystem — PASS

`da58f1586ca03827399f915af0301b9a104bf7e2` removed obsolete Stage-C implementation/harness/fixtures. Tests #4073 exposed 77 positive Stage-C test modules coupled solely to that removed subsystem; follow-up `ea043030086fe4afb92e8ed682c62eb254c98ae3` retired those tests and added a negative retirement guard. Tests #4075 / run `32541368986`: **972/972 PASS**.

### #66 — pre-production audio laboratory/rehearsal layer — PASS

`5fbc0a43f86b93132c3e132a9cd1cf0adad4b4f7` removed 14 obsolete laboratory/rehearsal scripts, including the disabled bare `scripts/install-master-eq.sh`, plus 13 dedicated historical test modules. `tests/test_retired_audio_lab_guard.py` pins those paths absent and the supported audio lifecycle present. Tests #4085 / run `32544751465`: **900/900 PASS**.

### #67 — superseded standalone helper installers — PASS

`82896ccaa88de52eced2a309e730256878f236b8` retired `scripts/install-shared-audio.sh`, `scripts/install-alarm-audio-helper.sh` and `scripts/install-shairport-name-helper.sh`. Runtime helpers and guarded transactional `scripts/install-appliance-helpers.sh` remain. Tests #4089 / run `32545282737`: **903/903 PASS**.

### #68 — legacy AirPlay source-tree artifacts — PASS

`9b4edfa41a0cb037bd9ce041ca097e9502be03a8` retired the old static Shairport callbacks that directly stopped/started Plexamp, their `display-mode.sh` fallback and the standalone metadata-listener installer. Current callbacks are rendered from `a-clockwork-plex-airplay-wrappers.py` and integration is owned transactionally by `install-airplay-integration.sh`. Tests #4091 / run `32545747002`: **907/907 PASS**.

### #69 — retained-script catalogue + local validation runner — PASS

`scripts/README.md` documents every retained regular file in `scripts/`, `scripts/audio/` and `scripts/audio_eq_camilladsp/` by purpose, safety class and intended use. `tests/test_script_catalog.py` dynamically enforces catalogue completeness. `scripts/run-tests.sh` now discovers current Python, shell and JavaScript source instead of carrying stale filenames. Tests #4095 / run `32546030629`: **911/911 PASS**.

### #70 — documentation classification + current-guide repair — PASS

`docs/README.md` classifies current authorities, architecture/testing guides, physical evidence, durable rationale, roadmap archives and historical Stage-C/EQ-development families. Historical provenance remains in place instead of being rewritten. Stale current-looking AirPlay, alarm-audio, application-state and testing guides were repaired to the accepted PlaybackCoordinator, fixed `-6.5 dB` reserve, alarm-bypass, Weather and validation contracts. `tests/test_docs_catalog.py` dynamically enforces top-level docs classification. Tests #4101 / run `32546425637`: **915/915 PASS**.

### #71 — final branch/ref + tracked-file/install-dependency audit — PASS

The two temporary refs `tmp-noop-annunciator-do-not-use` and `tmp-noop-annunciator-do-not-use-2` both pointed to ancestral commit `3dddbb24b9eb5b7f91efc7e6caf1b249dfba2123` with no unique work and were deleted through the GitHub web UI. A fresh branch listing now contains only:

- `main`;
- `feature/alarm-engine`;
- `feature/typography-weather-bridge`;
- `stage-c-terminal-install-20260806`.

The latter two are intentionally retained because they contain unique divergent/provenance history.

Root-tree inspection on exact release-hygiene head `da26e00f41117e0c1c5449a629ba451496fd5367` contains only expected repository authorities: `.github`, `.gitignore`, `LICENSE`, `README.md`, `app`, `appliance-installer.sh`, `config.example.json`, `docs`, `installer`, `requirements.txt`, `scripts`, `setup.sh`, `systemd`, `tests`, `vendor`.

Recursive tree inspection found no tracked `__pycache__`, `.pyc`, `node_modules`, `.venv` or `.tmp` residue.

`installer/repository-dependencies.txt` remains the exact supported fresh-install/runtime/verifier source closure. `tests/test_installer_repository_dependencies.py` proves:

1. manifest entries are exact, unique and safe relative paths;
2. every pinned dependency is a regular repository file and not a symlink;
3. public `setup.sh` fails closed on the manifest before sourcing/fetching/applying installer components;
4. `appliance-installer.sh` reuses the same dependency gate through `installer/lib/components.sh`;
5. high-risk transitive dependencies remain explicitly pinned.

All five checks passed in final Tests #4103.

### #72 — final post-cleanup validation — PASS

Exact validated release-hygiene head: `da26e00f41117e0c1c5449a629ba451496fd5367`.

Tests #4103 / workflow run `32546649704` passed:

- production Python compile;
- JavaScript syntax and page-wiring assertions;
- current shell syntax checks;
- release-hygiene/retirement guards;
- exact installer dependency closure;
- script and documentation catalogues;
- complete Python regression suite: **915/915 PASS** (`Ran 915 tests in 49.276s`, `OK`).

The workflow emitted GitHub Actions' hosted-runner notice that current `actions/checkout@v4`, `actions/setup-python@v5` and `actions/upload-artifact@v4` target the deprecated Actions Node 20 runtime and are being forced to Node 24. This is an upstream Actions-maintenance warning, not an A Clockwork Plex appliance/runtime/test failure, and does not invalidate #72.

## Documentation status

- `docs/eq-audio-installer-roadmap.md` is the active implementation/acceptance authority.
- Exact pre-consolidation roadmap history through checkpoint #64 remains byte-for-byte at `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md`.
- `docs/INSTALL.md` is the normal operator authority.
- `docs/appliance-installer.md` documents the advanced guarded engine.
- `scripts/README.md` is the retained-script purpose/safety/use catalogue.
- `docs/README.md` is the current-vs-historical documentation map.
- `docs/final-clean-room-physical-progress-2026-08-21.md` remains the final replacement-SD physical evidence record.

## Final release status

Repository/release hygiene is complete. The accepted physical release candidate remains unchanged; cleanup after #64 was source/repository/documentation hygiene and did not reopen the physical gate.

The only remaining release gate is **explicit owner approval**. Until that approval is given, PR #2 must remain Draft/open/unmerged. Do not mark it ready and do not merge it merely because all technical gates are green.
