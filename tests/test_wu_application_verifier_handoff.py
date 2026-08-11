from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-application.sh"
VERIFIER = ROOT / "scripts" / "verify-appliance.sh"

BASE_CONFIG = '''general =
{
    name = "WU Test Clock";
    interpolation = "soxr";
};

alsa =
{
    output_device = "old-output";
    mixer_control_name = "Master";
};
'''


class WeatherUndergroundApplicationVerifierHandoffTests(unittest.TestCase):
    def make_fixture(self, directory: str) -> tuple[Path, dict[str, str]]:
        root = Path(directory) / "root"
        (root / "project").mkdir(parents=True)
        (root / "tmp").mkdir(parents=True)
        shairport = root / "etc/shairport-sync.conf"
        shairport.parent.mkdir(parents=True)
        shairport.write_text(BASE_CONFIG, encoding="utf-8")
        shairport.chmod(0o640)

        fake_bin = Path(directory) / "fake-bin"
        fake_bin.mkdir()
        for name in ("systemd-analyze", "desktop-file-validate"):
            path = fake_bin / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)

        validator = Path(directory) / "fake-shairport-sync"
        validator.write_text(
            "#!/bin/bash\nprintf '%s\\n' '>> Display Config End.'\nexit 0\n",
            encoding="utf-8",
        )
        validator.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
        env["ACP_AIRPLAY_TEST_SHAIRPORT_BINARY"] = str(validator)
        env.pop("WEATHER_UNDERGROUND_API_KEY", None)
        return root, env

    def test_first_wu_application_transaction_passes_key_file_to_final_verifier_without_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, env = self.make_fixture(directory)
            key_file = Path(directory) / "wu-api-key"
            secret = "first-install-secret-must-never-appear"
            key_file.write_text(secret + "\n", encoding="utf-8")
            key_file.chmod(0o600)

            result = subprocess.run(
                [
                    "bash",
                    str(INSTALLER),
                    "--root",
                    str(root),
                    "--project-user",
                    "testclock",
                    "--project-dir",
                    "/project",
                    "--audio",
                    "direct",
                    "--weather-observations",
                    "weather-underground",
                    "--wu-station-id",
                    "ITEST1",
                    "--wu-api-key-file",
                    str(key_file),
                    "--activate",
                    "--confirm",
                    "INSTALL-APPLIANCE-APPLICATION",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("APPLIANCE_VERIFY=PASS", result.stdout)
            self.assertIn("APPLICATION_TRANSACTION=COMMITTED", result.stdout)
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, result.stderr)

            config = (root / "project/config.json").read_text(encoding="utf-8")
            self.assertIn('"provider": "weather_underground"', config)
            self.assertIn('"station_id": "ITEST1"', config)
            self.assertIn('"api_key_env": "WEATHER_UNDERGROUND_API_KEY"', config)
            self.assertNotIn(secret, config)

    def test_application_and_verifier_share_key_file_path_contract(self) -> None:
        application = INSTALLER.read_text(encoding="utf-8")
        verifier = VERIFIER.read_text(encoding="utf-8")

        self.assertIn('verify_args+=(--weather-api-key-file "$WU_API_KEY_FILE")', application)
        self.assertNotIn('WEATHER_UNDERGROUND_API_KEY="$wu_verify_key"', application)
        self.assertNotIn("run_final_verifier()", application)

        self.assertIn("--weather-api-key-file", verifier)
        self.assertIn("valid_wu_key_file()", verifier)
        self.assertIn("value is validated but never displayed", verifier)
        self.assertIn("credential file is readable and structurally valid (value hidden)", verifier)
        self.assertNotIn("cat \"$WU_KEY_FILE\"", verifier)

    def test_verifier_rejects_key_file_option_for_ecowitt_before_filesystem_checks(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(VERIFIER),
                "--audio",
                "direct",
                "--weather-observations",
                "ecowitt-push",
                "--weather-api-key-file",
                "/tmp/not-used",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("only valid with", result.stderr)


if __name__ == "__main__":
    unittest.main()
