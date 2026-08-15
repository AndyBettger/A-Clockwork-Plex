from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_nfc_python_deps.py"
PACKAGE_INSTALLER = ROOT / "scripts" / "install-appliance-packages.sh"

spec = importlib.util.spec_from_file_location("check_nfc_python_deps", CHECKER)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class FakeDistribution:
    def __init__(self, name: str, version: str = "1.0", requires: list[str] | None = None):
        self.metadata = {"Name": name}
        self.version = version
        self.requires = requires or []


class NfcPythonDependencyCheckTests(unittest.TestCase):
    def test_trixie_inherited_metadata_noise_is_not_an_nfc_failure(self) -> None:
        output = """\
types-flask-socketio 5.4 requires flask, which is not installed.
types-flask-migrate 4.0 requires flask, which is not installed.
types-flask-migrate 4.0 requires flask-sqlalchemy, which is not installed.
types-flask-cors 5.0 requires flask, which is not installed.
types-tree-sitter-languages 1.10 requires tree-sitter, which is not installed.
apt-listchanges 4.8 requires debconf, which is not installed.
types-click-default-group 1.2 requires click, which is not installed.
types-seaborn 0.13.2 requires matplotlib, which is not installed.
types-seaborn 0.13.2 requires pandas-stubs, which is not installed.
"""
        owned = {
            "adafruit-blinka",
            "adafruit-circuitpython-pn532",
            "rpi-gpio",
            "requests",
            "lgpio",
        }

        owned_errors, inherited_errors, unclassified = checker.classify_pip_check_output(
            output,
            owned,
        )

        self.assertEqual(owned_errors, [])
        self.assertEqual(len(inherited_errors), 9)
        self.assertEqual(unclassified, [])

    def test_broken_owned_dependency_still_fails_scope_classification(self) -> None:
        output = (
            "adafruit-blinka 9.2.0 requires lgpio>=0.2.2.0, "
            "which is not installed.\n"
        )
        owned = {"adafruit-blinka", "lgpio"}

        owned_errors, inherited_errors, unclassified = checker.classify_pip_check_output(
            output,
            owned,
        )

        self.assertEqual(len(owned_errors), 1)
        self.assertEqual(inherited_errors, [])
        self.assertEqual(unclassified, [])

    def test_owned_closure_follows_recursive_active_dependencies(self) -> None:
        roots = [checker.Requirement("adafruit-blinka"), checker.Requirement("requests")]
        distributions = {
            "adafruit-blinka": FakeDistribution(
                "adafruit-blinka",
                requires=["lgpio>=0.2.2.0", "Adafruit-PlatformDetect>=3.89.1"],
            ),
            "lgpio": FakeDistribution("lgpio"),
            "adafruit-platformdetect": FakeDistribution("Adafruit-PlatformDetect"),
            "requests": FakeDistribution("requests", requires=["urllib3<3"]),
            "urllib3": FakeDistribution("urllib3"),
        }

        owned = checker.owned_dependency_closure(roots, distributions)

        self.assertEqual(
            owned,
            {
                "adafruit-blinka",
                "lgpio",
                "adafruit-platformdetect",
                "requests",
                "urllib3",
            },
        )

    def test_missing_top_level_requirement_fails_closed(self) -> None:
        roots = [checker.Requirement("adafruit-circuitpython-pn532")]
        errors = checker.validate_roots(roots, {})
        self.assertEqual(len(errors), 1)
        self.assertIn("not installed", errors[0])

    def test_package_owner_uses_scoped_checker_for_candidate_and_live_nfc_venvs(self) -> None:
        source = PACKAGE_INSTALLER.read_text(encoding="utf-8")
        self.assertIn(
            'NFC_DEPENDENCY_CHECK="$REPO_ROOT/scripts/check_nfc_python_deps.py"',
            source,
        )
        self.assertIn(
            '"$NFC_CANDIDATE/bin/python" "$NFC_DEPENDENCY_CHECK" --requirements "$NFC_REQUIREMENTS"',
            source,
        )
        self.assertIn(
            '"$NFC_VENV_TARGET/bin/python" "$NFC_DEPENDENCY_CHECK" --requirements "$NFC_REQUIREMENTS"',
            source,
        )
        self.assertNotIn(
            '"$NFC_CANDIDATE/bin/python" -m pip check',
            source,
        )
        self.assertNotIn(
            '"$NFC_VENV_TARGET/bin/python" -m pip check',
            source,
        )
        # The ordinary application venv remains isolated, so its complete pip
        # integrity check must not be weakened by this NFC-specific fix.
        self.assertIn('"$APP_CANDIDATE/bin/python" -m pip check', source)
        self.assertIn('"$VENV_TARGET/bin/python" -m pip check', source)

    def test_checker_help_executes_with_repository_python(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--requirements", result.stdout)


if __name__ == "__main__":
    unittest.main()
