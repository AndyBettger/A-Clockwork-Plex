# Final release hygiene audit — 19 August 2026

**Status refreshed:** 22 August 2026  
**Current result:** release hygiene complete through checkpoint #72; final documentation/identity polish complete through #75; historical branch provenance resolved at #76. Two obsolete historical refs are proved safe to delete, then explicit owner approval remains.

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

The two temporary refs `tmp-noop-annunciator-do-not-use` and `tmp-noop-annunciator-do-not-use-2` both pointed to ancestral commit `3dddbb24b9eb5b7f91efc7e6caf1b249dfba2123` with no unique work and were deleted through the GitHub web UI. The branch listing at that checkpoint contained:

- `main`;
- `feature/alarm-engine`;
- `feature/typography-weather-bridge`;
- `stage-c-terminal-install-20260806`.

The latter two were retained temporarily because they contained unique commit identities that still required provenance review. That review is now resolved under checkpoint #76 below.

Root-tree inspection on exact release-hygiene head `da26e00f41117e0c1c5449a629ba451496fd5367` contained only expected repository authorities: `.github`, `.gitignore`, `LICENSE`, `README.md`, `app`, `appliance-installer.sh`, `config.example.json`, `docs`, `installer`, `requirements.txt`, `scripts`, `setup.sh`, `systemd`, `tests`, `vendor`.

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

### #73 — normal-user documentation layout — PASS

The root of `docs/` is now deliberately limited to `README.md`, `INSTALL.md`, `appliance-installer.md` and the `development/`, `roadmap/` and `archive/` directories. Engineering design, dated verification/audit material and historical snapshots are kept out of the normal operator path. `tests/test_docs_catalog.py` enforces that boundary.

The live roadmap was renamed from its obsolete EQ/audio-installer-era identity to `docs/roadmap/ROADMAP.md`. Historical roadmap snapshots remain alongside it or inside the exact engineering archive.

### #74 — project-user / “Andy” portability — PASS

Supported installer/runtime sources were audited for concrete `/home/andy`, `${USER:-andy}`, `User=andy` and `Group=andy` assumptions. Historical evidence remains untouched, but live installation now derives the invoking/project identity.

The first portability run correctly exposed one remaining exception: the CamillaDSP systemd source unit still contained `User=andy`. That unit is now a generic `User=ACP_PROJECT_USER` source template, rendered by `installer/lib/audio.sh` to the selected appliance project user while retaining the accepted `Group=audio` execution contract. Rooted-install coverage proves the placeholder cannot leak into the installed unit.

### #75 — post-polish full validation — PASS

Exact implementation head: `0698ebb6ac786812740312f96cf8b09cb221e41d`.

Tests #4127 / workflow run `32554699819` passed:

- production Python compile;
- JavaScript syntax and page-wiring assertions;
- current shell syntax checks;
- complete Python regression suite: **922/922 PASS** (`Ran 922 tests in 44.797s`, `OK`).

The only workflow notice was the same hosted-runner Node-runtime deprecation warning; it is not an appliance/runtime/test failure.

### #76 — historical branch provenance resolution — PASS; ref deletion pending

The two remaining historical development refs have now been compared against the release branch rather than being merged speculatively.

#### `feature/typography-weather-bridge`

This branch contains 63 commits after merge-base `35100c5292c4582dfd45983d1321f1cc63e39d0a`, affecting exactly 16 typography/Clock/Weather/AirPlay presentation files. Those 63 commits are precisely the head of PR #1, **Typography and weather bridge redesign**. PR #1 was merged into `main` on 19 July 2026 as squash commit `c69b2ee9f0ceed119d07e6d696e8b4a723abb614`. Its original branch commits therefore remain graph-divergent even though their product work was integrated. The subsequent release branch has continued to evolve and physically accept those same presentation areas. No unique branch work requires merging.

Conclusion: **safe to delete the historical branch ref**.

#### `stage-c-terminal-install-20260806`

This branch contains 23 unique commits after merge-base `0c6a91858dbebfa6a76da419c99dcb6e1ce9aca9`. Its complete unique file delta is confined to 16 Stage-C terminal-install/recovery/test paths: `scripts/stage_c_transaction/...`, `scripts/*stage-c*.sh` and `tests/test_stage_c*.py`.

Checkpoint #65 deliberately retired that subsystem, and `tests/test_retired_stage_c_guard.py` now asserts that those exact Stage-C implementation/script/test families remain absent. The accepted installer is the later `setup.sh` → `appliance-installer.sh` architecture, not this experimental terminal-install branch.

Conclusion: **obsolete provenance only; safe to delete the historical branch ref and do not merge it**.

The currently connected GitHub actions expose branch creation/movement but not branch/ref deletion, so the two deletions themselves must be performed with GitHub's branch-delete UI (or another authenticated Git client/API). They are intentionally not simulated by moving or overwriting refs.

## Documentation status

- `docs/roadmap/ROADMAP.md` is the single live implementation/release/future-product roadmap.
- `docs/roadmap/history-through-checkpoint64.md` preserves the exact pre-consolidation roadmap history through checkpoint #64.
- `docs/INSTALL.md` is the normal operator authority.
- `docs/appliance-installer.md` documents the advanced guarded engine.
- `scripts/README.md` is the retained-script purpose/safety/use catalogue.
- `docs/README.md` is the normal-user/development/roadmap/archive documentation map.
- `docs/development/evidence/final-clean-room-physical-progress-2026-08-21.md` remains the final replacement-SD physical evidence record.
- `docs/archive/pre-release-engineering-snapshot-2026-08-22/` preserves the former engineering-heavy docs tree for archaeology without cluttering normal use.

## Final release status

The accepted physical release candidate remains unchanged; cleanup after #64 was source/repository/documentation hygiene except for the narrowly scoped installer-user portability correction validated at #75.

No unique product work remains on either historical development branch. The only repository-hygiene action left is deleting the now-proven-obsolete refs `feature/typography-weather-bridge` and `stage-c-terminal-install-20260806`.

After those refs are deleted, the only remaining release gate is **explicit owner approval**. Until that approval is given, PR #2 must remain Draft/open/unmerged. Do not mark it ready and do not merge it merely because all technical gates are green.
