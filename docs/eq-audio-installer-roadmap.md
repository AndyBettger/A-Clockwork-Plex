# EQ-capable audio installer roadmap

**Status:** Active roadmap — Phase 5 feature and interface acceptance is complete; Phase 6 failure, reboot and uninstall acceptance is in progress  
**Started:** 7 August 2026  
**Last updated:** 10 August 2026  
**Target branch:** `feature/alarm-engine`  
**Production state:** The bedroom Pi is intentionally in the original **direct-only** audio state after a successful explicit EQ uninstall. Phase 6 reboot/persistence and corrected automatic-failback gates have already passed. The guarded uninstall ran from clean source `9eacee8`, returned `UNINSTALL_RC=0`, restored the exact accepted pre-EQ active ALSA SHA `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`, restored Plexamp/AirPlay/dashboard active and enabled, removed the EQ installed marker, install manifest, retained pre-EQ backup, route/EQ helpers and the three managed EQ systemd units, and left Plexamp physically audible in direct-only mode. The original pre-install loopback snapshot was `loaded`, so `snd_aloop` remains loaded after uninstall exactly as recorded. Saved EQ state is deliberately retained at Bass `+2 dB` / Mid `0 dB` / Treble `+2 dB`, bypass off, for the later reinstall. `route-state.json` truthfully records `direct-rollback` with the exact `08d00093...` checksum, while both EQ UI surfaces now correctly show **Install required** because the supported EQ installation is genuinely absent. The next Phase 6 gate is one controlled reboot in this direct-only state, followed by proof that the original direct route and normal Plexamp/AirPlay/dashboard operation survive reboot before EQ-capable reinstall is attempted.  
**Related PR:** PR #2 remains Draft and must not be merged without explicit approval

## Purpose

The split-bus EQ audio design has been selected, physically proven and fully exercised through installation, reboot, failure/failback, repair and explicit uninstall. Feature/interface acceptance is complete. The remaining Phase 6 work is direct-only reboot acceptance followed by EQ-capable reinstall acceptance, then integration of the supported standalone component into the future full installer and cleanup/archive work.

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

The trade-off is that the EQ-capable music lane has `6.5 dB` less maximum digital level even at neutral. The bedroom system uses a separate analogue amplifier, so normal physical listening gain can be established there while preserving conservative digital headroom. Physical testing confirmed that Music Master at `100%` still provides ample usable output with the reserve in place, so this trade-off is accepted.

Implementation checkpoint:

- `scripts/audio_eq_camilladsp/model.py` defines `FIXED_MUSIC_HEADROOM_DB = -6.5` and always renders that reserve on music channels 0/1;
- the CamillaDSP pipeline has a permanently enabled `[headroom]` filter followed by a separately bypassable `[bass, mid, treble]` filter stage;
- bypass preserves the actual saved tone-filter gains in the configuration instead of simulating bypass by rewriting them to zero;
- `runtime.py` reports `headroom_db=-6.5` whenever the EQ-capable backend is actually available, including Neutral and Bypass, but reports `0.0` when the backend is unavailable/direct-failback because the reserve is then physically absent;
- the static installer neutral profile mirrors the same pipeline so future install/repair does not regress to the dynamic model;
- dedicated tests protect fixed headroom at neutral/boost/cut/bypass, real tone-stage bypass, alarm-after-music processing order and truthful direct-failback reporting.

Source head `7555b8186355cddc214fe5e08908fa79ff8fd6c4` passed GitHub Actions **#2767 / run 31234727079**: compilation PASS, JavaScript/page-wiring/shell-syntax PASS, and **1,353/1,353 unit tests PASS**.

