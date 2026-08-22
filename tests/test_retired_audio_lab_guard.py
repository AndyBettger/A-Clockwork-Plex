from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


RETIRED_AUDIO_LAB_SCRIPTS = (
    "scripts/install-master-eq.sh",
    "scripts/test-master-eq-lab.sh",
    "scripts/test-master-eq-lab-stage2.sh",
    "scripts/test-dsp-loopback-lab.sh",
    "scripts/test-camilladsp-loopback-lab.sh",
    "scripts/test-camilladsp-eq-curves-lab.sh",
    "scripts/test-camilladsp-live-headroom-lab.sh",
    "scripts/test-camilladsp-physical-rehearsal.sh",
    "scripts/test-camilladsp-split-bus-lab.sh",
    "scripts/test-camilladsp-split-bus-physical-rehearsal.sh",
    "scripts/test-direct-alarm-bypass-failback-rehearsal.sh",
    "scripts/test-split-bus-alsa-routing-lab.sh",
    "scripts/test-alsa-control-alias-lab.sh",
    "scripts/test-alsa-control-alias-migration.sh",
)

RETIRED_AUDIO_LAB_TESTS = (
    "tests/test_eq_lab_safety.py",
    "tests/test_eq_lab_stage2_safety.py",
    "tests/test_dsp_loopback_lab_safety.py",
    "tests/test_camilladsp_loopback_lab_safety.py",
    "tests/test_camilladsp_eq_curves_lab_safety.py",
    "tests/test_camilladsp_live_headroom_lab_safety.py",
    "tests/test_camilladsp_physical_rehearsal_safety.py",
    "tests/test_camilladsp_split_bus_lab_safety.py",
    "tests/test_camilladsp_split_bus_physical_rehearsal_safety.py",
    "tests/test_direct_alarm_bypass_failback_rehearsal_safety.py",
    "tests/test_split_bus_alsa_routing_lab_safety.py",
    "tests/test_alsa_control_alias_lab_safety.py",
    "tests/test_alsa_control_alias_migration_safety.py",
)

RETAINED_AUDIO_LIFECYCLE = (
    "scripts/audio/preflight-eq.sh",
    "scripts/audio/install-direct.sh",
    "scripts/audio/install-eq.sh",
    "scripts/audio/repair-audio.sh",
    "scripts/audio/uninstall-eq.sh",
    "scripts/audio/verify-audio.sh",
)


class RetiredAudioLabGuardTests(unittest.TestCase):
    def test_preproduction_audio_lab_scripts_remain_retired(self):
        for relative in RETIRED_AUDIO_LAB_SCRIPTS:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists(), relative)

    def test_dedicated_historical_audio_lab_tests_remain_retired(self):
        for relative in RETIRED_AUDIO_LAB_TESTS:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists(), relative)

    def test_supported_audio_lifecycle_remains_present(self):
        for relative in RETAINED_AUDIO_LIFECYCLE:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_ci_does_not_reintroduce_retired_audio_lab_paths(self):
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        for relative in RETIRED_AUDIO_LAB_SCRIPTS:
            with self.subTest(path=relative):
                self.assertNotIn(relative, workflow)
        for relative in RETAINED_AUDIO_LIFECYCLE:
            with self.subTest(path=relative):
                self.assertIn(f"bash -n {relative}", workflow)


if __name__ == "__main__":
    unittest.main()
