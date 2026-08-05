#!/usr/bin/python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_SCRIPTS = SCRIPT_DIR.parent
if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))

from stage_c_activation_package import runtime_templates
from stage_c_activation_package.core import (
    RUNTIME_MODULES,
    create_lab_root,
    package_fingerprint,
    package_rows,
    validate_package,
    write_manifest,
)
from stage_c_package import templates
from stage_c_package.core import validate_host, validate_name
from stage_c_package.templates import HostContract


PACKAGE_VERSION = 1
AUTHORITY_SOURCE = REPO_SCRIPTS / "stage_c_runtime_authority"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and validate the separately versioned Stage C21 runtime-authority package. "
            "The generator has no install or activation mode and performs no privileged, service, "
            "module, mixer or PCM mutation."
        )
    )
    parser.add_argument("--binary", required=True, type=Path, help="Verified CamillaDSP 4.1.3 executable")
    parser.add_argument("--lab-root", type=Path, help="New or existing empty laboratory directory")
    return parser.parse_args()


def env_nonnegative_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid {name}: {raw}") from exc
    if value < 0:
        raise SystemExit(f"Invalid {name}: {raw}")
    return value


def write_text(path: Path, content: str, mode: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def main() -> int:
    args = parse_args()
    if shutil.which("aplay") is None:
        raise SystemExit("Required command not found: aplay")
    project_user = validate_name(
        "project user",
        os.environ.get("PROJECT_USER", os.environ.get("USER", "")),
    )
    contract = HostContract(
        project_user=project_user,
        dac_card=validate_name("DAC card", os.environ.get("DAC_CARD", "Pro")),
        dac_device=env_nonnegative_int("DAC_DEVICE", 0),
        loopback_index=env_nonnegative_int("LOOPBACK_INDEX", 7),
        loopback_id=validate_name("loopback ID", os.environ.get("LOOPBACK_ID", "ACP_Loopback")),
    )
    version = validate_host(args.binary, contract)
    lab = create_lab_root(args.lab_root)
    rootfs = lab / "rootfs"
    runtime_parent = rootfs / "usr/local/lib/a-clockwork-plex/runtime-authority"
    runtime_package = runtime_parent / "stage_c_runtime_authority"
    required_dirs = (
        rootfs / "etc/a-clockwork-plex/audio-routes",
        rootfs / "etc/default",
        rootfs / "etc/modules-load.d",
        rootfs / "etc/modprobe.d",
        rootfs / "etc/sudoers.d",
        rootfs / "etc/systemd/system",
        rootfs / "usr/local/bin",
        rootfs / f"usr/local/lib/a-clockwork-plex/camilladsp-{contract.camilladsp_version}",
        runtime_package,
        rootfs / "var/lib/a-clockwork-plex/split-bus",
    )
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    for directory in (rootfs, *rootfs.rglob("*")):
        if directory.is_dir():
            directory.chmod(0o755)

    paths = {
        "split": rootfs / "etc/a-clockwork-plex/audio-routes/split-bus.conf",
        "direct": rootfs / "etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf",
        "camilla_config": rootfs / "etc/a-clockwork-plex/camilladsp-split-bus.yml",
        "defaults": rootfs / "etc/default/a-clockwork-plex-split-bus",
        "module_load": rootfs / "etc/modules-load.d/a-clockwork-plex-aloop.conf",
        "module_options": rootfs / "etc/modprobe.d/a-clockwork-plex-aloop.conf",
        "route_helper": rootfs / "usr/local/bin/a-clockwork-plex-audio-route",
        "sudoers": rootfs / "etc/sudoers.d/a-clockwork-plex-audio-route",
        "route_unit": rootfs / "etc/systemd/system/a-clockwork-plex-audio-route.service",
        "camilla_unit": rootfs / "etc/systemd/system/a-clockwork-plex-camilladsp.service",
        "failback_unit": rootfs / "etc/systemd/system/a-clockwork-plex-audio-failback.service",
        "binary": rootfs / f"usr/local/lib/a-clockwork-plex/camilladsp-{contract.camilladsp_version}/camilladsp",
        "runtime_package": runtime_package,
        "package_entry": runtime_package / "package_entry.py",
        "package_contract": runtime_parent / "package-contract.json",
    }

    templates_to_write = {
        "split": (templates.split_route(contract), 0o644),
        "direct": (templates.direct_route(contract), 0o644),
        "camilla_config": (templates.camilladsp_config(contract), 0o644),
        "defaults": (runtime_templates.defaults(contract), 0o644),
        "module_load": (templates.module_load(), 0o644),
        "module_options": (templates.module_options(contract), 0o644),
        "route_helper": (runtime_templates.route_launcher(), 0o755),
        "sudoers": (runtime_templates.sudoers(contract.project_user), 0o440),
        "route_unit": (runtime_templates.route_unit(), 0o644),
        "camilla_unit": (runtime_templates.camilladsp_unit(contract), 0o644),
        "failback_unit": (runtime_templates.failback_unit(), 0o644),
        "package_entry": (runtime_templates.package_entry(), 0o644),
    }
    for name, (content, mode) in templates_to_write.items():
        write_text(paths[name], content, mode)

    for module_name in RUNTIME_MODULES:
        source = AUTHORITY_SOURCE / module_name
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"Runtime authority source is unavailable: {source}")
        destination = runtime_package / module_name
        shutil.copy2(source, destination)
        destination.chmod(0o644)

    shutil.copy2(args.binary, paths["binary"])
    paths["binary"].chmod(0o755)

    rows = package_rows(rootfs, exclude={paths["package_contract"]})
    fingerprint = package_fingerprint(rows)
    write_text(
        paths["package_contract"],
        runtime_templates.contract_json(
            package_fingerprint=fingerprint,
            files=rows,
        ),
        0o644,
    )

    validate_package(rootfs, lab, paths, version, contract)
    manifest = lab / "manifest.tsv"
    results = lab / "results.tsv"
    write_manifest(rootfs, manifest, results)
    file_count = sum(1 for path in rootfs.rglob("*") if path.is_file())
    report = lab / "report.txt"
    report.write_text(
        f"""A Clockwork Plex Stage C21 runtime-authority package review
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Package version: {PACKAGE_VERSION}
Package phase: stage-c21-adapter-pending-review
Package fingerprint: {fingerprint}
Host: {platform.node()}
Architecture: {platform.machine()}
Laboratory: {lab}
Rootfs candidate: {rootfs}
Verified CamillaDSP: {version}
Verified binary SHA-256: {contract.camilladsp_sha256}
Verified pre-Stage-C ALSA SHA-256: {contract.pre_stage_c_alsa_sha256}
Loopback: index {contract.loopback_index}, ID {contract.loopback_id}, substreams 2, pcm_notify 1
DAC: hw:CARD={contract.dac_card},DEV={contract.dac_device}
Format: {contract.sample_rate} Hz / {contract.sample_format} / period {contract.period_size} / buffer {contract.buffer_size}
Package files: {file_count}

Runtime structure:
- Stage C1 remains immutable historical input
- Stage C21 core and supervisor model are vendored as exact source files
- route preparation remains a oneshot authority
- the CamillaDSP unit is a Type=notify supervisor gate
- application services remain ordered behind that supervisor
- the package entry has fixed runtime action names
- the production host adapter is deliberately absent and all mutation actions return exit 78

Safety state:
- no installer or activation option exists in this generator
- no sudo command was invoked
- no production path was written
- no module was loaded or unloaded
- no service was started, stopped, restarted, enabled or disabled
- no PCM was opened
- no mixer value was changed
- supplied laboratory roots must be empty
- package contains no Python cache, symlink or special filesystem object
- manifest records the complete separately versioned package
""",
        encoding="utf-8",
    )
    print(
        f"""
A Clockwork Plex Stage C21 runtime-authority package prepared and validated.

  Directory:    {lab}
  Rootfs:       {rootfs}
  Manifest:     {manifest}
  Results:      {results}
  Report:       {report}
  Fingerprint:  {fingerprint}

This is a separately versioned review package. It contains the Stage C21 core,
structured approval store, supervised readiness model and corrected three-unit
systemd graph. The production host adapter is not present yet, so every
route-changing action remains blocked with exit 78.

No production path, service, ALSA route, mixer or PCM was changed.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
