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

from stage_c_package import runtime_templates, templates
from stage_c_package.core import create_lab_root, validate_host, validate_name, validate_package, write_manifest
from stage_c_package.templates import HostContract

PACKAGE_VERSION = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and validate the Stage C1 route package. There is no activation mode; "
            "no privileged, service, module, mixer or PCM operation is performed."
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


def main() -> int:
    args = parse_args()
    if shutil.which("aplay") is None:
        raise SystemExit("Required command not found: aplay")
    project_user = validate_name("project user", os.environ.get("PROJECT_USER", os.environ.get("USER", "")))
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
    required_dirs = (
        "etc/a-clockwork-plex/audio-routes",
        "etc/default",
        "etc/modules-load.d",
        "etc/modprobe.d",
        "etc/sudoers.d",
        "etc/systemd/system",
        "usr/local/bin",
        f"usr/local/lib/a-clockwork-plex/camilladsp-{contract.camilladsp_version}",
        "var/lib/a-clockwork-plex/split-bus",
    )
    for relative in required_dirs:
        path = rootfs / relative
        path.mkdir(parents=True, exist_ok=True)
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
    }
    templates_to_write = {
        "split": templates.split_route(contract),
        "direct": templates.direct_route(contract),
        "camilla_config": templates.camilladsp_config(contract),
        "defaults": templates.defaults(contract),
        "module_load": templates.module_load(),
        "module_options": templates.module_options(contract),
        "route_helper": runtime_templates.route_helper(),
        "sudoers": runtime_templates.sudoers(contract.project_user),
        "route_unit": runtime_templates.route_unit(),
        "camilla_unit": runtime_templates.camilladsp_unit(contract),
        "failback_unit": runtime_templates.failback_unit(),
    }
    for name, content in templates_to_write.items():
        mode = 0o755 if name == "route_helper" else 0o440 if name == "sudoers" else 0o644
        paths[name].write_text(content, encoding="utf-8")
        paths[name].chmod(mode)
    shutil.copy2(args.binary, paths["binary"])
    paths["binary"].chmod(0o755)

    validate_package(rootfs, lab, paths, version, contract)
    manifest = lab / "manifest.tsv"
    results = lab / "results.tsv"
    write_manifest(rootfs, manifest, results)
    file_count = sum(1 for p in rootfs.rglob("*") if p.is_file())
    report = lab / "report.txt"
    report.write_text(
        f"""A Clockwork Plex Stage C1 prepare-only route package
Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}
Package version: {PACKAGE_VERSION}
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

Safety state:
- no activation option exists
- no sudo command was invoked
- no production path was written
- no module was loaded or unloaded
- no service was started, stopped, restarted, enabled or disabled
- no PCM was opened
- no mixer value was changed
- supplied laboratory roots must be empty
- generated route mutation actions return exit 78
- generated units require an absent activation-approved marker
- package contains no Python cache, symlink or special filesystem object
- manifest records required empty directories as well as files
""",
        encoding="utf-8",
    )
    print(
        f"""
A Clockwork Plex Stage C1 route package prepared and validated.

  Directory:  {lab}
  Rootfs:     {rootfs}
  Manifest:   {manifest}
  Results:    {results}
  Report:     {report}

The package contains candidate split-bus and direct-failback ALSA routes,
CamillaDSP configuration, deterministic snd_aloop persistence, staged verified
binary, read-only route helper, restricted sudoers and three guarded systemd
units.

No activation path exists in this script. Generated mutation actions remain
blocked, and every generated unit requires an approval marker that is absent.
The manifest includes both files and required directories, with no cache files.
Review the generated files before transaction code is added.
""".strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
