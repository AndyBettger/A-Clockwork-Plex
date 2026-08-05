#!/usr/bin/python3
from __future__ import annotations

import argparse
import csv
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_SCRIPTS = SCRIPT_DIR.parent
if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))

from stage_c_transaction.host_review import (
    APPLICATION_SERVICES,
    APPROVAL_MARKER,
    CURRENT_ALSA,
    EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    STAGE_C_SERVICES,
    capture_mixer_states,
    capture_module_and_dac,
    capture_service_states,
    running_camilladsp_pids,
    validate_service_boundary,
)
from stage_c_transaction.package_review import (
    EXPECTED_PACKAGE_FILES,
    mode_string,
    owner_string,
    parse_manifest,
    sha256,
    validate_stage_c1_evidence,
)
from stage_c_transaction.snapshot_core import (
    chown_evidence_tree,
    collect_filesystem_snapshot,
    write_evidence_manifest,
)

REQUIRED_CONFIRMATION = "STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY"
SNAPSHOT_PREFIX = "a-clockwork-plex-stage-c3-snapshot."
EXPECTED_STAGE_C2_CHECKS = (
    "stage-c1-package-evidence",
    "manifest-replay",
    "current-audio-graph",
    "package-inertness",
    "destination-conflict-gate",
    "review-snapshot",
    "service-state-boundary",
    "mixer-state-capture",
    "module-dac-capture",
    "rollback-contract",
    "activation-interface",
)
PROTECTED_DESTINATION = "/etc/sudoers.d/a-clockwork-plex-audio-route"
SNAPSHOT_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture a read-only root-owned Stage C activation-boundary snapshot. "
            "This is not an installer and has no activation path."
        )
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c2-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _first_module_parameter(name: str) -> str:
    path = Path("/sys/module/snd_aloop/parameters") / name
    try:
        return path.read_text(encoding="utf-8").strip().split(",", 1)[0]
    except OSError as exc:
        raise SystemExit(f"Cannot read snd_aloop {name}: {exc}") from exc


def invoking_identity() -> tuple[int, int, str]:
    if os.geteuid() != 0:
        raise SystemExit("Stage C3 capture must run through sudo as root.")
    try:
        uid = int(os.environ["SUDO_UID"])
        gid = int(os.environ["SUDO_GID"])
        user = os.environ["SUDO_USER"]
    except (KeyError, ValueError) as exc:
        raise SystemExit("Stage C3 requires a non-root sudo invoking identity.") from exc
    if uid <= 0 or gid < 0 or not user or user == "root":
        raise SystemExit("Stage C3 refuses a root or unresolved invoking identity.")
    return uid, gid, user


def validate_snapshot_root(raw: Path, invoking_uid: int) -> Path:
    if not raw.is_absolute() or raw.parent != Path("/var/tmp"):
        raise SystemExit("--snapshot-root must be directly beneath /var/tmp.")
    if not raw.name.startswith(SNAPSHOT_PREFIX):
        raise SystemExit(f"--snapshot-root name must start with {SNAPSHOT_PREFIX}")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit("--snapshot-root must already exist and be empty.") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("--snapshot-root must be a real directory, not a symlink or special object.")
    if info.st_uid != invoking_uid:
        raise SystemExit("--snapshot-root must be owned by the invoking user before capture.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("--snapshot-root must have mode 0700.")
    if any(raw.iterdir()):
        raise SystemExit("--snapshot-root must be empty.")
    return raw


def _validate_user_review_root(path: Path, expected_prefix: str, invoking_uid: int) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.parent != Path("/var/tmp") or not resolved.name.startswith(expected_prefix):
        raise SystemExit(f"Unexpected review directory: {resolved}")
    info = resolved.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"Review path is not a real directory: {resolved}")
    if info.st_uid != invoking_uid:
        raise SystemExit(f"Review path is not owned by the invoking user: {resolved}")
    return resolved


