# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 4 controlled bedroom-Pi installation is complete; Phase 5 feature and interface acceptance is in progress  
**Started:** 7 August 2026  
**Last updated:** 7 August 2026  
**Target branch:** `feature/alarm-engine`  
**Production state:** EQ-capable split-bus audio installed and verified on the bedroom Pi; Plexamp remains audible through CamillaDSP; current saved curve has Bass `+6.0 dB`, Mid/Treble `0.0 dB`; EQ is currently bypassed from the live mixer overlay so applied/effective bands are neutral and headroom is `0.0 dB`; helper-level bypass/restore, dashboard/API truthfulness and mixer-overlay bypass/lock behaviour are accepted; the separate Settings → Audio → Equaliser page exposed a duplicate staged-EQ authority and its live-runtime unification fix is committed but still requires physical Pi deployment/acceptance  
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
- [x] Confirm the dashboard/API surfaces the same truthful EQ state.
- [x] Bass control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] Mid control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] Treble control is audibly distinct, persists the requested value and reports the applied value correctly.
- [ ] AirPlay plays through the same music EQ lane.
- [ ] AirPlay/Plexamp takeover and return still work.
- [x] EQ disable uses bypass without route remapping.
- [x] Stored values survive bypass and return when enabled.
- [ ] Controls are greyed and locked while bypassed. *(Mixer overlay PASS; Settings subpage re-test pending authority fix deployment.)*
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

Starting from the confirmed neutral curve, Mid was changed to `+6.0 dB`. The helper reported Mid stored/applied/effective `+6.0 dB`, Bass/Treble `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, config SHA `833f54aa09099c56543d12a70bab202862c3cc60e06f9dd04146ab698dd6addc`, headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual observation confirmed continuous playback and a strongly mid-forward tonal balance.

Mid was then moved directly to `-6.0 dB`. The helper reported Mid stored/applied/effective `-6.0 dB`, Bass/Treble `0.0 dB`, persisted `true`, unchanged backend/PID, config SHA `081875711e1a874ab6a5097bf826d7a270b4c2013aa3583038f4721914f3d7ce`, headroom `0.0 dB` and final limiter `-1.0 dB`. Manual observation confirmed a strongly scooped sound with bass/treble relatively prominent and vocals clearly thinner/recessed.

Mid was then returned to neutral `0.0 dB`, restoring the original neutral config SHA, `0.0 dB` headroom and normal tonal balance with PID still `1543417`.

#### Treble live EQ A/B — PASS

Starting from the confirmed neutral curve, Treble was changed to `+6.0 dB`. The helper reported Treble stored/applied/effective `+6.0 dB`, Bass/Mid `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, config SHA `0b9abd96aef92c132f9d11dfa8c400bb09cb3e83e520143b5f451b7a9e523039`, headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual listening clearly confirmed boosted treble/brightness with playback remaining continuous.

Treble was then moved directly from `+6.0 dB` to `-6.0 dB`, creating the same 12 dB relative A/B swing used for Bass and Mid. The helper reported Treble stored/applied/effective `-6.0 dB`, Bass/Mid `0.0 dB`, persisted `true`, backend still `split-bus-active`, CamillaDSP PID still `1543417`, config SHA `d6b941ac78d1460781672b956e0929da2a1fbd48d1f9ec4e145061ac221475da`, headroom returned to `0.0 dB` and final limiter remained `-1.0 dB`. Manual listening confirmed the track became markedly darker, conclusively accepting the Treble control both audibly and from the reported backend state.

Treble was then returned from `-6.0 dB` to neutral `0.0 dB`. The helper reported Bass/Mid/Treble all stored/applied/effective `0.0 dB`, headroom `0.0 dB`, backend still `split-bus-active`, original neutral config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, and unchanged CamillaDSP PID `1543417`. Manual listening confirmed the tonal balance returned to neutral. This established the accepted neutral EQ baseline before bypass testing.

#### Everyday bypass/restore — PASS

A deliberately obvious Bass `+6.0 dB` curve was reapplied while Plexamp remained active and audible. Before bypass the helper reported Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2`, headroom `-6.5 dB`, route `split-bus-active` and CamillaDSP PID `1543417`; manual listening confirmed the expected very bass-heavy sound.

`a-clockwork-plex-audio-eq bypass on` then reported `bypassed: true` while preserving Bass `stored_db=6.0` and `db=6.0`, but changing Bass `applied_db` and `effective_db` to `0.0 dB`. Headroom returned to `0.0 dB`, config SHA changed to `8e3216a59b7cb69441d45a5e788399b24ac61ee44f6fb491fd22f591e6564114`, route remained `split-bus-active`, CamillaDSP PID remained `1543417`, playback remained continuous and manual listening confirmed the sound became neutral.

`a-clockwork-plex-audio-eq bypass off` restored Bass stored/applied/effective `+6.0 dB`, config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2` and headroom `-6.5 dB` while the route and CamillaDSP PID remained unchanged. Manual listening immediately confirmed the heavy Bass curve returned.

This accepts both required runtime semantics: everyday EQ disable is a DSP bypass rather than route remapping, and stored values survive bypass and return when EQ is re-enabled.

#### Dashboard API state — PASS

With the live Bass `+6.0 dB` curve active, the first `GET /api/audio/eq` correctly surfaced all functional EQ values but exposed one presentation inconsistency: the dashboard wrapper replaced helper `backend_state=split-bus-active` with generic `active`, even though `route_mode` remained correctly detailed. The underlying backend was healthy; `MasterEqualizer.status()` was overwriting a truthful helper field after merging the helper payload.

