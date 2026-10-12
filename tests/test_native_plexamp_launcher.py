"""Tests for the manually invoked native Plexamp Phase-B Flatpak launcher."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "launch-native-plexamp.sh"


class NativePlexampLauncherTests(unittest.TestCase):
    def test_shell_syntax(self):
        subprocess.run(["bash", "-n", str(LAUNCHER)], check=True)

    def test_help_needs_no_desktop_or_flatpak(self):
        result = subprocess.run(["bash", str(LAUNCHER), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Flatpak", result.stdout)
        self.assertIn("Headless", result.stdout)

    @unittest.skipIf(os.geteuid() == 0, "desktop-session mocks require a non-root test user")
    def test_launch_from_ssh_and_already_running(self):
        with tempfile.TemporaryDirectory(prefix="acp-native-launcher-") as td:
            base = Path(td)
            runtime = base / "runtime"
            runtime.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            app_run = base / "flatpak-run.txt"
            flatpak = bin_dir / "flatpak"
            flatpak.write_text(
                "#!/bin/sh\n"
                'case "$1" in\n'
                '  info) exit 0 ;;\n'
                '  ps) if [ "${MOCK_RUNNING:-}" = 1 ]; then printf "%s\\n" com.plexamp.Plexamp; fi; exit 0 ;;\n'
                '  run) printf "%s\\n" "$WAYLAND_DISPLAY|$XDG_RUNTIME_DIR|$DBUS_SESSION_BUS_ADDRESS|$*" > "$MOCK_APP_RUN"; exit 0 ;;\n'
                '  *) exit 20 ;;\n'
                'esac\n', encoding="utf-8"
            )
            flatpak.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "HOME": str(base),
                "XDG_RUNTIME_DIR": str(runtime),
                "XDG_CACHE_HOME": str(base / "cache"),
                "PATH": f"{bin_dir}:{env['PATH']}",
                "MOCK_APP_RUN": str(app_run),
            })
            env.pop("WAYLAND_DISPLAY", None)  # SSH case
            env.pop("DBUS_SESSION_BUS_ADDRESS", None)
            # An already-running instance is not launched twice, even if the
            # caller has no Wayland environment yet.
            running_env = dict(env, MOCK_RUNNING="1")
            result = subprocess.run(["bash", str(LAUNCHER)], env=running_env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("already running", result.stdout)
            self.assertFalse(app_run.exists())

            # No active compositor socket: safely refuse to launch.
            result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No running Wayland", result.stderr)
            self.assertFalse(app_run.exists())

            with socket.socket(socket.AF_UNIX) as wayland, socket.socket(socket.AF_UNIX) as bus:
                wayland.bind(str(runtime / "wayland-0"))
                bus.bind(str(runtime / "bus"))
                result = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("launch requested", result.stdout)
                for _ in range(100):
                    if app_run.exists():
                        break
                    time.sleep(0.02)
                self.assertTrue(app_run.exists(), "Fake Flatpak was not launched")
                line = app_run.read_text(encoding="utf-8")
                self.assertIn("wayland-0|", line)
                self.assertIn("unix:path=", line)
                self.assertIn("run --branch=beta com.plexamp.Plexamp", line)
                self.assertTrue((base / "cache/a-clockwork-plex/native-plexamp.log").exists())


if __name__ == "__main__":
    unittest.main()
