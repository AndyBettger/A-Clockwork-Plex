from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-plexamp-runtime.sh"
LIBRARY = ROOT / "installer" / "lib" / "plexamp_runtime.sh"
CONFIRMATION = "INSTALL-PLEXAMP-RUNTIME"
NODE_SHA = "73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71"
PLEXAMP_SHA = "86e5ede3d852a87099a106f2cc6b83e4ec1350000176d83fbcedb83950c48041"


class PlexampRuntimeInstallerTests(unittest.TestCase):
    def make_archives(self, directory: Path) -> tuple[Path, Path, str, str]:
        node_tree = directory / "node-tree"
        node_bin = node_tree / "node-v20.20.2-linux-arm64" / "bin"
        node_bin.mkdir(parents=True)
        node = node_bin / "node"
        node.write_text("#!/usr/bin/env bash\necho v20.20.2\n", encoding="utf-8")
        node.chmod(0o755)
        node_archive = directory / "node.tar.xz"
        with tarfile.open(node_archive, "w:xz") as archive:
            archive.add(node_tree / "node-v20.20.2-linux-arm64", arcname="node-v20.20.2-linux-arm64")

        plex_tree = directory / "plex-tree" / "plexamp"
        (plex_tree / "js").mkdir(parents=True)
        (plex_tree / "js" / "index.js").write_text("// fixture Plexamp runtime\n", encoding="utf-8")
        (plex_tree / "plexamp.service").write_text("[Unit]\nDescription=fixture\n", encoding="utf-8")
        (plex_tree / "upgrade.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        plex_archive = directory / "plexamp.tar.bz2"
        with tarfile.open(plex_archive, "w:bz2") as archive:
            archive.add(plex_tree, arcname="plexamp")

        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        return node_archive, plex_archive, digest(node_archive), digest(plex_archive)

    def run_installer(
        self,
        root: Path | None = None,
        *arguments: str,
        env_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        argv = ["bash", str(INSTALLER)]
        if root is not None:
            argv.extend(["--root", str(root)])
        argv.extend(arguments)
        return subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_shell_syntax_and_prepare_only_are_inert(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(INSTALLER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = self.run_installer(None, "--project-user", "clockuser")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plexamp version:   4.13.2", result.stdout)
        self.assertIn("Node version:      20.20.2", result.stdout)
        self.assertIn(NODE_SHA, result.stdout)
        self.assertIn(PLEXAMP_SHA, result.stdout)
        self.assertIn("Artifact gate: READY", result.stdout)
        self.assertIn("No network request", result.stdout)

    def test_runtime_contract_pins_node_and_exact_plexamp_artifact(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")

        self.assertIn("ACP_PLEXAMP_VERSION=4.13.2", source)
        self.assertIn(
            'ACP_PLEXAMP_ARCHIVE_URL="https://plexamp.plex.tv/headless/${ACP_PLEXAMP_ARCHIVE}"',
            source,
        )
        self.assertIn(f'ACP_PLEXAMP_ARCHIVE_SHA256="{PLEXAMP_SHA}"', source)
        self.assertIn("ACP_PLEXAMP_ARCHIVE_BYTES=14566439", source)
        self.assertIn("ACP_NODE_VERSION=20.20.2", source)
        self.assertIn("ACP_NODE_PLATFORM=linux-arm64", source)
        self.assertIn(NODE_SHA, source)
        self.assertIn("nodejs.org/dist", source)

    def test_fresh_alternate_root_installs_verified_runtime_then_requests_local_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            node_archive, plex_archive, node_sha, plex_sha = self.make_archives(base)
            env = {
                "ACP_PLEXAMP_TEST_NODE_SHA256": node_sha,
                "ACP_PLEXAMP_TEST_ARCHIVE_SHA256": plex_sha,
            }

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                "--node-archive",
                str(node_archive),
                "--plexamp-archive",
                str(plex_archive),
                env_overrides=env,
            )

            self.assertEqual(result.returncode, 76, result.stderr)
            self.assertIn("PLEXAMP_RUNTIME=CLAIM-REQUIRED", result.stdout)
            self.assertIn("CLAIM_POLICY=INTERACTIVE-LOCAL-ONLY", result.stdout)
            self.assertIn("RERUN_ROOT_INSTALLER_AFTER_CLAIM=YES", result.stdout)

            node = root / "opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node"
            plex = root / "home/clockuser/plexamp/js/index.js"
            unit = root / "etc/systemd/system/plexamp.service"
            self.assertTrue(node.exists())
            self.assertTrue(plex.exists())
            unit_text = unit.read_text(encoding="utf-8")
            self.assertIn("User=clockuser", unit_text)
            self.assertIn("WorkingDirectory=/home/clockuser/plexamp", unit_text)
            self.assertIn(
                "ExecStart=/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node /home/clockuser/plexamp/js/index.js",
                unit_text,
            )

    def test_claimed_rerun_is_idempotent_and_does_not_need_archives_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            node_archive, plex_archive, node_sha, plex_sha = self.make_archives(base)
            env = {
                "ACP_PLEXAMP_TEST_NODE_SHA256": node_sha,
                "ACP_PLEXAMP_TEST_ARCHIVE_SHA256": plex_sha,
            }
            args = (
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                "--node-archive",
                str(node_archive),
                "--plexamp-archive",
                str(plex_archive),
            )
            first = self.run_installer(root, *args, env_overrides=env)
            self.assertEqual(first.returncode, 76, first.stderr)

            settings = root / "home/clockuser/.local/share/Plexamp/Settings"
            settings.mkdir(parents=True, exist_ok=True)
            (settings / "claimed-state").write_text("claimed\n", encoding="utf-8")

            second = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                env_overrides=env,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("PLEXAMP_RUNTIME=PASS", second.stdout)
            self.assertIn("PLEXAMP_VERSION=4.13.2", second.stdout)
            self.assertIn("NODE_VERSION=20.20.2", second.stdout)

    def test_injected_failure_restores_exact_previous_runtime_and_unit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            node_archive, plex_archive, node_sha, plex_sha = self.make_archives(base)
            env = {
                "ACP_PLEXAMP_TEST_NODE_SHA256": node_sha,
                "ACP_PLEXAMP_TEST_ARCHIVE_SHA256": plex_sha,
                "ACP_PLEXAMP_TEST_FAIL_AFTER_SWAP": "1",
            }

            old_node = root / "opt/a-clockwork-plex/node-v20.20.2-linux-arm64"
            old_node.mkdir(parents=True)
            (old_node / "old-node.txt").write_bytes(b"exact-old-node\n")
            old_plex = root / "home/clockuser/plexamp"
            old_plex.mkdir(parents=True)
            (old_plex / "old-plex.txt").write_bytes(b"exact-old-plex\n")
            unit = root / "etc/systemd/system/plexamp.service"
            unit.parent.mkdir(parents=True)
            old_unit = b"[Unit]\nDescription=old-plexamp\n"
            unit.write_bytes(old_unit)
            unit.chmod(0o600)

            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                "--node-archive",
                str(node_archive),
                "--plexamp-archive",
                str(plex_archive),
                env_overrides=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((old_node / "old-node.txt").read_bytes(), b"exact-old-node\n")
            self.assertEqual((old_plex / "old-plex.txt").read_bytes(), b"exact-old-plex\n")
            self.assertEqual(unit.read_bytes(), old_unit)
            self.assertEqual(unit.stat().st_mode & 0o777, 0o600)
            self.assertFalse((old_node / "bin/node").exists())
            self.assertFalse((old_plex / "js/index.js").exists())

    def test_digest_mismatch_fails_before_runtime_or_unit_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "root"
            root.mkdir()
            node_archive, plex_archive, _node_sha, plex_sha = self.make_archives(base)
            env = {
                "ACP_PLEXAMP_TEST_NODE_SHA256": "0" * 64,
                "ACP_PLEXAMP_TEST_ARCHIVE_SHA256": plex_sha,
            }
            result = self.run_installer(
                root,
                "--activate",
                "--confirm",
                CONFIRMATION,
                "--project-user",
                "clockuser",
                "--node-archive",
                str(node_archive),
                "--plexamp-archive",
                str(plex_archive),
                env_overrides=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Node archive SHA-256 mismatch", result.stderr)
            self.assertFalse((root / "home/clockuser/plexamp").exists())
            self.assertFalse((root / "etc/systemd/system/plexamp.service").exists())

    def test_claim_material_has_no_installer_option_or_environment_contract(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        library = LIBRARY.read_text(encoding="utf-8")

        self.assertNotIn("--claim", source)
        self.assertNotIn("--token", source)
        self.assertNotIn("PLEX_CLAIM", source)
        self.assertIn("explicit interactive boundary", library)
        self.assertIn("never accepted as a normal", library)
        self.assertIn("CLAIM_COMMAND=", source)
        self.assertNotIn("curl | bash", source)
        self.assertNotIn("nodesource", source.lower())
        self.assertNotIn("nvm install", source)

    def test_production_test_digest_overrides_are_explicitly_forbidden(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("ACP_PLEXAMP_TEST_* digest overrides are forbidden on the production root", source)


if __name__ == "__main__":
    unittest.main()
