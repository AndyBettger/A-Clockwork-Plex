# A Clockwork Plex — installation

This is the normal end-to-end installation path for a new A Clockwork Plex appliance. It starts with a blank SD card and ends with the dashboard, Plexamp Headless, NFC, AirPlay, alarm-safe audio and the guarded three-band CamillaDSP equaliser installed as one appliance.

The engineering acceptance runbooks under `docs/` contain deeper verification and rollback evidence. **A normal installation does not require running those acceptance tests or plan-only passes.** If setup reports an unexplained failure, stop at that failed stage rather than continuing with unrelated manual fixes.

> **Current production candidate:** until PR #2 is explicitly approved and merged, install from the `feature/alarm-engine` branch. After release, the normal installation target will move to the released/default branch.

## 1. Hardware used by the validated appliance

The current physically validated target is:

- Raspberry Pi 4B;
- 64-bit Raspberry Pi OS with Desktop;
- Raspberry Pi Touch Display 2 (720×1280 native, rotated left for landscape use on the validated appliance);
- Raspberry Pi DAC Pro, expected by ALSA as `CARD=Pro`;
- PN532 NFC hardware configured for I2C, expected on bus 1 at address `0x24`;
- network access for package installation and the pinned Plexamp/Node/CamillaDSP downloads.

Connect HATs and internal hardware with the Pi powered off. Do not run `rpi-update`, change Pi bootloader release channels, write HAT EEPROMs or perform other experimental/pre-release firmware updates as part of an A Clockwork Plex installation.

## 2. Install and prepare Raspberry Pi OS

Use Raspberry Pi Imager and select the current **64-bit Raspberry Pi OS with Desktop** image.

In Imager's OS customisation, set the normal appliance values before writing the card:

- hostname, for example `a-clockwork-plex` (a test appliance may use `plexamp-test`);
- username and password;
- Wi-Fi SSID/password and Wi-Fi country if Wi-Fi is used, or use wired Ethernet;
- locale, keyboard and timezone;
- enable SSH if you want to install/administer the appliance remotely.

Write the image and allow Raspberry Pi Imager to verify it. On first boot, let Raspberry Pi OS finish its first-boot setup and reach the desktop. The dashboard kiosk starts inside the logged-in desktop session, so enable **desktop auto-login** for the appliance user if the OS image has not already done so.

### Update the fresh OS first

A Clockwork Plex deliberately does **not** perform a blanket Raspberry Pi OS upgrade. On a newly imaged Pi, apply the normal supported OS updates before installing the appliance:

```bash
sudo apt update
sudo apt full-upgrade
sudo reboot
```

Do not use `rpi-update` for this.

### Raspberry Pi Touch Display 2 setup

The validated 7-inch Raspberry Pi Touch Display 2 is a **720×1280 native portrait panel**. A Clockwork Plex uses it physically in landscape, so configure the desktop before installing the kiosk.

#### Rotate the display to landscape

1. Open **Preferences → Control Centre → Screens**.
2. Right-click the rectangle representing the Touch Display 2 (normally `DSI-1`).
3. Choose **Orientation → Left**.
4. Select **Apply**, then **OK** to keep the change.

If deciding which way is "Left" starts turning into a matrix transformation in your head, the approved low-computation method is to tip the actual device onto its left side first and see whether the picture ends up the right way round. Bonus internet points are available for avoiding unnecessary linear algebra. 😁

Do not change the panel to a made-up 1280×720 resolution: its native mode remains **720×1280**; orientation is what makes it landscape on the desk.

#### Set screen scaling to 1.5×

1. Stay in **Preferences → Control Centre → Screens**.
2. Right-click the Touch Display 2 / `DSI-1` rectangle.
3. Choose **Scaling → 1.5**.
4. Select **Apply**, then **OK**.

#### Set touchscreen mode to Multitouch — required

**This is required for A Clockwork Plex to work correctly as a touchscreen appliance.** Mouse-emulation mode can register taps, but it does not provide the native touch-and-drag behaviour required for scrolling the Weather page and Plexamp.

1. Stay in **Preferences → Control Centre → Screens**.
2. Right-click the Touch Display 2 / `DSI-1` rectangle.
3. Choose **Touchscreen → Mode → Multitouch**.
4. Select **Apply**, then **OK** if prompted.

Do not leave the Touch Display 2 in mouse-emulation mode for normal A Clockwork Plex use.

#### Set desktop size and appearance

1. Open **Preferences → Control Centre → Appearance**.
2. Under **Defaults**, choose **Medium** rather than Small or Large.
3. Select the **Dark** appearance/theme if you want the same desktop appearance used during physical validation.

### Enable VNC for commissioning

VNC is strongly recommended during initial setup. It makes Plex sign-in, password-manager credentials, Weather Underground station IDs/API keys and other long values much easier to enter by copy/paste from a full-size computer.

1. Open **Preferences → Control Centre → Interfaces**.
2. Enable **VNC**.
3. Connect from another computer with a compatible VNC client whenever a full keyboard/mouse is useful.

VNC is an administration convenience; A Clockwork Plex does not require it for normal bedside operation.

### Chromium commissioning tweak

Before kiosk installation, give ordinary Chromium windows a little more usable space on the Touch Display 2:

1. Open Chromium.
2. Open **Settings → Appearance**.
3. Turn **Use system title bar and borders** **off**.

Kiosk mode overrides ordinary browser chrome, but this makes Chromium roomier while commissioning Plexamp and the appliance.

