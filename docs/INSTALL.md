# A Clockwork Plex — installation

This guide is the normal end-to-end installation path for a new A Clockwork Plex appliance. It starts with a blank SD card and ends with the dashboard, Plexamp Headless, NFC, AirPlay, alarm-safe audio and the guarded three-band CamillaDSP equaliser installed as one appliance.

The engineering acceptance runbooks under `docs/` contain deeper verification and rollback evidence. **A normal installation does not require running those acceptance tests or plan-only passes.** If the installer reports an unexplained failure, stop there and diagnose it rather than continuing with unrelated manual fixes.

> **Current production candidate:** until PR #2 is explicitly approved and merged, install from the `feature/alarm-engine` branch. After release, the normal installation target will move to the released/default branch.

## 1. Hardware used by the validated appliance

The current physically validated target is:

- Raspberry Pi 4B;
- 64-bit Raspberry Pi OS with Desktop;
- Raspberry Pi Touch Display 2 (720×1280 native, used in 1280×720 landscape orientation on the validated appliance);
- Raspberry Pi DAC Pro, expected by ALSA as `CARD=Pro`;
- PN532 NFC hardware configured for I2C, expected on bus 1 at address `0x24`;
- network access for package installation and the pinned Plexamp/Node/CamillaDSP downloads.

Connect HATs and internal hardware with the Pi powered off. Do not run `rpi-update`, change Pi bootloader release channels, write HAT EEPROMs or perform other experimental/pre-release firmware updates as part of an A Clockwork Plex installation.

## 2. Install Raspberry Pi OS

Use Raspberry Pi Imager and select the current **64-bit Raspberry Pi OS with Desktop** image.

In Imager's OS customisation, set the normal appliance values before writing the card:

- hostname, for example `a-clockwork-plex` (a test appliance may use `plexamp-test`);
- username and password;
- Wi-Fi SSID/password and Wi-Fi country if Wi-Fi is used, or use wired Ethernet;
- locale, keyboard and timezone;
- enable SSH if you want to install/administer the appliance remotely.

Write the image and allow Raspberry Pi Imager to verify it.

On first boot, let Raspberry Pi OS finish its first-boot setup and reach the desktop. The dashboard kiosk starts inside the logged-in desktop session, so enable **desktop auto-login** for the appliance user if the OS image has not already done so. Use Raspberry Pi Configuration / Control Centre or `raspi-config` for that OS setting.

### Update the fresh OS before installing A Clockwork Plex

A Clockwork Plex deliberately does **not** perform a blanket Raspberry Pi OS upgrade. It installs the packages it owns, but routine operating-system maintenance stays under the operator's control.

On a newly imaged Pi, apply the normal supported Raspberry Pi OS updates before installing the appliance:

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

Do not use `rpi-update` for this. Normal APT updates are the supported Raspberry Pi OS maintenance path; `rpi-update` is intended for experimental/pre-release firmware and specific engineering cases.

### Raspberry Pi Touch Display 2 setup

For the validated 720×1280 Raspberry Pi Touch Display 2, configure the desktop before installing the kiosk:

- set the display to the desired **landscape 1280×720** orientation;
- in **Control Centre → Appearance**, use the **Medium** desktop/default size;
- set **screen scaling to 1.5×**;
- use the **Dark** theme if you want the same validated desktop appearance;
- use **Multitouch** touchscreen behaviour rather than mouse emulation.

These values make normal desktop applications and commissioning screens usable on the small panel while preserving the proportions used during A Clockwork Plex physical validation. Kiosk mode subsequently occupies the dashboard display itself.

### Enable VNC for easier commissioning

Enabling VNC is strongly recommended during initial setup, especially for entering Plex credentials and other text that is awkward on the small touchscreen.

In Raspberry Pi OS:

1. open **Preferences → Control Centre**;
2. open **Interfaces**;
3. enable **VNC**;
4. connect from another computer with a compatible VNC client when you need a full keyboard/mouse during commissioning.

VNC is an administration convenience; A Clockwork Plex does not require it for normal bedside operation.

### Chromium commissioning tweak

Before kiosk installation, it is useful to give Chromium a little more usable space on the Touch Display 2:

1. open Chromium;
2. open **Settings → Appearance**;
3. turn **Use system title bar and borders** **off**.

The dashboard kiosk launch overrides the normal browser chrome anyway, but disabling the system title bar/borders makes ordinary Chromium windows roomier while you are claiming Plexamp or commissioning the appliance.

If the attached display needs a different supported rotation or resolution, set that through Raspberry Pi OS display settings before installing the appliance.

Do not manually install Plexamp, Node, Shairport Sync, CamillaDSP, NFC Python libraries, ALSA routes, DAC overlays or A Clockwork Plex services; those belong to the installer.

## 3. Obtain A Clockwork Plex

Open a terminal on the Pi or connect over SSH/VNC.

The source tree must exist before its installer can own the rest of the package baseline. Raspberry Pi OS with Desktop normally provides the required download tools; if `git` or `curl` is missing, install only those bootstrap tools first:

