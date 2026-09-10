# Fresh appliance physical acceptance runbook

**Status:** final Phase 7 release-candidate clean-room procedure  
**Branch under test:** `feature/alarm-engine`  
**Updated:** 3 September 2026

## Purpose

Prove that a completely fresh **spare SD card** can become a working A Clockwork Plex appliance by following the public installation path in `docs/INSTALL.md` and running **`bash setup.sh`**, without reconstructing the appliance from engineering-only component commands.

Earlier staged Direct/EQ acceptance, temporary lower-level installer commands and physical experiments are preserved in `docs/fresh-bootstrap-physical-progress-2026-08-15.md`, `docs/eq-to-direct-physical-verification-2026-08-17.md` and `docs/weather-physical-followup-2026-08-17.md`. They are evidence, not the final clean-room procedure.

This runbook deliberately tests the release-candidate contract that a new owner should actually use:

```text
fresh Raspberry Pi OS
  -> clone repository
  -> bash setup.sh
  -> operator-controlled reboot only if requested
  -> integrated CamillaDSP acquisition
  -> integrated Plexamp claim launch/resume
  -> setup-owned Plexamp commissioning
  -> Plexamp browser sign-in/library verification
  -> Settings commissioning
  -> playback/Weather/NFC/alarm checks
  -> reboot + formal verifiers
  -> repeat bash setup.sh
```

`setup.sh` is the public human-facing installer. It delegates guarded mutation to `appliance-installer.sh`. The obsolete root `install.sh` name is not part of this procedure and must not exist in the release candidate.

---

# 0. Stop rules and accepted identities

**Stop on the first unexplained failure.** Preserve evidence and diagnose the failed owner; do not fix forward blindly.

- Power down before reseating hardware or SD cards.
- Remove the **accepted production SD card** before the spare card is inserted.
- **Label/store that card safely. Do not reformat it for this test.**
- Use a **test hostname** distinct from production, for example `plexamp-test`.
- Run `setup.sh` as the normal appliance user, never with `sudo`.
- Do not update Pi EEPROM/bootloader, HAT EEPROM, audio-HAT firmware or other hardware firmware.
- Never put a Weather Underground API key, Plex claim code or account password in chat, evidence, `config.json`, command-line arguments or shell history.
- Do not substitute unverified Plexamp, Node or CamillaDSP artifacts.
- PR #2 remains Draft/open/unmerged throughout this procedure.

| Item | Accepted value |
|---|---|
| Fresh alarm-safe Direct route | `654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9` |
| EQ split-bus route | `1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9` |
| CamillaDSP executable | `4.1.3` aarch64, SHA-256 `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa` |
| CamillaDSP official archive | SHA-256 `d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a` |
| Managed CamillaDSP unit | `a-clockwork-plex-camilladsp.service` |
| Plexamp Headless | `4.13.2`, SHA-256 `86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041` |
| Node | `20.20.2` linux-arm64, SHA-256 `73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71` |
| PN532 | I2C bus `1`, address `0x24` |
| DAC | Raspberry Pi DAC Pro, ALSA `CARD=Pro` |
| DAC fallback overlay | `rpi-dacpro` only when commissioning requires it |
| Guarded engine confirmation | `APPLY-A-CLOCKWORK-PLEX` — owned internally by `setup.sh`; not a normal-user command |

The historical Phase 6 Direct rollback `08d00093...` remains evidence only, not the fresh Direct target.

---

# 1. Prepare a genuinely fresh spare SD

1. Shut the working appliance down normally and disconnect power.
2. Remove the accepted production SD card and store it safely.
3. Write current 64-bit Raspberry Pi OS with Desktop to the spare card.
4. In Raspberry Pi Imager configure the intended normal appliance username, network, locale/timezone and SSH if wanted.
5. Use a non-production test hostname.
6. Boot the fresh card with the normal A Clockwork Plex hardware attached.

Do not manually preinstall Plexamp, NFC libraries, Shairport routing, CamillaDSP or A Clockwork Plex services.

Record the fresh baseline:

```bash
hostname -s
id
uname -m
cat /etc/os-release
```

Require Raspberry Pi OS on `aarch64`.

---

# 2. Clone the exact release-candidate source

```bash
cd ~
git clone --branch feature/alarm-engine https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
git branch --show-current
git rev-parse HEAD
git status --short
```

Require:

- branch `feature/alarm-engine`;
- the exact green head selected for the clean-room run;
- a clean checkout;
- `setup.sh` and `appliance-installer.sh` present;
- no root `install.sh`.

Record the tested SHA somewhere outside the repository, for example:

```bash
EVIDENCE="$HOME/acp-phase7-final-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"
git rev-parse HEAD > "$EVIDENCE/00-tested-head.txt"
printf '%s\n' "$EVIDENCE" > "$HOME/.acp-phase7-final-evidence-path"
```

Do **not** pipe the interactive claim portion of setup through a general transcript that could capture secrets typed at a prompt.

---

# 3. Follow the public installation guide

