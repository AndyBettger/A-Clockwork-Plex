from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "prepare-stage-c-route-package.sh"
PACKAGE = ROOT / "scripts" / "stage_c_package"
PYTHON_FILES = tuple(sorted(PACKAGE.glob("*.py")))


class StageCRoutePackageSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scripts = str(ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from stage_c_package import runtime_templates, templates

        cls.runtime_templates = runtime_templates
        cls.templates = templates
        cls.contract = templates.HostContract(
            project_user="andy",
            dac_card="Pro",
            dac_device=0,
            loopback_index=7,
            loopback_id="ACP_Loopback",
        )

    @staticmethod
    def combined_source() -> str:
        return "\n".join(
            [WRAPPER.read_text(encoding="utf-8")]
            + [path.read_text(encoding="utf-8") for path in PYTHON_FILES]
        )

    def test_wrapper_has_valid_shell_syntax_and_disables_bytecode(self):
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('exec python3 -B "$SCRIPT_DIR/stage_c_package/prepare.py" "$@"', text)

    def test_python_generator_modules_compile_in_memory(self):
        self.assertGreaterEqual(len(PYTHON_FILES), 4)
        for path in PYTHON_FILES:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")

    def test_generator_has_no_activation_interface(self):
        text = self.combined_source()
        self.assertNotIn("--activate", text)
        self.assertNotIn("--confirm", text)
        self.assertIn("There is no activation mode", text)
        self.assertIn("No activation path exists", text)

    def test_prepare_layer_performs_no_privileged_or_audio_mutation(self):
        text = self.combined_source()
        self.assertIsNone(re.search(r"(?m)^\s*(?:sudo|modprobe|systemctl|amixer|alsactl)(?:\s|$)", text))
        self.assertNotIn("aplay -D", text)
        self.assertNotIn("subprocess.run([\"sudo\"", text)
        self.assertNotIn("subprocess.run([\"systemctl\"", text)

    def test_host_contract_is_pinned_to_physical_discovery(self):
        contract = self.contract
        self.assertEqual(contract.camilladsp_version, "4.1.3")
        self.assertEqual(
            contract.camilladsp_sha256,
            "e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa",
        )
        self.assertEqual(
            contract.pre_stage_c_alsa_sha256,
            "08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9",
        )
        self.assertEqual((contract.dac_card, contract.dac_device), ("Pro", 0))
        self.assertEqual((contract.loopback_index, contract.loopback_id), (7, "ACP_Loopback"))
        self.assertEqual((contract.sample_rate, contract.sample_format), (44100, "S16_LE"))
        self.assertEqual((contract.period_size, contract.buffer_size), (1024, 8192))
        text = self.combined_source()
        self.assertIn('"pcm_substreams": "2"', text)
        self.assertIn('"pcm_notify": "1"', text)

    def test_both_physically_proven_route_shapes_are_generated(self):
        split = self.templates.split_route(self.contract)
        direct = self.templates.direct_route(self.contract)
        camilla = self.templates.camilladsp_config(self.contract)
        self.assertIn('slave.pcm "acp_music_route"', split)
        self.assertIn('slave.pcm "acp_alarm_route"', split)
        self.assertIn('slave.pcm "acp_dmix"', direct)
        self.assertIn("Music-only EQ and headroom, independent alarm, final limiter", camilla)
        self.assertIn("final_safety_limiter", camilla)
        self.assertIn("clip_limit: -1.0", camilla)
        for pcm in ("acp_dmix", "acp_master", "acp_plexamp", "acp_airplay", "acp_alarm"):
            self.assertIn(pcm, split)
            self.assertIn(pcm, direct)

    def test_generated_runtime_assets_remain_deliberately_blocked(self):
        helper = self.runtime_templates.route_helper()
        self.assertIn("stage-c1-candidate-only", helper)
        self.assertIn("'activation_approved': False", helper)
        self.assertIn("mutation is deliberately blocked", helper)
        self.assertIn("return 78", helper)
        units = "\n".join(
            (
                self.runtime_templates.route_unit(),
                self.runtime_templates.camilladsp_unit(self.contract),
                self.runtime_templates.failback_unit(),
            )
        )
        self.assertEqual(
            units.count("ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved"),
            3,
        )
        self.assertNotIn("touch activation-approved", self.combined_source())

    def test_package_purity_and_fresh_lab_are_mandatory(self):
        text = self.combined_source()
        self.assertIn("if any(root.iterdir())", text)
        self.assertIn("--lab-root must be empty", text)
        self.assertIn("p.is_symlink()", text)
        self.assertIn('p.name == "__pycache__"', text)
        self.assertIn('p.suffix == ".pyc"', text)
        self.assertIn("EXPECTED_FILES = 12", text)
        self.assertIn('compile(source, str(paths["route_helper"]), "exec")', text)
        self.assertNotIn("py_compile", text)

    def test_manifest_records_directories_files_and_empty_state_directory(self):
        text = self.combined_source()
        self.assertIn('rows = ["type\\tdestination\\tmode\\towner\\tsha256"]', text)
        self.assertIn('directory\\t/var/lib/a-clockwork-plex/split-bus\\t755\\troot:root\\t-', text)
        self.assertIn("manifest records required empty directories as well as files", text)

    def test_systemd_ordering_has_one_route_authority(self):
        route = self.runtime_templates.route_unit()
        camilla = self.runtime_templates.camilladsp_unit(self.contract)
        self.assertIn(
            "Before=a-clockwork-plex-camilladsp.service plexamp.service shairport-sync.service a-clockwork-plex.service",
            route,
        )
        self.assertIn("Requires=a-clockwork-plex-audio-route.service sound.target", camilla)
        self.assertIn("Before=plexamp.service shairport-sync.service a-clockwork-plex.service", camilla)
        self.assertIn("OnFailure=a-clockwork-plex-audio-failback.service", camilla)

    def test_package_contains_expected_review_assets(self):
        text = self.combined_source()
        for expected in (
            "a-clockwork-plex-aloop.conf",
            "split-bus.conf",
            "direct-alarm-bypass.conf",
            "camilladsp-split-bus.yml",
            "a-clockwork-plex-split-bus",
            "a-clockwork-plex-audio-route",
            "a-clockwork-plex-audio-route.service",
            "a-clockwork-plex-camilladsp.service",
            "a-clockwork-plex-audio-failback.service",
            "manifest.tsv",
            "results.tsv",
            "report.txt",
            '"--check"',
            '"visudo"',
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
