# Fresh appliance bootstrap physical progress — 2026-08-15

Test target: spare SD card on the real Raspberry Pi appliance hardware, hostname `plexamp-test`, Raspberry Pi OS / Debian 13 (Trixie), 64-bit `aarch64`.

This file records Phase 7 physical bootstrap evidence while the accepted production SD card remains removed and untouched.

## Attempt 1 — Trixie inherited Python metadata

The package owner installed the additive fresh-Pi prerequisites and built both candidate Python environments. The NFC venv intentionally uses `--system-site-packages` so Raspberry Pi OS `python3-lgpio` is visible.

A raw whole-environment `pip check` then reported nine unrelated Debian system-site metadata issues (`types-flask-*`, `types-tree-sitter-languages`, `apt-listchanges`, `types-click-default-group`, and `types-seaborn`). The installer stopped before hardware, Plexamp, NFC-service, or application commissioning and restored the paired venv prestate.

The owner was corrected so NFC dependency checking remains fail-closed for the recursive listener dependency graph while unrelated inherited Debian distributions are reported as informational. The main isolated application venv retains a whole-environment `pip check`.

Checkpoint #26 is recorded in `docs/eq-audio-installer-roadmap.md`.

## Attempt 2 — hardware passed; fresh Plexamp unit verification ordering exposed

After pulling checkpoint #26, the rerun established the package/venv baseline successfully:

- main application venv: PASS;
- NFC venv owned dependency graph: PASS, 23 owned distributions;
- the same nine Trixie inherited issues were reported informationally;
- Shairport Sync and all other fresh prerequisites were already present.

The real hardware commissioning then passed:

- Raspberry Pi I2C enabled and live;
- PN532 detected at I2C bus 1 address `0x24`;
- Raspberry Pi DAC Pro exposed as ALSA card id `Pro`;
- no DAC boot-config mutation was required;
- no firmware, bootloader, or HAT EEPROM update was performed.

The post-hardware/player-pending preflight also passed with only the expected Ecowitt site-commissioning warning.

The Plexamp owner downloaded and SHA-verified both pinned production artifacts:

- Node 20.20.2 linux-arm64 SHA-256 `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71`;
- Plexamp Headless 4.13.2 SHA-256 `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041`.

It then stopped before runtime promotion because `systemd-analyze verify` resolved the rendered `ExecStart` path while the fresh pinned Node candidate was still staged rather than present at its final `/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node` path.

## Correction prepared after Attempt 2

Commit `1ca97d345ddb3caa2f1123db89146246101e9631` corrected the fresh-runtime transaction ordering:

1. stage and cryptographically verify Node and Plexamp before mutation;
2. open the runtime/unit rollback transaction;
3. promote both runtime candidates;
4. verify the activated runtime files, versions, and manifests;
5. run `systemd-analyze verify` while the exact rendered `ExecStart` and `WorkingDirectory` paths exist;
6. install the verified unit only after that passes;
7. retain exact rollback on any failure.

The correction also cleans staging parents after safe pre-transaction exits and after successful/rolled-back transactions, while deliberately preserving a staging directory if it still contains a `.previous` rollback payload after an unexpected post-mutation exit.

Focused validation passed before the patch commit was pushed:

- `bash -n scripts/install-plexamp-runtime.sh`;
- `python3 -m unittest tests.test_plexamp_runtime_installer -v`;
- regression coverage confirms systemd verification occurs after activated-runtime checks and before unit installation;
- fresh claim-required and injected-rollback fixtures leave no new staging parents behind.

## Attempt 3 — Plexamp claim/resume passed; standard NFC venv interpreter layout exposed

After pulling the corrected Plexamp runtime head, the real spare-SD install repeated package, venv and hardware acceptance successfully. The corrected Plexamp transaction then reached the intended explicit local claim boundary:

- pinned Node 20.20.2 installed under `/opt/a-clockwork-plex/node-v20.20.2-linux-arm64`;
- pinned Plexamp Headless 4.13.2 installed under `/home/andy/plexamp`;
- `plexamp.service` installed but deliberately left inactive/disabled before claim;
- root installer exited `76` with `PLEXAMP_RUNTIME=CLAIM-REQUIRED`.

Plexamp was then started locally in the foreground using the exact pinned Node executable. The fresh claim code and player name were entered only on the Pi. Plexamp reported `Plexamp is now signed in and ready!`; persistent state appeared at `/home/andy/.local/share/Plexamp/Settings`. Post-claim evidence confirmed Node `v20.20.2`, `PLEXAMP_SETTINGS=PRESENT`, and a loaded but still inactive/disabled `plexamp.service`, as intended before root-installer resume.

