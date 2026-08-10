# Full appliance installer and multi-node weather design

**Status:** Phase 7 source/read-only integration green; guarded activation next  
**Last updated:** 10 August 2026  
**Branch:** `feature/alarm-engine`

## Goal

A Clockwork Plex should be installable as a complete, repeatable Raspberry Pi appliance rather than reconstructed from remembered component commands. The repository-root `install.sh` is the conductor: it owns profile choices, ordering, prerequisite gates, transactional success/failure and final whole-appliance verification while specialist components retain authority for their own subsystem implementation.

This is intended for multiple bedroom/office/replacement clocks. Machine-specific state must not be copied between nodes, and the root installer must not create second implementations of ALSA routing, EQ, AirPlay, weather or dashboard behaviour.

## Current safety boundary

`install.sh` is deliberately **plan-only** and rejects `--apply` while Phase 7 activation design is incomplete. Planning and all existing preflight/checker/verifier entrypoints are read-only.

Supported profile axes are:

```text
--audio direct|eq
--weather-observations ecowitt-push|weather-underground
--project-user USER
--non-interactive
```

The read-only gates are:

```bash
bash scripts/check-appliance-packages.sh ...
bash scripts/preflight-appliance.sh ...
bash scripts/check-appliance-components.sh ...
bash scripts/verify-appliance.sh ...
```

The root plan now prints the exact profile-matched package/preflight commands and the exact post-install verifier command a future guarded build must pass.

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

`installer/profiles/direct/alarm-safe.conf` materialises the fresh Direct route. `installer/lib/direct_audio.sh` currently validates/plans it and contains no production activation path.

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

The standalone EQ installer still defaults to `phase6-direct`, preserving its physically proven historical contract instead of implicitly accepting either route. Uninstall restores the exact route bytes/checksum captured before EQ activation, so fresh alarm-safe builds return to `654ff170...` while the bedroom Phase 6 rollback evidence remains `08d00093...`.

Pinned CamillaDSP artifact:

```text
version 4.1.3 aarch64
SHA-256 e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa
```

It is supplied/verified; no silent alternate download is allowed.

## Weather architecture for multiple clocks

Forecast and current observations remain independent responsibilities.

- **Forecast:** Open-Meteo for every observation profile.
- **Ecowitt custom push:** existing/default mode where the station can target that appliance.
- **Weather Underground PWS:** each appliance independently polls the configured upstream station.

No local weather fan-out/cache server is introduced.

`app/weather_observations.py` owns WU polling and health. The API key is looked up through a configured environment-variable name; the value is never normal Settings/config/status/browser data. `app/weather_observation_store.py` is the single production store for both provider paths, owning current readings, receipt time, daily extrema and local pressure history.

WU current pressure maps to established `baromrelin` inHg vocabulary. Documented rapid/hourly historical pressure range/trend aggregates are not treated as instantaneous historical samples. Existing state preserves barometer history across reboots; a new clock accumulates trustworthy current observations unless a future real station payload proves a better like-for-like history field.

Weather → Station Settings exposes provider choice and provider-specific non-secret options. Open-Meteo remains under forecast settings.

## Package and artifact ownership

The root installer is intended to own these Debian/Raspberry Pi OS packages:

```text
git
curl
python3
python3-venv
alsa-utils
shairport-sync
chromium
```

It will own creation/reuse of the repository venv and installation of `requirements.txt` into that venv.

`systemd`, `sudo`, desktop/session availability and kernel/ALSA support are platform prerequisites rather than application packages.

**Plexamp Headless remains an external prerequisite.** This repository verifies `plexamp.service` and its local control/API assumptions but does not pretend to own unsupported Plexamp distribution installation/update.

`check-appliance-packages.sh` is read-only: it queries package state/availability and never runs apt update/install, pip install or direct downloads.

## Project user and repository location

The full installer cannot assume `/home/andy/A-Clockwork-Plex`. `--project-user` is explicit. The dashboard specialist installer renders its candidate systemd unit from the selected User/Group and actual repository root/venv entrypoint, checks that candidate before guarded apply and retains its own rollback/API-health behaviour.

## Specialist component ownership

| Component | Read-only gate | Apply owner |
|---|---|---|
| Dashboard service | native check | `scripts/install-dashboard-service.sh` |
| Dashboard kiosk | native check | `scripts/install-dashboard-kiosk.sh` |
| AirPlay lifecycle hooks | shared adapter check | `scripts/install-airplay-hooks.sh` |
| AirPlay metadata listener | shared adapter check | `scripts/install-airplay-metadata-listener.sh` |
| Alarm-audio helper | shared adapter check | `scripts/install-alarm-audio-helper.sh` |
| Shairport-name helper | shared adapter check | `scripts/install-shairport-name-helper.sh` |
| Direct audio | dedicated profile validator | future guarded Direct component owner |
| EQ-capable audio | standalone prepare/verify | `scripts/audio/install-eq.sh` and lifecycle siblings |

Several older apply owners still mutate immediately. The root installer must not simply call them during discovery/planning. Guarded activation must either add prepare/confirm semantics to those specialists or wrap each with captured pre-state and deterministic rollback while keeping one implementation owner.

## Fresh-Pi prerequisite gate