The live bedroom Pi then received only `__init__.py`, `model.py` and `runtime.py` into the installed helper package. With Plexamp actively audible, EQ already bypassed and saved Bass `+6.0 dB`, `a-clockwork-plex-audio-eq bypass on` reloaded the new graph in place. Playback remained continuous and the expected one-off broad level reduction was heard as the permanent reserve entered the music path. The helper reported `headroom_db=-6.5`, `bypassed=true`, saved Bass `+6.0 dB`, Bass applied/effective `0.0 dB`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active`, final limiter `-1.0 dB`, and unchanged CamillaDSP PID `1543417`.

The saved curve was then restored in place. Playback remained continuous and the Bass boost became immediately and more clearly audible because the overall music level no longer moved with it. The helper reported Bass stored/applied/effective `+6.0 dB`, `bypassed=false`, fixed `headroom_db=-6.5`, config SHA `2ee27d5fb13c0a087704f197cb0c3420cb453cc15f94c9fa5902a40584ac600f`, route/backend `split-bus-active`, final limiter `-1.0 dB`, and unchanged PID `1543417`.

Bypass was then re-enabled. The Bass boost disappeared and the music returned to a neutral tonal balance without the old broad loudness rise. The helper returned `bypassed=true`, saved Bass `+6.0 dB`, Bass applied/effective `0.0 dB`, fixed `headroom_db=-6.5`, config SHA `79adf02f489f3cc43c591e0bfe0f1883e81387a195b7a56e42f49ba23b026495`, route/backend `split-bus-active` and PID `1543417`.

This physically accepts the fixed-headroom refinement in both directions: the tone stage changes tonal balance while the permanent reserve remains stable, so everyday EQ A/B no longer introduces the distracting repeated `6.5 dB` master-level jump.

### Alarm loudness, limiter and hardware commissioning

The alarm lane intentionally bypasses the music-lane `-6.5 dB` reserve as well as Music Master and the tone controls. That independence is required and is physically accepted.

Maximum Alarm Volume has already been proven as a genuine persistent global ceiling after each alarm's target and fade: with the same `50%` per-alarm target, `15%` was audibly quieter than `22%`. No additional code calibration is required. Choosing the final fader position for the eventual amplifier/speaker combination is normal hardware commissioning and can be repeated whenever the analogue system changes; it is not a blocker for software acceptance.

The final `-1 dB` limiter protects against digital clipping at the combined output. Stage A objectively stressed simultaneous music and alarm content and measured the final output at exactly `-1.000 dBFS`, proving that the limiter protects the post-mix output. There is therefore no requirement to reproduce a deliberately loud combined-output stress test through the bedroom speakers.

The limiter cannot protect a loudspeaker from excessive analogue amplifier power, so sensible amplifier gain and Maximum Alarm Volume commissioning still matter on whatever final hardware is chosen.

### Deferred Plexamp high-resolution / variable-rate investigation

Native or near-native Plexamp playback is explicitly deferred until the current installer roadmap is complete. The later investigation should start from Plexamp's existing strict sample-rate matching and CamillaDSP's sample-format/resampling capabilities rather than assuming that the only solution is a separate raw-DAC bypass mode.

The promising direction is to investigate whether the Plexamp lane can negotiate or follow source sample rate/bit depth while AirPlay remains on a fixed `44.1 kHz / 16-bit` lane for podcasts/audiobooks, with CamillaDSP converting/mixing only where required and the DAC operating at the appropriate resulting rate. The Raspberry Pi DAC Pro is expected to support high-resolution rates up to its hardware/driver limits, but no bit-perfect or native-rate claim is accepted until the real end-to-end path is measured and verified.

This is a future enhancement only and must not block Phase 6–8 completion.

### Failure behaviour

Everyday EQ bypass is not failback. Automatic failback is reserved for a genuine backend failure, such as CamillaDSP failing to start or the expected PCMs becoming unavailable. The appliance must then return to the known-good direct alarm-safe route, restore affected application services and report that the EQ backend is unavailable.

The first physical failure-injection attempt proved that combining `Restart=on-failure` with `OnFailure=a-clockwork-plex-audio-failback.service` races an automatic CamillaDSP restart against direct failback. It also proved that placing `Before=plexamp.service shairport-sync.service a-clockwork-plex.service` on the failback oneshot deadlocks the route helper's own synchronous application-restoration calls. The corrected source contract is deterministic: CamillaDSP uses `Restart=no` and `OnFailure=a-clockwork-plex-audio-failback.service`; the failback oneshot has no `Before=` relationship to Plexamp/AirPlay/dashboard and delegates the complete stop/route-switch/restore transaction to `/usr/local/bin/a-clockwork-plex-audio-route activate-direct-failback`. The route-preparation unit continues to point genuine route-preparation failures to the same failback oneshot. The repeat physical SIGKILL test passed this corrected contract end-to-end: CamillaDSP did not restart, failback completed successfully, applications were restored and usable direct audio returned automatically.

## Accepted direct rollback baseline

The exact pre-EQ direct baseline remains the uninstall rollback reference:

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

`preflight-eq.sh` is the read-only bedroom-Pi validation gate. The other four commands own the installed audio lifecycle. The repository scripts are currently invoked explicitly through `bash`; their tracked mode is intentionally left unchanged rather than applying local executable-bit changes.

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

GitHub Actions run **31145374614** produced **1,346/1,346 passing tests**, including all six dedicated preflight safety tests. Python compilation, JavaScript/page-wiring and shell-syntax checks passed.

#### Bedroom-Pi read-only validation checkpoint — PASS

The read-only bedroom-Pi validation gate ran from exact source commit `9757006c2f1987b2a4c93a88f5a5bbd7cc3dc534` while normal direct Plexamp audio remained active.

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

No production file, route, module, mixer control, PCM or service was changed. No bedroom-Pi installation was performed by the preflight.

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
- failback service available and inactive during healthy split-bus operation;
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
- [x] Unprivileged installed `status` reports the same authoritative saved EQ state as the elevated restricted-sudo status path. *(Physical PASS after privilege-delegation fix.)*
- [x] Confirm the dashboard/API surfaces the same truthful EQ state.
- [x] Bass control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] Mid control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] Treble control is audibly distinct, persists the requested value and reports the applied value correctly.
- [x] AirPlay plays through the same music EQ lane.
- [x] AirPlay/Plexamp takeover and return still work. *(Plexamp → AirPlay takeover pauses Plexamp; genuine AirPlay disconnect releases ownership cleanly and leaves Plexamp paused at the takeover position, ready for deliberate manual resume.)*
- [x] EQ disable uses bypass without route remapping.
- [x] Stored values survive bypass and return when enabled.
- [x] Controls are greyed and locked while bypassed. *(Mixer overlay and Settings subpage physical PASS.)*
- [x] Return to neutral sets all bands to `0 dB`.
- [x] Fixed `-6.5 dB` music-lane pre-EQ reserve is physically accepted for level consistency. *(Source/CI, surgical deployment and Restore/Bypass A/B all PASS.)*
- [x] Music Master at 100% remains adequately loud with the permanent reserve.
- [x] Music Master at 0% silences Plexamp and AirPlay.
- [x] Music Master at 0% does not reduce a real scheduled alarm.
- [x] EQ and bypass do not alter alarm tone or level.
- [x] Maximum Alarm Volume still caps scheduled alarms.
- [x] Output Levels wording and fader presentation accurately represent Music Master, source trims and Maximum Alarm Volume. *(Physical PASS at 1024×600; final layout refinement commit `1cc797b0e90d449dedbc8d5d91f9c5de4bda7c5e`.)*
- [x] NFC playback still launches the correct Plexamp content and Plexamp's own playback controls remain normal. *(The earlier “dashboard controls” wording was corrected because the dashboard does not expose Plexamp transport controls.)*
- [x] Maximum Alarm Volume requires no further software calibration: the ceiling behaviour is physically proven, while the eventual fader position is hardware commissioning for the chosen analogue system.
- [x] The final limiter protects combined music and alarm playback. *(Stage A measured the deliberately overdriven combined output at exactly `-1.000 dBFS`.)*
- [x] Future amplifier/speaker alarm-volume commissioning is tracked as a hardware setup task rather than a Phase 5 software gate.

#### Initial EQ status — PASS

With Plexamp actively playing, the installed helper reported the expected original neutral post-install state: backend/route `split-bus-active`, selected route `split-bus-selected`, all three bands at `0.0 dB`, EQ not bypassed, original dynamic headroom `0.0 dB`, final limiter `-1.0 dB`, and CamillaDSP PID `1543417`.

#### Bass / Mid / Treble live EQ A/B — PASS

Each band was exercised independently through a deliberately obvious `+6 dB` / `-6 dB` swing while Plexamp remained playing. The helper reported the requested stored/applied/effective values correctly, the route and CamillaDSP PID remained stable, and manual listening clearly confirmed the expected tonal changes. Each band was subsequently returned to neutral. These tests physically accepted all three live controls and their state reporting.

#### Everyday bypass/restore — PASS

A deliberately obvious saved Bass `+6.0 dB` curve was bypassed and restored with playback continuous. Bypass preserved the saved curve while setting the tone stage's applied/effective values to zero and did not remap the ALSA route. Restore immediately brought the saved tonal curve back. The later fixed-headroom refinement removed the original distracting broad-level jump while preserving those bypass semantics.

#### Fixed-reserve deployment and level-consistency A/B — physical PASS

The live helper package was surgically updated while Plexamp remained actively audible. No ALSA route, Plexamp service, AirPlay service or dashboard service was remapped/restarted. The pre-existing bypassed state with saved Bass `+6.0 dB` was reapplied through the installed helper so CamillaDSP could reload the fixed-headroom graph in place.

Plexamp playback remained continuous. The expected one-time broad level reduction was audible as the permanent `-6.5 dB` music reserve first entered the path. Restore then reapplied the saved Bass `+6.0 dB` curve without a broad level jump, and a final bypass removed the Bass boost without the previous broad loudness rise. Route/backend stayed `split-bus-active`, the final limiter remained `-1.0 dB`, and CamillaDSP remained on PID `1543417` throughout.

This completes physical acceptance of the permanent music headroom design. Everyday EQ Bypass/Restore now changes tone without also moving the broad music level, while the safety reserve remains continuously available for the maximum `+6 dB` tone boost.

#### Music Master maximum-level acceptance — physical PASS

The fixed-reserve system was exercised with Music Master, trims and source volumes at `100%`. With the external test amplifier at a sensible gain, the permanent `-6.5 dB` reserve still left ample maximum music output. The amplifier gain was then increased slightly and Music Master returned to approximately `79%`, producing a comfortable normal listening level with substantial digital control range still available.

Several source tracks identified by Plexamp as `96 kHz / 24-bit` were also auditioned and sounded excellent subjectively. This does not establish native high-resolution output: the currently accepted split-bus/CamillaDSP contract remains fixed at `44.1 kHz`, `S16_LE`, two channels, so higher-rate/higher-bit-depth source material is converted somewhere in the current playback path.

#### AirPlay return and Music Master zero acceptance — physical PASS

Plexamp was started and then taken over by AirPlay from the iPhone. AirPlay correctly paused Plexamp. On genuine AirPlay disconnect the dashboard returned to Clock because no source was actively audible, AirPlay ownership was released, and Plexamp remained paused at exactly the takeover position, ready for deliberate manual resume.

Music Master isolation was then exercised independently with both sources. Music Master `0%` silenced Plexamp and AirPlay without changing source ownership or playback progression, and restoring Music Master immediately restored audible output. This physically accepts the shared music-lane master control and the deliberate no-synthetic-resume handoff contract.

#### Real scheduled-alarm isolation and maximum-ceiling A/B — physical PASS

A real scheduled alarm was tested with Plexamp playing and Music Master deliberately reduced to `0%`. Plexamp became silent, but the alarm remained clearly audible and took ownership by pausing Plexamp, physically proving that Music Master controls only the music lane.

The global alarm ceiling was then tested with the same `50%` per-alarm target. Maximum Alarm Volume `15%` was audibly quieter than `22%`, proving the control is a genuine hard ceiling after the per-alarm target/fade. A repeated real-alarm A/B with the saved Bass `+6 dB` curve active versus EQ bypassed sounded identical in both tone and level, physically proving that scheduled alarms bypass Bass/Mid/Treble, fixed music reserve and Music Master.

The resulting Settings presentation was clarified and physically accepted as **Music**, **Plexamp**, **AirPlay** and **Alarms**, with top-right percentage pills, equal fader geometry and bottom-aligned explanatory copy. The underlying `master`, `plexamp`, `airplay` and `alarm` mixer semantics are unchanged.

#### Dashboard API state — PASS

The dashboard wrapper was corrected so an explicit helper `backend_state=split-bus-active` is preserved rather than overwritten with a generic state. Commit `44d86a7cbdbbc6bdff14f8c471703d91d82821a1` and regression commit `28fe66d49f6b6145227dd58cf0cd794dbc5a3727` passed GitHub Actions. The live API subsequently reported the same detailed backend, route, EQ, headroom and limiter state as the helper.

#### Mixer overlay bypass/lock and Settings authority — PASS

The physical review exposed duplicate EQ authority between the old unified Settings model and the production `/api/audio/eq`/CamillaDSP state. Unified Settings was corrected to derive EQ exclusively from the live backend and to stop applying EQ from normal transactional Settings Save. A stale CSS rule that still hid the newly authoritative live EQ card was then removed. The final corrected Settings → Audio → Equaliser page physically displayed the saved curve, bypass state and lock/restore behaviour correctly.

#### Neutral action — physical PASS

From the restored Bass `+6.0 dB` curve, **Return to neutral** moved Bass, Mid and Treble to `0 dB`, kept bypass off and restored normal tonal balance. The backend reported every stored/applied/effective band value at exactly `0.0 dB`. Neutral is therefore physically accepted as a distinct reset operation rather than another form of bypass.

#### AirPlay shared-EQ lane and Plexamp takeover — physical PASS

A deliberate Bass `+6 dB` curve was applied while Plexamp played, then AirPlay took over from the iPhone. Plexamp paused correctly and AirPlay was audibly just as bass-heavy, proving that both sources traverse the same music-EQ lane. Bypass while AirPlay continued removed the exaggerated Bass without interrupting playback.

#### Settings Display Motion regression — physical PASS

Following the custom-select migration, Transition style had accidentally narrowed and Transition duration had regressed to numeric text entry. The eight supported transition choices and the `0–2000 ms` range slider were restored and physically confirmed working on the bedroom Pi.

#### Clean checkout reconciliation and NFC regression — physical PASS

The bedroom-Pi source checkout was reconciled from its older selective-deployment state after preserving the genuinely different local files outside the repository at `/home/andy/acp-pi-reconcile-20260809-024152`. The branch was reset to the remote feature branch, configured for normal fast-forward pulls and subsequently advanced cleanly through the status and Phase 6 fixes. A known-good NFC tag opened Plexamp and played the correct album, and Plexamp's own playback controls behaved normally.

#### Installed status privilege truthfulness — physical PASS

The authoritative saved EQ JSON is intentionally root-owned and mode `0600`. A direct unprivileged helper status had been silently falling back to neutral when it could not read that file, while the dashboard/restricted-sudo path remained truthful. Commit `f4453a5d69467a46cdc7e3ddeb236c2e5a46fba2` makes only the installed helper's exact unprivileged `status` command delegate to the existing restricted `sudo -n` status rule; commit `e7f4fbaa10610ca9dd41381cad3c0d20d388b861` adds regression coverage.

The live retest produced identical normal and elevated JSON status payloads: Bass `+2.0 dB`, Mid `0.0 dB`, Treble `+2.0 dB`, `bypassed=false`, fixed headroom `-6.5 dB`, final limiter `-1.0 dB`, route/backend `split-bus-active`, config SHA `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578`, and `ok=true`.

#### Phase 5 closure decision — accepted

The remaining proposed “Maximum Alarm Volume calibration” was reviewed and explicitly removed as a software acceptance gate. The code already exposes and persists the working global ceiling; selecting its final position is simply commissioning against the chosen analogue amplifier and speakers. The combined-output limiter was also already objectively proven in the isolated Stage A DSP stress run at exactly `-1.000 dBFS`, so reproducing that deliberate overdrive through the bedroom speakers adds no software evidence. Future analogue-hardware commissioning remains sensible but does not block Phase 6.

**Exit condition:** Met. The installed backend and redesigned Settings/interface behave as one coherent feature, and no unfinished software calibration remains.

### Phase 6 — failure, reboot and uninstall acceptance

- [x] Controlled CamillaDSP failure returns to usable direct audio. *(Attempt #1 exposed the service defects; corrected attempt #2 physical PASS with automatic direct failback and audible Plexamp.)*
- [x] Failback leaves Plexamp, AirPlay and dashboard usable. *(Corrected attempt #2 physical PASS; all three returned active without manual recovery.)*
- [x] One controlled reboot restores the EQ-capable graph.
- [x] Saved active/bypassed state survives reboot. *(Active `+2 / 0 / +2` curve survived exactly.)*
- [x] Persistent `snd_aloop` state is verified after reboot. *(Index 7, id `ACP_Loopback`, two substreams, notify 1.)*
- [x] Explicit uninstall restores the accepted direct-route checksum. *(Physical PASS: exact `08d00093...` active route restored, managed EQ installation removed, original services restored.)*
- [ ] Direct audio remains usable after uninstall and reboot. *(Pre-reboot direct-only Plexamp PASS; reboot still pending.)*
- [ ] Reinstall after uninstall succeeds.

#### Pre-reboot manifest/verifier reconciliation — physical PASS

The first Phase 6 pre-reboot verifier run correctly stopped progression but initially exposed an ambiguous generic manifest error. Instrumented comparison found five mismatches. Four were expected static-program drift from the deliberately deployed `__init__.py`, `model.py`, `runtime.py` and `cli.py` refinements; the fifth revealed the actual design defect: `/etc/a-clockwork-plex/camilladsp-split-bus.yml` had an installation-time hash in the manifest even though normal EQ/bypass changes legitimately regenerate that live file.

The manifest contract was corrected in commit `42b839db305f03104c238f052a45b4d759636119`: the live CamillaDSP YAML is now recorded as `runtime-generated`, its existence/mode and later semantic CamillaDSP validation remain enforced, while genuinely static installed files retain exact hash and mode checking. Commit `80c0868ccebfac86a7adeccde1e9085097388ece` adds regression coverage including old-manifest compatibility and useful mismatch diagnostics. GitHub Actions **Tests #2833 / run 31291978735** passed.

The bedroom Pi fast-forwarded cleanly to `80c0868`. A verified copy of the already-installed CamillaDSP 4.1.3 binary had SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`. `repair-audio.sh --prepare-only` made no production change. The guarded repair then snapshotted the installation, reinstalled the reviewed assets, preserved the original uninstall backup and saved EQ state, rewrote the manifest and reactivated split-bus audio. It completed with live verifier PASS and CamillaDSP PID `1871368`.

