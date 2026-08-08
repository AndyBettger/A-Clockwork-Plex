# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 4 controlled bedroom-Pi installation is complete; Phase 5 feature and interface acceptance is in progress  
**Started:** 7 August 2026  
**Last updated:** 8 August 2026  
**Target branch:** `feature/alarm-engine`  
**Production state:** EQ-capable split-bus audio is installed and verified on the bedroom Pi; AirPlay is physically proven through the same CamillaDSP music-EQ lane and correctly pauses an already-playing Plexamp session on takeover; Neutral, helper/dashboard bypass/restore, mixer-overlay lock, Settings EQ bypass/lock/restore and Settings → Display → Motion are physically accepted. The replacement **fixed `-6.5 dB` music-lane reserve is now fully physically accepted** on the live Pi: Plexamp remained continuous through deployment and both Restore/Bypass directions, the saved Bass `+6 dB` curve changes tone without the previous broad `6.5 dB` level jump, the route remains `split-bus-active`, and CamillaDSP remains on PID `1543417`. Music Master at `100%` has also been physically accepted as providing ample maximum listening level with the permanent reserve; with the test amplifier gain increased to a comfortable fixed point, normal listening is currently around Music Master `79%`. The live EQ state is currently bypassed with saved Bass `+6 dB`, applied/effective Bass `0 dB` and fixed headroom `-6.5 dB`.  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has been selected, physically proven and is now installed on the bedroom Pi. The remaining work is to accept the refined feature behaviour, failure/reboot/uninstall behaviour, integrate the supported standalone component into the future full installer, and archive the superseded Stage C deployment machinery.

The supported path deliberately favours readable operations, explicit checks and straightforward rollback over the former Stage C authority/transaction framework.

## Settled design

### Audio graph

```text
Plexamp player volume -> Plexamp trim --\
                                         +-> Music Master -> fixed EQ reserve -> tone controls --\
AirPlay sender volume -> AirPlay trim ---/                                                      \
                                                                                                  +-> final limiter -> DAC
Alarm start/target/fade -> Maximum Alarm Volume -----------------------------------------------/
```

The alarm lane bypasses Music Master, the permanent music-EQ reserve and the music tone controls, then joins the music lane before the final limiter.

### Install-time audio profiles

The future full installer will expose two audio capabilities:

- **Direct audio** — Plexamp, AirPlay and alarm playback without CamillaDSP EQ.
- **EQ-capable audio** — the split-bus route with CamillaDSP, music-only EQ and direct alarm bypass.

This is an installation choice, not the everyday EQ on/off setting.

### Runtime EQ enable and disable

When EQ-capable audio is installed, Plexamp and AirPlay stay mapped to the split-bus PCMs whether EQ is enabled or bypassed.

- **EQ enabled:** stored Bass, Mid and Treble values are applied after the fixed music-lane reserve.
- **EQ disabled:** CamillaDSP bypasses only the Bass/Mid/Treble tone stage while preserving the stored curve and fixed music-lane reserve.
- **Return to neutral:** deliberately sets all three bands to `0 dB` while leaving the fixed reserve in place.

Everyday bypass must not remap ALSA devices, restart source services or select another route. While bypassed, the Settings and drawer controls remain visible but are greyed and locked.

#### Fixed music-lane headroom refinement — physical PASS

Physical Plexamp and AirPlay A/B tests exposed a usability problem with the original dynamic-headroom implementation: a positive tone boost added attenuation at the same time as it changed tonal balance, and bypass removed that attenuation at the same time as it flattened the EQ. The result was a conspicuous loudness jump whenever a positive tone control was introduced or bypassed.

The accepted replacement design reserves the worst-case EQ headroom permanently on the music lane:

```text
Plexamp / AirPlay
        ↓
Music Master
        ↓
fixed -6.5 dB EQ preamp/headroom reserve   (always active)
        ↓
Bass / Mid / Treble                         (bypassable)
        ↓
mix with alarm
        ↓
-1 dB final limiter
```

