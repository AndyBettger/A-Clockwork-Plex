from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request

DEFAULT_EQ_HELPER = '/usr/local/bin/a-clockwork-plex-audio-eq'
EQ_BANDS = {'bass', 'mid', 'treble'}


class MasterEqualizer:
    """Restricted client for the root-owned equalizer helper.

    The dashboard keeps the EQ controls and API available even while no audio
    backend is active. This lets the feature survive a backend rollback without
    inviting somebody to reinstall an unproven ALSA graph on a working Pi.
    """

    def __init__(
        self,
        helper_path: str | Path = DEFAULT_EQ_HELPER,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.helper_path = Path(helper_path)
        self.runner = runner or subprocess.run

    def _base_payload(self) -> dict[str, Any]:
        installed = self.helper_path.exists() and os.access(self.helper_path, os.X_OK)
        return {
            'available': False,
            'installed': installed,
            'configured': False,
            'mode': 'master-three-band',
            'backend_state': 'installed' if installed else 'offline',
            'activation': 'production' if installed else 'laboratory-only',
            'helper_path': str(self.helper_path),
            'bypassed': False,
            'bands': {
                band: {
                    'db': 0.0,
                    'stored_db': 0.0,
                    'effective_db': 0.0,
                    'minimum_db': -6.0,
                    'maximum_db': 6.0,
                    'available': False,
                }
                for band in ('bass', 'mid', 'treble')
            },
            'error': None if installed else (
                'The Master EQ controls are preserved, but no production EQ backend is active. '
                'The ALSA backend is being diagnosed with the isolated laboratory procedure in '
                'docs/master-eq-testing.md.'
            ),
        }

    def _invoke(self, *arguments: str, timeout: int = 12) -> tuple[int, dict[str, Any], str]:
        if not self.helper_path.exists():
            return 1, {}, 'The master EQ backend is not active.'
        command = ['sudo', '-n', str(self.helper_path), *arguments]
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, {}, str(exc)
        output = (result.stdout or '').strip()
        error = (result.stderr or '').strip()
        try:
            payload = json.loads(output or '{}')
        except json.JSONDecodeError:
            payload = {}
            if not error:
                error = output or 'The EQ helper returned invalid JSON.'
        if not isinstance(payload, dict):
            payload = {}
        if result.returncode and not error:
            error = str(payload.get('error') or output or 'The EQ helper failed.')
        return result.returncode, payload, error

    def status(self) -> dict[str, Any]:
        payload = self._base_payload()
        if not payload['installed']:
            return payload
        return_code, helper, error = self._invoke('status')
        if helper:
            payload.update(helper)
        payload.setdefault('mode', 'master-three-band')
        payload.setdefault('backend_state', 'active' if payload.get('available') else 'unavailable')
        payload.setdefault('activation', 'production')
        payload['helper_path'] = str(self.helper_path)
        if return_code or error:
            payload['available'] = False
            payload['backend_state'] = 'unavailable'
            payload['error'] = error or payload.get('error') or 'The EQ helper is unavailable.'
        elif payload.get('available'):
            payload['backend_state'] = 'active'
        return payload

    def set_band(self, band: Any, db_value: Any, *, persist: bool = True) -> dict[str, Any]:
        band_id = str(band or '').strip().lower()
        if band_id not in EQ_BANDS:
            raise ValueError(f'Unknown EQ band: {band_id or "-"}')
        try:
            gain = round(float(db_value) * 2) / 2
        except (TypeError, ValueError) as exc:
            raise ValueError('EQ gain must be a number.') from exc
        if not -6.0 <= gain <= 6.0:
            raise ValueError('EQ gain must be from -6 dB to +6 dB.')
        action = 'set' if persist else 'live'
        return_code, payload, error = self._invoke(action, band_id, f'{gain:g}')
        if return_code:
            raise RuntimeError(error or str(payload.get('error') or 'Could not change the master EQ.'))
        return payload

    def set_bypass(self, enabled: Any) -> dict[str, Any]:
        value = bool(enabled)
        return_code, payload, error = self._invoke('bypass', 'on' if value else 'off')
        if return_code:
            raise RuntimeError(error or str(payload.get('error') or 'Could not change EQ bypass.'))
        return payload

    def neutral(self) -> dict[str, Any]:
        return_code, payload, error = self._invoke('neutral')
        if return_code:
            raise RuntimeError(error or str(payload.get('error') or 'Could not reset the master EQ.'))
        return payload


def register_audio_eq(app: Flask, equalizer: MasterEqualizer | None = None) -> MasterEqualizer:
    controller = equalizer or MasterEqualizer()
    if 'api_audio_eq' in app.view_functions:
        return controller

    @app.route('/api/audio/eq', methods=['GET', 'POST'])
    def api_audio_eq():
        if request.method == 'GET':
            return jsonify({'ok': True, 'eq': controller.status()})

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'ok': False, 'error': 'EQ request must be a JSON object.'}), 400
        action = str(payload.get('action', 'set')).strip().lower()
        try:
            if action == 'set':
                status = controller.set_band(
                    payload.get('band'),
                    payload.get('db'),
                    persist=payload.get('persist', True) is not False,
                )
                message = f"{str(payload.get('band') or 'EQ').title()} adjusted."
            elif action == 'bypass':
                status = controller.set_bypass(payload.get('enabled'))
                message = 'Master EQ bypass updated.'
            elif action == 'neutral':
                status = controller.neutral()
                message = 'Master EQ returned to neutral.'
            else:
                raise ValueError(f'Unsupported EQ action: {action}')
        except ValueError as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 409
        return jsonify({'ok': True, 'eq': status, 'message': message})

    return controller
