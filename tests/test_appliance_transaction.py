from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "installer" / "lib" / "transaction.sh"


class ApplianceTransactionTests(unittest.TestCase):
    def run_shell(self, script: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", script],
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_alternate_root_restores_changed_file_and_removes_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            transaction = Path(directory) / "transaction"
            existing = root / "etc/example.conf"
            created = root / "usr/local/bin/new-helper"
            existing.parent.mkdir(parents=True)
            existing.write_text("before\n", encoding="utf-8")
            os.chmod(existing, 0o640)
            expected_hash = hashlib.sha256(b"before\n").hexdigest()

            result = self.run_shell(
                f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_transaction_begin {transaction!s}
acp_transaction_capture_path {transaction!s} /etc/example.conf
acp_transaction_capture_path {transaction!s} /usr/local/bin/new-helper
printf 'after\n' > {existing!s}
mkdir -p {created.parent!s}
printf 'created\n' > {created!s}
acp_transaction_restore_paths {transaction!s}
'''
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(existing.read_text(encoding="utf-8"), "before\n")
            self.assertEqual(oct(existing.stat().st_mode & 0o777), "0o640")
            self.assertEqual(hashlib.sha256(existing.read_bytes()).hexdigest(), expected_hash)
            self.assertFalse(created.exists())

    def test_restore_runs_in_reverse_capture_order(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")
        self.assertIn("tail -n +2 \"$directory/paths.tsv\" | tac", source)
        self.assertIn("tail -n +2 \"$directory/services.tsv\" | tac", source)

    def test_duplicate_capture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            transaction = Path(directory) / "transaction"
            target = root / "etc/example.conf"
            target.parent.mkdir(parents=True)
            target.write_text("before\n", encoding="utf-8")

            result = self.run_shell(
                f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_transaction_begin {transaction!s}
acp_transaction_capture_path {transaction!s} /etc/example.conf
acp_transaction_capture_path {transaction!s} /etc/example.conf
'''
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("captured twice", result.stderr)

    def test_symlink_capture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            transaction = Path(directory) / "transaction"
            real = root / "etc/real.conf"
            link = root / "etc/example.conf"
            real.parent.mkdir(parents=True)
            real.write_text("before\n", encoding="utf-8")
            link.symlink_to(real.name)

            result = self.run_shell(
                f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_transaction_begin {transaction!s}
acp_transaction_capture_path {transaction!s} /etc/example.conf
'''
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Symlink capture is intentionally unsupported", result.stderr)

    def test_service_functions_refuse_alternate_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            transaction = Path(directory) / "transaction"
            result = self.run_shell(
                f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_transaction_begin {transaction!s}
if acp_transaction_capture_service {transaction!s} a-clockwork-plex.service; then
    exit 9
fi
if acp_transaction_restore_services {transaction!s}; then
    exit 10
fi
'''
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("production root", result.stderr)

    def test_library_has_no_automatic_activation_entrypoint(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")
        self.assertNotIn("apt install", source)
        self.assertNotIn("pip install", source)
        self.assertNotIn("install-eq.sh", source)
        self.assertNotIn("install-airplay-hooks.sh", source)
        self.assertNotIn("INSTALL-A-CLOCKWORK-PLEX", source)


if __name__ == "__main__":
    unittest.main()