The `-6.5 dB` value is the existing maximum `+6 dB` band boost plus the existing `0.5 dB` safety margin. Under this model Neutral and Bypass stay at the same base level; bypass defeats only Bass/Mid/Treble and does not remove the fixed reserve. This is the digital equivalent of provisioning tone-control headroom rather than changing the apparent master level whenever a tone control is moved.

The trade-off is that the EQ-capable music lane has `6.5 dB` less maximum digital level even at neutral. The planned bedroom system uses a separate analogue amplifier, so normal physical listening gain can be established there while preserving conservative digital headroom. Physical testing has now confirmed that Music Master at `100%` still provides ample usable output with the reserve in place, so this trade-off is accepted.

Implementation checkpoint:

- `scripts/audio_eq_camilladsp/model.py` now defines `FIXED_MUSIC_HEADROOM_DB = -6.5` and always renders that reserve on music channels 0/1;
- the CamillaDSP pipeline now has a permanently enabled `[headroom]` filter followed by a separately bypassable `[bass, mid, treble]` filter stage;
- bypass preserves the actual saved tone-filter gains in the configuration instead of simulating bypass by rewriting them to zero;
- `runtime.py` reports `headroom_db=-6.5` whenever the EQ-capable backend is actually available, including Neutral and Bypass, but reports `0.0` when the backend is unavailable/direct-failback because the reserve is then physically absent;
- the static installer neutral profile mirrors the same pipeline so future install/repair does not regress to the dynamic model;
- dedicated tests protect fixed headroom at neutral/boost/cut/bypass, real tone-stage bypass, alarm-after-music processing order and truthful direct-failback reporting.

Source head `7555b8186355cddc214fe5e08908fa79ff8fd6c4` passed GitHub Actions **#2767 / run 31234727079**: compilation PASS, JavaScript/page-wiring/shell-syntax PASS, and **1,353/1,353 unit tests PASS**.

The live bedroom Pi then received only `__init__.py`, `model.py` and `runtime.py` into the installed helper package. With Plexamp actively audible, EQ already bypassed and saved Bass `+6.0 dB`, `a-clockwork-plex-audio-eq bypass on` reloaded the new graph in place. Playback remained continuous and the expected one-off broad level reduction was heard as the permanent reserve entered the music path. The helper reported `headroom_db=-6.5`, `bypassed=true`, saved Bass `+6.0 dB`, Bass applied/effective `0.0 dB`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active`, final limiter `-1.0 dB`, and unchanged CamillaDSP PID `1543417`.

The saved curve was then restored in place. Playback remained continuous and the Bass boost became immediately and more clearly audible because the overall music level no longer moved with it. The helper reported Bass stored/applied/effective `+6.0 dB`, `bypassed=false`, fixed `headroom_db=-6.5`, config SHA `2ee27d5fb13c0a087704f197cb0c3420cb453cc15f94c9fa5902a40584ac600f`, route/backend `split-bus-active`, final limiter `-1.0 dB`, and unchanged PID `1543417`.

Bypass was then re-enabled. The Bass boost disappeared and the music returned to a neutral tonal balance without the old broad-volume rise. The helper returned to `bypassed=true`, saved Bass `+6.0 dB`, Bass applied/effective `0.0 dB`, fixed `headroom_db=-6.5`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active` and PID `1543417`.

This physically accepts the fixed-headroom refinement in both directions: the tone stage changes tonal balance while the permanent reserve remains stable, so everyday EQ A/B no longer introduces the distracting repeated `6.5 dB` master-level jump.

### Alarm loudness and speaker-safety acceptance

The alarm lane intentionally bypasses the music-lane `-6.5 dB` reserve as well as Music Master and the tone controls. That independence is required, but it means alarm loudness must be calibrated deliberately rather than inferred from music loudness.

