# A Clockwork Plex documentation

There is quite a lot of engineering behind a bedside clock that mainly wants to tell the time and play something nice. 😄 This page is the signpost so you do **not** need to read all of it.

## I want to install it

Start with **[`INSTALL.md`](INSTALL.md)**.

That is the normal end-to-end guide for a fresh Raspberry Pi. The normal appliance command is simply:

```bash
bash setup.sh
```

You do not need the roadmap, acceptance records or archived engineering notes to install the appliance. They are here for development, verification and the inevitable future occasion when somebody asks, “Why on earth did we do it *that* way?”

For advanced installer controls and recovery, see [`appliance-installer.md`](appliance-installer.md).

## I want to understand how it works

These are the maintained technical guides:

| Document | What it explains |
| --- | --- |
| [`application-state-architecture.md`](application-state-architecture.md) | Playback, screen, Settings, Weather and audio ownership. |
| [`airplay-metadata.md`](airplay-metadata.md) | Shairport/AirPlay metadata, integration ownership and read-only troubleshooting. |
| [`alarm-audio-testing.md`](alarm-audio-testing.md) | Scheduled-alarm audio topology, safety limits and regression checks. |
| [`testing.md`](testing.md) | Local validation and GitHub Actions CI. |
| [`fresh-pi-bootstrap-ownership-design.md`](fresh-pi-bootstrap-ownership-design.md) | Why hardware/bootstrap ownership and reboot boundaries are deliberately constrained. |
| [`full-appliance-installer-design.md`](full-appliance-installer-design.md) | Design rationale for the guarded staged installer and rollback model. |

The editable/reference segment-display design asset is [`airplay-segment-cell.svg`](airplay-segment-cell.svg).

## I am validating a release or debugging something awkward

These documents are maintained release/evidence material rather than first-time setup instructions:

| Document | Purpose |
| --- | --- |
| [`fresh-appliance-acceptance-runbook.md`](fresh-appliance-acceptance-runbook.md) | Formal clean-room acceptance procedure and pinned identities. |
| [`final-clean-room-physical-progress-2026-08-21.md`](final-clean-room-physical-progress-2026-08-21.md) | Final replacement-SD physical evidence. |
| [`fresh-bootstrap-physical-progress-2026-08-15.md`](fresh-bootstrap-physical-progress-2026-08-15.md) | Earlier fresh-bootstrap physical evidence. |
| [`eq-to-direct-physical-verification-2026-08-17.md`](eq-to-direct-physical-verification-2026-08-17.md) | Focused EQ → Direct transition verification. |
| [`direct-independent-verification-2026-08-17.md`](direct-independent-verification-2026-08-17.md) | Independent Direct-route verification. |
| [`eq-to-direct-desktop-audio-blocker-2026-08-17.md`](eq-to-direct-desktop-audio-blocker-2026-08-17.md) | Focused EQ → Direct blocker/diagnostic evidence. |
| [`reboot-eq-runtime-failure-2026-08-17.md`](reboot-eq-runtime-failure-2026-08-17.md) | Reboot/runtime failure evidence and correction record. |
| [`weather-physical-followup-2026-08-17.md`](weather-physical-followup-2026-08-17.md) | Focused Weather/rainfall-history physical follow-up. |

The active engineering/release authority is [`eq-audio-installer-roadmap.md`](eq-audio-installer-roadmap.md), with the repository-cleanup record in [`release-hygiene-audit-2026-08-19.md`](release-hygiene-audit-2026-08-19.md). Those are contributor/release documents; normal users can cheerfully ignore them.

The two preserved roadmap-history snapshots remain alongside the active roadmap because it links to them directly:

- [`eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md`](eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md)
- [`eq-audio-installer-roadmap-history-through-checkpoint64.md`](eq-audio-installer-roadmap-history-through-checkpoint64.md)

## I have brought a shovel and would like some archaeology

Excellent. The old engineering material now lives under **[`archive/`](archive/)** instead of filling the main documentation directory with dozens of historical Stage-C and laboratory files.

[`archive/pre-release-engineering-snapshot-2026-08-22/`](archive/pre-release-engineering-snapshot-2026-08-22/) is an exact snapshot of the former `docs/` tree. It preserves the complete Stage-C trail, pre-production audio/DSP work, superseded implementation notes and historical copies of the other documents.

Nothing in the archive is deleted history, but nothing in it outranks the maintained documentation above either. If an archived command and a current guide disagree, trust the current guide. The archive is allowed to be old; that is rather the point. 🏺

## Maintenance rule

`tests/test_docs_catalog.py` keeps the main `docs/` directory deliberately small and checks that the archive snapshot remains present. New maintained documents should have a clear purpose here; development archaeology belongs in `archive/` rather than slowly rebuilding the paper mountain we have just tidied away.
