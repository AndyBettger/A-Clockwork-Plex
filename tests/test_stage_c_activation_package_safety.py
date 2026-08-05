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
        cls.authority_dir = SCRIPTS / "stage_c_runtime_authority"
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
        self.assertNotIn("subprocess", source)

    def test_stage_c1_package_remains_historical_and_blocked(self):
        historical = (SCRIPTS / "stage_c_package/runtime_templates.py").read_text(encoding="utf-8")
        self.assertIn("stage-c1-candidate-only", historical)
        self.assertIn("mutation is deliberately blocked", historical)
        self.assertIn("return 78", historical)
        self.assertNotIn(runtime_templates.PACKAGE_PHASE, historical)

    def test_v2_package_vendors_exact_runtime_modules_without_test_adapter(self):
        self.assertEqual(
            core.RUNTIME_MODULES,
            (
                "__init__.py",
                "model.py",
                "approval_store.py",
                "state_machine.py",
                "supervisor_model.py",
                "runtime_executor.py",
                "linux_runtime_filesystem.py",
                "linux_runtime_process.py",
                "linux_runtime_adapter.py",
                "install_runtime_filesystem.py",
                "install_runtime_process.py",
                "install_runtime_adapter.py",
                "install_runtime_executor.py",
                "supervisor_service.py",
                "package_entry.py",
            ),
        )
        source = self.prepare.read_text(encoding="utf-8")
        self.assertIn("AUTHORITY_SOURCE", source)
        self.assertIn("shutil.copy2(source, destination)", source)
        self.assertIn("source.is_symlink()", source)
        self.assertEqual(core.EXPECTED_FILES, 28)
        self.assertNotIn("recording_runtime_adapter.py", core.RUNTIME_MODULES)
        for module_name in core.RUNTIME_MODULES:
            self.assertTrue((self.authority_dir / module_name).is_file(), module_name)

    def test_entrypoint_is_copied_not_synthesised(self):
        templates_source = (self.package_dir / "runtime_templates.py").read_text(encoding="utf-8")
        prepare_source = self.prepare.read_text(encoding="utf-8")
        self.assertNotIn("def package_entry", templates_source)
        self.assertNotIn('"package_entry": (runtime_templates.package_entry()', prepare_source)
        self.assertIn('"package_entry": runtime_package / "package_entry.py"', prepare_source)
        self.assertIn('"package_entry.py",', (self.package_dir / "core.py").read_text(encoding="utf-8"))

    def test_packaged_entry_has_fixed_actions_and_installed_image_guards(self):
        entry_path = self.authority_dir / "package_entry.py"
        entry = entry_path.read_text(encoding="utf-8")
        compile(entry, str(entry_path), "exec")
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
        self.assertIn("INSTALLED_PACKAGE_ROOT", entry)
        self.assertIn(runtime_templates.PACKAGE_PHASE, entry)
        self.assertIn('contract.get("host_mutation_available") is not True', entry)
        self.assertIn("runtime mutation requires root", entry)
        self.assertIn("transaction-only approval operation is not exposed", entry)
        self.assertNotIn("subprocess.Popen", entry)
        self.assertNotIn("systemctl", entry)
        self.assertNotIn("os.system", entry)
        self.assertNotIn("def dispatch", entry)

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

    def test_contract_records_activation_capable_phase_and_bound_payload(self):
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
        self.assertEqual(payload["package_phase"], runtime_templates.PACKAGE_PHASE)
        self.assertEqual(payload["package_fingerprint"], fingerprint)
        self.assertTrue(payload["host_mutation_available"])
        self.assertEqual(payload["files"], rows)

    def test_sudoers_remains_read_only_despite_root_owned_service_runtime(self):
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

    def test_report_describes_disposable_v2_not_an_install(self):
        source = self.prepare.read_text(encoding="utf-8")
        self.assertIn("PACKAGE_VERSION = 2", source)
        self.assertIn("complete fixed runtime authority", source)
        self.assertIn("It has not been installed or activated", source)
        self.assertIn("Approval creation and promotion remain outside the service helper", source)
        self.assertIn("No production path, service, process, ALSA route, mixer or PCM was changed", source)


if __name__ == "__main__":
    unittest.main()