The Phase 5 alarm test is therefore a **stepped calibration**, not a maximum-output blast test:

1. use the real scheduled-alarm path rather than a sustained speaker-stress tone;
2. set the physical amplifier conservatively;
3. begin Maximum Alarm Volume around `20–25%`;
4. increase only in controlled steps while listening for clean, unstressed reproduction;
5. stop before any audible distortion, knocking/bottoming, harshness or cabinet/driver distress;
6. establish a sensible software maximum well below any questionable level;
7. repeat final Maximum Alarm Volume calibration when the intended Sony amplifier and Wharfedale speakers replace the present test system.

The final `-1 dB` limiter protects against digital clipping at the combined output. It cannot protect a loudspeaker from excessive analogue amplifier power, so it is not a substitute for this physical calibration. There will be **no initial 100% alarm-output test**.

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
│   ├── audio.sh
│   ├── common.sh
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

The installed EQ-helper package lives at:

```text
/usr/local/lib/a-clockwork-plex/audio-eq/audio_eq_camilladsp/
```

and the stable launcher remains `/usr/local/bin/a-clockwork-plex-audio-eq`.

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
- active CamillaDSP configuration SHA-256 `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae` for the original dynamic-headroom neutral profile;
- CamillaDSP running with live PID `1543417` for the observed acceptance run;
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
- [x] AirPlay plays through the same music EQ lane.
- [ ] AirPlay/Plexamp takeover and return still work. *(Plexamp → AirPlay takeover PASS; reverse AirPlay → Plexamp takeover/return still open.)*
- [x] EQ disable uses bypass without route remapping.
- [x] Stored values survive bypass and return when enabled.
- [x] Controls are greyed and locked while bypassed. *(Mixer overlay and Settings subpage physical PASS.)*
- [x] Return to neutral sets all bands to `0 dB`.
- [x] Fixed `-6.5 dB` music-lane pre-EQ reserve is physically accepted for level consistency. *(Source/CI, surgical deployment and Restore/Bypass A/B all PASS.)*
- [x] Music Master at 100% remains adequately loud with the permanent reserve.
- [ ] Music Master at 0% silences Plexamp and AirPlay.
- [ ] Music Master at 0% does not reduce a real scheduled alarm.
- [ ] EQ and bypass do not alter alarm tone or level.
- [ ] Maximum Alarm Volume still caps scheduled alarms.
- [ ] Safe stepped Maximum Alarm Volume calibration completed on the current test system.
- [ ] Final Maximum Alarm Volume recalibrated on the intended Sony amplifier / Wharfedale speaker system.
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
- original dynamic headroom `0.0 dB`;
- final limiter `-1.0 dB`;
- CamillaDSP PID `1543417`.

This exactly matched the expected original neutral post-install state.

#### Bass live EQ A/B — PASS

With the same Plexamp stream active, Bass was first changed from `0.0 dB` to `+6.0 dB` using the installed helper.

The returned state reported Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, original automatic music headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual observation confirmed continuous playback, a lower overall level from protective headroom and a more bass-heavy tonal balance.

Bass was then moved directly from `+6.0 dB` to `-6.0 dB`, creating a 12 dB relative swing while the same track continued playing. The returned state reported Bass stored/applied/effective `-6.0 dB`, Mid/Treble `0.0 dB`, backend still `split-bus-active`, unchanged PID `1543417`, active config SHA `6022cac742227c72e41a71fb6b530a05c3848ade38580184d0cbfcdfbb997ec0`, original headroom returned to `0.0 dB` and final limiter remained `-1.0 dB`. Manual observation confirmed the level came back up and the music became clearly thinner/less bass-heavy.

Bass was then returned to neutral `0.0 dB`. The original helper returned neutral config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, original headroom `0.0 dB`, unchanged PID `1543417`, and manual listening confirmed the tonal balance sounded normal again.

#### Mid live EQ A/B — PASS