```bash
sudo apt update
sudo apt install -y git curl
```

Clone the current production-candidate branch:

```bash
cd ~
git clone --branch feature/alarm-engine \
  https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
```

Do not create a Python virtual environment or install `requirements.txt` manually. The fresh-appliance installer owns the verified application and NFC environments.

## 4. Fetch the accepted CamillaDSP artifact

The equaliser installer accepts only the pinned CamillaDSP 4.1.3 artifact. Fetch and verify it with the repository helper:

```bash
cd ~/A-Clockwork-Plex
bash scripts/fetch-camilladsp-4.1.3.sh \
  --activate \
  --confirm FETCH-CAMILLADSP-4.1.3
```

A successful fetch prints `CAMILLA_ARTIFACT=PASS` (or `PASS-EXISTING`) and the binary path. With the default destination, use:

```bash
CAMILLA_BINARY="$HOME/.cache/a-clockwork-plex/artifacts/camilladsp-4.1.3/camilladsp"
```

## 5. Install the appliance

For the validated configuration — Ecowitt Push for live observations, Open-Meteo forecasts and the guarded EQ audio profile — run:

```bash
cd ~/A-Clockwork-Plex

bash install.sh \
  --fresh-bootstrap \
  --audio eq \
  --weather-observations ecowitt-push \
  --project-user "$USER" \
  --camilladsp-binary "$CAMILLA_BINARY" \
  --apply \
  --confirm APPLY-A-CLOCKWORK-PLEX
```

Run the installer as the normal appliance user, **not** with `sudo`. It uses narrowly scoped `sudo` operations internally where root ownership is required.

The fresh installer owns the package/venv baseline, Pi hardware commissioning, pinned Plexamp Headless and Node runtime, NFC listener, dashboard/kiosk integration, Direct alarm-safe audio baseline, guarded EQ promotion, restricted helpers, AirPlay integration and the final appliance verification.

### If the installer asks for a reboot

Hardware commissioning may deliberately stop with:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
```

Reboot normally:

```bash
sudo reboot
```

After reconnecting, return to `~/A-Clockwork-Plex`, recreate the `CAMILLA_BINARY` shell variable if necessary, and rerun the **same install command**. Completed idempotent stages are checked and retained; do not manually reproduce them.

### If Plexamp needs claiming

A new appliance has no Plexamp account state, so the installer may deliberately stop with:

```text
PLEXAMP_RUNTIME=CLAIM-REQUIRED
```

The installer prints a `CLAIM_COMMAND`. Run that command locally on the Pi. When Plexamp asks for a claim code, obtain a fresh code from `https://plex.tv/claim`, enter it directly into Plexamp, then give the player its desired name. Wait for Plexamp to confirm successful startup, press `Ctrl-C`, return to `~/A-Clockwork-Plex`, and rerun the same appliance install command.

VNC is particularly useful for this commissioning step because it provides a full keyboard without consuming most of the Touch Display 2 with the on-screen keyboard.

Do not put a Plex claim code into installer arguments, shell scripts, logs or repository files.

### Successful completion

The final install should end with:

```text
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

An unexplained non-zero exit is not a cue to keep installing components by hand. Stop at that failed owner and diagnose it.

## 6. Reboot into the appliance

After the installer commits successfully, reboot once:

```bash
sudo reboot
```

After the desktop session opens, the A Clockwork Plex kiosk should start automatically and display the dashboard. The local dashboard is served on port `8088`.

## 7. First-time configuration

Use **Settings** in the dashboard for ordinary appliance configuration rather than editing `config.json` directly. Typical first-time setup includes:

- General: appliance name and time/display preferences;
- Display: brightness, night behaviour and presentation;
- Audio: Music Master, source trims, Maximum Alarm Volume and EQ preferences;
- AirPlay: receiver name;
- Alarms: alarm definitions and the explicit scheduled-alarm sound safety controls;
- Weather: station/location details, units, forecast preferences and observation source.

For the validated Ecowitt configuration, point the Ecowitt custom-upload destination at the appliance's `/ecowitt` endpoint using the Pi's LAN address/hostname.

Weather Underground can be commissioned from **Settings → Weather** for supplemental historical rainfall without exposing its API key to browser state or `config.json`. Enter credentials through the Settings credential controls; do not add the key to installer command lines or repository files.

## 8. NFC albums

The installed NFC listener expects the validated PN532 I2C reader on bus 1 at `0x24`. Existing compatible album tags can then trigger Plexamp playback. Tag creation/library workflow is documented separately by the Plexamp NFC project.

## 9. Updating an installed appliance

For a later source update on the same branch/release:

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
```

Then rerun the same guarded appliance installer for the desired profile. The installer is designed to converge an already-installed appliance rather than requiring a manual component-by-component reinstall.

## Development install

The manual `python3 -m venv`, `pip install -r requirements.txt`, `config.example.json` and `python app/runner.py` workflow is for development only. It is **not** the appliance installation procedure.