Commit `44d86a7cbdbbc6bdff14f8c471703d91d82821a1` changed the wrapper so an explicit helper `backend_state` is preserved, and commit `28fe66d49f6b6145227dd58cf0cd794dbc5a3727` added the regression assertion. GitHub Actions run **31219132479** / **#2703** passed.

The bedroom Pi checkout was deliberately not wholesale-updated because it was 331 commits behind the branch and had an unrelated local modification to `scripts/launch-dashboard-kiosk.sh`. Only `app/audio_eq.py` was restored from the fetched branch version. Restarting only `a-clockwork-plex.service` left Plexamp audio uninterrupted.

The subsequent live `GET /api/audio/eq` reported backend `camilladsp`, `backend_state=split-bus-active`, `route_mode=split-bus-active`, selected route `split-bus-selected`, Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, `bypassed=false`, config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2`, CamillaDSP PID `1543417`, headroom `-6.5 dB`, final limiter `-1.0 dB`, and overall `ok=true`. This accepts dashboard/API truthfulness and confirms a dashboard-only restart does not disturb the live audio graph.

#### Mixer overlay bypass/lock — PASS; duplicate Settings EQ authority found

The accepted frontend bypass-lock/copy correction was deployed by restoring only `app/static/js/audio-eq.js` from the fetched branch. The diff contained only the expected music-only/alarm-bypass copy change plus the `controlsEnabled = available && !bypassed` lock logic; audio continued uninterrupted during the static-file deployment.

After a hard refresh, the **audio mixer overlay** showed the live Bass `+6.0 dB`, Mid/Treble `0.0 dB` curve and the corrected Plexamp/AirPlay music-only wording. Pressing the overlay Bypass control successfully entered bypass and the three EQ knobs became greyed/locked as designed. The immediate API check reported:

- `bypassed=true`;
- Bass `db=6.0`, `stored_db=6.0`, `applied_db=0.0`, `effective_db=0.0`;
- Mid/Treble stored/applied/effective `0.0 dB`;
- bypass config SHA `8e3216a59b7cb69441d45a5e788399b24ac61ee44f6fb491fd22f591e6564114`;
- headroom `0.0 dB`;
- route/backend `split-bus-active`;
- CamillaDSP PID still `1543417`;
- `ok=true`.

This accepts the mixer-overlay user-facing bypass/lock path.

The same physical check exposed a separate defect in **Settings → Audio → Equaliser**: that page still showed all three bands at `0 dB` with “Equaliser enabled” unticked while the live overlay/backend held saved Bass `+6 dB`. Source review found two competing EQ authorities:

1. the old unified Settings page used staged `audio.eq.enabled` / `audio.eq.bands.*` values from `config.audio.eq`;
2. the production EQ controls used `/api/audio/eq` and CamillaDSP live state.

Worse, `eq_model_from_status()` preferred the saved config block over live status, and the unified Settings transaction could apply that stale staged model during Save. This was the exact kind of duplicate authority the audio redesign is intended to eliminate.

The correction is now committed:

- `4d24ca5fee0839d9094e8cc2cb93f475fc4cea52` — the existing Settings Equaliser subpage is replaced at runtime by the same live EQ surface used by the production controls; stale staged controls are removed from the DOM; the live EQ domain is supplied to unified Settings so normal saves cannot submit stale zero values;
- `cacd0b73684fdc980ae04c67ec54ea0a49b0ed31` — frontend authority regression contract;
- `083bea77618d39041ad8fefb35b0204349020c5d` — unified Settings now always derives its EQ view from live backend status, no longer applies EQ changes during transactional Save, advertises runtime rather than staged EQ control, and removes legacy `config.audio.eq` on the next Settings save;
- `2df281bb8572955fd734b8dd2fc4979792715714` — backend runtime-authority regression coverage;
- `b56e51f2fa35be949698528b312708f47f692ffe` — fresh example configuration no longer defines the obsolete staged EQ block.

Physical Settings-page acceptance remains open until the new JavaScript and `settings_unified.py` are deployed to the bedroom Pi, the dashboard is restarted/refreshed, and the Equaliser subpage proves it mirrors the current bypassed saved Bass `+6 dB` state and locks its sliders.

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
| 5. Feature/interface acceptance | In progress | Three-band A/B, helper bypass/restore, dashboard API and mixer-overlay bypass/lock accepted; duplicate Settings EQ authority removed in source and awaiting Pi acceptance |
| 6. Failure/reboot/uninstall acceptance | Not started | Follows feature acceptance |
| 7. Full-installer integration | Not started | Reuses the accepted standalone component |
| 8. Cleanup/release preparation | Not started | Includes Stage C archival and documentation cleanup |

## Immediate next action

Continue Phase 5 while **Plexamp remains actively playing and audible** and leave the current EQ state **bypassed with saved Bass `+6.0 dB`**:

1. allow CI to validate the live-Settings authority cleanup and regression contracts;
2. deploy only the accepted `app/static/js/audio-eq.js` and `app/settings_unified.py` changes to the bedroom Pi without overwriting the unrelated local kiosk-launcher modification;
3. restart only `a-clockwork-plex.service`, hard-refresh the dashboard, and open Settings → Audio → Equaliser;
4. confirm that subpage now shows the live bypassed state: Bass saved `+6.0 dB`, Mid/Treble `0.0 dB`, status Bypassed, Restore EQ action, and all three sliders greyed/locked;
5. use **Restore EQ** from the Settings subpage and confirm the heavy Bass curve returns with route/PID unchanged;
6. then test the separate `neutral` action explicitly so its reset semantics are accepted;
7. proceed to AirPlay handover, Music Master and alarm-isolation tests.

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