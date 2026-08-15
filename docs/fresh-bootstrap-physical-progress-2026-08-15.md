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

## Correction prepared

Commit `1ca97d345ddb3caa2f1123db89146246101e9631` corrects the fresh-runtime transaction ordering:

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

## Current physical acceptance position

The next spare-SD run should repeat the guarded fresh Direct installer from the root. Package, venv, I2C, PN532 and DAC stages are expected to be idempotent. If the corrected Plexamp transaction succeeds on the real Pi, the next deliberate bootstrap checkpoint is expected to be exit `76`, `PLEXAMP_RUNTIME=CLAIM-REQUIRED`, followed by local interactive Plexamp claim/name commissioning.

The production SD card remains the untouched recovery path. PR #2 remains Draft/open/unmerged until explicit approval.