On the resumed root installer run:

- package/main/NFC venv bootstrap: PASS;
- PN532 `0x24`: PASS;
- `CARD=Pro`: PASS;
- post-hardware/player-pending preflight: PASS;
- claimed Plexamp runtime repair/resume: PASS;
- `plexamp.service` was enabled and the pinned runtime owner reported `PLEXAMP_RUNTIME=PASS` and port `32500`.

The installer then reached the guarded NFC listener owner for the first time and stopped before any NFC service or application transaction because that owner required:

```text
[[ -x "$NFC_PYTHON" && ! -L "$NFC_PYTHON" ]]
```

A Python `venv` created by the paired package owner normally exposes `bin/python` as a symlink to the distribution interpreter. The same live interpreter had just been executed successfully by the package owner after the paired venv swap, including `lgpio`, Blinka/busio, requests and PN532 imports. The NFC service owner therefore rejected a healthy, standard venv layout rather than a broken dependency state.

The root wrapper maps NFC-owner failure through its generic fail-closed path (`exit 2`). The shell transcript displayed a stale `76` because `rc` had not been refreshed from the new installer pipeline after the previous claim-required run; this was evidence-command bookkeeping and did not alter installer behaviour.

## Correction prepared after Attempt 3

The NFC owner now validates the actual boundary it depends on instead of banning Python's standard venv interpreter symlink:

- the `nfc-venv` directory itself must be a real directory, not a symlink;
- `pyvenv.cfg` must be a real file, not a symlink;
- `bin/python` must be executable, but may use the normal venv symlink layout;
- the interpreter must prove `sys.prefix != sys.base_prefix`;
- the owner re-imports `lgpio`, `board`, `busio`, `requests` and `PN532_I2C` before installing the unit;
- the existing pinned NFC runtime/display-helper and systemd transaction checks remain unchanged.

Regression coverage explicitly prevents reintroducing the `! -L "$NFC_PYTHON"` guard and constructs a real Python venv to prove the runtime-prefix check accepts standard interpreter layout.

Tests #3368 passed on source/test head `40c179de6a80cf6b91e4e0b5d308264a6e871b1f`: dependency setup, compile, JavaScript/page wiring, shell syntax, unit tests and diagnostics upload all completed successfully.

## Attempt 4 — NFC and full preflight passed; protected sudoers verification exposed

After pulling the documented NFC correction at `ac623156612030cf154e86c9851ce34759402ddf`, the real spare-SD Direct rerun advanced through every fresh-bootstrap owner and entered the whole-application transaction for the first time.

Fresh/bootstrap evidence:

- package/artifact availability: PASS;
- fresh stage-zero preflight: PASS with only the expected Ecowitt site-commissioning warning;
- paired main/NFC venv bootstrap: PASS;
- NFC owned dependency graph: PASS, 23 owned distributions; the same nine unrelated inherited Trixie metadata issues remained informational;
- PN532 I2C bus 1 address `0x24`: PASS;
- Raspberry Pi DAC Pro `CARD=Pro`: PASS;
- DAC boot config remained untouched because the accepted card was already exposed;
- Plexamp Headless 4.13.2 / Node 20.20.2 claimed-runtime resume: PASS;
- guarded `nfc-listener.service` install/enable: PASS;
- full mandatory host preflight: PASS with the expected Ecowitt warning only.

The guarded whole-application transaction then physically exercised these stages successfully:

- Ecowitt-push observation-provider configuration: PASS;
- dashboard service + Chromium kiosk integration: PASS;
- alarm-safe Direct route SHA `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`: PASS.

The transaction stopped at restricted helper packaging. The helper installer had already installed the helper and sudoers candidates through its root-aware write path, but its post-install verification attempted to inspect all six managed targets as the normal project user. On a real Raspberry Pi OS host `/etc/sudoers.d` is deliberately protected, so an ordinary-user `[[ -f ... ]]`, `stat`, or `grep` cannot reliably traverse/read those policy files even though the root-owned installation itself succeeded.

The failure remained safe:

- helper installer restored its captured helper pre-state;
- outer whole-application transaction restored the complete managed application pre-state;
- package/venv/Plexamp/NFC prerequisite baseline remained retained by explicit policy;
- AirPlay activation and the final whole-appliance verifier were not reached;
- authoritative root installer exit was `2`.

