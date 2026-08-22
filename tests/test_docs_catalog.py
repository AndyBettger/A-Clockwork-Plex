from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "README.md"
ARCHIVE = DOCS / "archive"
SNAPSHOT = ARCHIVE / "pre-release-engineering-snapshot-2026-08-22"

TOP_LEVEL_FILES = {
    "README.md",
    "INSTALL.md",
    "appliance-installer.md",
    "eq-audio-installer-roadmap.md",
    "eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md",
    "eq-audio-installer-roadmap-history-through-checkpoint64.md",
    "release-hygiene-audit-2026-08-19.md",
    "fresh-appliance-acceptance-runbook.md",
    "application-state-architecture.md",
    "airplay-metadata.md",
    "alarm-audio-testing.md",
    "testing.md",
    "final-clean-room-physical-progress-2026-08-21.md",
    "fresh-bootstrap-physical-progress-2026-08-15.md",
    "eq-to-direct-physical-verification-2026-08-17.md",
    "direct-independent-verification-2026-08-17.md",
    "eq-to-direct-desktop-audio-blocker-2026-08-17.md",
    "reboot-eq-runtime-failure-2026-08-17.md",
    "weather-physical-followup-2026-08-17.md",
    "fresh-pi-bootstrap-ownership-design.md",
    "full-appliance-installer-design.md",
    "airplay-segment-cell.svg",
}


class DocsCatalogTests(unittest.TestCase):
    def test_top_level_docs_are_deliberately_small_and_classified(self):
        files = {path.name for path in DOCS.iterdir() if path.is_file()}
        dirs = {path.name for path in DOCS.iterdir() if path.is_dir()}
        self.assertEqual(TOP_LEVEL_FILES, files)
        self.assertEqual({"archive"}, dirs)

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

    def test_catalog_points_normal_users_to_install_and_history_to_archive(self):
        text = CATALOG.read_text(encoding="utf-8")
        self.assertIn("Start with **[`INSTALL.md`](INSTALL.md)**", text)
        self.assertIn("You do not need the roadmap", text)
        self.assertIn("archive/pre-release-engineering-snapshot-2026-08-22/", text)
        self.assertIn("The archive is allowed to be old", text)

    def test_repaired_current_guides_do_not_reintroduce_retired_instructions(self):
        airplay = (DOCS / "airplay-metadata.md").read_text(encoding="utf-8")
        alarm = (DOCS / "alarm-audio-testing.md").read_text(encoding="utf-8")
        architecture = (DOCS / "application-state-architecture.md").read_text(encoding="utf-8")
        testing = (DOCS / "testing.md").read_text(encoding="utf-8")

        self.assertNotIn("install-airplay-metadata-listener.sh", airplay)
        self.assertNotIn("install-shared-audio.sh", alarm)
        self.assertNotIn("known-good direct shared ALSA mixer remains the production audio graph", architecture)
        self.assertNotIn("Production EQ is the next", architecture)
        self.assertNotIn("Ecowitt remains authoritative", architecture)
        self.assertNotIn("scheduler remains disabled", testing)
        self.assertNotIn("when Node.js is available", testing)

    def test_current_audio_docs_pin_alarm_bypass_and_fixed_reserve(self):
        alarm = (DOCS / "alarm-audio-testing.md").read_text(encoding="utf-8")
        architecture = (DOCS / "application-state-architecture.md").read_text(encoding="utf-8")
        for text in (alarm, architecture):
            self.assertIn("fixed -6.5 dB", text)
            self.assertIn("bypass", text.lower())
            self.assertIn("Music Master", text)
            self.assertIn("Maximum Alarm Volume", text)


if __name__ == "__main__":
    unittest.main()
