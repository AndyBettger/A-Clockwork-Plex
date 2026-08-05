from __future__ import annotations

import ast
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.stage_c_transaction import locked_snapshot
from scripts.stage_c_transaction.locked_snapshot import (
    EXPECTED_STAGE_C5_CHECKS,
    REQUIRED_CONFIRMATION,
    SNAPSHOT_PREFIX,
    acquire_rehearsal_lock,
    inspect_production_lock_boundary,
    prove_lock_contention,
    validate_snapshot_root,
)


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "test-stage-c-locked-privileged-snapshot.sh"
ENGINE = ROOT / "scripts" / "stage_c_transaction" / "locked_snapshot.py"


class StageCLockedPrivilegedSnapshotSafetyTests(unittest.TestCase):
    def test_wrapper_and_engine_syntax(self):
        shell = subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(shell.returncode, 0, shell.stderr)
        compile(ENGINE.read_text(encoding="utf-8"), str(ENGINE), "exec")

    def test_prepare_only_has_no_privileged_execution(self):
        with tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c1-review-test.", dir="/var/tmp"
        ) as package_dir, tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c3-snapshot.test.", dir="/var/tmp"
        ) as c3_dir, tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c4-sandbox.test.", dir="/var/tmp"
        ) as c4_dir, tempfile.TemporaryDirectory(
            prefix="a-clockwork-plex-stage-c5-review.test.", dir="/var/tmp"
        ) as c5_dir:
            package = Path(package_dir)
            c3 = Path(c3_dir)
            c4 = Path(c4_dir)
            c5 = Path(c5_dir)
            (package / "rootfs").mkdir()
            (package / "manifest.tsv").write_text("placeholder\n", encoding="utf-8")
            (c3 / "results.tsv").write_text("placeholder\n", encoding="utf-8")
            (c3 / "evidence-manifest.tsv").write_text("placeholder\n", encoding="utf-8")
            (c4 / "scenario-state.tsv").write_text("placeholder\n", encoding="utf-8")
            (c4 / "evidence-manifest.tsv").write_text("placeholder\n", encoding="utf-8")
            (c5 / "transaction-state-machine.tsv").write_text(
                "placeholder\n", encoding="utf-8"
            )
            (c5 / "evidence-manifest.tsv").write_text("placeholder\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "bash",
                    str(WRAPPER),
                    "--package-root",
                    str(package),
                    "--stage-c3-root",
                    str(c3),
                    "--stage-c4-root",
                    str(c4),
                    "--stage-c5-root",
                    str(c5),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Prepare-only invoked no sudo", result.stdout)
        self.assertIn("--capture-read-only", result.stdout)
        self.assertIn(REQUIRED_CONFIRMATION, result.stdout)
        self.assertIn("must remain absent", result.stdout)

    def test_wrapper_has_one_constrained_sudo_command(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertEqual(
            len(re.findall(r"(?m)^\s*exec sudo\s+env\s+\\\s*$", text)),
            1,
        )
        self.assertIn("python3 -B -m stage_c_transaction.locked_snapshot", text)
        for forbidden in (
            "--activate)",
            "--install)",
            "--route)",
            "--rollback)",
            "--uninstall)",
            "systemctl ",
            "amixer ",
            "modprobe ",
            "aplay ",
        ):
            self.assertNotIn(forbidden, text)

    def test_engine_cli_is_snapshot_only(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            'parser.add_argument("--package-root"',
            'parser.add_argument("--stage-c3-root"',
            'parser.add_argument("--stage-c4-root"',
            'parser.add_argument("--stage-c5-root"',
            'parser.add_argument("--snapshot-root"',
            'parser.add_argument("--confirm"',
            REQUIRED_CONFIRMATION,
        ):
            self.assertIn(expected, text)
        for forbidden in (
            'add_argument("--activate"',
            'add_argument("--install"',
            'add_argument("--route"',
            'add_argument("--rollback"',
            'add_argument("--uninstall"',
            'add_argument("--transaction-id"',
        ):
            self.assertNotIn(forbidden, text)

    def test_fresh_snapshot_root_is_direct_mode_0700_var_tmp(self):
        with tempfile.TemporaryDirectory(
            prefix=SNAPSHOT_PREFIX, dir="/var/tmp"
        ) as directory:
            root = Path(directory)
            root.chmod(0o700)
            self.assertEqual(validate_snapshot_root(root, os.getuid()), root.resolve())
            root.chmod(0o755)
            with self.assertRaises(SystemExit):
                validate_snapshot_root(root, os.getuid())

        with tempfile.TemporaryDirectory(dir="/var/tmp") as parent:
            parent_path = Path(parent)
            real = parent_path / "real"
            real.mkdir()
            link = Path("/var/tmp") / f"{SNAPSHOT_PREFIX}symlink-test-{os.getpid()}"
            try:
                link.symlink_to(real)
                with self.assertRaises(SystemExit):
                    validate_snapshot_root(link, os.getuid())
            finally:
                link.unlink(missing_ok=True)

    def test_rehearsal_lock_is_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = acquire_rehearsal_lock(root)
            self.assertEqual(stat.S_IMODE(lock.path.stat().st_mode), 0o600)
            prove_lock_contention(lock)
            lock.release()
            self.assertTrue(lock.released)
            second = os.open(lock.path, os.O_RDWR)
            try:
                import fcntl

                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(second, fcntl.LOCK_UN)
            finally:
                os.close(second)

    def test_production_lock_boundary_is_read_only_and_rejects_conflicts(self):
        lock_path = Path("/tmp") / f"acp-stage-c6-lock-test-{os.getpid()}"
        lock_path.unlink(missing_ok=True)
        try:
            with patch.object(locked_snapshot, "PRODUCTION_LOCK", lock_path):
                parent_mode, state = inspect_production_lock_boundary()
                self.assertEqual(state, "absent")
                self.assertEqual(parent_mode, f"{stat.S_IMODE(Path('/tmp').stat().st_mode):o}")
                lock_path.write_text("conflict\n", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    inspect_production_lock_boundary()
        finally:
            lock_path.unlink(missing_ok=True)

    def test_production_lock_is_never_opened_or_created(self):
        text = ENGINE.read_text(encoding="utf-8")
        self.assertIn(
            'PRODUCTION_LOCK = Path("/run/lock/a-clockwork-plex-audio-route.lock")',
            text,
        )
        self.assertNotIn("os.open(PRODUCTION_LOCK", text)
        self.assertNotIn("PRODUCTION_LOCK.open", text)
        self.assertNotIn("PRODUCTION_LOCK.write_text", text)
        self.assertNotIn("PRODUCTION_LOCK.touch", text)
        self.assertNotIn("PRODUCTION_LOCK.mkdir", text)
        self.assertNotIn("PRODUCTION_LOCK.unlink", text)
        self.assertIn("PRODUCTION_LOCK.lstat()", text)

    def test_lock_identity_and_snapshot_order_are_fixed(self):
        text = ENGINE.read_text(encoding="utf-8")
        ordered = (
            'event("rehearsal-lock-acquired"',
            "prove_lock_contention(lock)",
            "identity = write_identity",
            'event("snapshot-started"',
            "summary = collect_filesystem_snapshot",
            'event("snapshot-verified"',
            "write_evidence_manifest(snapshot_root)",
            "lock.release()",
            'event("rehearsal-lock-released"',
        )
        positions = [text.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_exact_seventeen_result_checks_are_emitted(self):
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        checks: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "append_result":
                continue
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                if isinstance(node.args[1].value, str):
                    checks.append((node.lineno, node.args[1].value))
        observed = [value for _line, value in sorted(checks)]
        expected = [
            "root-scope",
            "input-replay",
            "current-host-boundary",
            "production-lock-boundary",
            "rehearsal-lock-acquired",
            "lock-contention",
            "fresh-identity",
            "privileged-destination-resolution",
            "filesystem-snapshot",
            "service-state-boundary",
            "mixer-state-capture",
            "module-dac-capture",
            "rollback-ledger",
            "input-integrity",
            "snapshot-integrity",
            "rehearsal-lock-released",
            "activation-interface",
        ]
        self.assertEqual(observed, expected)

    def test_c5_contract_is_replayed_exactly(self):
        text = ENGINE.read_text(encoding="utf-8")
        self.assertEqual(len(EXPECTED_STAGE_C5_CHECKS), 10)
        for expected in (
            "state_machine_rows()",
            "lock_rows()",
            "snapshot_rows()",
            "command_rows()",
            "rollback_rows()",
            "blocker_rows()",
            "Stage C5 evidence does not contain the exact ten checks",
        ):
            self.assertIn(expected, text)

    def test_live_snapshot_reuses_proven_capture_primitives(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            "validate_inputs(package_root, stage_c3_root)",
            "validate_current_host_as_root()",
            "validate_physical_capture_boundary()",
            'collect_filesystem_snapshot(entries, Path("/"), snapshot_root)',
            "capture_service_states",
            "capture_mixer_states",
            "capture_module_and_dac",
            "summary.managed_absent != EXPECTED_PACKAGE_FILES",
            "write_rollback_ledger",
            "write_evidence_manifest",
            "chown_evidence_tree",
        ):
            self.assertIn(expected, text)

    def test_engine_has_no_command_or_dynamic_execution_adapter(self):
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertFalse(
            imported
            & {
                "subprocess",
                "socket",
                "requests",
                "urllib",
                "http.client",
            }
        )
        forbidden_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "compile"}
        ]
        self.assertEqual(forbidden_calls, [])
        text = ENGINE.read_text(encoding="utf-8")
        self.assertNotIn("os.system", text)
        self.assertNotIn("subprocess.", text)
        self.assertNotIn("shell=True", text)

    def test_physical_boundary_precedes_any_evidence_ownership_change(self):
        text = ENGINE.read_text(encoding="utf-8")
        boundary = text.index("validate_physical_capture_boundary()")
        chown = text.index("os.chown(snapshot_root, 0, 0)")
        acquire = text.index("lock = acquire_rehearsal_lock(snapshot_root)")
        self.assertLess(boundary, chown)
        self.assertLess(chown, acquire)

    def test_identity_is_random_and_explicitly_non_authoritative(self):
        text = ENGINE.read_text(encoding="utf-8")
        for expected in (
            "secrets.token_hex(12)",
            '("caller_supplied", "false")',
            '("activation_authoritative", "false")',
            "this rehearsal must never be reused as an activation-authoritative snapshot",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
