#!/usr/bin/python3
from __future__ import annotations

"""Fixed Stage C21 package-v2 and accepted-baseline review contracts.

This module is validation and comparison code only. It has no production lock,
transaction, filesystem-mutation, service, route, mixer, PCM, DAC, CamillaDSP,
installation, approval or activation capability.
"""

import csv
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from stage_c_activation_package.core import (
    EXPECTED_FILES,
    RUNTIME_MODULES,
    package_fingerprint,
)
from stage_c_activation_package.runtime_templates import PACKAGE_PHASE

from .package_review import ManifestEntry, mode_string, sha256
from .production_adapter_contract import (
    AdapterStatus,
    DacSnapshot,
    HostContractSnapshot,
    LoopbackSnapshot,
    MixerSnapshot,
    PackageFingerprint,
    ProductionLockObservation,
    ServiceActiveState,
    ServiceEnableState,
    ServiceLoadState,
    ServiceSnapshot,
    ServiceUnit,
)
from .production_prepare_only_inspector_v7 import (
    ProductionApprovalBaselineStateV7,
    ProductionPrepareOnlyDispositionV7,
    ProductionPrepareOnlyReportV7,
)


EXPECTED_PAYLOAD_FILES = EXPECTED_FILES - 1
PACKAGE_CONTRACT_DESTINATION = (
    "/usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json"
)
STATE_DIRECTORY_DESTINATION = "/var/lib/a-clockwork-plex/split-bus"
ACCEPTED_PACKAGE_FINGERPRINT = (
    "dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5"
)
BASELINE_PREFIX = "a-clockwork-plex-stage-c21-production-baseline."
BASELINE_REPORT_TEXT_SHA256 = (
    "350ae99ee63911cb524f7220e4629e5da669f3c79f8e409d2f9fdf4652c16a85"
)
BASELINE_REPORT_JSON_SHA256 = (
    "3c6dcd3c17a3ce363ddf3f5bdd9d93c8891a2a006c0c154905a3a809b79348e0"
)
BASELINE_MANIFEST_JSON_SHA256 = (
    "4995bdf85cb06995a9b26c164fdc28991d755631e9c4dbe527eddc005253c1dc"
)
EXPECTED_PACKAGE_RESULTS = (
    "alsa-split-parse",
    "alsa-direct-parse",
    "public-pcm-contract",
    "camilladsp-config",
    "runtime-python-syntax",
    "sudoers-candidate",
    "package-purity",
    "systemd-readiness-contract",
    "runtime-entry-boundary",
    "package-fingerprint",
    "manifest-contract",
)
EXPECTED_MIXER_VALUES = (94, 100, 100, 100)
EXPECTED_DAC_OWNER = ("andy", "node", "read-write")


class CurrentPackageContractErrorV7(RuntimeError):
    """The fixed current-package or accepted-baseline contract changed."""


@dataclass(frozen=True)
class AcceptedBaselineEvidenceV7:
    root: str
    package: PackageFingerprint
    report_text_sha256: str
    report_json_sha256: str
    manifest_json_sha256: str

    def __post_init__(self) -> None:
        root = Path(self.root)
        if not root.name.startswith(BASELINE_PREFIX):
            raise ValueError("accepted baseline root uses the wrong fixed prefix")
        if self.package.sha256 != ACCEPTED_PACKAGE_FINGERPRINT:
            raise ValueError("accepted baseline package fingerprint changed")
        if self.report_text_sha256 != BASELINE_REPORT_TEXT_SHA256:
            raise ValueError("accepted baseline text digest changed")
        if self.report_json_sha256 != BASELINE_REPORT_JSON_SHA256:
            raise ValueError("accepted baseline JSON digest changed")
        if self.manifest_json_sha256 != BASELINE_MANIFEST_JSON_SHA256:
            raise ValueError("accepted baseline manifest digest changed")


def _safe_destination(raw: str) -> str:
    pure = PurePosixPath(raw)
    if not pure.is_absolute() or raw == "/" or ".." in pure.parts:
        raise CurrentPackageContractErrorV7(
            f"unsafe current-package manifest destination: {raw}"
        )
    return str(pure)


