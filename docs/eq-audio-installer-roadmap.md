# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 2 in progress  
**Started:** 7 August 2026  
**Last updated:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Current production state:** Direct shared audio route restored and working; no EQ installation committed  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has already been selected and physically proven with Plexamp, AirPlay and scheduled alarms. The next task is not to redesign that audio graph. It is to turn the known-good design into a small, understandable and repeatable installer that:

1. installs the EQ-capable audio architecture on the current bedroom Pi;
2. provides the backend required for final interface and Settings testing;
3. can be removed or repaired without rebuilding the Pi;
4. can later be called by the full A Clockwork Plex installer after an SD-card replacement or fresh deployment.

This roadmap replaces further development of the experimental multi-stage transactional installer as the intended production deployment path. The existing Stage C evidence and code remain preserved for reference, but the new installer should favour readable operations, explicit checks and straightforward rollback.

## Decisions already made

These decisions are considered settled unless new physical evidence proves one of them unsafe.

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

### Runtime EQ enable/disable

When the EQ-capable architecture is installed, Plexamp and AirPlay remain mapped to the same split-bus PCMs whether the EQ is enabled or disabled.

The Settings switch must use CamillaDSP bypass:

- **EQ enabled:** stored Bass, Mid and Treble values are applied.
- **EQ disabled:** the EQ filters are bypassed while the stored curve is preserved.
- **Return to neutral:** deliberately sets Bass, Mid and Treble to `0 dB`.

Disabling EQ must not remap ALSA devices, restart Plexamp, restart AirPlay or swap the active route.

While bypassed, the Settings and drawer EQ controls should remain visible but be greyed and locked. Re-enabling EQ restores the stored curve.

### Failure behaviour

Everyday EQ bypass is not failback.

Automatic failback is reserved for a genuine backend failure, such as CamillaDSP failing to start or the expected audio PCMs becoming unavailable. In that case the appliance must return to the known-good direct shared route, restart the affected services and report that the EQ backend is unavailable.

## Known-good starting state

The current bedroom Pi has been restored to the accepted direct-audio baseline:

- `plexamp.service`, `shairport-sync.service` and `a-clockwork-plex.service` are active and enabled;
- the original direct ALSA route is active;
- active route SHA-256 is `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
- no production EQ lock or authoritative transaction remains;
- no EQ installation is committed;
- Plexamp sees its normal audio outputs and audible playback works;
- the retained Stage C failure was archived and closed successfully.

This is the rollback reference state for the new installer.

## Installer scope

The standalone EQ installer must own only the audio capability. It should not attempt to reinstall the whole dashboard or rebuild unrelated application features.

### Required installation responsibilities

The installer should:

1. verify the host, invoking user and required existing services;
2. verify the current direct route and record a backup;
3. verify the DAC and accepted sample contract;
4. install and persist the required `snd_aloop` configuration;
5. install the known-good split-bus and direct-alarm-bypass ALSA configurations;
6. install the tested CamillaDSP binary and configuration;
7. install the dashboard EQ control helper and its sudo rule;
8. install the route, CamillaDSP and failback systemd units;
9. reload systemd;
10. select the split-bus route;
11. enable and start the managed audio services in the correct order;
12. restart Plexamp, AirPlay and the dashboard as required;
13. apply the saved Settings EQ state as active or bypassed;
14. verify the public audio PCMs, managed services, dashboard backend and direct rollback copy;
15. print a short human-readable result.

### Required companion commands

The initial implementation should provide:

```text
scripts/audio/install-eq.sh
scripts/audio/uninstall-eq.sh
scripts/audio/verify-audio.sh
scripts/audio/repair-audio.sh
```

The final names may change slightly to fit repository conventions, but the responsibilities should remain separate and obvious.

### Rollback responsibilities

If installation fails before completion, rollback should:

1. stop any newly started managed services;
2. restore the backed-up direct ALSA route;
3. remove only files installed by the EQ installer;
4. reload systemd;
5. restore the original enabled/active state of Plexamp, AirPlay and the dashboard;
6. verify that the direct public PCMs are visible;
7. leave a readable failure report.

Rollback does not need authority borrowing, temporary approval records, numbered adapter generations or a separate retained-transaction framework.

### Idempotence

Running the installer again on an already installed system should verify and repair the installation rather than duplicate files or create a second configuration.

Running the uninstaller on a direct-audio system should report that no EQ backend is installed and leave the system unchanged.

## Proposed repository layout

The exact layout will be finalised as Phase 2 continues, but the target shape is:

```text
installer/
├── install.sh
├── uninstall.sh
├── verify.sh
├── lib/
│   ├── common.sh
│   ├── audio.sh
│   └── services.sh
└── profiles/
    ├── direct/
    │   └── 99-a-clockwork-plex-shared.conf
    └── eq-split-bus/
        ├── split-bus.conf
        ├── direct-alarm-bypass.conf
        ├── camilladsp-split-bus.yml
        ├── modules-load.d/
        └── modprobe.d/

