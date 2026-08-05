#!/usr/bin/python3
from __future__ import annotations

"""Authoritative Stage C4 sandbox-only transaction and rollback rehearsal.

This module is the single executable owner for the Stage C4 synthetic transaction.
It contains the validated evidence replay, sandbox mapping, installation, failure
injection, rollback and reporting paths. No companion runtime module exists.
"""

import argparse
import csv
import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .package_review import ManifestEntry, parse_manifest, sha256, validate_stage_c1_evidence

REQUIRED_CONFIRMATION = "STAGE-C4-SANDBOX-TRANSACTION"
SANDBOX_PREFIX = "a-clockwork-plex-stage-c4-sandbox."
CURRENT_ALSA_DESTINATION = "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
SPLIT_ROUTE_DESTINATION = "/etc/a-clockwork-plex/audio-routes/split-bus.conf"
EXPECTED_PRE_STAGE_C_ALSA_SHA256 = (
    "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
)
EXPECTED_STAGE_C3_CHECKS = (
    "root-scope",
    "stage-c1-package-replay",
    "stage-c2-review-replay",
    "current-host-boundary",
    "privileged-destination-resolution",
    "filesystem-snapshot",
    "service-state-boundary",
    "mixer-state-capture",
    "module-dac-capture",
    "rollback-ledger",
    "activation-interface",
    "snapshot-integrity",
)
APPLICATION_SERVICES = (
    "plexamp.service",
    "shairport-sync.service",
    "a-clockwork-plex.service",
)
STAGE_C_SERVICES = (
    "a-clockwork-plex-audio-route.service",
    "a-clockwork-plex-camilladsp.service",
    "a-clockwork-plex-audio-failback.service",
)
MIXER_CONTROLS = (
    "A Clockwork Master",
    "A Clockwork Plexamp",
    "A Clockwork AirPlay",
    "A Clockwork Alarm",
)
FAILURE_POINTS = (
    "after-files-installed",
    "after-route-selected",
    "after-services-restored",
)


class InjectedFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class StageC3Evidence:
    filesystem_rows: tuple[dict[str, str], ...]
    initial_directory_states: dict[str, str]


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    injected_failure: str
    install_verified: bool
    rollback_reason: str
    rollback_mismatches: int


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Required evidence file is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.lstat().st_mode):o}"


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_regular_tree(root: Path, label: str) -> None:
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"{label} must be a real directory: {root}")
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"{label} contains a symlink: {path}")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise SystemExit(f"{label} contains a special object: {path}")


def tree_fingerprint(root: Path) -> tuple[tuple[str, str, str, str], ...]:
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        info = path.lstat()
        relative = str(path.relative_to(root))
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", f"{stat.S_IMODE(info.st_mode):o}", "-"))
        elif stat.S_ISREG(info.st_mode):
            rows.append(
                (
                    relative,
                    "file",
                    f"{stat.S_IMODE(info.st_mode):o}",
                    sha256(path),
                )
            )
        else:
            raise SystemExit(f"Unsupported object while fingerprinting {root}: {path}")
    return tuple(rows)


def combined_scenario_fingerprint(
    scenario_root: Path,
) -> tuple[tuple[str, str, str, str], ...]:
    rows: list[tuple[str, str, str, str]] = []
    for name in ("system-root", "simulated-state"):
        child = scenario_root / name
        for relative, kind, mode, digest in tree_fingerprint(child):
            rows.append((f"{name}/{relative}", kind, mode, digest))
    return tuple(rows)


