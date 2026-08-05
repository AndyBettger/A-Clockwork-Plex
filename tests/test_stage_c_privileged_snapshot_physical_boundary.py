from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from scripts.stage_c_transaction import privileged_snapshot_entry as entry


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "test-stage-c-privileged-snapshot.sh"
ENTRY = ROOT / "scripts" / "stage_c_transaction" / "privileged_snapshot_entry.py"


VALID_HW_PARAMS = """access: MMAP_INTERLEAVED
format: S16_LE
subformat: STD
channels: 2
rate: 44100 (44100/1)
period_size: 1024
buffer_size: 8192
"""


class StageCPrivilegedSnapshotPhysicalBoundaryTests(unittest.TestCase):
    def test_entry_module_compiles_and_wrapper_uses_it(self):
        compile(ENTRY.read_text(encoding="utf-8"), str(ENTRY), "exec")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn(
            'ENGINE="$SCRIPT_DIR/stage_c_transaction/privileged_snapshot_entry.py"',
            wrapper,
        )
        self.assertNotIn(
            'ENGINE="$SCRIPT_DIR/stage_c_transaction/privileged_snapshot.py"',
            wrapper,
        )

    def test_exact_validated_dac_contract_is_pinned(self):
        self.assertEqual(
            entry.EXPECTED_HW_PARAMS,
            {
                "access": "MMAP_INTERLEAVED",
                "format": "S16_LE",
                "subformat": "STD",
                "channels": "2",
                "rate": "44100",
                "period_size": "1024",
                "buffer_size": "8192",
            },
        )
        self.assertEqual(entry.parse_hw_params(VALID_HW_PARAMS), entry.EXPECTED_HW_PARAMS)

    def test_rate_fraction_is_normalised_without_weakening_other_values(self):
        parsed = entry.parse_hw_params(VALID_HW_PARAMS.replace("44100 (44100/1)", "48000 (48000/1)"))
        self.assertEqual(parsed["rate"], "48000")
        self.assertEqual(parsed["format"], "S16_LE")
        self.assertEqual(parsed["period_size"], "1024")

    def test_validation_accepts_only_enabled_loopback_and_exact_dac_state(self):
        fake_device = mock.Mock()
        fake_device.exists.return_value = True
        fake_hw = mock.Mock()
        fake_hw.read_text.return_value = VALID_HW_PARAMS

        def fake_path(raw: str):
            if raw == "/dev/snd/pcmC2D0p":
                return fake_device
            if raw == "/proc/asound/Pro/pcm0p/sub0/hw_params":
                return fake_hw
            return Path(raw)

        with mock.patch.object(entry, "first_module_parameter", return_value="Y"), mock.patch.object(
            entry, "Path", side_effect=fake_path
        ):
            entry.validate_physical_capture_boundary()

    def test_disabled_loopback_is_rejected(self):
        with mock.patch.object(entry, "first_module_parameter", return_value="N"):
            with self.assertRaises(SystemExit) as context:
                entry.validate_physical_capture_boundary()
        self.assertIn("Unexpected snd_aloop enable state", str(context.exception))

    def test_each_dac_parameter_mismatch_is_rejected(self):
        for key, replacement in (
            ("access", "access: RW_INTERLEAVED"),
            ("format", "format: S32_LE"),
            ("subformat", "subformat: OTHER"),
            ("channels", "channels: 4"),
            ("rate", "rate: 48000 (48000/1)"),
            ("period_size", "period_size: 512"),
            ("buffer_size", "buffer_size: 4096"),
        ):
            with self.subTest(key=key):
                lines = VALID_HW_PARAMS.splitlines()
                mutated = "\n".join(
                    replacement if line.startswith(f"{key}:") else line for line in lines
                ) + "\n"
                fake_device = mock.Mock()
                fake_device.exists.return_value = True
                fake_hw = mock.Mock()
                fake_hw.read_text.return_value = mutated

                def fake_path(raw: str):
                    if raw == "/dev/snd/pcmC2D0p":
                        return fake_device
                    if raw == "/proc/asound/Pro/pcm0p/sub0/hw_params":
                        return fake_hw
                    return Path(raw)

                with mock.patch.object(entry, "first_module_parameter", return_value="Y"), mock.patch.object(
                    entry, "Path", side_effect=fake_path
                ):
                    with self.assertRaises(SystemExit) as context:
                        entry.validate_physical_capture_boundary()
                self.assertIn(key, str(context.exception))


if __name__ == "__main__":
    unittest.main()
