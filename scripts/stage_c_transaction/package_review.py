#!/usr/bin/python3
from __future__ import annotations

import csv
import grp
import hashlib
import pwd
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

EXPECTED_PACKAGE_FILES = 12
REQUIRED_STATE_ROW = ("directory", "/var/lib/a-clockwork-plex/split-bus", "755", "root:root", "-")


@dataclass(frozen=True)
class ManifestEntry:
    kind: str
    destination: str
    mode: str
    owner: str
    digest: str

    @property
    def relative(self) -> Path:
        return Path(self.destination.lstrip("/"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def owner_string(path: Path) -> str:
    info = path.lstat()
    try:
        user = pwd.getpwuid(info.st_uid).pw_name
    except KeyError:
        user = str(info.st_uid)
    try:
        group = grp.getgrgid(info.st_gid).gr_name
    except KeyError:
        group = str(info.st_gid)
    return f"{user}:{group}"


def mode_string(path: Path) -> str:
    return f"{stat.S_IMODE(path.lstat().st_mode):o}"


def _safe_destination(raw: str) -> str:
    pure = PurePosixPath(raw)
    if not pure.is_absolute() or ".." in pure.parts or raw == "/":
        raise SystemExit(f"Unsafe manifest destination: {raw}")
    return str(pure)


def parse_manifest(package_root: Path) -> list[ManifestEntry]:
    manifest = package_root / "manifest.tsv"
    rootfs = package_root / "rootfs"
    if not manifest.is_file() or not rootfs.is_dir():
        raise SystemExit("Stage C1 package must contain manifest.tsv and rootfs/.")

    with manifest.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows or rows[0] != ["type", "destination", "mode", "owner", "sha256"]:
        raise SystemExit("Unexpected Stage C1 manifest header.")

    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for row in rows[1:]:
        if len(row) != 5:
            raise SystemExit(f"Malformed manifest row: {row}")
        kind, destination, mode, owner, digest = row
        destination = _safe_destination(destination)
        if destination in seen:
            raise SystemExit(f"Duplicate manifest destination: {destination}")
        seen.add(destination)
        if kind not in {"directory", "file"}:
            raise SystemExit(f"Unsupported manifest type: {kind}")
        try:
            int(mode, 8)
        except ValueError as exc:
            raise SystemExit(f"Invalid manifest mode for {destination}: {mode}") from exc
        if owner != "root:root":
            raise SystemExit(f"Unexpected manifest owner for {destination}: {owner}")
        if kind == "directory" and digest != "-":
            raise SystemExit(f"Directory digest must be '-': {destination}")
        if kind == "file" and not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SystemExit(f"Invalid file digest: {destination}")

        source = rootfs / destination.lstrip("/")
        if source.is_symlink():
            raise SystemExit(f"Package contains a symlink: {destination}")
        if kind == "directory" and not source.is_dir():
            raise SystemExit(f"Manifest directory is missing: {destination}")
        if kind == "file":
            if not source.is_file():
                raise SystemExit(f"Manifest file is missing: {destination}")
            if sha256(source) != digest:
                raise SystemExit(f"Package checksum mismatch: {destination}")
        if mode_string(source) != mode:
            raise SystemExit(f"Package mode mismatch: {destination}")
        entries.append(ManifestEntry(kind, destination, mode, owner, digest))

    files = [entry for entry in entries if entry.kind == "file"]
    if len(files) != EXPECTED_PACKAGE_FILES:
        raise SystemExit(
            f"Stage C1 package file count mismatch: expected {EXPECTED_PACKAGE_FILES}, found {len(files)}"
        )
    rows_set = {(e.kind, e.destination, e.mode, e.owner, e.digest) for e in entries}
    if REQUIRED_STATE_ROW not in rows_set:
        raise SystemExit("Stage C1 manifest omitted the empty split-bus state directory.")
    if any("__pycache__" in e.destination or e.destination.endswith(".pyc") for e in entries):
        raise SystemExit("Stage C1 manifest contains Python cache material.")
    return entries


def validate_stage_c1_evidence(package_root: Path) -> None:
    results_path = package_root / "results.tsv"
    if not results_path.is_file():
        raise SystemExit("Stage C1 results.tsv is missing.")
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows or rows[0] != ["check", "result", "detail"]:
        raise SystemExit("Unexpected Stage C1 results header.")
    failures = [row for row in rows[1:] if len(row) != 3 or row[1] != "PASS"]
    if len(rows) < 2 or failures:
        raise SystemExit(f"Stage C1 package is not fully PASS: {failures[0] if failures else 'no checks'}")

    report_path = package_root / "report.txt"
    if not report_path.is_file():
        raise SystemExit("Stage C1 report.txt is missing.")
    report = report_path.read_text(encoding="utf-8")
    for expected in (
        "Package version: 2",
        "Package files: 12",
        "- no activation option exists",
        "- generated route mutation actions return exit 78",
        "- generated units require an absent activation-approved marker",
    ):
        if expected not in report:
            raise SystemExit(f"Stage C1 report contract is missing: {expected}")

    rootfs = package_root / "rootfs"
    helper = (rootfs / "usr/local/bin/a-clockwork-plex-audio-route").read_text(encoding="utf-8")
    if "stage-c1-candidate-only" not in helper or "return 78" not in helper:
        raise SystemExit("Generated route helper is not the inert Stage C1 candidate.")
    for relative in (
        "etc/systemd/system/a-clockwork-plex-audio-route.service",
        "etc/systemd/system/a-clockwork-plex-camilladsp.service",
        "etc/systemd/system/a-clockwork-plex-audio-failback.service",
    ):
        unit = (rootfs / relative).read_text(encoding="utf-8")
        marker = "ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved"
        if marker not in unit:
            raise SystemExit(f"Generated unit lacks the approval-marker gate: /{relative}")


def write_destination_state(entries: list[ManifestEntry], package_root: Path, output: Path) -> int:
    rows = [
        "type\tdestination\tcandidate_mode\tcandidate_sha256\tcurrent_state\t"
        "current_mode\tcurrent_owner\tcurrent_sha256\tverdict"
    ]
    existing_files = 0
    rootfs = package_root / "rootfs"
    for entry in entries:
        destination = Path(entry.destination)
        if entry.kind == "directory":
            if destination.exists():
                current_state = "directory" if destination.is_dir() and not destination.is_symlink() else "conflict"
                current_mode = mode_string(destination)
                current_owner = owner_string(destination)
                verdict = "existing-directory" if current_state == "directory" else "conflict"
            else:
                current_state = "absent"
                current_mode = current_owner = "-"
                verdict = "create-directory"
            rows.append(
                f"directory\t{entry.destination}\t{entry.mode}\t-\t{current_state}\t"
                f"{current_mode}\t{current_owner}\t-\t{verdict}"
            )
            continue

        candidate = rootfs / entry.relative
        if not destination.exists() and not destination.is_symlink():
            rows.append(
                f"file\t{entry.destination}\t{entry.mode}\t{sha256(candidate)}\tabsent\t-\t-\t-\tinstall-new"
            )
            continue

        existing_files += 1
        if destination.is_symlink():
            current_state, current_sha = "symlink", "-"
        elif destination.is_file():
            current_state, current_sha = "file", sha256(destination)
        else:
            current_state, current_sha = "non-file", "-"
        rows.append(
            f"file\t{entry.destination}\t{entry.mode}\t{entry.digest}\t{current_state}\t"
            f"{mode_string(destination)}\t{owner_string(destination)}\t{current_sha}\t"
            "unexpected-existing-destination"
        )
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return existing_files
