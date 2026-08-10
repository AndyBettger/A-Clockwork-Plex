from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight-appliance.sh"
INSTALLER = ROOT / "install.sh"
PREREQS = ROOT / "installer" / "lib" / "prerequisites.sh"


class AppliancePreflightTests(unittest.TestCase):
    def run_preflight(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PREFLIGHT), *arguments],
            cwd=ROOT,
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

    def test_root_plan_accepts_explicit_project_user_and_points_to_host_gate(self) -> None:
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
        self.assertIn("Project user:          bedroomclock", result.stdout)
        self.assertIn("Fresh-Pi prerequisite contract", result.stdout)
        self.assertIn("Plexamp Headless", result.stdout)
        self.assertIn("external appliance prerequisite", result.stdout)
        self.assertIn("scripts/preflight-appliance.sh", result.stdout)
        self.assertIn(
            "install-dashboard-service.sh --check --project-user bedroomclock",
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
