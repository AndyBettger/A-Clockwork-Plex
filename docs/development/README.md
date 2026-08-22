# Development documentation

This directory contains the engineering material that is useful when changing, validating or diagnosing A Clockwork Plex, but which a normal appliance owner should not have to wade through. 🔧

## Architecture and design

- [`architecture/application-state-architecture.md`](architecture/application-state-architecture.md) — playback, screen, Settings, Weather and audio ownership.
- [`architecture/airplay-metadata.md`](architecture/airplay-metadata.md) — Shairport/AirPlay metadata and integration ownership.
- [`architecture/fresh-pi-bootstrap-ownership-design.md`](architecture/fresh-pi-bootstrap-ownership-design.md) — constrained hardware/bootstrap ownership and reboot boundaries.
- [`architecture/full-appliance-installer-design.md`](architecture/full-appliance-installer-design.md) — guarded staged installer and rollback rationale.
- [`architecture/airplay-segment-cell.svg`](architecture/airplay-segment-cell.svg) — editable/reference segment-display geometry.

## Testing and acceptance

- [`testing/testing.md`](testing/testing.md) — local validation and GitHub Actions CI.
- [`testing/alarm-audio-testing.md`](testing/alarm-audio-testing.md) — scheduled-alarm topology, safety limits and regression checks.
- [`testing/fresh-appliance-acceptance-runbook.md`](testing/fresh-appliance-acceptance-runbook.md) — formal clean-room/replacement-SD acceptance procedure.

## Evidence and investigations

The `evidence/` directory contains dated physical results, focused verification reports and release-hygiene records. They are retained because they explain what was actually proved on real hardware and why some safeguards exist.

They are **evidence, not installation instructions**. A 3 a.m. fault report may be fascinating, but it should not ambush somebody looking for the setup guide over breakfast. 😄

Current release/engineering authority remains the live [`../roadmap/ROADMAP.md`](../roadmap/ROADMAP.md), while normal installation remains [`../INSTALL.md`](../INSTALL.md).
