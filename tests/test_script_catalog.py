from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CATALOG = SCRIPTS / "README.md"
RUNNER = SCRIPTS / "run-tests.sh"
DOCUMENTED_DIRS = (SCRIPTS, SCRIPTS / "audio", SCRIPTS / "audio_eq_camilladsp")

RETIRED_RUNNER_REFERENCES = (
    "install-alarm-audio-helper.sh",
    "install-shared-audio.sh",
    "install-shairport-name-helper.sh",
    "install-master-eq.sh",
    "shairport-airplay-start.sh",
    "shairport-airplay-end.sh",
    "display-mode.sh",
    "install-airplay-metadata-listener.sh",
)


class ScriptCatalogTests(unittest.TestCase):
    def test_catalog_exists_and_points_normal_users_to_setup(self):
        text = CATALOG.read_text(encoding="utf-8")
        self.assertIn("bash setup.sh", text)
        self.assertIn("docs/INSTALL.md", text)
        self.assertIn("docs/appliance-installer.md", text)
        self.assertIn("Do **not** cherry-pick component installers", text)

    def test_every_retained_script_file_is_documented(self):
        text = CATALOG.read_text(encoding="utf-8")
        missing: list[str] = []
        for directory in DOCUMENTED_DIRS:
            for path in sorted(directory.iterdir()):
                if not path.is_file() or path == CATALOG:
                    continue
                relative = path.relative_to(ROOT).as_posix()
                if f"`{relative}`" not in text:
                    missing.append(relative)
        self.assertEqual([], missing, f"undocumented retained scripts: {missing}")

    def test_catalog_explains_safety_and_non_operator_runtime_sources(self):
        text = CATALOG.read_text(encoding="utf-8")
        for phrase in (
            "Read-only",
            "Guarded mutation",
            "Internal mutation",
            "Runtime/helper",
            "Developer",
            "not an operator command",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_local_runner_discovers_current_source_instead_of_pinning_retired_paths(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("find app scripts -type f -name '*.py'", text)
        self.assertIn("find scripts -type f -name '*.sh'", text)
        self.assertIn("find app/static/js -type f -name '*.js'", text)
        self.assertIn("python -m unittest discover -s tests", text.replace('"$PYTHON"', "python"))
        for retired in RETIRED_RUNNER_REFERENCES:
            with self.subTest(retired=retired):
                self.assertNotIn(retired, text)


if __name__ == "__main__":
    unittest.main()
