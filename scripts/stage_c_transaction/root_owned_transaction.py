#!/usr/bin/python3
from __future__ import annotations

"""Stage C7 root-owned disposable-system transaction rehearsal.

All production-style destinations are mapped beneath a fresh Stage C7 evidence
root. The module has no service, mixer, module, PCM, DAC, CamillaDSP or
production-lock command adapter.
"""

import argparse
import csv
import fcntl
import grp
import hashlib
import os
import pwd
import secrets
import shutil
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from .package_review import (
    ManifestEntry,
    parse_manifest,
    sha256,
    validate_stage_c1_evidence,
)

REQUIRED_CONFIRMATION = "STAGE-C7-ROOT-OWNED-DISPOSABLE-TRANSACTION"
ROOT_PREFIX = "a-clockwork-plex-stage-c7-root-transaction."
CURRENT_ALSA_DESTINATION = "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
SPLIT_ROUTE_DESTINATION = "/etc/a-clockwork-plex/audio-routes/split-bus.conf"
STATE_RECORD_DESTINATION = "/var/lib/a-clockwork-plex/split-bus/stage-c7-transaction-state.tsv"
EXPECTED_PRE_STAGE_C_ALSA_SHA256 = (
    "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9"
)
EXPECTED_C6_CHECKS = (
    "root-scope",
    "input-replay",
    "current-host-boundary",
    "production-lock-boundary",
    "rehearsal-lock-acquired",
    "lock-contention",
    "fresh-identity",
    "privileged-destination-resolution",
    "filesystem-snapshot",
    "service-state-boundary",
    "mixer-state-capture",
    "module-dac-capture",
    "rollback-ledger",
    "input-integrity",
    "snapshot-integrity",
    "rehearsal-lock-released",
    "activation-interface",
)
FAILURE_POINTS = (
    "after-files-installed",
    "after-route-selected",
    "after-state-recorded",
)
TOP_LEVEL_CHECKS = (
    "root-scope",
    "input-replay",
    "disposable-mapping",
    "first-install-boundary",
    "existing-directory-preservation",
    "atomic-install",
    "synthetic-route-selection",
    "failure-injection",
    "shared-rollback",
    "exact-state-verification",
    "production-boundary",
    "activation-interface",
)


@dataclass(frozen=True)
class C6Evidence:
    filesystem_rows: tuple[dict[str, str], ...]
    current_alsa_snapshot: Path


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    injected_failure: str
    install_verified: bool
    rollback_reason: str
    rollback_mismatches: int
    existing_directories_preserved: bool


class InjectedFailure(RuntimeError):
    pass


class RehearsalLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = path.open("a+b")
        os.chmod(path, 0o600)
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.inode = path.stat().st_ino
        self.released = False

    def prove_contention(self) -> None:
        with self.path.open("a+b") as competing:
            try:
                fcntl.flock(competing.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            fcntl.flock(competing.fileno(), fcntl.LOCK_UN)
            raise SystemExit("Independent descriptor unexpectedly acquired Stage C7 lock.")

    def release(self) -> None:
        if self.released:
            return
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.released = True


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"Required regular TSV is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_tsv(path: Path, header: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _append_result(path: Path, check: str, detail: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{check}\tPASS\t{detail}\n")
    print(f"{check}\tPASS\t{detail}")


def _journal(path: Path, event: str, detail: str) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8") as handle:
        if not exists:
            handle.write("monotonic_ns\twall_time\tevent\tdetail\n")
        handle.write(
            f"{time.monotonic_ns()}\t{datetime.now().astimezone().isoformat()}\t"
            f"{event}\t{detail}\n"
        )


def _assert_regular_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"Input must be a real directory: {root}")
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Symlink is forbidden in evidence/package tree: {path}")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise SystemExit(f"Special object is forbidden in evidence/package tree: {path}")


def tree_fingerprint(root: Path) -> tuple[tuple[str, str, str, str], ...]:
    _assert_regular_tree(root)
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", f"{stat.S_IMODE(info.st_mode):o}", "-"))
        else:
            rows.append((relative, "file", f"{stat.S_IMODE(info.st_mode):o}", sha256(path)))
    return tuple(rows)


