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

The current Phase 7 installer grew from an already-working appliance, so its
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
  -> additive package + repository venv bootstrap
  -> Pi board/HAT commissioning
       -> enable I2C
       -> project-user hardware groups
       -> PN532 at bus 1 / address 0x24
       -> exact pinned DAC boot configuration
       -> explicit reboot/resume if required
  -> pinned Plexamp Headless compatibility runtime
       -> player service
       -> Plex authentication / player-name commissioning
       -> local port-32500 contract
  -> pinned NFC listener runtime
       -> isolated NFC venv
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

## Package ownership

The additive package baseline now includes the NFC/Pi hardware support packages:

```text
i2c-tools
python3-lgpio
raspi-config
```

They join the existing `git`, `curl`, `python3`, `python3-venv`, `alsa-utils`,
`shairport-sync` and `chromium` ownership.

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

The future Plexamp owner must:

- pin the exact compatibility version used for Phase 7;
- pin and verify the downloadable artifact identity before extraction;
- pin/review the required Node runtime strategy;
- establish `plexamp.service` for the selected normal appliance user;
- preserve an explicit Plex account authentication/player-name boundary without
  putting claim tokens in logs, evidence or ordinary command-line arguments;
- verify the port-32500 API contract used by A Clockwork Plex;
- capture the selected Plexamp audio-device setting and ensure it targets the
  managed appliance route rather than the raw DAC.

`scripts/prepare-plexamp-upgrade-rehearsal.sh` already provides the read-only
physical evidence collector for installed version, `upgrade.sh` hash, systemd
unit/properties, journal, `audioDeviceUuid` and ALSA device lists.

**Current blocker:** the exact Plexamp compatibility archive checksum/download
contract has not yet been pinned. The production installer must not use a mutable
community `curl | bash` installer or an unverified `latest` artifact.

## NFC listener ownership

The current `AndyBettger/Plexamp-NFC-Listener` repository is MIT-licensed and its
runtime contract is small enough to own deterministically. The accepted listener:

- uses PN532 over I2C;
- converts Plexamp NFC `listen.plex.tv` playback URLs to the local port-32500 API;
- asks A Clockwork Plex to switch the display to Plexamp after a successful scan.

Its historical `setup.sh` must **not** be executed wholesale from this installer.
That setup script also owns OS-wide upgrade, kiosk and AirPlay behaviour, including
old direct Plexamp service stop/start hooks, which conflicts with current A
Clockwork Plex authorities.

The A Clockwork Plex NFC owner will instead own only:

- a pinned listener source identity;
- an NFC-specific venv using system site packages where required for `lgpio`;
- the listener Python requirements;
- `nfc-listener.service` rendered for the selected project user;
- explicit display-switch/dashboard integration environment;
- PN532/service verification.

It will not write Chromium autostart, Shairport configuration or Plexamp/AirPlay
handoff hooks.

## Final verifier expansion

Before fresh-appliance physical acceptance, `scripts/verify-appliance.sh` must add
truthful checks for installer-owned bootstrap state:

- pinned Plexamp runtime/service and local API;
- I2C bus and PN532 `0x24` availability;
- NFC listener source/venv/unit/service;
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