Read `docs/INSTALL.md` from top to bottom and perform its Raspberry Pi OS/display preparation exactly as written. The runbook is an acceptance checklist; `INSTALL.md` remains the operator installation authority.

The public installation command is:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

Do not replace this with direct component installers merely because they exist in the repository.

### Controlled reboot checkpoint

If hardware commissioning requires a reboot, setup may surface:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
```

This corresponds to the guarded engine's `--fresh-bootstrap` **fresh stage-zero preflight** and exit `75` reboot-required contract. Reboot manually; the installer never reboots the Pi itself. After login, return to the repository and run:

```bash
bash setup.sh
```

again.

Any unexplained nonzero exit is a failure: stop and preserve the visible output before changing anything.

---

# 4. Verify integrated artifact acquisition and Plexamp claim handoff

The final public setup path must acquire/verify the pinned CamillaDSP 4.1.3 artifact itself. The operator must **not** have to run `scripts/fetch-camilladsp-4.1.3.sh`, supply `--camilladsp-binary`, or calculate a path by hand.

A new unclaimed player may make the lower-level guarded engine report its internal exit `76` / `PLEXAMP_RUNTIME=CLAIM-REQUIRED` state, but `setup.sh` owns the public response: it automatically launches the installed Plexamp Headless process and allows the claim code to be entered directly into Plexamp. The operator must **not** have to run:

```text
/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node js/index.js
```

manually.

Obtain a fresh claim code from `https://plex.tv/claim` only when Plexamp asks for it. Enter it directly into the local Plexamp prompt. Do not save the code in the evidence directory. The **player name entered during this claim becomes the appliance's reset baseline once setup completes its commissioning step**.

After claim completes, `setup.sh` must resume/converge the guarded install rather than asking the operator to reconstruct the remaining stages. Once the guarded appliance install commits, setup must also capture/verify the claimed player name baseline and resolve the exact **`A Clockwork Plex - Plexamp`** device from Plexamp's live output list. It must not hard-code or export a device UUID.

For later identity evidence, once setup has completed:

```bash
CAMILLA="$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"
"$CAMILLA" --version | tee "$EVIDENCE/10-camilladsp-version.txt"
sha256sum "$CAMILLA" | tee "$EVIDENCE/11-camilladsp-sha.txt"
```

Require CamillaDSP 4.1.3 and executable SHA `e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa`.

---

# 5. Finish Plexamp browser commissioning and verify setup-owned output

After setup has completed its own Plexamp commissioning:

1. open the Plexamp Headless browser interface;
2. sign into the Plex account if required;
3. choose the intended music library;
4. **verify** the audio output is already **`A Clockwork Plex - Plexamp`**;
5. verify Plexamp is **not** left on **Follows system output**.

The browser UI remains the owner of account sign-in and library selection. It is no longer the normal owner of the appliance audio-route choice: `setup.sh` resolves and verifies the managed output through Plexamp's loopback settings API. If the expected output is not selected after successful setup, treat that as a commissioning failure and diagnose/re-run `bash setup.sh` rather than silently creating a second manual source of truth.

VNC is recommended for account/password-manager use and long Settings values.

Record only non-secret commissioning outcomes, not credentials, player-setting values or device UUIDs.

---

# 6. Commission Weather Underground through Settings

Use **Settings → Weather**. Do not put the API key on a command line.

1. Select Weather Underground PWS as the observation source.
2. Enter the station ID.
3. Use **Set API key** for first commissioning; use **Replace API key** only when deliberately changing an existing credential.
4. Use **Test connection**.
5. Save/allow unified Settings autosave as normal.
6. Confirm the dashboard/Weather page fills with WU current observations.

The browser must never receive the secret back. Persistent managed storage is:

```text
/etc/default/a-clockwork-plex-weather
```

with root ownership/mode `0600`. Sanitized diagnostic/config output must continue to report:

```text
WU_CONFIG_SECRET_FIELDS=NONE
```

If this appliance also receives the Ecowitt custom push, confirm only fresh indoor temperature/humidity supplement the WU display and WU remains outdoor authority. Do not redirect the one working Ecowitt custom destination merely to manufacture a WU-only test; source expiry coverage already protects the no-supplement path and another appliance can confirm it later.

---

# 7. Functional appliance acceptance

Confirm the complete appliance, not just service status.

### Clock / presentation

- selected Version 3 fourteen-segment geometry is visible and stable;
- numeric `0`, capital `O` and `W` match the accepted mappings;
- alarm annunciator behaves according to the configured 12-hour/any-future rule;
- final accepted daytime theme is present;
- Classic/Astronomy night behavior remains correct;
- touch-to-wake/dimming and navigation remain usable.

### Weather

- WU current values appear;
- Clock rain summary appears;
- Weather current rain shows Rain rate, Hourly rain, Rain today and Event rain when applicable;
- Rainy Day Fund/current rain share the accepted horizontal scroll behavior;
- max gust today appears when data has accumulated;
- no secret is exposed in Settings/API output.

### Plexamp / EQ