The post-repair manifest contained:

- generated CamillaDSP config: `runtime-generated`, mode `644`;
- `__init__.py` SHA `e7f5f8c1aa35c054069796328426ea842010a9417ab40168c509ef14b9c759b9`;
- `model.py` SHA `85fa2a7a2bfc8713f0990324099bcfe3d54fb5cd2d35a0d52f43e14205cda4cd`;
- `runtime.py` SHA `df68a2b4fae100da9bba698e2b726a86f76e0590aa2ce5a46331152b1218958a`;
- `cli.py` SHA `b0dc88be7d267b9b8c5a21a47fca285125332c316bf31e1bf6207dc027f3ff49`.

The saved EQ remained Bass `+2`, Mid `0`, Treble `+2`, bypass off, fixed headroom `-6.5 dB`, final limiter `-1.0 dB`, route `split-bus-active`, split-route SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`, generated config SHA `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578`, and the checkout remained clean at `80c0868`.

#### Controlled reboot — physical PASS

The bedroom Pi rebooted normally at `2026-08-09 04:37:49` on kernel `6.18.39+rpt-rpi-2712`.

Post-reboot acceptance:

- `plexamp.service` active;
- `shairport-sync.service` active;
- `a-clockwork-plex.service` active;
- `a-clockwork-plex-audio-route.service` active;
- `a-clockwork-plex-camilladsp.service` active;
- all five main units remain enabled; the failback unit correctly reports `static` because it is invoked through `OnFailure` rather than independently enabled;
- saved Bass `+2.0 dB`, Mid `0.0 dB`, Treble `+2.0 dB` returned exactly with `bypassed=false`;
- fixed headroom remained `-6.5 dB` and final limiter `-1.0 dB`;
- CamillaDSP restarted normally with PID `934`;
- route/backend returned `split-bus-active`, selected route `split-bus-selected`;
- active split-route SHA remained `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`;
- generated CamillaDSP config SHA remained `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578`;
- live verifier reported `EQ-capable audio verification passed.`;
- `snd_aloop` loaded with index `7`, id `ACP_Loopback`, first-card `pcm_substreams=2` and `pcm_notify=1`;
- the dashboard returned normally;
- a known-good NFC card opened Plexamp and started the correct album audibly, with the saved EQ active and working;
- `git status --short` remained empty and source HEAD remained `80c0868` at the physical acceptance point.

This accepts reboot restoration, saved EQ persistence, persistent loopback setup, dashboard return and real post-boot source playback.

#### Controlled CamillaDSP failure attempt #1 — physical FAIL; direct recovery PASS

A single controlled `SIGKILL` was sent to the running CamillaDSP main process PID `934` while Plexamp was playing. Systemd immediately recorded the signal failure and triggered `OnFailure=a-clockwork-plex-audio-failback.service`. Two conflicting paths then ran at the same time:

- `Restart=on-failure` scheduled a CamillaDSP restart after two seconds and started a new process at PID `44862`;
- the failback oneshot started `/usr/local/bin/a-clockwork-plex-audio-route activate-direct-failback`.

The failback helper successfully installed the reviewed direct alarm-safe route: active ALSA SHA became `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`, `active_matches_direct_failback=true`, and route/EQ status truthfully changed to `direct-failback` / unavailable while retaining saved Bass `+2`, Mid `0`, Treble `+2` state. However, the failback unit itself declared `Before=plexamp.service shairport-sync.service a-clockwork-plex.service`, while the helper's contract is to synchronously restart whichever of those applications were active before the transition. Those start jobs therefore waited for the failback unit to finish, while the failback helper waited for the start jobs to return. After 30 seconds systemd terminated the failback oneshot for timeout, leaving Plexamp, AirPlay and the dashboard stopped. The automatic CamillaDSP restart had also raced back into service despite the route already being direct failback.

The journal captured the sequence explicitly: CamillaDSP signal failure and `OnFailure` trigger at `05:01:56`, CamillaDSP restart counter 1 and PID `44862` at `05:01:58`, then failback start timeout/termination at `05:02:26`.

Recovery deliberately preserved the successful direct-route transition rather than forcing the EQ graph back immediately. The stuck failback was stopped, the racing CamillaDSP service was stopped, both failure states were reset, and Plexamp, AirPlay and the dashboard were started manually. The resulting recovery state is healthy direct failback: Plexamp/AirPlay/dashboard active, CamillaDSP inactive, failback inactive, direct route SHA `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`, loopback contract still correct, saved `+2 / 0 / +2` curve preserved but unapplied, `headroom_db=0.0` because the DSP path is absent, and Plexamp is physically audible again. The Pi checkout remained clean at `3391d64` at that recovery checkpoint. The captured journal is stored at `~/acp-phase6-failback-failure-journal.txt`.

#### Deterministic failback correction and repeat test — physical PASS

Commit `6bf5b0df5a1048ae20966d086ff4e5096990de64` corrects the two systemd orchestration defects without changing the ALSA profiles or route-helper transaction:

- CamillaDSP now uses explicit `Restart=no`; the redundant restart delay/start-limit settings are removed, so a genuine service failure proceeds directly to `OnFailure` rather than racing a DSP restart against failback;
- the failback oneshot no longer has a `Before=` relationship to Plexamp, AirPlay or the dashboard, so the route helper can complete its existing stop/switch/restore transaction without circular systemd ordering;
- `tests/test_eq_audio_runtime_assets.py` locks both policies and continues to require the fixed failback helper action;
- the existing route-helper tests already cover stopping and restoring only the applications that were active before failback.

GitHub Actions **Tests #2843 / run 31294416551** passed at `6bf5b0d`.

The production Pi then fast-forwarded cleanly from `3391d64` to `a2e079c`. The retained CamillaDSP 4.1.3 repair binary was present with expected SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`. `repair-audio.sh --prepare-only` again made no production change. The guarded repair reinstalled the reviewed assets and returned `split-bus-active` with CamillaDSP PID `168877`.

