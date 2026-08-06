#!/usr/bin/python3
from __future__ import annotations

"""Read-only identity freeze for the accepted Stage C23 evidence tree.

This module has no host mutation, sudo, lock, transaction, service, DAC,
systemd or production-file interface. It accepts only the exact retained
Stage C23 physical-evidence root, verifies the already frozen manifest digest
and rehearsal contract, and prints the manifest shape needed by Stage C24.
"""

import os
import stat
from pathlib import Path

from .current_package_contract_v7 import ACCEPTED_PACKAGE_FINGERPRINT
from .current_package_managed_file_rollback_rehearsal_v9 import (
    EXPECTED_CHECKS as STAGE_C23_EXPECTED_CHECKS,
)
from .package_review import sha256
from .production_plan import _validate_evidence_manifest
from .sandbox_transaction import _assert_regular_tree, _read_tsv


ACCEPTED_STAGE_C23_ROOT = Path(
    "/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG"
)
ACCEPTED_PACKAGE_ROOT = Path(
    "/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo"
)
ACCEPTED_BASELINE_ROOT = Path(
    "/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac"
)
ACCEPTED_STAGE_C21_ROOT = Path(
    "/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg"
)
ACCEPTED_STAGE_C22_ROOT = Path(
    "/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL"
)
ACCEPTED_STAGE_C22_MANIFEST_SHA256 = (
    "4720c6d2dd99080abbde5b9d34b4862ecd0cb0c62b44262fd695c40de7c169eb"
)
ACCEPTED_STAGE_C23_MANIFEST_SHA256 = (
    "e51bac4fb54357c5b30a31152af1309f484b5f2a82c0d2e9e9a866f64432466a"
)
ACCEPTED_STAGE_C23_MANIFEST_ROWS = 144

REPORT_MARKERS = (
    "Current package files installed and removed: 28",
    "Current package payload files: 27",
    "Ordinary blocked operations: 11",
    "Approval operations exposed by rehearsal: 0",
    "Approval operations blocked: 4",
    "Final transaction state: current-package-managed-files-rolled-back-and-closed",
    "Systemd reloaded: false",
    "Route selected: false",
    "CamillaDSP started: false",
    "Committed: false",
    "Persistent Stage C activation remains blocked.",
)


def _rows_by_key(path: Path, key: str, value: str) -> dict[str, str]:
    return {
        row.get(key, ""): row.get(value, "")
        for row in _read_tsv(path)
    }


def validate_results(rows: list[dict[str, str]]) -> None:
    observed = tuple(row.get("check", "") for row in rows)
    if observed != STAGE_C23_EXPECTED_CHECKS:
        raise SystemExit("Stage C23 evidence does not contain the exact 47 checks")
    if any(row.get("result", "") != "PASS" for row in rows):
        raise SystemExit("Stage C23 evidence contains a non-PASS result")


def validate_input_binding(binding: dict[str, str]) -> None:
    expected = {
        "package_root": str(ACCEPTED_PACKAGE_ROOT),
        "package_fingerprint": ACCEPTED_PACKAGE_FINGERPRINT,
        "baseline_root": str(ACCEPTED_BASELINE_ROOT),
        "stage_c21_root": str(ACCEPTED_STAGE_C21_ROOT),
        "stage_c22_root": str(ACCEPTED_STAGE_C22_ROOT),
        "stage_c22_manifest_sha256": ACCEPTED_STAGE_C22_MANIFEST_SHA256,
        "stage_c22_manifest_rows": "140",
        "stage_c22_manifest_entries": "139",
        "package_files": "28",
        "package_payload_files": "27",
    }
    for item, value in expected.items():
        if binding.get(item) != value:
            raise SystemExit(f"Stage C23 input binding changed: {item}")


