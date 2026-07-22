#!/usr/bin/python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG_PATH = Path('/etc/default/a-clockwork-plex-eq')
DEFAULT_STATE_PATH = Path('/var/lib/a-clockwork-plex/master-eq.json')
DEFAULT_DEVICE = 'acp_equal'
USER_MIN_DB = -6.0
USER_MAX_DB = 6.0
PLUGIN_MIN_DB = -48.0
PLUGIN_MAX_DB = 24.0

BAND_INDEXES: dict[str, tuple[int, ...]] = {
    'bass': (0, 1, 2),
    'mid': (3, 4, 5, 6),
    'treble': (7, 8, 9),
}


def emit(payload: dict[str, Any], code: int = 0) -> None:
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(code)


def load_config() -> dict[str, str]:
    values = {
        'ALSA_EQ_DEVICE': DEFAULT_DEVICE,
        'EQ_STATE_PATH': str(DEFAULT_STATE_PATH),
    }
    try:
        lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in values:
            values[key] = value
    return values


def run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def clamp_db(value: Any) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('EQ gain must be a number.') from exc
    number = max(USER_MIN_DB, min(USER_MAX_DB, number))
    return round(number * 2) / 2


def db_to_control_value(db_value: float) -> int:
    """Return the closest integer control value exposed by alsaequal.

    Alsaequal presents Eq10's -48 dB to +24 dB range as integers 0..100.
    Exact 0 dB would be 66.666..., so 67 is the closest representable value.
    """
    span = PLUGIN_MAX_DB - PLUGIN_MIN_DB
    return max(0, min(100, round(((db_value - PLUGIN_MIN_DB) / span) * 100)))


def control_value_to_db(control_value: int) -> float:
    value = max(0, min(100, int(control_value)))
    return PLUGIN_MIN_DB + (value / 100) * (PLUGIN_MAX_DB - PLUGIN_MIN_DB)


# Compatibility names used by older tests/status consumers.
def db_to_raw_percent(db_value: float) -> int:
    return db_to_control_value(db_value)


def raw_percent_to_db(raw_percent: int) -> float:
    return control_value_to_db(raw_percent)


def default_state() -> dict[str, Any]:
    return {
        'schema_version': 1,
        'bypassed': False,
        'bands': {'bass': 0.0, 'mid': 0.0, 'treble': 0.0},
    }


def load_state(path: Path) -> dict[str, Any]:
    state = default_state()
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return state
    if not isinstance(raw, dict):
        return state
    state['bypassed'] = bool(raw.get('bypassed'))
    raw_bands = raw.get('bands') if isinstance(raw.get('bands'), dict) else {}
    for band in BAND_INDEXES:
        try:
            state['bands'][band] = clamp_db(raw_bands.get(band, 0))
        except ValueError:
            state['bands'][band] = 0.0
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def control_sort_key(name: str) -> tuple[int, str]:
    match = re.match(r'\s*(\d+)\.', name)
    return (int(match.group(1)) if match else 999, name)


def discover_controls(device: str) -> tuple[list[str], str | None]:
    result = run(['/usr/bin/amixer', '-D', device, 'scontrols'])
    output = '\n'.join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode:
        return [], output or f'ALSA equalizer control device {device} is unavailable.'
    names = re.findall(r"Simple mixer control '([^']+)'", output)
    names = sorted(dict.fromkeys(names), key=control_sort_key)
    if len(names) < 10:
        return names, f'Expected ten Eq10 controls but found {len(names)}.'
    return names[:10], None


def parse_control_contents(output: str) -> dict[str, dict[str, float | int | None]]:
    """Parse diagnostic mixer output without inventing dB from percentages.

    Alsaequal writes a float, then its read callback converts that float back to
    a long by truncation. A control written as 67 can therefore be reported by
    amixer as 66%. That reported percentage is useful for diagnostics but is not
    a reliable inverse mapping to the dB value that was written.
    """
    controls: dict[str, dict[str, float | int | None]] = {}
    matches = list(re.finditer(r"(?m)^Simple mixer control '([^']+)'", output))
    for index, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        block = output[start:end]
        raw_matches = re.findall(r'\[(\d{1,3})%\]', block)
        db_matches = re.findall(r'\[(-?\d+(?:\.\d+)?)dB\]', block)
        reported_percent = int(raw_matches[0]) if raw_matches else None
        reported_db = float(db_matches[0]) if db_matches else None
        controls[name] = {
            'reported_percent': reported_percent,
            'reported_db': round(reported_db, 2) if reported_db is not None else None,
        }
    return controls


def read_controls(
    device: str,
    names: list[str],
    applied_bands: dict[str, float],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], str | None]:
    result = run(['/usr/bin/amixer', '-D', device, 'scontents'])
    output = '\n'.join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode:
        return {}, [], output or 'Could not read equalizer controls.'

    parsed = parse_control_contents(output)
    band_diagnostics: dict[str, dict[str, Any]] = {}
    control_payload: list[dict[str, Any]] = []

    for band, indexes in BAND_INDEXES.items():
        requested_db = clamp_db(applied_bands.get(band, 0.0))
        control_value = db_to_control_value(requested_db)
        quantised_db = round(control_value_to_db(control_value), 2)
        reported_values: list[int] = []
        in_sync = True

        for index in indexes:
            name = names[index]
            diagnostic = parsed.get(name, {})
            reported = diagnostic.get('reported_percent')
            if isinstance(reported, int):
                reported_values.append(reported)
                # The plugin read callback can truncate by one because it stores
                # the control as float and returns it through a long integer API.
                in_sync = in_sync and abs(reported - control_value) <= 1
            control_payload.append({
                'band': band,
                'name': name,
                'requested_db': requested_db,
                'control_value': control_value,
                'quantised_db': quantised_db,
                'in_sync': abs(reported - control_value) <= 1 if isinstance(reported, int) else None,
                **diagnostic,
            })

        band_diagnostics[band] = {
            'requested_db': requested_db,
            'control_value': control_value,
            'quantised_db': quantised_db,
            'reported_percent': (
                round(sum(reported_values) / len(reported_values), 2)
                if reported_values else None
            ),
            'in_sync': in_sync if reported_values else None,
        }

    return band_diagnostics, control_payload, None


def set_controls(device: str, names: list[str], band: str, db_value: float) -> str | None:
    control_value = db_to_control_value(db_value)
    for index in BAND_INDEXES[band]:
        result = run([
            '/usr/bin/amixer', '-D', device, '-q', 'sset', names[index], str(control_value)
        ])
        if result.returncode:
            output = '\n'.join(part for part in (result.stdout, result.stderr) if part).strip()
            return output or f'Could not set {names[index]}.'
    return None


def apply_bands(device: str, names: list[str], bands: dict[str, Any]) -> str | None:
    for band in BAND_INDEXES:
        error = set_controls(device, names, band, clamp_db(bands.get(band, 0)))
        if error:
            return error
    return None


def unavailable_status(state: dict[str, Any], device: str, error: str) -> dict[str, Any]:
    applied_bands = {band: 0.0 for band in BAND_INDEXES} if state['bypassed'] else state['bands']
    return {
        'ok': False,
        'available': False,
        'installed': Path('/usr/lib').exists(),
        'configured': False,
        'device': device,
        'bypassed': state['bypassed'],
        'bands': {
            band: {
                'db': state['bands'][band],
                'stored_db': state['bands'][band],
                'applied_db': applied_bands[band],
                'effective_db': round(control_value_to_db(db_to_control_value(applied_bands[band])), 2),
                'minimum_db': USER_MIN_DB,
                'maximum_db': USER_MAX_DB,
                'available': False,
            }
            for band in BAND_INDEXES
        },
        'controls': [],
        'error': error,
    }


def full_status() -> dict[str, Any]:
    config = load_config()
    device = config['ALSA_EQ_DEVICE']
    state_path = Path(config['EQ_STATE_PATH'])
    state = load_state(state_path)
    names, discovery_error = discover_controls(device)
    if discovery_error:
        return unavailable_status(state, device, discovery_error)

    applied_bands = {band: 0.0 for band in BAND_INDEXES} if state['bypassed'] else state['bands']
    diagnostics, controls, read_error = read_controls(device, names, applied_bands)
    bands: dict[str, dict[str, Any]] = {}

    for band in BAND_INDEXES:
        diagnostic = diagnostics.get(band, {})
        bands[band] = {
            # The managed half-dB request is the public/UI value. The plugin's
            # truncated percentage readback is diagnostic only.
            'db': state['bands'][band],
            'stored_db': state['bands'][band],
            'applied_db': applied_bands[band],
            'effective_db': diagnostic.get(
                'quantised_db',
                round(control_value_to_db(db_to_control_value(applied_bands[band])), 2),
            ),
            'control_value': diagnostic.get('control_value'),
            'reported_percent': diagnostic.get('reported_percent'),
            'in_sync': diagnostic.get('in_sync'),
            'minimum_db': USER_MIN_DB,
            'maximum_db': USER_MAX_DB,
            'available': read_error is None,
        }

    neutral_control = db_to_control_value(0.0)
    return {
        'ok': read_error is None,
        'available': read_error is None,
        'installed': True,
        'configured': read_error is None,
        'device': device,
        'bypassed': state['bypassed'],
        'bands': bands,
        'controls': controls,
        'neutral_control_value': neutral_control,
        'neutral_effective_db': round(control_value_to_db(neutral_control), 2),
        'quantisation_note': (
            'Alsaequal exposes Eq10 through integer controls 0..100; '
            '0 dB maps to 66.666, so control 67 (+0.24 dB) is the closest available neutral.'
        ),
        'error': read_error,
    }


def set_band(band: str, value: Any, *, persist: bool) -> dict[str, Any]:
    if band not in BAND_INDEXES:
        raise ValueError(f'Unknown EQ band: {band or "-"}')
    db_value = clamp_db(value)
    config = load_config()
    device = config['ALSA_EQ_DEVICE']
    state_path = Path(config['EQ_STATE_PATH'])
    state = load_state(state_path)
    names, error = discover_controls(device)
    if error:
        raise RuntimeError(error)

    if persist:
        state['bands'][band] = db_value
        save_state(state_path, state)
    if not state['bypassed']:
        error = set_controls(device, names, band, db_value)
        if error:
            raise RuntimeError(error)
    payload = full_status()
    payload.update({'changed_band': band, 'requested_db': db_value, 'persisted': persist})
    return payload


def set_bypass(enabled: bool) -> dict[str, Any]:
    config = load_config()
    device = config['ALSA_EQ_DEVICE']
    state_path = Path(config['EQ_STATE_PATH'])
    state = load_state(state_path)
    names, error = discover_controls(device)
    if error:
        raise RuntimeError(error)

    if enabled and not state['bypassed']:
        # The managed state already contains the authoritative curve. Do not
        # overwrite it with alsaequal's lossy/truncated percentage readback.
        error = apply_bands(device, names, {band: 0.0 for band in BAND_INDEXES})
        if error:
            raise RuntimeError(error)
        state['bypassed'] = True
    elif not enabled and state['bypassed']:
        error = apply_bands(device, names, state['bands'])
        if error:
            raise RuntimeError(error)
        state['bypassed'] = False
    save_state(state_path, state)
    return full_status()


def neutral() -> dict[str, Any]:
    config = load_config()
    device = config['ALSA_EQ_DEVICE']
    state_path = Path(config['EQ_STATE_PATH'])
    names, error = discover_controls(device)
    if error:
        raise RuntimeError(error)
    state = default_state()
    error = apply_bands(device, names, state['bands'])
    if error:
        raise RuntimeError(error)
    save_state(state_path, state)
    return full_status()


def main() -> None:
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'status'
    try:
        if action == 'status' and len(sys.argv) == 2:
            emit(full_status())
        if action in {'set', 'live'} and len(sys.argv) == 4:
            emit(set_band(sys.argv[2].strip().lower(), sys.argv[3], persist=action == 'set'))
        if action == 'bypass' and len(sys.argv) == 3:
            value = sys.argv[2].strip().lower()
            if value not in {'on', 'off', 'true', 'false', '1', '0'}:
                raise ValueError('Bypass must be on or off.')
            emit(set_bypass(value in {'on', 'true', '1'}))
        if action == 'neutral' and len(sys.argv) == 2:
            emit(neutral())
        raise ValueError(
            'Usage: a-clockwork-plex-audio-eq '
            '{status|set <bass|mid|treble> <-6..6>|live <band> <-6..6>|bypass <on|off>|neutral}'
        )
    except ValueError as exc:
        emit({'ok': False, 'error': str(exc)}, 64)
    except RuntimeError as exc:
        emit({'ok': False, 'error': str(exc)}, 70)


if __name__ == '__main__':
    main()
