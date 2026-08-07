# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 4 controlled bedroom-Pi installation is complete; Phase 5 feature and interface acceptance is in progress  
**Started:** 7 August 2026  
**Last updated:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Production state:** EQ-capable split-bus audio installed and verified on the bedroom Pi; Plexamp audible through CamillaDSP; current test curve is neutral with Bass/Mid/Treble `0.0 dB`, automatic music headroom `0.0 dB`, EQ active/not bypassed  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has been selected, physically proven and is now installed on the bedroom Pi. The remaining work is to accept the feature behaviour, failure/reboot/uninstall behaviour, integrate the supported standalone component into the future full installer, and archive the superseded Stage C deployment machinery.

The supported path deliberately favours readable operations, explicit checks and straightforward rollback over the former Stage C authority/transaction framework.

## Settled design

### Audio graph

```text
Plexamp player volume -> Plexamp trim --\
                                         +-> Music Master -> music EQ/headroom --\
AirPlay sender volume -> AirPlay trim ---/                                      \
                                                                                  +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume -------------------------------/
```

The alarm lane bypasses Music Master and the music EQ, then joins the music lane before the final limiter.

### Install-time audio profiles

The future full installer will expose two audio capabilities:

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

## Accepted direct rollback baseline

The exact pre-EQ direct baseline remains the rollback reference:

- `plexamp.service`, `shairport-sync.service` and `a-clockwork-plex.service` active and enabled;
- active direct ALSA route SHA-256 `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
- audible Plexamp playback;
- no supported EQ installation committed.

After failed Phase 4 attempt #1, this baseline was explicitly restored and rechecked. A protected-file cleanup defect left two installer sudoers files behind; those files were verified against their exact installer-generated hashes before manual removal. The final check reported `POST_ROLLBACK_CLEANUP=PASS` with the exact direct checksum and all three application services active/enabled.

`snd_aloop` remained loaded after attempt #1 but was not part of that rollback-check failure and was deliberately left unchanged rather than assuming it was introduced by the attempt.

## Supported commands

```text
scripts/audio/preflight-eq.sh
scripts/audio/install-eq.sh
scripts/audio/uninstall-eq.sh
scripts/audio/verify-audio.sh
scripts/audio/repair-audio.sh
```

`preflight-eq.sh` is the read-only bedroom-Pi validation gate. The other four commands own the installed audio lifecycle.

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

- [x] Confirm direct audio is restored and audible.
- [x] Confirm the retained Stage C transaction and lock are absent.
- [x] Preserve failed Stage C evidence for diagnosis.
- [x] Stop expanding the experimental transactional installer.
- [x] Define DSP bypass rather than route swapping for everyday EQ disable.
- [x] Publish and maintain this roadmap.

**Exit condition:** Met.

### Phase 1 — known-good artifact inventory

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
- [x] Run the preflight on the bedroom Pi with the accepted CamillaDSP 4.1.3 binary.
- [x] Record successful real ALSA, CamillaDSP, systemd and sudoers parser results.
- [x] Record exact before/after production-state equality.

#### Repository-validation checkpoint

GitHub Actions run **31145374614** produced **1,346/1,346 passing tests**, including all six dedicated preflight safety tests. Python compilation, JavaScript/page wiring and shell-syntax checks passed.

#### Bedroom-Pi read-only validation checkpoint — PASS

The **read-only bedroom-Pi validation gate** ran from exact source commit `9757006c2f1987b2a4c93a88f5a5bbd7cc3dc534` while normal direct Plexamp audio remained active.

Results:

- exact direct baseline — PASS;
- CamillaDSP 4.1.3 binary/version/SHA — PASS;
- split route isolated `aplay -L` parse — PASS;
- direct route isolated `aplay -L` parse — PASS;
- reviewed and rendered neutral CamillaDSP `--check` — PASS;
- restricted sudoers `visudo` validation — PASS;
- three units in private systemd model — PASS;
- exact before/after production-state equality — PASS;
- final marker `EQ_AUDIO_READ_ONLY_PREFLIGHT=PASS`.

Evidence remains at `/var/tmp/a-clockwork-plex-eq-preflight.KztFun`.

No production file, route, module, mixer control, PCM or service was changed. **No bedroom-Pi installation** was performed by the preflight.

**Exit condition:** Met.

### Phase 4 — controlled bedroom-Pi installation

**Goal:** Install the EQ-capable backend once on the current appliance.

#### Attempt #1 — audio graph PASS; installer bookkeeping FAIL; direct rollback PASS

Source commit: `9757006c2f1987b2a4c93a88f5a5bbd7cc3dc534`.

The live appliance reached healthy `split-bus-active`, CamillaDSP was running, loopback matched the accepted contract, all three application services returned and manual Plexamp playback was audible. Installation then failed because protected `/etc/sudoers.d` files were inspected through an unprivileged existence/hash path.

Manifest/verifier inspection was corrected in commit `c3682ac9727d1373ab3813c93fd412531f861af3`; rollback removal of protected files was corrected in commit `3c17b7fba115e95e7e419c48edbfe8cc3ee512f2`. GitHub Actions run **31154999148** passed the latter correction and regression test.

The direct baseline and protected-file cleanup were then rechecked manually with `POST_ROLLBACK_CLEANUP=PASS`.

#### Attempt #2 — PASS

Source commit: `3c17b7fba115e95e7e419c48edbfe8cc3ee512f2`.

The retry began with Plexamp actively playing and audible. During the controlled handover:

- Plexamp audio silenced at the same time as the dashboard/interface disappeared;
- Plexamp, AirPlay and dashboard services were intentionally quiesced for DAC handover;
- the interface returned with Plexamp paused;
- manual Play then produced audible Plexamp audio through the installed split-bus route.

Installer/live-verifier results:

- `ok: true`;
- effective mode `split-bus-active`;
- active route matches split profile;
- active split-route SHA-256 `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`;
- active CamillaDSP configuration SHA-256 `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`;
- CamillaDSP running with live PID `1543417` for this observed run;
- `snd_aloop` present and correct: index `7`, id `ACP_Loopback`, `pcm_substreams=2`, `pcm_notify=1`;
- `plexamp.service` active/enabled;
- `shairport-sync.service` active/enabled;
- `a-clockwork-plex.service` active/enabled;
- `a-clockwork-plex-audio-route.service` active/enabled;
- `a-clockwork-plex-camilladsp.service` active/enabled;
- failback service enabled and inactive during healthy split-bus operation;
- installed marker present;
- installer verifier reported `EQ-capable audio verification passed.`;
- installer reported `EQ-capable audio profile installed successfully.`;
- audible Plexamp playback manually confirmed after pressing Play.

- [x] Recheck accepted direct baseline after attempt #1.
- [x] Capture the exact pre-EQ backup for the corrected retry.
- [x] Install and start the EQ-capable graph from corrected commit `3c17b7fba115e95e7e419c48edbfe8cc3ee512f2`.
- [x] Restore Plexamp, AirPlay and dashboard availability.
- [x] Verify public route/backend/service state through the live installer verifier.
- [x] Verify audible Plexamp playback through the persistent split-bus route.
- [x] Record both live attempts and their outcomes.

**Exit condition:** Met. The corrected installer reports success and Plexamp is audible through the persistent split-bus route.

### Phase 5 — feature and interface acceptance

**Goal:** Test the installed user-facing feature rather than the deployment framework.

- [x] Plexamp plays audibly through the EQ-capable split-bus route.
- [x] Verify installed EQ-helper backend state is available, configured and truthful.
- [ ] Confirm the dashboard/API surfaces the same truthful EQ state.
- [x] Bass control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] Mid control is audibly distinct, persists the requested value and reports the applied value correctly.
- [ ] Treble control is audibly distinct and reported correctly.
- [ ] AirPlay plays through the same music EQ lane.
- [ ] AirPlay/Plexamp takeover and return still work.
- [ ] EQ disable uses bypass without route remapping.
- [ ] Stored values survive bypass and return when enabled.
- [ ] Controls are greyed and locked while bypassed.
- [ ] Return to neutral sets all bands to `0 dB`.
- [ ] Music Master at 0% silences Plexamp and AirPlay.
- [ ] Music Master at 0% does not reduce a real scheduled alarm.
- [ ] EQ and bypass do not alter alarm tone or level.
- [ ] Maximum Alarm Volume still caps scheduled alarms.
- [ ] The final limiter protects combined music and alarm playback.
- [ ] NFC playback and dashboard controls still work.

#### Initial EQ status — PASS

With Plexamp actively playing, `a-clockwork-plex-audio-eq status` reported:

- `ok: true`;
- installed/configured/available all `true`;
- backend `camilladsp`;
- backend/route mode `split-bus-active`;
- selected route `split-bus-selected`;
- EQ not bypassed;
- Bass, Mid and Treble stored/applied/effective values all exactly `0.0 dB`;
- automatic headroom `0.0 dB`;
- final limiter `-1.0 dB`;
- CamillaDSP PID `1543417`.

This exactly matched the expected neutral post-install state.

#### Bass live EQ A/B — PASS

With the same Plexamp stream active, Bass was first changed from `0.0 dB` to `+6.0 dB` using the installed helper.

The returned state reported Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, automatic music headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual observation confirmed continuous playback, a lower overall level from protective headroom and a more bass-heavy tonal balance.

Bass was then moved directly from `+6.0 dB` to `-6.0 dB`, creating a 12 dB relative swing while the same track continued playing. The returned state reported Bass stored/applied/effective `-6.0 dB`, Mid/Treble `0.0 dB`, backend still `split-bus-active`, unchanged PID `1543417`, active config SHA `6022cac742227c72e41a71fb6b530a05c3848ade38580184d0cbfcdfbb997ec0`, headroom returned to `0.0 dB` and final limiter remained `-1.0 dB`. Manual observation confirmed the level came back up and the music became clearly thinner/less bass-heavy.

Bass was then returned to neutral `0.0 dB`. The helper returned the original neutral config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, headroom `0.0 dB`, unchanged PID `1543417`, and manual listening confirmed the tonal balance sounded normal again.

#### Mid live EQ A/B — PASS

Starting from the confirmed neutral curve, Mid was changed to `+6.0 dB`. The helper reported:

- Mid stored/applied/effective `+6.0 dB`;
- Bass and Treble exactly `0.0 dB`;
- persisted `true`;
- backend remained `split-bus-active`;
- CamillaDSP PID remained exactly `1543417`;
- active CamillaDSP config SHA `833f54aa09099c56543d12a70bab202862c3cc60e06f9dd04146ab698dd6addc`;
- automatic music headroom `-6.5 dB`;
- final limiter `-1.0 dB`.

Manual observation: playback remained continuous and the tonal balance became strongly mid-forward, perceived as less bassy and less trebley.

Mid was then moved directly from `+6.0 dB` to `-6.0 dB`, again creating a 12 dB relative swing. The helper reported:

- Mid stored/applied/effective `-6.0 dB`;
- Bass and Treble exactly `0.0 dB`;
- persisted `true`;
- backend still `split-bus-active`;
- CamillaDSP PID still exactly `1543417`;
- active CamillaDSP config SHA `081875711e1a874ab6a5097bf826d7a270b4c2013aa3583038f4721914f3d7ce`;
- automatic music headroom returned to `0.0 dB`;
- final limiter remained `-1.0 dB`.

Manual observation: playback remained uninterrupted and the sound became strongly scooped, with bass and treble relatively prominent and vocals clearly thinner/recessed. This conclusively accepts the Mid control both audibly and from the reported backend state.

Mid was then returned from `-6.0 dB` to neutral `0.0 dB`. The helper reported Bass/Mid/Treble all stored/applied/effective `0.0 dB`, headroom `0.0 dB`, backend still `split-bus-active`, the original neutral CamillaDSP config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, and unchanged CamillaDSP PID `1543417`. Manual listening confirmed the tonal balance returned to normal.

**Exit condition:** The installed backend and redesigned Settings/interface behave as one coherent feature.

### Phase 6 — failure, reboot and uninstall acceptance

- [ ] Controlled CamillaDSP failure returns to usable direct audio.
- [ ] Failback leaves Plexamp, AirPlay and dashboard usable.
- [ ] One controlled reboot restores the EQ-capable graph.
- [ ] Saved active/bypassed state survives reboot.
- [ ] Persistent `snd_aloop` state is verified after reboot.
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
| 3. Non-production/read-only validation | Complete | Real Pi preflight PASS; exact before/after production-state equality |
| 4. Bedroom-Pi installation | Complete | Attempt #2 installed split-bus successfully; live verifier PASS; audible Plexamp confirmed |
| 5. Feature/interface acceptance | In progress | Bass and Mid A/B accepted and both returned to neutral; Treble test next |
| 6. Failure/reboot/uninstall acceptance | Not started | Follows feature acceptance |
| 7. Full-installer integration | Not started | Reuses the accepted standalone component |
| 8. Cleanup/release preparation | Not started | Includes Stage C archival and documentation cleanup |

## Immediate next action

Continue Phase 5 while **Plexamp remains actively playing and audible**:

1. test Treble from the confirmed neutral baseline using the same bounded `+6.0 dB` / `-6.0 dB` A/B method;
2. confirm playback remains uninterrupted, the CamillaDSP PID remains unchanged and automatic headroom behaves as expected;
3. return Treble to neutral;
4. after all three bands are accepted, test bypass/restore semantics and the UI lock/grey state;
5. proceed to AirPlay handover and alarm-isolation tests only after the basic music EQ path is accepted.

Do not begin reboot, intentional backend failure or uninstall testing until Phase 5 is complete.

## Roadmap maintenance discipline

This file is part of the implementation workflow, not an occasional retrospective document.

- Any commit that materially completes, blocks or changes a roadmap item must update this file in the same change or immediately afterward.
- A phase must not be marked complete until its exit condition passes.
- Failed gates must be recorded with exact scope and result.
- Any physical Pi change must record route, checksum, relevant service state and rollback outcome.
- The roadmap must be checked before project status is reported in chat.
- PR #2 remains Draft and must not be merged without explicit approval.

The owner should not need to prompt for routine roadmap updates as development progresses.
