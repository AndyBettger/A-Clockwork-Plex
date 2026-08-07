# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 2 and repository validation are complete; Phase 3 now requires only the read-only bedroom-Pi preflight run  
**Started:** 7 August 2026  
**Last updated:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Current production state:** Direct shared audio route restored and working; no EQ installation committed  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has already been selected and physically proven with Plexamp, AirPlay and scheduled alarms. The supported work now turns that known-good design into a small, understandable and repeatable installer that:

1. installs the EQ-capable audio architecture on the bedroom Pi;
2. provides the backend required for final interface and Settings testing;
3. can be verified, repaired and removed without rebuilding the Pi;
4. can later be called by the full A Clockwork Plex installer after an SD-card replacement or fresh deployment.

This roadmap replaces further development of the experimental multi-stage Stage C transactional installer as the intended production deployment path. Stage C evidence and code remain preserved for reference, but the supported installer uses readable operations, explicit checks and straightforward rollback.

## Decisions already made

These decisions remain settled unless new physical evidence proves one of them unsafe.

### Audio graph

The production-capable route is the tested split-bus CamillaDSP design documented in [`production-eq-split-bus-design.md`](production-eq-split-bus-design.md):

```text
Plexamp player volume -> Plexamp trim --\
                                         +-> Music Master -> music EQ/headroom --\
AirPlay sender volume -> AirPlay trim ---/                                      \
                                                                                  +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume -------------------------------/
```

The alarm lane bypasses Music Master and the music EQ, then joins the music lane before the final limiter.

### Install-time audio profiles

The future full installer will offer two audio capabilities:

- **Direct audio** — Plexamp, AirPlay and alarm playback without CamillaDSP EQ.
- **EQ-capable audio** — the split-bus route with CamillaDSP, music-only EQ and direct alarm bypass.

This is an installation choice, not the everyday EQ on/off setting.

### Runtime EQ enable and disable

When EQ-capable audio is installed, Plexamp and AirPlay stay mapped to the split-bus PCMs whether EQ is enabled or bypassed.

- **EQ enabled:** stored Bass, Mid and Treble values are applied.
- **EQ disabled:** CamillaDSP bypasses the music EQ while preserving the stored curve.
- **Return to neutral:** deliberately sets all three bands to `0 dB`.

Everyday bypass must not remap ALSA devices, restart source services or select another route. While bypassed, the Settings and drawer controls remain visible but are greyed and locked.

### Failure behaviour

Everyday EQ bypass is not failback. Automatic failback is reserved for a genuine backend failure, such as CamillaDSP failing to start or the expected PCMs becoming unavailable. The appliance must then return to the known-good direct route, restore affected application services and report that the EQ backend is unavailable.

## Known-good production baseline

The bedroom Pi is currently restored to the accepted direct-audio baseline:

- `plexamp.service`, `shairport-sync.service` and `a-clockwork-plex.service` are active and enabled;
- the original direct ALSA route is active;
- active route SHA-256 is `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
- no production EQ lock or authoritative transaction remains;
- no supported EQ installation is committed;
- Plexamp sees its normal outputs and audible playback works;
- the retained Stage C failure was archived and closed successfully.

This remains the rollback reference state. Repository, CI and temporary-root tests have not changed the bedroom Pi.

## Supported commands

```text
scripts/audio/preflight-eq.sh
scripts/audio/install-eq.sh
scripts/audio/uninstall-eq.sh
scripts/audio/verify-audio.sh
scripts/audio/repair-audio.sh
```

`preflight-eq.sh` is the read-only host/parser gate. The other four commands own the installed audio lifecycle.

## Supported installer behaviour

The installer is designed to:

1. verify the host, invoking user, direct route and required existing services;
2. retain one exact pre-EQ backup;
3. verify the DAC and accepted sample contract;
4. install and persist the accepted `snd_aloop` configuration;
5. install the split-bus and direct-alarm-bypass ALSA routes;
6. install the accepted CamillaDSP binary and configuration;
7. install the EQ and route helpers with restricted sudo rules;
8. install the route, CamillaDSP and failback systemd units;
9. reload systemd and activate the split-bus route in the reviewed order;
10. apply saved EQ state as active or bypassed;
11. restore Plexamp, AirPlay and dashboard availability;
12. verify PCMs, services, backend state and rollback assets;
13. print a concise result.

If installation fails before completion, rollback restores the exact direct route, files, runtime state, module state where applicable, managed services and captured application-service state before reporting failure.

Repeated installation delegates to repair and preserves the original pre-EQ backup. Uninstall on a direct-audio system is a no-op with a clear result.

## Current repository layout

```text
installer/
├── lib/
│   ├── common.sh
│   ├── audio.sh
│   ├── backup.sh
│   ├── files.sh
│   ├── runtime.sh
│   ├── services.sh
│   └── verification.sh
└── profiles/
    ├── direct/
    └── eq-split-bus/