def _require_regular_single_link(path: Path, label: str) -> stat.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CurrentPackageContractErrorV7(f"{label} is unavailable: {exc}") from exc
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
    ):
        raise CurrentPackageContractErrorV7(
            f"{label} is not a single-link regular file: {path}"
        )
    return info


def parse_current_package_manifest_v7(package_root: Path) -> tuple[ManifestEntry, ...]:
    manifest = package_root / "manifest.tsv"
    rootfs = package_root / "rootfs"
    _require_regular_single_link(manifest, "current-package manifest")
    if rootfs.is_symlink() or not rootfs.is_dir():
        raise CurrentPackageContractErrorV7(
            "current package must contain one real rootfs directory"
        )

    with manifest.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows or rows[0] != ["type", "destination", "mode", "owner", "sha256"]:
        raise CurrentPackageContractErrorV7(
            "unexpected current-package manifest header"
        )

    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for row in rows[1:]:
        if len(row) != 5:
            raise CurrentPackageContractErrorV7(f"malformed manifest row: {row}")
        kind, destination, mode, owner, digest = row
        destination = _safe_destination(destination)
        if destination in seen:
            raise CurrentPackageContractErrorV7(
                f"duplicate current-package destination: {destination}"
            )
        seen.add(destination)
        if kind not in {"directory", "file"}:
            raise CurrentPackageContractErrorV7(
                f"unsupported current-package object type: {kind}"
            )
        try:
            parsed_mode = int(mode, 8)
        except ValueError as exc:
            raise CurrentPackageContractErrorV7(
                f"invalid current-package mode for {destination}: {mode}"
            ) from exc
        if parsed_mode < 0 or parsed_mode > 0o7777:
            raise CurrentPackageContractErrorV7(
                f"out-of-range current-package mode for {destination}: {mode}"
            )
        if owner != "root:root":
            raise CurrentPackageContractErrorV7(
                f"unexpected current-package owner for {destination}: {owner}"
            )
        if kind == "directory" and digest != "-":
            raise CurrentPackageContractErrorV7(
                f"directory digest must be '-' for {destination}"
            )
        if kind == "file" and not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CurrentPackageContractErrorV7(
                f"invalid current-package digest for {destination}"
            )

        source = rootfs / destination.lstrip("/")
        try:
            info = source.lstat()
        except OSError as exc:
            raise CurrentPackageContractErrorV7(
                f"manifest object is unavailable: {destination}: {exc}"
            ) from exc
        if stat.S_ISLNK(info.st_mode):
            raise CurrentPackageContractErrorV7(
                f"current package contains a symlink: {destination}"
            )
        if kind == "directory":
            if not stat.S_ISDIR(info.st_mode):
                raise CurrentPackageContractErrorV7(
                    f"manifest directory differs: {destination}"
                )
        else:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise CurrentPackageContractErrorV7(
                    f"manifest file is not single-link regular: {destination}"
                )
            if sha256(source) != digest:
                raise CurrentPackageContractErrorV7(
                    f"current-package checksum differs: {destination}"
                )
        if mode_string(source) != mode:
            raise CurrentPackageContractErrorV7(
                f"current-package mode differs: {destination}"
            )
        entries.append(ManifestEntry(kind, destination, mode, owner, digest))

    files = tuple(entry for entry in entries if entry.kind == "file")
    if len(files) != EXPECTED_FILES:
        raise CurrentPackageContractErrorV7(
            f"current package must contain exactly {EXPECTED_FILES} files; "
            f"found {len(files)}"
        )
    state_rows = {
        (entry.kind, entry.destination, entry.mode, entry.owner, entry.digest)
        for entry in entries
    }
    required_state = (
        "directory",
        STATE_DIRECTORY_DESTINATION,
        "755",
        "root:root",
        "-",
    )
    if required_state not in state_rows:
        raise CurrentPackageContractErrorV7(
            "current manifest omitted the fixed root:root 0755 state directory"
        )
    if any(
        "__pycache__" in entry.destination or entry.destination.endswith(".pyc")
        for entry in entries
    ):
        raise CurrentPackageContractErrorV7(
            "current manifest contains Python cache material"
        )
    return tuple(entries)


