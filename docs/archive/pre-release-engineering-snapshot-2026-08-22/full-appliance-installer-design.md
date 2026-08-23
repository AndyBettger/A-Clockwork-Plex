# Full appliance installer and multi-node weather design

**Status:** Phase 7 source/transaction implementation green; physical fresh-appliance acceptance next  
**Last updated:** 11 August 2026  
**Branch:** `feature/alarm-engine`  
**PR:** #2 remains Draft/open/unmerged until explicit owner approval.

## Goal

A Clockwork Plex is being made installable as a complete, repeatable Raspberry Pi appliance rather than reconstructed from remembered component commands. Repository-root `install.sh` is the conductor: it owns profile choices, ordering, prerequisite gates and the handoff into one whole-application transaction while specialist components retain authority for their own subsystem implementation.

This is intended for multiple bedroom/office/replacement clocks. Machine-specific state must not be copied between nodes, and the root installer must not create second implementations of ALSA routing, EQ, AirPlay, weather or dashboard behaviour.

## Current safety boundary

`install.sh` remains **read-only plan mode by default**. Production mutation requires:

```text
--apply --confirm APPLY-A-CLOCKWORK-PLEX
```

The accepted root apply sequence is:

1. read-only package/artifact availability check;
2. read-only **pre-bootstrap platform/external preflight**;
3. guarded additive package + staged/verified venv bootstrap;
4. read-only **full post-bootstrap host preflight**;
5. one guarded whole-application transaction;
6. one profile-aware whole-appliance verifier inside the transaction commit boundary.

The first host preflight uses `--bootstrap-pending`. Package-owned tools may report `READY` there because their absence is exactly what the bootstrap is meant to fix. Platform/external requirements still fail closed before package mutation. After bootstrap, the same preflight runs without `--bootstrap-pending` and every installer-owned prerequisite must actually exist before application mutation can start.

No Phase 7 root installer checkpoint has been deployed to the physically accepted bedroom Pi.

## Supported profile axes

```text
--audio direct|eq
--weather-observations ecowitt-push|weather-underground
--project-user USER
--non-interactive
```

EQ apply additionally requires a supplied, verified CamillaDSP 4.1.3 aarch64 binary. Weather Underground apply additionally requires station ID plus an API-key **file path**; the secret value is never a normal command-line/config/browser field.

## Audio profiles

### Direct

Fresh appliances use the physically proven alarm-safe Direct route:

```text
654ff170e6a009d50fa7494500ca930093aa22ab6cd10a606a7d7fe14d0493c9
```

Graph:

```text
Plexamp -> Plexamp trim --\
                          +-> Music Master -> DAC-facing mix
AirPlay -> AirPlay trim --/
Alarm -> Maximum Alarm Volume -----------> DAC-facing mix
```

Alarm bypasses Music Master.

The historical route `08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9` remains the exact Phase 6 uninstall baseline for the already-accepted bedroom-Pi lifecycle. It is not promoted to the fresh Direct profile because its historical graph puts alarm under Music Master.

`scripts/audio/install-direct.sh` is the guarded fresh-Direct activation owner. It defaults to prepare-only and requires `--activate --confirm INSTALL-DIRECT-AUDIO`.

### EQ-capable

EQ-capable audio reuses the accepted `scripts/audio/*` lifecycle rather than duplicating it.

```text
Plexamp / AirPlay -> source trims -> Music Master -> fixed -6.5 dB reserve
                                                -> Bass/Mid/Treble
Alarm -> per-alarm target/fade -> Maximum Alarm Volume

both lanes -> final -1 dB limiter -> DAC
```

Fresh EQ builds first establish alarm-safe Direct and call:

```text
scripts/audio/install-eq.sh ... --baseline alarm-safe-direct
```

The standalone EQ installer still defaults to `phase6-direct`, preserving the physically proven bedroom rollback contract. Uninstall restores the exact route bytes/checksum captured before EQ activation, so fresh alarm-safe builds return to `654ff170...` while the bedroom Phase 6 rollback evidence remains `08d00093...`.

Pinned CamillaDSP artifact:

```text
version 4.1.3 aarch64
SHA-256 e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

It is supplied and verified; the repository does not silently download or substitute an alternate binary.

`scripts/audio/verify-audio.sh`, `repair-audio.sh` and `uninstall-eq.sh` remain the specialist verify/recovery/uninstall authorities.

## Weather architecture for multiple clocks

Forecast and current observations remain independent responsibilities.

- **Forecast:** Open-Meteo for every observation profile.
- **Ecowitt custom push:** existing/default mode where the station can target that appliance.
- **Weather Underground PWS:** each appliance independently polls the configured upstream station.

No local weather fan-out/cache server is introduced.

`app/weather_observations.py` owns WU current polling and health. `app/weather_observation_store.py` remains the single production store for both provider paths, owning current readings, receipt time, daily extrema and locally accumulated pressure history.

WU current pressure maps to established `baromrelin` inHg vocabulary. Historical aggregate/range fields are **not** silently treated as instantaneous barometer samples. A new clock accumulates trustworthy current observations unless real upstream history evidence proves a like-for-like historical pressure field.

### WU credential contract

Fresh and repeat installs use a secret-file path:

```text
--wu-api-key-file PATH
```

The path may be passed through root install, preflight, guarded weather installation and post-install verification. The secret value itself is not printed, stored in `config.json`, exposed to browser state or accepted as a literal root-installer argument.

The guarded weather owner stores production runtime material under:

```text
/etc/default/a-clockwork-plex-weather
```

with the dashboard service consuming it through its optional systemd `EnvironmentFile`.

### WU current/history inspection

`scripts/inspect-weather-underground-payloads.py` is a read-only acceptance tool. It fetches the existing WU current and one-day history endpoints using station ID plus API-key file, but never prints credential-bearing request URLs or writes dashboard/config/history state.

It reports payload keys, observation counts, timestamp evidence, unit blocks and pressure-related paths. A history payload is only labelled `YES — REVIEW REQUIRED` when every row exposes `obsTimeUtc` plus numeric `imperial.pressure`. Aggregate/range fields such as `pressureAvg`, `pressureMin` or `pressureMax` are explicitly not promoted into instantaneous samples.

## Package and artifact ownership

The guarded package bootstrap owns these Debian/Raspberry Pi OS packages:

```text
git
curl
python3
python3-venv
alsa-utils
shairport-sync
chromium
```

It also owns staged creation/replacement of the repository venv and installation/verification of `requirements.txt`.

Package rollback is intentionally additive: packages successfully installed as shared host prerequisites are not automatically removed/purged/autoremoved after a later application failure. The verified venv is staged before replacement and a failed venv activation restores the exact previous directory or previous absence.

`systemd`, `sudo`, the normal desktop/session environment and kernel/ALSA support are platform prerequisites rather than application packages.

**Plexamp Headless remains an external prerequisite.** This repository verifies `plexamp.service` and its local API assumptions but does not pretend to own unsupported Plexamp distribution installation/update.

CamillaDSP is a supplied/verified EQ artifact, not an APT package and not silently downloaded.

## Fresh-Pi prerequisite gate

`installer/lib/prerequisites.sh` and `scripts/preflight-appliance.sh` own the read-only host contract.

### Pre-bootstrap mode

```bash
bash scripts/preflight-appliance.sh --bootstrap-pending ...
```

This must pass before package mutation. It requires the correct Linux/Debian-Raspberry Pi platform, aarch64 architecture, normal project user, physical ALSA card id `Pro`, external `plexamp.service`, profile-specific EQ artifact/kernel capability and the selected weather credential input. Installer-owned packages may be `READY` if absent.

### Post-bootstrap mode

```bash
bash scripts/preflight-appliance.sh ...
```

This runs after package/venv bootstrap and requires package-owned Python/venv, ALSA tools, Shairport Sync/service and Chromium to exist. Application mutation does not begin unless this full host gate passes.

Source-only mode remains available for CI and never probes the current host.

Ecowitt network delivery remains a site/physical acceptance check.

## Specialist component ownership

| Component | Guarded apply owner |
|---|---|
| Package + repository venv | `scripts/install-appliance-packages.sh` |
| Weather observation config/secret reference | `scripts/install-weather-config.sh` |
| Dashboard service + kiosk | `scripts/install-dashboard-integration.sh` |
| Fresh Direct audio | `scripts/audio/install-direct.sh` |
| EQ-capable audio | `scripts/audio/install-eq.sh` + lifecycle siblings |
| Alarm-audio + Shairport-name helper packaging | `scripts/install-appliance-helpers.sh` |
| AirPlay lifecycle + metadata + Shairport integration | `scripts/install-airplay-integration.sh` |
| Whole application sequence | `scripts/install-appliance-application.sh` |

Root `install.sh` does not call the individual application specialist activation entrypoints directly. It establishes prerequisites and delegates the whole application mutation sequence to `scripts/install-appliance-application.sh`.

## Whole-application transaction

Package/venv bootstrap forms the prerequisite baseline. After the post-bootstrap full preflight passes, `scripts/install-appliance-application.sh` captures the application-managed pre-state and owns this order:

1. weather observation configuration/managed secret reference;
2. dashboard service + kiosk;
3. alarm-safe Direct baseline when required;
4. optional EQ installation/repair;
5. restricted helpers;
6. AirPlay/Shairport integration;
7. `scripts/verify-appliance.sh` as final commit gate.

`installer/lib/application_transaction.sh` captures application configuration, weather environment, dashboard/kiosk, helper policies, AirPlay/Shairport integration, metadata FIFO, Direct/EQ route/state and relevant service state.

A newly installed EQ is unwound through the accepted EQ uninstaller **before** generic application-state restoration. Alternate-root failure injection has proved this ordering and exact restoration for both Direct and fresh-EQ late failures.

A failed final verifier is an installation failure, not a warning.

## Appliance-level post-install verifier

`scripts/verify-appliance.sh` is the single read-only end-state verifier for the selected profile.

It checks:

- rendered dashboard identity/path;
- accepted AirPlay lifecycle wrapper semantics and metadata service;
- alarm-audio helper/sudoers;
- Shairport-name helper/sudoers;
- Shairport hooks, metadata FIFO and `acp_airplay` route;
- kiosk autostart;
- exact Direct route/no-EQ marker or delegated standalone EQ verification;
- selected weather configuration and Open-Meteo forecast retention;
- no secret-like WU fields in config;
- WU credential-file validity when supplied for production verification.

On production root it additionally checks expected services and dashboard `/api/state`, `/api/weather/observations` and `/api/audio/eq` truthfulness. Alternate `--root` mode deliberately skips live probes while validating the same filesystem/config contracts in non-production.

## Complete non-production profile matrix and rollback evidence

`tests/test_appliance_profile_matrix.py` covers all four combinations:

| Audio | Observations |
|---|---|
| Direct | Ecowitt push |
| Direct | Weather Underground |
| EQ-capable | Ecowitt push |
| EQ-capable | Weather Underground |

For every combination the test exercises the root/source contracts and profile-aware verifier. EQ cases run the real rooted standalone EQ prepare/activation using `--baseline alarm-safe-direct`, then uninstall and require exact restoration of the alarm-safe Direct route.

Additional application-transaction tests inject late failures after specialist mutation. Direct rollback restores prior files/FIFO/route state; fresh-EQ rollback additionally proves the EQ uninstaller runs before outer restoration and returns a deliberately different pre-appliance route exactly.

No CI test writes production `/etc`, `/usr/local`, systemd or audio devices.

## Root production apply

The implemented root sequence is intentionally thin:

```text
install.sh
  -> package/artifact checker
  -> preflight --bootstrap-pending
  -> guarded package/venv bootstrap
  -> full preflight
  -> guarded whole-application transaction
       -> specialist owners
       -> whole-appliance verifier
       -> commit or rollback
