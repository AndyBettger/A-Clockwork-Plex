from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.stage_c_transaction.host_review import _dac_owner_rows


class StageCDacOwnerEvidenceTests(unittest.TestCase):
    def test_fuser_pid_is_structured_without_stderr_label_spaghetti(self):
        device = Path("/dev/snd/pcmC2D0p")
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            process = proc_root / "466057"
            (process / "fd").mkdir(parents=True)
            (process / "fdinfo").mkdir()
            (process / "comm").write_text("node\n", encoding="utf-8")
            (process / "status").write_text("Name:\tnode\nUid:\t1000\t1000\t1000\t1000\n", encoding="utf-8")
            (process / "fd" / "17").symlink_to(device)
            (process / "fdinfo" / "17").write_text("pos:\t0\nflags:\t02100001\n", encoding="utf-8")

            with patch(
                "scripts.stage_c_transaction.host_review.pwd.getpwuid",
                return_value=SimpleNamespace(pw_name="andy"),
            ):
                rows = _dac_owner_rows(device, " 466057", proc_root)

        self.assertEqual(
            rows,
            [
                "dac.owner_count\t1",
                "dac.owners\t466057",
                "dac.owner.1.pid\t466057",
                "dac.owner.1.user\tandy",
                "dac.owner.1.command\tnode",
                "dac.owner.1.fds\t17:write",
            ],
        )
        joined = "\n".join(rows)
        self.assertNotIn("/dev/snd/pcmC2D0p:", joined)
        self.assertNotIn("  m", joined)

    def test_multiple_pids_are_deduplicated_and_sorted(self):
        rows = _dac_owner_rows(Path("/dev/snd/pcmC2D0p"), " 42 7 42", Path("/missing-proc"))
        self.assertEqual(rows[0], "dac.owner_count\t2")
        self.assertEqual(rows[1], "dac.owners\t7,42")
        self.assertIn("dac.owner.1.pid\t7", rows)
        self.assertIn("dac.owner.2.pid\t42", rows)

    def test_no_owner_is_explicit(self):
        self.assertEqual(
            _dac_owner_rows(Path("/dev/snd/pcmC2D0p"), "", Path("/missing-proc")),
            ["dac.owner_count\t0", "dac.owners\tnone"],
        )


if __name__ == "__main__":
    unittest.main()
