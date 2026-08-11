from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "installer" / "lib" / "application_transaction.sh"


class ApplianceApplicationTransactionTests(unittest.TestCase):
    def run_bash(self, script: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(
            ["bash", "-c", script],
            cwd=ROOT,
            env=merged,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_source_contract_keeps_package_baseline_outside_application_transaction(self) -> None:
        text = LIBRARY.read_text(encoding="utf-8")
        self.assertIn("Package/venv bootstrap intentionally happens before this transaction", text)
        self.assertIn("acp_application_transaction_begin", text)
        self.assertIn("acp_application_transaction_restore", text)
        self.assertIn("/tmp/shairport-sync-metadata", text)
        self.assertIn("acp_managed_file_destinations", text)
        self.assertNotIn("apt-get", text)
        self.assertNotIn("venv", "\n".join(line for line in text.splitlines() if line.lstrip().startswith(("sudo ", "mv ", "rm "))))

    def test_alternate_root_restores_files_absence_modes_and_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            project = root / "project"
            project.mkdir()

            existing_config = project / "config.json"
            existing_config.write_text('{"before": true}\n', encoding="utf-8")
            existing_config.chmod(0o640)

            route = root / "etc/alsa/conf.d/99-a-clockwork-plex-shared.conf"
            route.parent.mkdir(parents=True)
            route.write_text("old route\n", encoding="utf-8")
            route.chmod(0o600)

            shairport = root / "etc/shairport-sync.conf"
            shairport.parent.mkdir(parents=True, exist_ok=True)
            shairport.write_text("old shairport\n", encoding="utf-8")

            fifo = root / "tmp/shairport-sync-metadata"
            fifo.parent.mkdir(parents=True)
            os.mkfifo(fifo, 0o620)
            fifo.chmod(0o620)

            transaction = root / "transaction"
            script = f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_application_transaction_begin {transaction!s} testclock /project
printf 'changed config\n' > {existing_config!s}
chmod 600 {existing_config!s}
printf 'changed route\n' > {route!s}
chmod 644 {route!s}
printf 'new helper\n' > {root / 'usr/local/bin/a-clockwork-plex-alarm-audio'!s}
rm -f {fifo!s}
mkfifo {fifo!s}
chmod 666 {fifo!s}
acp_application_transaction_restore {transaction!s}
'''
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(existing_config.read_text(encoding="utf-8"), '{"before": true}\n')
            self.assertEqual(stat.S_IMODE(existing_config.stat().st_mode), 0o640)
            self.assertEqual(route.read_text(encoding="utf-8"), "old route\n")
            self.assertEqual(stat.S_IMODE(route.stat().st_mode), 0o600)
            self.assertFalse((root / "usr/local/bin/a-clockwork-plex-alarm-audio").exists())
            self.assertTrue(stat.S_ISFIFO(fifo.stat().st_mode))
            self.assertEqual(stat.S_IMODE(fifo.stat().st_mode), 0o620)

    def test_transaction_rejects_unexpected_fifo_object_before_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "project").mkdir()
            fifo = root / "tmp/shairport-sync-metadata"
            fifo.parent.mkdir(parents=True)
            fifo.write_text("not a fifo\n", encoding="utf-8")
            shairport = root / "etc/shairport-sync.conf"
            shairport.parent.mkdir(parents=True)
            shairport.write_text("config\n", encoding="utf-8")
            transaction = root / "transaction"
            script = f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
export ACP_ROOT={root!s}
source {LIBRARY!s}
acp_application_transaction_begin {transaction!s} testclock /project
'''
            result = self.run_bash(script)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("neither absent nor a FIFO", result.stderr)

    def test_managed_path_list_contains_shared_dashboard_and_audio_authorities(self) -> None:
        script = f'''
set -euo pipefail
export ACP_REPO_ROOT={ROOT!s}
source {LIBRARY!s}
acp_application_managed_paths testclock /home/testclock/A-Clockwork-Plex
'''
        result = self.run_bash(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in (
            "/etc/systemd/system/a-clockwork-plex.service",
            "/home/testclock/.config/autostart/a-clockwork-plex-dashboard.desktop",
            "/etc/default/a-clockwork-plex-weather",
            "/etc/shairport-sync.conf",
            "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf",
            "/etc/systemd/system/a-clockwork-plex-camilladsp.service",
            "/usr/local/bin/a-clockwork-plex-alarm-audio",
        ):
            self.assertIn(expected, result.stdout)

    def test_shell_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(LIBRARY)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
