from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight-appliance.sh"
INSTALLER = ROOT / "install.sh"
PREREQS = ROOT / "installer" / "lib" / "prerequisites.sh"


class AppliancePreflightTests(unittest.TestCase):
    def run_preflight(
        self,
        *arguments: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PREFLIGHT), *arguments],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_source_only_preflight_accepts_all_four_profile_combinations(self) -> None:
        for audio in ("direct", "eq"):
            for weather in ("ecowitt-push", "weather-underground"):
                with self.subTest(audio=audio, weather=weather):
                    result = self.run_preflight(
                        "--source-only",
                        "--audio",
                        audio,
                        "--weather-observations",
                        weather,
                        "--project-user",
                        "testuser",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(f"Audio profile:        {audio}", result.stdout)
                    self.assertIn(f"Weather observations: {weather}", result.stdout)
                    self.assertIn("APPLIANCE_PREFLIGHT=SOURCE-PASS", result.stdout)
                    self.assertIn("No host prerequisite was probed", result.stdout)
                    self.assertIn("No production file", result.stdout)

    def test_profile_specific_prerequisites_are_truthful(self) -> None:
        direct = self.run_preflight(
            "--source-only", "--audio", "direct", "--project-user", "andy"
        )
        eq = self.run_preflight(
            "--source-only", "--audio", "eq", "--project-user", "andy"
        )
        wu = self.run_preflight(
            "--source-only",
            "--weather-observations",
            "weather-underground",
            "--project-user",
            "andy",
        )

        self.assertIn("EQ artifact:         not required for Direct audio", direct.stdout)
        self.assertIn("verified CamillaDSP 4.1.3", eq.stdout)
        self.assertIn("snd_aloop module available", eq.stdout)
        self.assertIn("server environment variable", wu.stdout)
        self.assertIn("never config.json/browser", wu.stdout)
        self.assertNotIn("WEATHER_UNDERGROUND_API_KEY=", wu.stdout)

    def test_bootstrap_pending_contract_is_host_only_and_preserves_compatibility_gate(self) -> None:
        source = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn("--bootstrap-pending", source)
        self.assertIn("APPLIANCE_PREFLIGHT=PLATFORM-PASS", source)
        self.assertIn("owned package bootstrap will install this prerequisite", source)
        self.assertIn("missing after package bootstrap", source)
        self.assertIn("shairport-sync package/service is owned by package bootstrap", source)
        self.assertIn("shairport-sync.service is not installed after package bootstrap", source)
        self.assertIn(
            "current compatibility/full gate still requires Plexamp",
            source,
        )

        invalid = self.run_preflight("--source-only", "--bootstrap-pending", "--audio", "direct")
        self.assertEqual(invalid.returncode, 64)
        self.assertIn("cannot be combined", invalid.stderr)

    def test_fresh_stage_zero_marks_future_owned_hardware_and_player_ready_only(self) -> None:
        result = self.run_preflight(
            "--fresh-bootstrap-pending",
            "--audio",
            "direct",
            "--project-user",
            os.environ.get("USER", "runner"),
        )

        # CI is not the target aarch64 Raspberry Pi, so the overall host report
        # can fail. The important contract is that not-yet-run owners are READY,
        # not falsely PASS and not prematurely FAIL.
        self.assertIn("Mode:                 fresh-bootstrap-stage-zero", result.stdout)
        self.assertIn("READY plexamp-service", result.stdout)
        self.assertIn("guarded Plexamp compatibility-runtime owner has not run yet", result.stdout)
        self.assertIn("READY dac-card", result.stdout)
        self.assertIn("guarded platform-hardware owner has not commissioned", result.stdout)
        self.assertIn("READY pn532-i2c", result.stdout)
        self.assertIn("bus 1 address 0x24", result.stdout)
        self.assertNotIn("PASS  pn532-i2c", result.stdout)

    def test_player_pending_requires_hardware_but_allows_only_player_to_remain_pending(self) -> None:
        source = PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("--player-pending", source)
        self.assertIn("APPLIANCE_PREFLIGHT=HARDWARE-PASS-PLAYER-PENDING", source)
        self.assertIn("PN532 not found on I2C bus 1 address 0x24 after hardware bootstrap", source)
        self.assertIn("ALSA card id Pro not found", source)
        self.assertIn("guarded Plexamp compatibility-runtime owner has not run yet", source)
        self.assertIn('sudo -- i2cdetect -y 1 0x24 0x24', source)

        invalid = self.run_preflight(
            "--bootstrap-pending",
            "--player-pending",
            "--audio",
            "direct",
        )
        self.assertEqual(invalid.returncode, 64)
        self.assertIn("Choose only one staged host mode", invalid.stderr)

    def test_fresh_wu_preflight_accepts_secret_file_without_exposing_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "wu-key"
            secret_value = "preflight-secret-must-not-leak"
            secret.write_text(secret_value + "\n", encoding="utf-8")
            secret.chmod(0o600)
            env = os.environ.copy()
            env.pop("WEATHER_UNDERGROUND_API_KEY", None)

            result = self.run_preflight(
                "--audio",
                "direct",
                "--weather-observations",
                "weather-underground",
                "--weather-api-key-file",
                str(secret),
                env=env,
            )

        # CI is not an aarch64 appliance, so the whole host report is expected
        # to fail other hardware checks. The credential check itself must pass.
        self.assertIn("PASS  weather-credential", result.stdout)
        self.assertIn("fresh-install API-key file is readable", result.stdout)
        self.assertNotIn(secret_value, result.stdout)
        self.assertNotIn(secret_value, result.stderr)

    def test_wu_preflight_without_file_or_existing_environment_fails_credential_check(self) -> None:
        env = os.environ.copy()
        env.pop("WEATHER_UNDERGROUND_API_KEY", None)
        result = self.run_preflight(
            "--audio",
            "direct",
            "--weather-observations",
            "weather-underground",
            env=env,
        )
        self.assertIn("FAIL  weather-credential", result.stdout)
        self.assertIn("--weather-api-key-file PATH", result.stdout)

    def test_wu_key_file_option_is_rejected_for_ecowitt(self) -> None:
        result = self.run_preflight(
            "--source-only",
            "--audio",
            "direct",
            "--weather-observations",
            "ecowitt-push",
            "--weather-api-key-file",
            "/tmp/not-used",
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("only valid with", result.stderr)

    def test_root_plan_accepts_explicit_project_user_and_points_to_both_host_gates(self) -> None:
        result = subprocess.run(
            [
                "bash",
                str(INSTALLER),
                "--project-user",
                "bedroomclock",
                "--audio",
                "direct",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"Project user:\s+bedroomclock")
        self.assertIn("Fresh-Pi prerequisite contract", result.stdout)
        self.assertIn("Plexamp Headless", result.stdout)
        self.assertIn("external appliance prerequisite", result.stdout)
        self.assertIn("scripts/preflight-appliance.sh --bootstrap-pending", result.stdout)
        self.assertIn(
            "scripts/preflight-appliance.sh --audio direct --weather-observations ecowitt-push --project-user bedroomclock",
            result.stdout,
        )
        self.assertIn(
            "install-dashboard-integration.sh --prepare-only --project-user bedroomclock",
            result.stdout,
        )

    def test_preflight_is_statically_read_only(self) -> None:
        source = PREFLIGHT.read_text(encoding="utf-8")
        mutating = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:apt|apt-get|install|cp|mv|rm|chmod|chown|"
            r"mkfifo|mkdir|systemctl\s+(?:start|stop|restart|enable|disable)|"
            r"modprobe|tee)\b"
        )
        self.assertIsNone(mutating.search(source))
        self.assertNotIn("> /etc/", source)
        self.assertNotIn("> /usr/local/", source)
        self.assertNotIn("systemctl daemon-reload", source)

    def test_preflight_rejects_invalid_profiles_and_unsafe_names(self) -> None:
        bad_audio = self.run_preflight("--source-only", "--audio", "mystery")
        bad_weather = self.run_preflight(
            "--source-only", "--weather-observations", "mystery"
        )
        bad_user = self.run_preflight(
            "--source-only", "--project-user", "bad user"
        )
        bad_env = self.run_preflight(
            "--source-only", "--weather-api-key-env", "BAD-NAME"
        )

        for result in (bad_audio, bad_weather, bad_user, bad_env):
            self.assertEqual(result.returncode, 64)

    def test_prerequisite_library_contains_no_activation_path(self) -> None:
        source = PREREQS.read_text(encoding="utf-8")
        mutating = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:apt|apt-get|install|cp|mv|rm|chmod|chown|"
            r"systemctl|modprobe|tee)\b"
        )
        self.assertIn("acp_prerequisite_plan", source)
        self.assertIsNone(mutating.search(source))


if __name__ == "__main__":
    unittest.main()