## Correction prepared after Attempt 4

The helper owner now verifies protected managed files through the same privileged boundary that owns their write and rollback paths:

- regular-file/non-symlink checks use `acp_run_root test`;
- mode checks use `acp_run_root stat`;
- required sudoers-rule checks use `acp_run_root grep`;
- every failed validation now emits the exact managed path/check rather than collapsing silently into the generic transaction failure;
- helper executables and sudoers policies retain their existing `0755` / `0440` requirements and exact restricted command rules.

Regression coverage prevents reintroducing ordinary-user post-install reads of protected helper policy files.

Tests #3374 / run `31898610147` passed on source/test head `302a1ee3979c34e404b280590e43450d7cd83c16`: dependency setup, compile, JavaScript/page wiring, shell syntax, all 1,598 unit tests and diagnostics upload completed successfully.

## Attempt 5 — helpers and AirPlay passed; final verifier repeated the protected sudoers assumption

After pulling documented head `a3e960e41f5ff741276bbf94516e2a7faf535057`, the next real spare-SD Direct rerun repeated the established package, paired venv, PN532, DAC Pro, claimed Plexamp, NFC-service and full-preflight gates successfully. The whole-application transaction then advanced beyond the previous blocker:

- Ecowitt-push configuration: PASS;
- dashboard service and kiosk integration: PASS;
- alarm-safe Direct route SHA `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9`: PASS;
- restricted appliance helper installation: PASS on the real protected filesystem, physically proving the Attempt 4 root-aware correction;
- guarded AirPlay/Shairport integration: PASS, including metadata service enablement.

The final whole-appliance verifier then reached its complete application/integration, audio, weather and live service/API checks. Every check passed except the two helper sudoers-file presence checks:

```text
FAIL  alarm-sudoers            missing/unsafe: /etc/sudoers.d/a-clockwork-plex-alarm-audio
FAIL  shairport-name-sudoers   missing/unsafe: /etc/sudoers.d/a-clockwork-plex-shairport-name
```

This was the same host-permission assumption in a second independent consumer: `scripts/verify-appliance.sh` used its ordinary-user `require_file` helper for paths beneath real `/etc/sudoers.d`. The helper installer had already proved those installed files through its root-aware verification, while the final verifier could not traverse the protected directory as `andy`.

The final commit gate correctly rejected the application transaction before commit. The complete application-managed pre-state was restored and the package/venv/Plexamp/NFC prerequisite baseline remained retained. The authoritative root installer exit was `2`.

## Correction prepared after Attempt 5

The independent verifier now has a narrowly scoped protected-file check:

- only the two protected sudoers-file checks use `require_protected_file`;
- production-root inspection is read-only and uses `sudo -n test -f` plus a non-symlink `test -L` rejection;
- alternate-root integration fixtures retain the ordinary unprivileged `require_file` path;
- all other verifier checks are unchanged;
- a failed or unavailable production protected-file inspection still fails closed rather than treating the policy as present.

Regression coverage now pins the two sudoers paths to the protected verifier and places a deliberately failing fake `sudo` first in `PATH` during an alternate-root fixture, proving non-production verification remains unprivileged. The existing static read-only verifier safety check remains green.

Tests #3380 / run `31899362927` passed on source/test head `ab6271f896464a7bbff37e74803fbfc3e18ec5a0`: dependency setup, compile, JavaScript/page wiring, shell syntax, the full unit suite and diagnostics upload completed successfully.

## Current physical acceptance position

The spare-SD appliance has now physically proven the fresh package/venv baseline, PN532 `0x24`, Raspberry Pi DAC Pro `CARD=Pro`, pinned/claimed Plexamp runtime, guarded NFC listener service, full mandatory host preflight, Weather configuration, dashboard/kiosk, alarm-safe Direct audio, restricted helper packaging and guarded AirPlay integration. The final whole-appliance verifier has also physically passed every check except the two protected sudoers reads that were corrected after Attempt 5, while its failed commit gate again proved complete application rollback.

The next run should pull the protected-verifier correction, repeat the idempotent fresh Direct bootstrap and reach the final `scripts/verify-appliance.sh` commit gate again. If the two protected sudoers checks now pass and no new host-only issue appears, this is the first run expected to commit the complete fresh Direct application transaction and return root installer exit `0`.

The production SD card remains the untouched recovery path. PR #2 remains Draft/open/unmerged until explicit approval.
