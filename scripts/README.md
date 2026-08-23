# Scripts catalogue

This directory contains the implementation, diagnostics and maintenance tooling behind **A Clockwork Plex**. It is deliberately broader than the normal installation interface.

## Start here

For a normal appliance installation or repeat convergence, use the repository-root command:

```bash
bash setup.sh
```

Do **not** cherry-pick component installers from this directory for a normal install. `setup.sh` and the guarded `appliance-installer.sh` engine own sequencing, preflight checks, rollback and final verification. `docs/INSTALL.md` is the normal operator guide; `docs/appliance-installer.md` documents the advanced lower-level engine.

The tables below document every retained file in `scripts/`, `scripts/audio/` and `scripts/audio_eq_camilladsp/`. A script being documented here does **not** mean it is intended for direct execution.

### Safety labels

| Label | Meaning |
| --- | --- |
| **Read-only** | Observes repository/appliance state and is not intended to change it. |
| **Guarded mutation** | Can change appliance state, but activation is protected by an explicit plan/confirmation/transaction boundary. Normal users should let `setup.sh` invoke it. |
| **Internal mutation** | Changes state as an implementation detail of a guarded owner. Do not invoke directly for normal maintenance. |
| **Runtime/helper** | Installed or called by a service, restricted helper or application API; not an operator command. |
| **Developer** | Repository-development tooling; does not install the appliance. |

## Appliance installer and verification owners

These files are part of the supported fresh-install/convergence payload. Direct use is for development or deliberately scoped recovery only; prefer `bash setup.sh`. For advanced direct work, read `docs/appliance-installer.md` and the script's `--help`/plan output before activation.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/preflight-appliance.sh` | Read-only whole-appliance prerequisite/profile preflight used before any mutation. | **Read-only.** Normally called by the installer engine. |
| `scripts/check-appliance-components.sh` | Checks whether installer-owned component files/services match the selected appliance profile. | **Read-only.** Installer/internal diagnostic. |
| `scripts/check-appliance-packages.sh` | Checks the profile-specific package/runtime dependency contract. | **Read-only.** Installer/internal diagnostic. |
| `scripts/check_nfc_python_deps.py` | Validates the NFC Python dependency closure without treating unrelated environment metadata as an NFC failure. | **Read-only.** Called by package/runtime installation and tests; `python3 scripts/check_nfc_python_deps.py --help` for development. |
| `scripts/fetch-camilladsp-4.1.3.sh` | Fetches and verifies the pinned CamillaDSP 4.1.3 aarch64 artifact used by the EQ profile. | **Guarded mutation.** `setup.sh` owns normal acquisition; do not substitute an unpinned binary. |
| `scripts/install-appliance-packages.sh` | Builds/activates the project Python environments and package baseline transactionally. | **Guarded mutation.** Installer owner; use its help/plan path only for deliberate advanced work. |
| `scripts/install-platform-hardware.sh` | Owns supported Pi hardware configuration for PN532/I2C and Raspberry Pi DAC Pro, including reboot checkpoint policy. | **Guarded mutation.** Never use it as a generic OS/firmware updater. |
| `scripts/install-plexamp-runtime.sh` | Installs/verifies the pinned Plexamp Headless + private Node runtime and hands an unclaimed install back for local claim. | **Guarded mutation.** Normal claim flow belongs to `setup.sh`. |
| `scripts/install-nfc-listener.sh` | Installs the pinned NFC listener runtime/service for the selected project user. | **Guarded mutation.** Installer owner. |
| `scripts/install-appliance-helpers.sh` | Transactionally installs restricted runtime helpers and sudoers policies, including alarm audio, Shairport naming and Weather-secret helpers. | **Guarded mutation.** Replaces the retired standalone helper installers. |
| `scripts/install-airplay-integration.sh` | Transactionally installs rendered Shairport callbacks, metadata FIFO/listener service and validated Shairport integration with rollback. | **Guarded mutation.** Current AirPlay integration owner. |
| `scripts/install-airplay-hooks.sh` | Renders/copies the coordinator-event AirPlay callbacks and removes obsolete callback/sudoers remnants. | **Internal mutation.** It is a lower-level implementation helper; normal work goes through `install-airplay-integration.sh`/`setup.sh`. |
| `scripts/install-dashboard-integration.sh` | Transactionally installs the dashboard systemd service and kiosk/autostart integration as one guarded component. | **Guarded mutation.** Current fresh-install dashboard owner. |
| `scripts/install-weather-config.sh` | Applies selected observation-provider settings and manages the root-owned WU secret boundary without putting the secret in public config. | **Guarded mutation.** Normal Weather commissioning is through `setup.sh` and Settings. |
| `scripts/install-appliance-application.sh` | Coordinates the final application/audio/Weather/dashboard transaction and keeps final verification inside the commit boundary. | **Guarded mutation.** Installer engine owner, not a normal standalone command. |
| `scripts/verify-fresh-bootstrap.sh` | Verifies the fresh bootstrap identities and files (hardware/runtime/NFC/claim boundary) without changing them. | **Read-only.** Formal acceptance verifier. |
| `scripts/verify-appliance.sh` | Verifies the selected whole-appliance audio/Weather/runtime contract, including protected-file checks through restricted boundaries. | **Read-only.** Formal acceptance/post-install verifier. |

## Installed runtime/helper sources

These files are source material for installed services, restricted helpers or application-owned commands. They are retained because the running appliance depends on them; they are **not** alternative operator entry points.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/a-clockwork-plex-airplay-wrappers.py` | Renders the current Shairport start/end callback scripts that publish lifecycle intent to PlaybackCoordinator. | **Runtime/helper.** Rendered by the AirPlay installer; callbacks never stop/start Plexamp. |
| `scripts/airplay-metadata-listener.py` | Reads Shairport metadata from the managed FIFO and publishes sanitised metadata/lifecycle state to the dashboard. | **Runtime/helper.** Installed as the managed metadata-listener service. |
| `scripts/a-clockwork-plex-shairport-integration.py` | Renders/validates the Shairport configuration blocks used by the transactional AirPlay integration owner. | **Runtime/helper.** Called by installation/validation. |
| `scripts/a-clockwork-plex-shairport-name.py` | Restricted helper implementation for reading/changing the AirPlay receiver name while preserving/validating Shairport config. | **Runtime/helper.** Application/installer invokes the installed restricted command. |
| `scripts/a-clockwork-plex-weather-secret.py` | Restricted helper for set/remove/status of the root-owned Weather Underground API-key environment file. | **Runtime/helper.** Secret is supplied via stdin and status exposes presence only; do not bypass this boundary. |
| `scripts/a-clockwork-plex-alarm-audio-helper.sh` | Restricted alarm-audio helper used by the application/audio safety contract. | **Runtime/helper.** Installed transactionally by `install-appliance-helpers.sh`. |
| `scripts/a-clockwork-plex-audio-mixer.py` | Installed mixer helper for the accepted Music Master/source-trim/alarm-ceiling controls. | **Runtime/helper.** Called through the restricted application/audio interface. |
| `scripts/a-clockwork-plex-audio-eq.py` | Installed entry point for managed EQ status/curve/bypass operations. | **Runtime/helper.** Application/restricted-helper use; not a replacement for the audio installer lifecycle. |
| `scripts/a-clockwork-plex-audio-route.py` | Owns selected Direct/EQ route preparation, status, validation and fixed failback operations. | **Runtime/helper.** Used by audio lifecycle/systemd integration under guarded ownership. |
| `scripts/nfc-plexamp-mode.sh` | Small NFC playback-mode bridge used by the installed NFC integration. | **Runtime/helper.** Called by the NFC path, not normal manual navigation. |
| `scripts/launch-dashboard-kiosk.sh` | Starts Chromium with the dedicated A Clockwork Plex kiosk profile after the dashboard is reachable. | **Runtime/helper.** Installed/autostarted by dashboard integration. |

## Supported audio lifecycle

The accepted audio lifecycle lives only in `scripts/audio/`. Normal appliance installation still goes through `setup.sh`; these commands exist for the guarded audio component lifecycle, recovery and formal verification.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/audio/preflight-eq.sh` | Historical read-only bedroom-Pi validation gate that proves the pinned DAC/direct-baseline/CamillaDSP assumptions before EQ work. | **Read-only diagnostic/acceptance.** Retained intentionally; it is not an installer. |
| `scripts/audio/install-direct.sh` | Installs/converges the accepted alarm-safe Direct route. | **Guarded mutation.** Normally delegated by the appliance installer. |
| `scripts/audio/install-eq.sh` | Installs/converges the accepted CamillaDSP split-bus EQ route with captured rollback baseline. | **Guarded mutation.** Normally delegated by the appliance installer. |
| `scripts/audio/repair-audio.sh` | Repairs an installed managed audio profile while preserving/restoring pre-repair runtime state on failure. | **Guarded mutation.** Recovery tool; inspect its plan/help before activation. |
| `scripts/audio/uninstall-eq.sh` | Removes managed EQ and restores the captured Direct baseline/loopback state transactionally. | **Guarded mutation.** Recovery/profile-transition owner, not an ad-hoc reset command. |
| `scripts/audio/verify-audio.sh` | Verifies Direct or EQ audio route, services, manifests and accepted safety invariants. | **Read-only.** Formal audio verifier; use the profile option documented by `--help`. |

## Read-only diagnostics

These are intentionally outside the fresh-install dependency closure because an appliance does not need them to install, but they are useful when diagnosing or auditing a commissioned system.

| File | Purpose | Invocation |
| --- | --- | --- |
| `scripts/inspect-application-state.sh` | Compares the installed dashboard unit with the repository unit and reports the running ApplicationStateHub/API state. | `bash scripts/inspect-application-state.sh` — **read-only**. |
| `scripts/inspect-playback-coordinator.sh` | Dumps PlaybackCoordinator, screen projection, local input, handoff, hold, command and event-journal state. | `bash scripts/inspect-playback-coordinator.sh` — **read-only**. |
| `scripts/inspect-mixer-controller.sh` | Dumps mixer authority, AirPlay sender-volume command state and raw Shairport volume observation. | `bash scripts/inspect-mixer-controller.sh` — **read-only**. |
| `scripts/dump-airplay-mpris-metadata.sh` | Watches raw Shairport MPRIS metadata/playback/volume properties to diagnose sender behaviour. | `bash scripts/dump-airplay-mpris-metadata.sh [interval-seconds]` — **read-only**; Ctrl+C to stop. |
| `scripts/inspect-weather-underground-payloads.py` | Secret-safe diagnostic comparing supported WU current/history payloads with the existing mapper contract; does not write dashboard state. | `python3 scripts/inspect-weather-underground-payloads.py --help` first — **read-only**. |
| `scripts/audit-plexamp-preferences.py` | Inventories safe-looking `@Plexamp:settings:*` key names/sizes in its default content-blind mode; `--show-safe-values` reads only the explicit ordinary-preference allow-list and never unknown/device-identity/authentication or Chromium storage values. | `python3 scripts/audit-plexamp-preferences.py` or add `--show-safe-values` for the guarded second-stage audit — **read-only**; intended for backup-ownership discovery, not routine operation. |

## Guarded maintenance and migration tools

These are retained because they solve specific recovery/migration jobs that are useful after installation. They are not alternate fresh-install paths.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/install-dashboard-service.sh` | Standalone guarded repair/check tool for the dashboard systemd unit. | **Guarded mutation.** Default/check path is non-mutating; use `--help` before a deliberate repair. Fresh install uses `install-dashboard-integration.sh`. |
| `scripts/install-dashboard-kiosk.sh` | Standalone guarded repair/check tool for Chromium kiosk/autostart configuration. | **Guarded mutation.** Use `--help`; fresh install uses `install-dashboard-integration.sh`. |
| `scripts/migrate-dashboard-browser-auth.sh` | Migrates the dedicated Chromium kiosk profile/auth state while excluding session-restore state. | **Guarded mutation.** Defaults read-only and requires explicit confirmed apply; it does not manage audio. Run `bash scripts/migrate-dashboard-browser-auth.sh --help`. |
| `scripts/prepare-plexamp-upgrade-rehearsal.sh` | Captures a read-only Plexamp/audio/device evidence bundle before a future controlled Plexamp upgrade rehearsal. | **Read-only.** `bash scripts/prepare-plexamp-upgrade-rehearsal.sh [--plexamp-dir PATH] [--lab-root PATH]`; it does not download, upgrade or stop services. |
| `scripts/set-airplay-hold-seconds.py` | CLI fallback for inspecting/changing the persisted AirPlay paused-session hold (15–420 seconds). | **Configuration mutation when a value is supplied.** Prefer Settings for normal use. `python3 scripts/set-airplay-hold-seconds.py` shows the current value; add an integer to set it, then follow the script's restart instruction. |

## Developer tooling

| File | Purpose | Invocation |
| --- | --- | --- |
| `scripts/run-tests.sh` | Local contributor validation: project-wide Python, shell and JavaScript syntax checks followed by the complete unit suite. It deliberately discovers files instead of maintaining a stale hand-written script list. | Create/install a project venv as instructed by the script, then run `bash scripts/run-tests.sh`. CI additionally keeps a few targeted early page-wiring assertions. |

## Internal CamillaDSP EQ package

`scripts/audio_eq_camilladsp/` is a Python implementation package used by the installed `a-clockwork-plex-audio-eq.py` entry point. These modules are not standalone operator commands.

| File | Purpose | Intended use |
| --- | --- | --- |
| `scripts/audio_eq_camilladsp/__init__.py` | Package surface/versioned imports for the managed CamillaDSP EQ helper. | **Runtime/helper.** Imported by the EQ entry point/tests. |
| `scripts/audio_eq_camilladsp/cli.py` | Command parsing/dispatch for managed EQ status and mutation actions. | **Runtime/helper.** Invoked through `a-clockwork-plex-audio-eq.py`. |
| `scripts/audio_eq_camilladsp/model.py` | Saved-state, filter/headroom and CamillaDSP configuration model/rendering logic. | **Runtime/helper.** Internal library. |
| `scripts/audio_eq_camilladsp/runtime.py` | Live CamillaDSP validation/reload/rollback and process/runtime boundary logic. | **Runtime/helper.** Internal library. |

## Maintenance rule

`tests/test_script_catalog.py` enforces that every retained file in the documented script directories appears in this catalogue. When adding a new script, decide its ownership and safety class here at the same time. When retiring one, remove its catalogue entry and add/extend an appropriate retirement regression if returning that path would be unsafe.