Do not manually install Plexamp, Node, Shairport Sync, CamillaDSP, NFC Python libraries, ALSA routes, DAC overlays or A Clockwork Plex services; setup owns those components.

## 3. Obtain A Clockwork Plex

Open a terminal on the Pi or connect over SSH/VNC. Raspberry Pi OS with Desktop normally provides the required download tools; if `git` or `curl` is missing, install only those bootstrap tools first:

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

Do not create a Python virtual environment or install `requirements.txt` manually. Appliance setup owns the verified application and NFC environments.

## 4. Install the appliance

For the normal physically validated installation, run one command as the normal appliance user, **not** with `sudo`:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

`setup.sh` is the user-facing setup entry point. It automatically:

- acquires and verifies the pinned CamillaDSP 4.1.3 artifact for the EQ profile;
- invokes the guarded fresh-appliance installer with the accepted EQ profile;
- installs the package/application and NFC Python environments;
- commissions the Pi hardware/I2C/DAC path;
- installs the pinned Plexamp Headless and Node runtime;
- installs NFC, dashboard/kiosk, alarm-safe audio, EQ, AirPlay and restricted helpers;
- runs the installer's final appliance verification.

There is no CamillaDSP session variable to copy or preserve between commands.

### If setup asks for a reboot

Hardware commissioning may deliberately stop with:

```text
ROOT_INSTALL=REBOOT-REQUIRED
REBOOT_POLICY=OPERATOR-CONTROLLED
```

Run:

```bash
sudo reboot
```

After the Pi returns:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

Completed idempotent stages are checked and reused.

### If Plexamp Headless needs claiming

A new player has no Plex account claim state. When the guarded installer reaches that point, interactive `setup.sh` automatically launches the installed Plexamp Headless process for you; there is no separate claim command to copy and run.

1. On another device, open `https://plex.tv/claim` and obtain a fresh claim code.
2. Enter the code into the Plexamp prompt shown by setup.
3. Enter the player name when requested.
4. Wait for Plexamp to report that it has started successfully.
5. Press `Ctrl-C` once.

`setup.sh` checks that Plexamp saved its claim state and then resumes the guarded appliance installation automatically. The claim code is entered directly into Plexamp and is never accepted as a setup argument, environment variable or repository value.

### Successful completion

The underlying guarded installer should finish with:

```text
ROOT_INSTALL=COMMITTED
INSTALL_ROUTE=fresh-bootstrap
PACKAGE_VENV_BASELINE=RETAINED
APPLICATION_VERIFY=PASS
```

An unexplained non-zero exit is not a cue to install components manually. Stop there and diagnose the failed owner.

## 5. Reboot into the appliance

After setup commits successfully, reboot once:

```bash
sudo reboot
```

After desktop auto-login, the A Clockwork Plex kiosk should start automatically and display the dashboard. The local dashboard is served on port `8088`.

## 6. Finish Plexamp commissioning

Claiming Plexamp Headless from the command line establishes the headless player, but the first browser visit still needs ordinary Plexamp commissioning.

Open the Plexamp surface and:

1. sign into your Plex account if prompted;
2. select the Plex music library you want this appliance to use;
3. open Plexamp's audio-output settings;
4. select **`A Clockwork Plex - Plexamp`** as the audio output.

Do **not** leave Plexamp on its default **`Follows system output`** choice. The dedicated **A Clockwork Plex - Plexamp** output routes Plexamp through the appliance-managed Music Master/EQ audio path.

This is one of the places where VNC is especially useful. A long random password from a password manager is exactly what you should be using and exactly what nobody wants to peck into a 7-inch touchscreen one character at a time. Copy/paste it from the VNC-connected computer instead.

## 7. First-time A Clockwork Plex configuration

Use **Settings** in the dashboard for ordinary appliance configuration rather than editing `config.json` directly. Typical first-time setup includes:

- **General:** appliance name and time/display preferences;
- **Display:** brightness, night behaviour and presentation;
- **Audio:** Music Master, source trims, Maximum Alarm Volume and EQ preferences;
- **AirPlay:** receiver name;
- **Alarms:** alarm definitions and the explicit scheduled-alarm sound safety controls;
- **Weather:** station/location details, units, forecast preferences and observation source.

For Ecowitt Push, point the station's custom-upload destination at the appliance's `/ecowitt` endpoint using the Pi's LAN address/hostname.

Weather Underground can be selected and commissioned from **Settings → Weather**. Its API key remains write-only managed secret material and should be entered through the Settings credential controls, never into `config.json`, shell history or repository files. VNC is very convenient here too: copy/paste the station ID and API key rather than retyping them.

The same rule applies to other long commissioning values: use VNC/copy-paste where practical, but keep secrets in the UI or other intended secret-entry path rather than placing them in scripts or logs.

## 8. NFC albums

The installed NFC listener expects the validated PN532 I2C reader on bus 1 at `0x24`. Existing compatible album tags can then trigger Plexamp playback. Tag creation/library workflow is documented separately by the Plexamp NFC project.

## 9. Updating an installed appliance

For a later source update on the same branch/release:

```bash
cd ~/A-Clockwork-Plex
git pull --ff-only
```

Follow the release/update instructions for the installed version after pulling. Do not manually rebuild Python environments, audio routes or services component by component.

## Development install

The manual `python3 -m venv`, `pip install -r requirements.txt`, `config.example.json` and `python app/runner.py` workflow is for development only. It is **not** the appliance installation procedure.