def system_fingerprint(root: Path) -> tuple[tuple[str, str, str, str, str, str], ...]:
    if root.is_symlink() or not root.is_dir():
        raise SystemExit(f"Synthetic system root is unsafe: {root}")
    rows: list[tuple[str, str, str, str, str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = f"{stat.S_IMODE(info.st_mode):o}"
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Synthetic system root contains a symlink: {path}")
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", mode, str(info.st_uid), str(info.st_gid), "-"))
        elif stat.S_ISREG(info.st_mode):
            rows.append((relative, "file", mode, str(info.st_uid), str(info.st_gid), sha256(path)))
        else:
            raise SystemExit(f"Synthetic system root contains a special object: {path}")
    return tuple(rows)


def write_fingerprint(path: Path, rows: tuple[tuple[str, str, str, str, str, str], ...]) -> None:
    _write_tsv(path, ("path", "type", "mode", "uid", "gid", "sha256"), list(rows))


def _safe_destination(destination: str) -> PurePosixPath:
    pure = PurePosixPath(destination)
    if not pure.is_absolute() or destination == "/" or ".." in pure.parts:
        raise SystemExit(f"Unsafe production-style destination: {destination}")
    return pure


def mapped_path(system_root: Path, destination: str) -> Path:
    pure = _safe_destination(destination)
    candidate = system_root.joinpath(*pure.parts[1:])
    root_resolved = system_root.resolve(strict=True)
    cursor = system_root
    for component in pure.parts[1:]:
        cursor = cursor / component
        if cursor.exists() or cursor.is_symlink():
            info = cursor.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise SystemExit(f"Mapped path contains a symlink: {destination}")
    parent = candidate.parent
    if parent.exists():
        parent_resolved = parent.resolve(strict=True)
        if parent_resolved != root_resolved and root_resolved not in parent_resolved.parents:
            raise SystemExit(f"Mapped parent escapes disposable root: {destination}")
    return candidate


def validate_c6(stage_c6_root: Path) -> C6Evidence:
    _assert_regular_tree(stage_c6_root)
    results = _read_tsv(stage_c6_root / "results.tsv")
    observed = tuple(row.get("check", "") for row in results)
    if observed != EXPECTED_C6_CHECKS or any(row.get("result") != "PASS" for row in results):
        raise SystemExit("Stage C6 evidence is not the exact seventeen-check PASS contract.")

    lock_rows = {row["item"]: row["value"] for row in _read_tsv(stage_c6_root / "lock-state.tsv")}
    required_lock = {
        "production.lock_path": "/run/lock/a-clockwork-plex-audio-route.lock",
        "production.lock_state": "absent",
        "production.lock_opened": "false",
        "rehearsal.lock_acquired": "true",
        "rehearsal.lock_released": "true",
    }
    for key, value in required_lock.items():
        if lock_rows.get(key) != value:
            raise SystemExit(f"Stage C6 lock contract mismatch: {key}")

    identity = {row["item"]: row["value"] for row in _read_tsv(stage_c6_root / "identity.tsv")}
    if identity.get("caller_supplied") != "false" or identity.get("activation_authoritative") != "false":
        raise SystemExit("Stage C6 identity is not explicitly non-authoritative.")

    report = (stage_c6_root / "report.txt").read_text(encoding="utf-8")
    for marker in (
        "Production lock state: absent and never opened",
        "this rehearsal must never be reused as an activation-authoritative snapshot",
        "persistent Stage C activation remains blocked",
    ):
        if marker not in report:
            raise SystemExit(f"Stage C6 report contract is missing: {marker}")

    filesystem_rows = tuple(_read_tsv(stage_c6_root / "filesystem-state.tsv"))
    current = [
        row for row in filesystem_rows
        if row.get("kind") == "file" and row.get("destination") == CURRENT_ALSA_DESTINATION
    ]
    if len(current) != 1 or current[0].get("sha256") != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit("Stage C6 current ALSA snapshot contract is not exact.")
    current_snapshot = Path(current[0].get("snapshot", ""))
    expected_inside = stage_c6_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")
    if current_snapshot.resolve() != expected_inside.resolve() or sha256(current_snapshot) != EXPECTED_PRE_STAGE_C_ALSA_SHA256:
        raise SystemExit("Stage C6 current ALSA snapshot is missing or changed.")

    return C6Evidence(filesystem_rows=filesystem_rows, current_alsa_snapshot=current_snapshot)


def validate_root_scope(
    rehearsal_root: Path,
    package_root: Path,
    stage_c6_root: Path,
    invoking_uid: int,
) -> Path:
    rehearsal_root = rehearsal_root.absolute()
    info = rehearsal_root.lstat()
    if rehearsal_root.parent != Path("/var/tmp") or not rehearsal_root.name.startswith(ROOT_PREFIX):
        raise SystemExit("Stage C7 root must be a direct /var/tmp child with the exact prefix.")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("Stage C7 root must be a real directory.")
    if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != invoking_uid:
        raise SystemExit("Stage C7 root must be invoking-user-owned mode 0700.")
    if any(rehearsal_root.iterdir()):
        raise SystemExit("Stage C7 root must be fresh and empty.")
    resolved = rehearsal_root.resolve(strict=True)
    if resolved != rehearsal_root:
        raise SystemExit("Stage C7 root must not resolve through a symlink.")
    for source in (package_root.resolve(strict=True), stage_c6_root.resolve(strict=True)):
        if source == resolved or resolved in source.parents or source in resolved.parents:
            raise SystemExit("Stage C7 inputs and output root must be disjoint.")
    return rehearsal_root


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_copy(
    source: Path,
    destination: Path,
    mode: int,
    uid: int,
    gid: int,
    expected_digest: str | None = None,
) -> str:
    if source.is_symlink() or not source.is_file():
        raise SystemExit(f"Atomic source is not a regular file: {source}")
    source_before = sha256(source)
    if expected_digest is not None and source_before != expected_digest:
        raise SystemExit(f"Atomic source checksum mismatch: {source}")
    destination.parent.mkdir(parents=False, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.stage-c7.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb", closefd=False) as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, uid, gid)
    finally:
        os.close(descriptor)
    try:
        copied = sha256(temporary)
        source_after = sha256(source)
        if copied != source_before or source_after != source_before:
            raise SystemExit(f"Atomic copy or source-drift verification failed: {source}")
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
    final = sha256(destination)
    info = destination.lstat()
    if (
        final != source_before
        or stat.S_IMODE(info.st_mode) != mode
        or info.st_uid != uid
        or info.st_gid != gid
    ):
        raise SystemExit(f"Atomic destination verification failed: {destination}")
    return final


def _captured_directories(evidence: C6Evidence) -> dict[str, tuple[int, str]]:
    captured: dict[str, tuple[int, str]] = {}
    for row in evidence.filesystem_rows:
        if row.get("kind") != "directory":
            continue
        destination = row.get("destination", "")
        state = row.get("preinstall_state", "")
        mode_text = row.get("mode", "")
        if state == "present":
            captured[destination] = (int(mode_text, 8), "present")
        elif state == "absent":
            captured[destination] = (0, "absent")
    return captured


def seed_scenario(
    scenario_root: Path,
    evidence: C6Evidence,
    entries: list[ManifestEntry],
    ownership_uid: int,
    ownership_gid: int,
) -> tuple[
    tuple[tuple[str, str, str, str, str, str], ...],
    dict[str, tuple[int, int, int]],
    set[str],
]:
    system_root = scenario_root / "system-root"
    system_root.mkdir()
    os.chmod(system_root, 0o700)
    os.chown(system_root, ownership_uid, ownership_gid)

    captured = _captured_directories(evidence)
    present: dict[str, tuple[int, int, int]] = {}
    absent: set[str] = set()
    for destination, (mode, state) in sorted(
        captured.items(), key=lambda item: len(PurePosixPath(item[0]).parts)
    ):
        if state == "absent":
            absent.add(destination)
            continue
        path = mapped_path(system_root, destination)
        if not path.exists():
            path.mkdir()
        os.chmod(path, mode)
        os.chown(path, ownership_uid, ownership_gid)
        present[destination] = (mode, ownership_uid, ownership_gid)

    current_destination = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    atomic_copy(
        evidence.current_alsa_snapshot,
        current_destination,
        0o644,
        ownership_uid,
        ownership_gid,
        EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    )

    baseline = system_fingerprint(system_root)
    write_fingerprint(scenario_root / "baseline-fingerprint.tsv", baseline)
    _write_tsv(
        scenario_root / "existing-directory-baseline.tsv",
        ("destination", "mode", "uid", "gid"),
        [
            (destination, f"{mode:o}", uid, gid)
            for destination, (mode, uid, gid) in sorted(present.items())
        ],
    )
    managed_directories = {entry.destination for entry in entries if entry.kind == "directory"}
    absent_managed = managed_directories.intersection(absent)
    return baseline, present, absent_managed


def create_manifest_directories(
    system_root: Path,
    entries: list[ManifestEntry],
    existing: dict[str, tuple[int, int, int]],
    ownership_uid: int,
    ownership_gid: int,
) -> None:
    for entry in sorted(
        (item for item in entries if item.kind == "directory"),
        key=lambda item: len(PurePosixPath(item.destination).parts),
    ):
        path = mapped_path(system_root, entry.destination)
        if path.exists():
            if path.is_symlink() or not path.is_dir():
                raise SystemExit(f"Managed directory has conflicting type: {entry.destination}")
            if entry.destination in existing:
                expected_mode, expected_uid, expected_gid = existing[entry.destination]
                info = path.lstat()
                if (
                    stat.S_IMODE(info.st_mode) != expected_mode
                    or info.st_uid != expected_uid
                    or info.st_gid != expected_gid
                ):
                    raise SystemExit(f"Existing directory drifted before install: {entry.destination}")
                continue
            raise SystemExit(f"Unexpected pre-existing managed directory: {entry.destination}")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise SystemExit(f"Managed directory parent is missing or unsafe: {entry.destination}")
        path.mkdir()
        os.chmod(path, int(entry.mode, 8))
        os.chown(path, ownership_uid, ownership_gid)


def verify_existing_directories(
    system_root: Path, existing: dict[str, tuple[int, int, int]]
) -> None:
    for destination, (mode, uid, gid) in existing.items():
        path = mapped_path(system_root, destination)
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != mode
            or info.st_uid != uid
            or info.st_gid != gid
        ):
            raise SystemExit(f"Existing directory was modified: {destination}")


def install_files(
    system_root: Path,
    package_root: Path,
    entries: list[ManifestEntry],
    ownership_uid: int,
    ownership_gid: int,
) -> None:
    for entry in (item for item in entries if item.kind == "file"):
        destination = mapped_path(system_root, entry.destination)
        if destination.exists() or destination.is_symlink():
            raise SystemExit(f"Candidate destination was not absent: {entry.destination}")
        source = package_root / "rootfs" / entry.destination.lstrip("/")
        atomic_copy(
            source,
            destination,
            int(entry.mode, 8),
            ownership_uid,
            ownership_gid,
            entry.digest,
        )


def select_synthetic_route(
    system_root: Path,
    entries: list[ManifestEntry],
    ownership_uid: int,
    ownership_gid: int,
) -> str:
    entry = next((item for item in entries if item.destination == SPLIT_ROUTE_DESTINATION), None)
    if entry is None or entry.kind != "file":
        raise SystemExit("Stage C1 package lacks the split-bus route candidate.")
    source = mapped_path(system_root, SPLIT_ROUTE_DESTINATION)
    destination = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    return atomic_copy(
        source,
        destination,
        0o644,
        ownership_uid,
        ownership_gid,
        entry.digest,
    )


def write_state_record(
    system_root: Path, identity: str, ownership_uid: int, ownership_gid: int
) -> None:
    destination = mapped_path(system_root, STATE_RECORD_DESTINATION)
    if destination.exists() or destination.is_symlink():
        raise SystemExit("Synthetic Stage C7 state record unexpectedly exists.")
    content = (
        "item\tvalue\n"
        f"identity\t{identity}\n"
        "scope\tdisposable-system-root-only\n"
        "activation_authoritative\tfalse\n"
    ).encode("utf-8")
    temporary_source = destination.parent / f".stage-c7-state-source.{secrets.token_hex(8)}"
    temporary_source.write_bytes(content)
    os.chmod(temporary_source, 0o600)
    try:
        atomic_copy(
            temporary_source,
            destination,
            0o600,
            ownership_uid,
            ownership_gid,
            hashlib.sha256(content).hexdigest(),
        )
    finally:
        temporary_source.unlink(missing_ok=True)


def verify_installed_state(
    system_root: Path,
    entries: list[ManifestEntry],
    existing: dict[str, tuple[int, int, int]],
    ownership_uid: int,
    ownership_gid: int,
) -> None:
    verify_existing_directories(system_root, existing)
    for entry in entries:
        path = mapped_path(system_root, entry.destination)
        info = path.lstat()
        if entry.kind == "directory":
            if not stat.S_ISDIR(info.st_mode):
                raise SystemExit(f"Installed directory missing: {entry.destination}")
            if entry.destination in existing:
                continue
            if (
                stat.S_IMODE(info.st_mode) != int(entry.mode, 8)
                or info.st_uid != ownership_uid
                or info.st_gid != ownership_gid
            ):
                raise SystemExit(f"Installed directory metadata mismatch: {entry.destination}")
        else:
            if (
                not stat.S_ISREG(info.st_mode)
                or sha256(path) != entry.digest
                or stat.S_IMODE(info.st_mode) != int(entry.mode, 8)
                or info.st_uid != ownership_uid
                or info.st_gid != ownership_gid
            ):
                raise SystemExit(f"Installed file mismatch: {entry.destination}")
    split = next(item for item in entries if item.destination == SPLIT_ROUTE_DESTINATION)
    active = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    if sha256(active) != split.digest:
        raise SystemExit("Synthetic active ALSA route is not the installed split-bus candidate.")
    state = mapped_path(system_root, STATE_RECORD_DESTINATION)
    if not state.is_file() or state.is_symlink():
        raise SystemExit("Synthetic transaction-state record is missing.")
    approval = mapped_path(system_root, "/var/lib/a-clockwork-plex/split-bus/activation-approved")
    if approval.exists() or approval.is_symlink():
        raise SystemExit("Stage C7 must never create an activation-approved marker.")


def rollback(
    scenario_root: Path,
    evidence: C6Evidence,
    entries: list[ManifestEntry],
    existing: dict[str, tuple[int, int, int]],
    absent_managed: set[str],
    baseline: tuple[tuple[str, str, str, str, str, str], ...],
    ownership_uid: int,
    ownership_gid: int,
    reason: str,
) -> int:
    system_root = scenario_root / "system-root"
    journal = scenario_root / "journal.tsv"
    _journal(journal, "rollback-start", reason)

    state = mapped_path(system_root, STATE_RECORD_DESTINATION)
    if state.exists() or state.is_symlink():
        if state.is_symlink() or not state.is_file():
            raise SystemExit("Unsafe Stage C7 state record during rollback.")
        state.unlink()

    for entry in reversed([item for item in entries if item.kind == "file"]):
        destination = mapped_path(system_root, entry.destination)
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                raise SystemExit(f"Unsafe managed file during rollback: {entry.destination}")
            destination.unlink()

    active = mapped_path(system_root, CURRENT_ALSA_DESTINATION)
    atomic_copy(
        evidence.current_alsa_snapshot,
        active,
        0o644,
        ownership_uid,
        ownership_gid,
        EXPECTED_PRE_STAGE_C_ALSA_SHA256,
    )

    for destination in sorted(
        absent_managed,
        key=lambda item: len(PurePosixPath(item).parts),
        reverse=True,
    ):
        path = mapped_path(system_root, destination)
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(f"Unsafe managed directory during rollback: {destination}")
        try:
            path.rmdir()
        except OSError as exc:
            raise SystemExit(f"Rollback would remove non-empty directory: {destination}") from exc

    for destination, (mode, uid, gid) in sorted(
        existing.items(), key=lambda item: len(PurePosixPath(item[0]).parts)
    ):
        path = mapped_path(system_root, destination)
        if path.is_symlink() or not path.is_dir():
            raise SystemExit(f"Captured existing directory missing during rollback: {destination}")
        os.chmod(path, mode)
        os.chown(path, uid, gid)

    observed = system_fingerprint(system_root)
    write_fingerprint(scenario_root / "post-rollback-fingerprint.tsv", observed)
    mismatches = 0 if observed == baseline else 1
    _journal(journal, "rollback-finish", f"baseline mismatches={mismatches}")
    return mismatches


def run_scenario(
    rehearsal_root: Path,
    name: str,
    failure_point: str | None,
    package_root: Path,
    evidence: C6Evidence,
    entries: list[ManifestEntry],
    ownership_uid: int,
    ownership_gid: int,
) -> ScenarioResult:
    scenario_root = rehearsal_root / "scenarios" / name
    scenario_root.mkdir(parents=True)
    control = scenario_root / "control"
    control.mkdir()
    lock = RehearsalLock(control / "a-clockwork-plex-audio-route.lock")
    journal = scenario_root / "journal.tsv"
    _journal(journal, "lock-acquired", f"inode={lock.inode}")
    lock.prove_contention()
    _journal(journal, "lock-contention-proved", "second descriptor failed closed")
    identity = f"stage-c7-{secrets.token_hex(12)}"
    _write_tsv(
        scenario_root / "identity.tsv",
        ("item", "value"),
        [
            ("identity", identity),
            ("caller_supplied", "false"),
            ("activation_authoritative", "false"),
        ],
    )
    _journal(journal, "identity-created", identity)

    baseline, existing, absent_managed = seed_scenario(
        scenario_root, evidence, entries, ownership_uid, ownership_gid
    )
    _journal(journal, "baseline-captured", f"entries={len(baseline)}")
    install_verified = False
    rollback_reason = "explicit-uninstall"
    preserved = False
    try:
        system_root = scenario_root / "system-root"
        create_manifest_directories(
            system_root, entries, existing, ownership_uid, ownership_gid
        )
        install_files(
            system_root, package_root, entries, ownership_uid, ownership_gid
        )
        verify_existing_directories(system_root, existing)
        _journal(journal, "files-installed", "all twelve files atomically verified")
        if failure_point == "after-files-installed":
            raise InjectedFailure(failure_point)

        route_digest = select_synthetic_route(
            system_root, entries, ownership_uid, ownership_gid
        )
        verify_existing_directories(system_root, existing)
        _journal(journal, "route-selected", route_digest)
        if failure_point == "after-route-selected":
            raise InjectedFailure(failure_point)

        write_state_record(system_root, identity, ownership_uid, ownership_gid)
        verify_existing_directories(system_root, existing)
        _journal(journal, "state-recorded", STATE_RECORD_DESTINATION)
        if failure_point == "after-state-recorded":
            raise InjectedFailure(failure_point)

        verify_installed_state(
            system_root,
            entries,
            existing,
            ownership_uid,
            ownership_gid,
        )
        preserved = True
        install_verified = True
        write_fingerprint(
            scenario_root / "installed-fingerprint.tsv",
            system_fingerprint(system_root),
        )
        _journal(journal, "installed-state-verified", "candidate files, route and metadata exact")
    except InjectedFailure as exc:
        if str(exc) != failure_point:
            raise
        rollback_reason = f"automatic:{failure_point}"
        verify_existing_directories(scenario_root / "system-root", existing)
        preserved = True
        _journal(journal, "injected-failure", str(exc))
    finally:
        mismatches = rollback(
            scenario_root,
            evidence,
            entries,
            existing,
            absent_managed,
            baseline,
            ownership_uid,
            ownership_gid,
            rollback_reason,
        )
        lock.release()
        _journal(journal, "lock-released", f"rollback mismatches={mismatches}")

    if mismatches:
        raise SystemExit(f"Stage C7 rollback did not restore exact baseline: {name}")
    return ScenarioResult(
        name=name,
        injected_failure=failure_point or "none",
        install_verified=install_verified,
        rollback_reason=rollback_reason,
        rollback_mismatches=mismatches,
        existing_directories_preserved=preserved,
    )


def write_file_plan(path: Path, entries: list[ManifestEntry], evidence: C6Evidence) -> None:
    states = {
        row.get("destination", ""): row.get("preinstall_state", "")
        for row in evidence.filesystem_rows
    }
    _write_tsv(
        path,
        ("type", "destination", "candidate_mode", "candidate_sha256", "captured_state", "mapped_only"),
        [
            (
                entry.kind,
                entry.destination,
                entry.mode,
                entry.digest,
                states.get(entry.destination, "not-recorded"),
                "true",
            )
            for entry in entries
        ],
    )


def write_evidence_manifest(root: Path) -> None:
    rows: list[tuple[object, ...]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = f"{stat.S_IMODE(info.st_mode):o}"
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Evidence contains a symlink: {relative}")
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", mode, "-"))
        elif stat.S_ISREG(info.st_mode):
            digest = "-" if relative == "evidence-manifest.tsv" else sha256(path)
            kind = "self" if relative == "evidence-manifest.tsv" else "file"
            rows.append((relative, kind, mode, digest))
        else:
            raise SystemExit(f"Evidence contains a special object: {relative}")
    manifest = root / "evidence-manifest.tsv"
    if not manifest.exists():
        manifest.write_text("path\ttype\tmode\tsha256\n", encoding="utf-8")
        return write_evidence_manifest(root)
    _write_tsv(manifest, ("path", "type", "mode", "sha256"), rows)


def chown_tree(root: Path, uid: int, gid: int) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            raise SystemExit(f"Refusing to chown symlinked evidence: {path}")
        os.chown(path, uid, gid)
    os.chown(root, uid, gid)


def run_rehearsal(
    package_root: Path,
    stage_c6_root: Path,
    rehearsal_root: Path,
    invoking_uid: int,
    invoking_gid: int,
    ownership_uid: int = 0,
    ownership_gid: int = 0,
) -> list[ScenarioResult]:
    validate_stage_c1_evidence(package_root)
    entries = parse_manifest(package_root)
    evidence = validate_c6(stage_c6_root)
    rehearsal_root = validate_root_scope(
        rehearsal_root, package_root, stage_c6_root, invoking_uid
    )
    package_before = tree_fingerprint(package_root)
    c6_before = tree_fingerprint(stage_c6_root)

    os.chown(rehearsal_root, ownership_uid, ownership_gid)
    results_path = rehearsal_root / "results.tsv"
    results_path.write_text("check\tresult\tdetail\n", encoding="utf-8")
    _append_result(results_path, "root-scope", f"root writes constrained to {rehearsal_root}")
    _append_result(results_path, "input-replay", "Stage C1 package and Stage C6 locked snapshot replayed")
    _append_result(results_path, "disposable-mapping", "all absolute destinations remapped beneath per-scenario system roots")
    _append_result(results_path, "first-install-boundary", "all twelve managed file destinations begin absent")
    write_file_plan(rehearsal_root / "file-plan.tsv", entries, evidence)

    scenarios = [
        run_scenario(
            rehearsal_root,
            "success-explicit-uninstall",
            None,
            package_root,
            evidence,
            entries,
            ownership_uid,
            ownership_gid,
        )
    ]
    for failure in FAILURE_POINTS:
        scenarios.append(
            run_scenario(
                rehearsal_root,
                f"failure-{failure}",
                failure,
                package_root,
                evidence,
                entries,
                ownership_uid,
                ownership_gid,
            )
        )

    if not all(item.existing_directories_preserved for item in scenarios):
        raise SystemExit("A Stage C7 scenario changed a captured existing directory.")
    _append_result(
        results_path,
        "existing-directory-preservation",
        "captured existing modes and ownership remained unchanged during all installs",
    )
    _append_result(results_path, "atomic-install", "all candidate files used double-hashed atomic root-owned copies")
    _append_result(results_path, "synthetic-route-selection", "split-bus candidate selected only inside disposable roots")
    _append_result(results_path, "failure-injection", "three independent post-mutation failures exercised")
    _append_result(results_path, "shared-rollback", "success and all failures invoked the same rollback implementation")
    if any(item.rollback_mismatches for item in scenarios):
        raise SystemExit("One or more Stage C7 scenarios reported rollback mismatches.")
    _append_result(results_path, "exact-state-verification", "all four scenarios ended with zero baseline mismatches")

    _write_tsv(
        rehearsal_root / "scenario-state.tsv",
        (
            "scenario",
            "injected_failure",
            "install_verified",
            "rollback_reason",
            "rollback_mismatches",
            "existing_directories_preserved",
        ),
        [
            (
                item.name,
                item.injected_failure,
                str(item.install_verified).lower(),
                item.rollback_reason,
                item.rollback_mismatches,
                str(item.existing_directories_preserved).lower(),
            )
            for item in scenarios
        ],
    )

    if tree_fingerprint(package_root) != package_before or tree_fingerprint(stage_c6_root) != c6_before:
        raise SystemExit("Stage C1 or Stage C6 input changed during Stage C7.")
    _append_result(
        results_path,
        "production-boundary",
        "inputs unchanged; no production path, service or audio command was used",
    )
    _append_result(
        results_path,
        "activation-interface",
        "absent; no production install, activation, failback, rollback or uninstall action",
    )

    report = f"""A Clockwork Plex Stage C7 root-owned disposable transaction rehearsal
Generated: {datetime.now().astimezone().isoformat()}
Stage C1 package: {package_root.resolve()}
Stage C6 evidence: {stage_c6_root.resolve()}
Stage C7 root: {rehearsal_root}
Managed package files: 12
Scenarios: 4
Injected failures: 3
Final rollback mismatches: 0

Proved by Stage C7:
- root-owned atomic installation of all candidate files inside disposable roots
- source checksum before and after each copy
- exact candidate mode and ownership verification
- existing captured directories were never chmodded or chowned during install
- synthetic /etc/sudoers.d remained at its captured mode throughout
- split-bus selection occurred only inside disposable roots
- successful explicit uninstall and three automatic failure rollbacks shared one implementation
- exact type, mode, UID, GID and checksum baseline restoration
- Stage C1 and Stage C6 inputs remained unchanged

Not proved by Stage C7:
- production lock creation or production filesystem mutation
- service-manager, mixer, module, PCM, DAC or CamillaDSP behaviour
- ALSA parsing, route health, failback or reboot behaviour

Safety state:
- one constrained sudo command launched the root engine
- root wrote only inside the fresh Stage C7 directory
- no production path was opened for writing
- no activation-approved marker was created
- no production activation interface exists
- persistent Stage C activation remains blocked
"""
    (rehearsal_root / "report.txt").write_text(report, encoding="utf-8")
    write_evidence_manifest(rehearsal_root)
    return scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run root-owned Stage C file transactions only in disposable system roots."
    )
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--stage-c6-root", required=True, type=Path)
    parser.add_argument("--rehearsal-root", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.confirm != REQUIRED_CONFIRMATION:
        raise SystemExit("Exact Stage C7 disposable-transaction token was not supplied.")
    if os.geteuid() != 0:
        raise SystemExit("Stage C7 root-owned engine requires the constrained sudo wrapper.")
    invoking_user = os.environ.get("SUDO_USER", "")
    if not invoking_user or invoking_user == "root":
        raise SystemExit("Stage C7 requires a non-root invoking user through sudo.")
    account = pwd.getpwnam(invoking_user)
    invoking_gid = account.pw_gid
    completed = False
    rehearsal_root = args.rehearsal_root
    try:
        run_rehearsal(
            args.package_root,
            args.stage_c6_root,
            rehearsal_root,
            account.pw_uid,
            invoking_gid,
        )
        completed = True
    finally:
        if rehearsal_root.exists() and not rehearsal_root.is_symlink():
            chown_tree(rehearsal_root, account.pw_uid, invoking_gid)
            rehearsal_root.chmod(0o700)
    if not completed:
        raise SystemExit("Stage C7 root-owned disposable transaction did not complete.")
    print("A Clockwork Plex Stage C7 root-owned disposable transaction rehearsal passed.")
    print(f"  Directory: {rehearsal_root}")
    print(f"  Results:   {rehearsal_root / 'results.tsv'}")
    print(f"  Scenarios: {rehearsal_root / 'scenario-state.tsv'}")
    print(f"  Report:    {rehearsal_root / 'report.txt'}")
    print("No production path was written or changed. Persistent activation remains blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
