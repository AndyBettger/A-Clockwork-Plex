# Commissioned Pi Backup/Restore acceptance — 10 September 2026

## Scope

Physical acceptance for checkpoints #89/#90 schema-v2 portable Backup/Restore on the commissioned `plexamp-bedroom` appliance.

This record is intentionally chronological. PR #10 remains Draft/unmerged until the complete Backup → Reset → Restore cycle passes and the owner explicitly approves promotion/merge.

## Starting state

- Previous physically accepted #93 implementation head: `477bf0fd0cd7090a4d434816611f35673d83851e` on `feature/reset-defaults`.
- Working tree was clean.
- Appliance switched cleanly to `feature/backup-restore-completeness` at `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e`.

## Repeat setup / production convergence — PASS

Normal `bash setup.sh` completed successfully.

Key evidence:

- CamillaDSP 4.1.3 reused with `CAMILLA_ARTIFACT=PASS-EXISTING` and accepted executable SHA-256;
- commissioned Weather Underground profile and managed credential preserved;
- no APT package mutation required;
- paired main/NFC venv bootstrap passed;
- PN532 passed at I2C bus 1 / address `0x24`;
- DAC `CARD=Pro` passed with existing EEPROM/config; no firmware update;
- pinned Plexamp Headless 4.13.2 + Node 20.20.2 runtime owner passed while persistent Plexamp user state remained outside runtime replacement;
- NFC listener, restricted helpers and AirPlay integration converged successfully;
- existing EQ path remained on accepted split-bus route `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` and verified successfully;
- final whole-appliance verifier: **0 failures / 0 warnings**, `APPLIANCE_VERIFY=PASS`;
- application transaction committed with `APPLICATION_TRANSACTION=COMMITTED`, `ROOT_INSTALL=COMMITTED`, `APPLICATION_VERIFY=PASS`;
- Plexamp commissioning verification reported `changed_count: 0`, existing player-name baseline present, and managed `A Clockwork Plex - Plexamp` output already correct.

One transient dashboard `curl: (7)` occurred during the guarded service replacement/restart window; the dashboard owner subsequently verified successfully and the final independent verifier reported `dashboard-api PASS`, so this is not a final verification failure.

## Genuine reboot / bridge 1.5 production load — PASS

After a real `sudo reboot`:

- dashboard and embedded Plexamp appeared normal;
- branch remained `feature/backup-restore-completeness` at `fb5e77c3a3c8caf6e23ab9def68110dd9636be5e` with a clean working tree;
- complete `scripts/verify-appliance.sh --audio eq --weather-observations weather-underground ...` passed again with **0 failures / 0 warnings**;
- bridge manifest reported version **1.5.0**;
- content scripts were exactly `content.js`, `reset.js`, `portability.js`;
- web-accessible resources were exactly `native-reset.js`, `native-portability.js`, `home-portability-v2.js`;
- manifest contained no `permissions`, `host_permissions` or `background` authority;
- running Chromium kiosk used `/home/andy/.config/a-clockwork-plex/chromium-profile`;
- Chromium loaded the repository Plexamp bridge and Plexamp Search bridge through `--load-extension`;
- no Chromium `--remote-debugging-port` or `--remote-debugging-address` flags were present.

**Disposition:** production bridge 1.5.0 installation/reboot precondition is physically accepted. The remaining #89/#90 product gate is the deliberate normal-use configuration → schema-v2 Backup → backup inspection → accepted #93 Reset → schema-v2 Restore → physical/logical convergence cycle.
