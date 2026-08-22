# Direct fresh-bootstrap independent verification — 2026-08-17

Target: spare SD card on `plexamp-test`. The accepted production SD remained removed and untouched.

The repaired installed-EQ → Direct fresh-bootstrap transaction had already committed successfully with root installer exit `0`. Independent read-only verification was then run from the same physical spare-SD state.

## Fresh-bootstrap verifier

`bash scripts/verify-fresh-bootstrap.sh --project-user "$USER" --project-dir "$PWD"`

Result:

- pinned Node 20.20.2 runtime and manifest: PASS;
- pinned Plexamp Headless 4.13.2 runtime and manifest: PASS;
- persistent Plexamp claim state: PASS;
- pinned NFC source/runtime/venv/unit: PASS;
- `/dev/i2c-1`: PASS;
- PN532 at bus 1 address `0x24`: PASS;
- Raspberry Pi DAC Pro `CARD=Pro`: PASS;
- Plexamp service active/enabled and local API reachable: PASS;
- NFC listener active/enabled and hardware imports: PASS;
- DAC managed boot configuration not required because accepted card is supplied by EEPROM/existing configuration.

Final result:

```text
Failures: 0
Warnings: 0
FRESH_BOOTSTRAP_VERIFY=PASS
```

Evidence:

`/home/andy/acp-phase7-spare-sd-20260815-171112/21-fresh-bootstrap-verify.txt`

## Direct appliance verifier

`bash scripts/verify-appliance.sh --audio direct --weather-observations ecowitt-push --project-user "$USER" --project-dir "$PWD"`

Result:

- dashboard, kiosk, AirPlay wrappers/metadata, alarm helper, Shairport-name helper and mixer helper: PASS;
- Direct route SHA-256: `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`;
- EQ installed marker absent as required for Direct: PASS;
- Ecowitt live provider and Open-Meteo forecast provider configuration: PASS;
- no Weather API secret stored in `config.json`: PASS;
- Plexamp, Shairport Sync, dashboard and AirPlay metadata services active/enabled: PASS;
- mixer runtime, dashboard API, Weather API, truthful Direct EQ API and mixer API: PASS.

Final result:

```text
Failures: 0
Warnings: 0
APPLIANCE_VERIFY=PASS
```

Evidence:

`/home/andy/acp-phase7-spare-sd-20260815-171112/22-direct-appliance-verify.txt`

## Acceptance position

The guarded EQ → Direct convergence and both independent software/hardware verifiers have now passed on the real spare-SD appliance. The next gate is a small residue check for the canonical Direct route, absent EQ marker, and absent `snd_aloop`, followed by physical Direct appliance behaviour and Weather/Settings acceptance. No manual EQ uninstall or fix-forward was used.

PR #2 remains Draft/open/unmerged until explicit approval.