`installer/lib/prerequisites.sh` and `scripts/preflight-appliance.sh` own the read-only host contract.

Source-only mode validates repository/component source on CI. Host mode checks Linux/Debian-RPi OS assumptions, aarch64, selected normal user/sudo environment, Python/venv/base tools, ALSA/Shairport/browser, external `plexamp.service`, physical card id `Pro`, EQ-only verified Camilla artifact and `snd_aloop`, and WU-only API-key environment presence without printing the secret.

Ecowitt network delivery remains a site/physical acceptance check.

## Appliance-level post-install verifier

`scripts/verify-appliance.sh` is the single read-only end-state verifier for the selected profile.

It checks:

- rendered dashboard identity/path;
- AirPlay lifecycle wrappers and metadata service;
- alarm-audio helper/sudoers;
- Shairport-name helper/sudoers;
- Shairport hooks, metadata FIFO and `acp_airplay` route;
- kiosk autostart;
- exact Direct route/no-EQ marker or delegated standalone EQ verification;
- selected weather configuration and Open-Meteo forecast retention;
- no secret-like WU fields in config.

On production root it additionally checks expected services and dashboard `/api/state`, `/api/weather/observations` and `/api/audio/eq` truthfulness. Alternate `--root` mode deliberately skips live probes while validating the same filesystem/config contracts in non-production.

Provider names are canonicalized at the CLI/config/API boundary (`ecowitt_push` ↔ `ecowitt-push`, `weather_underground` ↔ `weather-underground`) rather than forcing one layer's representation into another. The verifier reads the actual top-level observation-service snapshot and the nested `eq` payload returned by the EQ API.

## Complete non-production profile matrix

`tests/test_appliance_profile_matrix.py` covers all four combinations:

| Audio | Observations |
|---|---|
| Direct | Ecowitt push |
| Direct | Weather Underground |
| EQ-capable | Ecowitt push |
| EQ-capable | Weather Underground |

For every combination the test runs the root plan, source-only package contract, source-only fresh-Pi preflight, materialises common integration/config state and starts from the exact alarm-safe Direct route.

Direct cases run the whole-appliance verifier. EQ cases run the real rooted standalone EQ prepare/activation using `--baseline alarm-safe-direct`, run the whole-appliance verifier, uninstall and require exact restoration of the alarm-safe Direct route.

No CI test writes production `/etc`, `/usr/local`, systemd or audio devices.

Latest normal CI at source head `3606f59`: **Tests #3003 / run 31355427351 — PASS**, including compile, JavaScript/page wiring, shell syntax and **1440 unit tests**.

## Guarded top-level activation design

The next implementation is one root transaction, not a chain of optimistic shell calls.

Intended order:

1. require an explicit root-installer activation token and selected profiles;
2. rerun matching host package/preflight/component checks immediately before mutation;
3. capture root-level pre-state needed to restore packages/venv/config/component-owned files/services/routes;
4. install required OS packages and create/reuse the application venv/requirements;
5. install/verify dashboard service using the selected project identity/path;
6. install/verify Shairport lifecycle integration, metadata and restricted helpers;
7. establish exact alarm-safe Direct `654ff170...` as the common audio baseline;
8. if EQ selected, call the accepted standalone installer with `--baseline alarm-safe-direct` and verified Camilla artifact;
9. apply selected observation-provider configuration and secret **reference** while preserving Open-Meteo forecast configuration;
10. install/verify kiosk startup;
11. run `scripts/verify-appliance.sh` for the exact selected profile;
12. only after whole-appliance verification passes, declare the install committed; otherwise restore the preceding accepted state in deterministic reverse ownership order.

The root installer should coordinate specialist owners, not copy their ALSA/systemd/Shairport/weather algorithms.

## Rollback design principles

- Capture before first mutation.
- Every owned mutation records enough pre-state to restore exact prior presence/content/enablement where practical.
- Component rollback executes in reverse dependency/order and must not replace specialist rollback logic that already exists.
- EQ rollback/uninstall remains owned by the accepted standalone audio lifecycle.
- A failed post-install verifier is an installation failure, not a warning.
- Do not attempt to roll back an already-committed package manager transaction by inventing package versions unless exact prior package state/version is captured and restoration is supported; package rollback policy must be explicit before enabling `--apply`.
- Never leave a new clock half-configured and call it successful merely because the dashboard starts.

## Remaining gates before physical fresh-Pi install

- implement safe root-level apply/rollback wrappers for legacy immediate-mutating specialists;
- implement package/venv transaction with explicit rollback policy;
- implement guarded Direct activation owner;
- implement weather config/environment-secret reference installation;
- compose dashboard/kiosk/app verification into one guarded commit boundary;
- inject failures at meaningful non-production stages and prove restoration;
- only then enable a fresh-Pi physical rehearsal.

Live Weather Underground current/history inspection is deliberately separate: use a station ID and runtime secret installed on the host, never paste the API key into chat or save it in browser/config data.

## Relationship to the roadmap

`docs/eq-audio-installer-roadmap.md` is the active progress/acceptance authority. The detailed roadmap through Phase 7 checkpoint #6 is preserved verbatim in `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md` rather than being discarded. PR #2 remains Draft until explicit owner approval.