scripts/audio/
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

The standalone audio scripts should later become library-backed entry points used by the full installer rather than being rewritten.

## Roadmap

### Phase 0 — roadmap and baseline

**Goal:** Establish one written source of truth and freeze the current working direct state.

- [x] Confirm the direct route is restored and audible.
- [x] Confirm the retained Stage C transaction and lock are absent.
- [x] Preserve the failed Stage C evidence for diagnosis.
- [x] Agree to stop expanding the experimental transactional installer.
- [x] Agree that the Settings switch uses DSP bypass rather than route swapping.
- [x] Publish this roadmap.

**Exit condition:** The next implementation step can be evaluated against an agreed plan rather than reconstructed from chat history.

### Phase 1 — known-good artifact inventory

**Goal:** Identify the exact tested files and runtime behaviour to reuse without redesigning the audio graph.

- [x] Inventory the accepted Stage A, A2, Stage B and Stage C0 artifacts.
- [x] Identify the final split-bus ALSA configuration.
- [x] Identify the direct-alarm-bypass configuration.
- [x] Identify the accepted CamillaDSP configuration and binary provenance.
- [x] Identify the EQ helper, runtime state and sudo-rule requirements.
- [x] Identify the route, CamillaDSP and failback service units.
- [x] Identify persistent `snd_aloop` requirements.
- [x] Record all installation destinations, modes and owners.
- [x] Record the required service start, stop and restart order.
- [x] Confirm which existing files are source-controlled and which must be generated.
- [x] Publish [`eq-audio-installation-manifest.md`](eq-audio-installation-manifest.md).
- [x] Freeze `stage-c-terminal-install-20260806` as historical/recovery-only; do not merge it.

**Finding:** the former `scripts/a-clockwork-plex-audio-eq.py` was tied to the rejected `alsaequal` backend. Phase 2 has replaced that implementation with a CamillaDSP-backed helper while preserving the existing dashboard command and JSON contract.

**Exit condition:** Met. The exact audio contract and a concise installation manifest are documented without mutating the Pi.

### Phase 2 — standalone installer implementation

**Goal:** Build the smallest readable installer that can install and reverse the known-good audio design.

- [x] Materialise the accepted split-bus, direct-failback and neutral CamillaDSP profiles as reviewed static files.
- [x] Implement the CamillaDSP-backed EQ helper while preserving `status`, `set`, `live`, `bypass` and `neutral`.
- [ ] Implement shared shell helpers with clear error messages.
- [ ] Implement direct-route backup and validation.
- [ ] Implement EQ file installation.
- [ ] Implement persistent loopback setup.
- [ ] Implement the small route helper and route-state reporting.
- [ ] Implement systemd reload, enablement and service ordering.
- [ ] Implement saved Settings state application: active or bypassed.
- [ ] Implement automatic rollback on installation failure.
- [ ] Implement explicit uninstall.
- [ ] Implement verification and repair commands.
- [ ] Produce a concise installation report.

**Implementation checkpoint — 7 August 2026:**

