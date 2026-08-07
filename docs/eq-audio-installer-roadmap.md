# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 2 implementation and repository validation are complete; Phase 3 continues with read-only bedroom-Pi parser validation  
**Started:** 7 August 2026  
**Last updated:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Current production state:** Direct shared audio route restored and working; no EQ installation committed  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has already been selected and physically proven with Plexamp, AirPlay and scheduled alarms. The current task is not to redesign that graph. It is to turn the known-good design into a small, understandable and repeatable installer that:

1. installs the EQ-capable audio architecture on the current bedroom Pi;
2. provides the backend required for final interface and Settings testing;
3. can be verified, repaired and removed without rebuilding the Pi;
4. can later be called by the full A Clockwork Plex installer after an SD-card replacement or fresh deployment.

This roadmap replaces further development of the experimental multi-stage transactional installer as the intended production deployment path. The existing Stage C evidence and code remain preserved for reference, but the supported installer favours readable operations, explicit checks and straightforward rollback.

## Decisions already made

These decisions are settled unless new physical evidence proves one of them unsafe.

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

This choice determines which audio architecture is installed. It is not the same as the everyday EQ on/off setting.

### Runtime EQ enable and disable

When the EQ-capable architecture is installed, Plexamp and AirPlay remain mapped to the same split-bus PCMs whether EQ is enabled or disabled.

The Settings switch uses CamillaDSP bypass:

- **EQ enabled:** stored Bass, Mid and Treble values are applied.
- **EQ disabled:** the EQ filters are bypassed while the stored curve is preserved.
- **Return to neutral:** deliberately sets Bass, Mid and Treble to `0 dB`.

Disabling EQ must not remap ALSA devices, restart Plexamp, restart AirPlay or swap the active route.

While bypassed, the Settings and drawer EQ controls remain visible but are greyed and locked. Re-enabling EQ restores the stored curve.

### Failure behaviour

Everyday EQ bypass is not failback.

Automatic failback is reserved for a genuine backend failure, such as CamillaDSP failing to start or the expected audio PCMs becoming unavailable. In that case the appliance returns to the known-good direct shared route, restores the affected application services and reports that the EQ backend is unavailable.

## Known-good production baseline

The bedroom Pi is currently restored to the accepted direct-audio baseline:

- `plexamp.service`, `shairport-sync.service` and `a-clockwork-plex.service` are active and enabled;
- the original direct ALSA route is active;
- active route SHA-256 is `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
- no production EQ lock or authoritative transaction remains;
- no EQ installation is committed;
- Plexamp sees its normal audio outputs and audible playback works;
- the retained Stage C failure was archived and closed successfully.

This remains the rollback reference state for the new installer. Repository-only and temporary-root tests performed during Phases 2 and 3 have not changed the bedroom Pi.

## Supported installer scope

The standalone EQ installer owns only the audio capability. It does not reinstall the dashboard or rebuild unrelated application features.

### Supported commands

```text
scripts/audio/preflight-eq.sh
scripts/audio/install-eq.sh
scripts/audio/uninstall-eq.sh
scripts/audio/verify-audio.sh
scripts/audio/repair-audio.sh
```

The first command is the read-only host/parser gate. The other four commands own the installed audio lifecycle.

### Installation responsibilities

The supported installer is designed to:

1. verify the host, invoking user and required existing services;
2. verify the current direct route and retain one exact pre-EQ backup;
3. verify the DAC and accepted sample contract;
4. install and persist the required `snd_aloop` configuration;
5. install the known-good split-bus and direct-alarm-bypass ALSA configurations;
6. install the accepted CamillaDSP binary and configuration;
7. install the dashboard EQ control helper and restricted sudo rules;
8. install the route, CamillaDSP and failback systemd units;
9. reload systemd;
10. select the split-bus route;
11. enable and start the managed audio services in the correct order;
12. restart Plexamp, AirPlay and the dashboard only where required;
13. apply the saved Settings EQ state as active or bypassed;
14. verify the public audio PCMs, managed services, dashboard backend and rollback copy;
15. print a short human-readable result.

### Rollback responsibilities

If installation fails before completion, rollback must:

1. stop newly started managed services;
2. restore the exact backed-up direct ALSA route;
3. remove only files installed by the EQ installer;
4. reload systemd;
5. restore the captured active and enabled state of Plexamp, AirPlay and the dashboard;
6. restore captured runtime state files and the prior CamillaDSP service state where applicable;
7. verify the direct public PCMs and direct route;
8. leave a readable failure report.

This path deliberately does not use Stage C authority borrowing, temporary approval records, numbered adapter generations or a retained-transaction framework.

### Idempotence

Running the installer again on an already installed system delegates to repair and preserves the original pre-EQ backup rather than creating a second baseline.

Running the uninstaller on a direct-audio system reports that no EQ backend is installed and leaves the system unchanged.

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

The standalone audio commands are intended to become library-backed entry points used by the future full installer rather than being rewritten.

## Roadmap

### Phase 0 — roadmap and baseline

**Goal:** Establish one written source of truth and freeze the current working direct state.

- [x] Confirm the direct route is restored and audible.
- [x] Confirm the retained Stage C transaction and lock are absent.
- [x] Preserve the failed Stage C evidence for diagnosis.
- [x] Agree to stop expanding the experimental transactional installer.
- [x] Agree that the Settings switch uses DSP bypass rather than route swapping.
- [x] Publish this roadmap.

**Exit condition:** Met. The implementation can be assessed against an agreed plan rather than reconstructed from chat history.

### Phase 1 — known-good artifact inventory

**Goal:** Identify the exact tested files and runtime behaviour to reuse without redesigning the audio graph.

- [x] Inventory the accepted Stage A, A2, Stage B and Stage C0 artifacts.
- [x] Identify the final split-bus ALSA configuration.
- [x] Identify the direct-alarm-bypass configuration.
- [x] Identify the accepted CamillaDSP configuration and binary provenance.
- [x] Identify the EQ helper, runtime state and sudo-rule requirements.
- [x] Identify the route, CamillaDSP and failback service units.
- [x] Identify persistent `snd_aloop` requirements.
- [x] Record installation destinations, modes and owners.
- [x] Record the required service start, stop and restart order.
- [x] Confirm which files are source-controlled and which are generated.
- [x] Publish [`eq-audio-installation-manifest.md`](eq-audio-installation-manifest.md).
- [x] Freeze `stage-c-terminal-install-20260806` as historical and recovery-only; do not merge it.

**Finding:** the former `scripts/a-clockwork-plex-audio-eq.py` implementation was tied to the rejected `alsaequal` backend. It has been replaced with a CamillaDSP-backed helper while preserving the dashboard command and JSON contract.

**Exit condition:** Met. The audio contract and installation manifest are documented without mutating the Pi.

### Phase 2 — standalone installer implementation

**Goal:** Build the smallest readable installer that can install and reverse the known-good audio design.

- [x] Materialise the accepted split-bus, direct-failback and neutral CamillaDSP profiles as reviewed static files.
- [x] Implement the CamillaDSP-backed EQ helper while preserving `status`, `set`, `live`, `bypass` and `neutral`.
- [x] Implement shared shell helpers with clear errors and fixed root handling.
- [x] Implement direct-route backup and validation.
- [x] Implement managed EQ file installation and manifests.
- [x] Implement persistent loopback setup.
- [x] Implement the small route helper and route-state reporting.
- [x] Implement systemd reload, enablement and service ordering.
- [x] Implement saved Settings state application as active or bypassed.
- [x] Implement automatic rollback on installation failure.
- [x] Implement explicit uninstall.
- [x] Implement verification and repair commands.
- [x] Implement concise installation and failure reporting.
- [x] Add repeated-install delegation to repair while retaining the original backup.
- [x] Add runtime snapshots for repair, failed install and failed uninstall restoration.
- [x] Ensure installed Python launchers do not leave bytecode cache files.

**Implementation checkpoint — 7 August 2026:**

- the CamillaDSP-backed EQ helper preserves the dashboard command and JSON contract;
- the route helper owns only fixed route, validation and failback actions;
- install, verify, repair and uninstall are separate, readable entry points;
- destructive commands require explicit activation tokens while prepare remains the default;
- one exact pre-EQ backup supports rollback and later uninstall;
- repair and failed uninstall snapshot the current route, state files and CamillaDSP service state;
- a full live verifier is required before install or repair can report success;
- temporary-root lifecycle, repeated-install and injected-failure tests are present;
- the former approval, authority-borrowing and retained-transaction machinery is not used;
- no Phase 2 implementation work changed the bedroom Pi.

**Exit condition:** Met. All implementation items exist and the complete repository suite passes with no installer regression.

### Phase 3 — non-production and read-only host validation

**Goal:** Prove file handling, idempotence and rollback without changing live audio, then validate the candidate with the real Pi parsers in read-only or prepare-only mode.

- [x] Validate shell syntax for the installer libraries and four lifecycle commands.
- [x] Add temporary-root installation lifecycle coverage.
- [x] Add repeated-install and original-backup preservation coverage.
- [x] Add explicit uninstall and reinstall coverage.
- [x] Add injected mid-install rollback coverage.
- [x] Add runtime snapshot and permission coverage.
- [x] Confirm temporary-root tests do not write production paths.
- [x] Resolve the six failures from the earlier complete repository suite.
- [x] Re-run the complete repository suite and record a green result.
- [ ] Implement the dedicated read-only `preflight-eq.sh` host/parser command.
- [ ] Validate both ALSA configurations with the Pi's real ALSA parser in an isolated configuration root.
- [ ] Validate rendered CamillaDSP configuration with the accepted CamillaDSP 4.1.3 binary.
- [ ] Validate the systemd units with the Pi's real systemd verifier.
- [ ] Confirm the read-only host checks make no production change.

#### Green repository-validation checkpoint

GitHub Actions `Tests` run **31144537952** for source commit `f465d60aa8aa7deae637585b0495a2b940e30f2b` on 7 August 2026 produced:

- **1,340 tests run**;
- **1,340 passed**;
- **0 failed**;
- Python compilation passed;
- JavaScript checks, page-wiring checks and shell-syntax checks passed;
- the temporary-root install, verify, repair, uninstall and reinstall lifecycle passed;
- repeated installation preserved the original pre-EQ backup;
- injected mid-install failure restored the direct baseline;
- runtime-state snapshots restored present and absent files correctly;
- privileged verifier and manifest-tampering checks passed;
- no production Pi path, route, module or service was changed.

The six earlier failures were resolved by three narrow corrections:

1. `installer/lib/runtime.sh` now assigns the snapshot root before deriving `state-files.tsv`, preventing accidental resolution to `/state-files.tsv`;
2. `scripts/audio/verify-audio.sh` now uses the privileged installed-file read boundary, validates saved state through the shared verifier library and parses the route/EQ helper JSON structurally;
3. installer-to-verifier and installer-to-repair handoffs explicitly invoke Bash, so correctness does not depend on repository executable-bit preservation.

**Exit condition:** The complete suite is green and the real Pi parsers accept the candidate without changing production audio or service state. The repository half is met; the read-only Pi parser half remains.

### Phase 4 — controlled bedroom-Pi installation

**Goal:** Install the EQ-capable backend once on the current appliance.

Before the physical run, operator instructions must explicitly state:

- whether Plexamp must be playing, paused or stopped;
- which services and screen elements will temporarily disappear;
- when audio will go silent;
- what success and automatic rollback will look like;
- which command verifies the final state.

The physical run will:

- [ ] verify the accepted direct baseline and checksum;
- [ ] capture the exact pre-EQ backup;
- [ ] install the EQ-capable audio graph;
- [ ] start the managed services;
- [ ] restore Plexamp, AirPlay and dashboard availability;
- [ ] verify public PCMs, backend state and rollback copy;
- [ ] verify ordinary Plexamp playback is audible through the split-bus route;
- [ ] record the installation result in this roadmap.

**Exit condition:** The installer reports success and ordinary Plexamp playback is audible through the split-bus route.

### Phase 5 — feature and interface acceptance

**Goal:** Test the real feature rather than the deployment framework.

- [ ] Plexamp plays through the EQ-capable route.
- [ ] Bass, Mid and Treble changes are audible and reported correctly.
- [ ] AirPlay plays through the same music EQ lane.
- [ ] AirPlay takeover still pauses Plexamp correctly.
- [ ] Returning from AirPlay to Plexamp still works.
- [ ] Settings EQ disable uses bypass without remapping devices.
- [ ] Stored band values survive bypass and return when re-enabled.
- [ ] EQ controls are greyed and locked while bypassed.
- [ ] Return to neutral sets all three bands to `0 dB`.
- [ ] Music Master at 0% silences Plexamp and AirPlay.
- [ ] Music Master at 0% does not reduce a real scheduled alarm.
- [ ] EQ and bypass do not alter alarm tone or level.
- [ ] Maximum Alarm Volume still caps scheduled alarms.
- [ ] The final limiter protects combined music and alarm playback.
- [ ] NFC playback and dashboard controls still work.

**Exit condition:** The installed backend and redesigned Settings interface behave as one coherent feature.

### Phase 6 — failure, reboot and uninstall acceptance

**Goal:** Prove the appliance remains recoverable in normal ownership conditions.

- [ ] Controlled CamillaDSP failure returns to direct audio.
- [ ] Failback leaves Plexamp, AirPlay and dashboard usable.
- [ ] One controlled reboot restores the EQ-capable graph.
- [ ] Saved active or bypassed state survives reboot.
- [ ] Persistent `snd_aloop` state is verified after reboot.
- [ ] Explicit uninstall restores the accepted direct-route checksum.
- [ ] Direct audio remains usable after uninstall and reboot.
- [ ] Reinstall after uninstall succeeds.

**Exit condition:** Installation, reboot, failure recovery, uninstall and reinstall are all repeatable.

### Phase 7 — integration with the full Pi installer

**Goal:** Make SD-card replacement and fresh installation straightforward.

- [ ] Add the full-installer choice: Direct audio or EQ-capable audio.
- [ ] Make the EQ option call the tested standalone audio installer.
- [ ] Provide a non-interactive audio-profile argument.
- [ ] Ensure the direct profile does not expose a misleading active EQ toggle.
- [ ] Ensure the EQ-capable profile applies saved active or bypassed state.
- [ ] Add fresh-Pi documentation and prerequisites.
- [ ] Add post-install verification output.

**Exit condition:** A fresh Pi can be built into either supported audio profile without manual reconstruction.

### Phase 8 — cleanup and release preparation

**Goal:** Reduce confusion and leave maintainable documentation.

- [ ] Preserve the final `stage-c-terminal-install-20260806` head as an archival reference after its evidence has been extracted.
- [ ] Delete the frozen `stage-c-terminal-install-20260806` branch after the archival reference is recorded.
- [ ] Mark the experimental Stage C transactional installer as archived or non-production.
- [ ] Keep its evidence and lessons without presenting it as the supported install path.
- [ ] Update `README.md` with the two audio-profile choices.
- [ ] Link the installer, verifier, repair and uninstall documentation.
- [ ] Update this roadmap with final results and accepted deviations.
- [ ] Review PR #2 separately; do not merge without explicit approval.

**Exit condition:** The supported installation path is obvious to a future maintainer or to the owner rebuilding after an SD-card failure.

## Progress status

| Phase | State | Current note |
|---|---|---|
| 0. Roadmap and baseline | Complete | Direct audio recovered; roadmap published |
| 1. Artifact inventory | Complete | Exact audio contract and installation manifest published |
| 2. Standalone installer | Complete | Four lifecycle commands, shared libraries and complete 1,340-test gate are green |
| 3. Non-production/read-only validation | In progress | Repository and temporary-root validation are green; standalone preflight and real Pi parser checks remain |
| 4. Bedroom-Pi installation | Not started | Blocked only on the remaining read-only Phase 3 checks |
| 5. Feature and interface acceptance | Not started | Follows controlled installation |
| 6. Failure, reboot and uninstall acceptance | Not started | Follows feature acceptance |
| 7. Full-installer integration | Not started | Reuses the accepted standalone installer |
| 8. Cleanup and release preparation | Not started | Includes Stage C archival and documentation cleanup |

## Immediate next action

Implement and run the **read-only bedroom-Pi validation gate** as `scripts/audio/preflight-eq.sh`:

1. check out the exact reviewed branch head in a fresh temporary directory rather than using the stale production checkout;
2. keep normal direct audio active and audible during the checks;
3. validate both candidate ALSA route files with the Pi's real ALSA parser using isolated configuration roots;
4. render and validate the neutral CamillaDSP configuration with the accepted CamillaDSP 4.1.3 binary;
5. validate the candidate systemd units with the Pi's real verifier in a private unit model;
6. validate rendered restricted sudoers rules with `visudo`;
7. capture the direct-route checksum, managed-file absence, loopback state, DAC parameters and application-service state before and after;
8. require exact before/after equality and retain an evidence directory under `/var/tmp`;
9. record the result here before preparing a controlled installation command.

The preflight must contain no `sudo`, route selection, module loading, service start/stop/restart, mixer write or PCM-opening command.

No bedroom-Pi installation, route change, module load, service restart or EQ activation is authorised by this validation step.

## Roadmap maintenance discipline

This file is part of the implementation workflow, not an occasional retrospective document.

From this checkpoint onward:

- any commit that materially completes, blocks or changes a roadmap item must update this file in the same change or the immediately following documentation commit;
- a phase must not be described as complete until its recorded exit condition has passed;
- failed test gates must be recorded with the exact scope and result rather than omitted;
- any physical Pi change must record the resulting route, checksum, relevant service state and rollback outcome;
- the roadmap must be checked before project status is reported in chat;
- PR #2 remains Draft and must not be merged without explicit approval.

The owner should not need to prompt for routine roadmap updates as development progresses.
