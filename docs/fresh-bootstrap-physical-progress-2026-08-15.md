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

## Current physical acceptance position

The spare-SD appliance now has a successfully installed and locally claimed pinned Plexamp runtime, physically accepted PN532 and DAC hardware, and the paired Trixie Python environments. The next run should pull the documented NFC-venv correction, repeat the idempotent fresh Direct bootstrap, pass the NFC service owner, then reach the full host preflight and guarded whole-application transaction for the first time.

The production SD card remains the untouched recovery path. PR #2 remains Draft/open/unmerged until explicit approval.