Physical installed-unit verification confirmed effective `Restart=no`, `OnFailure=a-clockwork-plex-audio-failback.service`, no failback `Before=` line for Plexamp/AirPlay/dashboard, active split-route SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`, saved/applied `+2 / 0 / +2`, fixed `-6.5 dB` headroom, final limiter `-1.0 dB`, all five main services active, live verifier PASS and audible Plexamp/EQ.

The same source head contains the EQ-health wording correction: installed direct failback is reported as **Direct failback** rather than the false **Install required** state, with regression coverage in `tests/test_audio_eq_failback_status_copy.py`. GitHub Actions **Tests #2849 / run 31294821174** passed at `a2e079c`.

The Pi then fast-forwarded the docs-only roadmap commit to clean HEAD `3e07957` and repeated exactly one controlled SIGKILL while Plexamp was active. Pre-fault CamillaDSP PID was `168877`, `Restart=no`, `NRestarts=0`, route was `split-bus-active`, and Plexamp/AirPlay/dashboard were active.

At `06:40:03` systemd recorded the SIGKILL and triggered the failback dependency. By `06:40:04` the route helper had selected the reviewed direct alarm-safe route and the failback oneshot had completed successfully. Post-fault acceptance was:

- CamillaDSP `ActiveState=failed`, `SubState=failed`, `MainPID=0`, `Result=signal`, `NRestarts=0`, proving there was no restart race;
- failback `Result=success`, `ExecMainStatus=0`, `ActiveState=inactive`, `SubState=dead`, proving the oneshot completed rather than timing out;
- Plexamp active;
- AirPlay active;
- dashboard active;
- route service active;
- active ALSA SHA `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` with `active_matches_direct_failback=true`;
- CamillaDSP PID absent and selected route `direct-failback`;
- saved Bass `+2`, Mid `0`, Treble `+2` preserved with applied/effective values `0` while processing is unavailable;
- `headroom_db=0.0`, correctly reflecting that the DSP music reserve is physically absent on direct failback;
- Plexamp physically playable/audible after failback without any manual recovery;
- both the drawer EQ box and Settings → Audio → Equaliser physically displayed **Direct failback**;
- checkout remained clean at `3e07957`.

This accepts the corrected automatic failback path end-to-end and physically closes the EQ failback-status wording regression.

#### Split-bus restoration after accepted failback — physical PASS

After recording the automatic-failback PASS, the Pi fast-forwarded cleanly to docs-only head `24e1ee4`. The retained CamillaDSP 4.1.3 binary again matched SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`. `repair-audio.sh --prepare-only` made no production changes, then guarded repair restored the normal split-bus graph from the accepted direct-failback state.

