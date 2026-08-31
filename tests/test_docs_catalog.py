from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "README.md"
ASSETS = DOCS / "assets"
SCREENSHOTS = ASSETS / "screenshots"
DEVELOPMENT = DOCS / "development"
ROADMAP_DIR = DOCS / "roadmap"
ARCHIVE = DOCS / "archive"
SNAPSHOT = ARCHIVE / "pre-release-engineering-snapshot-2026-08-22"

TOP_LEVEL_FILES = {"README.md", "INSTALL.md", "appliance-installer.md"}
TOP_LEVEL_DIRS = {"archive", "assets", "development", "roadmap"}

SCREENSHOT_FILES = {
    "airplay-now-playing.png",
    "airplay-ready.png",
    "alarm-ringing.png",
    "clock-day.png",
    "clock-night.png",
    "plexamp-now-playing.png",
    "settings-about.png",
    "settings-alarms.png",
    "settings-audio.png",
    "settings-weather.png",
    "weather-1.png",
    "weather-2.png",
    "weather-3.png",
}
DEVELOPMENT_ARCHITECTURE = {
    "application-state-architecture.md",
    "airplay-metadata.md",
    "airplay-segment-cell.svg",
    "configuration-backup-ownership.md",
    "fresh-pi-bootstrap-ownership-design.md",
    "full-appliance-installer-design.md",
    "touchscreen-text-entry.md",
}
DEVELOPMENT_TESTING = {
    "testing.md",
    "test-catalogue.md",
    "alarm-audio-testing.md",
    "fresh-appliance-acceptance-runbook.md",
}
DEVELOPMENT_EVIDENCE = {
    "direct-independent-verification-2026-08-17.md",
    "eq-to-direct-desktop-audio-blocker-2026-08-17.md",
    "eq-to-direct-physical-verification-2026-08-17.md",
    "final-clean-room-physical-progress-2026-08-21.md",
    "fresh-bootstrap-physical-progress-2026-08-15.md",
    "reboot-eq-runtime-failure-2026-08-17.md",
    "release-hygiene-audit-2026-08-19.md",
    "weather-physical-followup-2026-08-17.md",
}
ROADMAP_FILES = {
    "README.md",
    "ROADMAP.md",
    "history-through-phase7-checkpoint6.md",
    "history-through-checkpoint64.md",
}


class DocsCatalogTests(unittest.TestCase):
    def test_top_level_docs_are_normal_user_focused(self):
        files = {path.name for path in DOCS.iterdir() if path.is_file()}
        dirs = {path.name for path in DOCS.iterdir() if path.is_dir()}
        self.assertEqual(TOP_LEVEL_FILES, files)
        self.assertEqual(TOP_LEVEL_DIRS, dirs)

    def test_documentation_assets_are_curated_and_out_of_root(self):
        self.assertTrue((ASSETS / "README.md").is_file())
        self.assertTrue(SCREENSHOTS.is_dir())
        self.assertEqual(
            SCREENSHOT_FILES,
            {path.name for path in SCREENSHOTS.iterdir() if path.is_file()},
        )
        self.assertFalse(any(path.suffix.lower() == ".png" for path in DOCS.iterdir() if path.is_file()))

    def test_development_tree_is_deliberately_classified(self):
        self.assertTrue((DEVELOPMENT / "README.md").is_file())
        self.assertEqual(
            DEVELOPMENT_ARCHITECTURE,
            {path.name for path in (DEVELOPMENT / "architecture").iterdir() if path.is_file()},
        )
        self.assertEqual(
            DEVELOPMENT_TESTING,
            {path.name for path in (DEVELOPMENT / "testing").iterdir() if path.is_file()},
        )
        self.assertEqual(
            DEVELOPMENT_EVIDENCE,
            {path.name for path in (DEVELOPMENT / "evidence").iterdir() if path.is_file()},
        )

    def test_roadmap_has_one_live_authority_and_preserved_history(self):
        self.assertEqual(
            ROADMAP_FILES,
            {path.name for path in ROADMAP_DIR.iterdir() if path.is_file()},
        )
        roadmap = (ROADMAP_DIR / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("# A Clockwork Plex Roadmap", roadmap)
        self.assertIn("Future product backlog", roadmap)
        self.assertIn("Friendly forecast-location entry", roadmap)
        self.assertIn("Configuration backup/export", roadmap)
        self.assertIn("Plexamp Search keyboard/bridge", roadmap)
        self.assertNotIn("# EQ-capable Audio + Full Appliance Installer Roadmap", roadmap)

    def test_archive_preserves_the_pre_reorganisation_engineering_tree(self):
        self.assertTrue((ARCHIVE / "README.md").is_file())
        self.assertTrue(SNAPSHOT.is_dir())
        for name in (
            "stage-c21-production-approval-writer-design.md",
            "production-eq-stage-c-install-design.md",
            "bedroom-dsp-laboratory-results.md",
            "post-weather-settings-redesign.md",
            "eq-audio-installer-roadmap-history-through-checkpoint64.md",
        ):
            with self.subTest(name=name):
                self.assertTrue((SNAPSHOT / name).is_file())

    def test_catalog_points_normal_users_away_from_engineering_clutter(self):
        text = CATALOG.read_text(encoding="utf-8")
        self.assertIn("Start with **[`INSTALL.md`](INSTALL.md)**", text)
        self.assertIn("visual first-use tour", text)
        self.assertIn("normal supported source channel is `main`", text)
        self.assertIn("v0.4.0", text)
        self.assertIn("assets/", text)
        self.assertIn("development/", text)
        self.assertIn("roadmap/ROADMAP.md", text)
        self.assertIn("archive/pre-release-engineering-snapshot-2026-08-22/", text)
        self.assertIn("The archive is allowed to be old", text)

    def test_repaired_current_guides_do_not_reintroduce_retired_instructions(self):
        airplay = (DEVELOPMENT / "architecture" / "airplay-metadata.md").read_text(encoding="utf-8")
        alarm = (DEVELOPMENT / "testing" / "alarm-audio-testing.md").read_text(encoding="utf-8")
        architecture = (DEVELOPMENT / "architecture" / "application-state-architecture.md").read_text(encoding="utf-8")
        testing = (DEVELOPMENT / "testing" / "testing.md").read_text(encoding="utf-8")

        self.assertNotIn("install-airplay-metadata-listener.sh", airplay)
        self.assertNotIn("install-shared-audio.sh", alarm)
        self.assertNotIn("known-good direct shared ALSA mixer remains the production audio graph", architecture)
        self.assertNotIn("Production EQ is the next", architecture)
        self.assertNotIn("Ecowitt remains authoritative", architecture)
        self.assertNotIn("scheduler remains disabled", testing)
        self.assertNotIn("when Node.js is available", testing)

    def test_current_audio_docs_pin_alarm_bypass_and_fixed_reserve(self):
        alarm = (DEVELOPMENT / "testing" / "alarm-audio-testing.md").read_text(encoding="utf-8")
        architecture = (DEVELOPMENT / "architecture" / "application-state-architecture.md").read_text(encoding="utf-8")
        for text in (alarm, architecture):
            self.assertIn("fixed -6.5 dB", text)
            self.assertIn("bypass", text.lower())
            self.assertIn("Music Master", text)
            self.assertIn("Maximum Alarm Volume", text)


if __name__ == "__main__":
    unittest.main()
