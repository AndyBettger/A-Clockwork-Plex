from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-plexamp-runtime.sh"
LIBRARY = ROOT / "installer" / "lib" / "plexamp_runtime.sh"
CONFIRMATION = "INSTALL-PLEXAMP-RUNTIME"
NODE_SHA = "73093db209e4e9e09dd7d15a47aeaab1b74833830df03efa5f942a1122c5fa71"


class PlexampRuntimeInstallerTests(unittest.TestCase):
    def run_installer(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALLER), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_shell_syntax_and_prepare_only_are_inert(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", str(INSTALLER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

        result = self.run_installer("--project-user", "clockuser")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Plexamp version:   4.13.2", result.stdout)
        self.assertIn("Node version:      20.20.2", result.stdout)
        self.assertIn(NODE_SHA, result.stdout)
        self.assertIn("Artifact gate: BLOCKED", result.stdout)
        self.assertIn("No network request", result.stdout)

    def test_runtime_contract_pins_node_and_exact_plexamp_url_but_not_fake_digest(self) -> None:
        source = LIBRARY.read_text(encoding="utf-8")

        self.assertIn("ACP_PLEXAMP_VERSION=4.13.2", source)
        self.assertIn(
            'ACP_PLEXAMP_ARCHIVE_URL="https://plexamp.plex.tv/headless/${ACP_PLEXAMP_ARCHIVE}"',
            source,
        )
        self.assertIn('ACP_PLEXAMP_ARCHIVE_SHA256=""', source)
        self.assertIn("ACP_NODE_VERSION=20.20.2", source)
        self.assertIn("ACP_NODE_PLATFORM=linux-arm64", source)
        self.assertIn(NODE_SHA, source)
        self.assertIn("nodejs.org/dist", source)

    def test_activation_requires_confirmation_then_fails_before_any_mutation(self) -> None:
        wrong = self.run_installer("--activate", "--confirm", "WRONG")
        self.assertEqual(wrong.returncode, 64)

        blocked = self.run_installer(
            "--activate",
            "--confirm",
            CONFIRMATION,
            "--project-user",
            "clockuser",
        )
        self.assertEqual(blocked.returncode, 78)
        self.assertIn("PLEXAMP_RUNTIME=ARTIFACT-PIN-REQUIRED", blocked.stdout)
        self.assertIn("MUTATION=NOT-ATTEMPTED", blocked.stdout)

        source = INSTALLER.read_text(encoding="utf-8")
        guard = source.index("if ! acp_plexamp_runtime_artifact_pinned")
        self.assertLess(guard, source.index("PLEXAMP_RUNTIME=INSTALLER-IMPLEMENTATION-REQUIRED"))

    def test_blocked_entrypoint_contains_no_network_or_host_mutation_path(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        executable_mutation = re.compile(
            r"(?m)^\s*(?:sudo\s+)?(?:curl|wget|tar|apt|apt-get|install|cp|mv|rm|"
            r"chmod|chown|mkdir|systemctl|tee)\b"
        )
        self.assertIsNone(executable_mutation.search(source))
        self.assertNotIn("curl | bash", source)
        self.assertNotIn("nodesource", source.lower())
        self.assertNotIn("nvm install", source)

    def test_claim_material_has_no_command_line_option(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        library = LIBRARY.read_text(encoding="utf-8")

        self.assertNotIn("--claim", source)
        self.assertNotIn("--token", source)
        self.assertIn("interactive authentication boundary", library)
        self.assertIn("never accepted as a normal command-line argument", library)


if __name__ == "__main__":
    unittest.main()
