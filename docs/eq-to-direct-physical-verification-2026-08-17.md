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

The next acceptance action is Section 10: promote this same verified Direct appliance to guarded EQ, then run the bootstrap, appliance and audio verifiers before the substantive post-EQ physical regression.

PR #2 remains Draft, open and unmerged until explicit approval.