Starting from the confirmed neutral curve, Mid was changed to `+6.0 dB`. The helper reported Mid stored/applied/effective `+6.0 dB`, Bass/Treble `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, config SHA `833f54aa09099c56543d12a70bab202862c3cc60e06f9dd04146ab698dd6addc`, original headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual observation confirmed continuous playback and a strongly mid-forward tonal balance.

Mid was then moved directly to `-6.0 dB`. The helper reported Mid stored/applied/effective `-6.0 dB`, Bass/Treble `0.0 dB`, persisted `true`, unchanged backend/PID, config SHA `081875711e1a874ab6a5097bf826d7a270b4c2013aa3583038f4721914f3d7ce`, original headroom `0.0 dB` and final limiter `-1.0 dB`. Manual observation confirmed a strongly scooped sound with bass/treble relatively prominent and vocals clearly thinner/recessed.

Mid was then returned to neutral `0.0 dB`, restoring the original neutral config SHA, `0.0 dB` headroom and normal tonal balance with PID still `1543417`.

#### Treble live EQ A/B — PASS

Starting from the confirmed neutral curve, Treble was changed to `+6.0 dB`. The helper reported Treble stored/applied/effective `+6.0 dB`, Bass/Mid `0.0 dB`, persisted `true`, backend `split-bus-active`, unchanged CamillaDSP PID `1543417`, config SHA `0b9abd96aef92c132f9d11dfa8c400bb09cb3e83e520143b5f451b7a9e523039`, original headroom `-6.5 dB` and final limiter `-1.0 dB`. Manual listening clearly confirmed boosted treble/brightness with playback remaining continuous.

Treble was then moved directly from `+6.0 dB` to `-6.0 dB`, creating the same 12 dB relative A/B swing used for Bass and Mid. The helper reported Treble stored/applied/effective `-6.0 dB`, Bass/Mid `0.0 dB`, persisted `true`, backend still `split-bus-active`, CamillaDSP PID still `1543417`, config SHA `d6b941ac78d1460781672b956e0929da2a1fbd48d1f9ec4e145061ac221475da`, original headroom returned to `0.0 dB` and final limiter remained `-1.0 dB`. Manual listening confirmed the track became markedly darker, conclusively accepting the Treble control both audibly and from the reported backend state.

Treble was then returned from `-6.0 dB` to neutral `0.0 dB`. The helper reported Bass/Mid/Treble all stored/applied/effective `0.0 dB`, original headroom `0.0 dB`, backend still `split-bus-active`, original neutral config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, and unchanged CamillaDSP PID `1543417`. Manual listening confirmed the tonal balance returned to neutral.

#### Everyday bypass/restore — PASS under original dynamic-headroom implementation

A deliberately obvious Bass `+6.0 dB` curve was reapplied while Plexamp remained active and audible. Before bypass the helper reported Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2`, original headroom `-6.5 dB`, route `split-bus-active` and CamillaDSP PID `1543417`; manual listening confirmed the expected very bass-heavy sound.

`a-clockwork-plex-audio-eq bypass on` then reported `bypassed: true` while preserving Bass `stored_db=6.0` and `db=6.0`, but changing Bass `applied_db` and `effective_db` to `0.0 dB`. Under the original implementation headroom returned to `0.0 dB`, config SHA changed to `8e3216a59b7cb69441d45a5e788399b24ac61ee44f6fb491fd22f591e6564114`, route remained `split-bus-active`, CamillaDSP PID remained `1543417`, playback remained continuous and manual listening confirmed the sound became neutral.