def write_fingerprint(
    path: Path,
    rows: tuple[tuple[str, str, str, str], ...],
) -> None:
    output = ["path\ttype\tmode\tsha256"]
    output.extend("\t".join(row) for row in rows)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _validate_evidence_manifest(stage_c3_root: Path) -> None:
    manifest = stage_c3_root / "evidence-manifest.tsv"
    rows = _read_tsv(manifest)
    if not rows:
        raise SystemExit("Stage C3 evidence manifest is empty.")
    listed: set[str] = set()
    for row in rows:
        relative = row.get("path", "")
        kind = row.get("type", "")
        mode = row.get("mode", "")
        digest = row.get("sha256", "")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not relative:
            raise SystemExit(f"Unsafe Stage C3 evidence manifest path: {relative}")
        if relative in listed:
            raise SystemExit(f"Duplicate Stage C3 evidence manifest path: {relative}")
        listed.add(relative)
        path = stage_c3_root / Path(*pure.parts)
        if kind == "self":
            if relative != "evidence-manifest.tsv" or not path.is_file():
                raise SystemExit("Stage C3 evidence manifest self row is invalid.")
            continue
        info = path.lstat() if path.exists() else None
        if info is None:
            raise SystemExit(f"Stage C3 evidence manifest entry is missing: {relative}")
        if kind == "directory":
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SystemExit(f"Stage C3 evidence directory mismatch: {relative}")
            if f"{stat.S_IMODE(info.st_mode):o}" != mode or digest != "-":
                raise SystemExit(
                    f"Stage C3 evidence directory metadata mismatch: {relative}"
                )
        elif kind == "file":
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SystemExit(f"Stage C3 evidence file mismatch: {relative}")
            if f"{stat.S_IMODE(info.st_mode):o}" != mode or sha256(path) != digest:
                raise SystemExit(f"Stage C3 evidence file metadata mismatch: {relative}")
        else:
            raise SystemExit(f"Unsupported Stage C3 evidence manifest type: {kind}")

    actual = {str(path.relative_to(stage_c3_root)) for path in stage_c3_root.rglob("*")}
    if actual != listed:
        missing = sorted(actual - listed)
        extra = sorted(listed - actual)
        raise SystemExit(
            "Stage C3 evidence manifest inventory mismatch: "
            f"unlisted={missing[:1]} missing={extra[:1]}"
        )


def validate_inputs(
    package_root: Path,
    stage_c3_root: Path,
) -> tuple[list[ManifestEntry], StageC3Evidence]:
    package_root = package_root.resolve()
    stage_c3_root = stage_c3_root.resolve()
    if package_root == stage_c3_root:
        raise SystemExit("Stage C1 package and Stage C3 evidence must be different directories.")
    _assert_regular_tree(package_root, "Stage C1 package")
    _assert_regular_tree(stage_c3_root, "Stage C3 evidence")

    entries = parse_manifest(package_root)
    validate_stage_c1_evidence(package_root)
    _validate_evidence_manifest(stage_c3_root)

    results = _read_tsv(stage_c3_root / "results.tsv")
    observed = tuple(row.get("check", "") for row in results)
    if observed != EXPECTED_STAGE_C3_CHECKS or any(
        row.get("result") != "PASS" for row in results
    ):
        raise SystemExit("Stage C3 evidence is not the exact twelve-check PASS result.")

    report = (stage_c3_root / "report.txt").read_text(encoding="utf-8")
    for expected in (
        "Managed package files: 12",
        "Verified absent managed files: 12",
        "Existing managed files: 0",
        "Managed destination conflicts: 0",
        "Protected sudoers destination resolved: absent",
        "no production path was written",
        "this rehearsal evidence must never be reused as the future activation snapshot",
    ):
        if expected not in report:
            raise SystemExit(f"Stage C3 report contract is missing: {expected}")

    filesystem_rows = _read_tsv(stage_c3_root / "filesystem-state.tsv")
    files = {
        row.get("destination", ""): row
        for row in filesystem_rows
        if row.get("kind") == "file"
    }
    current = files.get(CURRENT_ALSA_DESTINATION)
    if not current or current.get("preinstall_state") != "present":
        raise SystemExit("Stage C3 did not capture the current ALSA file as present.")
    if current.get("sha256") != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit(
            "Stage C3 current ALSA checksum differs from the physically validated route."
        )
    current_copy = stage_c3_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")
    if not current_copy.is_file() or sha256(current_copy) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit("Stage C3 copied ALSA rollback file is missing or changed.")

    for entry in (item for item in entries if item.kind == "file"):
        row = files.get(entry.destination)
        if not row or row.get("preinstall_state") != "absent":
            raise SystemExit(
                f"Stage C3 first-install boundary is not absent: {entry.destination}"
            )

    service_rows = _read_tsv(stage_c3_root / "service-state.tsv")
    services = {row.get("service", ""): row for row in service_rows}
    for service in APPLICATION_SERVICES:
        row = services.get(service)
        if not row or (
            row.get("load_state"),
            row.get("active_state"),
            row.get("enabled_state"),
        ) != ("loaded", "active", "enabled"):
            raise SystemExit(f"Stage C3 application service boundary changed: {service}")
    for service in STAGE_C_SERVICES:
        row = services.get(service)
        if not row or (row.get("load_state"), row.get("enabled_state")) != (
            "not-found",
            "not-found",
        ):
            raise SystemExit(f"Stage C3 proposed service boundary changed: {service}")

    mixer_rows = _read_tsv(stage_c3_root / "mixer-state.tsv")
    if tuple(row.get("control", "") for row in mixer_rows) != MIXER_CONTROLS:
        raise SystemExit(
            "Stage C3 mixer evidence does not contain the four expected controls."
        )

    module_rows = _read_tsv(stage_c3_root / "module-dac-state.tsv")
    module = {row.get("item", ""): row.get("value", "") for row in module_rows}
    expected_module = {
        "snd_aloop.loaded": "true",
        "snd_aloop.index": "7",
        "snd_aloop.id": "ACP_Loopback",
        "snd_aloop.pcm_substreams": "2",
        "snd_aloop.pcm_notify": "1",
        "snd_aloop.enable": "Y",
        "dac.device": "/dev/snd/pcmC2D0p",
        "dac.exists": "true",
    }
    for item, expected in expected_module.items():
        if module.get(item) != expected:
            raise SystemExit(
                f"Stage C3 module/DAC evidence changed: {item}={module.get(item)}"
            )

    rollback_rows = _read_tsv(stage_c3_root / "rollback-ledger.tsv")
    if len(rollback_rows) != 23 or rollback_rows[-1].get("area") != "final":
        raise SystemExit("Stage C3 rollback ledger is not the expected 23-step contract.")

    directory_states = {
        row.get("destination", ""): row.get("preinstall_state", "")
        for row in filesystem_rows
        if row.get("kind") == "directory"
    }
    return entries, StageC3Evidence(tuple(filesystem_rows), directory_states)


