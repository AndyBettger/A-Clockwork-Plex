from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "scripts" / "a-clockwork-plex-airplay-wrappers.py"
LEGACY_INSTALLER = ROOT / "scripts" / "install-airplay-hooks.sh"
SPEC = importlib.util.spec_from_file_location("acp_airplay_wrappers", RENDERER_PATH)
RENDERER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RENDERER)


class AirPlayWrapperRendererTests(unittest.TestCase):
    def test_rendered_wrappers_preserve_playback_coordinator_contract(self) -> None:
        start = RENDERER.render_start_wrapper()
        end = RENDERER.render_end_wrapper()

        self.assertIn("/api/airplay/start", start)
        self.assertIn("PlaybackCoordinator owns Plexamp pause", start)
        self.assertNotIn("systemctl", start)
        self.assertNotIn("/player/playback/pause", start)

        self.assertIn("org.gnome.ShairportSync.RemoteControl", end)
        self.assertIn("PlayerState", end)
        self.assertIn("Available", end)
        self.assertIn("/api/airplay/end", end)
        self.assertIn("/api/playback/events", end)
        self.assertIn('s "Playing"', end)
        self.assertIn("b false", end)
        self.assertNotIn("systemctl", end)
        self.assertNotIn("/player/playback/pause", end)

    def test_dashboard_base_is_baked_into_both_candidates(self) -> None:
        base = "http://clock.example:8088"
        self.assertIn(f'DASHBOARD_BASE="{base}"', RENDERER.render_start_wrapper(base))
        self.assertIn(f'DASHBOARD_BASE="{base}"', RENDERER.render_end_wrapper(base))

    def test_unsafe_dashboard_base_is_rejected(self) -> None:
        for value in ("", "localhost:8088", "http://bad host:8088", 'http://bad"host'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RENDERER.validate_dashboard_base(value)

    def test_cli_writes_shell_syntax_valid_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = subprocess.run(
                [
                    "python3",
                    str(RENDERER_PATH),
                    "--output-dir",
                    str(output),
                    "--dashboard-base",
                    "http://localhost:8088",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in (RENDERER.START_NAME, RENDERER.END_NAME):
                candidate = output / name
                self.assertTrue(candidate.is_file())
                syntax = subprocess.run(
                    ["bash", "-n", str(candidate)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_legacy_installer_delegates_wrapper_logic_to_renderer(self) -> None:
        source = LEGACY_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-airplay-wrappers.py", source)
        self.assertIn("--dashboard-base", source)
        self.assertNotIn("cat <<START_WRAPPER_EOF", source)
        self.assertNotIn("remote_available_status()", source)


if __name__ == "__main__":
    unittest.main()
