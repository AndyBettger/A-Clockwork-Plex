from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

RETIRED_WRAPPERS = (
    "scripts/install-shared-audio.sh",
    "scripts/install-alarm-audio-helper.sh",
    "scripts/install-shairport-name-helper.sh",
)

TRANSACTIONAL_OWNER = "scripts/install-appliance-helpers.sh"
RUNTIME_SOURCES = (
    "scripts/a-clockwork-plex-alarm-audio-helper.sh",
    "scripts/a-clockwork-plex-shairport-name.py",
    "scripts/a-clockwork-plex-audio-mixer.py",
)


class RetiredLegacyHelperInstallersGuardTests(unittest.TestCase):
    def test_standalone_legacy_helper_installers_remain_retired(self):
        for relative in RETIRED_WRAPPERS:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists(), relative)

    def test_transactional_helper_owner_and_runtime_sources_remain_present(self):
        owner_path = ROOT / TRANSACTIONAL_OWNER
        self.assertTrue(owner_path.is_file(), TRANSACTIONAL_OWNER)
        owner = owner_path.read_text(encoding="utf-8")
        for relative in RUNTIME_SOURCES:
            with self.subTest(path=relative):
                source = ROOT / relative
                self.assertTrue(source.is_file(), relative)
                self.assertIn(source.name, owner)
        self.assertIn("INSTALL-APPLIANCE-HELPERS", owner)
        self.assertIn("restoring captured state", owner)

    def test_ci_checks_transactional_owner_not_retired_wrappers(self):
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn(f"bash -n {TRANSACTIONAL_OWNER}", workflow)
        for relative in RETIRED_WRAPPERS:
            with self.subTest(path=relative):
                self.assertNotIn(relative, workflow)


if __name__ == "__main__":
    unittest.main()
