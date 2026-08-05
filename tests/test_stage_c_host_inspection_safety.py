from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "inspect-stage-c-host.sh"


class StageCHostInspectionSafetyTests(unittest.TestCase):
    def test_script_has_valid_shell_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(INSPECTOR)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_inspection_is_read_only_and_unprivileged(self):
        text = INSPECTOR.read_text(encoding="utf-8")
        self.assertNotRegex(
            text,
            re.compile(r"(?m)^\s*(?:sudo|rm|cp|mv|install|modprobe)\b"),
        )
        self.assertNotRegex(
            text,
            re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable)\b"),
        )
        self.assertNotIn("tee /etc", text)
        self.assertNotIn(">/etc", text)
        self.assertNotIn("> /etc", text)
        self.assertNotIn("aplay -D", text)

    def test_reports_every_stage_c_host_dependency(self):
        text = INSPECTOR.read_text(encoding="utf-8")
        for expected in (
            "modinfo -p snd_aloop",
            "/sys/module/snd_aloop/parameters",
            "/etc/modules-load.d/*aloop*.conf",
            "/etc/modprobe.d/*aloop*.conf",
            "/proc/asound/cards",
            "aplay -l",
            "aplay -L",
            "sha256sum \"$ALSA_CONFIG\"",
            r"pcm\.acp_alarm_volume",
            "systemctl is-active",
            "systemctl is-enabled",
            "pgrep -a -x camilladsp",
            "--version",
            "sha256sum \"$CAMILLADSP_BINARY\"",
            "fuser -v",
            "No file, service, module, mixer level or audio route was changed.",
        ):
            self.assertIn(expected, text)

    def test_optional_binary_path_is_explicit(self):
        text = INSPECTOR.read_text(encoding="utf-8")
        self.assertIn("--binary PATH", text)
        self.assertIn('CAMILLADSP_BINARY="${CAMILLADSP_BINARY:-}"', text)
        self.assertIn("not supplied; rerun with --binary PATH", text)


if __name__ == "__main__":
    unittest.main()
