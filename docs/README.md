# A Clockwork Plex documentation

There is quite a lot of engineering behind a bedside clock that mainly wants to tell the time and play something nice. 😄 This page is the short route through it.

## I want to install or use it

Start with **[`INSTALL.md`](INSTALL.md)**.

That is the normal end-to-end guide for a fresh Raspberry Pi. The normal appliance command is simply:

```bash
bash setup.sh
```

For advanced installer controls and recovery, see [`appliance-installer.md`](appliance-installer.md).

That is deliberately almost everything a normal owner needs to see in this directory. You should not have to read an audio-verification report from 17 August just because you wanted to find out where the Weather Underground key goes. 😁

## I am developing or debugging it

Current architecture, testing, release-validation and physical-evidence material lives under **[`development/`](development/)**.

That includes:

- architecture and design rationale;
- local/CI testing guidance;
- the clean-room acceptance runbook;
- dated physical verification and fault-investigation records;
- release-hygiene evidence.

These files remain useful and maintained where appropriate, but they are intentionally kept out of the normal-user path.

## I want the roadmap

The live project roadmap is **[`roadmap/ROADMAP.md`](roadmap/ROADMAP.md)**.

The project originally grew out of an EQ/audio-installer roadmap. It then acquired a full appliance installer, alarms, Weather history, AirPlay ownership, NFC, theme work, clean-room acceptance and enough other jobs to make the old name increasingly optimistic. The live file is therefore simply **the A Clockwork Plex roadmap** now. 😄

Older roadmap snapshots are preserved beside it under [`roadmap/`](roadmap/) and in the exact pre-release archive.

## I have brought a shovel and would like some archaeology

Excellent. Superseded Stage-C work, laboratory experiments and old engineering snapshots live under **[`archive/`](archive/)**.

[`archive/pre-release-engineering-snapshot-2026-08-22/`](archive/pre-release-engineering-snapshot-2026-08-22/) is an exact snapshot of the former engineering-heavy `docs/` tree. It preserves the complete Stage-C trail, pre-production audio/DSP work and historical copies of documents that later moved or changed.

Nothing in the archive is deleted history, but nothing in it outranks the maintained documentation above either. If an archived command and a current guide disagree, trust the current guide. The archive is allowed to be old; that is rather the point. 🏺

## Maintenance rule

The root of `docs/` is intentionally boring and small:

- `README.md`
- `INSTALL.md`
- `appliance-installer.md`
- `development/`
- `roadmap/`
- `archive/`

`tests/test_docs_catalog.py` enforces that boundary so the paper mountain cannot quietly grow back while nobody is looking.