- reviewed static split-bus ALSA profile committed;
- reviewed static direct alarm-bypass profile committed;
- reviewed neutral CamillaDSP profile committed with explicit `bypassed: false`;
- reviewed `snd_aloop` load and options profiles committed;
- focused profile contract tests committed;
- modular CamillaDSP EQ helper committed under `scripts/audio_eq_camilladsp/`;
- stable launcher retained at `scripts/a-clockwork-plex-audio-eq.py`;
- existing dashboard commands and JSON fields preserved;
- authoritative state selected as `/var/lib/a-clockwork-plex/split-bus/master-eq.json`;
- automatic music headroom implemented as the largest positive boost plus `0.5 dB` attenuation margin;
- native pipeline bypass implemented without route swapping or source-service restart;
- complete candidate YAML is validated before atomic replacement;
- live reload uses `SIGHUP` and requires the same CamillaDSP PID to remain healthy;
- prior state and YAML are restored if validation or reload fails;
- status distinguishes split-bus active, direct failback, direct rollback and offline;
- helper contract documented in [`camilladsp-eq-helper-contract.md`](camilladsp-eq-helper-contract.md);
- boot and repair paths are required to render the saved JSON state before CamillaDSP starts so a transient `live` drag value cannot persist across restart.

**Exit condition:** The scripts are readable, shell-checked and complete without touching the production Pi.

### Phase 3 — non-production tests

**Goal:** Prove file handling and rollback without changing live audio.

- [ ] Validate shell syntax.
- [ ] Validate ALSA configuration parsing in an isolated configuration root.
- [ ] Validate CamillaDSP configuration parsing.
- [ ] Validate systemd unit syntax.
- [ ] Exercise install against a temporary filesystem root.
- [ ] Exercise repeated install for idempotence.
- [ ] Exercise explicit uninstall.
- [ ] Inject one or more simple failures and verify restoration.
- [ ] Confirm no test command writes to production paths.

**Exit condition:** The installer and uninstaller produce the expected temporary-root state and exact rollback.

### Phase 4 — controlled bedroom-Pi installation

**Goal:** Install the EQ-capable backend once on the current appliance.

Before the physical run, the operator instructions must explicitly state:

- whether Plexamp must be playing or paused;
- what services and screen elements will temporarily disappear;
- whether audio will go silent;
- what success and rollback will look like.

The physical run should:

- [ ] verify the direct baseline;
- [ ] install the EQ-capable audio graph;
- [ ] start the managed services;
- [ ] restore Plexamp, AirPlay and dashboard availability;
- [ ] verify public PCMs and backend status;
- [ ] leave a direct-route rollback copy.

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

**Exit condition:** The installed backend and the redesigned Settings interface behave as one coherent feature.

### Phase 6 — failure, reboot and uninstall acceptance

**Goal:** Prove the appliance remains recoverable in normal ownership conditions.

- [ ] Controlled CamillaDSP failure returns to direct audio.
- [ ] Failback leaves Plexamp, AirPlay and dashboard usable.
- [ ] One controlled reboot restores the EQ-capable graph.
- [ ] Saved active/bypassed state survives reboot.
- [ ] Persistent `snd_aloop` state is verified after reboot.
- [ ] Explicit uninstall restores the accepted direct-route checksum.
- [ ] Direct audio remains usable after uninstall and reboot.
- [ ] Reinstall after uninstall succeeds.

**Exit condition:** Installation, reboot, failure recovery, uninstall and reinstall are all repeatable.

### Phase 7 — integration with the full Pi installer

**Goal:** Make SD-card replacement and fresh installation straightforward.

- [ ] Add the full-installer choice: Direct audio or EQ-capable audio.
- [ ] Make the EQ option call the tested standalone audio installer.
- [ ] Ensure a non-interactive audio-profile argument is available.
- [ ] Ensure the direct profile does not expose a misleading active EQ toggle.
- [ ] Ensure the EQ-capable profile applies saved active/bypassed state.
- [ ] Add fresh-Pi documentation and prerequisites.
- [ ] Add post-install verification output.

**Exit condition:** A fresh Pi can be built into either supported audio profile without manual reconstruction.

