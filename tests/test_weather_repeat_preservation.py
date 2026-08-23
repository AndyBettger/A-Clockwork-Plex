from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WeatherRepeatPreservationTests(unittest.TestCase):
    def test_changed_shell_scripts_are_syntax_valid(self) -> None:
        for relative in (
            "setup.sh",
            "appliance-installer.sh",
            "scripts/preflight-appliance.sh",
            "scripts/install-appliance-application.sh",
        ):
            with self.subTest(relative=relative):
                subprocess.run(
                    ["bash", "-n", str(ROOT / relative)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_public_setup_distinguishes_default_from_explicit_weather_choice(self) -> None:
        source = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("WEATHER_OBSERVATIONS_EXPLICIT=false", source)
        self.assertIn("WEATHER_OBSERVATIONS_EXPLICIT=true", source)
        self.assertIn(
            '[[ "$WEATHER_OBSERVATIONS_EXPLICIT" == false && -f "$REPO_ROOT/config.json"',
            source,
        )
        self.assertIn("args+=(--preserve-weather-observations)", source)

    def test_lower_installer_resolves_preserved_provider_from_config(self) -> None:
        source = (ROOT / "appliance-installer.sh").read_text(encoding="utf-8")
        self.assertIn("--preserve-weather-observations", source)
        self.assertIn('provider = data.get("weather", {}).get("provider")', source)
        self.assertIn('ecowitt_push) WEATHER_OBSERVATIONS=ecowitt-push', source)
        self.assertIn('weather_underground) WEATHER_OBSERVATIONS=weather-underground', source)
        self.assertIn(
            'export ACP_PRESERVE_WEATHER_OBSERVATIONS="$PRESERVE_WEATHER_OBSERVATIONS"',
            source,
        )

    def test_preserved_wu_preflight_uses_boolean_managed_secret_status(self) -> None:
        source = (ROOT / "scripts/preflight-appliance.sh").read_text(encoding="utf-8")
        self.assertIn('"$WEATHER_SECRET_HELPER" status', source)
        self.assertIn("WEATHER_SECRET_CONFIGURED=1", source)
        self.assertIn("commissioned profile will be preserved", source)

    def test_application_preservation_skips_weather_owner_but_keeps_verifier(self) -> None:
        source = (ROOT / "scripts/install-appliance-application.sh").read_text(encoding="utf-8")
        self.assertIn(
            "Preserving commissioned Weather configuration and managed credential",
            source,
        )
        self.assertIn('if [[ "$PRESERVE_WEATHER_OBSERVATIONS" == true ]]; then', source)
        self.assertIn("scripts/install-weather-config.sh", source)
        self.assertIn("scripts/verify-appliance.sh", source)
        self.assertIn(
            'if [[ "$WEATHER_PROVIDER" == weather-underground && "$PRESERVE_WEATHER_OBSERVATIONS" != true ]]; then',
            source,
        )


if __name__ == "__main__":
    unittest.main()