scripts/audio/
├── preflight-eq.sh
├── install-eq.sh
├── uninstall-eq.sh
├── verify-audio.sh
└── repair-audio.sh

scripts/audio_eq_camilladsp/
├── __init__.py
├── model.py
├── runtime.py
└── cli.py
```

The standalone audio commands will later become the tested audio component called by the full installer rather than being rewritten.

## Roadmap

### Phase 0 — roadmap and baseline

**Goal:** Establish one written source of truth and freeze the current working direct state.

- [x] Confirm direct audio is restored and audible.
- [x] Confirm the retained Stage C transaction and lock are absent.
- [x] Preserve failed Stage C evidence for diagnosis.
- [x] Stop expanding the experimental transactional installer.
- [x] Define DSP bypass rather than route swapping for everyday EQ disable.
- [x] Publish and maintain this roadmap.

**Exit condition:** Met.

### Phase 1 — known-good artifact inventory

**Goal:** Identify the exact tested files and runtime behaviour without redesigning the graph.

- [x] Inventory accepted Stage A, A2, Stage B and Stage C0 artifacts.
- [x] Identify split-bus and direct-alarm-bypass ALSA configurations.
- [x] Identify CamillaDSP configuration, binary provenance and EQ-helper contract.
- [x] Identify route, CamillaDSP and failback units.
- [x] Identify persistent `snd_aloop` requirements.
- [x] Record destinations, modes, owners and service ordering.
- [x] Publish [`eq-audio-installation-manifest.md`](eq-audio-installation-manifest.md).
- [x] Freeze `stage-c-terminal-install-20260806` as historical and recovery-only.

**Finding:** the former `scripts/a-clockwork-plex-audio-eq.py` implementation was tied to the rejected `alsaequal` backend. The supported implementation uses CamillaDSP while preserving the dashboard command and JSON contract.

**Exit condition:** Met.

### Phase 2 — standalone installer implementation

**Goal:** Build the smallest readable installer that can install and reverse the known-good design.

- [x] Materialise accepted route, CamillaDSP and loopback profiles.
- [x] Implement the CamillaDSP EQ helper with `status`, `set`, `live`, `bypass` and `neutral`.
- [x] Implement shared shell helpers and fixed root handling.
- [x] Implement exact direct-route backup and validation.
- [x] Implement managed file installation and manifests.
- [x] Implement persistent loopback setup.
- [x] Implement fixed route actions and route-state reporting.
- [x] Implement systemd reload, enablement and service ordering.
- [x] Apply saved active or bypassed EQ state.
- [x] Implement automatic install rollback.
- [x] Implement explicit uninstall, verification and repair.
- [x] Preserve the original backup across repeated install/repair.
- [x] Add runtime snapshots for failed install, repair and uninstall restoration.
- [x] Prevent installed Python launchers from leaving bytecode cache files.

**Exit condition:** Met. The implementation exists and the complete repository suite passes.

### Phase 3 — non-production and read-only host validation

**Goal:** Prove the complete lifecycle without changing live audio, then validate the candidate with the real Pi parsers.

- [x] Validate installer-library and command shell syntax.
- [x] Exercise install, verify, repair, uninstall and reinstall under a temporary root.
- [x] Exercise repeated install and original-backup preservation.
- [x] Inject mid-install failure and verify exact direct-baseline restoration.
- [x] Exercise runtime snapshot and permission handling.
- [x] Confirm tests do not write production paths.
- [x] Resolve the six failures exposed by the first complete repository run.
- [x] Re-run the complete suite successfully.
- [x] Implement standalone read-only `preflight-eq.sh`.
- [x] Add a static safety contract proving the preflight has no privileged or audio-mutation path.
- [ ] Run the preflight on the bedroom Pi with the accepted CamillaDSP 4.1.3 binary.
- [ ] Record successful real ALSA, CamillaDSP, systemd and sudoers parser results.
- [ ] Record exact before/after production-state equality.

#### Repository-validation checkpoint

The first corrected full gate, GitHub Actions run **31144537952** for commit `f465d60aa8aa7deae637585b0495a2b940e30f2b`, produced **1,340/1,340 passing tests**.

The six earlier failures were fixed by:

1. assigning the runtime snapshot root before deriving `state-files.tsv`;
2. using the privileged installed-file read boundary and structural JSON validation in `verify-audio.sh`;
3. explicitly invoking Bash for internal installer-to-verifier and installer-to-repair handoffs.

#### Read-only preflight implementation checkpoint

The dedicated preflight was added in commit `ff69a805a2ab5e52b7be9de2bb436239bd4713f1`, with its safety tests in commit `e283b9578659b97be918d0d3402a03f5b33152ab`.

GitHub Actions run **31145374614** produced:

- **1,346 tests run**;
- **1,346 passed**;
- **0 failed**;
- Python compilation passed;
- JavaScript, page-wiring and shell-syntax checks passed;
- all six new preflight safety tests passed.

The preflight:

- requires the exact direct-route checksum and active/enabled application services;
- requires EQ managed paths, lock, approval record, installed marker and backup to be absent;
- pins the accepted CamillaDSP 4.1.3 binary digest;
- parses both candidate routes with isolated `aplay -L` configurations without opening a PCM;
- renders and checks the neutral DSP configuration with `camilladsp --check`;
- verifies candidate units inside a private systemd model;
- checks rendered restricted rules with `visudo`;
- captures route, service, loopback, managed-path and DAC state before and after;
- requires exact equality and retains evidence beneath `/var/tmp/a-clockwork-plex-eq-preflight.*`;
- contains no `sudo`, install, route-selection, module-load, service-mutation, mixer-write or PCM-opening command.

No production Pi state was changed while implementing or testing it.

**Exit condition:** The repository half is met. Phase 3 completes when the bedroom Pi reports `EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS` with exact before/after equality.

### Phase 4 — controlled bedroom-Pi installation

**Goal:** Install the EQ-capable backend once on the current appliance.

Before the run, operator instructions must explicitly state the required audio state, expected temporary outage, success markers, rollback behaviour and final verifier.

- [ ] Verify the accepted direct baseline and checksum.
- [ ] Capture the exact pre-EQ backup.
- [ ] Install and start the EQ-capable graph.
- [ ] Restore Plexamp, AirPlay and dashboard availability.
- [ ] Verify public PCMs, backend state and rollback assets.
- [ ] Verify audible Plexamp playback through the split-bus route.
- [ ] Record the result here.

**Exit condition:** The installer reports success and Plexamp is audible through the split-bus route.

### Phase 5 — feature and interface acceptance

- [ ] Plexamp and AirPlay use the EQ-capable music lane.
- [ ] Bass, Mid and Treble changes are audible and truthful.
- [ ] AirPlay/Plexamp takeover and return still work.
- [ ] EQ disable uses bypass without route remapping.
- [ ] Stored values survive bypass and return when enabled.
- [ ] Controls are greyed and locked while bypassed.
- [ ] Return to neutral sets all bands to `0 dB`.
- [ ] Music Master at 0% silences music but not a real alarm.
- [ ] EQ and bypass do not alter alarm tone or level.
- [ ] Maximum Alarm Volume and the final limiter still behave correctly.
- [ ] NFC playback and dashboard controls still work.

**Exit condition:** The backend and redesigned interface behave as one coherent feature.

### Phase 6 — failure, reboot and uninstall acceptance

- [ ] Controlled CamillaDSP failure returns to usable direct audio.
- [ ] One controlled reboot restores the EQ-capable graph.
- [ ] Saved active/bypassed state and persistent loopback survive reboot.
- [ ] Explicit uninstall restores the accepted direct-route checksum.
- [ ] Direct audio remains usable after uninstall and reboot.
- [ ] Reinstall after uninstall succeeds.

**Exit condition:** Installation, reboot, failure recovery, uninstall and reinstall are repeatable.

### Phase 7 — integration with the full Pi installer

- [ ] Add Direct audio / EQ-capable audio selection.
- [ ] Call the tested standalone component for EQ-capable audio.
- [ ] Add a non-interactive profile argument.
- [ ] Hide or truthfully disable EQ controls for a direct-only installation.
- [ ] Apply saved active/bypassed state for EQ-capable installs.
- [ ] Add fresh-Pi prerequisites and post-install verification.

**Exit condition:** A fresh Pi can be built into either supported audio profile without manual reconstruction.

### Phase 8 — cleanup and release preparation

- [ ] Record an archival reference for the final Stage C branch head.
- [ ] Delete `stage-c-terminal-install-20260806` after archival reference is recorded.
- [ ] Mark Stage C transactional material as historical/non-production.
- [ ] Update `README.md` with the two audio profiles and supported commands.
- [ ] Link installer, verifier, repair and uninstall documentation.
- [ ] Record final results and accepted deviations here.
- [ ] Review PR #2 separately; do not merge without explicit approval.

**Exit condition:** The supported path is obvious to a future maintainer or owner rebuilding the Pi.

## Progress status

| Phase | State | Current note |
|---|---|---|
| 0. Roadmap and baseline | Complete | Direct audio recovered; roadmap published |
| 1. Artifact inventory | Complete | Exact audio contract and manifest published |
| 2. Standalone installer | Complete | Four lifecycle commands and shared libraries are green |
| 3. Non-production/read-only validation | In progress | 1,346/1,346 repository tests pass; only the read-only Pi run remains |
| 4. Bedroom-Pi installation | Not started | Blocked only on a successful read-only preflight |
| 5. Feature/interface acceptance | Not started | Follows controlled installation |
| 6. Failure/reboot/uninstall acceptance | Not started | Follows feature acceptance |
| 7. Full-installer integration | Not started | Reuses the accepted standalone component |
| 8. Cleanup/release preparation | Not started | Includes Stage C archival and documentation cleanup |

## Immediate next action

Run `scripts/audio/preflight-eq.sh` from a fresh checkout pinned to its reviewed branch head while **normal direct audio remains active and audible**.

The run must:

1. locate the accepted CamillaDSP 4.1.3 binary by its exact digest;
2. run without `sudo`;
3. retain its evidence directory;
4. report the accepted direct-route checksum;
5. report `EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS`;
6. prove the before/after production snapshots are identical.

No bedroom-Pi installation, route change, module load, service restart, mixer write or EQ activation is authorised by this step.

## Roadmap maintenance discipline

This file is part of the implementation workflow, not an occasional retrospective document.

- Any commit that materially completes, blocks or changes a roadmap item must update this file in the same change or immediately afterward.
- A phase must not be marked complete until its exit condition passes.
- Failed gates must be recorded with exact scope and result.
- Any physical Pi change must record route, checksum, relevant service state and rollback outcome.
- The roadmap must be checked before project status is reported in chat.
- PR #2 remains Draft and must not be merged without explicit approval.

The owner should not need to prompt for routine roadmap updates as development progresses.
