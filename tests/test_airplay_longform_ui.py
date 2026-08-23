from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA_KIND = ROOT / "app" / "static" / "js" / "airplay-media-kind.js"
EXTRA_CONTROLS = ROOT / "app" / "static" / "js" / "airplay-extra-controls.js"
TITLE_CLIENT = ROOT / "app" / "static" / "js" / "airplay-title-marquee.js"
TITLE_STYLE = ROOT / "app" / "static" / "css" / "airplay-title-marquee.css"
AIRPLAY_TEMPLATE = ROOT / "app" / "templates" / "airplay.html"


class AirPlayLongformUiTests(unittest.TestCase):
    def test_changed_airplay_clients_have_valid_javascript_syntax(self) -> None:
        for path in (MEDIA_KIND, EXTRA_CONTROLS, TITLE_CLIENT):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_classifier_handles_real_long_podcast_case_without_misclassifying_named_music_apps(self) -> None:
        cases = [
            {
                "name": "screenshot podcast behind generic Music label",
                "expected": "spoken",
                "metadata": {
                    "source_name": "Music",
                    "title": "Mobile and Piracy — 339: Billionaires Versus Everyone",
                    "artist": "Brad & Will Made a Tech Pod.",
                    "progress": {"duration_seconds": 4946},
                },
            },
            {
                "name": "generic Music label with unmistakable long form",
                "expected": "spoken",
                "metadata": {
                    "player_name": "Music",
                    "title": "Long programme",
                    "artist": "Presenter",
                    "progress": {"duration_seconds": 65 * 60},
                },
            },
            {
                "name": "named Spotify long mix remains music",
                "expected": "track",
                "metadata": {
                    "player_name": "Spotify",
                    "title": "Long DJ Mix",
                    "artist": "DJ Example",
                    "progress": {"duration_seconds": 82 * 60},
                },
            },
            {
                "name": "named Apple Music long work remains music",
                "expected": "track",
                "metadata": {
                    "player_name": "Apple Music",
                    "title": "Symphony",
                    "artist": "Orchestra",
                    "progress": {"duration_seconds": 70 * 60},
                },
            },
            {
                "name": "explicit Prologue app is spoken regardless of duration",
                "expected": "spoken",
                "metadata": {
                    "player_name": "Prologue",
                    "title": "Chapter 1",
                    "artist": "Narrator",
                    "progress": {"duration_seconds": 10 * 60},
                },
            },
            {
                "name": "episode metadata overcomes generic Music label",
                "expected": "spoken",
                "metadata": {
                    "source_name": "Music",
                    "title": "Episode 42",
                    "artist": "Example Pod",
                    "progress": {"duration_seconds": 25 * 60},
                },
            },
        ]
        script = f"""
require({json.dumps(str(MEDIA_KIND))});
const classify = globalThis.ACPAirPlayMediaKind.classify;
const cases = {json.dumps(cases)};
for (const item of cases) {{
  const payload = {{ state: {{ airplay: {{ metadata: item.metadata }} }} }};
  const actual = classify(payload);
  if (actual !== item.expected) {{
    console.error(`${{item.name}}: expected ${{item.expected}}, got ${{actual}}`);
    process.exit(1);
  }}
}}
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_spoken_artwork_keeps_shairport_supported_remote_command_boundary(self) -> None:
        source = EXTRA_CONTROLS.read_text(encoding="utf-8")
        self.assertIn("ACPAirPlayMediaKind?.classify", source)
        self.assertIn("Shairport Sync exposes Previous/Next remote commands", source)
        self.assertIn("not a precise\n    // MPRIS relative-seek method", source)
        self.assertIn("makeButton('airplay-skip-back', 'previous', 'previous')", source)
        self.assertIn("makeButton('airplay-skip-forward', 'next', 'next')", source)
        self.assertIn("source app\n    // therefore remains the authority for the exact skip distance", source)

    def test_episode_title_is_single_line_measured_marquee(self) -> None:
        client = TITLE_CLIENT.read_text(encoding="utf-8")
        style = TITLE_STYLE.read_text(encoding="utf-8")
        template = AIRPLAY_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("MutationObserver", client)
        self.assertIn("airplay-title-scroll-shell", client)
        self.assertIn("title.scrollWidth - shell.clientWidth", client)
        self.assertIn("estimatedOverflow", client)
        self.assertIn("Math.max(measuredOverflow, estimatedOverflow)", client)
        self.assertIn("--airplay-source-overflow", client)
        self.assertIn("--airplay-scroll-duration", client)
        self.assertIn("is-overflowing", client)
        self.assertIn("body.airplay-metadata-active .airplay-title-scroll-shell h1", style)
        self.assertIn("white-space: nowrap;", style)
        self.assertIn("animation: airplay-source-scroll", style)
        self.assertNotIn("style.textIndent", client)
        self.assertNotIn("text-indent:", style)
        self.assertIn("airplay-title-marquee.css", template)
        self.assertIn("airplay-title-marquee.js", template)
        self.assertIn("airplay-media-kind.js", template)
        self.assertLess(template.index("airplay-media-kind.js"), template.index("airplay-extra-controls.js"))


if __name__ == "__main__":
    unittest.main()
