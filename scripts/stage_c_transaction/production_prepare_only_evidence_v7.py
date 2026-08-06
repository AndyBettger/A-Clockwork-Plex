#!/usr/bin/python3
from __future__ import annotations

"""Durable read-only evidence for the Stage C21 production baseline inspector.

The only writes in this module are three new mode-0600 evidence files beneath
one fresh current-user-owned mode-0700 directory in /var/tmp. It has no
production lock, approval, transaction, service, process, route, mixer, PCM,
DAC, CamillaDSP, install or activation capability.
"""

import argparse
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .production_adapter_contract import (
    AdapterResult,
    AdapterStatus,
    DacContract,
    DacSnapshot,
    HostContractSnapshot,
    LoopbackContract,
    LoopbackSnapshot,
    MixerSnapshot,
    PackageFingerprint,
    ProductionLockObservation,
    ServiceSnapshot,
)
from .production_prepare_only_inspector_v7 import (
    ProductionApprovalBaselineObservationV7,
    ProductionPrepareOnlyDispositionV7,
    ProductionPrepareOnlyInspectorV7,
    ProductionPrepareOnlyReportV7,
)
from .read_only_host_adapter import ReadOnlyHostProductionAdapter


REVIEW_PARENT = "/var/tmp"
REVIEW_PREFIX = "a-clockwork-plex-stage-c21-production-baseline."
REPORT_JSON_NAME = "report.json"
REPORT_TEXT_NAME = "report.txt"
MANIFEST_JSON_NAME = "manifest.json"
REPORT_SCHEMA = "a-clockwork-plex.stage-c21.production-prepare-only-report.v1"
MANIFEST_SCHEMA = "a-clockwork-plex.stage-c21.production-prepare-only-manifest.v1"
ROOT_MODE = 0o700
FILE_MODE = 0o600


class ProductionPrepareOnlyEvidenceErrorV7(RuntimeError):
    """Raised without deleting an incomplete review root."""


@dataclass(frozen=True)
class PublishedEvidenceFileV7:
    name: str
    path: str
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if self.name not in {
            REPORT_JSON_NAME,
            REPORT_TEXT_NAME,
            MANIFEST_JSON_NAME,
        }:
            raise ValueError("evidence file uses an unexpected fixed name")
        expected = str(Path(self.path).parent / self.name)
        if self.path != expected:
            raise ValueError("evidence file path and name differ")
        if not _is_sha256(self.sha256):
            raise ValueError("evidence file digest must be a lowercase SHA-256")
        if self.byte_length <= 0:
            raise ValueError("evidence file must be non-empty")


@dataclass(frozen=True)
class ProductionPrepareOnlyEvidenceBundleV7:
    root: str
    disposition: ProductionPrepareOnlyDispositionV7
    candidate_package: PackageFingerprint
    report_json: PublishedEvidenceFileV7
    report_text: PublishedEvidenceFileV7
    manifest_json: PublishedEvidenceFileV7
    complete: bool = True
    production_mutation_authorised: bool = False
    activation_authorised: bool = False
    pi_execution_authorised: bool = False
    production_lock_acquired: bool = False
    transaction_created: bool = False

    def __post_init__(self) -> None:
        root = Path(self.root)
        if root.parent != Path(REVIEW_PARENT) or not root.name.startswith(REVIEW_PREFIX):
            raise ValueError("evidence bundle root is outside the fixed review scope")
        if not self.complete:
            raise ValueError("returned evidence bundle must be complete")
        for flag in (
            self.production_mutation_authorised,
            self.activation_authorised,
            self.pi_execution_authorised,
            self.production_lock_acquired,
            self.transaction_created,
        ):
            if flag:
                raise ValueError("prepare-only evidence cannot grant authority")
        expected = {
            REPORT_JSON_NAME: self.report_json,
            REPORT_TEXT_NAME: self.report_text,
            MANIFEST_JSON_NAME: self.manifest_json,
        }
        for name, item in expected.items():
            if item.name != name or Path(item.path).parent != root:
                raise ValueError("evidence bundle file identity changed")


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _loopback_contract_payload(contract: LoopbackContract) -> dict[str, Any]:
    return {
        "module": contract.module,
        "card_index": contract.card_index,
        "card_id": contract.card_id,
        "pcm_substreams": contract.pcm_substreams,
        "pcm_notify": contract.pcm_notify,
    }


