from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "scripts" / "stage_c_runtime_authority"
WRAPPER = ROOT / "scripts" / "test-stage-c-runtime-authority-core.sh"
FILES = tuple(sorted(PACKAGE.glob("*.py")))


class StageCRuntimeAuthoritySafetyTests(unittest.TestCase):
    @staticmethod
    def source() -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in FILES)

    def test_modules_compile_and_wrapper_has_valid_shell_syntax(self):
        self.assertGreaterEqual(len(FILES), 5)
        for path in FILES:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        checked = subprocess.run(["bash", "-n", str(WRAPPER)], capture_output=True, text=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", wrapper)
        self.assertIn("PYTHONPATH=", wrapper)

    def test_core_has_no_host_mutation_or_network_process_boundary(self):
        text = self.source()
        tree = ast.parse(text)
        forbidden_imports = {"subprocess", "socket", "requests", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue({alias.name.split(".")[0] for alias in node.names}.isdisjoint(forbidden_imports))
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0], forbidden_imports)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertNotEqual(node.name, "dispatch")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, "dispatch")
        for forbidden_path in ("/etc/alsa", "/run/lock/a-clockwork-plex-audio-route.lock", "/var/lib/a-clockwork-plex"):
            self.assertNotIn(forbidden_path, text)
        for forbidden_command in ("systemctl", "amixer", "alsactl", "aplay"):
            self.assertNotIn(forbidden_command, text)

    def test_no_arbitrary_command_path_unit_or_transaction_arguments(self):
        tree = ast.parse(self.source())
        forbidden_parameter_names = {"command", "unit_name", "path_override", "route_name"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}
                self.assertTrue(names.isdisjoint(forbidden_parameter_names), (node.name, names))
        self.assertIn("EXPECTED_MANAGED_UNITS", self.source())
        self.assertIn("RuntimeAction", self.source())

    def test_review_is_disposable_only_and_has_no_activation_or_keep_active_mode(self):
        text = self.source() + "\n" + WRAPPER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-stage-c21-runtime-authority.", text)
        self.assertIn("--lab-root must be empty", text)
        self.assertNotIn("--activate", text)
        self.assertNotIn("--keep-active", text)
        self.assertNotIn("--confirm", text)
        self.assertIn("No host observation, sudo, service, route, mixer, PCM or production write occurred.", text)

    def test_approval_record_is_structured_not_a_marker_flag(self):
        text = self.source()
        for required in (
            "schema_version",
            "transaction_id",
            "lock_lease_id",
            "package_fingerprint",
            "commit_manifest_sha256",
            "active_route_sha256",
            "camilladsp_config_sha256",
            "camilladsp_binary_sha256",
            "loopback_pcm_substreams",
            "dac_card",
            "sample_format",
            "record_sha256",
        ):
            self.assertIn(required, text)
        self.assertIn("RENAME_EXCHANGE", text)
        self.assertIn("os.O_NOFOLLOW", text)
        self.assertIn("os.O_EXCL", text)


if __name__ == "__main__":
    unittest.main()
