from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE_TEMPLATE = ROOT / "systemd" / "a-clockwork-plex.service"
SETUP = ROOT / "setup.sh"

# These are live installer/runtime source locations. Historical documentation is
# intentionally excluded: a physical evidence path such as /home/andy/... must
# remain an accurate record of what was actually tested.
SCAN_ROOTS = (
    ROOT / "installer",
    ROOT / "scripts",
    ROOT / "systemd",
)
ROOT_FILES = (
    ROOT / "setup.sh",
    ROOT / "appliance-installer.sh",
)
TEXT_SUFFIXES = {
    ".sh",
    ".py",
    ".service",
    ".in",
    ".conf",
    ".txt",
    ".yml",
    ".yaml",
}


class ProjectUserPortabilityTests(unittest.TestCase):
    def live_source_files(self) -> list[Path]:
        paths = list(ROOT_FILES)
        for directory in SCAN_ROOTS:
            paths.extend(
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
            )
        return sorted(set(paths))

    def test_live_source_has_no_andy_specific_home_or_user_default(self) -> None:
        forbidden = (
            "/home/andy",
            "${USER:-andy}",
            "User=andy",
            "Group=andy",
        )
        offenders: list[str] = []
        for path in self.live_source_files():
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                if needle in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {needle}")
        self.assertEqual([], offenders, "live Andy-specific assumptions:\n" + "\n".join(offenders))

    def test_public_setup_falls_back_to_real_invoking_identity(self) -> None:
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn('${ACP_PROJECT_USER:-${USER:-$(id -un)}}', text)
        self.assertNotIn('${ACP_PROJECT_USER:-${USER:-andy}}', text)

    def test_dashboard_service_source_is_a_rendered_generic_template(self) -> None:
        text = SERVICE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("User=ACP_PROJECT_USER", text)
        self.assertIn("Group=ACP_PROJECT_USER", text)
        self.assertIn("WorkingDirectory=/ACP_PROJECT_DIR", text)
        self.assertIn(
            "ExecStart=/ACP_PROJECT_DIR/venv/bin/python /ACP_PROJECT_DIR/app/runner.py",
            text,
        )


if __name__ == "__main__":
    unittest.main()