Post-repair acceptance:

- active route/backend `split-bus-active`, selected mode `split-bus-selected`;
- active split-route SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`;
- generated CamillaDSP config SHA `d2fed55d9bd10bb3b70837e7af9117400139247bad5ec65640f69ae3fb8f0578`;
- CamillaDSP PID `216238`;
- Bass stored/applied/effective `+2.0 dB`, Mid `0.0 dB`, Treble `+2.0 dB`;
- `bypassed=false`, fixed `headroom_db=-6.5`, final limiter `-1.0 dB`;
- Plexamp, AirPlay, dashboard, route and CamillaDSP services all active;
- live verifier reported `EQ-capable audio verification passed.`;
- Plexamp physically audible;
- drawer Audio EQ and Settings → Audio → Equaliser both physically showed the active, working EQ;
- checkout remained clean at `24e1ee4`.

This re-establishes a known-good installed EQ-capable starting point for the explicit uninstall test.

#### Explicit uninstall — physical PASS; direct reboot pending

The Pi fast-forwarded cleanly to docs-only head `9eacee8` and ran `bash scripts/audio/uninstall-eq.sh --prepare-only`. The prepare gate reported retained direct-route SHA `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` and explicitly confirmed that no production file, module, service, route, mixer or PCM was changed. Immediately before activation, the current route remained split-bus SHA `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`, and Plexamp/AirPlay/dashboard/route/CamillaDSP were all active.

The original retained pre-EQ snapshots were copied to `~/acp-phase6-uninstall-acceptance` before activation. They recorded:

- loopback runtime state `loaded`;
- Plexamp, AirPlay and dashboard all active and enabled;
- original active route SHA `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`.

The guarded uninstall then ran with `--confirm UNINSTALL-EQ-AUDIO`, returned `UNINSTALL_RC=0`, and reported that the original direct-audio state was restored. Post-uninstall acceptance was:

- active `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf` SHA exactly `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
- Plexamp active/enabled;
- AirPlay active/enabled;
- dashboard active/enabled;
- `/var/lib/a-clockwork-plex/split-bus/installed` absent;
- `/var/lib/a-clockwork-plex/split-bus/install-manifest.tsv` absent;
- `/var/lib/a-clockwork-plex/split-bus/pre-eq-backup` absent after successful rollback completion;
- `/usr/local/bin/a-clockwork-plex-audio-route` absent;
- `/usr/local/bin/a-clockwork-plex-audio-eq` absent;
- route, CamillaDSP and failback managed systemd unit files absent;
- saved `master-eq.json` intentionally retained with Bass `+2.0`, Mid `0.0`, Treble `+2.0`, `bypassed=false`;
- `route-state.json` records `mode=direct-rollback`, reason `EQ-capable audio profile uninstalled`, and exact active ALSA SHA `08d00093...`;
- `snd_aloop` remains loaded, matching the original recorded pre-install runtime state;
- checkout remains clean at `9eacee8`;
- Plexamp physically plays through the restored direct-only route;
- drawer Audio EQ and Settings → Audio → Equaliser both truthfully show **Install required** because the supported EQ installation is now actually absent.

