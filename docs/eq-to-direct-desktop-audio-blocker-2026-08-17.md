# EQ to Direct desktop-audio teardown blocker — 2026-08-17

## Physical spare-SD result

Target: `plexamp-test` spare SD only. Production SD remained removed and untouched.

Fresh-bootstrap Direct retry reached the intended installed-EQ convergence path:

- `EQ already installed: true`
- `EQ -> Direct migrate: true`
- package/venv bootstrap passed
- PN532 I2C `0x24` passed
- RPi DAC Pro passed
- Plexamp runtime and NFC listener stages passed
- full host preflight passed
- the whole-application transaction entered `eq-teardown`

The retry then failed with installer exit `2` while restoring the pre-EQ `snd_aloop` state:

```text
modprobe: FATAL: Module snd_aloop is in use.
[A Clockwork Plex] ERROR: Uninstall failed; the installed EQ state was restored: snd_aloop state restoration failed
[A Clockwork Plex] ERROR: Whole-appliance application transaction failed at stage: eq-teardown
```

Physical evidence log:

`/home/andy/acp-phase7-spare-sd-20260815-171112/20-direct-install-20260816-235948.txt`

The transaction reported that managed pre-state was restored. No manual EQ uninstall or fix-forward was performed on the spare SD.

## Read-only diagnosis

After rollback, `snd_aloop` was loaded and the restored EQ services were active again. `fuser` showed the expected restored CamillaDSP/Plexamp users plus a desktop-session holder:

- `wireplumber` held `/dev/snd/controlC7`
- card 7 was the configured `ACP_Loopback` card
- CamillaDSP used the loopback PCM again after rollback
- Plexamp used the loopback playback PCM again after rollback

This exposed a production-only gap not covered by alternate-root tests: the EQ uninstall stopped appliance audio applications and managed EQ units but did not temporarily quiesce the Raspberry Pi Desktop WirePlumber ALSA monitor before attempting to unload `snd_aloop`.

## Source correction

The EQ uninstall path now:

1. verifies managed EQ units are actually inactive after the stop request;
2. checks the retained pre-EQ loopback state;
3. only when that state requires `snd_aloop` to become absent, temporarily stops an active `wireplumber.service` in the project user's systemd session;
4. restores the saved `snd_aloop` state;
5. restarts WirePlumber before restoring the original application services;
6. on rollback, reloads `snd_aloop` before restoring CamillaDSP service activity.

The change deliberately does not kill arbitrary processes and does not broadly stop PipeWire. It targets the observed WirePlumber card monitor only when a loopback unload is actually required.

Regression coverage is in `tests/test_eq_uninstall_desktop_audio_quiesce.py`.

## Next physical gate

Do not rerun the spare-SD installer until the exact branch head containing this correction has a successful CI run. After that gate, fast-forward the spare Pi and repeat the guarded Direct fresh-bootstrap command, preserving a new evidence log.