def _load_json_file(path: Path, label: str) -> dict[str, Any]:
    _require_regular_single_link(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentPackageContractErrorV7(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CurrentPackageContractErrorV7(f"{label} must contain one JSON object")
    return value


def _validate_package_results(package_root: Path) -> None:
    path = package_root / "results.tsv"
    _require_regular_single_link(path, "current-package results")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if not rows or rows[0] != ["check", "result", "detail"]:
        raise CurrentPackageContractErrorV7(
            "unexpected current-package results header"
        )
    observed = tuple(row[0] for row in rows[1:] if len(row) == 3)
    if observed != EXPECTED_PACKAGE_RESULTS or len(rows) != len(observed) + 1:
        raise CurrentPackageContractErrorV7(
            "current-package validation check order changed"
        )
    if any(row[1] != "PASS" for row in rows[1:]):
        raise CurrentPackageContractErrorV7(
            "current-package validation contains a non-PASS result"
        )


def _validate_package_report(package_root: Path) -> None:
    path = package_root / "report.txt"
    _require_regular_single_link(path, "current-package report")
    report = path.read_text(encoding="utf-8")
    markers = (
        "Package version: 2",
        f"Package phase: {PACKAGE_PHASE}",
        f"Package fingerprint: {ACCEPTED_PACKAGE_FINGERPRINT}",
        f"Package files: {EXPECTED_FILES}",
        f"Fingerprinted payload files: {EXPECTED_PAYLOAD_FILES}",
        "this generator has no installer or activation option",
        "no production path was written",
    )
    for marker in markers:
        if marker not in report:
            raise CurrentPackageContractErrorV7(
                f"current-package report omitted: {marker}"
            )


def validate_current_package_v7(package_root: Path) -> PackageFingerprint:
    root = package_root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise CurrentPackageContractErrorV7(
            "current package root must be one real directory"
        )
    entries = parse_current_package_manifest_v7(root)
    _validate_package_results(root)
    _validate_package_report(root)

    contract_path = root / "rootfs" / PACKAGE_CONTRACT_DESTINATION.lstrip("/")
    contract = _load_json_file(contract_path, "current-package contract")
    if contract.get("schema_version") != 1:
        raise CurrentPackageContractErrorV7(
            "current-package contract schema changed"
        )
    if contract.get("package_phase") != PACKAGE_PHASE:
        raise CurrentPackageContractErrorV7(
            "current-package contract phase changed"
        )
    if contract.get("host_mutation_available") is not True:
        raise CurrentPackageContractErrorV7(
            "current-package contract no longer identifies reviewed host authority"
        )
    rows = contract.get("files")
    if not isinstance(rows, list) or len(rows) != EXPECTED_PAYLOAD_FILES:
        raise CurrentPackageContractErrorV7(
            "current-package contract payload inventory changed"
        )

    canonical_rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise CurrentPackageContractErrorV7(
                "current-package contract row shape changed"
            )
        path = _safe_destination(row["path"])
        digest = row["sha256"]
        if path == PACKAGE_CONTRACT_DESTINATION:
            raise CurrentPackageContractErrorV7(
                "current-package contract fingerprints itself"
            )
        if path in seen_paths or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise CurrentPackageContractErrorV7(
                f"invalid current-package contract row: {path}"
            )
        seen_paths.add(path)
        candidate = root / "rootfs" / path.lstrip("/")
        _require_regular_single_link(candidate, f"contract payload {path}")
        if sha256(candidate) != digest:
            raise CurrentPackageContractErrorV7(
                f"contract payload checksum differs: {path}"
            )
        canonical_rows.append({"path": path, "sha256": digest})
    if canonical_rows != sorted(canonical_rows, key=lambda row: row["path"]):
        raise CurrentPackageContractErrorV7(
            "current-package contract payload rows are not canonical"
        )

    manifest_files = {
        entry.destination for entry in entries if entry.kind == "file"
    }
    if manifest_files != seen_paths | {PACKAGE_CONTRACT_DESTINATION}:
        raise CurrentPackageContractErrorV7(
            "manifest and package-contract file inventories differ"
        )
    observed_fingerprint = package_fingerprint(canonical_rows)
    if contract.get("package_fingerprint") != observed_fingerprint:
        raise CurrentPackageContractErrorV7(
            "current-package contract fingerprint does not match its rows"
        )
    if observed_fingerprint != ACCEPTED_PACKAGE_FINGERPRINT:
        raise CurrentPackageContractErrorV7(
            "current package differs from the accepted target package"
        )

    runtime_root = root / "rootfs/usr/local/lib/a-clockwork-plex/runtime-authority/stage_c_runtime_authority"
    expected_runtime = set(RUNTIME_MODULES)
    observed_runtime = {
        path.name for path in runtime_root.iterdir() if path.is_file()
    }
    if observed_runtime != expected_runtime:
        raise CurrentPackageContractErrorV7(
            "current runtime-authority module inventory changed"
        )
    if (runtime_root / "recording_runtime_adapter.py").exists():
        raise CurrentPackageContractErrorV7(
            "current package contains the disposable recording adapter"
        )
    return PackageFingerprint(observed_fingerprint)


def validate_accepted_baseline_evidence_v7(
    baseline_root: Path,
    package: PackageFingerprint,
) -> AcceptedBaselineEvidenceV7:
    root = baseline_root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir() or not root.name.startswith(BASELINE_PREFIX):
        raise CurrentPackageContractErrorV7(
            "accepted baseline must be one real fixed-prefix directory"
        )
    observed_names = {path.name for path in root.iterdir()}
    if observed_names != {"report.txt", "report.json", "manifest.json"}:
        raise CurrentPackageContractErrorV7(
            "accepted baseline evidence inventory changed"
        )
    report_text = root / "report.txt"
    report_json = root / "report.json"
    manifest_json = root / "manifest.json"
    for path, label in (
        (report_text, "baseline text report"),
        (report_json, "baseline JSON report"),
        (manifest_json, "baseline manifest"),
    ):
        _require_regular_single_link(path, label)

    if sha256(report_text) != BASELINE_REPORT_TEXT_SHA256:
        raise CurrentPackageContractErrorV7(
            "accepted baseline text report digest changed"
        )
    if sha256(report_json) != BASELINE_REPORT_JSON_SHA256:
        raise CurrentPackageContractErrorV7(
            "accepted baseline JSON report digest changed"
        )
    if sha256(manifest_json) != BASELINE_MANIFEST_JSON_SHA256:
        raise CurrentPackageContractErrorV7(
            "accepted baseline manifest digest changed"
        )

    manifest = _load_json_file(manifest_json, "baseline manifest")
    if (
        manifest.get("complete") is not True
        or manifest.get("disposition") != "baseline-ready"
        or manifest.get("candidate_package_sha256") != package.sha256
    ):
        raise CurrentPackageContractErrorV7(
            "accepted baseline completion contract changed"
        )
    files = manifest.get("files")
    expected_files = {
        "report.txt": {
            "bytes": report_text.stat().st_size,
            "sha256": BASELINE_REPORT_TEXT_SHA256,
        },
        "report.json": {
            "bytes": report_json.stat().st_size,
            "sha256": BASELINE_REPORT_JSON_SHA256,
        },
    }
    if files != expected_files:
        raise CurrentPackageContractErrorV7(
            "accepted baseline manifest file binding changed"
        )
    authority = manifest.get("authority")
    if not isinstance(authority, dict) or any(authority.values()):
        raise CurrentPackageContractErrorV7(
            "accepted baseline manifest invents authority"
        )

    report = _load_json_file(report_json, "baseline JSON report")
    _validate_baseline_report_payload_v7(report, package)
    return AcceptedBaselineEvidenceV7(
        root=str(root),
        package=package,
        report_text_sha256=BASELINE_REPORT_TEXT_SHA256,
        report_json_sha256=BASELINE_REPORT_JSON_SHA256,
        manifest_json_sha256=BASELINE_MANIFEST_JSON_SHA256,
    )


def _validate_baseline_report_payload_v7(
    report: dict[str, Any],
    package: PackageFingerprint,
) -> None:
    if (
        report.get("status") != "pass"
        or report.get("disposition") != "baseline-ready"
        or report.get("candidate_package") != {"sha256": package.sha256}
    ):
        raise CurrentPackageContractErrorV7(
            "accepted baseline report identity changed"
        )
    authority = report.get("authority")
    if not isinstance(authority, dict) or any(authority.values()):
        raise CurrentPackageContractErrorV7(
            "accepted baseline report invents authority"
        )
    observations = report.get("observations")
    if not isinstance(observations, dict):
        raise CurrentPackageContractErrorV7(
            "accepted baseline observations are missing"
        )
    lock = observations.get("production_lock", {}).get("payload")
    if not isinstance(lock, dict) or lock.get("exists") is not False or lock.get("held_by_caller") is not False:
        raise CurrentPackageContractErrorV7(
            "accepted baseline production lock is not absent"
        )
    approval = observations.get("approval")
    if not isinstance(approval, dict) or approval.get("state") != "absent" or approval.get("present") is not False:
        raise CurrentPackageContractErrorV7(
            "accepted baseline approval is not absent"
        )

    service_rows = observations.get("services", {}).get("payload", {}).get("services")
    expected_services = [
        {
            "unit": "plexamp.service",
            "load": "loaded",
            "active": "active",
            "enabled": "enabled",
        },
        {
            "unit": "shairport-sync.service",
            "load": "loaded",
            "active": "active",
            "enabled": "enabled",
        },
        {
            "unit": "a-clockwork-plex.service",
            "load": "loaded",
            "active": "active",
            "enabled": "enabled",
        },
        {
            "unit": "a-clockwork-plex-audio-route.service",
            "load": "not-found",
            "active": "inactive",
            "enabled": "not-found",
        },
        {
            "unit": "a-clockwork-plex-camilladsp.service",
            "load": "not-found",
            "active": "inactive",
            "enabled": "not-found",
        },
        {
            "unit": "a-clockwork-plex-audio-failback.service",
            "load": "not-found",
            "active": "inactive",
            "enabled": "not-found",
        },
    ]
    if service_rows != expected_services:
        raise CurrentPackageContractErrorV7(
            "accepted baseline service state changed"
        )
    mixer = observations.get("mixer", {}).get("payload")
    if mixer != {
        "plexamp_output": 94,
        "airplay_output": 100,
        "music_master": 100,
        "maximum_alarm_volume": 100,
    }:
        raise CurrentPackageContractErrorV7(
            "accepted baseline mixer state changed"
        )
    loopback = observations.get("loopback", {}).get("payload")
    if loopback != {
        "contract": {
            "module": "snd_aloop",
            "card_index": 7,
            "card_id": "ACP_Loopback",
            "pcm_substreams": 2,
            "pcm_notify": 1,
        },
        "loaded": True,
    }:
        raise CurrentPackageContractErrorV7(
            "accepted baseline loopback state changed"
        )
    dac = observations.get("dac", {}).get("payload")
    if not isinstance(dac, dict) or dac.get("released") is not False:
        raise CurrentPackageContractErrorV7(
            "accepted baseline DAC state changed"
        )
    if dac.get("contract") != {
        "sample_format": "S16_LE",
        "channels": 2,
        "rate": 44100,
        "period_size": 1024,
        "buffer_size": 8192,
    }:
        raise CurrentPackageContractErrorV7(
            "accepted baseline DAC contract changed"
        )
    owners = dac.get("owners")
    if not isinstance(owners, list) or not any(
        isinstance(owner, dict)
        and owner.get("user") == EXPECTED_DAC_OWNER[0]
        and owner.get("command") == EXPECTED_DAC_OWNER[1]
        and owner.get("access") == EXPECTED_DAC_OWNER[2]
        and isinstance(owner.get("pid"), int)
        and owner["pid"] > 0
        for owner in owners
    ):
        raise CurrentPackageContractErrorV7(
            "accepted baseline lacks the required Plexamp DAC owner contract"
        )


def validate_prepare_only_report_against_accepted_v7(
    report: ProductionPrepareOnlyReportV7,
    package: PackageFingerprint,
) -> None:
    if not isinstance(report, ProductionPrepareOnlyReportV7):
        raise TypeError("live baseline comparison requires ProductionPrepareOnlyReportV7")
    if report.candidate_package != package:
        raise CurrentPackageContractErrorV7(
            "live prepare-only report uses the wrong package"
        )
    if report.disposition is not ProductionPrepareOnlyDispositionV7.BASELINE_READY:
        raise CurrentPackageContractErrorV7(
            f"live appliance is not baseline-ready: {report.disposition.value}"
        )
    if report.status is not AdapterStatus.PASS:
        raise CurrentPackageContractErrorV7(
            "live prepare-only report did not pass"
        )
    if report.production_lock.payload != ProductionLockObservation(
        path="/run/lock/a-clockwork-plex-audio-route.lock",
        exists=False,
        held_by_caller=False,
        owner_uid=None,
        owner_gid=None,
        mode=None,
    ):
        raise CurrentPackageContractErrorV7(
            "live production lock differs from the accepted absent baseline"
        )
    if (
        report.approval.state is not ProductionApprovalBaselineStateV7.ABSENT
        or report.approval.present
    ):
        raise CurrentPackageContractErrorV7(
            "live approval differs from the accepted absent baseline"
        )
    if report.host_contract.payload is None:
        raise CurrentPackageContractErrorV7("live host contract is unavailable")
    validate_host_contract_against_accepted_v7(report.host_contract.payload)
    if report.services.payload is None or report.mixer.payload is None:
        raise CurrentPackageContractErrorV7(
            "live service or mixer snapshot is unavailable"
        )
    if report.loopback.payload is None or report.dac.payload is None:
        raise CurrentPackageContractErrorV7(
            "live loopback or DAC snapshot is unavailable"
        )
    validate_snapshot_payloads_against_accepted_v7(
        report.services.payload,
        report.mixer.payload,
        report.loopback.payload,
        report.dac.payload,
    )


def validate_host_contract_against_accepted_v7(
    host: HostContractSnapshot,
) -> None:
    if not isinstance(host, HostContractSnapshot):
        raise TypeError("host contract comparison requires HostContractSnapshot")
    # HostContractSnapshot validates the exact service, mixer, loopback and DAC
    # contract in its own frozen dataclass invariant.


def validate_snapshot_payloads_against_accepted_v7(
    services: ServiceSnapshot,
    mixer: MixerSnapshot,
    loopback: LoopbackSnapshot,
    dac: DacSnapshot,
) -> None:
    expected_services = {
        ServiceUnit.PLEXAMP: (
            ServiceLoadState.LOADED,
            ServiceActiveState.ACTIVE,
            ServiceEnableState.ENABLED,
        ),
        ServiceUnit.SHAIRPORT_SYNC: (
            ServiceLoadState.LOADED,
            ServiceActiveState.ACTIVE,
            ServiceEnableState.ENABLED,
        ),
        ServiceUnit.DASHBOARD: (
            ServiceLoadState.LOADED,
            ServiceActiveState.ACTIVE,
            ServiceEnableState.ENABLED,
        ),
        ServiceUnit.ROUTE_AUTHORITY: (
            ServiceLoadState.NOT_FOUND,
            ServiceActiveState.INACTIVE,
            ServiceEnableState.NOT_FOUND,
        ),
        ServiceUnit.CAMILLADSP: (
            ServiceLoadState.NOT_FOUND,
            ServiceActiveState.INACTIVE,
            ServiceEnableState.NOT_FOUND,
        ),
        ServiceUnit.AUDIO_FAILBACK: (
            ServiceLoadState.NOT_FOUND,
            ServiceActiveState.INACTIVE,
            ServiceEnableState.NOT_FOUND,
        ),
    }
    observed_services = {
        state.unit: (state.load, state.active, state.enabled)
        for state in services.services
    }
    if observed_services != expected_services:
        raise CurrentPackageContractErrorV7(
            "live service snapshot differs from the accepted baseline"
        )
    if (
        mixer.plexamp_output,
        mixer.airplay_output,
        mixer.music_master,
        mixer.maximum_alarm_volume,
    ) != EXPECTED_MIXER_VALUES:
        raise CurrentPackageContractErrorV7(
            "live mixer snapshot differs from the accepted baseline"
        )
    if not loopback.loaded:
        raise CurrentPackageContractErrorV7(
            "live loopback is not loaded as accepted"
        )
    if dac.released or not any(
        owner.user == EXPECTED_DAC_OWNER[0]
        and owner.command == EXPECTED_DAC_OWNER[1]
        and owner.access == EXPECTED_DAC_OWNER[2]
        for owner in dac.owners
    ):
        raise CurrentPackageContractErrorV7(
            "live DAC ownership differs from the accepted Plexamp baseline"
        )
