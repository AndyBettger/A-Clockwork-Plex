from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-appliance-packages.sh"
INSTALLER = ROOT / "install.sh"
LIBRARY = ROOT / "installer" / "lib" / "packages.sh"


class AppliancePackageOwnershipTests(unittest.TestCase):
    def run_checker(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CHECKER), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_source_only_contract_accepts_all_profile_combinations(self) -> None:
        for audio in ("direct", "eq"):
            for weather in ("ecowitt-push", "weather-underground"):
                with self.subTest(audio=audio, weather=weather):
                    result = self.run_checker(
                        "--source-only",
                        "--audio",
                        audio,
                        "--weather-observations",
                        weather,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("APPLIANCE_PACKAGE_CHECK=SOURCE-PASS", result.stdout)
                    self.assertIn("No host package state was probed", result.stdout)
                    self.assertIn("No package, Python environment", result.stdout)

    def test_package_contract_has_explicit_ownership_boundaries(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")

        for package in (
            "git",
            "curl",
            "python3",
            "python3-venv",
            "alsa-utils",
            "shairport-sync",
            "chromium",
        ):
            self.assertRegex(source, rf"(?m)^\s*{re.escape(package)}\s*$")
        self.assertIn("requirements.txt", source)
        self.assertIn("Plexamp Headless distribution", source)
        self.assertIn("never silently downloaded", source)
        self.assertIn(
            "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
            source,
        )

    def test_root_plan_prints_package_contract_and_read_only_check(self) -> None:
        result = subprocess.run(
            ["bash", str(INSTALLER), "--audio", "eq"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Package and artifact ownership", result.stdout)
        self.assertIn("python3-venv", result.stdout)
        self.assertIn("Plexamp Headless distribution", result.stdout)
        self.assertIn("check-appliance-packages.sh", result.stdout)
        self.assertIn("No production file", result.stdout)

    def test_package_checker_is_statically_read_only(self) -> None:
        source = CHECKER.read_text(encoding="utf-8")

        # Ignore literal help/report heredoc bodies: words such as "pip install"
        # there describe forbidden behaviour rather than execute it. Scan only
        # shell program lines for mutating command entrypoints.
        executable_lines: list[str] = []
        heredoc_terminator: str | None = None
        heredoc_start = re.compile(r"<<-?['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
        for line in source.splitlines():
            if heredoc_terminator is not None:
                if line.strip() == heredoc_terminator:
                    heredoc_terminator = None
                continue
            executable_lines.append(line)
            match = heredoc_start.search(line)
            if match:
                heredoc_terminator = match.group(1)

        executable_source = "\n".join(executable_lines)
        mutation = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:apt(?:-get)?\s+(?:update|upgrade|install|remove|purge)|"
            r"dpkg\s+-i|pip(?:3)?\s+install|python3\s+-m\s+pip\s+install|install|cp|mv|rm|"
            r"chmod|chown|systemctl\s+(?:start|stop|restart|enable|disable|daemon-reload)|"
            r"modprobe|curl\s+https?://|wget\s+https?://)\b"
        )
        self.assertIsNone(mutation.search(executable_source))
        self.assertIn("dpkg-query", source)
        self.assertIn("apt-cache show", source)
        self.assertNotIn("apt-cache update", source)

    def test_direct_profile_does_not_claim_camilladsp_requirement(self) -> None:
        direct = self.run_checker("--source-only", "--audio", "direct")
        eq = self.run_checker("--source-only", "--audio", "eq")

        self.assertIn("not required by the Direct profile", direct.stdout)
        self.assertIn("CamillaDSP 4.1.3", eq.stdout)

    def test_invalid_profile_is_rejected(self) -> None:
        result = self.run_checker("--source-only", "--audio", "mystery")
        self.assertEqual(result.returncode, 64)


if __name__ == "__main__":
    unittest.main()
