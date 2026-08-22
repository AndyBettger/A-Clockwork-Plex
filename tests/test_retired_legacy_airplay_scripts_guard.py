from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "installer" / "repository-dependencies.txt"
RENDERER = ROOT / "scripts" / "a-clockwork-plex-airplay-wrappers.py"
INTEGRATION = ROOT / "scripts" / "install-airplay-integration.sh"

RETIRED_PATHS = (
    ROOT / "scripts" / "shairport-airplay-start.sh",
    ROOT / "scripts" / "shairport-airplay-end.sh",
    ROOT / "scripts" / "display-mode.sh",
    ROOT / "scripts" / "install-airplay-metadata-listener.sh",
)


class RetiredLegacyAirPlayScriptsGuardTests(unittest.TestCase):
    def test_legacy_airplay_scripts_remain_retired(self):
        for path in RETIRED_PATHS:
            with self.subTest(path=path.name):
                self.assertFalse(path.exists(), f"retired AirPlay path returned: {path}")

    def test_supported_renderer_and_transactional_owner_remain_present(self):
        self.assertTrue(RENDERER.is_file())
        self.assertTrue(INTEGRATION.is_file())

    def test_current_wrappers_do_not_manage_plexamp_service(self):
        text = RENDERER.read_text(encoding="utf-8")
        self.assertIn("PlaybackCoordinator owns Plexamp pause", text)
        self.assertNotIn("systemctl stop plexamp", text)
        self.assertNotIn("systemctl start plexamp", text)
        self.assertNotIn("display-mode.sh", text)

    def test_fresh_install_manifest_uses_current_airplay_owner_only(self):
        manifest = MANIFEST.read_text(encoding="utf-8")
        self.assertIn("scripts/install-airplay-integration.sh", manifest)
        self.assertIn("scripts/a-clockwork-plex-airplay-wrappers.py", manifest)
        self.assertIn("scripts/airplay-metadata-listener.py", manifest)
        for path in RETIRED_PATHS:
            relative = path.relative_to(ROOT).as_posix()
            self.assertNotIn(relative, manifest)


if __name__ == "__main__":
    unittest.main()
