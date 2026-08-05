from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from stage_c_activation_package import core, runtime_templates
from stage_c_package.templates import HostContract


class StageCActivationPackageSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wrapper = SCRIPTS / "prepare-stage-c21-activation-package.sh"
        cls.prepare = SCRIPTS / "stage_c_activation_package/prepare.py"
        cls.package_dir = SCRIPTS / "stage_c_activation_package"
        cls.contract = HostContract(
            project_user="andy",
            dac_card="Pro",
            dac_device=0,
            loopback_index=7,
            loopback_id="ACP_Loopback",
        )

    def test_wrapper_and_generator_syntax(self):
        checked = subprocess.run(
            ["bash", "-n", str(self.wrapper)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        for path in sorted(self.package_dir.glob("*.py")):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        self.assertIn(
            'exec python3 -B "$SCRIPT_DIR/stage_c_activation_package/prepare.py" "$@"',
            self.wrapper.read_text(encoding="utf-8"),
        )

    def test_generator_has_no_install_or_activation_interface(self):
        source = self.prepare.read_text(encoding="utf-8")
        wrapper = self.wrapper.read_text(encoding="utf-8")
        self.assertNotIn("--activate", source)
        self.assertNotIn("--install", source)
        self.assertNotIn("--confirm", source)
        self.assertIn("no install or activation mode", source)
        self.assertNotIn("sudo ", wrapper)
        self.assertNotIn("systemctl ", wrapper)
        self.assertNotIn("aplay -D", source)
        self.assertNotIn("amixer ", source)

    def test_stage_c1_package_remains_historical_and_blocked(self):
        historical = (SCRIPTS / "stage_c_package/runtime_templates.py").read_text(encoding="utf-8")
        self.assertIn("stage-c1-candidate-only", historical)
        self.assertIn("mutation is deliberately blocked", historical)
        self.assertIn("return 78", historical)
        self.assertNotIn("stage-c21-adapter-pending-review", historical)

    def test_new_package_vendors_exact_runtime_core_modules(self):
        self.assertEqual(
            core.RUNTIME_MODULES,
            (
                "__init__.py",
                "model.py",
                "approval_store.py",
                "state_machine.py",
                "supervisor_model.py",
            ),
        )
        source = self.prepare.read_text(encoding="utf-8")
        self.assertIn("AUTHORITY_SOURCE", source)
        self.assertIn("shutil.copy2(source, destination)", source)
        self.assertIn("source.is_symlink()", source)
        self.assertEqual(core.EXPECTED_FILES, 19)

    def test_generated_entry_has_fixed_actions_and_blocks_host_mutation(self):
        entry = runtime_templates.package_entry()
        compile(entry, "package_entry.py", "exec")
        for action in (
            "status",
            "validate-runtime",
            "accept-install-handoff",
            "promote-committed-approval",
            "boot-prepare",
            "supervise",
            "emergency-direct-failback",
        ):
            self.assertIn(action, entry)
        self.assertIn('"host_mutation_available": False', entry)
        self.assertIn("mutation remains blocked", entry)
        self.assertIn("return 78 if action in MUTATING_ACTIONS else 1", entry)
        self.assertNotIn("subprocess", entry)
        self.assertNotIn("systemctl", entry)
        self.assertNotIn("os.system", entry)

    def test_type_notify_supervisor_is_the_application_readiness_gate(self):
        route = runtime_templates.route_unit()
        supervisor = runtime_templates.camilladsp_unit(self.contract)
        failback = runtime_templates.failback_unit()
        self.assertIn("Type=oneshot", route)
        self.assertIn("boot-prepare", route)
        self.assertIn("Type=notify", supervisor)
        self.assertIn("NotifyAccess=main", supervisor)
        self.assertIn("ExecStart=/usr/local/bin/a-clockwork-plex-audio-route supervise", supervisor)
        self.assertIn("Before=plexamp.service shairport-sync.service a-clockwork-plex.service", supervisor)
        self.assertIn("OnFailure=a-clockwork-plex-audio-failback.service", supervisor)
        self.assertNotIn("/camilladsp /etc/", supervisor)
        self.assertIn("emergency-direct-failback", failback)
        self.assertIn("Before=plexamp.service shairport-sync.service a-clockwork-plex.service", failback)

    def test_launcher_imports_only_the_fixed_packaged_entry(self):
        launcher = runtime_templates.route_launcher()
        compile(launcher, "a-clockwork-plex-audio-route", "exec")
        self.assertIn(
            "from stage_c_runtime_authority.package_entry import main",
            launcher,
        )
        self.assertIn(runtime_templates.RUNTIME_ROOT, launcher)
        self.assertNotIn("eval(", launcher)
        self.assertNotIn("exec(", launcher)

    def test_package_fingerprint_is_deterministic_and_ordered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "z.txt"
            second = root / "a.txt"
            first.write_text("z", encoding="utf-8")
            second.write_text("a", encoding="utf-8")
            rows = core.package_rows(root, exclude=set())
            self.assertEqual([row["path"] for row in rows], ["/a.txt", "/z.txt"])
            self.assertEqual(core.package_fingerprint(rows), core.package_fingerprint(list(rows)))
            changed = json.loads(json.dumps(rows))
            changed[0]["sha256"] = "0" * 64
            self.assertNotEqual(core.package_fingerprint(rows), core.package_fingerprint(changed))

    def test_contract_records_blocked_phase_and_bound_payload(self):
        rows = [
            {"path": "/etc/example", "sha256": "a" * 64},
            {"path": "/usr/example", "sha256": "b" * 64},
        ]
        fingerprint = core.package_fingerprint(rows)
        payload = json.loads(
            runtime_templates.contract_json(
                package_fingerprint=fingerprint,
                files=rows,
            )
        )
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["package_fingerprint"], fingerprint)
        self.assertFalse(payload["host_mutation_available"])
        self.assertEqual(payload["files"], rows)

    def test_sudoers_remains_read_only(self):
        rules = runtime_templates.sudoers("andy")
        self.assertIn(" status", rules)
        self.assertIn(" validate-runtime", rules)
        for forbidden in (
            "boot-prepare",
            "supervise",
            "emergency-direct-failback",
            "accept-install-handoff",
            "promote-committed-approval",
        ):
            self.assertNotIn(forbidden, rules)


if __name__ == "__main__":
    unittest.main()
