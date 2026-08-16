from __future__ import annotations

import io
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app.alarm_audio import render_tone_wav
from app.alarm_audio_streaming import iter_tone_pcm_chunks, stream_scheduled_alarm


TONE = {
    "id": "test-tone",
    "label": "Test tone",
    "pattern": [
        {
            "frequency": 440,
            "end_frequency": 660,
            "duration_ms": 120,
            "gap_ms": 40,
            "wave": "sine",
            "gain": 0.15,
        }
    ],
}


class FakeStdin:
    def __init__(self, process, events):
        self.process = process
        self.events = events
        self.closed = False

    def write(self, payload):
        self.events.append("write")
        return len(payload)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.events.append("stdin-close")
        self.process.returncode = 0


class FakeProcess:
    def __init__(self, events):
        self.events = events
        self.returncode = None
        self.stderr = io.BytesIO()
        self.stdin = FakeStdin(self, events)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class FakeManager:
    def __init__(self, events):
        self.events = events
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.state = {}
        self.process = None
        self.owner_snapshot = None

    def _record(self, action, **details):
        self.events.append(action)

    def _release(self, settings):
        self.events.append("release")
        return {"available": True, "handover_id": "handover-test"}

    def _restore(self, settings, snapshot):
        self.events.append("restore")

    def _tone(self, tone_id):
        return dict(TONE)

    def popen(self, command, **kwargs):
        self.events.append("popen")
        self.command = command
        self.popen_kwargs = kwargs
        return FakeProcess(self.events)

    @staticmethod
    def _terminate_process(process):
        if process is None:
            return None
        if process.poll() is None:
            process.terminate()
        return process.poll()


class AlarmAudioStreamingTests(unittest.TestCase):
    def test_stream_generator_matches_established_stereo_renderer(self):
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "reference.wav"
            render_tone_wav(
                TONE,
                wav_path,
                duration_seconds=1,
                start_percent=20,
                target_percent=80,
                fade_seconds=1,
            )
            with wave.open(str(wav_path), "rb") as reference:
                expected = reference.readframes(reference.getnframes())

        streamed = b"".join(
            iter_tone_pcm_chunks(
                TONE,
                duration_seconds=1,
                start_percent=20,
                target_percent=80,
                fade_seconds=1,
            )
        )
        self.assertEqual(streamed, expected)

    def test_aplay_starts_before_pcm_generator_is_consumed(self):
        events = []
        manager = FakeManager(events)
        occurrence = {
            "occurrence_key": "alarm|2026-08-16|12:00",
            "audio_duration_seconds": 3,
            "source": {
                "tone_id": "test-tone",
                "fallback_tone_id": "fallback-tone",
            },
            "volume": {
                "start_percent": 60,
                "target_percent": 85,
                "fade_seconds": 10,
            },
        }
        settings = {
            "alsa_device": "acp_alarm",
            "test_duration_seconds": 3,
            "test_volume_cap_percent": 100,
        }

        def generated_chunks(*args, **kwargs):
            events.append("generator-consumed")
            yield b"\x00" * 4096

        with patch("app.alarm_audio_streaming.shutil.which", return_value="/usr/bin/aplay"), patch(
            "app.alarm_audio_streaming.iter_tone_pcm_chunks",
            generated_chunks,
        ):
            stream_scheduled_alarm(manager, occurrence, settings)

        self.assertLess(events.index("popen"), events.index("generator-consumed"))
        self.assertLess(events.index("playback-started"), events.index("generator-consumed"))
        self.assertIn("write", events)
        self.assertIn("restore", events)
        self.assertIn("-t", manager.command)
        self.assertIn("raw", manager.command)
        self.assertIn("S16_LE", manager.command)
        self.assertIn("44100", manager.command)
        self.assertIn("2", manager.command)
        self.assertNotIn(".wav", " ".join(manager.command))
        self.assertIs(manager.popen_kwargs["stdin"], __import__("subprocess").PIPE)
        self.assertEqual(manager.popen_kwargs["bufsize"], 0)


if __name__ == "__main__":
    unittest.main()