def validate_stage_c2_evidence(stage_c2_root: Path, package_root: Path) -> None:
    results_path = stage_c2_root / "results.tsv"
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows or rows[0] != ["check", "result", "detail"]:
        raise SystemExit("Unexpected Stage C2 results header.")
    observed = [row[0] for row in rows[1:] if len(row) == 3 and row[1] == "PASS"]
    if tuple(observed) != EXPECTED_STAGE_C2_CHECKS or len(rows) != len(EXPECTED_STAGE_C2_CHECKS) + 1:
        raise SystemExit("Stage C2 does not contain the exact eleven-check PASS contract.")

    report = (stage_c2_root / "report.txt").read_text(encoding="utf-8")
    for expected in (
        "Planner version: 2",
        f"Stage C1 package: {package_root}",
        "Managed package files: 12",
        "Existing managed destination conflicts: 0",
        "Privileged destination checks required: 1",
        f"- {PROTECTED_DESTINATION}",
        "- no --activate or --confirm option exists",
        "- no sudo command was invoked",
    ):
        if expected not in report:
            raise SystemExit(f"Stage C2 report contract is missing: {expected}")

    destination_state = (stage_c2_root / "destination-state.tsv").read_text(encoding="utf-8")
    protected_rows = [
        line
        for line in destination_state.splitlines()
        if PROTECTED_DESTINATION in line and "privileged-check-required:permission-denied-errno-13" in line
    ]
    if len(protected_rows) != 1:
        raise SystemExit("Stage C2 protected-destination evidence is not exact.")

    expected_fingerprints = {
        "manifest.tsv": sha256(package_root / "manifest.tsv"),
        "results.tsv": sha256(package_root / "results.tsv"),
        "report.txt": sha256(package_root / "report.txt"),
    }
    with (stage_c2_root / "package-fingerprint.tsv").open("r", encoding="utf-8", newline="") as handle:
        fingerprint_rows = list(csv.reader(handle, delimiter="\t"))
    if not fingerprint_rows or fingerprint_rows[0] != ["item", "sha256"]:
        raise SystemExit("Unexpected Stage C2 package fingerprint header.")
    observed_fingerprints = {row[0]: row[1] for row in fingerprint_rows[1:] if len(row) == 2}
    if observed_fingerprints != expected_fingerprints:
        raise SystemExit("Stage C2 package fingerprint no longer matches the supplied Stage C1 package.")


def validate_current_host_as_root() -> None:
    if platform.machine() != "aarch64":
        raise SystemExit(f"Expected aarch64; found {platform.machine()}.")
    if not CURRENT_ALSA.is_file() or CURRENT_ALSA.is_symlink():
        raise SystemExit(f"Current ALSA route is missing or symlinked: {CURRENT_ALSA}")
    if sha256(CURRENT_ALSA) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit("Current ALSA checksum is not the physically validated pre-Stage-C route.")
    if mode_string(CURRENT_ALSA) != "644" or owner_string(CURRENT_ALSA) != "root:root":
        raise SystemExit("Current ALSA owner/mode differs from the validated pre-Stage-C state.")
    text = CURRENT_ALSA.read_text(encoding="utf-8")
    start = text.index("pcm.acp_alarm_volume")
    end = text.index("pcm.acp_alarm {", start)
    if 'slave.pcm "acp_master"' not in text[start:end]:
        raise SystemExit("Current route is not the expected alarm-under-Master rollback graph.")

    expected = {"index": "7", "id": "ACP_Loopback", "pcm_substreams": "2", "pcm_notify": "1"}
    for name, value in expected.items():
        observed = _first_module_parameter(name)
        if observed != value:
            raise SystemExit(f"Unexpected snd_aloop {name}: {observed}")
    if APPROVAL_MARKER.exists():
        raise SystemExit(f"Unexpected Stage C approval marker already exists: {APPROVAL_MARKER}")
    pids = running_camilladsp_pids()
    if pids:
        raise SystemExit(f"Unexpected running CamillaDSP process: {pids}")


def append_result(results: Path, check: str, detail: str) -> None:
    with results.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def write_package_fingerprint(package_root: Path, output: Path) -> None:
    output.write_text(
        "item\tsha256\n"
        f"manifest.tsv\t{sha256(package_root / 'manifest.tsv')}\n"
        f"results.tsv\t{sha256(package_root / 'results.tsv')}\n"
        f"report.txt\t{sha256(package_root / 'report.txt')}\n",
        encoding="utf-8",
    )


