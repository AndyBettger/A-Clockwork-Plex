#!/usr/bin/python3
from __future__ import annotations

from pathlib import Path

from .host_review import EXPECTED_PRE_STAGE_C_ALSA_SHA256
from .package_review import ManifestEntry


def write_rollback_obligations(entries: list[ManifestEntry], output: Path) -> None:
    rows = ["order\tarea\trestore_action\tmandatory_verification"]
    order = 1

    def add(area: str, action: str, verification: str) -> None:
        nonlocal order
        rows.append(f"{order}\t{area}\t{action}\t{verification}")
        order += 1

    add("lock", "acquire the single Stage C route transaction lock", "no competing route writer")
    add("services", "stop only services recorded active at transaction start", "DAC and loopback endpoints released")
    add("camilladsp", "stop the managed CamillaDSP unit/process", "no CamillaDSP PID and DAC released")
    add("active ALSA", "restore the snapshotted pre-Stage-C ALSA file atomically", EXPECTED_PRE_STAGE_C_ALSA_SHA256)
    for entry in (item for item in entries if item.kind == "file"):
        add(
            entry.destination,
            "restore original file or exact absence marker",
            "checksum/mode/owner or verified absence matches activation-time snapshot",
        )
    add("managed directories", "remove only directories absent before install and empty after file rollback", "preinstall existence/mode/owner restored")
    add("systemd", "daemon-reload and restore exact enabled states", "all six service enabled/load states match snapshot")
    add("snd_aloop", "restore loaded and persistence state exactly", "index/id/substreams/pcm_notify and persistence files match snapshot")
    add("mixer", "restore all four captured control percentages", "live readback matches activation-time snapshot")
    add("services", "restore exact original active states", "application services match snapshot")
    add("final", "verify active route, services, module, mixer and managed-path state", "zero rollback mismatches")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_command_plans(review_root: Path) -> None:
    install = """STAGE C2 REVIEW ONLY — NOT AN EXECUTABLE INSTALLER

Future activated Stage C transaction sequence:

01. Acquire an exclusive route/install lock.
02. Re-run every host, package, checksum, conflict and service preflight.
03. Create a new activation-time snapshot; never reuse this Stage C2 review snapshot.
04. Stage every candidate on the destination filesystem and revalidate checksums/modes.
05. Stop plexamp.service, shairport-sync.service and a-clockwork-plex.service only.
06. Verify the DAC and loopback playback/capture endpoints are released.
07. Install deterministic snd_aloop persistence and the managed package atomically.
08. Run systemd daemon-reload without enabling source services differently.
09. Install the split-bus ALSA route atomically.
10. Start the route authority and managed CamillaDSP service.
11. Prove CamillaDSP PID, DAC format and split-bus route state.
12. Run finite low-level music-lane and alarm-lane probes.
13. Restore only the application services that were active before the transaction.
14. Verify CamillaDSP survives real service startup and dashboard health agrees.
15. Commit the transaction manifest only after every check passes.
16. On any failure before commit, execute exact rollback and verify every restored item.

Stage C2 intentionally contains no --activate option, no confirmation token and no root command path.
"""
    rollback = """STAGE C2 REVIEW ONLY — EXACT ROLLBACK ORDER

01. Acquire the same exclusive route/install lock.
02. Stop the application services that the failed transaction restarted.
03. Stop the managed CamillaDSP service and verify the DAC is released.
04. Restore the exact preinstall active ALSA file atomically.
05. Restore each managed file or its original absence marker.
06. Restore managed directory existence, modes and owners without deleting unrelated content.
07. Run systemd daemon-reload.
08. Restore exact service enabled states.
09. Restore exact snd_aloop loaded/options/persistence state.
10. Restore all four captured mixer controls.
11. Restore exact application service active states.
12. Compare every checksum, absence marker, mode, owner, module parameter, mixer value and service state.
13. Report rollback success only when the mismatch count is zero.
"""
    blockers = """Stage C activation remains blocked after this transaction-plan rehearsal.

Still required before any persistent install can be authorised:
- replace the inert Stage C1 route helper with reviewed transactional mutation logic;
- add activation-time snapshot/rollback implementation and one exact confirmation token;
- add atomic installation and exact uninstall entry points;
- add finite split-bus route probes and DAC ownership verification;
- add bounded CamillaDSP startup/failure handling and automatic direct failback;
- migrate the EQ helper/state/render/reload contract from alsaequal to CamillaDSP;
- connect root route/EQ health to dashboard diagnostics and degraded-mode warning;
- test install failure injection, deliberate CamillaDSP failure and exact uninstall rollback;
- receive explicit user authorisation for the physical install.
"""
    (review_root / "install-command-plan.txt").write_text(install, encoding="utf-8")
    (review_root / "rollback-command-plan.txt").write_text(rollback, encoding="utf-8")
    (review_root / "activation-blockers.txt").write_text(blockers, encoding="utf-8")
