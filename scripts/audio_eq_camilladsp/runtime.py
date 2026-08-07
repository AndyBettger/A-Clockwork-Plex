from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .model import (
    BANDS,
    FINAL_LIMITER_DB,
    USER_MAX_DB,
    USER_MIN_DB,
    PidSender,
    Runner,
    Settings,
    Sleeper,
    atomic_write,
    atomic_write_json,
    calculate_headroom_db,
    clamp_db,
    default_state,
    load_state,
    normalise_state,
    render_config,
    run,
    sha256,
)


class EqController:
    def __init__(
        self,
        settings: Settings,
        *,
        runner: Runner = run,
        signal_sender: PidSender = os.kill,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self.settings = settings
        self.runner = runner
        self.signal_sender = signal_sender
        self.sleeper = sleeper

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self.runner(command, capture_output=True, text=True, check=False)

    def _service_pid(self) -> int:
        result = self._run([
            '/usr/bin/systemctl',
            'show',
            self.settings.service,
            '--property=MainPID',
            '--value',
        ])
        try:
            return int((result.stdout or '').strip()) if result.returncode == 0 else 0
        except ValueError:
            return 0

    def _service_active(self) -> bool:
        result = self._run([
            '/usr/bin/systemctl',
            'is-active',
            '--quiet',
            self.settings.service,
        ])
        return result.returncode == 0

    def _route_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(
                self.settings.route_state_path.read_text(encoding='utf-8')
            )
        except (OSError, json.JSONDecodeError):
            return {'mode': 'offline', 'reason': 'route state is unavailable'}
        if isinstance(payload, dict):
            return payload
        return {'mode': 'offline', 'reason': 'invalid route state'}

    def _validate_candidate(self, path: Path) -> None:
        if not self.settings.binary.is_file() or not os.access(
            self.settings.binary, os.X_OK
        ):
            raise RuntimeError(
                f'CamillaDSP binary is unavailable: {self.settings.binary}'
            )
        result = self._run([str(self.settings.binary), '--check', str(path)])
        if result.returncode:
            detail = '\n'.join(
                part for part in (result.stdout, result.stderr) if part
            ).strip()
            raise RuntimeError(
                detail or 'CamillaDSP rejected the candidate configuration.'
            )

    def _write_candidate(self, content: str) -> Path:
        self.settings.active_config.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f'.{self.settings.active_config.name}.candidate.',
            dir=self.settings.active_config.parent,
        )
        candidate = Path(name)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        candidate.chmod(0o644)
        return candidate

    def _wait_for_same_process(self, expected_pid: int) -> None:
        for _ in range(15):
            if self._service_active() and self._service_pid() == expected_pid:
                return
            self.sleeper(0.1)
        observed = self._service_pid()
        raise RuntimeError(
            'CamillaDSP did not remain healthy after reload '
            f'(expected PID {expected_pid}, observed {observed or "none"}).'
        )

    def _reload_config(self, state: dict[str, Any], *, persist: bool) -> None:
        if not self.settings.active_config.is_file():
            raise RuntimeError(
                'Active CamillaDSP configuration is unavailable: '
                f'{self.settings.active_config}'
            )
        expected_pid = self._service_pid()
        if expected_pid <= 0 or not self._service_active():
            raise RuntimeError('CamillaDSP is not active; EQ changes are unavailable.')

        old_config = self.settings.active_config.read_bytes()
        old_state = (
            self.settings.state_path.read_bytes()
            if self.settings.state_path.exists()
            else None
        )
        candidate = self._write_candidate(render_config(self.settings, state))
        try:
            self._validate_candidate(candidate)
            candidate.replace(self.settings.active_config)
            self.signal_sender(expected_pid, signal.SIGHUP)
            self._wait_for_same_process(expected_pid)
            if persist:
                atomic_write_json(self.settings.state_path, normalise_state(state))
        except Exception as exc:
            try:
                atomic_write(
                    self.settings.active_config,
                    old_config.decode('utf-8'),
                    0o644,
                )
                if expected_pid > 0 and self._service_pid() == expected_pid:
                    self.signal_sender(expected_pid, signal.SIGHUP)
                    self._wait_for_same_process(expected_pid)
                if persist:
                    if old_state is None:
                        self.settings.state_path.unlink(missing_ok=True)
                    else:
                        atomic_write(
                            self.settings.state_path,
                            old_state.decode('utf-8'),
                            0o600,
                        )
            except Exception as rollback_exc:
                raise RuntimeError(
                    'EQ reload failed and rollback also failed: '
                    f'{exc}; rollback: {rollback_exc}'
                ) from exc
            raise RuntimeError(
                'EQ reload failed; the previous configuration was restored: '
                f'{exc}'
            ) from exc
        finally:
            candidate.unlink(missing_ok=True)

    def _selected_route_mode(self) -> str:
        return str(self._route_state().get('mode') or 'offline')

    def _effective_route_mode(self, selected: str, service_active: bool) -> str:
        if selected in {'split-bus-selected', 'split-bus-active'}:
            return 'split-bus-active' if service_active else 'split-bus-selected'
        return selected

    def _mutation_ready(self) -> None:
        selected = self._selected_route_mode()
        service_active = self._service_pid() > 0 and self._service_active()
        if selected not in {'split-bus-selected', 'split-bus-active'} or not service_active:
            effective = self._effective_route_mode(selected, service_active)
            raise RuntimeError(
                'The EQ curve is stored but cannot be applied while the audio '
                f'route is {effective}.'
            )

    def status(
        self,
        state_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = normalise_state(
            state_override
            if state_override is not None
            else load_state(self.settings.state_path)
        )
        route = self._route_state()
        selected_route_mode = str(route.get('mode') or 'offline')
        pid = self._service_pid()
        service_active = pid > 0 and self._service_active()
        route_mode = self._effective_route_mode(selected_route_mode, service_active)
        installed = self.settings.binary.is_file()
        configured = self.settings.active_config.is_file()
        available = (
            route_mode == 'split-bus-active'
            and installed
            and configured
            and service_active
        )
        applied = {
            band: 0.0 if state['bypassed'] or not available else state['bands'][band]
            for band in BANDS
        }
        headroom = calculate_headroom_db(
            applied,
            state['bypassed'] or not available,
        )

        error: str | None = None
        if route_mode == 'direct-failback':
            error = (
                'The saved EQ curve is unavailable while audio is using '
                'direct failback.'
            )
        elif route_mode == 'direct-rollback':
            error = (
                'The EQ backend is not installed in the active direct-audio profile.'
            )
        elif selected_route_mode in {'split-bus-selected', 'split-bus-active'} and not service_active:
            error = 'The split-bus route is selected but CamillaDSP is not active.'
        elif route_mode != 'split-bus-active':
            error = str(route.get('reason') or 'The EQ-capable audio route is offline.')
        elif not installed or not configured:
            error = 'The CamillaDSP EQ backend is incomplete.'

        return {
            'ok': available,
            'available': available,
            'installed': installed,
            'configured': configured,
            'mode': 'master-three-band',
            'backend': 'camilladsp',
            'backend_state': route_mode,
            'activation': 'production' if installed else 'laboratory-only',
            'bypassed': bool(state['bypassed']),
            'bands': {
                band: {
                    'db': state['bands'][band],
                    'stored_db': state['bands'][band],
                    'applied_db': applied[band],
                    'effective_db': applied[band],
                    'minimum_db': USER_MIN_DB,
                    'maximum_db': USER_MAX_DB,
                    'available': available,
                }
                for band in BANDS
            },
            'headroom_db': headroom,
            'final_limiter_db': FINAL_LIMITER_DB,
            'controls': [],
            'route_mode': route_mode,
            'selected_route_mode': selected_route_mode,
            'route_reason': route.get('reason'),
            'camilladsp_pid': pid or None,
            'camilladsp_config_sha256': sha256(self.settings.active_config),
            'error': error,
        }

    def set_band(self, band: str, value: Any, *, persist: bool) -> dict[str, Any]:
        if band not in BANDS:
            raise ValueError(f'Unknown EQ band: {band or "-"}')
        self._mutation_ready()
        state = load_state(self.settings.state_path)
        state['bands'][band] = clamp_db(value)
        self._reload_config(state, persist=persist)
        payload = self.status(state)
        payload.update({
            'changed_band': band,
            'requested_db': state['bands'][band],
            'persisted': persist,
        })
        return payload

    def set_bypass(self, enabled: bool) -> dict[str, Any]:
        self._mutation_ready()
        state = load_state(self.settings.state_path)
        state['bypassed'] = bool(enabled)
        self._reload_config(state, persist=True)
        return self.status(state)

    def neutral(self) -> dict[str, Any]:
        self._mutation_ready()
        state = default_state()
        self._reload_config(state, persist=True)
        return self.status(state)

    def locked(self):
        self.settings.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.settings.lock_path.open('a+', encoding='utf-8')
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle
