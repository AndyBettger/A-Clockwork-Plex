from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

CONFIG_PATH = Path('/etc/default/a-clockwork-plex-split-bus')
USER_MIN_DB = -6.0
USER_MAX_DB = 6.0
STEP_DB = 0.5
HEADROOM_MARGIN_DB = 0.5
FINAL_LIMITER_DB = -1.0
BANDS = ('bass', 'mid', 'treble')


class Settings:
    def __init__(
        self,
        *,
        binary: Path = Path('/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp'),
        active_config: Path = Path('/etc/a-clockwork-plex/camilladsp-split-bus.yml'),
        state_path: Path = Path('/var/lib/a-clockwork-plex/split-bus/master-eq.json'),
        route_state_path: Path = Path('/var/lib/a-clockwork-plex/split-bus/route-state.json'),
        lock_path: Path = Path('/run/lock/a-clockwork-plex-audio-route.lock'),
        service: str = 'a-clockwork-plex-camilladsp.service',
        sample_rate: int = 44100,
        sample_format: str = 'S16_LE',
        chunksize: int = 1024,
        target_level: int = 2048,
        loopback_index: int = 7,
        dac_card: str = 'Pro',
        dac_device: int = 0,
    ) -> None:
        self.binary = binary
        self.active_config = active_config
        self.state_path = state_path
        self.route_state_path = route_state_path
        self.lock_path = lock_path
        self.service = service
        self.sample_rate = sample_rate
        self.sample_format = sample_format
        self.chunksize = chunksize
        self.target_level = target_level
        self.loopback_index = loopback_index
        self.dac_card = dac_card
        self.dac_device = dac_device


Runner = Callable[..., subprocess.CompletedProcess[str]]
PidSender = Callable[[int, int], None]
Sleeper = Callable[[float], None]


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, **kwargs)


def _read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    values = _read_key_values(path)
    defaults = Settings()

    def integer(name: str, default: int) -> int:
        try:
            return int(values.get(name, str(default)))
        except ValueError:
            return default

    return Settings(
        binary=Path(values.get('CAMILLADSP_BINARY', str(defaults.binary))),
        active_config=Path(values.get('CAMILLADSP_CONFIG', str(defaults.active_config))),
        state_path=Path(values.get('EQ_STATE_PATH', str(defaults.state_path))),
        route_state_path=Path(values.get('ROUTE_STATE_PATH', str(defaults.route_state_path))),
        lock_path=Path(values.get('AUDIO_LOCK_PATH', str(defaults.lock_path))),
        service=values.get('CAMILLADSP_SERVICE', defaults.service),
        sample_rate=integer('SAMPLE_RATE', defaults.sample_rate),
        sample_format=values.get('FORMAT', defaults.sample_format),
        chunksize=integer('CHUNKSIZE', defaults.chunksize),
        target_level=integer('TARGET_LEVEL', defaults.target_level),
        loopback_index=integer('LOOPBACK_INDEX', defaults.loopback_index),
        dac_card=values.get('DAC_CARD', defaults.dac_card),
        dac_device=integer('DAC_DEVICE', defaults.dac_device),
    )


def clamp_db(value: Any) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('EQ gain must be a number.') from exc
    number = max(USER_MIN_DB, min(USER_MAX_DB, number))
    return round(number / STEP_DB) * STEP_DB


def default_state() -> dict[str, Any]:
    return {
        'schema_version': 2,
        'bypassed': False,
        'bands': {band: 0.0 for band in BANDS},
    }


def normalise_state(raw: Any) -> dict[str, Any]:
    state = default_state()
    if not isinstance(raw, dict):
        return state
    state['bypassed'] = bool(raw.get('bypassed'))
    raw_bands = raw.get('bands') if isinstance(raw.get('bands'), dict) else {}
    for band in BANDS:
        try:
            state['bands'][band] = clamp_db(raw_bands.get(band, 0.0))
        except ValueError:
            state['bands'][band] = 0.0
    return state


def load_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default_state()
    return normalise_state(raw)


def calculate_headroom_db(bands: dict[str, Any], bypassed: bool = False) -> float:
    if bypassed:
        return 0.0
    largest_boost = max(0.0, *(clamp_db(bands.get(band, 0.0)) for band in BANDS))
    return -(largest_boost + HEADROOM_MARGIN_DB) if largest_boost > 0 else 0.0


def render_config(settings: Settings, state: dict[str, Any]) -> str:
    state = normalise_state(state)
    bypassed = bool(state['bypassed'])
    applied = {band: clamp_db(state['bands'][band]) for band in BANDS}
    headroom = calculate_headroom_db(applied)
    pipeline_bypassed = 'true' if bypassed else 'false'
    return f'''---
title: "A Clockwork Plex EQ-capable split bus"
description: "Music-only three-band EQ and headroom, independent alarm, final limiter"
devices:
  samplerate: {settings.sample_rate}
  chunksize: {settings.chunksize}
  queuelimit: 4
  silence_timeout: 0
  target_level: {settings.target_level}
  adjust_period: 1
  enable_rate_adjust: true
  resampler: null
  volume_ramp_time: 100
  volume_limit: 0.0
  capture:
    type: Alsa
    channels: 4
    device: "hw:{settings.loopback_index},1,0"
    format: {settings.sample_format}
  playback:
    type: Alsa
    channels: 2
    device: "hw:CARD={settings.dac_card},DEV={settings.dac_device}"
    format: {settings.sample_format}
filters:
  bass:
    type: Biquad
    parameters: {{type: Lowshelf, freq: 125, gain: {applied['bass']:.1f}, slope: 6}}
  mid:
    type: Biquad
    parameters: {{type: Peaking, freq: 1000, gain: {applied['mid']:.1f}, q: 0.7}}
  treble:
    type: Biquad
    parameters: {{type: Highshelf, freq: 4000, gain: {applied['treble']:.1f}, slope: 6}}
  headroom:
    type: Gain
    parameters: {{gain: {headroom:.1f}, scale: dB, inverted: false, mute: false}}
  final_safety_limiter:
    type: Limiter
    parameters: {{soft_clip: false, clip_limit: {FINAL_LIMITER_DB:.1f}}}
mixers:
  combine_music_and_alarm:
    channels: {{in: 4, out: 2}}
    mapping:
      - dest: 0
        sources:
          - {{channel: 0, gain: 0, scale: dB, inverted: false}}
          - {{channel: 2, gain: 0, scale: dB, inverted: false}}
      - dest: 1
        sources:
          - {{channel: 1, gain: 0, scale: dB, inverted: false}}
          - {{channel: 3, gain: 0, scale: dB, inverted: false}}
pipeline:
  - {{type: Filter, channels: [0, 1], bypassed: {pipeline_bypassed}, names: [bass, mid, treble, headroom]}}
  - {{type: Mixer, name: combine_music_and_alarm}}
  - {{type: Filter, channels: [0, 1], names: [final_safety_limiter]}}
'''


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def atomic_write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + '\n', mode)
