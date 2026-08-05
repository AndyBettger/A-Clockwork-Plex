from __future__ import annotations

import ast
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "scripts" / "stage_c_runtime_authority"
WRAPPER = ROOT / "scripts" / "test-stage-c-runtime-authority-core.sh"
FILES = tuple(sorted(PACKAGE.glob("*.py")))
FILESYSTEM_BOUNDARY_FILES = {
    PACKAGE / "linux_runtime_filesystem.py",
    PACKAGE / "install_runtime_filesystem.py",
}
PROCESS_BOUNDARY_FILES = {
    PACKAGE / "linux_runtime_process.py",
    PACKAGE / "install_runtime_process.py",
}
HOST_BOUNDARY_FILES = FILESYSTEM_BOUNDARY_FILES | PROCESS_BOUNDARY_FILES
PURE_FILES = tuple(path for path in FILES if path not in HOST_BOUNDARY_FILES)


class StageCRuntimeAuthoritySafetyTests(unittest.TestCase):
    @staticmethod
    def pure_source() -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in PURE_FILES)

    @staticmethod
    def all_source() -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in FILES)

    def test_modules_compile_and_wrapper_has_valid_shell_syntax(self):
        self.assertGreaterEqual(len(FILES), 5)
        self.assertTrue(HOST_BOUNDARY_FILES.issubset(set(FILES)))
        for path in FILES:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        checked = subprocess.run(["bash", "-n", str(WRAPPER)], capture_output=True, text=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", wrapper)
        self.assertIn("PYTHONPATH=", wrapper)

    def test_core_has_no_host_mutation_or_network_process_boundary(self):
        text = self.pure_source()
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

    def test_filesystem_family_is_explicit_and_has_no_process_boundary(self):
        self.assertEqual(
            FILESYSTEM_BOUNDARY_FILES,
            {
                PACKAGE / "linux_runtime_filesystem.py",
                PACKAGE / "install_runtime_filesystem.py",
            },
        )
        production = (PACKAGE / "linux_runtime_filesystem.py").read_text(encoding="utf-8")
        install = (PACKAGE / "install_runtime_filesystem.py").read_text(encoding="utf-8")
        for required_path in (
            "/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf",
            "/run/lock/a-clockwork-plex-audio-route.lock",
            "/var/lib/a-clockwork-plex/split-bus",
        ):
            self.assertIn(required_path, production)
        self.assertIn("assert_borrowed_transaction_lock", install)
        self.assertIn("pre-commit failure belongs to exact transaction rollback", install)
        for text in (production, install):
            for forbidden_boundary in (
                "subprocess",
                "systemctl",
                "amixer",
                "alsactl",
                "aplay",
                "shell=True",
                "os.system",
                "os.exec",
            ):
                self.assertNotIn(forbidden_boundary, text)
        self.assertIn("class LinuxRuntimeFilesystem", production)
        self.assertIn("class InstallRuntimeFilesystem", install)
        self.assertIn("def __init__(self) -> None", production)
        self.assertIn("def _for_test(cls, root: Path)", production)

    def test_process_family_is_explicit_and_has_one_popen_boundary(self):
        self.assertEqual(
            PROCESS_BOUNDARY_FILES,
            {
                PACKAGE / "linux_runtime_process.py",
                PACKAGE / "install_runtime_process.py",
            },
        )
        production = (PACKAGE / "linux_runtime_process.py").read_text(encoding="utf-8")
        install = (PACKAGE / "install_runtime_process.py").read_text(encoding="utf-8")
        self.assertEqual(production.count("subprocess.Popen"), 1)
        self.assertNotIn("subprocess.Popen", install)
        self.assertIn("shell=False", production)
        for required_path in (
            "/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp",
            "/etc/a-clockwork-plex/camilladsp-split-bus.yml",
            "/dev/snd/pcmC7D1c",
        ):
            self.assertIn(required_path, production)
        for text in (production, install):
            for forbidden_boundary in (
                "systemctl",
                "amixer",
                "alsactl",
                "aplay",
                "shell=True",
                "os.system",
                "os.exec",
                "def dispatch",
                "command:",
                "path_override",
            ):
                self.assertNotIn(forbidden_boundary, text)
        self.assertIn("class LinuxRuntimeProcess", production)
        self.assertIn("class InstallRuntimeProcess", install)
        self.assertIn("def __init__(self) -> None", production)
        self.assertIn("def _for_test(", production)

    def test_all_host_capability_is_confined_to_two_boundary_families(self):
        self.assertEqual(
            HOST_BOUNDARY_FILES,
            {
                PACKAGE / "linux_runtime_filesystem.py",
                PACKAGE / "install_runtime_filesystem.py",
                PACKAGE / "linux_runtime_process.py",
                PACKAGE / "install_runtime_process.py",
            },
        )
        for path in PURE_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("subprocess.Popen", text, path)
            self.assertNotIn("socket.socket", text, path)
            self.assertNotIn("os.replace", text, path)
            self.assertNotIn("fcntl.flock", text, path)

    def test_no_arbitrary_command_path_unit_or_transaction_arguments(self):
        tree = ast.parse(self.pure_source())
        forbidden_parameter_names = {"command", "unit_name", "path_override", "route_name"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = {arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)}
                self.assertTrue(names.isdisjoint(forbidden_parameter_names), (node.name, names))
        self.assertIn("EXPECTED_MANAGED_UNITS", self.pure_source())
        self.assertIn("RuntimeAction", self.pure_source())

    def test_review_is_disposable_only_and_has_no_activation_or_keep_active_mode(self):
        text = self.all_source() + "\n" + WRAPPER.read_text(encoding="utf-8")
        self.assertIn("a-clockwork-plex-stage-c21-runtime-authority.", text)
        self.assertIn("--lab-root must be empty", text)
        self.assertNotIn("--activate", text)
        self.assertNotIn("--keep-active", text)
        self.assertNotIn("--confirm", text)
        self.assertIn("No host observation, sudo, service, route, mixer, PCM or production write occurred.", text)

    def test_approval_record_is_structured_not_a_marker_flag(self):
        text = self.pure_source()
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