- Plexamp plays stable stereo audio through `A Clockwork Plex - Plexamp`;
- Music Master changes Plexamp loudness;
- Bass/Mid/Treble adjustments are audible;
- EQ bypass works;
- canonical Camilla service is active.

### AirPlay

- the configured receiver appears on the iPhone;
- AirPlay takes over correctly and produces audio through the EQ path;
- normal handoff does not restart the audio services.

### NFC

- one known-good NFC album tag starts Plexamp playback;
- dashboard changes to the Plexamp surface;
- immediate repeat-tag debounce remains correct.

### Real scheduled alarm

With Plexamp playing:

1. allow a real scheduled alarm to fire;
2. confirm it pauses/takes audio ownership from Plexamp;
3. confirm the configured Fade start → target ramp is audible and Maximum Alarm Volume remains the ceiling;
4. Snooze it;
5. allow the re-ring and confirm it starts a fresh fade cycle;
6. Dismiss it.

Music Master must not silence the alarm lane.

Stop on any unexplained regression.

---

# 8. Reboot and run the formal verifiers

Perform one deliberate full reboot after functional commissioning. Confirm the kiosk returns normally, then:

```bash
cd ~/A-Clockwork-Plex
EVIDENCE="$(cat "$HOME/.acp-phase7-final-evidence-path")"

bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/20-post-reboot-bootstrap-verifier.txt"

bash scripts/verify-appliance.sh \
  --audio eq \
  --weather-observations weather-underground \
  --project-user "$USER" \
  --project-dir "$PWD" \
  | tee "$EVIDENCE/21-post-reboot-appliance-verifier.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/22-post-reboot-audio-verifier.txt"
```

The appliance verifier checks the commissioned WU credential through the restricted root-owned helper's presence-only `status` action. It must not be given `--weather-api-key-file`, a secret-bearing environment override or any other copy of the API key for this clean-room proof; only `WEATHER_SECRET_CONFIGURED=0|1` is exposed by that helper.

Require:

```text
FRESH_BOOTSTRAP_VERIFY=PASS
APPLIANCE_VERIFY=PASS
```

and an audio verifier PASS.

Confirm the canonical managed service, not a generic Camilla unit:

```bash
systemctl is-active a-clockwork-plex-camilladsp.service
systemctl is-enabled a-clockwork-plex-camilladsp.service
sha256sum /etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
```

Expected EQ route SHA:

```text
1bc69f106768d438d1fdb9d321fdb597ee8c83339c5fa89187935636f9c08bd9
```

---

# 9. Repeat the public setup command — final idempotence proof

Do **not** rerun an engineering component or the guarded engine directly. From the already-installed, claimed and configured appliance run exactly:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

Require:

- no renewed Plexamp claim requirement;
- no unnecessary reboot checkpoint;
- the captured Plexamp player-name reset baseline is not silently replaced by a later rename;
- the managed `A Clockwork Plex - Plexamp` output is still verified;
- no loss of WU configuration or managed credential;
- no route/EQ ownership drift;
- no duplicate services/helpers/autostart entries;
- dashboard, Plexamp, AirPlay, NFC and EQ remain functional afterwards.

Then rerun the formal verifiers and save their non-secret output:

```bash
EVIDENCE="$(cat "$HOME/.acp-phase7-final-evidence-path")"

bash scripts/verify-fresh-bootstrap.sh \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/30-repeat-bootstrap-verifier.txt"

bash scripts/verify-appliance.sh \
  --audio eq --weather-observations weather-underground \
  --project-user "$USER" --project-dir "$PWD" \
  | tee "$EVIDENCE/31-repeat-appliance-verifier.txt"

bash scripts/audio/verify-audio.sh \
  | tee "$EVIDENCE/32-repeat-audio-verifier.txt"
```

---

# 10. Confirm normal operation leaves the checkout clean

After Weather updates, playback, alarm use, reboot and repeat setup:

```bash
cd ~/A-Clockwork-Plex
git status --porcelain | tee "$EVIDENCE/40-git-status.txt"
```

Expected result: no tracked modifications caused by normal runtime/generated state.

If legitimate runtime state dirties the checkout, fix its storage/ignore contract before release rather than accepting a permanently dirty install.

---

# 11. Commit the final physical result

Create/update final dated evidence in the repository containing only non-secret facts:

- exact tested Git commit;
- Raspberry Pi OS/architecture/hardware identities;
- whether a hardware reboot checkpoint occurred;
- integrated Camilla acquisition result;
- integrated Plexamp claim/resume result;
- setup-owned Plexamp player-name/output commissioning and browser verification result;
- WU Settings commissioning result without key material;
- Clock/daytime/night presentation result;
- Plexamp/EQ, AirPlay, NFC and real scheduled-alarm results;
- post-reboot verifier results;
- repeat `setup.sh` idempotence result;
- clean-checkout result;
- any remaining explicitly deferred non-blocking check.

**Phase 7 does not close until that physical result is committed and the active roadmap is updated.** PR #2 remains Draft/open/unmerged until release hygiene is complete and the owner explicitly approves making it ready/merging it.