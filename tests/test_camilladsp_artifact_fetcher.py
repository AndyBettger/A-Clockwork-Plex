from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FETCHER = ROOT / "scripts" / "fetch-camilladsp-4.1.3.sh"
ARCHIVE_SHA = "d9a17092923ebfe5d20a770c6b6a7eb2268f9700f999bf604b9db09f518aca5a"
BINARY_SHA = "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa"


class CamillaDspArtifactFetcherTests(unittest.TestCase):
    def test_shell_syntax_and_prepare_only_are_inert(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(FETCHER)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = subprocess.run(
            ["bash", str(FETCHER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Version:           4.1.3", result.stdout)
        self.assertIn(ARCHIVE_SHA, result.stdout)
        self.assertIn(BINARY_SHA, result.stdout)
        self.assertIn("Prepare-only complete", result.stdout)

    def test_fetcher_pins_official_release_and_accepted_executable(self) -> None:
        source = FETCHER.read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/HEnquist/camilladsp/releases/download/v${VERSION}/${ARCHIVE}",
            source,
        )
        self.assertIn(f"ARCHIVE_SHA256={ARCHIVE_SHA}", source)
        self.assertIn(f"BINARY_SHA256={BINARY_SHA}", source)
        self.assertIn("camilladsp-linux-aarch64.tar.gz", source)
        self.assertIn("Archive SHA-256 verified", source)
        self.assertIn("CamillaDSP executable SHA-256 mismatch", source)
        self.assertIn("--version", source)

    def test_fetcher_is_user_artifact_only_not_system_installer(self) -> None:
        source = FETCHER.read_text(encoding="utf-8")
        for forbidden in (
            "sudo ",
            "systemctl ",
            "apt-get ",
            "apt ",
            "/usr/local/bin",
            "rpi-update",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("$HOME/.cache/a-clockwork-plex/artifacts", source)
        self.assertIn("CAMILLA_BINARY=", source)

    def test_digest_verification_precedes_extraction_and_live_swap(self) -> None:
        source = FETCHER.read_text(encoding="utf-8")
        archive_check = source.index('[[ "$observed_archive" == "$ARCHIVE_SHA256" ]]')
        extraction = source.index('tar -xzf "$DOWNLOAD"')
        binary_check = source.index('[[ "$observed_binary" == "$BINARY_SHA256" ]]')
        live_swap = source.index('mv -- "$EXTRACT" "$DESTINATION"')
        self.assertLess(archive_check, extraction)
        self.assertLess(extraction, binary_check)
        self.assertLess(binary_check, live_swap)

    def test_activation_requires_explicit_confirmation(self) -> None:
        result = subprocess.run(
            ["bash", str(FETCHER), "--activate", "--confirm", "WRONG"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 64)
        self.assertIn("FETCH-CAMILLADSP-4.1.3", result.stderr)


if __name__ == "__main__":
    unittest.main()