def validate_identity(identity: dict[str, str]) -> None:
    expected = {
        "action": "install",
        "package_sha256": ACCEPTED_PACKAGE_FINGERPRINT,
        "host": "plexamp-bedroom",
        "architecture": "aarch64",
        "invoking_user": "andy",
        "caller_supplied": "false",
        "mutation_started": "true",
        "managed_files_installed": "true",
        "filesystem_restored": "true",
        "services_restored": "true",
        "systemd_reloaded": "false",
        "route_selected": "false",
        "committed": "false",
        "reusable_for_activation": "false",
        "reusable_for_rollback": "false",
    }
    for item, value in expected.items():
        if identity.get(item) != value:
            raise SystemExit(f"Stage C23 identity changed: {item}")

    transaction = identity.get("transaction", "")
    snapshot = identity.get("snapshot", "")
    lease = identity.get("lease_id", "")
    if not transaction.startswith("stage-c23-managed-file-rollback-install-"):
        raise SystemExit("Stage C23 transaction identity changed")
    if not snapshot.startswith("stage-c23-managed-file-rollback-snapshot-"):
        raise SystemExit("Stage C23 snapshot identity changed")
    if not lease.startswith("stage-c14-lock-"):
        raise SystemExit("Stage C23 production-lock lease identity changed")


def validate_blocked_boundaries(root: Path) -> None:
    blocked = _read_tsv(root / "blocked-operations.tsv")
    if len(blocked) != 11 or any(
        row.get("state", "") != "blocked" for row in blocked
    ):
        raise SystemExit("Stage C23 ordinary blocked-operation evidence changed")

    approvals = _read_tsv(root / "approval-operations.tsv")
    if len(approvals) != 4 or any(
        row.get("state", "") != "blocked" for row in approvals
    ):
        raise SystemExit("Stage C23 approval boundary evidence changed")


def validate_report(report: str) -> None:
    for marker in REPORT_MARKERS:
        if marker not in report:
            raise SystemExit(f"Stage C23 report contract is missing: {marker}")


def inspect_stage_c23_evidence(
    root: Path = ACCEPTED_STAGE_C23_ROOT,
) -> dict[str, str | int]:
    resolved = root.resolve()
    if resolved != ACCEPTED_STAGE_C23_ROOT:
        raise SystemExit(
            "Stage C23 identity freeze accepts only the exact retained evidence root"
        )
    if resolved.parent != Path("/var/tmp"):
        raise SystemExit("Stage C23 evidence must remain directly under /var/tmp")

    try:
        info = resolved.lstat()
    except FileNotFoundError as exc:
        raise SystemExit("accepted Stage C23 evidence root is unavailable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise SystemExit("Stage C23 evidence root is not a directory")
    if info.st_uid != os.getuid():
        raise SystemExit("Stage C23 evidence root is not owned by the invoking user")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("Stage C23 evidence root must retain mode 0700")

    _assert_regular_tree(resolved, "accepted Stage C23 evidence")
    _validate_evidence_manifest(resolved, "Stage C23")

    manifest = resolved / "evidence-manifest.tsv"
    if sha256(manifest) != ACCEPTED_STAGE_C23_MANIFEST_SHA256:
        raise SystemExit("Stage C23 accepted evidence-manifest digest changed")
    manifest_rows = sum(1 for _ in manifest.open("r", encoding="utf-8"))
    if manifest_rows != ACCEPTED_STAGE_C23_MANIFEST_ROWS:
        raise SystemExit("Stage C23 accepted evidence-manifest row count changed")

    results = _read_tsv(resolved / "results.tsv")
    validate_results(results)
    binding = _rows_by_key(resolved / "input-binding.tsv", "item", "value")
    validate_input_binding(binding)
    identity = _rows_by_key(resolved / "identity.tsv", "item", "value")
    validate_identity(identity)
    validate_blocked_boundaries(resolved)
    validate_report((resolved / "report.txt").read_text(encoding="utf-8"))

    for name in ("candidate-review-copy", "transaction-rehearsal-copy"):
        if not (resolved / name).is_dir():
            raise SystemExit(f"Stage C23 review evidence is missing: {name}")

    manifest_entries = len(_read_tsv(manifest))
    return {
        "root": str(resolved),
        "manifest_sha256": sha256(manifest),
        "manifest_rows": manifest_rows,
        "manifest_entries": manifest_entries,
        "results_checks": len(results),
        "results_pass": sum(
            1 for row in results if row.get("result", "") == "PASS"
        ),
        "transaction": identity["transaction"],
        "snapshot": identity["snapshot"],
        "lease_id": identity["lease_id"],
    }


def main() -> int:
    identity = inspect_stage_c23_evidence()
    print("STAGE_C23_EVIDENCE_IDENTITY=PASS")
    for key in (
        "root",
        "manifest_sha256",
        "manifest_rows",
        "manifest_entries",
        "results_checks",
        "results_pass",
        "transaction",
        "snapshot",
        "lease_id",
    ):
        print(f"{key}={identity[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())