from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.stage_c_package import runtime_templates
from scripts.stage_c_package.templates import HostContract


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = REPO_ROOT / "scripts/stage_c_transaction/candidate_validation_rehearsal_adapter.py"


class StageCCandidateValidationSystemdRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ADAPTER.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_private_unit_path_includes_default_dependency_targets(self) -> None:
        for name in ("sysinit.target", "basic.target", "shutdown.target"):
            self.assertIn(f'"{name}"', self.source)
        self.assertIn('env["SYSTEMD_UNIT_PATH"] = str(unit_dir)', self.source)
        self.assertNotIn('env["SYSTEMD_UNIT_PATH"] = f"{unit_dir}:"', self.source)

    def test_failed_validator_output_is_retained_outside_transaction(self) -> None:
        self.assertIn('FAILED_VALIDATION_ROOT_NAME = "failed-validation"', self.source)
        self.assertIn("root = self._evidence_root / FAILED_VALIDATION_ROOT_NAME", self.source)
        self.assertIn("os.chown(target, 0, 0)", self.source)
        self.assertIn("target.chmod(0o600)", self.source)
        for name in (
            "aplay-{name}.txt",
            "visudo.txt",
            "systemd-analyze.txt",
            "camilladsp-check.txt",
        ):
            self.assertIn(name, self.source)

    def test_systemd_failure_detail_contains_retained_path_and_diagnostic(self) -> None:
        method = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "CandidateValidationRehearsalAdapter"
        )
        validator = next(
            node
            for node in method.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "validate_candidate_units"
        )
        text = ast.get_source_segment(self.source, validator) or ""
        self.assertIn("retained = self._retain_failed_command", text)
        self.assertIn("self._failure_summary(result)", text)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze unavailable")
    def test_exact_private_systemd_model_verifies_without_host_unit_path(self) -> None:
        contract = HostContract(project_user="andy")
        units = {
            "a-clockwork-plex-audio-route.service": runtime_templates.route_unit(),
            "a-clockwork-plex-camilladsp.service": runtime_templates.camilladsp_unit(contract),
            "a-clockwork-plex-audio-failback.service": runtime_templates.failback_unit(),
        }
        with tempfile.TemporaryDirectory() as temporary:
            unit_dir = Path(temporary)
            for name, text in units.items():
                rewritten = "\n".join(
                    "ExecStart=/bin/true" if line.startswith("ExecStart=") else line
                    for line in text.splitlines()
                    if not line.startswith(("User=", "Group="))
                ) + "\n"
                (unit_dir / name).write_text(rewritten, encoding="utf-8")
            for name in (
                "plexamp.service",
                "shairport-sync.service",
                "a-clockwork-plex.service",
                "systemd-modules-load.service",
            ):
                (unit_dir / name).write_text(
                    "[Unit]\nDescription=Stage C16 validation stub\n"
                    "[Service]\nType=oneshot\nExecStart=/bin/true\n",
                    encoding="utf-8",
                )
            for name in (
                "sound.target",
                "multi-user.target",
                "sysinit.target",
                "basic.target",
                "shutdown.target",
            ):
                (unit_dir / name).write_text(
                    "[Unit]\nDescription=Stage C16 validation target\n",
                    encoding="utf-8",
                )
            env = os.environ.copy()
            env["SYSTEMD_UNIT_PATH"] = str(unit_dir)
            result = subprocess.run(
                (
                    shutil.which("systemd-analyze") or "systemd-analyze",
                    "verify",
                    *(str(unit_dir / name) for name in units),
                ),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=30,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout={result.stdout}\nstderr={result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
