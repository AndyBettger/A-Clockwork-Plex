#!/usr/bin/python3
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
INSTALLED_EQ_ROOT = Path('/usr/local/lib/a-clockwork-plex/audio-eq')
for root in (INSTALLED_EQ_ROOT, SCRIPT_DIR):
    if root.is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

from audio_eq_camilladsp import (  # noqa: E402
    Settings as EqSettings,
    atomic_write,
    atomic_write_json,
    load_state,
    render_config,
    sha256,
)

CONFIG_PATH = Path('/etc/default/a-clockwork-plex-split-bus')
PUBLIC_PCMS = ('acp_dmix', 'acp_master', 'acp_plexamp', 'acp_airplay', 'acp_alarm')
APP_STOP_ORDER = ('dashboard', 'airplay', 'plexamp')
APP_START_ORDER = ('plexamp', 'airplay', 'dashboard')
Runner = Callable[..., subprocess.CompletedProcess[str]]
Sleeper = Callable[[float], None]


class RouteSettings:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        data = values or {}
        self.project_user = data.get('PROJECT_USER', 'andy')
        self.dac_card = data.get('DAC_CARD', 'Pro')
        self.dac_device = int(data.get('DAC_DEVICE', '0'))
        self.loopback_index = int(data.get('LOOPBACK_INDEX', '7'))
        self.loopback_id = data.get('LOOPBACK_ID', 'ACP_Loopback')
        self.sample_rate = int(data.get('SAMPLE_RATE', '44100'))
        self.sample_format = data.get('FORMAT', 'S16_LE')
        self.chunksize = int(data.get('CHUNKSIZE', '1024'))
        self.target_level = int(data.get('TARGET_LEVEL', '2048'))
        self.camilladsp_version = data.get('CAMILLADSP_VERSION', '4.1.3')
        self.camilladsp_sha256 = data.get(
            'CAMILLADSP_SHA256',
            'e04c7a6603e9482bab33c1e18afc41d3c07410b54ba9c246eda69f7e9cbaedfa',
        )
        self.active_alsa = Path(data.get(
            'ACTIVE_ALSA_CONFIG',
            '/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf',
        ))
        self.split_route = Path(data.get(
            'SPLIT_ROUTE',
            '/etc/a-clockwork-plex/audio-routes/split-bus.conf',
        ))
        self.direct_route = Path(data.get(
            'DIRECT_FAILBACK_ROUTE',
            '/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf',
        ))
        self.camilladsp_binary = Path(data.get(
            'CAMILLADSP_BINARY',
            '/usr/local/lib/a-clockwork-plex/camilladsp-4.1.3/camilladsp',
        ))
        self.camilladsp_config = Path(data.get(
            'CAMILLADSP_CONFIG',
            '/etc/a-clockwork-plex/camilladsp-split-bus.yml',
        ))
        self.state_dir = Path(data.get(
            'STATE_DIR',
            '/var/lib/a-clockwork-plex/split-bus',
        ))
        self.eq_state = Path(data.get(
            'EQ_STATE_PATH',
            str(self.state_dir / 'master-eq.json'),
        ))
        self.route_state = Path(data.get(
            'ROUTE_STATE_PATH',
            str(self.state_dir / 'route-state.json'),
        ))
        self.installed_marker = Path(data.get(
            'INSTALLED_MARKER',
            str(self.state_dir / 'installed'),
        ))
        self.lock_path = Path(data.get(
            'AUDIO_LOCK_PATH',
            '/run/lock/a-clockwork-plex-audio-route.lock',
        ))
        self.camilladsp_service = data.get(
            'CAMILLADSP_SERVICE',
            'a-clockwork-plex-camilladsp.service',
        )
        self.route_service = data.get(
            'ROUTE_SERVICE',
            'a-clockwork-plex-audio-route.service',
        )
        self.failback_service = data.get(
            'FAILBACK_SERVICE',
            'a-clockwork-plex-audio-failback.service',
        )
        self.services = {
            'plexamp': data.get('PLEXAMP_SERVICE', 'plexamp.service'),
            'airplay': data.get('AIRPLAY_SERVICE', 'shairport-sync.service'),
            'dashboard': data.get('DASHBOARD_SERVICE', 'a-clockwork-plex.service'),
        }
        self.dac_hw_params = Path(data.get(
            'DAC_HW_PARAMS',
            '/proc/asound/Pro/pcm0p/sub0/hw_params',
        ))
        self.alsa_base = Path(data.get(
            'ALSA_BASE_CONFIG',
            '/usr/share/alsa/alsa.conf',
        ))
        self.cards_path = Path(data.get('ALSA_CARDS_PATH', '/proc/asound/cards'))
        self.module_parameters = Path(data.get(
            'LOOPBACK_PARAMETERS_PATH',
            '/sys/module/snd_aloop/parameters',
        ))

    def eq_settings(self) -> EqSettings:
        return EqSettings(
            binary=self.camilladsp_binary,
            active_config=self.camilladsp_config,
            state_path=self.eq_state,
            route_state_path=self.route_state,
            lock_path=self.lock_path,
            service=self.camilladsp_service,
            sample_rate=self.sample_rate,
            sample_format=self.sample_format,
            chunksize=self.chunksize,
            target_level=self.target_level,
            loopback_index=self.loopback_index,
            dac_card=self.dac_card,
            dac_device=self.dac_device,
        )


