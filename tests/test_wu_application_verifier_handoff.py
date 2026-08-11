from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-appliance-application.sh"

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

    def test_first_wu_application_transaction_hands_secret_only_to_final_verifier(self) -> None:
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

    def test_source_keeps_secret_off_verifier_command_line(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("run_final_verifier()", source)
        self.assertIn('WEATHER_UNDERGROUND_API_KEY="$wu_verify_key"', source)
        self.assertIn('python3 - "$WU_API_KEY_FILE"', source)
        self.assertNotIn('--weather-api-key "$wu_verify_key"', source)
        self.assertNotIn('echo "$wu_verify_key"', source)


if __name__ == "__main__":
    unittest.main()
