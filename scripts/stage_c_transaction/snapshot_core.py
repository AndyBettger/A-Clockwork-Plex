#!/usr/bin/python3
from __future__ import annotations

import grp
import hashlib
import os
import pwd
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .package_review import ManifestEntry

CURRENT_ALSA_DESTINATION = "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"


@dataclass(frozen=True)
class SnapshotSummary:
    managed_absent: int
    managed_present: int
    conflicts: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_absolute_destination(raw: str) -> PurePosixPath:
    destination = PurePosixPath(raw)
    if not destination.is_absolute() or raw == "/" or ".." in destination.parts:
        raise SystemExit(f"Unsafe snapshot destination: {raw}")
    return destination


def _system_path(system_root: Path, destination: str) -> Path:
    pure = _safe_absolute_destination(destination)
    return system_root.joinpath(*pure.parts[1:])


def _relative_path(destination: str) -> Path:
    pure = _safe_absolute_destination(destination)
    return Path(*pure.parts[1:])


def _mode_from_stat(info: os.stat_result) -> str:
    return f"{stat.S_IMODE(info.st_mode):o}"


def _owner_from_stat(info: os.stat_result) -> str:
    try:
        user = pwd.getpwuid(info.st_uid).pw_name
    except KeyError:
        user = str(info.st_uid)
    try:
        group = grp.getgrgid(info.st_gid).gr_name
    except KeyError:
        group = str(info.st_gid)
    return f"{user}:{group}"


def _marker_path(markers_root: Path, destination: str, suffix: str) -> Path:
    relative = str(_relative_path(destination)).replace("/", "__")
    return markers_root / f"{relative}.{suffix}"


def _copy_regular(source: Path, destination: Path) -> tuple[str, str, str]:
    info = source.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise SystemExit(f"Refusing to snapshot symlinked path: {source}")
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"Snapshot source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination, follow_symlinks=False)
    return _mode_from_stat(info), _owner_from_stat(info), sha256(source)


def collect_filesystem_snapshot(
    entries: list[ManifestEntry],
    system_root: Path,
    evidence_root: Path,
    current_alsa_destination: str = CURRENT_ALSA_DESTINATION,
) -> SnapshotSummary:
    """Capture production file/absence state beneath evidence_root only.

    system_root is `/` in the real root-owned rehearsal and a temporary fake
    root in unit tests. This function never writes through system_root.
    """

    rootfs = evidence_root / "rootfs"
    markers = evidence_root / "absence-markers"
    rootfs.mkdir(parents=True, exist_ok=False)
    markers.mkdir(parents=True, exist_ok=False)

    rows = ["kind\tdestination\tpreinstall_state\tmode\towner\tsha256\tsnapshot"]

    current_source = _system_path(system_root, current_alsa_destination)
    current_snapshot = rootfs / _relative_path(current_alsa_destination)
    if not current_source.exists() or current_source.is_symlink():
        raise SystemExit(f"Current ALSA route is missing or symlinked: {current_alsa_destination}")
    mode, owner, digest = _copy_regular(current_source, current_snapshot)
    rows.append(
        f"file\t{current_alsa_destination}\tpresent\t{mode}\t{owner}\t{digest}\t{current_snapshot}"
    )

    managed_absent = 0
    managed_present = 0
    conflicts = 0

    for entry in (item for item in entries if item.kind == "file"):
        source = _system_path(system_root, entry.destination)
        try:
            info = source.lstat()
        except FileNotFoundError:
            marker = _marker_path(markers, entry.destination, "absent")
            marker.write_text(f"ABSENT\t{entry.destination}\n", encoding="utf-8")
            rows.append(f"file\t{entry.destination}\tabsent\t-\t-\t-\t{marker}")
            managed_absent += 1
            continue
        except PermissionError as exc:
            raise SystemExit(
                f"Root-owned snapshot could not resolve protected destination {entry.destination}: {exc}"
            ) from exc

        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Refusing symlinked managed file destination: {entry.destination}")
        if not stat.S_ISREG(info.st_mode):
            conflicts += 1
            rows.append(
                f"file\t{entry.destination}\tconflict\t{_mode_from_stat(info)}\t"
                f"{_owner_from_stat(info)}\t-\t-"
            )
            continue

        snapshot = rootfs / entry.relative
        mode, owner, digest = _copy_regular(source, snapshot)
        rows.append(f"file\t{entry.destination}\tpresent\t{mode}\t{owner}\t{digest}\t{snapshot}")
        managed_present += 1

    for entry in (item for item in entries if item.kind == "directory"):
        source = _system_path(system_root, entry.destination)
        try:
            info = source.lstat()
        except FileNotFoundError:
            rows.append(f"directory\t{entry.destination}\tabsent\t-\t-\t-\t-")
            continue
        except PermissionError as exc:
            raise SystemExit(
                f"Root-owned snapshot could not resolve managed directory {entry.destination}: {exc}"
            ) from exc

        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Refusing symlinked managed directory: {entry.destination}")
        if not stat.S_ISDIR(info.st_mode):
            conflicts += 1
            rows.append(
                f"directory\t{entry.destination}\tconflict\t{_mode_from_stat(info)}\t"
                f"{_owner_from_stat(info)}\t-\t-"
            )
        else:
            rows.append(
                f"directory\t{entry.destination}\tpresent\t{_mode_from_stat(info)}\t"
                f"{_owner_from_stat(info)}\t-\t-"
            )

    (evidence_root / "filesystem-state.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return SnapshotSummary(
        managed_absent=managed_absent,
        managed_present=managed_present,
        conflicts=conflicts,
    )


def write_evidence_manifest(evidence_root: Path) -> Path:
    output = evidence_root / "evidence-manifest.tsv"
    rows = ["path\ttype\tmode\tsha256"]
    for path in sorted(evidence_root.rglob("*")):
        if path == output:
            continue
        info = path.lstat()
        relative = path.relative_to(evidence_root)
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Evidence tree contains a symlink: {relative}")
        if stat.S_ISDIR(info.st_mode):
            rows.append(f"{relative}\tdirectory\t{_mode_from_stat(info)}\t-")
        elif stat.S_ISREG(info.st_mode):
            rows.append(f"{relative}\tfile\t{_mode_from_stat(info)}\t{sha256(path)}")
        else:
            raise SystemExit(f"Evidence tree contains a special object: {relative}")
    rows.append("evidence-manifest.tsv\tself\t-\t-")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return output


def chown_evidence_tree(evidence_root: Path, uid: int, gid: int) -> None:
    for path in sorted(evidence_root.rglob("*"), reverse=True):
        if path.is_symlink():
            raise SystemExit(f"Refusing to chown symlink in evidence tree: {path}")
        os.chown(path, uid, gid)
    os.chown(evidence_root, uid, gid)