This physically accepts explicit uninstall and exact direct-route restoration before reboot.

**Exit condition:** In progress. Reboot persistence, corrected automatic failback/application restoration, post-failback repair and explicit uninstall are accepted. Remaining Phase 6 work is direct-only reboot acceptance followed by EQ-capable reinstall acceptance.

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
- [ ] Retire or archive orphan Settings presentation code such as `settings-audio-workspace.js` once the supported presenter path is frozen.
- [ ] Retire obsolete self-mutating Phase 2 completion workflows after preserving any historical evidence they still provide; they currently fire on branch pushes independently of the normal PR test workflow.
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
| 5. Feature/interface acceptance | Complete | Fixed headroom, source/master/alarm isolation, Output Levels, NFC/handoff, EQ authority/truthfulness and measured final-limiter protection accepted; future analogue alarm level is hardware commissioning |
| 6. Failure/reboot/uninstall acceptance | In progress | Reboot/persistence + corrected automatic failback PASS; explicit uninstall/direct restoration PASS; direct-only reboot and reinstall remain |
| 7. Full-installer integration | Not started | Reuses the accepted standalone component |
| 8. Cleanup/release preparation | Not started | Includes Stage C archival, obsolete self-mutating workflow retirement and documentation cleanup |

## Immediate next action

