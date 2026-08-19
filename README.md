# A Clockwork Plex

A Clockwork Plex turns a Raspberry Pi into a bedside touchscreen music appliance built around Plexamp Headless, with NFC album playback, AirPlay, scheduled alarms, a local-weather dashboard and a guarded three-band CamillaDSP equaliser.

The project is designed as one appliance rather than a collection of manually installed components: the installer owns Plexamp, Node, NFC, AirPlay, dashboard/kiosk integration, alarm-safe audio routing and the EQ path.

> **Current release candidate:** development is finishing on `feature/alarm-engine` in draft PR #2. The PR remains Draft/open/unmerged until final physical acceptance, repository cleanup and explicit owner approval are complete.

For the full fresh-install procedure, use **[`docs/INSTALL.md`](docs/INSTALL.md)**.

## Validated hardware

The physically validated appliance uses:

- Raspberry Pi 4B;
- 64-bit Raspberry Pi OS with Desktop;
- Raspberry Pi Touch Display 2, rotated left for landscape use;
- Raspberry Pi DAC Pro, exposed by ALSA as `CARD=Pro`;
- PN532 NFC reader on I2C bus 1 at `0x24`;
- network access for package installation and the pinned Plexamp, Node and CamillaDSP downloads.

A Clockwork Plex does not require or perform `rpi-update`, experimental bootloader changes or HAT firmware updates.

## Fresh installation

Prepare Raspberry Pi OS and the Touch Display as described in [`docs/INSTALL.md`](docs/INSTALL.md), then clone the current production-candidate branch:

```bash
cd ~
git clone --branch feature/alarm-engine \
  https://github.com/AndyBettger/A-Clockwork-Plex.git
cd A-Clockwork-Plex
```

Run the normal installer as the ordinary appliance user, **not** with `sudo`:

```bash
bash setup.sh
```

`setup.sh` is the human-facing entry point. It acquires and verifies the pinned CamillaDSP artifact, invokes the guarded transactional installer and launches the Plexamp Headless claim flow automatically when a new player needs claiming.

If hardware commissioning asks for a reboot, reboot and run `bash setup.sh` again. Completed idempotent stages are detected and reused.

After a successful install, reboot once into the appliance and finish Plexamp commissioning in its browser interface:

1. sign into the Plex account if prompted;
2. choose the required music library;
3. choose **`A Clockwork Plex - Plexamp`** as Plexamp's audio output rather than leaving **Follows system output** selected.

VNC is strongly recommended while commissioning because Plex credentials, Weather Underground station IDs/API keys and other long values are much easier to copy/paste from a normal computer than enter on a 7-inch touchscreen.

## What the appliance provides

### Clock

The main bedside surface provides:

- large 14-segment-style time and date;
- selectable 12/24-hour presentation;
- configurable local-weather cards;
- an LCD-style alarm-set annunciator driven by the scheduler's real next occurrence;
- **Next alarm within 12 hours** or **Any future alarm** annunciator modes;
- scheduled night dimming, Classic and Astronomy night presentation, touch-to-wake and burn-in shifting.

### Weather

Forecast and live observations are deliberately separate:

- **Open-Meteo** supplies cached forecast data;
- **Ecowitt Push** or **Weather Underground PWS** can supply current outdoor observations;
- WU can also supply cached historical rainfall and Rainy Day Fund totals.

The selected live provider remains authoritative for outdoor conditions. When WU is selected, a Pi that also receives the Ecowitt custom upload may use **fresh supplementary indoor temperature/humidity** without allowing Ecowitt to overwrite the WU outdoor readings.

Ecowitt's validated custom-upload setup provides only one custom destination at a time. That makes it suitable for the one appliance where direct local/indoor readings matter most, but **Weather Underground is the practical shared live source when several A Clockwork Plex appliances need the same station data**.

WU does not directly provide every Ecowitt rain field. A Clockwork Plex derives rolling Hourly rain, Event rain and the current day's maximum observed gust where required, while native provider values retain precedence when present.

WU API keys are write-only managed secret material. Commission them through **Settings → Weather**; do not put them in `config.json`, shell history or repository files.

### Plexamp and NFC

Plexamp Headless remains the music player for this release. The installer pins and manages its compatible Node runtime rather than replacing the operating system's Node installation.

The bundled NFC listener uses the validated PN532 I2C reader. Compatible NFC album tags can start Plexamp playback and hand the dashboard to the Plexamp surface.

### AirPlay

Shairport Sync provides AirPlay reception through the same appliance-managed music path as Plexamp. The dashboard shows receiver/Now Playing state, and playback coordination handles Plexamp/AirPlay handoff without routinely stopping or restarting the services.