def read_defaults(path: Path = CONFIG_PATH) -> dict[str, str]:
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


def emit(payload: dict[str, Any], code: int = 0, *, stderr: bool = False) -> int:
    print(json.dumps(payload, sort_keys=True), file=sys.stderr if stderr else sys.stdout)
    return code


def _remove_global_hooks(base: str) -> str:
    lines = base.splitlines()
    result: list[str] = []
    skipping = False
    depth = 0
    removed = False
    for line in lines:
        stripped = line.strip()
        if not removed and not skipping and stripped.startswith('@hooks') and '[' in stripped:
            skipping = True
            depth = line.count('[') - line.count(']')
            if depth == 0:
                skipping = False
                removed = True
            continue
        if skipping:
            depth += line.count('[') - line.count(']')
            if depth == 0:
                skipping = False
                removed = True
            continue
        result.append(line)
    if not removed:
        raise RuntimeError('Could not isolate the ALSA base configuration.')
    return '\n'.join(result).rstrip() + '\n'


class RouteController:
    def __init__(
        self,
        settings: RouteSettings,
        *,
        runner: Runner = subprocess.run,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self.settings = settings
        self.runner = runner
        self.sleeper = sleeper

    def _run(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self.runner(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def locked(self):
        self.settings.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.settings.lock_path.open('a+', encoding='utf-8')
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    def _service_active(self, unit: str) -> bool:
        return self._run([
            '/usr/bin/systemctl', 'is-active', '--quiet', unit,
        ]).returncode == 0

    def _service_enabled(self, unit: str) -> bool:
        return self._run([
            '/usr/bin/systemctl', 'is-enabled', '--quiet', unit,
        ]).returncode == 0

    def _service_pid(self, unit: str) -> int:
        result = self._run([
            '/usr/bin/systemctl', 'show', unit, '--property=MainPID', '--value',
        ])
        try:
            return int((result.stdout or '').strip()) if result.returncode == 0 else 0
        except ValueError:
            return 0

    def _systemctl(self, action: str, unit: str) -> None:
        result = self._run(['/usr/bin/systemctl', action, unit])
        if result.returncode:
            detail = '\n'.join(
                part for part in (result.stdout, result.stderr) if part
            ).strip()
            raise RuntimeError(detail or f'systemctl {action} failed for {unit}')

    def _module_parameter(self, name: str) -> str | None:
        try:
            return (
                (self.settings.module_parameters / name)
                .read_text(encoding='utf-8')
                .strip()
                .split(',', 1)[0]
            )
        except OSError:
            return None

    def loopback_status(self) -> dict[str, Any]:
        parameters = {
            name: self._module_parameter(name)
            for name in ('index', 'id', 'pcm_substreams', 'pcm_notify')
        }
        try:
            cards = self.settings.cards_path.read_text(encoding='utf-8')
        except OSError:
            cards = ''
        card_present = bool(re.search(
            rf'^\s*{self.settings.loopback_index}\s+\[ACPLoopback\s*\]',
            cards,
            re.MULTILINE,
        ))
        expected = {
            'index': str(self.settings.loopback_index),
            'id': self.settings.loopback_id,
            'pcm_substreams': '2',
            'pcm_notify': '1',
        }
        return {
            'ok': card_present and parameters == expected,
            'card_present': card_present,
            'expected': expected,
            'observed': parameters,
        }

    def _validate_alsa(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f'ALSA route is unavailable: {path}')
        try:
            isolated = _remove_global_hooks(
                self.settings.alsa_base.read_text(encoding='utf-8')
            )
        except OSError as exc:
            raise RuntimeError(
                f'ALSA base configuration is unavailable: {self.settings.alsa_base}'
            ) from exc
        with tempfile.TemporaryDirectory(prefix='a-clockwork-plex-alsa-check.') as directory:
            validation = Path(directory) / 'alsa.conf'
            validation.write_text(
                isolated + '\n' + path.read_text(encoding='utf-8'),
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['ALSA_CONFIG_PATH'] = str(validation)
            result = self._run(['/usr/bin/aplay', '-L'], env=env)
        if result.returncode:
            detail = '\n'.join(
                part for part in (result.stdout, result.stderr) if part
            ).strip()
            raise RuntimeError(detail or f'ALSA rejected {path}')
        names = set((result.stdout or '').splitlines())
        missing = [pcm for pcm in PUBLIC_PCMS if pcm not in names]
        if missing:
            raise RuntimeError(
                f'ALSA route {path} is missing public PCMs: {", ".join(missing)}'
            )
        return {'path': str(path), 'sha256': sha256(path), 'public_pcms': list(PUBLIC_PCMS)}

    def _validate_binary(self) -> dict[str, Any]:
        binary = self.settings.camilladsp_binary
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError(f'CamillaDSP binary is unavailable: {binary}')
        observed_hash = sha256(binary)
        if observed_hash != self.settings.camilladsp_sha256:
            raise RuntimeError(
                'CamillaDSP checksum mismatch: '
                f'expected {self.settings.camilladsp_sha256}, observed {observed_hash}'
            )
        result = self._run([str(binary), '--version'])
        version = ((result.stdout or result.stderr) or '').splitlines()
        first_line = version[0] if version else ''
        if result.returncode or self.settings.camilladsp_version not in first_line:
            raise RuntimeError(f'Unexpected CamillaDSP version: {first_line or "unknown"}')
        return {'path': str(binary), 'sha256': observed_hash, 'version': first_line}

    def _validate_camilla(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f'CamillaDSP configuration is unavailable: {path}')
        result = self._run([
            str(self.settings.camilladsp_binary), '--check', str(path),
        ])
        if result.returncode:
            detail = '\n'.join(
                part for part in (result.stdout, result.stderr) if part
            ).strip()
            raise RuntimeError(detail or f'CamillaDSP rejected {path}')
        return {'path': str(path), 'sha256': sha256(path)}

    def validate(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        errors: list[str] = []
        for name, operation in (
            ('split_route', lambda: self._validate_alsa(self.settings.split_route)),
            ('direct_route', lambda: self._validate_alsa(self.settings.direct_route)),
            ('binary', self._validate_binary),
            ('loopback', self.loopback_status),
        ):
            try:
                value = operation()
                checks[name] = value
                if name == 'loopback' and not value['ok']:
                    errors.append('snd_aloop does not match the accepted contract')
            except RuntimeError as exc:
                checks[name] = {'ok': False, 'error': str(exc)}
                errors.append(str(exc))
        if self.settings.camilladsp_config.is_file():
            try:
                checks['camilladsp_config'] = self._validate_camilla(
                    self.settings.camilladsp_config
                )
            except RuntimeError as exc:
                checks['camilladsp_config'] = {'ok': False, 'error': str(exc)}
                errors.append(str(exc))
        return {'ok': not errors, 'checks': checks, 'errors': errors}

    def _read_route_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(
                self.settings.route_state.read_text(encoding='utf-8')
            )
        except (OSError, json.JSONDecodeError):
            return {'mode': 'offline', 'reason': 'route state is unavailable'}
        return payload if isinstance(payload, dict) else {
            'mode': 'offline',
            'reason': 'invalid route state',
        }

    def _write_route_state(self, mode: str, reason: str) -> None:
        payload = {
            'schema_version': 1,
            'mode': mode,
            'reason': reason,
            'transition_time': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'active_alsa_sha256': sha256(self.settings.active_alsa),
            'split_route_sha256': sha256(self.settings.split_route),
            'direct_failback_sha256': sha256(self.settings.direct_route),
            'camilladsp_config_sha256': sha256(self.settings.camilladsp_config),
        }
        atomic_write_json(self.settings.route_state, payload, 0o644)

    def status(self) -> dict[str, Any]:
        route_state = self._read_route_state()
        active_hash = sha256(self.settings.active_alsa)
        split_hash = sha256(self.settings.split_route)
        direct_hash = sha256(self.settings.direct_route)
        selected = str(route_state.get('mode') or 'offline')
        camilla_active = self._service_active(self.settings.camilladsp_service)
        camilla_pid = self._service_pid(self.settings.camilladsp_service)
        effective = (
            'split-bus-active'
            if selected in {'split-bus-selected', 'split-bus-active'}
            and camilla_active
            and camilla_pid > 0
            else selected
        )
        services = {
            name: {
                'unit': unit,
                'active': self._service_active(unit),
                'enabled': self._service_enabled(unit),
            }
            for name, unit in {
                **self.settings.services,
                'camilladsp': self.settings.camilladsp_service,
                'route': self.settings.route_service,
                'failback': self.settings.failback_service,
            }.items()
        }
        return {
            'ok': effective in {'split-bus-active', 'direct-failback', 'direct-rollback'},
            'selected_mode': selected,
            'mode': effective,
            'reason': route_state.get('reason'),
            'active_alsa_sha256': active_hash,
            'split_route_sha256': split_hash,
            'direct_failback_sha256': direct_hash,
            'active_matches_split': bool(active_hash and active_hash == split_hash),
            'active_matches_direct_failback': bool(active_hash and active_hash == direct_hash),
            'camilladsp_config_sha256': sha256(self.settings.camilladsp_config),
            'camilladsp_pid': camilla_pid or None,
            'loopback': self.loopback_status(),
            'services': services,
            'installed_marker': self.settings.installed_marker.exists(),
            'state': route_state,
        }

    def _install_route(self, source: Path) -> None:
        self._validate_alsa(source)
        atomic_write(
            self.settings.active_alsa,
            source.read_text(encoding='utf-8'),
            0o644,
        )

    def _render_saved_camilla(self) -> None:
        state = load_state(self.settings.eq_state)
        content = render_config(self.settings.eq_settings(), state)
        self.settings.camilladsp_config.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f'.{self.settings.camilladsp_config.name}.candidate.',
            dir=self.settings.camilladsp_config.parent,
        )
        candidate = Path(name)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            candidate.chmod(0o644)
            self._validate_camilla(candidate)
            atomic_write(self.settings.camilladsp_config, content, 0o644)
        finally:
            candidate.unlink(missing_ok=True)

    def _snapshot_applications(self) -> dict[str, bool]:
        return {
            name: self._service_active(self.settings.services[name])
            for name in APP_START_ORDER
        }

    def _stop_applications(self, snapshot: dict[str, bool]) -> None:
        for name in APP_STOP_ORDER:
            if snapshot.get(name):
                self._systemctl('stop', self.settings.services[name])

    def _restore_applications(self, snapshot: dict[str, bool]) -> None:
        failures: list[str] = []
        for name in APP_START_ORDER:
            if not snapshot.get(name):
                continue
            try:
                self._systemctl('start', self.settings.services[name])
            except RuntimeError as exc:
                failures.append(str(exc))
        if failures:
            raise RuntimeError('; '.join(failures))

    def _stop_camilla(self) -> None:
        if self._service_active(self.settings.camilladsp_service):
            self._systemctl('stop', self.settings.camilladsp_service)

    def _wait_dac_released(self) -> None:
        for _ in range(40):
            try:
                value = self.settings.dac_hw_params.read_text(encoding='utf-8').strip()
            except OSError:
                value = ''
            if value in {'', 'closed'}:
                return
            self.sleeper(0.1)
        raise RuntimeError('The physical DAC did not become idle.')

    def _wait_camilla_active(self) -> None:
        for _ in range(40):
            if (
                self._service_active(self.settings.camilladsp_service)
                and self._service_pid(self.settings.camilladsp_service) > 0
            ):
                return
            self.sleeper(0.1)
        raise RuntimeError('CamillaDSP did not become active.')

    def _select_direct_locked(self, reason: str) -> None:
        self._install_route(self.settings.direct_route)
        self._write_route_state('direct-failback', reason)

    def prepare_split_bus(self) -> dict[str, Any]:
        with self.locked():
            try:
                direct = self._validate_alsa(self.settings.direct_route)
                split = self._validate_alsa(self.settings.split_route)
                binary = self._validate_binary()
                loopback = self.loopback_status()
                if not loopback['ok']:
                    raise RuntimeError('snd_aloop does not match the accepted contract')
                self._render_saved_camilla()
                self._install_route(self.settings.split_route)
                self._write_route_state(
                    'split-bus-selected',
                    'validated split-bus route selected; CamillaDSP service health is evaluated separately',
                )
                return {
                    'ok': True,
                    'mode': 'split-bus-selected',
                    'split_route': split,
                    'direct_failback': direct,
                    'binary': binary,
                    'loopback': loopback,
                    'camilladsp_config_sha256': sha256(self.settings.camilladsp_config),
                }
            except RuntimeError as exc:
                try:
                    self._select_direct_locked(f'split-bus preparation failed: {exc}')
                except RuntimeError as failback_exc:
                    raise RuntimeError(
                        f'Split-bus preparation failed and direct failback failed: {exc}; {failback_exc}'
                    ) from exc
                raise RuntimeError(
                    f'Split-bus preparation failed; direct failback was selected: {exc}'
                ) from exc

    def activate_split_bus(self) -> dict[str, Any]:
        snapshot = self._snapshot_applications()
        self._stop_applications(snapshot)
        try:
            self._stop_camilla()
            self._wait_dac_released()
            self.prepare_split_bus()
            self._systemctl('start', self.settings.camilladsp_service)
            self._wait_camilla_active()
            self._restore_applications(snapshot)
            return self.status()
        except RuntimeError as exc:
            try:
                self._stop_camilla()
                self._wait_dac_released()
                with self.locked():
                    self._select_direct_locked(f'split-bus activation failed: {exc}')
                self._restore_applications(snapshot)
            except RuntimeError as recovery_exc:
                raise RuntimeError(
                    f'Split-bus activation failed and recovery was incomplete: {exc}; {recovery_exc}'
                ) from exc
            raise RuntimeError(
                f'Split-bus activation failed; direct failback was selected: {exc}'
            ) from exc

    def activate_direct_failback(self) -> dict[str, Any]:
        snapshot = self._snapshot_applications()
        self._stop_applications(snapshot)
        try:
            self._stop_camilla()
            self._wait_dac_released()
            with self.locked():
                self._select_direct_locked('managed direct failback requested')
            self._restore_applications(snapshot)
            return self.status()
        except RuntimeError as exc:
            try:
                self._restore_applications(snapshot)
            except RuntimeError as restore_exc:
                raise RuntimeError(
                    f'Direct failback failed and application restoration failed: {exc}; {restore_exc}'
                ) from exc
            raise


def main() -> int:
    action = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'status'
    controller = RouteController(RouteSettings(read_defaults()))
    try:
        if action == 'status' and len(sys.argv) == 2:
            return emit(controller.status())
        if action == 'validate' and len(sys.argv) == 2:
            payload = controller.validate()
            return emit(payload, 0 if payload['ok'] else 1, stderr=not payload['ok'])
        if os.geteuid() != 0:
            raise RuntimeError('Audio-route mutation requires root through a fixed installer or sudo rule.')
        if action == 'prepare-split-bus' and len(sys.argv) == 2:
            return emit(controller.prepare_split_bus())
        if action == 'activate-split-bus' and len(sys.argv) == 2:
            return emit(controller.activate_split_bus())
        if action == 'activate-direct-failback' and len(sys.argv) == 2:
            return emit(controller.activate_direct_failback())
        raise ValueError(f'Unsupported audio-route action: {action}')
    except (ValueError, RuntimeError, OSError) as exc:
        return emit({'ok': False, 'error': str(exc)}, 1, stderr=True)


if __name__ == '__main__':
    raise SystemExit(main())