The bedroom Pi is intentionally in the accepted **direct-only post-uninstall state**: source checkout clean at `9eacee8`, original active ALSA SHA `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`, Plexamp/AirPlay/dashboard active and enabled, supported EQ helpers/units/marker absent, saved `+2 / 0 / +2` curve retained for reinstall, Plexamp audibly usable, and the UI truthfully reports **Install required**.

1. fast-forward the Pi checkout to this roadmap update;
2. reboot the Pi without reinstalling or repairing EQ first;
3. after reboot, confirm `/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf` still hashes to exact direct SHA `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9`;
4. confirm Plexamp, AirPlay and dashboard are active/enabled and the managed EQ helpers/units remain absent;
5. physically start Plexamp (NFC is acceptable) and confirm normal audible direct-only playback; confirm both EQ surfaces still show **Install required**;
6. record `snd_aloop` post-reboot state for evidence only — its presence or absence is not a direct-audio pass/fail criterion because the supported EQ persistence files have been removed;
7. only after direct-only reboot PASS, reinstall EQ-capable audio through the supported installer using the retained verified CamillaDSP 4.1.3 binary, then verify the live graph and saved EQ restoration.

Do not reinstall EQ before the direct-only reboot gate is complete.

## Roadmap maintenance discipline

This file is part of the implementation workflow, not an occasional retrospective document.

- Any commit that materially completes, blocks or changes a roadmap item must update this file in the same change or immediately afterward.
- A phase must not be marked complete until its exit condition passes.
- Failed gates must be recorded with exact scope and result.
- Any physical Pi change must record route, checksum, relevant service state and rollback outcome.
- The roadmap must be checked before project status is reported in chat.
- PR #2 remains Draft and must not be merged without explicit approval.

The owner should not need to prompt for routine roadmap updates as development progresses.
