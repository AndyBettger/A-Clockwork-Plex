# Documentation map

This directory contains both **current release documentation** and the detailed engineering history that led to the accepted A Clockwork Plex appliance. Historical files are intentionally retained as provenance, but they are not automatically current instructions.

If two documents disagree, use the category order below: current operator/release authority first, then current architecture/testing guides. Historical designs/results explain how decisions were reached; they do not override the implemented release.

## Current operator and release authority

| Document | Purpose |
| --- | --- |
| `docs/INSTALL.md` | Normal fresh/repeat appliance installation and commissioning guide. Start here for a real appliance. |
| `docs/appliance-installer.md` | Advanced guide to the guarded lower-level `appliance-installer.sh` engine. |
| `docs/eq-audio-installer-roadmap.md` | Active Phase 7 implementation/acceptance/release-hygiene authority. |
| `docs/release-hygiene-audit-2026-08-19.md` | Current repository-cleanup classification and release-hygiene record. |
| `docs/fresh-appliance-acceptance-runbook.md` | Formal clean-room/replacement-SD acceptance procedure and pinned release identities. |

For normal installation, the human-facing command remains:

```bash
bash setup.sh
```

## Current architecture, operation and testing guides

| Document | Purpose |
| --- | --- |
| `docs/application-state-architecture.md` | Current authority/ownership architecture for playback, screen, Settings, Weather and audio. |
| `docs/airplay-metadata.md` | Current Shairport metadata/integration ownership and read-only troubleshooting. |
| `docs/alarm-audio-testing.md` | Current scheduled-alarm audio topology, safety model and regression procedure. |
| `docs/testing.md` | Current local validation runner and CI relationship. |

These documents describe implemented behavior. They are maintained alongside regression tests that pin critical wording/ownership boundaries.

## Final and focused physical evidence

These files are evidence records. They remain valuable because they capture what was physically observed on a specific acceptance run; they are not general installation instructions.

| Document | Evidence role |
| --- | --- |
| `docs/final-clean-room-physical-progress-2026-08-21.md` | Final replacement-SD clean-room evidence through the empty tracked-checkout proof. |
| `docs/fresh-bootstrap-physical-progress-2026-08-15.md` | Earlier fresh-bootstrap physical evidence. |
| `docs/eq-to-direct-physical-verification-2026-08-17.md` | Focused EQ → Direct transition verification. |
| `docs/direct-independent-verification-2026-08-17.md` | Independent Direct-route verification. |
| `docs/eq-to-direct-desktop-audio-blocker-2026-08-17.md` | Focused blocker/diagnostic evidence from EQ → Direct validation. |
| `docs/reboot-eq-runtime-failure-2026-08-17.md` | Reboot/runtime failure evidence and correction record. |
| `docs/weather-physical-followup-2026-08-17.md` | Focused Weather/rainfall-history physical follow-up. |

## Durable design/rationale records

These remain useful for explaining design ownership, but the running implementation, current operator docs and active roadmap win when an old design detail has since changed.

| Document | Rationale role |
| --- | --- |
| `docs/fresh-pi-bootstrap-ownership-design.md` | Why fresh-Pi hardware/bootstrap ownership and reboot boundaries are constrained. |
| `docs/full-appliance-installer-design.md` | Design rationale for staged guarded appliance installation and rollback. |
| `docs/airplay-segment-cell.svg` | Editable/reference visual design asset used during accepted AirPlay/segment presentation work. |

## Roadmap archives

These are deliberately preserved snapshots of former active-roadmap content:

| Document | Archive role |
| --- | --- |
| `docs/eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md` | Detailed earlier roadmap chronology through Phase 7 checkpoint 6. |
| `docs/eq-audio-installer-roadmap-history-through-checkpoint64.md` | Exact pre-consolidation active-roadmap snapshot through physical checkpoint #64. |

Do not edit these archives to make them sound current; their value is preserving the historical record.

## Historical development and laboratory records

The following families are intentionally retained as engineering provenance. Their status lines, commands, service ownership and “next step” wording may describe an earlier phase and **must not be treated as current instructions**.

### Retired Stage-C transaction/deployment history

Every `docs/stage-c*.md` file and `docs/production-eq-stage-c-install-design.md` belongs to the retired Stage-C validation/deployment lineage. The executable Stage-C subsystem and its dedicated positive tests were retired at checkpoint #65; the Markdown history remains so the design/rehearsal trail is not erased.

### Pre-production EQ/DSP laboratory and rehearsal history

The historical EQ/audio development family includes:

- `docs/bedroom-dsp-laboratory-results.md`;
- `docs/post-mix-dsp-laboratory.md`;
- `docs/master-eq-testing.md`;
- `docs/production-eq-split-bus-design.md`;
- `docs/eq-audio-installation-manifest.md`;
- `docs/camilladsp-eq-helper-contract.md`;
- `docs/eq-audio-route-helper-contract.md`;
- `docs/direct-alarm-bypass-failback-result-2026-08-05.md`;
- every `docs/split-bus-*.md` file;
- every `docs/stage-seven-*.md` file.

These records contain valuable measurements and design reasoning, but some describe now-retired scripts, Stage-C as future work, or the earlier boost-dependent headroom model. The accepted release instead uses the current `scripts/audio/` lifecycle and fixed `-6.5 dB` music reserve recorded in the active roadmap/architecture.

### Other superseded implementation snapshots

| Document | Historical role |
| --- | --- |
| `docs/airplay-control-plane-review-2026-07-26.md` | Earlier AirPlay control-plane review before the final PlaybackCoordinator ownership model. |
| `docs/plexamp-4.12.4-restart-investigation.md` | Investigation tied to the older Plexamp 4.12.4 runtime; release runtime is 4.13.2. |
| `docs/post-weather-settings-redesign.md` | Implemented Settings-redesign checkpoint record. Useful regression provenance, but its “EQ next/physical validation remaining” status text predates the completed release-candidate acceptance. |

## Classification rule

`tests/test_docs_catalog.py` enforces this map. Every regular top-level artefact under `docs/` must match one of the explicit current/evidence/design/archive entries or one of the deliberately historical filename families above.

When adding a new document, classify it here at the same time. When an active guide becomes stale, either update it to current behavior or deliberately reclassify it as historical; do not leave ambiguous “current-looking” instructions beside the release authority.
