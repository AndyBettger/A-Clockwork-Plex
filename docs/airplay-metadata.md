# AirPlay metadata and integration

A Clockwork Plex receives AirPlay metadata from Shairport Sync and presents it on the AirPlay dashboard surface. Metadata collection is deliberately separate from playback ownership: **PlaybackCoordinator** owns Plexamp/AirPlay handoff, while the metadata listener only observes and publishes sender information.

## Current ownership

```text
Shairport start/end callbacks
  → publish lifecycle intent to PlaybackCoordinator
  → never stop/start Plexamp or Shairport Sync

Shairport metadata FIFO
  → a-clockwork-plex-airplay-metadata.service
  → airplay-metadata-listener.py
  → sanitised AirPlay metadata/state for the dashboard

PlaybackCoordinator
  → decides Plexamp ↔ AirPlay takeover
  → owns paused-sender hold and transport commands
```

The callback scripts installed on the appliance are rendered from `scripts/a-clockwork-plex-airplay-wrappers.py`. The guarded owner for the callbacks, Shairport configuration, FIFO and metadata-listener service is `scripts/install-airplay-integration.sh`.

The old static callbacks that directly managed `plexamp.service`, the old `display-mode.sh` fallback and the standalone metadata-listener installer are retired and regression-pinned absent.

## Normal installation

Do not install the metadata listener separately on a normal appliance. AirPlay integration is part of the supported appliance convergence:

```bash
cd ~/A-Clockwork-Plex
bash setup.sh
```

For deliberate component-level diagnosis, the guarded integration owner is prepare-only by default:

```bash
bash scripts/install-airplay-integration.sh --prepare-only
```

A direct component activation is an advanced recovery/development action and requires the explicit guard:

```bash
bash scripts/install-airplay-integration.sh \
  --activate \
  --confirm INSTALL-AIRPLAY-INTEGRATION
```

Prefer the full `setup.sh` path unless there is a specific reason to operate on the AirPlay component alone.

## Managed metadata contract

The integration owner configures Shairport Sync to publish metadata to the managed FIFO used by the listener service. The listener decodes the Shairport line-oriented metadata stream and exposes sanitised values used by the dashboard, including fields such as:

```text
title
artist
album
genre
source_name
source_model
volume
client_ip
artwork
```

Availability varies by sending application. Missing fields are normal and do not give the metadata layer permission to infer playback ownership or manufacture transport state.

## Check Shairport metadata support

```bash
shairport-sync -V
```

The installed Shairport Sync build must support metadata. If the AirPlay destination works but no metadata ever arrives, this is one of the first host-level checks.

## Read-only diagnostics

Service state:

```bash
systemctl status a-clockwork-plex-airplay-metadata.service --no-pager
systemctl status shairport-sync.service --no-pager
```

Recent listener logs:

```bash
journalctl -u a-clockwork-plex-airplay-metadata.service -n 100 --no-pager
```

Dashboard state:

```bash
curl -s http://localhost:8088/api/status | python -m json.tool
curl -s http://localhost:8088/api/playback/state | python -m json.tool
```

Raw Shairport MPRIS observation can be watched with the retained diagnostic:

```bash
bash scripts/dump-airplay-mpris-metadata.sh
```

That command is read-only and is useful for distinguishing “the sender did not publish it” from “the dashboard failed to present it.”

For the complete playback/handoff decision snapshot:

```bash
bash scripts/inspect-playback-coordinator.sh
```

## Metadata FIFO troubleshooting

The metadata path must be a FIFO, not an ordinary file. The appliance verifier and guarded installer own the exact managed path and mode. If integration verification reports the FIFO missing or wrong, do not recreate it ad hoc while services are running; use the guarded integration owner so exact rollback and candidate validation remain available.

## Shairport configuration troubleshooting

If Shairport configuration is suspected, validate the installed configuration before restarting anything:

```bash
shairport-sync -t
```

The guarded integration owner renders the required metadata and session-control blocks without replacing the configured receiver name. A failed candidate validation is read-only and must not replace the live configuration.

## Artwork

Some sending applications provide artwork and some do not. The dashboard must continue to present available text metadata when artwork is absent. Generated runtime artwork belongs to ignored runtime state rather than tracked repository source.

## Handoff troubleshooting rule

Metadata is evidence, not authority. If a sender appears stuck, inspect PlaybackCoordinator and Shairport observations rather than editing callback scripts or restarting audio services from a browser hook. The accepted handoff implementation intentionally keeps Plexamp, Shairport Sync and CamillaDSP service ownership outside the metadata listener.
