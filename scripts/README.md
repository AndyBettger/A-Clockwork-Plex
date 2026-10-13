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
| `scripts/commission-plexamp.py` | Captures/verifies the appliance-local Plexamp commissioning baseline and converges the commissioned player name plus the exact managed `A Clockwork Plex - Plexamp` output through Plexamp's loopback settings API. | **Internal mutation.** Called by `setup.sh` after guarded appliance installation; it is not a portable Backup/Restore owner and is not a normal standalone operator command. |
| `scripts/install-nfc-listener.sh` | Installs the pinned NFC listener runtime/service for the selected project user. | **Guarded mutation.** Installer owner. |
| `scripts/install-appliance-helpers.sh` | Transactionally installs restricted runtime helpers and sudoers policies, including alarm audio, Shairport naming, Weather-secret, mixer and allow-listed Plexamp Headless preference restore helpers. | **Guarded mutation.** Replaces the retired standalone helper installers; Plexamp restore gets only narrow `status`/`apply` authority, never broad service-control sudo. |
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
| `scripts/a-clockwork-plex-shairport-integration.py` | Renders/validates the Shairport Sync integration configuration. | **Runtime/helper.** Called by installation/validation. |
| `scripts/a-clockwork-plex-shairport-name.py` | Restricted helper implementation for reading/changing the AirPlay receiver name while preserving/validating Shairport config. | **Runtime/helper.** Application/installer invokes the installed restricted command. |
| `scripts/a-clockwork-plex-weather-secret.py` | Restricted helper for set/remove/status of the root-owned Weather Underground API-key environment file. | **Runtime/helper.** Secret is supplied via stdin and status exposes presence only; do not bypass this boundary. |
| `scripts/a-clockwork-plex-alarm-audio-helper.sh` | Restricted alarm-audio helper used by the application/audio safety contract. | **Runtime/helper.** Installed transactionally by `install-appliance-helpers.sh`. |
| `scripts/a-clockwork-plex-audio-mixer.py` | Installed mixer helper for the accepted Music Master/source-trim/alarm-ceiling controls. | **Runtime/helper.** Called through the restricted application/audio interface. |
| `scripts/a-clockwork-plex-audio-eq.py` | Installed entry point for managed EQ status/curve/bypass operations. | **Runtime/helper.** Application/restricted-helper use; not a replacement for the audio installer lifecycle. |
| `scripts/a-clockwork-plex-audio-route.py` | Owns selected Direct/EQ route preparation, status, validation and fixed failback operations. | **Runtime/helper.** Used by audio lifecycle/systemd integration under guarded ownership. |
| `scripts/a-clockwork-plex-plexamp-preferences.py` | Restricted transactional owner for the exact eight approved non-authentication Plexamp Headless preferences. Values arrive as bounded JSON on stdin; the helper quiesces `plexamp.service`, atomically writes only existing allow-listed files, verifies/restarts and restores exact prior state on failure. | **Runtime/helper.** Installed by `install-appliance-helpers.sh`; sudo policy exposes only `status` and `apply`, never arbitrary preference names or broad `systemctl`. |
| `scripts/nfc-plexamp-mode.sh` | Small NFC playback-mode bridge used by the installed NFC integration. | **Runtime/helper.** Called by the NFC path, not normal manual navigation. |
| `scripts/launch-dashboard-kiosk.sh` | Starts Chromium with the dedicated A Clockwork Plex kiosk profile after the dashboard is reachable. | **Runtime/helper.** Installed/autostarted by dashboard integration. |

**ACP Chromium one-keyboard opt-in (12 October):** a real Settings → Weather screenshot shows both the experimental OVERLAY Squeekboard and the existing ACP HTML keyboard open for the same field. Settings → Advanced → Keyboard trial now provides a **reversible browser-tab-only five-minute** selection that suppresses the HTML keyboard and exposes native input hints. The UI toggle does not launch, install or stop Squeekboard; use only during the independently guarded 180-second `scripts/try-squeekboard-overlay.py --start <ZIP>` experiment. Existing #91 browser keyboard and its specialised time/number/URL layouts remain the default, and the user can always tap Restore ACP keyboard. Physical no-overlap/field usability still pending. 

**12 October physical OSK update:** the opt-in, separately built Squeekboard `OVERLAY` prototype has now been seen and used above true fullscreen native Plexamp Search and an Add-dialog input. The standard distro keyboard remains `TOP` and **does not** overlay fullscreen; no global replacement, auto-start or installation of the test executable has occurred. The trial restored a single original Squeekboard process afterwards. The native launcher is still windowed by default to keep the unmodified appliance touch-friendly until keyboard ownership is integrated safely.