The AirPlay receiver name is managed from Settings and applied through a restricted helper with validation and rollback.

### Scheduled alarms

A Clockwork Plex supports multiple recurring alarms with:

- real clock-triggered playback;
- Snooze and repeated ring cycles;
- deliberate Dismiss;
- configurable tone, target volume, fade-start volume and fade duration;
- automatic takeover from Plexamp/AirPlay while the alarm owns priority;
- a separate **Maximum Alarm Volume** safety ceiling.

Alarm fade-start volume defaults to 10% for newly-created alarms and may be overridden per alarm. Fade Off starts immediately at the target; a faded ring starts at the configured start level and rises to the target, and a Snooze re-ring starts a fresh fade cycle.

## Audio and equaliser architecture

The accepted EQ appliance deliberately separates the music path from alarm loudness:

```text
Plexamp ----\
             +-> source trims -> Music Master -> -6.5 dB reserve
AirPlay ----/                                  -> Bass/Mid/Treble
                                                -> music bus ---------\
                                                                       +-> final limiter -> DAC
Alarm -> per-alarm start/target/fade -> Maximum Alarm Volume ----------/
```

Important consequences:

- Plexamp and AirPlay both follow Music Master and the three-band EQ;
- scheduled alarms **bypass Music Master and music EQ**;
- Maximum Alarm Volume limits alarms independently;
- all output still passes through the final safety limiter before the DAC;
- CamillaDSP is pinned to the accepted 4.1.3 build and managed by `a-clockwork-plex-camilladsp.service`.

The supported audio lifecycle tools live under `scripts/audio/`, including verification and repair. The old bare `scripts/install-master-eq.sh` production path remains intentionally blocked and is not the normal installer.

## Settings

The touchscreen Settings workspace covers:

- General appliance preferences;
- Display/Clock behaviour and night presentation;
- Weather sources, units, forecast and WU credentials;
- Alarms and alarm defaults;
- AirPlay receiver naming;
- Music Master, source trims, Maximum Alarm Volume and EQ;
- Plexamp and Advanced diagnostics;
- About/status information.

Ordinary configuration should be changed through Settings rather than by editing `config.json` directly.

## Updating an installed appliance

For a source update on the current branch/release:

```bash
cd ~/A-Clockwork-Plex
git status
git pull --ff-only
```

If `git status` shows unexpected tracked modifications, investigate them before pulling rather than forcing the checkout.

After pulling a release-candidate update, use the same public convergent entry point rather than rebuilding components by hand:

```bash
bash setup.sh
```

Completed stages are detected and reused; follow any explicit reboot or local Plexamp-commissioning checkpoint that `setup.sh` reports. Do not rebuild the Python environments, ALSA graph or managed services component by component unless performing a documented repair procedure.

## Useful diagnostics

The dashboard listens locally on port `8088`. Supported verifier/diagnostic tooling includes:

```bash
bash scripts/verify-fresh-bootstrap.sh
bash scripts/verify-appliance.sh
bash scripts/audio/verify-audio.sh
```

Other read-only inspection helpers live under `scripts/`. Weather Underground includes a sanitized payload inspector that does not require exposing the API key in normal diagnostic output.

For service-level diagnosis:

```bash
systemctl status a-clockwork-plex.service --no-pager -l
systemctl status plexamp.service --no-pager -l
systemctl status nfc-listener.service --no-pager -l
systemctl status shairport-sync.service --no-pager -l
systemctl status a-clockwork-plex-camilladsp.service --no-pager -l
```

## Development and validation

The repository intentionally retains maintained regression tests and CI even though they are not part of normal bedside runtime. They protect installer convergence, rollback, audio ownership, Weather source authority, secret handling and UI contracts.

The normal development validation path is:

```bash
python3 -m compileall .
python3 -m unittest discover -s tests -v
```

GitHub Actions additionally performs production-module compilation, JavaScript syntax/page wiring checks and shell syntax checks.

Historical engineering evidence and the active Phase 7 roadmap live under `docs/`. The final release-hygiene classification is recorded in [`docs/release-hygiene-audit-2026-08-19.md`](docs/release-hygiene-audit-2026-08-19.md).

## Release status

The appliance has physically passed the major dashboard, Weather, Plexamp, NFC, AirPlay, scheduled-alarm and persistent split-bus EQ paths on the spare-SD target. Remaining release gates are tracked in [`docs/eq-audio-installer-roadmap.md`](docs/eq-audio-installer-roadmap.md), including the final wiped-SD `setup.sh` clean-room run, formal post-reboot verifiers, repeat-setup idempotence and final repository/documentation hygiene.

PR #2 remains Draft and must not be merged until those gates are complete and explicit owner approval is given.