def write_rollback_ledger(entries: list, output: Path, snapshot_root: Path) -> None:
    rows = ["order\tarea\trestore_action\tmandatory_verification"]
    order = 1

    def add(area: str, action: str, verification: str) -> None:
        nonlocal order
        rows.append(f"{order}\t{area}\t{action}\t{verification}")
        order += 1

    add("scope", f"use a new activation snapshot; never reuse rehearsal {snapshot_root}", "future transaction ID differs")
    add("lock", "acquire the single Stage C route transaction lock before the future snapshot", "no competing route writer")
    add("services", "stop only services recorded active in the future activation snapshot", "DAC and loopback endpoints released")
    add("camilladsp", "stop the managed CamillaDSP unit/process", "no CamillaDSP PID and DAC released")
    add("active ALSA", "restore the future snapshotted pre-Stage-C ALSA file atomically", EXPECTED_PRE_STAGE_C_ALSA_SHA256)
    for entry in (item for item in entries if item.kind == "file"):
        add(
            entry.destination,
            "restore original file or exact verified absence from the future root-owned activation snapshot",
            "checksum/mode/owner or verified absence matches that activation snapshot",
        )
    add("managed directories", "remove only directories absent before install and empty after file rollback", "preinstall existence/mode/owner restored")
    add("systemd", "daemon-reload and restore exact enabled states", "all six service enabled/load states match snapshot")
    add("snd_aloop", "restore loaded and persistence state exactly", "index/id/substreams/pcm_notify and persistence files match snapshot")
    add("mixer", "restore all four captured control percentages", "live readback matches activation snapshot")
    add("services", "restore exact original active states", "application services match snapshot")
    add("final", "verify route, services, module, mixer and every managed path", "zero rollback mismatches")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit(f"Read-only privileged capture requires --confirm {REQUIRED_CONFIRMATION}")
    for command in ("systemctl", "amixer", "fuser"):
        if shutil.which(command) is None:
            raise SystemExit(f"Required read-only inspection command not found: {command}")

    invoking_uid, invoking_gid, invoking_user = invoking_identity()
    package_root = _validate_user_review_root(
        args.package_root, "a-clockwork-plex-stage-c1-review-", invoking_uid
    )
    stage_c2_root = _validate_user_review_root(
        args.stage_c2_root, "a-clockwork-plex-stage-c2-review-", invoking_uid
    )
    snapshot_root = validate_snapshot_root(args.snapshot_root, invoking_uid)

    entries = parse_manifest(package_root)
    validate_stage_c1_evidence(package_root)
    validate_stage_c2_evidence(stage_c2_root, package_root)
    validate_current_host_as_root()

    os.chown(snapshot_root, 0, 0)
    snapshot_root.chmod(0o700)
    completed = False
    try:
        results = snapshot_root / "results.tsv"
        results.write_text("check\tresult\tdetail\n", encoding="utf-8")
        append_result(results, "root-scope", f"sudo root capture constrained to {snapshot_root}")
        append_result(results, "stage-c1-package-replay", "manifest, checksums, modes and PASS evidence replayed")
        append_result(results, "stage-c2-review-replay", "exact eleven-check review and package fingerprint replayed")
        append_result(results, "current-host-boundary", "pre-Stage-C route, loopback and process boundary remain exact")

        summary = collect_filesystem_snapshot(entries, Path("/"), snapshot_root)
        if summary.conflicts or summary.managed_present or summary.managed_absent != EXPECTED_PACKAGE_FILES:
            raise SystemExit(
                "Privileged destination boundary failed: "
                f"absent={summary.managed_absent} present={summary.managed_present} "
                f"conflicts={summary.conflicts}"
            )
        append_result(
            results,
            "privileged-destination-resolution",
            f"all {EXPECTED_PACKAGE_FILES} managed file destinations verified absent; zero conflicts",
        )
        append_result(results, "filesystem-snapshot", "current ALSA copied and exact managed absence markers recorded")

        service_state = snapshot_root / "service-state.tsv"
        states = capture_service_states(service_state)
        validate_service_boundary(states)
        append_result(results, "service-state-boundary", "application services active/enabled; Stage C services absent")

        capture_mixer_states(snapshot_root / "mixer-state.tsv", snapshot_root / "mixer-raw")
        append_result(results, "mixer-state-capture", "four live ALSA control percentages captured read-only")

        capture_module_and_dac(snapshot_root / "module-dac-state.tsv", snapshot_root)
        append_result(results, "module-dac-capture", "snd_aloop parameters, DAC owner and hw_params captured")

        write_package_fingerprint(package_root, snapshot_root / "package-fingerprint.tsv")
        write_rollback_ledger(entries, snapshot_root / "rollback-ledger.tsv", snapshot_root)
        append_result(results, "rollback-ledger", "fresh privileged file/absence and state obligations generated")
        append_result(results, "activation-interface", "absent; Stage C3 is a read-only snapshot rehearsal only")

        report = snapshot_root / "report.txt"
        report.write_text(
            f"""A Clockwork Plex Stage C3 read-only privileged snapshot rehearsal
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Snapshot version: {SNAPSHOT_VERSION}
Host: {platform.node()}
Architecture: {platform.machine()}
Invoking user: {invoking_user}
Stage C1 package: {package_root}
Stage C2 review: {stage_c2_root}
Stage C3 snapshot: {snapshot_root}
Verified pre-Stage-C ALSA SHA-256: {EXPECTED_PRE_STAGE_C_ALSA_SHA256}
Managed package files: {EXPECTED_PACKAGE_FILES}
Verified absent managed files: {summary.managed_absent}
Existing managed files: {summary.managed_present}
Managed destination conflicts: {summary.conflicts}
Protected sudoers destination resolved: absent

Evidence:
- Stage C1 package and Stage C2 review were independently replayed
- current production ALSA remains the exact physically validated rollback graph
- all 12 managed file destinations were resolved by root and verified absent
- the protected sudoers destination was resolved without creating or changing it
- the current ALSA file, true absence markers, service states, mixer controls,
  snd_aloop parameters, DAC owner and DAC hw_params were captured
- the rollback ledger is tied to this rehearsal but explicitly requires a new
  authoritative snapshot under the future transaction lock

Safety state:
- one sudo command launched this constrained read-only engine
- no production path was written
- no route or candidate file was installed
- no service was started, stopped, restarted, enabled or disabled
- no systemd daemon-reload was run
- no module was loaded or unloaded
- no PCM was opened
- no mixer value was changed
- no activation marker or production lock was created
- no --activate, install, route, rollback or uninstall action exists
- this rehearsal evidence must never be reused as the future activation snapshot
- persistent activation remains blocked
""",
            encoding="utf-8",
        )

        write_evidence_manifest(snapshot_root)
        append_result(results, "snapshot-integrity", "evidence inventory generated with no symlink or special object")
        write_evidence_manifest(snapshot_root)
        completed = True
    finally:
        chown_evidence_tree(snapshot_root, invoking_uid, invoking_gid)
        snapshot_root.chmod(0o700)

    if not completed:
        raise SystemExit("Stage C3 snapshot did not complete.")

    print(
        f"""
A Clockwork Plex Stage C3 privileged snapshot rehearsal passed.

  Directory:          {snapshot_root}
  Results:            {snapshot_root / 'results.tsv'}
  Filesystem state:   {snapshot_root / 'filesystem-state.tsv'}
  Service state:      {snapshot_root / 'service-state.tsv'}
  Mixer state:        {snapshot_root / 'mixer-state.tsv'}
  Module/DAC state:   {snapshot_root / 'module-dac-state.tsv'}
  Rollback ledger:    {snapshot_root / 'rollback-ledger.tsv'}
  Evidence manifest:  {snapshot_root / 'evidence-manifest.tsv'}
  Report:             {snapshot_root / 'report.txt'}

No production path was written or changed. This is a read-only rehearsal and
must never be reused as the future activation snapshot.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
