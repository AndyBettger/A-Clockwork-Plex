# Fresh Raspberry Pi bootstrap ownership design

**Status:** Phase 7 staged implementation in progress  
**Last updated:** 13 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 remains Draft/open/unmerged until explicit owner approval.

## Goal

A newly imaged Raspberry Pi OS installation must be convertible into the complete
A Clockwork Plex appliance without manually installing Plexamp Headless, the NFC
listener, dashboard dependencies, AirPlay packages or appliance services first.

The reasonable operator baseline is deliberately small:

- assemble the intended Pi, display, DAC HAT and PN532 HAT;
- flash Raspberry Pi OS 64-bit;
- create the normal appliance user and configure network/SSH/locale as desired;
- obtain the A Clockwork Plex source tree so its installer can execute;
- complete Plex account authentication when the installed player asks for it.

Everything else that can be deterministic and safely owned belongs to the
repository installer.

## Why bootstrap must be staged

The current Phase 7 root installer grew from an already-working appliance, so its
pre-bootstrap preflight still assumes two things a genuinely fresh Pi cannot
provide:

1. `plexamp.service` already exists and serves the local port-32500 API;
2. the physical DAC is already exposed by ALSA as `CARD=Pro`.

Those requirements cannot remain gates *before* the installer has a chance to
install/commission them. The root orchestration therefore needs explicit stages
rather than weakening preflight into optimistic success.

Target order:

```text
source tree
  -> platform/package availability gate
  -> additive package + paired main/NFC venv bootstrap
  -> Pi board/HAT commissioning
       -> enable I2C
       -> project-user hardware groups
       -> PN532 at bus 1 / address 0x24
       -> exact pinned DAC boot configuration
       -> explicit reboot/resume if required
  -> pinned Plexamp Headless compatibility runtime
       -> pinned Node runtime
       -> player service
       -> Plex authentication / player-name commissioning
       -> local port-32500 contract
  -> pinned NFC listener service
       -> vendored exact listener runtime
       -> nfc-listener.service
       -> dashboard display-switch integration
  -> full application preflight
  -> existing whole-application transaction
       -> weather
       -> dashboard/kiosk
       -> Direct/EQ
       -> helpers
       -> AirPlay
       -> final verifier
```

A reboot is a first-class bootstrap outcome, not a failure and not an automatic
side effect. The installer must stop cleanly with a deterministic resume command;
it must never reboot the appliance without the operator choosing to do so.

## Package and Python-environment ownership

The additive package baseline now includes the NFC/Pi hardware support packages:

```text
i2c-tools
python3-lgpio
raspi-config
```

They join the existing `git`, `curl`, `python3`, `python3-venv`, `alsa-utils`,
`shairport-sync` and `chromium` ownership.

The bootstrap now owns **two staged Python environments as one paired transaction**:

```text
venv      -> A Clockwork Plex application dependencies
nfc-venv  -> Plexamp NFC Listener dependencies, --system-site-packages
```

The NFC venv intentionally sees the Raspberry Pi OS `python3-lgpio` package so
Blinka can use the system GPIO backend. Both venv candidates are built and
verified before either live directory is replaced. A failure after either swap
restores both exact prior directories, including exact prior absence.

The package policy remains additive. A later application failure does not run
`apt remove`, `purge`, `autoremove`, `apt upgrade`, `rpi-update`, bootloader
update or firmware update.

## Pi/NFC hardware owner

`scripts/install-platform-hardware.sh` is prepare-only by default and requires:

```text
--activate --confirm INSTALL-PLATFORM-HARDWARE
```

Known accepted hardware facts are pinned:

```text
PN532 bus:       1
PN532 address:   0x24
hardware groups: i2c gpio spi
DAC result:      ALSA CARD=Pro
```

Activation uses the Raspberry Pi OS `raspi-config nonint do_i2c 0` action rather
than reproducing its boot-file implementation. It then verifies the live I2C bus,
requires PN532 at `0x24`, and requires the normal project user to belong to the
hardware groups.

If `/dev/i2c-1` is not live after configuration, the owner reports:

```text
PLATFORM_HARDWARE=REBOOT-REQUIRED
```

and exits before NFC/DAC acceptance. It prints a resume command and never invokes
`reboot` itself.

This source slice is CI-green at Phase 7 checkpoint #22. It is not yet promoted
into root `install.sh` because the root preflight order still assumes Plexamp and
the DAC already exist.

## DAC ownership is deliberately blocked until identity is captured

The accepted audio contract proves that the DAC must appear as:

```text
CARD=Pro
```

but the repository and preserved Phase 6 evidence do **not** currently identify
the exact physical DAC HAT model or the exact Raspberry Pi boot `dtoverlay`
contract that produced it.

That missing identity is safety-critical. The installer must not infer a HAT from
the ALSA card name or copy an arbitrary Internet example. Until physical evidence
captures the accepted HAT/overlay, the hardware owner reports:

```text
PLATFORM_HARDWARE=DAC-COMMISSIONING-REQUIRED
DAC_POLICY=NO-GUESSED-OVERLAY
```

when `CARD=Pro` is absent.

The next physical evidence pass on the accepted image should capture the exact
boot configuration and HAT identity before the fresh card is wiped. Once pinned,
that reviewed configuration can be added to the same guarded hardware owner with
before/after and reboot acceptance.

## Plexamp Headless compatibility runtime

Phase 7 retains Plexamp Headless because the accepted appliance is coupled to its
local browsing surface and port-32500 control API. Player migration is not mixed
into fresh-installer acceptance.

The selected compatibility build under investigation is:

```text
Plexamp Headless: 4.13.2
```

The Node runtime candidate is now pinned from the official Node release archive:

```text
Node:      20.20.2
Platform:  linux-arm64
Archive:   node-v20.20.2-linux-arm64.tar.xz
SHA-256:   73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71
```

This is a **source/runtime candidate**, not yet physical acceptance. The final
Plexamp owner still must prove that exact Node binary against the accepted 4.13.2
headless runtime on the Pi.

The future Plexamp owner must:

- pin and verify the Plexamp 4.13.2 downloadable archive identity before extraction;
- install the pinned Node runtime without NodeSource/nvm `curl | bash` bootstraps;
- establish `plexamp.service` for the selected normal appliance user;
- preserve an explicit Plex account authentication/player-name boundary without
  putting claim tokens in logs, evidence or ordinary command-line arguments;
- verify the port-32500 API contract used by A Clockwork Plex;
- capture the selected Plexamp audio-device setting and ensure it targets the
  managed appliance route rather than the raw DAC.

`scripts/prepare-plexamp-upgrade-rehearsal.sh` already provides the read-only
physical evidence collector for installed version, `upgrade.sh` hash, systemd
unit/properties, journal, `audioDeviceUuid` and ALSA device lists.

**Current blocker:** the exact Plexamp 4.13.2 archive checksum/download contract
has not yet been pinned. The production installer must not use a mutable community
`curl | bash` installer or an unverified `latest` artifact.

## NFC listener ownership

The NFC runtime is now vendored from exact upstream repository state:

```text
repository: AndyBettger/Plexamp-NFC-Listener
commit:     8f5f04213b22cfb5affc6931cb2db91fd07de537
```

The exact upstream blobs retained under `vendor/plexamp-nfc-listener/` are:

```text
nfc_listener.py   5f87b477bfdac27a34373cb7708af8236c33c2ab
requirements.txt  a35eb89930ffac8e5b25179832e450aaa4403a13
LICENSE           739abcadcd68145a60b32ac67d2ec9fcd0a395ad
```

The historical standalone `setup.sh` is **not** executed or vendored as an
appliance installer. It also owns OS-wide upgrades, kiosk and AirPlay behaviour,
including old direct Plexamp service stop/start hooks, which conflicts with
current A Clockwork Plex authorities.

`scripts/install-nfc-listener.sh` is the guarded appliance owner. It renders only:

```text
/etc/systemd/system/nfc-listener.service
```

for the selected project user, uses `nfc-venv`, supplies the dashboard display
switch explicitly, and lists `i2c gpio spi` as supplementary groups. Its own
activation transaction restores exact previous unit contents/mode or exact prior
absence on failure.

It does **not** write Chromium autostart, Shairport configuration, AirPlay hooks,
Plexamp service state or boot/I2C configuration. This source slice is CI-green at
Phase 7 checkpoint #23.

## Final verifier expansion

Before fresh-appliance physical acceptance, `scripts/verify-appliance.sh` must add
truthful checks for installer-owned bootstrap state:

- pinned Plexamp runtime/service and local API;
- I2C bus and PN532 `0x24` availability;
- exact vendored NFC source identity, NFC venv, unit and active service;
- accepted DAC boot identity and `CARD=Pro` after the overlay is pinned;
- reboot-resume completion marker/state where applicable.

No fresh appliance is accepted merely because the dashboard starts.

## Backup/reimage target safety

The physical target may be the same bedroom Pi/HAT/display hardware **only after**
the accepted SD card has been captured as a verified off-device full image and a
fresh Raspberry Pi OS image has replaced the card contents.

Hostname alone is therefore not a sufficient safety identity. The acceptance
runbook will replace its old permanent `plexamp-bedroom` ban with a backup/reimage
guard that distinguishes the accepted production card state from explicitly
reimaged hardware.

The bootstrap installer does not update Pi EEPROM/bootloader or external hardware
firmware, because those changes would not be restored by rewriting the SD-card
image.

## Promotion rule

This document describes the staged target. Individual bootstrap owners may be
source/CI-green before root `install.sh` calls them. They are promoted into root
orchestration only when the preceding/following preflight contracts have been
moved to the correct side of that stage and failure/reboot behaviour is tested.

PR #2 remains Draft throughout Phase 7.
