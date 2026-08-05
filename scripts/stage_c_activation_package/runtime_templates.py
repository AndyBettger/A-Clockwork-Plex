from __future__ import annotations

import json

from stage_c_package.templates import HostContract


RUNTIME_ROOT = "/usr/local/lib/a-clockwork-plex/runtime-authority"


def route_launcher() -> str:
    return f'''#!/usr/bin/python3
from __future__ import annotations

import sys

sys.path.insert(0, {RUNTIME_ROOT!r})
from stage_c_runtime_authority.package_entry import main

if __name__ == "__main__":
    raise SystemExit(main())
'''


def package_entry() -> str:
    return '''#!/usr/bin/python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .approval_store import ApprovalStore
from .model import RuntimeAuthorityError

STATE_ROOT = Path("/var/lib/a-clockwork-plex/split-bus")
CONTRACT = Path("/usr/local/lib/a-clockwork-plex/runtime-authority/package-contract.json")
MUTATING_ACTIONS = {
    "accept-install-handoff",
    "promote-committed-approval",
    "boot-prepare",
    "supervise",
    "emergency-direct-failback",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contract() -> dict[str, object]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeAuthorityError("runtime package contract is invalid")
    return payload


def validate_runtime() -> dict[str, object]:
    contract = _contract()
    files = contract.get("files")
    if not isinstance(files, list):
        raise RuntimeAuthorityError("runtime package file contract is invalid")
    checked = 0
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise RuntimeAuthorityError("runtime package file row is invalid")
        path = Path(str(row["path"]))
        expected = str(row["sha256"])
        if not path.is_file() or path.is_symlink() or _sha256(path) != expected:
            raise RuntimeAuthorityError(f"runtime package file mismatch: {path}")
        checked += 1
    return {
        "ok": True,
        "package_phase": "stage-c21-adapter-pending-review",
        "package_fingerprint": contract.get("package_fingerprint"),
        "checked_files": checked,
        "host_mutation_available": False,
    }


def status() -> dict[str, object]:
    payload = validate_runtime()
    try:
        approval = ApprovalStore(STATE_ROOT).read()
    except RuntimeAuthorityError as exc:
        payload["approval"] = None
        payload["approval_status"] = str(exc)
    else:
        payload["approval"] = approval.as_dict()
        payload["approval_status"] = "valid"
    return payload


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if action == "status":
            print(json.dumps(status(), sort_keys=True))
            return 0
        if action == "validate-runtime":
            print(json.dumps(validate_runtime(), sort_keys=True))
            return 0
        if action in MUTATING_ACTIONS:
            raise RuntimeAuthorityError(
                "Stage C21 package review has no production host adapter; mutation remains blocked"
            )
        raise RuntimeAuthorityError("unsupported fixed runtime action")
    except (OSError, ValueError, json.JSONDecodeError, RuntimeAuthorityError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 78 if action in MUTATING_ACTIONS else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def defaults(c: HostContract) -> str:
    return f"""# A Clockwork Plex Stage C21 activation package review candidate.
PACKAGE_PHASE=stage-c21-adapter-pending-review
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
    return f"""# Stage C21 package review: read-only actions only.
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
    return f"""[Unit]
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
        "package_phase": "stage-c21-adapter-pending-review",
        "package_fingerprint": package_fingerprint,
        "host_mutation_available": False,
        "files": files,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