## Manual Phase-B native Plexamp launcher

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/launch-native-plexamp.sh` | Launches the **already installed** ARM64 Plexamp Flatpak into the existing labwc/Wayland session, including from SSH. Backgrounds the application, checks for an existing instance, and writes a private log under `~/.cache/a-clockwork-plex/native-plexamp.log`. | **Manual development launch only.** Use `bash scripts/launch-native-plexamp.sh` as the ordinary user (no sudo); `--fullscreen` optionally targets the native Wayland window through `wlrctl` (requires `sudo apt install wlrctl` if not present), waits up to 20 seconds for the real Wayland toplevel (tries the Flatpak ID, otherwise discovers a uniquely titled `Plexamp` toplevel with `wlrctl toplevel list`, excluding Chromium identities), and deliberately leaves the default windowed because the Pi OS keyboard hides under true fullscreen. `--help` explains usage. The current `beta` branch is deliberately pinned for #94 discovery. Never installs Flatpak, changes autostart/audio, restarts Headless, or replaces `setup.sh`. |

## Supported audio lifecycle

The accepted audio lifecycle lives only in `scripts/audio/`. Normal appliance installation still goes through `setup.sh`; these commands exist for the guarded audio component lifecycle, recovery and formal verification.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/audio/preflight-eq.sh` | Historical read-only bedroom-Pi validation gate that proves the pinned DAC/direct-baseline/CamillaDSP assumptions before EQ work. | **Read-only diagnostic/acceptance.** Retained intentionally; it is not an installer. |
| `scripts/audio/audit-hi-res-audio.sh` | Audits the already-installed managed EQ/split-bus path for hi-res development: live ALSA/DAC/loopback state, profile/config format and rate, route/EQ status, services and CamillaDSP process state. | **Read-only developer diagnostic.** Run with `bash scripts/audio/audit-hi-res-audio.sh`; it never opens a PCM or mutates the appliance. |
| `scripts/audio/snapshot-airplay-hi-res.py` | Captures a bounded timing/buffer snapshot of the active high-resolution AirPlay path: configured frame durations, live ALSA `hw_params`, selected Shairport/CamillaDSP timing settings, service/process state and filtered/redacted journal clues. | **Read-only developer diagnostic.** Run while the guarded 192 kHz rehearsal and problem AirPlay stream are active; it opens no PCM and changes no route, service, mixer or configuration. |
| `scripts/audio/probe-hi-res-dac.py` | Temporarily quiesces dashboard/AirPlay/Plexamp/CamillaDSP, opens the idle physical DAC only to query exact stereo ALSA format/rate constraints, closes it without starting playback, then restores and re-verifies the managed audio stack. | **Guarded developer diagnostic.** Default invocation is plan-only; `python3 scripts/audio/probe-hi-res-dac.py --apply` deliberately interrupts audio briefly and requires sudo for service lifecycle only. |
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
| `scripts/audit-plexamp-preferences.py` | Audits Plexamp backup candidates in three read-only modes: content-blind Headless key inventory, explicit typed allow-listed Headless values, and structured loopback Chromium Local Storage key names. Unknown/device-identity/authentication values and all browser values remain excluded. | `python3 scripts/audit-plexamp-preferences.py --help` — **read-only**; intended for backup-ownership discovery, not routine operation. |
| `scripts/inspect-plexamp-home-runtime.py` | Bounded developer probe for finding Plexamp's live/effective Home model beneath `rootStore` from a disposable Chromium profile. It emits object/member names and shapes only, skips sensitive-name subtrees, never reads primitive values or invokes getters, and accepts only a loopback DevTools target whose page is `http://localhost:32500`. | Launch the disposable profile with loopback-only remote debugging, then run `python3 scripts/inspect-plexamp-home-runtime.py` — **read-only developer diagnostic**; never enable remote debugging on the production kiosk profile. |
| `scripts/inspect-plexamp-home-hubs.py` | Narrow follow-up probe for the live Plexamp discovery-hub authority found by the broader runtime probe. It emits only bounded hub/member names, kinds and collection lengths; primitive values and getters remain excluded. | With the disposable loopback-debug Chromium profile open, run `python3 scripts/inspect-plexamp-home-hubs.py` — **read-only developer diagnostic**; never target the production kiosk profile. |
| `scripts/inspect-plexamp-home-customizations.py` | Inventories only bounded Local Storage key families beneath Plexamp's Home `discovery:customizations` namespace so an untouched disposable profile can be compared with deliberate Home edits. Stored values and raw identifiers are never read or emitted. | With the disposable loopback-debug Chromium profile open, run `python3 scripts/inspect-plexamp-home-customizations.py` — **read-only developer diagnostic**; never target the production kiosk profile. |
| `scripts/inspect-plexamp-home-title.py` | Compares one caller-supplied expected title against only the optional validated `title` field of structurally classified Plexamp Home `viewSettings` records. It reads no other Home values and never emits stored titles, raw Local Storage values/keys, context IDs or hub IDs. | With a disposable loopback-debug Chromium profile open, run `python3 scripts/inspect-plexamp-home-title.py --debug-port <port> --expected-title "Known title"` — **read-only developer diagnostic**; never target the production kiosk profile. |
| `scripts/inspect-plexamp-browser-storage.py` | Inventories browser-local persistence metadata for the disposable Plexamp profile: bounded Local/Session Storage key-family counts plus IndexedDB database/object-store names. It never reads Web Storage values, IndexedDB records or opens IndexedDB transactions. | With a disposable loopback-debug Chromium profile open, run `python3 scripts/inspect-plexamp-browser-storage.py` — **read-only developer diagnostic**; never target the production kiosk profile. |
| `scripts/compare-plexamp-local-storage-keys.py` | Compares Local Storage key-name sets between two disposable Plexamp Chromium profiles and emits only bounded/sanitised metadata for keys unique to either profile. Stored values are never read; sensitive-looking key names are redacted. | With tracer/control disposable profiles on loopback debug ports, run `python3 scripts/compare-plexamp-local-storage-keys.py` — **read-only developer diagnostic**; never target the production kiosk profile. |

