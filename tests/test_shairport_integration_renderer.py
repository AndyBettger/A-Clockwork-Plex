from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "a-clockwork-plex-shairport-integration.py"

spec = importlib.util.spec_from_file_location("shairport_integration", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ShairportIntegrationRendererTests(unittest.TestCase):
    def test_updates_required_blocks_without_changing_receiver_name(self) -> None:
        original = '''general =
{
    name = "Bedroom Plexamp";
};

alsa =
{
    output_device = "old_pcm";
    mixer_control_name = "ACP AirPlay";
};

sessioncontrol =
{
    run_this_after_play_ends = "/old/end";
    session_timeout = 20;
};
'''
        rendered = module.render_integration(original)

        self.assertIn('name = "Bedroom Plexamp";', rendered)
        self.assertIn('output_device = "acp_airplay";', rendered)
        self.assertIn('mixer_control_name = "ACP AirPlay";', rendered)
        self.assertIn(
            'run_this_before_entering_active_state = "/usr/local/bin/a-clockwork-plex-airplay-start";',
            rendered,
        )
        self.assertIn(
            'run_this_after_exiting_active_state = "/usr/local/bin/a-clockwork-plex-airplay-end";',
            rendered,
        )
        self.assertIn("active_state_timeout = 10;", rendered)
        self.assertIn('wait_for_completion = "yes";', rendered)
        self.assertNotIn("run_this_after_play_ends", rendered)
        self.assertNotIn("session_timeout", rendered)
        self.assertIn('enabled = "yes";', rendered)
        self.assertIn('include_cover_art = "yes";', rendered)
        self.assertIn('pipe_name = "/tmp/shairport-sync-metadata";', rendered)
        self.assertIn("pipe_timeout = 5000;", rendered)

    def test_missing_blocks_are_added_without_removing_existing_general_block(self) -> None:
        original = 'general = {\n    name = "Office Plexamp";\n};\n'
        rendered = module.render_integration(original)

        self.assertIn('name = "Office Plexamp";', rendered)
        self.assertIn("alsa =", rendered)
        self.assertIn("sessioncontrol =", rendered)
        self.assertIn("metadata =", rendered)

    def test_render_is_idempotent(self) -> None:
        original = '''general = { name = "Bedroom Plexamp"; };
alsa = { output_device = "default"; };
'''
        once = module.render_integration(original)
        twice = module.render_integration(once)
        self.assertEqual(twice, once)
        self.assertEqual(once.count("output_device"), 1)
        self.assertEqual(once.count("run_this_before_entering_active_state"), 1)
        self.assertEqual(once.count("pipe_name"), 1)

    def test_custom_paths_are_quoted_and_rendered(self) -> None:
        rendered = module.render_integration(
            "",
            start_wrapper="/opt/acp/start",
            end_wrapper="/opt/acp/end",
            metadata_pipe="/run/acp metadata",
        )
        self.assertIn('run_this_before_entering_active_state = "/opt/acp/start";', rendered)
        self.assertIn('run_this_after_exiting_active_state = "/opt/acp/end";', rendered)
        self.assertIn('pipe_name = "/run/acp metadata";', rendered)

    def test_cli_writes_candidate_without_mutating_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source = directory_path / "source.conf"
            output = directory_path / "candidate.conf"
            original = 'general = {\n    name = "Clock";\n};\n'
            source.write_text(original, encoding="utf-8")

            import subprocess

            result = subprocess.run(
                ["python3", str(SCRIPT), "--input", str(source), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertIn('output_device = "acp_airplay";', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
