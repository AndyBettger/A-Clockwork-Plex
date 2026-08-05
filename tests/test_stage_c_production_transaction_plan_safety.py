import ast
import os
import py_compile
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
WRAPPER = SCRIPTS / "prepare-stage-c-production-transaction-plan.sh"
MODULE = SCRIPTS / "stage_c_transaction" / "production_plan.py"

sys.path.insert(0, str(SCRIPTS))
from stage_c_transaction import production_plan as plan  # noqa: E402


class StageCProductionTransactionPlanSafetyTests(unittest.TestCase):
    def test_wrapper_and_module_syntax(self):
        subprocess.run(["bash", "-n", str(WRAPPER)], check=True)
        py_compile.compile(str(MODULE), doraise=True)

    def test_prepare_only_precedes_review_generation(self):
        text = WRAPPER.read_text(encoding="utf-8")
        prepare = text.index('if [[ "$MODE" == "prepare" ]]')
        guarded = text.index('[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]]')
        execute = text.index("exec python3 -B -m stage_c_transaction.production_plan")
        self.assertLess(prepare, guarded)
        self.assertLess(guarded, execute)
        self.assertIn("Prepare-only invoked no sudo and created no review directory.", text)
        self.assertNotIn("--activate", text)
        self.assertNotIn("--install", text)
        self.assertNotIn("--rollback", text)
        self.assertNotIn("--uninstall", text)
        executable_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertFalse(any(line == "sudo" or line.startswith("sudo ") for line in executable_lines))

    def test_review_token_is_not_an_activation_token(self):
        self.assertEqual(
            plan.REQUIRED_CONFIRMATION,
            "STAGE-C5-PRODUCTION-TRANSACTION-PLAN-REVIEW",
        )
        blockers = {row["blocker"]: row for row in plan.blocker_rows()}
        self.assertEqual(blockers["activation-token"]["state"], "absent")
        self.assertIn("review-generation-only", blockers["activation-token"]["detail"])
        self.assertEqual(blockers["root-adapter"]["state"], "absent")
        self.assertEqual(blockers["persistent-activation"]["state"], "blocked")

    def test_single_lock_precedes_snapshot_and_all_mutation(self):
        rows = plan.state_machine_rows()
        by_state = {row["state"]: row for row in rows}
        self.assertEqual(plan.ROUTE_LOCK, "/run/lock/a-clockwork-plex-audio-route.lock")
        self.assertLess(
            int(by_state["acquire-route-lock"]["order"]),
            int(by_state["create-transaction-identity"]["order"]),
        )
        self.assertLess(
            int(by_state["create-transaction-identity"]["order"]),
            int(by_state["capture-authoritative-snapshot"]["order"]),
        )
        self.assertLess(
            int(by_state["verify-snapshot"]["order"]),
            int(by_state["stop-application-services"]["order"]),
        )
        self.assertLess(
            int(by_state["commit-manifest"]["order"]),
            int(by_state["release-route-lock"]["order"]),
        )
        mutation_rows = [row for row in rows if row["production_mutation"] == "true"]
        self.assertTrue(mutation_rows)
        self.assertTrue(all(row["route_lock"] == "held" for row in mutation_rows))
        self.assertEqual(by_state["release-route-lock"]["route_lock"], "release")

    def test_failure_ownership_is_deliberately_separated(self):
        rows = plan.rollback_rows()
        actions = {row["action"] for row in rows}
        self.assertEqual(
            actions,
            {
                "pre-mutation-abort",
                "exact-install-rollback",
                "explicit-uninstall-only",
                "direct-alarm-bypass-failback",
            },
        )
        runtime = next(row for row in rows if row["from_state"] == "runtime-camilladsp-failure")
        self.assertIn("do not perform uninstall rollback", runtime["requirement"])
        committed = next(row for row in rows if row["action"] == "explicit-uninstall-only")
        self.assertIn("authoritative transaction snapshot", committed["requirement"])

    def test_fresh_snapshot_contract_forbids_rehearsal_reuse(self):
        rows = {row["area"]: row for row in plan.snapshot_rows()}
        self.assertEqual(
            plan.TRANSACTION_ROOT,
            "/var/lib/a-clockwork-plex/split-bus/transactions",
        )
        self.assertIn("caller cannot supply or reuse", rows["identity"]["requirement"])
        self.assertIn("root:root mode 0700", rows["directory"]["requirement"])
        self.assertEqual(rows["rehearsal-evidence"]["capture"], "forbidden-as-backup")
        self.assertIn("review provenance", rows["rehearsal-evidence"]["requirement"])

    def test_command_contract_forbids_dynamic_shell_and_download(self):
        rows = {row["family"]: row for row in plan.command_rows()}
        self.assertEqual(rows["shell"]["allowed_shape"], "forbidden")
        self.assertIn("shell=True", rows["shell"]["restriction"])
        self.assertEqual(rows["network-download"]["allowed_shape"], "forbidden")
        self.assertIn("no dynamic unit name", rows["systemd"]["restriction"])
        self.assertIn("no caller-supplied production path", rows["filesystem"]["restriction"])

    def test_module_has_no_command_execution_or_hidden_dynamic_execution(self):
        source = MODULE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        forbidden_calls = {"eval", "exec", "compile", "__import__", "system", "popen", "spawn"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden_calls)
            if isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden_calls)
            self.assertFalse(
                any(keyword.arg == "shell" for keyword in node.keywords),
                "Stage C5 may not construct shell-executed commands.",
            )

    def test_parser_exposes_review_only_arguments(self):
        parser = plan.build_parser()
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertEqual(
            option_strings,
            {
                "-h",
                "--help",
                "--package-root",
                "--stage-c3-root",
                "--stage-c4-root",
                "--review-root",
                "--confirm",
            },
        )

    def test_review_root_is_fresh_direct_var_tmp_and_mode_0700(self):
        path = Path(tempfile.mkdtemp(prefix=plan.REVIEW_PREFIX, dir="/var/tmp"))
        try:
            path.chmod(0o700)
            resolved = plan.validate_review_root(path, Path("/tmp/input-a"), Path("/tmp/input-b"))
            self.assertEqual(resolved, path.resolve())
            path.chmod(0o755)
            with self.assertRaises(SystemExit):
                plan.validate_review_root(path, Path("/tmp/input-a"))
        finally:
            path.chmod(0o700)
            shutil.rmtree(path)

    def test_symlinked_review_root_is_rejected(self):
        target = Path(tempfile.mkdtemp(prefix=plan.REVIEW_PREFIX, dir="/var/tmp"))
        link = target.with_name(target.name + "-link")
        try:
            target.chmod(0o700)
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(SystemExit):
                plan.validate_review_root(link, Path("/tmp/input-a"))
        finally:
            if link.is_symlink():
                link.unlink()
            shutil.rmtree(target)

    def test_stage_c4_expected_scenarios_are_exact_and_zero_mismatch(self):
        self.assertEqual(len(plan.EXPECTED_SCENARIOS), 4)
        self.assertEqual(plan.EXPECTED_SCENARIOS[0][2], "true")
        self.assertEqual(plan.EXPECTED_SCENARIOS[0][3], "explicit-uninstall")
        self.assertTrue(all(row[4] == "0" for row in plan.EXPECTED_SCENARIOS))
        self.assertTrue(
            all(row[3].startswith("automatic:") for row in plan.EXPECTED_SCENARIOS[1:])
        )


if __name__ == "__main__":
    unittest.main()