## Guarded maintenance and migration tools

These are retained because they solve specific recovery/migration jobs that are useful after installation. They are not alternate fresh-install paths.

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/install-dashboard-service.sh` | Standalone guarded repair/check tool for the dashboard systemd unit. | **Guarded mutation.** Default/check path is non-mutating; use `--help` before a deliberate repair. Fresh install uses `install-dashboard-integration.sh`. |
| `scripts/install-dashboard-kiosk.sh` | Standalone guarded repair/check tool for Chromium kiosk/autostart configuration. | **Guarded mutation.** Use `--help`; fresh install uses `install-dashboard-integration.sh`. |
| `scripts/migrate-dashboard-browser-auth.sh` | Migrates the dedicated Chromium kiosk profile/auth state while excluding session-restore state. | **Guarded mutation.** Defaults read-only and requires explicit confirmed apply; it does not manage audio. Run `bash scripts/migrate-dashboard-browser-auth.sh --help`. |
| `scripts/rehearse-plexamp-home-scrub.py` | Disposable-profile-only proof tool for the classified Plexamp Home persistence surface: read-only plan, exact mode-0600 snapshot, stale-checked bounded scrub of only `order`/`hidden`/`viewSettings`/`customHubs`, and exact rollback. It refuses the preserved 9224–9229 profiles, active `editing`, unknown families, non-empty rollback targets and arbitrary DevTools code/URLs. | **Developer-only guarded mutation.** Use only on a newly created loopback-debug disposable Chromium profile (normally port 9230+). Never target the production kiosk or the preserved evidence profiles. |
| `scripts/prepare-plexamp-upgrade-rehearsal.sh` | Captures a read-only Plexamp/audio/device evidence bundle before a future controlled Plexamp upgrade rehearsal. | **Read-only.** `bash scripts/prepare-plexamp-upgrade-rehearsal.sh [--plexamp-dir PATH] [--lab-root PATH]`; it does not download, upgrade or stop services. |
| `scripts/set-airplay-hold-seconds.py` | CLI fallback for inspecting/changing the persisted AirPlay paused-session hold (15–420 seconds). | **Configuration mutation when a value is supplied.** Prefer Settings for normal use. `python3 scripts/set-airplay-hold-seconds.py` shows the current value; add an integer to set it, then follow the script's restart instruction. |

## Native Plexamp on-screen keyboard discovery

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/validate-squeekboard-uk-theme-stage.py` | Read-only post-staging check: pinned vendor-derived GB YAML matches original source, all ACP day/night GTK3 style samples match current theme tokens, private stage manifest/symlink safety, and optional PyYAML / `squeekboard-test-layout` parsing if already installed. | `python3 scripts/validate-squeekboard-uk-theme-stage.py --check` as normal Pi user. Does **not** install any parser, start/stop the OSK, alter GTK globally, or activate themes. A static PASS does not mean native parser/physical keyboard acceptance. |
| `scripts/stage-squeekboard-uk-theme.py` | Offline Stage C2 planner/stager. Copies the pinned installed US YAML into a private UK keyboard candidate (including `£`, decimal and `:`) and creates isolated ACP GTK3 daytime/night stylesheet samples. | Run `python3 scripts/stage-squeekboard-uk-theme.py --plan` first (read-only). After its source-schema check passes, `--stage` creates a new private cache tree and refuses overwrite. **Does not launch/replace any keyboard or modify global GTK, audio or services.** |
| `scripts/inspect-squeekboard-theme-layout.py` | Read-only inventory of the installed Squeekboard binary/package, GNOME/XKB input sources, available US/GB YAML layouts, GTK3 stylesheet existence (not contents) and ACP day/night palette names before Stage C2 native-keyboard styling. | `python3 scripts/inspect-squeekboard-theme-layout.py --inspect` as the ordinary Pi user; **read-only**. No keyboard service, XKB/GSettings, GTK CSS, audio, credentials, NFC or Plexamp changes. |
| `scripts/try-squeekboard-overlay.py` | Opt-in **user-scoped, timed native OSK trial** with a staged SHA-256-verified ELF, transient systemd user trial service and a separately armed rescue timer. Restores stock `/usr/bin/sbtest` as its own user unit. | `--plan ZIP` is diagnostic. `--start ZIP` is a deliberately disruptive **180-second** physical experiment, with independent rescue at **240 seconds**. Must have one original OSK and an active labwc/Wayland session; no `sudo`, system package modifications, desktop/autostart changes, or Headless/audio changes. For unexpected issues, `systemctl --user start acp-squeekboard-overlay-restore.service` requests early restore. **Do not run `--start` until `--plan` passes and user is ready at the touchscreen.** |
| `scripts/inspect-squeekboard-overlay-artifact.py` | Read-only target-Pi inspection of the successful ARM64 Squeekboard run #5 ZIP: pinned executable and .deb SHA-256/size, AArch64 ELF, package version/dependencies, every direct SONAME and target ldconfig cache. | Run as normal Pi user with an already downloaded ZIP. **No executable launch, package installation, service/autostart or keyboard process changes**. This is only a package/SONAME preflight, not proof of dynamic symbol compatibility or Wayland text entry. |

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/ci/prepare-squeekboard-overlay-source.py` | Downloads and checks the Raspberry Pi `1.43.1-1+rpt1` source package, extracts the six vendor patches and proves the commissioned Pi's exact original and patched `src/panel.c` SHA-256 values. | **Off-device disposable ARM64 builder only**; called from the dedicated GitHub Actions job, never by `setup.sh`. No system package deployment or keyboard process changes. |
| `scripts/ci/build-squeekboard-overlay-arm64.sh` | Installs vendor build dependencies inside a disposable Debian Trixie ARM64 container, compiles using the vendor Debian/Meson/Cargo rules as an unprivileged user, exports only a **test-only** Debian package, executable and ABI/dependency manifest. | **Never execute on the commissioned Pi.** Requires GitHub Actions, Docker-container marker and ARM64; `CARGO_NET_OFFLINE=true`; never copies, installs or starts the experimental OSK on a device. Run is triggered by `.github/workflows/squeekboard-overlay-arm64.yml` only. |

## Native Plexamp on-screen keyboard discovery

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/plan-squeekboard-build-deps.py` | Validates the commissioned Pi's staged Squeekboard `1.43.1-1+rpt1` panel SHA-256, overlay-layer marker, source provenance and vendor `debian/control` before asking APT's dependency solver which packages the exact source would need. | **Read-only APT simulation.** Run `python3 scripts/plan-squeekboard-build-deps.py` without sudo. Calls only `apt-get --simulate -o APT::Install-Recommends=false satisfy <Build-Depends>`; does not update repositories, install/build a package, alter the keyboard/desktop, or change audio/Headless. Review possible upgrades/removals before planning any installation. |

| File | Purpose | Safety / intended use |
| --- | --- | --- |
| `scripts/prepare-squeekboard-overlay.py` | Fetches **exact** Raspberry Pi Squeekboard `1.43.1-1+rpt1` source descriptor and tarballs via HTTPS, validates SHA-256/size entries, extracts via `dpkg-source`, then makes exactly one `TOP` → `OVERLAY` change in `src/panel.c`, recording a provenance manifest under the user's cache. Requires that the installed stock executable still matches the commissioned Pi SHA-256. | **Developer staging only; no system mutation.** `python3 scripts/prepare-squeekboard-overlay.py --plan` is offline/read-only; `--prepare` downloads and writes **only** in `~/.cache/a-clockwork-plex/squeekboard-overlay-1.43.1-1+rpt1`, refusing an existing destination. Does **not** install build dependencies, compile, run or stop Squeekboard, edit XDG/labwc, or alter audio/Headless. No `sudo`. Actual build and live single-instance handover require a separately reviewed procedure and watchdog rollback. |

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