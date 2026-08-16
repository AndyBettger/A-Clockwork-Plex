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

This closes the installer/convergence portion of Direct physical acceptance on the reused spare SD. Remaining acceptance is hands-on appliance behaviour: dashboard/kiosk presentation, Plexamp/NFC playback, AirPlay handoff, Direct music/alarm isolation, alarm Snooze/Dismiss behaviour, Direct-mode EQ presentation, Weather Settings/history behaviour, and final notes.

PR #2 remains Draft, open and unmerged until explicit approval.
