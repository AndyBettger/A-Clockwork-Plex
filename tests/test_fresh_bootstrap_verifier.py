from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify-fresh-bootstrap.sh"
VENDORED_NFC = ROOT / "vendor" / "plexamp-nfc-listener" / "nfc_listener.py"
NODE_SHA = "1" * 64
PLEXAMP_SHA = "2" * 64


class FreshBootstrapVerifierTests(unittest.TestCase):
    def make_fixture(self, root: Path, *, claimed: bool = True) -> None:
        node_root = root / "opt/a-clockwork-plex/node-v20.20.2-linux-arm64"
        (node_root / "bin").mkdir(parents=True)
        node = node_root / "bin/node"
        node.write_text("#!/usr/bin/env bash\necho v20.20.2\n", encoding="utf-8")
        node.chmod(0o755)
        (node_root / ".a-clockwork-plex-runtime").write_text(
            f"kind=node\nversion=20.20.2\narchive_sha256={NODE_SHA}\n",
            encoding="utf-8",
        )

        plex = root / "home/clockuser/plexamp"
        (plex / "js").mkdir(parents=True)
        (plex / "js/index.js").write_text("// fixture\n", encoding="utf-8")
        (plex / ".a-clockwork-plex-runtime").write_text(
            f"kind=plexamp\nversion=4.13.2\narchive_sha256={PLEXAMP_SHA}\n",
            encoding="utf-8",
        )
        if claimed:
            settings = root / "home/clockuser/.local/share/Plexamp/Settings"
            settings.mkdir(parents=True)
            (settings / "claim-state").write_text("present\n", encoding="utf-8")

        project = root / "project"
        vendor = project / "vendor/plexamp-nfc-listener"
        vendor.mkdir(parents=True)
        shutil.copyfile(VENDORED_NFC, vendor / "nfc_listener.py")
        nfc_venv = project / "nfc-venv"
        subprocess.run(
            [sys.executable, "-m", "venv", "--symlinks", str(nfc_venv)],
            check=True,
            capture_output=True,
            text=True,
        )

        systemd = root / "etc/systemd/system"
        systemd.mkdir(parents=True)
        (systemd / "plexamp.service").write_text(
            "[Service]\n"
            "User=clockuser\n"
            "WorkingDirectory=/home/clockuser/plexamp\n"
            "ExecStart=/opt/a-clockwork-plex/node-v20.20.2-linux-arm64/bin/node /home/clockuser/plexamp/js/index.js\n",
            encoding="utf-8",
        )
        (systemd / "nfc-listener.service").write_text(
            "[Service]\n"
            "User=clockuser\n"
            "SupplementaryGroups=i2c gpio spi\n"
            "ExecStart=/project/nfc-venv/bin/python /project/vendor/plexamp-nfc-listener/nfc_listener.py\n",
            encoding="utf-8",
        )

    def run_verifier(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["ACP_PLEXAMP_TEST_NODE_SHA256"] = NODE_SHA
        env["ACP_PLEXAMP_TEST_ARCHIVE_SHA256"] = PLEXAMP_SHA
        return subprocess.run(
            [
                "bash",
                str(VERIFIER),
                "--root",
                str(root),
                "--project-user",
                "clockuser",
                "--project-dir",
                "/project",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_shell_syntax_and_complete_alternate_root_pass(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(VERIFIER)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root)
            nfc_python = root / "project/nfc-venv/bin/python"
            self.assertTrue(nfc_python.is_symlink())
            result = self.run_verifier(root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS  node-manifest", result.stdout)
        self.assertIn("PASS  plexamp-manifest", result.stdout)
        self.assertIn("PASS  plexamp-claim", result.stdout)
        self.assertIn("PASS  nfc-source", result.stdout)
        self.assertIn("PASS  nfc-venv", result.stdout)
        self.assertIn("PASS  nfc-pyvenv", result.stdout)
        self.assertIn("PASS  nfc-python", result.stdout)
        self.assertIn("PASS  nfc-venv-runtime", result.stdout)
        self.assertIn("WARN  live-hardware", result.stdout)
        self.assertIn("FRESH_BOOTSTRAP_VERIFY=PASS", result.stdout)

    def test_missing_claim_state_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root, claimed=False)
            result = self.run_verifier(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  plexamp-claim", result.stdout)
        self.assertIn("FRESH_BOOTSTRAP_VERIFY=FAIL", result.stdout)

    def test_wrong_nfc_source_identity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root)
            nfc = root / "project/vendor/plexamp-nfc-listener/nfc_listener.py"
            nfc.write_text("print('not the pinned listener')\n", encoding="utf-8")
            result = self.run_verifier(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  nfc-source", result.stdout)

    def test_missing_pyvenv_cfg_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_fixture(root)
            (root / "project/nfc-venv/pyvenv.cfg").unlink()
            result = self.run_verifier(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL  nfc-pyvenv", result.stdout)
        self.assertIn("FAIL  nfc-venv-runtime", result.stdout)

    def test_verifier_is_statically_read_only(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        for forbidden in (
            "apt-get install",
            "apt install",
            "systemctl start",
            "systemctl stop",
            "systemctl restart",
            "systemctl enable",
            "raspi-config",
            "dtoverlay=rpi-dacpro\" >>",
            "rpi-update",
            "rm -rf",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("FRESH_BOOTSTRAP_VERIFY=PASS", source)
        self.assertIn("sudo -- i2cdetect", source)
        self.assertNotIn('require_file nfc-python "$NFC_VENV/bin/python"', source)
        self.assertIn('require_executable nfc-python "$NFC_VENV/bin/python"', source)
        self.assertIn("sys.prefix != sys.base_prefix", source)


if __name__ == "__main__":
    unittest.main()
