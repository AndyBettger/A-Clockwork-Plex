from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "a-clockwork-plex-weather-secret.py"
HELPER_INSTALLER = ROOT / "scripts" / "install-appliance-helpers.sh"
VERIFIER = ROOT / "scripts" / "verify-appliance.sh"
RUNBOOK = ROOT / "docs" / "fresh-appliance-acceptance-runbook.md"


@unittest.skipIf(os.geteuid() == 0, "The helper deliberately forbids its test-path override as root.")
class ManagedWeatherSecretStatusRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.secret_file = Path(self.temporary.name) / "weather.env"
        self.environment = os.environ.copy()
        self.environment["ACP_WEATHER_SECRET_TEST_FILE"] = str(self.secret_file)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_helper(self, action: str, secret: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), action],
            input=secret,
            text=True,
            capture_output=True,
            env=self.environment,
            check=False,
        )

    def test_status_reports_only_boolean_presence_across_lifecycle(self) -> None:
        missing = self.run_helper("status")
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertEqual(missing.stdout.strip(), "WEATHER_SECRET_CONFIGURED=0")

        secret = "test-weather-key-123456"
        stored = self.run_helper("set", secret + "\n")
        self.assertEqual(stored.returncode, 0, stored.stderr)
        self.assertNotIn(secret, stored.stdout + stored.stderr)

        configured = self.run_helper("status")
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertEqual(configured.stdout.strip(), "WEATHER_SECRET_CONFIGURED=1")
        self.assertNotIn(secret, configured.stdout + configured.stderr)

        removed = self.run_helper("remove")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertNotIn(secret, removed.stdout + removed.stderr)

        absent_again = self.run_helper("status")
        self.assertEqual(absent_again.returncode, 0, absent_again.stderr)
        self.assertEqual(absent_again.stdout.strip(), "WEATHER_SECRET_CONFIGURED=0")

    def test_duplicate_or_malformed_assignments_are_not_reported_configured(self) -> None:
        first = "fake-one"
        second = "fake-two"
        self.secret_file.write_text(
            f'WEATHER_UNDERGROUND_API_KEY="{first}"\n'
            f'WEATHER_UNDERGROUND_API_KEY="{second}"\n',
            encoding="utf-8",
        )
        self.secret_file.chmod(0o600)

        duplicate = self.run_helper("status")
        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        self.assertEqual(duplicate.stdout.strip(), "WEATHER_SECRET_CONFIGURED=0")
        self.assertNotIn(first, duplicate.stdout + duplicate.stderr)
        self.assertNotIn(second, duplicate.stdout + duplicate.stderr)

        malformed = "fake-malformed"
        self.secret_file.write_text(
            f"WEATHER_UNDERGROUND_API_KEY={malformed}\n",
            encoding="utf-8",
        )
        self.secret_file.chmod(0o600)
        result = self.run_helper("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "WEATHER_SECRET_CONFIGURED=0")
        self.assertNotIn(malformed, result.stdout + result.stderr)

    def test_symlink_is_rejected_without_secret_disclosure(self) -> None:
        secret = "symlink-secret-value"
        backing = Path(self.temporary.name) / "backing.env"
        backing.write_text(f'WEATHER_UNDERGROUND_API_KEY="{secret}"\n', encoding="utf-8")
        backing.chmod(0o600)
        self.secret_file.symlink_to(backing)

        result = self.run_helper("status")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(secret, result.stdout + result.stderr)


class ManagedWeatherSecretVerifierContractTests(unittest.TestCase):
    def test_status_helper_validates_production_metadata_without_printing_secret(self) -> None:
        source = HELPER.read_text(encoding="utf-8")
        self.assertIn('argv[1] not in {"set", "remove", "status"}', source)
        self.assertIn("WEATHER_SECRET_CONFIGURED=", source)
        self.assertIn("stat.S_IMODE(metadata.st_mode) != 0o600", source)
        self.assertIn("metadata.st_uid != 0 or metadata.st_gid != 0", source)
        self.assertIn("len(assignments) != 1", source)
        self.assertNotIn("print(secret", source)

    def test_restricted_helper_installer_allows_presence_only_status(self) -> None:
        source = HELPER_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET status", source)
        self.assertIn(
            'verify_contains "$WEATHER_SUDOERS" "$PROJECT_USER ALL=(root) NOPASSWD: $WEATHER_TARGET status"',
            source,
        )

    def test_appliance_verifier_uses_managed_status_when_no_override_is_supplied(self) -> None:
        source = VERIFIER.read_text(encoding="utf-8")
        self.assertIn(
            'WEATHER_SECRET_HELPER="${WEATHER_SECRET_HELPER:-/usr/local/bin/a-clockwork-plex-weather-secret}"',
            source,
        )
        self.assertIn('sudo -n "$WEATHER_SECRET_HELPER" status', source)
        self.assertIn("[[ \"$output\" == 'WEATHER_SECRET_CONFIGURED=1' ]]", source)
        self.assertIn("elif managed_wu_credential_configured; then", source)
        self.assertIn("managed root-owned credential is configured (value hidden)", source)
        self.assertNotIn('provide --weather-api-key-file PATH or set $wu_key_env', source)

    def test_clean_room_runbook_keeps_no_secret_verifier_command(self) -> None:
        source = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("--weather-observations weather-underground", source)
        self.assertNotIn("--weather-api-key-file", source)


if __name__ == "__main__":
    unittest.main()
