from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "README.md"

CURRENT = {
    "README.md",
    "INSTALL.md",
    "appliance-installer.md",
    "eq-audio-installer-roadmap.md",
    "release-hygiene-audit-2026-08-19.md",
    "fresh-appliance-acceptance-runbook.md",
    "application-state-architecture.md",
    "airplay-metadata.md",
    "alarm-audio-testing.md",
    "testing.md",
}

EVIDENCE = {
    "final-clean-room-physical-progress-2026-08-21.md",
    "fresh-bootstrap-physical-progress-2026-08-15.md",
    "eq-to-direct-physical-verification-2026-08-17.md",
    "direct-independent-verification-2026-08-17.md",
    "eq-to-direct-desktop-audio-blocker-2026-08-17.md",
    "reboot-eq-runtime-failure-2026-08-17.md",
    "weather-physical-followup-2026-08-17.md",
}

DURABLE_DESIGN = {
    "fresh-pi-bootstrap-ownership-design.md",
    "full-appliance-installer-design.md",
    "airplay-segment-cell.svg",
}

ROADMAP_ARCHIVES = {
    "eq-audio-installer-roadmap-history-through-phase7-checkpoint6.md",
    "eq-audio-installer-roadmap-history-through-checkpoint64.md",
}

HISTORICAL_EXACT = {
    "production-eq-stage-c-install-design.md",
    "bedroom-dsp-laboratory-results.md",
    "post-mix-dsp-laboratory.md",
    "master-eq-testing.md",
    "production-eq-split-bus-design.md",
    "eq-audio-installation-manifest.md",
    "camilladsp-eq-helper-contract.md",
    "eq-audio-route-helper-contract.md",
    "direct-alarm-bypass-failback-result-2026-08-05.md",
    "airplay-control-plane-review-2026-07-26.md",
    "plexamp-4.12.4-restart-investigation.md",
    "post-weather-settings-redesign.md",
}


def classification(name: str) -> str | None:
    if name in CURRENT:
        return "current"
    if name in EVIDENCE:
        return "evidence"
    if name in DURABLE_DESIGN:
        return "design"
    if name in ROADMAP_ARCHIVES:
        return "archive"
    if name in HISTORICAL_EXACT:
        return "historical"
    if name.startswith("stage-c") and name.endswith(".md"):
        return "historical"
    if name.startswith("split-bus-") and name.endswith(".md"):
        return "historical"
    if name.startswith("stage-seven-") and name.endswith(".md"):
        return "historical"
    return None


class DocsCatalogTests(unittest.TestCase):
    def test_every_top_level_docs_artifact_is_classified(self):
        unclassified: list[str] = []
        for path in sorted(DOCS.iterdir()):
            if path.is_file() and classification(path.name) is None:
                unclassified.append(path.name)
        self.assertEqual([], unclassified, f"unclassified docs artifacts: {unclassified}")

    def test_catalog_names_current_authorities_and_warns_about_history(self):
        text = CATALOG.read_text(encoding="utf-8")
        for name in CURRENT - {"README.md"}:
            with self.subTest(name=name):
                self.assertIn(f"`docs/{name}`", text)
        self.assertIn("must not be treated as current instructions", text)
        self.assertIn("Every `docs/stage-c*.md` file", text)
        self.assertIn("fixed `-6.5 dB` music reserve", text)

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