`a-clockwork-plex-audio-eq bypass off` restored Bass stored/applied/effective `+6.0 dB`, config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2` and original headroom `-6.5 dB` while the route and CamillaDSP PID remained unchanged. Manual listening immediately confirmed the heavy Bass curve returned.

This accepted the required runtime semantics that everyday EQ disable is a DSP operation rather than route remapping and stored values survive bypass. The later AirPlay A/B test exposed the associated dynamic-headroom level jump as undesirable UX; the replacement fixed-reserve implementation is now physically accepted and supersedes that headroom behaviour.

#### Fixed-reserve deployment and level-consistency A/B — physical PASS

The live helper package was surgically updated while Plexamp remained actively audible. No ALSA route, Plexamp service, AirPlay service or dashboard service was remapped/restarted. The pre-existing bypassed state with saved Bass `+6.0 dB` was then reapplied through the installed helper so CamillaDSP could reload the fixed-headroom graph in place.

Plexamp playback remained continuous. The expected one-time broad level reduction was audible as the permanent `-6.5 dB` music reserve first entered the path. The returned state reported `bypassed=true`, Bass `db=6.0` / `stored_db=6.0` / `applied_db=0.0` / `effective_db=0.0`, Mid/Treble all zero, `headroom_db=-6.5`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active`, selected route `split-bus-selected`, final limiter `-1.0 dB`, `ok=true`, and unchanged CamillaDSP PID `1543417`.

Restore then reapplied the saved Bass `+6.0 dB` curve without a broad level jump. The Bass change was subjectively much more obvious now that overall level was not changing at the same time. Backend state showed `bypassed=false`, Bass stored/applied/effective `+6.0 dB`, Mid/Treble zero, `headroom_db=-6.5`, active config SHA `2ee27d5fb13c0a087704f197cb0c3420cb453cc15f94c9fa5902a40584ac600f`, route/backend still `split-bus-active`, and PID still `1543417`.

