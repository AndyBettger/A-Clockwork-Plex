from __future__ import annotations

from .templates import HostContract


def route_helper() -> str:
    return '''#!/usr/bin/python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DEFAULTS = Path('/etc/default/a-clockwork-plex-split-bus')
STATE = Path('/var/lib/a-clockwork-plex/split-bus/route-state.json')
ACTIVE = Path('/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf')
BLOCKED = {'boot-select', 'activate-split-bus', 'activate-direct-failback', 'restore-backup'}


def digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def status() -> dict[str, object]:
    try:
        state = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        state = {'mode': 'offline', 'reason': 'no committed Stage C state'}
    return {
        'ok': True,
        'package_phase': 'stage-c1-candidate-only',
        'activation_approved': False,
        'active_alsa_sha256': digest(ACTIVE),
        'defaults_present': DEFAULTS.exists(),
        'state': state,
    }


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'status' and len(sys.argv) == 2:
        print(json.dumps(status(), sort_keys=True))
        return 0
    if action == 'validate-package' and len(sys.argv) == 2:
        payload = status()
        payload['validated'] = DEFAULTS.exists()
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload['validated'] else 1
    if action in BLOCKED:
        print(json.dumps({'ok': False, 'error': 'Stage C1 is prepare-only; mutation is deliberately blocked.'}), file=sys.stderr)
        return 78
    print(json.dumps({'ok': False, 'error': f'Unsupported action: {action}'}), file=sys.stderr)
    return 64


if __name__ == '__main__':
    raise SystemExit(main())
'''


def sudoers(project_user: str) -> str:
    return f"""# Stage C1 candidate only. Mutation actions are not authorised.
{project_user} ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route status
{project_user} ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route validate-package
"""


def route_unit() -> str:
    return """[Unit]
Description=A Clockwork Plex guarded audio-route authority
After=systemd-modules-load.service sound.target
Before=a-clockwork-plex-camilladsp.service plexamp.service shairport-sync.service a-clockwork-plex.service
Wants=sound.target
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-select
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""


def camilladsp_unit(c: HostContract) -> str:
    return f"""[Unit]
Description=A Clockwork Plex split-bus CamillaDSP
After=a-clockwork-plex-audio-route.service systemd-modules-load.service sound.target
Requires=a-clockwork-plex-audio-route.service sound.target
Before=plexamp.service shairport-sync.service a-clockwork-plex.service
OnFailure=a-clockwork-plex-audio-failback.service
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User={c.project_user}
Group=audio
ExecStart=/usr/local/lib/a-clockwork-plex/camilladsp-{c.camilladsp_version}/camilladsp /etc/a-clockwork-plex/camilladsp-split-bus.yml
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def failback_unit() -> str:
    return """[Unit]
Description=A Clockwork Plex direct alarm-bypass failback
After=sound.target
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route activate-direct-failback
"""
