# EQ to Direct physical verification — 2026-08-17

Target: spare SD card on `plexamp-test`. The accepted production SD card remained removed and untouched throughout.

## Successful guarded convergence

The spare SD was running the previously accepted EQ-capable appliance when Direct fresh-bootstrap was requested. After the WirePlumber/snd_aloop teardown correction, the guarded fresh-bootstrap run completed successfully with:

- `APPLIANCE_VERIFY=PASS`
- `APPLICATION_TRANSACTION=COMMITTED`
- `ROOT_INSTALL=COMMITTED`
- `INSTALL_ROUTE=fresh-bootstrap`
- `PACKAGE_VENV_BASELINE=RETAINED`
- `APPLICATION_VERIFY=PASS`
- root installer exit `0`

Physical evidence log:

`/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260817-001024.txt`

## Independent verification

Independent post-install verification was then run outside the installer transaction.

`verify-fresh-bootstrap.sh` reported:

- pinned Node 20.20.2: PASS
- pinned Plexamp Headless 4.13.2 and claimed Settings state: PASS
- pinned NFC listener/runtime/venv: PASS
- PN532 at I2C bus 1 address `0x24`: PASS
- Raspberry Pi DAC Pro `CARD=Pro`: PASS
- Plexamp service/API: PASS
- NFC listener service/imports: PASS
- failures: 0
- warnings: 0
- `FRESH_BOOTSTRAP_VERIFY=PASS`

Evidence:

`/home/andy/acp-phase7-spare-sd-20260815-171112/21-fresh-bootstrap-verify.txt`

`verify-appliance.sh --audio direct --weather-observations ecowitt-push` reported:

- dashboard/service/kiosk integration: PASS
- AirPlay wrappers/metadata integration: PASS
- restricted alarm, receiver-name and mixer helpers: PASS
- Direct route SHA-256 `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`: PASS
- EQ marker absent: PASS
- Ecowitt live observations + retained Open-Meteo forecast: PASS
- Plexamp/Shairport/dashboard/metadata services active+enabled: PASS
- mixer/dashboard/weather/EQ/mixer APIs: PASS
- failures: 0
- warnings: 0
- `APPLIANCE_VERIFY=PASS`

Evidence:

`/home/andy/acp-phase7-spare-sd-20260815-171112/22-direct-appliance-verify.txt`

## Direct residue check

A final read-only residue check confirmed the committed Direct state is clean:

- active ALSA route SHA-256 exactly `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`
- `DIRECT_MARKER_OK`
- `DIRECT_LOOPBACK_OK` — `snd_aloop` absent
- `PRE_EQ_BACKUP_CLEAN`
- `DIRECT_TOMBSTONE_CLEAN`

Route evidence:

`/home/andy/acp-phase7-spare-sd-20260815-171112/23-direct-route.sha256`

## Focused Direct smoke before EQ promotion — PASS

After the Weather follow-up was fully accepted, the spare card remained in the verified Direct state and received a deliberately small pre-EQ smoke test rather than repeating the already-established AirPlay/alarm/handoff suite.

Physical results:

- ordinary Plexamp playback was healthy;
- a known-good NFC album tag was read successfully and triggered local Plexamp playback;
- the NFC path requested the dashboard switch to `/plexamp`, and the user observed the intended Plexamp dashboard behavior;
- the NFC service log contained `Playback triggered!` and `Dashboard switched to Plexamp mode` with no playback failure;
- the log also noted `xdotool is not installed; mode state was updated but browser was not navigated`; because the intended dashboard state was observed, this is recorded as a non-blocking diagnostic note rather than a Direct/EQ installer failure;
- both the Audio surface and **Settings → Audio → Master equaliser** truthfully reported **Install required** while Direct was installed.

The immediate repeat-scan debounce was not freshly re-exercised during this focused smoke and is not a blocker for EQ promotion. Likewise, AirPlay/PlaybackCoordinator handoff, Music Master/alarm isolation and Snooze/Dismiss are not being redundantly re-run in Direct immediately before EQ. Those behaviors have prior physical evidence and the meaningful release regression is the **post-EQ** pass, where the new audio route can actually affect them.

## CamillaDSP promotion artifact — PASS

Section 9 of the fresh-appliance runbook was completed on the same spare card before EQ promotion.

The prepare-only artifact plan selected:

- CamillaDSP version `4.1.3`;
- official archive SHA-256 `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a`;
- accepted executable SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`;
- cache location `/home/andy/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp`.

Activation returned `CAMILLA_ARTIFACT=PASS-EXISTING`, so the exact accepted artifact was already present and no replacement download was required. Independent checks then reported `CamillaDSP 4.1.3 (05e9cfc)` and the executable SHA exactly matched the accepted value above.

Evidence:

- `/home/andy/acp-phase7-spare-sd-20260815-171112/30-camilladsp-plan.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/31-camilladsp-fetch.txt`

## Guarded EQ promotion plan — PASS

The Section 10 `install.sh --fresh-bootstrap --audio eq` read-only plan was run on the same verified spare appliance with the accepted CamillaDSP binary supplied explicitly.

The plan was reviewed before activation and confirmed:

- `Audio profile: eq`, `Fresh bootstrap: true` and `Weather observations: ecowitt-push`;
- the exact accepted CamillaDSP 4.1.3 executable identity is required;
- EQ explicitly selects `--baseline alarm-safe-direct`, validating the physically accepted fresh Direct route before capture;
- the top-level installer delegates audio mutation to `scripts/audio/install-eq.sh` rather than duplicating or bypassing the specialist lifecycle;
- package, hardware, Plexamp and NFC bootstrap stages remain guarded and idempotent ahead of application mutation;
- application mutation is delegated to `scripts/install-appliance-application.sh` under one rollback transaction;
- `scripts/verify-appliance.sh --audio eq` is the commit gate inside that transaction;
- the plan reported that no production file, package, service, route, mixer, PCM or configuration was changed.

Evidence:

- `/home/andy/acp-phase7-spare-sd-20260815-171112/32-eq-plan.txt`

## Guarded persistent EQ promotion — PASS

The guarded Section 10 apply was then run on the same spare appliance. The full fresh-bootstrap route revalidated package/venv prerequisites, PN532 `0x24`, `CARD=Pro`, pinned Plexamp/Node, pinned NFC runtime and the full host preflight before entering one whole-application transaction.

The EQ application transaction physically passed with:

- root installer exit `0`;
- `ROOT_INSTALL=COMMITTED`;
- `INSTALL_ROUTE=fresh-bootstrap`;
- `PACKAGE_VENV_BASELINE=RETAINED`;
- `APPLICATION_TRANSACTION=COMMITTED`;
- `APPLICATION_VERIFY=PASS`;
- independent `FRESH_BOOTSTRAP_VERIFY=PASS`;
- independent `APPLIANCE_VERIFY=PASS`;
- independent `scripts/audio/verify-audio.sh` PASS;
- active ALSA route SHA-256 exactly `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9`;
- `/var/lib/a-clockwork-plex/split-bus/installed` present;
- split-bus loopback card present with the expected identity/settings;
- the Audio and **Settings → Audio → Master equaliser** surfaces both reported **EQ Active**;
- Plexamp produced normal audible playback and physical EQ adjustment was audibly effective.

The production CamillaDSP unit is canonically named `a-clockwork-plex-camilladsp.service`. Physical systemd checks reported:

- `systemctl is-active a-clockwork-plex-camilladsp.service` → `active`;
- `systemctl is-enabled a-clockwork-plex-camilladsp.service` → `enabled`;
- `MainPID=2468941`;
- `ActiveState=active`;
- `SubState=running`;
- `systemctl list-unit-files '*camilla*'` listed only `a-clockwork-plex-camilladsp.service`.

An earlier ad-hoc check of `camilladsp.service` returned `inactive` only because that is not the managed unit name; it was not an EQ/runtime failure. Future acceptance checks use `a-clockwork-plex-camilladsp.service`.

Evidence:

- `/home/andy/acp-phase7-spare-sd-20260815-171112/33-eq-install.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/34-eq-bootstrap-verify.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/35-eq-appliance-verify.txt`
- `/home/andy/acp-phase7-spare-sd-20260815-171112/36-eq-audio-verify.txt`

## Focused post-EQ physical regression — PASS

After persistent EQ promotion, the deliberately focused Section 11 regression was completed on the same spare appliance with no issues found.

Physical results:

- Plexamp remained clean through the installed split-bus EQ; audible EQ changes worked and bypass removed/restored the EQ effect as expected;
- AirPlay takeover and playback remained healthy through the installed EQ path, and EQ/bypass audibly affected AirPlay as intended;
- with **Music Master at 0%**, music was silenced while a real scheduled alarm remained audible on its independent alarm lane;
- **Maximum Alarm Volume** continued to act as an independent alarm ceiling;
- Snooze, subsequent ringing and Dismiss all worked normally;
- NFC playback and dashboard handoff still worked after EQ promotion;
- an immediate repeat scan of the same tag was successfully debounced rather than retriggering playback.

No functional issue was found in the post-EQ regression. This closes the substantive feature/playback acceptance gate for persistent EQ. The remaining Phase 7 work is durability/idempotence only: reboot persistence, then one repeat whole-appliance install and final evidence closure.

PR #2 remains Draft, open and unmerged until explicit approval.