A final bypass removed the Bass boost and returned the music to a normal tonal balance, again without the previous broad loudness jump. The helper returned `bypassed=true`, saved Bass `+6.0 dB`, applied/effective Bass `0.0 dB`, `headroom_db=-6.5`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active`, and PID `1543417`.

This completes physical acceptance of the permanent music headroom design. Everyday EQ Bypass/Restore now changes tone without also moving the broad music level, while the safety reserve remains continuously available for the maximum `+6 dB` tone boost.

#### Music Master maximum-level acceptance — physical PASS

The fixed-reserve system was then exercised with Music Master, trims and source volumes at `100%`. With the external Sony test amplifier set to a sensible listening gain, the permanent `-6.5 dB` reserve still left ample maximum music output. The amplifier gain was then increased slightly and Music Master returned to approximately `79%`, producing a comfortable normal listening level with substantial digital control range still available.

This closes the practical trade-off introduced by the permanent reserve: the music lane retains conservative EQ headroom without making the appliance feel underpowered in normal use.

Several source tracks identified by Plexamp as `96 kHz / 24-bit` were also auditioned and sounded excellent subjectively. This does **not** establish native high-resolution output: the currently accepted split-bus/CamillaDSP contract remains fixed at `44.1 kHz`, `S16_LE`, two channels, so higher-rate/higher-bit-depth source material is converted somewhere in the playback path before the DAC under the present design.

#### Dashboard API state — PASS

With the live Bass `+6.0 dB` curve active, the first `GET /api/audio/eq` correctly surfaced all functional EQ values but exposed one presentation inconsistency: the dashboard wrapper replaced helper `backend_state=split-bus-active` with generic `active`, even though `route_mode` remained correctly detailed. The underlying backend was healthy; `MasterEqualizer.status()` was overwriting a truthful helper field after merging the helper payload.

Commit `44d86a7cbdbbc6bdff14f8c471703d91d82821a1` changed the wrapper so an explicit helper `backend_state` is preserved, and commit `28fe66d49f6b6145227dd58cf0cd794dbc5a3727` added the regression assertion. GitHub Actions run **31219132479** / **#2703** passed.

The bedroom Pi checkout was deliberately not wholesale-updated because it was hundreds of commits behind the branch and had an unrelated local modification to `scripts/launch-dashboard-kiosk.sh`. Only `app/audio_eq.py` was restored from the fetched branch version. Restarting only `a-clockwork-plex.service` left Plexamp audio uninterrupted.

The subsequent live `GET /api/audio/eq` reported backend `camilladsp`, `backend_state=split-bus-active`, `route_mode=split-bus-active`, selected route `split-bus-selected`, Bass stored/applied/effective `+6.0 dB`, Mid/Treble `0.0 dB`, `bypassed=false`, original config SHA `ce53497e62006b985cee198ecb7b274c7bfca0feca3b90762a13f6c142e53fa2`, CamillaDSP PID `1543417`, original headroom `-6.5 dB`, final limiter `-1.0 dB`, and overall `ok=true`. This accepts dashboard/API truthfulness and confirms a dashboard-only restart does not disturb the live audio graph.

#### Mixer overlay bypass/lock — PASS; duplicate Settings EQ authority found and removed

The accepted frontend bypass-lock/copy correction was deployed by restoring only `app/static/js/audio-eq.js` from the fetched branch. After a hard refresh, the **audio mixer overlay** showed the live Bass `+6.0 dB`, Mid/Treble `0.0 dB` curve and the corrected Plexamp/AirPlay music-only wording. Pressing the overlay Bypass control successfully entered bypass and the three EQ knobs became greyed/locked as designed.

The same physical check exposed a separate defect in **Settings → Audio → Equaliser**: that page still showed stale staged values while the live overlay/backend held saved Bass `+6 dB`. Source review found two competing EQ authorities: the old unified Settings `config.audio.eq` model and the production `/api/audio/eq`/CamillaDSP state.

Unified Settings was corrected to derive EQ exclusively from the live backend and to stop applying EQ from normal transactional Settings Save. The legacy `config.audio.eq` block is removed on a subsequent Settings save and was also removed from fresh example configuration.

The first live-authority retest then exposed a blank Equaliser subpage. Static-template/resilient-mount work proved the correct template and JavaScript were reaching Chromium. The actual remaining culprit was a stale migration CSS rule:

```css
body.mode-settings #acp-eq-settings-card {
  display: none !important;
}
```

That rule had intentionally hidden the historic injected EQ card while the old staged Equaliser page was authoritative. After the architecture was reversed, it continued hiding the correct production card.

The final correction:

- `72517ff1439e86d9c6e0ed0040a5296c41a34a83` — removed the obsolete hide rule and retargeted EQ layout CSS to the live controls;
- `bf8c000e3745a0aa0cd0e9eca40e22ee628d5ad0` — regression guard preventing the live Settings EQ card from being hidden again;
- `733ef321034374fe31ee25873569c1bff0dd0fec` — updated the remaining old visual-contract test.

GitHub Actions **#2749 / run 31230224890** passed all **1,354 tests** with JavaScript/page wiring and shell syntax green.

Only the corrected CSS file was restored on the bedroom Pi. After refresh, **Settings → Audio → Equaliser displayed correctly** in the physically bypassed state: saved Bass `+6.0 dB`, Mid/Treble `0.0 dB`, bypass status visible and all three sliders greyed/locked. Pressing **Restore EQ** from that Settings page restored the EQ and immediately re-enabled the sliders; the saved Bass-heavy curve returned. This physically accepts the Settings EQ bypass/lock/restore path and closes the duplicate-authority/blank-card defect chain.

#### Neutral action — physical PASS

From the restored Bass `+6.0 dB` curve, **Return to neutral** was pressed in Settings → Audio → Equaliser while Plexamp remained audible. The UI moved Bass, Mid and Treble to `0 dB` and the music returned to a natural tonal balance without entering bypass.

The immediate `GET /api/audio/eq` reported all three bands with `db`, `stored_db`, `applied_db` and `effective_db` exactly `0.0 dB`, `bypassed=false`, original dynamic headroom `0.0 dB`, original neutral CamillaDSP config SHA `52feaf6e97624b067811d0e440355d42f0e97d5585192cae5a25ac7d67d107ae`, route/backend `split-bus-active`, final limiter `-1.0 dB`, `ok=true`, and unchanged CamillaDSP PID `1543417`. This physically accepts Neutral as a distinct reset operation rather than another form of bypass.

#### AirPlay shared-EQ lane and Plexamp takeover — physical PASS

Starting from the accepted neutral baseline, Bass was moved to `+6.0 dB` while Plexamp was playing. Plexamp immediately became strongly bass-heavy and, under the original dynamic-headroom model, quieter by the expected `6.5 dB` reserve.

AirPlay was then started from the iPhone while Plexamp remained playing. The appliance correctly **paused Plexamp on AirPlay takeover**, and AirPlay playback was audibly just as bass-heavy, physically proving that AirPlay traverses the same CamillaDSP music-EQ lane as Plexamp.

While AirPlay continued playing, EQ Bypass was pressed. Playback remained continuous, the exaggerated bass disappeared and the sound became neutral, while overall level rose because the original implementation also removed the `-6.5 dB` dynamic headroom when bypassed. This accepts the shared AirPlay EQ lane and Plexamp → AirPlay takeover direction. Reverse AirPlay → Plexamp takeover/return remains to be tested separately.

The same A/B exposed the user-facing weakness that motivated the fixed reserve now physically accepted on the live Pi.

#### Settings Display Motion regression — physical PASS

The Settings review also found two regressions in **Settings → Display → Motion** following the custom-select migration:

- Transition style had collapsed from the eight transition choices supported by the dashboard engine to only Grow and fade, Crossfade and Instant.
- Transition duration had regressed from a slider to a numeric text-entry field.

The transition engine and CSS still contained the missing effects; only the Settings exposure/validation contract had been narrowed. Corrections restored the eight user-facing choices and the `0–2000 ms` range slider. GitHub Actions **#2729 / run 31227257674** passed, and the owner subsequently confirmed the Motion page is working correctly on the bedroom Pi.

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
| 2. Standalone installer | Complete | Lifecycle commands and shared libraries are green |
| 3. Non-production/read-only validation | Complete | Real Pi preflight PASS; exact before/after production-state equality |
| 4. Bedroom-Pi installation | Complete | Attempt #2 installed split-bus successfully; live verifier PASS; audible Plexamp confirmed |
| 5. Feature/interface acceptance | In progress | Fixed `-6.5 dB` reserve and maximum useful Music Master level physically accepted; next is reverse AirPlay→Plexamp handover, then Music Master/alarm isolation |
| 6. Failure/reboot/uninstall acceptance | Not started | Follows feature acceptance |
| 7. Full-installer integration | Not started | Reuses the accepted standalone component |
| 8. Cleanup/release preparation | Not started | Includes Stage C archival and documentation cleanup |

## Immediate next action

Continue Phase 5 with **audio active/audible**. The live Pi is on the physically accepted fixed-headroom runtime, currently bypassed with saved Bass `+6.0 dB`, applied/effective Bass `0.0 dB`, `headroom_db=-6.5`, route `split-bus-active`, fixed-reserve bypass config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, and CamillaDSP PID `1543417`. The external amplifier gain has been raised to a comfortable fixed setting and Music Master is currently around `79%`; `100%` has already been physically confirmed to provide ample output with the permanent reserve.

1. test reverse AirPlay → Plexamp takeover/return and record whether source ownership returns cleanly;
2. test Music Master at 0% independently with Plexamp and AirPlay and confirm both music sources mute;
3. then test that a real scheduled alarm remains independent of Music Master and EQ/bypass, followed by Maximum Alarm Volume and combined-output limiter checks using the conservative stepped speaker-safety procedure above;
4. finally recheck NFC playback/dashboard controls before Phase 5 is closed.

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