def _dac_contract_payload(contract: DacContract) -> dict[str, Any]:
    return {
        "sample_format": contract.sample_format,
        "channels": contract.channels,
        "rate": contract.rate,
        "period_size": contract.period_size,
        "buffer_size": contract.buffer_size,
    }


def _host_contract_payload(payload: HostContractSnapshot) -> dict[str, Any]:
    return {
        "service_units": [unit.value for unit in payload.service_units],
        "mixer_controls": [control.value for control in payload.mixer_controls],
        "loopback": _loopback_contract_payload(payload.loopback),
        "dac": _dac_contract_payload(payload.dac),
    }


def _lock_payload(payload: ProductionLockObservation) -> dict[str, Any]:
    return {
        "path": payload.path,
        "exists": payload.exists,
        "held_by_caller": payload.held_by_caller,
        "owner_uid": payload.owner_uid,
        "owner_gid": payload.owner_gid,
        "mode": payload.mode,
    }


def _service_payload(payload: ServiceSnapshot) -> dict[str, Any]:
    return {
        "services": [
            {
                "unit": service.unit.value,
                "load": service.load.value,
                "active": service.active.value,
                "enabled": service.enabled.value,
            }
            for service in payload.services
        ]
    }


def _mixer_payload(payload: MixerSnapshot) -> dict[str, Any]:
    return {
        "plexamp_output": payload.plexamp_output,
        "airplay_output": payload.airplay_output,
        "music_master": payload.music_master,
        "maximum_alarm_volume": payload.maximum_alarm_volume,
    }


def _loopback_payload(payload: LoopbackSnapshot) -> dict[str, Any]:
    return {
        "contract": _loopback_contract_payload(payload.contract),
        "loaded": payload.loaded,
    }


def _dac_payload(payload: DacSnapshot) -> dict[str, Any]:
    return {
        "contract": _dac_contract_payload(payload.contract),
        "owners": [
            {
                "pid": owner.pid,
                "user": owner.user,
                "command": owner.command,
                "access": owner.access,
            }
            for owner in payload.owners
        ],
        "released": payload.released,
    }