def validate_sandbox_root(
    requested: Path,
    package_root: Path,
    stage_c3_root: Path,
) -> Path:
    if os.geteuid() == 0:
        raise SystemExit("Run Stage C4 as the normal project user, not as root.")
    raw = requested.expanduser()
    if not raw.is_absolute():
        raise SystemExit("--sandbox-root must be an absolute path beneath /var/tmp.")
    try:
        info = raw.lstat()
    except FileNotFoundError as exc:
        raise SystemExit(f"--sandbox-root must already exist: {raw}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("--sandbox-root must be a real directory, not a symlink.")
    resolved = raw.resolve()
    if resolved.parent != Path("/var/tmp") or not resolved.name.startswith(SANDBOX_PREFIX):
        raise SystemExit(
            f"--sandbox-root must be a direct /var/tmp/{SANDBOX_PREFIX}* directory."
        )
    if info.st_uid != os.getuid():
        raise SystemExit("--sandbox-root must be owned by the invoking user.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("--sandbox-root must have mode 0700.")
    if any(resolved.iterdir()):
        raise SystemExit(f"--sandbox-root must be empty: {resolved}")
    package_resolved = package_root.resolve()
    stage_c3_resolved = stage_c3_root.resolve()
    if resolved in (package_resolved, stage_c3_resolved):
        raise SystemExit("Sandbox root must be separate from both input trees.")
    return resolved


def mapped_path(system_root: Path, destination: str) -> Path:
    pure = PurePosixPath(destination)
    if not pure.is_absolute() or destination == "/" or ".." in pure.parts:
        raise SystemExit(f"Unsafe sandbox destination: {destination}")
    root = system_root.resolve()
    candidate = root.joinpath(*pure.parts[1:])
    for parent in (candidate, *candidate.parents):
        if parent == root:
            break
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Refusing symlinked sandbox path: {parent}")
    if root not in candidate.parents:
        raise SystemExit(f"Sandbox destination escaped synthetic root: {destination}")
    return candidate


def _atomic_copy(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.stage-c4-tmp")
    if temporary.exists() or temporary.is_symlink():
        raise SystemExit(f"Unexpected sandbox staging collision: {temporary}")
    try:
        shutil.copyfile(source, temporary)
        temporary.chmod(mode)
        os.replace(temporary, destination)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _journal(path: Path, action: str, detail: str) -> None:
    if not path.exists():
        path.write_text("sequence\taction\tdetail\n", encoding="utf-8")
    sequence = len(path.read_text(encoding="utf-8").splitlines())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{sequence}\t{action}\t{detail}\n")


def _set_application_active_state(state_root: Path, active: str) -> None:
    rows = _read_tsv(state_root / "services.tsv")
    for row in rows:
        if row.get("service") in APPLICATION_SERVICES:
            row["active_state"] = active
    _write_tsv(
        state_root / "services.tsv",
        ["service", "load_state", "active_state", "enabled_state"],
        rows,
    )


def _captured_present_directory_modes(
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> dict[str, int]:
    managed = {entry.destination for entry in entries if entry.kind == "directory"}
    captured: dict[str, int] = {}
    for row in evidence.filesystem_rows:
        destination = row.get("destination", "")
        if (
            row.get("kind") != "directory"
            or row.get("preinstall_state") != "present"
            or destination not in managed
        ):
            continue
        mode_text = row.get("mode", "")
        try:
            mode = int(mode_text, 8)
        except ValueError as exc:
            raise SystemExit(
                f"Invalid captured managed-directory mode: {destination} {mode_text}"
            ) from exc
        captured[destination] = mode
    return captured


def seed_scenario(
    scenario_root: Path,
    package_root: Path,
    stage_c3_root: Path,
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> tuple[
    tuple[tuple[str, str, str, str], ...],
    set[str],
    dict[str, int],
]:
    system_root = scenario_root / "system-root"
    state_root = scenario_root / "simulated-state"
    baseline_root = scenario_root / "baseline"
    system_root.mkdir(parents=True)
    state_root.mkdir()
    baseline_root.mkdir()

    absent_directories: set[str] = set()
    for entry in (item for item in entries if item.kind == "directory"):
        destination = mapped_path(system_root, entry.destination)
        state = evidence.initial_directory_states.get(entry.destination)
        if state == "present":
            destination.mkdir(parents=True, exist_ok=True)
            captured_row = next(
                row
                for row in evidence.filesystem_rows
                if row.get("kind") == "directory"
                and row.get("destination") == entry.destination
            )
            destination.chmod(int(captured_row.get("mode", "755"), 8))
        elif state == "absent":
            absent_directories.add(entry.destination)
        else:
            raise SystemExit(
                f"Stage C3 did not resolve managed directory state: {entry.destination}"
            )

    current_source = stage_c3_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")
    current_destination = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    _atomic_copy(current_source, current_destination, 0o644)

    shutil.copyfile(stage_c3_root / "service-state.tsv", state_root / "services.tsv")
    shutil.copyfile(stage_c3_root / "mixer-state.tsv", state_root / "mixer.tsv")
    shutil.copyfile(stage_c3_root / "module-dac-state.tsv", state_root / "module-dac.tsv")
    (state_root / "route-selected.txt").write_text(
        "direct-shared-pre-stage-c\n",
        encoding="utf-8",
    )

    shutil.copytree(system_root, baseline_root / "rootfs")
    shutil.copytree(state_root, baseline_root / "simulated-state")
    baseline = combined_scenario_fingerprint(scenario_root)
    write_fingerprint(scenario_root / "baseline-fingerprint.tsv", baseline)

    present_directory_modes = _captured_present_directory_modes(entries, evidence)
    rows = ["destination\tmode"]
    rows.extend(
        f"{destination}\t{mode:o}"
        for destination, mode in sorted(present_directory_modes.items())
    )
    (scenario_root / "baseline/present-directory-modes.tsv").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return baseline, absent_directories, present_directory_modes


def apply_sandbox_install(
    scenario_root: Path,
    package_root: Path,
    entries: list[ManifestEntry],
    fail_after: str | None,
) -> None:
    system_root = scenario_root / "system-root"
    state_root = scenario_root / "simulated-state"
    journal = scenario_root / "journal.tsv"

    for entry in (item for item in entries if item.kind == "directory"):
        destination = mapped_path(system_root, entry.destination)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise SystemExit(
                    f"Sandbox directory conflicts with candidate: {entry.destination}"
                )
            continue
        destination.mkdir(parents=False)
        destination.chmod(int(entry.mode, 8))
        _journal(journal, "create-directory", entry.destination)

    for entry in (item for item in entries if item.kind == "file"):
        source = package_root / "rootfs" / entry.destination.lstrip("/")
        destination = mapped_path(system_root, entry.destination)
        _atomic_copy(source, destination, int(entry.mode, 8))
        _journal(journal, "install-file", entry.destination)

    if fail_after == "after-files-installed":
        raise InjectedFailure(fail_after)

    split_source = mapped_path(system_root, SPLIT_ROUTE_DESTINATION)
    active_route = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    _atomic_copy(split_source, active_route, 0o644)
    (state_root / "route-selected.txt").write_text("split-bus\n", encoding="utf-8")
    _journal(journal, "select-route", SPLIT_ROUTE_DESTINATION)

    if fail_after == "after-route-selected":
        raise InjectedFailure(fail_after)

    _set_application_active_state(state_root, "active")
    _journal(journal, "restore-services", "application services active")

    if fail_after == "after-services-restored":
        raise InjectedFailure(fail_after)

    (scenario_root / "transaction-committed.sandbox-only").write_text(
        "not a production activation marker\n",
        encoding="utf-8",
    )
    verify_install(scenario_root, package_root, entries)


def verify_install(
    scenario_root: Path,
    package_root: Path,
    entries: list[ManifestEntry],
) -> None:
    system_root = scenario_root / "system-root"
    for entry in entries:
        destination = mapped_path(system_root, entry.destination)
        if entry.kind == "directory":
            if destination.is_symlink() or not destination.is_dir():
                raise SystemExit(f"Sandbox installed directory missing: {entry.destination}")
            continue
        if destination.is_symlink() or not destination.is_file():
            raise SystemExit(f"Sandbox installed file missing: {entry.destination}")
        source = package_root / "rootfs" / entry.destination.lstrip("/")
        if sha256(destination) != sha256(source):
            raise SystemExit(f"Sandbox installed checksum mismatch: {entry.destination}")
        if _mode(destination) != entry.mode:
            raise SystemExit(f"Sandbox installed mode mismatch: {entry.destination}")

    active_route = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    split_route = mapped_path(system_root, SPLIT_ROUTE_DESTINATION)
    if sha256(active_route) != sha256(split_route):
        raise SystemExit("Sandbox active ALSA selection does not match split-bus candidate.")


def rollback_sandbox(
    scenario_root: Path,
    entries: list[ManifestEntry],
    absent_directories: set[str],
    present_directory_modes: dict[str, int],
    baseline: tuple[tuple[str, str, str, str], ...],
    reason: str,
) -> int:
    system_root = scenario_root / "system-root"
    state_root = scenario_root / "simulated-state"
    baseline_root = scenario_root / "baseline"
    journal = scenario_root / "journal.tsv"
    _journal(journal, "rollback-start", reason)

    for entry in reversed([item for item in entries if item.kind == "file"]):
        destination = mapped_path(system_root, entry.destination)
        if destination.is_symlink():
            raise SystemExit(f"Refusing symlink during sandbox rollback: {entry.destination}")
        if destination.exists():
            if not destination.is_file():
                raise SystemExit(
                    f"Sandbox rollback file has conflicting type: {entry.destination}"
                )
            destination.unlink()

    baseline_current = baseline_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")
    active_current = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    _atomic_copy(baseline_current, active_current, 0o644)

    shutil.rmtree(state_root)
    shutil.copytree(baseline_root / "simulated-state", state_root)
    committed = scenario_root / "transaction-committed.sandbox-only"
    if committed.exists() or committed.is_symlink():
        committed.unlink()

    for destination in sorted(
        absent_directories,
        key=lambda item: len(PurePosixPath(item).parts),
        reverse=True,
    ):
        path = mapped_path(system_root, destination)
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(
                f"Sandbox rollback directory has conflicting type: {destination}"
            )
        try:
            path.rmdir()
        except OSError as exc:
            raise SystemExit(
                f"Sandbox rollback would remove a non-empty directory: {destination}"
            ) from exc

    for destination, mode in sorted(
        present_directory_modes.items(),
        key=lambda item: len(PurePosixPath(item[0]).parts),
    ):
        path = mapped_path(system_root, destination)
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(
                f"Captured existing sandbox directory is missing or unsafe: {destination}"
            )
        path.chmod(mode)
    _journal(
        journal,
        "directory-modes",
        f"restored {len(present_directory_modes)} captured existing managed-directory modes",
    )

    observed = combined_scenario_fingerprint(scenario_root)
    mismatches = 0 if observed == baseline else 1
    write_fingerprint(scenario_root / "post-rollback-fingerprint.tsv", observed)
    _journal(journal, "rollback-finish", f"baseline mismatches={mismatches}")
    return mismatches


def run_scenario(
    sandbox_root: Path,
    name: str,
    fail_after: str | None,
    package_root: Path,
    stage_c3_root: Path,
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> ScenarioResult:
    scenario_root = sandbox_root / "scenarios" / name
    scenario_root.mkdir(parents=True)
    baseline, absent_directories, present_directory_modes = seed_scenario(
        scenario_root,
        package_root,
        stage_c3_root,
        entries,
        evidence,
    )
    install_verified = False
    rollback_reason = "explicit-uninstall"
    try:
        apply_sandbox_install(scenario_root, package_root, entries, fail_after)
        if fail_after is not None:
            raise SystemExit(f"Failure injection did not trigger: {fail_after}")
        install_verified = True
    except InjectedFailure as exc:
        if str(exc) != fail_after:
            raise
        rollback_reason = f"automatic:{fail_after}"
        _journal(scenario_root / "journal.tsv", "injected-failure", str(exc))

    mismatches = rollback_sandbox(
        scenario_root,
        entries,
        absent_directories,
        present_directory_modes,
        baseline,
        rollback_reason,
    )
    if mismatches:
        raise SystemExit(f"Sandbox rollback did not restore exact baseline: {name}")
    return ScenarioResult(
        name=name,
        injected_failure=fail_after or "none",
        install_verified=install_verified,
        rollback_reason=rollback_reason,
        rollback_mismatches=mismatches,
    )


def result(results: Path, check: str, detail: str) -> None:
    with results.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def write_file_plan(
    path: Path,
    entries: list[ManifestEntry],
    evidence: StageC3Evidence,
) -> None:
    states = {
        row.get("destination", ""): row.get("preinstall_state", "")
        for row in evidence.filesystem_rows
    }
    rows = ["type\tdestination\tpreinstall_state\tmode\tsha256"]
    rows.extend(
        "\t".join(
            (
                entry.kind,
                entry.destination,
                states.get(entry.destination, "unknown"),
                entry.mode,
                entry.digest,
            )
        )
        for entry in entries
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_evidence_manifest(root: Path) -> None:
    rows = ["path\ttype\tmode\tsha256"]
    manifest = root / "evidence-manifest.tsv"
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        if path == manifest:
            continue
        info = path.lstat()
        relative = str(path.relative_to(root))
        mode = f"{stat.S_IMODE(info.st_mode):o}"
        if stat.S_ISDIR(info.st_mode):
            rows.append(f"{relative}\tdirectory\t{mode}\t-")
        elif stat.S_ISREG(info.st_mode):
            rows.append(f"{relative}\tfile\t{mode}\t{sha256(path)}")
        else:
            raise SystemExit(f"Unsupported Stage C4 evidence object: {path}")
    rows.append("evidence-manifest.tsv\tself\t644\t-")
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run_rehearsal(
    package_root: Path,
    stage_c3_root: Path,
    sandbox_root: Path,
) -> list[ScenarioResult]:
    entries, evidence = validate_inputs(package_root, stage_c3_root)
    sandbox_root = validate_sandbox_root(sandbox_root, package_root, stage_c3_root)
    package_before = tree_fingerprint(package_root)
    stage_c3_before = tree_fingerprint(stage_c3_root)

    results = sandbox_root / "results.tsv"
    results.write_text("check\tresult\tdetail\n", encoding="utf-8")
    result(
        results,
        "input-replay",
        "Stage C1 package and complete Stage C3 evidence replayed",
    )
    result(
        results,
        "sandbox-scope",
        f"all mutation paths constrained beneath {sandbox_root}",
    )
    result(
        results,
        "first-install-boundary",
        "all twelve managed files begin absent in every scenario",
    )
    write_file_plan(sandbox_root / "file-plan.tsv", entries, evidence)

    scenarios = [
        run_scenario(
            sandbox_root,
            "success-explicit-uninstall",
            None,
            package_root,
            stage_c3_root,
            entries,
            evidence,
        )
    ]
    result(
        results,
        "install-success",
        "twelve files and synthetic split route verified before uninstall",
    )
    result(
        results,
        "explicit-uninstall-rollback",
        "successful sandbox install restored files, state and captured directory modes",
    )

    for failure in FAILURE_POINTS:
        scenarios.append(
            run_scenario(
                sandbox_root,
                f"failure-{failure}",
                failure,
                package_root,
                stage_c3_root,
                entries,
                evidence,
            )
        )
    result(
        results,
        "failure-injection",
        "three independent transaction failure points exercised",
    )
    result(
        results,
        "automatic-rollback",
        "all injected failures invoked the exact rollback implementation",
    )
    if any(item.rollback_mismatches for item in scenarios):
        raise SystemExit("One or more Stage C4 scenarios reported rollback mismatches.")
    result(
        results,
        "exact-state-verification",
        "all four scenarios ended with zero baseline mismatches",
    )

    scenario_rows = [
        "scenario\tinjected_failure\tinstall_verified\trollback_reason\trollback_mismatches"
    ]
    scenario_rows.extend(
        f"{item.name}\t{item.injected_failure}\t{str(item.install_verified).lower()}\t"
        f"{item.rollback_reason}\t{item.rollback_mismatches}"
        for item in scenarios
    )
    (sandbox_root / "scenario-state.tsv").write_text(
        "\n".join(scenario_rows) + "\n",
        encoding="utf-8",
    )

    if tree_fingerprint(package_root) != package_before:
        raise SystemExit("Stage C1 package changed during sandbox rehearsal.")
    if tree_fingerprint(stage_c3_root) != stage_c3_before:
        raise SystemExit("Stage C3 evidence changed during sandbox rehearsal.")
    result(
        results,
        "production-boundary",
        "input trees unchanged; no production path or command was used",
    )

    report = f"""A Clockwork Plex Stage C4 sandbox transaction and exact-rollback rehearsal
Sandbox version: 3
Stage C1 package: {package_root.resolve()}
Stage C3 evidence: {stage_c3_root.resolve()}
Stage C4 sandbox: {sandbox_root}
Managed package files: 12
Scenarios: 4
Injected failure points: 3
Final rollback mismatches: 0
Transaction authority: scripts.stage_c_transaction.sandbox_transaction

Proved in synthetic filesystems:
- exact Stage C1 and Stage C3 evidence replay
- first-install absence boundary for all twelve managed files
- atomic sandbox installation of all package files
- synthetic active ALSA selection from the installed split-bus route
- successful install verification followed by explicit exact uninstall
- automatic exact rollback after files installed, route selected and services restored
- restoration of captured modes for pre-existing managed directories
- unchanged Stage C1 package and Stage C3 evidence trees
- one executable transaction and rollback authority

Not proved by Stage C4:
- real ALSA parsing or PCM availability
- CamillaDSP startup, DSP health or DAC ownership
- real service-manager ordering or service behaviour
- real music/alarm lane probes
- runtime direct alarm-bypass failback
- EQ migration or dashboard health

Safety state:
- no sudo or root execution
- no production path opened for writing
- no service-manager, mixer, module, PCM-owner or CamillaDSP command execution
- no device or PCM opened
- no activation marker created
- no production activation/install/rollback/uninstall interface exists
- persistent Stage C activation remains blocked
"""
    (sandbox_root / "report.txt").write_text(report, encoding="utf-8")
    write_evidence_manifest(sandbox_root)
    print("A Clockwork Plex Stage C4 sandbox transaction rehearsal passed.")
    print(f"  Directory: {sandbox_root}")
    print(f"  Results:   {results}")
    print(f"  Scenarios: {sandbox_root / 'scenario-state.tsv'}")
    print(f"  Report:    {sandbox_root / 'report.txt'}")
    print(
        "No production path was written or changed. Persistent activation remains blocked."
    )
    return scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Stage C4 transaction and rollback only inside a synthetic root."
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c3-root", required=True, type=Path)
    parser.add_argument("--sandbox-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit("Exact Stage C4 sandbox confirmation token was not supplied.")
    run_rehearsal(args.package_root, args.stage_c3_root, args.sandbox_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