```

The root installer coordinates authorities; it does not copy their ALSA/systemd/Shairport/weather logic.

## Rollback design principles

- Capture before first application mutation.
- Package additions are an explicit retained prerequisite baseline; no destructive automatic apt rollback.
- Staged venv activation restores exact previous directory/absence on activation failure.
- Every application-owned mutation records enough pre-state to restore prior presence/content/mode/enablement where practical.
- Component rollback executes in reverse dependency/order and does not replace specialist rollback logic.
- Fresh EQ teardown uses the accepted EQ uninstaller before generic restoration.
- A failed post-install verifier is an installation failure.
- Never leave a new clock half-configured and call it successful merely because the dashboard starts.

## Remaining gates before Phase 7 closes

Source/CI architecture is implemented and green. Remaining work is physical acceptance on a **fresh/disposable target**, not the accepted bedroom Pi:

1. fresh Direct whole-appliance install and physical Plexamp/AirPlay/alarm/UI acceptance;
2. fresh EQ promotion, physical isolation/EQ acceptance and reboot verification;
3. real Weather Underground current + recent-history payload inspection using the read-only inspector;
4. real WU runtime acceptance with secret installed only on the host;
5. repeat the whole-appliance installer on the already-configured fresh target and require a clean verifier/no ownership drift.

A live WU history payload is evidence for review only; history is not automatically ingested into barometer state during this acceptance.

## Relationship to the roadmap

`docs/eq-audio-installer-roadmap.md` is the active progress/acceptance authority. Detailed earlier history is preserved in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`. The physical acceptance procedure is maintained in `docs/fresh-appliance-acceptance-runbook.md` once created.

PR #2 remains Draft and must not be made ready or merged without explicit owner approval.