def _adapter_result_payload(
    result: AdapterResult[Any],
    serializer: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    payload = None
    if result.status is AdapterStatus.PASS:
        if result.payload is None:
            raise ValueError("successful adapter result has no payload")
        payload = serializer(result.payload)
    return {
        "operation": result.operation.value,
        "status": result.status.value,
        "detail": result.detail,
        "evidence": [
            {"key": key, "value": value} for key, value in result.evidence
        ],
        "payload": payload,
    }


def _approval_payload(
    approval: ProductionApprovalBaselineObservationV7,
) -> dict[str, Any]:
    return {
        "state": approval.state.value,
        "detail": approval.detail,
        "approval_path": approval.approval_path,
        "present": approval.present,
        "canonical_record": approval.canonical_record,
        "raw_sha256": approval.raw_sha256,
        "device": approval.device,
        "inode": approval.inode,
        "mode": approval.mode,
        "owner_uid": approval.owner_uid,
        "owner_gid": approval.owner_gid,
        "link_count": approval.link_count,
        "size": approval.size,
        "phase": approval.phase.value if approval.phase is not None else None,
        "transaction_id": approval.transaction_id,
        "lock_lease_id": approval.lock_lease_id,
        "package_fingerprint": approval.package_fingerprint,
        "record_sha256": approval.record_sha256,
    }


def production_prepare_only_report_payload_v7(
    report: ProductionPrepareOnlyReportV7,
) -> dict[str, Any]:
    if not isinstance(report, ProductionPrepareOnlyReportV7):
        raise TypeError("evidence renderer requires ProductionPrepareOnlyReportV7")
    return {
        "schema": REPORT_SCHEMA,
        "status": report.status.value,
        "disposition": report.disposition.value,
        "detail": report.detail,
        "candidate_package": {"sha256": report.candidate_package.sha256},
        "observations": {
            "host_contract": _adapter_result_payload(
                report.host_contract, _host_contract_payload
            ),
            "production_lock": _adapter_result_payload(
                report.production_lock, _lock_payload
            ),
            "services": _adapter_result_payload(report.services, _service_payload),
            "mixer": _adapter_result_payload(report.mixer, _mixer_payload),
            "loopback": _adapter_result_payload(
                report.loopback, _loopback_payload
            ),
            "dac": _adapter_result_payload(report.dac, _dac_payload),
            "approval": _approval_payload(report.approval),
        },
        "authority": {
            "production_mutation_authorised": report.production_mutation_authorised,
            "activation_authorised": report.activation_authorised,
            "pi_execution_authorised": report.pi_execution_authorised,
            "review_bundle_persisted": report.review_bundle_persisted,
            "production_lock_acquired": report.production_lock_acquired,
            "transaction_created": report.transaction_created,
        },
    }


def production_prepare_only_report_json_v7(
    report: ProductionPrepareOnlyReportV7,
) -> bytes:
    return _canonical_json_bytes(production_prepare_only_report_payload_v7(report))


def _append_result_text(
    lines: list[str],
    label: str,
    result: AdapterResult[Any],
) -> None:
    lines.extend(
        (
            f"{label}",
            f"  operation: {result.operation.value}",
            f"  status: {result.status.value}",
            f"  detail: {result.detail}",
        )
    )
    if result.evidence:
        lines.append("  evidence:")
        lines.extend(f"    {key}: {value}" for key, value in result.evidence)
    else:
        lines.append("  evidence: none")


def production_prepare_only_report_text_v7(
    report: ProductionPrepareOnlyReportV7,
) -> bytes:
    if not isinstance(report, ProductionPrepareOnlyReportV7):
        raise TypeError("evidence renderer requires ProductionPrepareOnlyReportV7")

    lines = [
        "A Clockwork Plex Stage C21 production baseline review",
        "REVIEW ONLY — NO INSTALLATION OR ACTIVATION AUTHORITY",
        "",
        f"Status: {report.status.value}",
        f"Disposition: {report.disposition.value}",
        f"Detail: {report.detail}",
        f"Candidate package SHA-256: {report.candidate_package.sha256}",
        "",
        "Host observations",
        "-----------------",
    ]
    _append_result_text(lines, "Host contract", report.host_contract)
    _append_result_text(lines, "Production lock", report.production_lock)
    _append_result_text(lines, "Services", report.services)
    _append_result_text(lines, "Mixer", report.mixer)
    _append_result_text(lines, "Loopback", report.loopback)
    _append_result_text(lines, "DAC", report.dac)

    lines.extend(("", "Typed payloads", "--------------"))
    if report.host_contract.payload is not None:
        host = report.host_contract.payload
        lines.append(
            "Service units: " + ", ".join(unit.value for unit in host.service_units)
        )
        lines.append(
            "Mixer controls: "
            + ", ".join(control.value for control in host.mixer_controls)
        )
    if report.production_lock.payload is not None:
        lock = report.production_lock.payload
        lines.extend(
            (
                f"Production lock path: {lock.path}",
                f"Production lock exists: {str(lock.exists).lower()}",
                f"Production lock held by caller: {str(lock.held_by_caller).lower()}",
                f"Production lock owner: {lock.owner_uid}:{lock.owner_gid}",
                f"Production lock mode: {lock.mode}",
            )
        )
    if report.services.payload is not None:
        lines.append("Services:")
        lines.extend(
            (
                f"  {service.unit.value}: load={service.load.value}, "
                f"active={service.active.value}, enabled={service.enabled.value}"
            )
            for service in report.services.payload.services
        )
    if report.mixer.payload is not None:
        mixer = report.mixer.payload
        lines.extend(
            (
                f"Plexamp Output: {mixer.plexamp_output}",
                f"AirPlay Output: {mixer.airplay_output}",
                f"Music Master: {mixer.music_master}",
                f"Maximum Alarm Volume: {mixer.maximum_alarm_volume}",
            )
        )
    if report.loopback.payload is not None:
        loopback = report.loopback.payload
        lines.extend(
            (
                f"Loopback loaded: {str(loopback.loaded).lower()}",
                f"Loopback card: {loopback.contract.card_index} / {loopback.contract.card_id}",
                f"Loopback substreams: {loopback.contract.pcm_substreams}",
                f"Loopback pcm_notify: {loopback.contract.pcm_notify}",
            )
        )
    if report.dac.payload is not None:
        dac = report.dac.payload
        lines.extend(
            (
                f"DAC released: {str(dac.released).lower()}",
                f"DAC format: {dac.contract.sample_format}",
                f"DAC geometry: {dac.contract.channels} channels / {dac.contract.rate} Hz / "
                f"period {dac.contract.period_size} / buffer {dac.contract.buffer_size}",
                f"DAC owners: {len(dac.owners)}",
            )
        )
        lines.extend(
            f"  pid={owner.pid} user={owner.user} command={owner.command} access={owner.access}"
            for owner in dac.owners
        )

    approval = report.approval
    lines.extend(
        (
            "",
            "Approval observation",
            "--------------------",
            f"State: {approval.state.value}",
            f"Detail: {approval.detail}",
            f"Path: {approval.approval_path}",
            f"Present: {str(approval.present).lower()}",
            f"Canonical record: {str(approval.canonical_record).lower()}",
            f"Raw SHA-256: {approval.raw_sha256}",
            f"Device/inode: {approval.device}/{approval.inode}",
            f"Mode/owner/links/size: {approval.mode} / {approval.owner_uid}:{approval.owner_gid} / "
            f"{approval.link_count} / {approval.size}",
            f"Phase: {approval.phase.value if approval.phase is not None else None}",
            f"Transaction ID: {approval.transaction_id}",
            f"Lock lease ID: {approval.lock_lease_id}",
            f"Package fingerprint: {approval.package_fingerprint}",
            f"Record SHA-256: {approval.record_sha256}",
            "",
            "Authority",
            "---------",
            f"production_mutation_authorised: {str(report.production_mutation_authorised).lower()}",
            f"activation_authorised: {str(report.activation_authorised).lower()}",
            f"pi_execution_authorised: {str(report.pi_execution_authorised).lower()}",
            f"review_bundle_persisted: {str(report.review_bundle_persisted).lower()}",
            f"production_lock_acquired: {str(report.production_lock_acquired).lower()}",
            f"transaction_created: {str(report.transaction_created).lower()}",
            "",
            "This evidence does not authorise installation, activation or Pi execution.",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _root_identity(path: str, directory_fd: int) -> tuple[int, int]:
    path_info = os.lstat(path)
    fd_info = os.fstat(directory_fd)
    if not stat.S_ISDIR(path_info.st_mode) or not stat.S_ISDIR(fd_info.st_mode):
        raise ProductionPrepareOnlyEvidenceErrorV7("review root is not a directory")
    if (path_info.st_dev, path_info.st_ino) != (fd_info.st_dev, fd_info.st_ino):
        raise ProductionPrepareOnlyEvidenceErrorV7("review root identity changed")
    if stat.S_IMODE(fd_info.st_mode) != ROOT_MODE:
        raise ProductionPrepareOnlyEvidenceErrorV7("review root mode changed")
    if fd_info.st_uid != os.geteuid() or fd_info.st_gid != os.getegid():
        raise ProductionPrepareOnlyEvidenceErrorV7("review root ownership changed")
    return fd_info.st_dev, fd_info.st_ino


def _verify_root_identity(
    path: str,
    directory_fd: int,
    expected: tuple[int, int],
) -> None:
    if _root_identity(path, directory_fd) != expected:
        raise ProductionPrepareOnlyEvidenceErrorV7("review root was substituted")


def _write_all(file_fd: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(file_fd, content[offset:])
        if written <= 0:
            raise ProductionPrepareOnlyEvidenceErrorV7("short evidence write")
        offset += written


def _publish_file(
    *,
    root: str,
    directory_fd: int,
    root_identity: tuple[int, int],
    name: str,
    content: bytes,
) -> PublishedEvidenceFileV7:
    _verify_root_identity(root, directory_fd, root_identity)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | os.O_CLOEXEC
    )
    file_fd = os.open(name, flags, FILE_MODE, dir_fd=directory_fd)
    try:
        os.fchmod(file_fd, FILE_MODE)
        opened = os.fstat(file_fd)
        path_info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(opened.st_mode):
            raise ProductionPrepareOnlyEvidenceErrorV7("evidence object is not regular")
        if (opened.st_dev, opened.st_ino) != (path_info.st_dev, path_info.st_ino):
            raise ProductionPrepareOnlyEvidenceErrorV7("evidence file identity changed")
        if (
            stat.S_IMODE(opened.st_mode) != FILE_MODE
            or opened.st_uid != os.geteuid()
            or opened.st_gid != os.getegid()
            or opened.st_nlink != 1
            or opened.st_size != 0
        ):
            raise ProductionPrepareOnlyEvidenceErrorV7(
                "new evidence file metadata differs"
            )
        _write_all(file_fd, content)
        os.fsync(file_fd)
        closed_shape = os.fstat(file_fd)
        path_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (closed_shape.st_dev, closed_shape.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ) or (path_after.st_dev, path_after.st_ino) != (
            opened.st_dev,
            opened.st_ino,
        ):
            raise ProductionPrepareOnlyEvidenceErrorV7(
                "evidence file was substituted during publication"
            )
        if closed_shape.st_size != len(content):
            raise ProductionPrepareOnlyEvidenceErrorV7(
                "evidence file length differs after publication"
            )
    finally:
        os.close(file_fd)
    os.fsync(directory_fd)
    _verify_root_identity(root, directory_fd, root_identity)
    return PublishedEvidenceFileV7(
        name=name,
        path=str(Path(root) / name),
        sha256=hashlib.sha256(content).hexdigest(),
        byte_length=len(content),
    )


def _manifest_payload(
    report: ProductionPrepareOnlyReportV7,
    report_json: PublishedEvidenceFileV7,
    report_text: PublishedEvidenceFileV7,
) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "complete": True,
        "disposition": report.disposition.value,
        "candidate_package_sha256": report.candidate_package.sha256,
        "files": {
            REPORT_JSON_NAME: {
                "sha256": report_json.sha256,
                "bytes": report_json.byte_length,
            },
            REPORT_TEXT_NAME: {
                "sha256": report_text.sha256,
                "bytes": report_text.byte_length,
            },
        },
        "authority": {
            "production_mutation_authorised": False,
            "activation_authorised": False,
            "pi_execution_authorised": False,
            "production_lock_acquired": False,
            "transaction_created": False,
        },
    }


def publish_production_prepare_only_evidence_v7(
    report: ProductionPrepareOnlyReportV7,
) -> ProductionPrepareOnlyEvidenceBundleV7:
    if not isinstance(report, ProductionPrepareOnlyReportV7):
        raise TypeError("evidence renderer requires ProductionPrepareOnlyReportV7")

    root = tempfile.mkdtemp(prefix=REVIEW_PREFIX, dir=REVIEW_PARENT)
    try:
        os.chmod(root, ROOT_MODE, follow_symlinks=False)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        directory_fd = os.open(root, flags)
        try:
            root_identity = _root_identity(root, directory_fd)
            report_json_bytes = production_prepare_only_report_json_v7(report)
            report_text_bytes = production_prepare_only_report_text_v7(report)
            report_json = _publish_file(
                root=root,
                directory_fd=directory_fd,
                root_identity=root_identity,
                name=REPORT_JSON_NAME,
                content=report_json_bytes,
            )
            report_text = _publish_file(
                root=root,
                directory_fd=directory_fd,
                root_identity=root_identity,
                name=REPORT_TEXT_NAME,
                content=report_text_bytes,
            )
            manifest_bytes = _canonical_json_bytes(
                _manifest_payload(report, report_json, report_text)
            )
            manifest_json = _publish_file(
                root=root,
                directory_fd=directory_fd,
                root_identity=root_identity,
                name=MANIFEST_JSON_NAME,
                content=manifest_bytes,
            )
            _verify_root_identity(root, directory_fd, root_identity)
        finally:
            os.close(directory_fd)
    except BaseException as exc:
        raise ProductionPrepareOnlyEvidenceErrorV7(
            f"incomplete Stage C21 review evidence retained at {root}: {exc}"
        ) from exc

    return ProductionPrepareOnlyEvidenceBundleV7(
        root=root,
        disposition=report.disposition,
        candidate_package=report.candidate_package,
        report_json=report_json,
        report_text=report_text,
        manifest_json=manifest_json,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Observe the fixed Stage C21 production baseline and publish a "
            "read-only human-review bundle. This command cannot install or activate."
        )
    )
    parser.add_argument(
        "--package-fingerprint",
        required=True,
        help="Lowercase SHA-256 printed by the validated Stage C21 package generator",
    )
    return parser.parse_args(argv)


def run_production_prepare_only_evidence_v7(
    package_fingerprint: str,
) -> tuple[ProductionPrepareOnlyReportV7, ProductionPrepareOnlyEvidenceBundleV7]:
    package = PackageFingerprint(package_fingerprint)
    adapter = ReadOnlyHostProductionAdapter()
    report = ProductionPrepareOnlyInspectorV7(adapter, package).inspect()
    bundle = publish_production_prepare_only_evidence_v7(report)
    return report, bundle


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if os.geteuid() == 0:
        raise SystemExit(
            "Run the Stage C21 production baseline wrapper as the normal project user, not as root."
        )
    try:
        report, bundle = run_production_prepare_only_evidence_v7(
            args.package_fingerprint
        )
    except (TypeError, ValueError, ProductionPrepareOnlyEvidenceErrorV7) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Evidence bundle: {bundle.root}")
    print(f"Disposition: {report.disposition.value}")
    return 0 if report.ready_for_human_review else 1


if __name__ == "__main__":
    raise SystemExit(main())