### Phase 8 — cleanup and release preparation

**Goal:** Reduce confusion and leave maintainable documentation.

- [ ] Preserve the final `stage-c-terminal-install-20260806` head as an archival reference after its Phase 1 evidence has been extracted.
- [ ] Delete the frozen `stage-c-terminal-install-20260806` branch after archival reference is recorded.
- [ ] Mark the experimental Stage C transactional installer as archived or non-production.
- [ ] Keep its evidence and lessons without presenting it as the supported install path.
- [ ] Update `README.md` with the audio-profile choices.
- [ ] Link the installer, verifier, repair and uninstall documentation.
- [ ] Update this roadmap with final results and any accepted deviations.
- [ ] Review PR #2 separately; do not merge without explicit approval.

**Exit condition:** The supported installation path is obvious to a future maintainer or to the owner rebuilding after an SD-card failure.

## Progress status

| Phase | State | Current note |
|---|---|---|
| 0. Roadmap and baseline | Complete | Direct audio recovered; roadmap published |
| 1. Artifact inventory | Complete | Exact audio contract and installation manifest published |
| 2. Standalone installer | In progress | Static profiles and CamillaDSP EQ helper complete; route helper and installer shell follow |
| 3. Non-production tests | Not started | Profile/helper contract tests exist; full installer tests follow Phase 2 |
| 4. Bedroom-Pi installation | Not started | One controlled run after Phase 3 |
| 5. Feature/interface acceptance | Not started | Includes bypass and locked controls |
| 6. Failure/reboot/uninstall | Not started | Required before full-installer integration |
| 7. Full installer integration | Not started | Reuse the standalone audio installer |
| 8. Cleanup/release preparation | Not started | Archive experimental path and remove frozen branch later |

## Communication and operating rules

To prevent repeated or ambiguous physical testing:

1. Every Pi command must state the required audio state first: **playing**, **paused** or **idle**.
2. Every mutating command must state which services or interface elements may disappear and whether silence is expected.
3. Validation and installation should be separate commands when practical.
4. Commands must not contain `exit`, `logout`, reboot, shutdown or process-wide kill operations that could close the active SSH session unexpectedly.
5. Do not rerun a failed installer while a retained failure or lock is present.
6. Prefer short, understandable commands over large one-line orchestration.
7. Do not repeat accepted physical tests unless a changed component invalidates their evidence.
8. After each milestone, update the progress table and provide the owner with:
   - what was completed;
   - what changed;
   - what remains;
   - the next concrete step.

## Acceptance summary

The EQ-capable audio feature is complete only when all of the following are true:

- the standalone installer can add the known-good split-bus design;
- Plexamp and AirPlay both work through the music EQ lane;
- scheduled alarms remain independent of Music Master and music EQ;
- the Settings switch uses bypass and preserves the user curve;
- bypassed controls are visibly locked;
- reboot restores the chosen state;
- failure returns to direct audio;
- uninstall restores the current direct baseline;
- the full installer can select and invoke the same tested audio component.

## Related documents

- [`eq-audio-installation-manifest.md`](eq-audio-installation-manifest.md)
- [`camilladsp-eq-helper-contract.md`](camilladsp-eq-helper-contract.md)
- [`production-eq-split-bus-design.md`](production-eq-split-bus-design.md)
- [`production-eq-stage-c-install-design.md`](production-eq-stage-c-install-design.md)
- [`bedroom-dsp-laboratory-results.md`](bedroom-dsp-laboratory-results.md)
- [`master-eq-testing.md`](master-eq-testing.md)
- [`direct-alarm-bypass-failback-result-2026-08-05.md`](direct-alarm-bypass-failback-result-2026-08-05.md)
- [`alarm-audio-testing.md`](alarm-audio-testing.md)

## Next action

Continue **Phase 2 — standalone installer implementation** with the small route helper, defaults file, restricted sudoers templates and three reviewed systemd units. The route/startup path must render the saved EQ JSON into the active CamillaDSP YAML before starting the DSP service, then publish one truthful route state for both the EQ helper and dashboard diagnostics.
