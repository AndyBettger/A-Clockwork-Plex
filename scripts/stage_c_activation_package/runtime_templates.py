from __future__ import annotations

import json

from stage_c_package.templates import HostContract


RUNTIME_ROOT = "/usr/local/lib/a-clockwork-plex/runtime-authority"
PACKAGE_PHASE = "stage-c21-activation-capable-review-v2"


def route_launcher() -> str:
    return f'''#!/usr/bin/python3
from __future__ import annotations

import sys

sys.path.insert(0, {RUNTIME_ROOT!r})
from stage_c_runtime_authority.package_entry import main

if __name__ == "__main__":
    raise SystemExit(main())
'''


def defaults(c: HostContract) -> str:
    return f"""# A Clockwork Plex Stage C21 activation-capable package review candidate.
PACKAGE_PHASE={PACKAGE_PHASE}
PROJECT_USER={c.project_user}
DAC_CARD={c.dac_card}
DAC_DEVICE={c.dac_device}
LOOPBACK_INDEX={c.loopback_index}
LOOPBACK_ID={c.loopback_id}
SAMPLE_RATE={c.sample_rate}
FORMAT={c.sample_format}
PERIOD_SIZE={c.period_size}
BUFFER_SIZE={c.buffer_size}
CAMILLADSP_VERSION={c.camilladsp_version}
CAMILLADSP_SHA256={c.camilladsp_sha256}
ACTIVE_ALSA_CONFIG=/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf
SPLIT_ROUTE=/etc/a-clockwork-plex/audio-routes/split-bus.conf
DIRECT_FAILBACK_ROUTE=/etc/a-clockwork-plex/audio-routes/direct-alarm-bypass.conf
CAMILLADSP_BINARY=/usr/local/lib/a-clockwork-plex/camilladsp-{c.camilladsp_version}/camilladsp
CAMILLADSP_CONFIG=/etc/a-clockwork-plex/camilladsp-split-bus.yml
STATE_DIR=/var/lib/a-clockwork-plex/split-bus
RUNTIME_ROOT={RUNTIME_ROOT}
"""


def sudoers(project_user: str) -> str:
    return f"""# Stage C21 package review: read-only user actions only.
{project_user} ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route status
{project_user} ALL=(root) NOPASSWD: /usr/local/bin/a-clockwork-plex-audio-route validate-runtime
"""


def route_unit() -> str:
    return """[Unit]
Description=A Clockwork Plex guarded audio-route preparation authority
After=systemd-modules-load.service sound.target
Before=a-clockwork-plex-camilladsp.service plexamp.service shairport-sync.service a-clockwork-plex.service
Wants=sound.target
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route boot-prepare
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""


def camilladsp_unit(c: HostContract) -> str:
    del c
    return """[Unit]
Description=A Clockwork Plex supervised split-bus runtime
After=a-clockwork-plex-audio-route.service systemd-modules-load.service sound.target
Requires=a-clockwork-plex-audio-route.service sound.target
Before=plexamp.service shairport-sync.service a-clockwork-plex.service
OnFailure=a-clockwork-plex-audio-failback.service
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=notify
NotifyAccess=main
User=root
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route supervise
Restart=on-failure
RestartSec=2
TimeoutStartSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""


def failback_unit() -> str:
    return """[Unit]
Description=A Clockwork Plex emergency direct alarm-bypass failback
After=sound.target
Before=plexamp.service shairport-sync.service a-clockwork-plex.service
ConditionPathExists=/var/lib/a-clockwork-plex/split-bus/activation-approved

[Service]
Type=oneshot
ExecStart=/usr/local/bin/a-clockwork-plex-audio-route emergency-direct-failback
"""


def contract_json(*, package_fingerprint: str, files: list[dict[str, str]]) -> str:
    payload = {
        "schema_version": 1,
        "package_phase": PACKAGE_PHASE,
        "package_fingerprint": package_fingerprint,
        "host_mutation_available": True,
        "files": files,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
