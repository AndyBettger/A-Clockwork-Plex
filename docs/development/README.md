# Development documentation

This directory contains the engineering material that is useful when changing, validating or diagnosing A Clockwork Plex, but which a normal appliance owner should not have to wade through. 🔧

## Architecture and design

- [`architecture/application-state-architecture.md`](architecture/application-state-architecture.md) — playback, screen, Settings, Weather and audio ownership.
- [`architecture/configuration-backup-ownership.md`](architecture/configuration-backup-ownership.md) — portable backup/restore ownership, secret exclusions and Plexamp preference boundaries.
- [`architecture/reset-to-defaults.md`](architecture/reset-to-defaults.md) — bounded four-owner Reset transaction, rollback and physically accepted Home-reset semantics.
- [`architecture/appliance-resilience.md`](architecture/appliance-resilience.md) — queued storage/write hardening and kiosk-safe network-recovery design.
- [`architecture/touchscreen-text-entry.md`](architecture/touchscreen-text-entry.md) — shared touchscreen keyboard behaviour and the narrow local Plexamp text-entry bridge boundary.
- [`architecture/bbc-news.md`](architecture/bbc-news.md) — BBC RSS feed/cache authority, safe public story model and planned News presentation boundary.
- [`architecture/airplay-metadata.md`](architecture/airplay-metadata.md) — Shairport/AirPlay metadata and integration ownership.
- [`architecture/fresh-pi-bootstrap-ownership-design.md`](architecture/fresh-pi-bootstrap-ownership-design.md) — constrained hardware/bootstrap ownership and reboot boundaries.
- [`architecture/full-appliance-installer-design.md`](architecture/full-appliance-installer-design.md) — guarded staged installer and rollback rationale.
- [`architecture/airplay-segment-cell.svg`](architecture/airplay-segment-cell.svg) — editable/reference segment-display geometry.

## Testing and acceptance

- [`testing/testing.md`](testing/testing.md) — local validation, targeted-test guidance and GitHub Actions CI.
- [`testing/test-catalogue.md`](testing/test-catalogue.md) — maintained module-by-module catalogue of the automated regression suite, with purpose, run commands and expected-result contract.
- [`testing/alarm-audio-testing.md`](testing/alarm-audio-testing.md) — scheduled-alarm topology, safety limits and regression checks.
- [`testing/bbc-news-testing.md`](testing/bbc-news-testing.md) — fixture-based BBC feed/cache regression boundary and later physical UI acceptance scope.
- [`testing/fresh-appliance-acceptance-runbook.md`](testing/fresh-appliance-acceptance-runbook.md) — formal clean-room/replacement-SD acceptance procedure.
- [`testing/commissioned-pi-backup-restore-acceptance-2026-09-10.md`](testing/commissioned-pi-backup-restore-acceptance-2026-09-10.md) — chronological commissioned-Pi schema-v2 Backup → Reset → Restore acceptance record for #89/#90.

## Evidence and investigations

The `evidence/` directory contains dated physical results, focused verification reports and release-hygiene records. They are retained because they explain what was actually proved on real hardware and why some safeguards exist.

They are **evidence, not installation instructions**. A 3 a.m. fault report may be fascinating, but it should not ambush somebody looking for the setup guide over breakfast. 😄

Current release/engineering authority remains the live [`../roadmap/ROADMAP.md`](../roadmap/ROADMAP.md), while normal installation remains [`../INSTALL.md`](../INSTALL.md).