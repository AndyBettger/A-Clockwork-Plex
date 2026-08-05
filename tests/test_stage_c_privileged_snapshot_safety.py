from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_transaction.package_review import ManifestEntry
from scripts.stage_c_transaction.snapshot_core import (
    CURRENT_ALSA_DESTINATION,
    collect_filesystem_snapshot,
    write_evidence_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "test-stage-c-privileged-snapshot.sh"
ENGINE = ROOT / "scripts" / "stage_c_transaction" / "privileged_snapshot.py"
CORE = ROOT / "scripts" / "stage_c_transaction" / "snapshot_core.py"
TOKEN = "STAGE-C3-PRIVILEGED-SNAPSHOT-READ-ONLY"
PROTECTED_PATH = "/etc/sudoers.d/a-clockwork-plex-audio-route"


def combined_source() -> str:
    return ENGINE.read_text(encoding="utf-8") + "\n" + CORE.read_text(encoding="utf-8")


def tree_fingerprint(root: Path) -> list[tuple[str, str, int, str]]:
    rows: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        relative = str(path.relative_to(root))
        if stat.S_ISDIR(info.st_mode):
            rows.append((relative, "directory", stat.S_IMODE(info.st_mode), "-"))
        elif stat.S_ISLNK(info.st_mode):
            rows.append((relative, "symlink", stat.S_IMODE(info.st_mode), os.readlink(path)))
        elif stat.S_ISREG(info.st_mode):
            rows.append(
                (
                    relative,
                    "file",
                    stat.S_IMODE(info.st_mode),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        else:
            rows.append((relative, "special", stat.S_IMODE(info.st_mode), "-"))
    return rows


def fake_entries() -> list[ManifestEntry]:
    files = (
        "/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf",
        "/etc/a-clockwork-plex/audio-routes/split-bus.conf",
        "/etc/a-clockwork-plex/camilladsp-split-bus.yml",
        "/etc/default/a-clockwork-plex-split-bus",
        "/etc/modprobe.d/a-clockwork-plex-aloop.conf",
        "/etc/modules-load.d/a-clockwork-plex-aloop.conf",
        PROTECTED_PATH,
        "/etc/systemd/system/a-clockwork-plex-audio-failback.service",
        "/etc/systemd/system/a-clockwork-plex-audio-route.service",
        "/etc/systemd/system/a-clockwork-plex-camilladsp.service",
        "/usr/local/bin/a-clockwork-plex-audio-route",
        "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
    )
    directories = (
        "/etc",
        "/etc/a-clockwork-plex",
        "/etc/a-clockwork-plex/audio-routes",
        "/etc/default",
        "/etc/modprobe.d",
        "/etc/modules-load.d",
        "/etc/sudoers.d",
        "/etc/systemd/system",
        "/usr/local/bin",
        "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3",
        "/var/lib/a-clockwork-plex/split-bus",
    )
    return [
        *(ManifestEntry("directory", path, "755", "root:root", "-") for path in directories),
        *(ManifestEntry("file", path, "644", "root:root", "0" * 64) for path in files),
    ]


def create_fake_system_root(root: Path) -> None:
    current = root / CURRENT_ALSA_DESTINATION.lstrip("/")
    current.parent.mkdir(parents=True)
    current.write_text("physically validated direct route\n", encoding="utf-8")
    for destination in (
        "/etc/default",
        "/etc/modprobe.d",
        "/etc/modules-load.d",
        "/etc/sudoers.d",
        "/etc/systemd/system",
        "/usr/local/bin",
    ):
        (root / destination.lstrip("/")).mkdir(parents=True, exist_ok=True)


class StageCPrivilegedSnapshotSafetyTests(unittest.TestCase):
    def test_wrapper_and_python_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in (ENGINE, CORE):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_prepare_only_runs_without_sudo_or_architecture_gate(self):
        with tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c1-review-test.", dir="/var/tmp"
        ) as package_dir, tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c2-review-test.", dir="/var/tmp"
        ) as c2_dir:
            package = Path(package_dir)
            c2 = Path(c2_dir)
            (package / "rootfs").mkdir()
            (package / "manifest.tsv").write_text("placeholder\n", encoding="utf-8")
            (c2 / "results.tsv").write_text("placeholder\n", encoding="utf-8")
            (c2 / "report.txt").write_text("placeholder\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER),
                    "--package-root",
                    str(package),
                    "--stage-c2-root",
                    str(c2),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Prepare-only invoked no sudo", result.stdout)
        self.assertIn("--capture-read-only", result.stdout)
        self.assertIn(TOKEN, result.stdout)

    def test_wrapper_has_one_privileged_command_and_no_forbidden_case_branch(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"(?m)^\s*sudo\s+", text)), 1)
        self.assertIn("sudo env PYTHONDONTWRITEBYTECODE=1", text)
        self.assertIn("if [[ \"$MODE\" == prepare ]]", text)
        self.assertNotRegex(text, r"(?m)^\s*--activate\)")
        self.assertNotRegex(text, r"(?m)^\s*--install\)")
        self.assertNotRegex(text, r"(?m)^\s*--rollback\)")
        self.assertNotRegex(text, r"(?m)^\s*--uninstall\)")

    def test_engine_cli_and_confirmation_are_snapshot_only(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            'parser.add_argument("--package-root"',
            'parser.add_argument("--stage-c2-root"',
            'parser.add_argument("--snapshot-root"',
            'parser.add_argument("--confirm"',
            "args.confirm != REQUIRED_CONFIRMATION",
            TOKEN,
        ):
            self.assertIn(expected, text)
        for forbidden in (
            'add_argument("--activate"',
            'add_argument("--install"',
            'add_argument("--route"',
            'add_argument("--rollback"',
        ):
            self.assertNotIn(forbidden, text)

    def test_root_scope_is_fresh_user_owned_var_tmp_only(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            'raw.parent != Path("/var/tmp")',
            "SNAPSHOT_PREFIX",
            "info.st_uid != invoking_uid",
            "stat.S_IMODE(info.st_mode) != 0o700",
            "if any(raw.iterdir())",
            "os.chown(snapshot_root, 0, 0)",
            "chown_evidence_tree(snapshot_root, invoking_uid, invoking_gid)",
        ):
            self.assertIn(expected, text)

    def test_executable_commands_are_read_only(self):
        text = combined_source()
        forbidden_patterns = (
            r'run\(\["systemctl",\s*"(?:start|stop|restart|enable|disable|daemon-reload)"',
            r'run\(\["amixer".*"(?:sset|set)"',
            r'run\(\["modprobe"',
            r'run\(\["aplay"',
        )
        for pattern in forbidden_patterns:
            self.assertNotRegex(text, pattern)
        self.assertNotIn("subprocess.Popen", text)
        for expected in (
            "capture_service_states",
            "capture_mixer_states",
            "capture_module_and_dac",
        ):
            self.assertIn(expected, text)

    def test_absent_protected_path_is_resolved_without_changing_system_tree(self):
        with tempfile.TemporaryDirectory() as system_dir, tempfile.TemporaryDirectory() as parent:
            system_root = Path(system_dir)
            evidence_root = Path(parent) / "evidence"
            evidence_root.mkdir()
            create_fake_system_root(system_root)
            before = tree_fingerprint(system_root)
            summary = collect_filesystem_snapshot(fake_entries(), system_root, evidence_root)
            self.assertEqual(before, tree_fingerprint(system_root))
            self.assertEqual((summary.managed_absent, summary.managed_present, summary.conflicts), (12, 0, 0))
            marker = evidence_root / "absence-markers/etc__sudoers.d__a-clockwork-plex-audio-route.absent"
            self.assertEqual(marker.read_text(encoding="utf-8"), f"ABSENT\t{PROTECTED_PATH}\n")
            self.assertTrue(
                (evidence_root / "rootfs" / CURRENT_ALSA_DESTINATION.lstrip("/")).is_file()
            )

    def test_existing_protected_file_is_copied_outward_and_counted_present(self):
        with tempfile.TemporaryDirectory() as system_dir, tempfile.TemporaryDirectory() as parent:
            system_root = Path(system_dir)
            evidence_root = Path(parent) / "evidence"
            evidence_root.mkdir()
            create_fake_system_root(system_root)
            protected = system_root / PROTECTED_PATH.lstrip("/")
            protected.write_text("existing protected rule\n", encoding="utf-8")
            before = tree_fingerprint(system_root)
            summary = collect_filesystem_snapshot(fake_entries(), system_root, evidence_root)
            self.assertEqual(before, tree_fingerprint(system_root))
            self.assertEqual((summary.managed_absent, summary.managed_present, summary.conflicts), (11, 1, 0))
            copied = evidence_root / "rootfs" / PROTECTED_PATH.lstrip("/")
            self.assertEqual(copied.read_text(encoding="utf-8"), "existing protected rule\n")

    def test_symlinked_managed_path_and_symlinked_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as system_dir, tempfile.TemporaryDirectory() as parent:
            system_root = Path(system_dir)
            evidence_root = Path(parent) / "evidence"
            evidence_root.mkdir()
            create_fake_system_root(system_root)
            target = system_root / "target"
            target.write_text("target\n", encoding="utf-8")
            (system_root / "etc/default/a-clockwork-plex-split-bus").symlink_to(target)
            with self.assertRaises(SystemExit):
                collect_filesystem_snapshot(fake_entries(), system_root, evidence_root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ordinary.txt").write_text("ok\n", encoding="utf-8")
            (root / "link").symlink_to(root / "ordinary.txt")
            with self.assertRaises(SystemExit):
                write_evidence_manifest(root)

    def test_stage_c1_c2_and_live_host_are_replayed(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            "parse_manifest",
            "validate_stage_c1_evidence",
            "EXPECTED_STAGE_C2_CHECKS",
            "Stage C2 package fingerprint no longer matches",
            "privileged-check-required:permission-denied-errno-13",
            "EXPECTED_PRE_STAGE_C_ALSA_SHA256",
            '"index": "7"',
            '"id": "ACP_Loopback"',
            '"pcm_substreams": "2"',
            '"pcm_notify": "1"',
            "Unexpected Stage C approval marker",
            "Unexpected running CamillaDSP process",
        ):
            self.assertIn(expected, text)

    def test_success_requires_all_twelve_absent_and_future_snapshot_is_new(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            "summary.managed_absent != EXPECTED_PACKAGE_FILES",
            "summary.managed_present",
            "summary.conflicts",
            "all {EXPECTED_PACKAGE_FILES} managed file destinations verified absent",
            "use a new activation snapshot; never reuse rehearsal",
            "acquire the single Stage C route transaction lock before the future snapshot",
            "zero rollback mismatches",
            "this rehearsal evidence must never be reused as the future activation snapshot",
        ):
            self.assertIn(expected, text)

    def test_source_has_no_hidden_dynamic_execution(self):
        for path in (ENGINE, CORE):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile"}
            ]
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
