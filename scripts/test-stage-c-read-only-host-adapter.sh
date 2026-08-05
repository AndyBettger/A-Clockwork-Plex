#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_CONFIRMATION="STAGE-C13-TYPED-READ-ONLY-HOST-ADAPTER"
MODE="prepare"
EVIDENCE_ROOT=""
CONFIRM=""

usage() {
  cat <<'EOF'
Usage:
  test-stage-c-read-only-host-adapter.sh

  test-stage-c-read-only-host-adapter.sh \
    --observe-read-only \
    --confirm STAGE-C13-TYPED-READ-ONLY-HOST-ADAPTER \
    --evidence-root /var/tmp/a-clockwork-plex-stage-c13-read-only-adapter.<suffix>

The default is prepare-only. It invokes no sudo, performs no host observation
and creates no Stage C13 evidence directory.

The guarded mode uses one constrained sudo command. Root writes only beneath
the fresh evidence directory. The real production lock is inspected with lstat
and is never opened or created. No service, mixer, module, PCM, DAC, route or
CamillaDSP state is changed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --observe-read-only)
      MODE="observe"
      shift
      ;;
    --confirm)
      [[ $# -ge 2 ]] || { echo "--confirm requires a value" >&2; exit 2; }
      CONFIRM="$2"
      shift 2
      ;;
    --evidence-root)
      [[ $# -ge 2 ]] || { echo "--evidence-root requires a value" >&2; exit 2; }
      EVIDENCE_ROOT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" == "prepare" ]]; then
  cat <<EOF
A Clockwork Plex Stage C13 typed read-only host-adapter rehearsal is prepared.

Prepare-only invoked no sudo, performed no host observation and created no
Stage C13 evidence directory.

After review, run the exact guarded observation:

  EVIDENCE="\$(mktemp -d /var/tmp/a-clockwork-plex-stage-c13-read-only-adapter.XXXXXX)"
  chmod 0700 "\$EVIDENCE"
  echo "EVIDENCE=\$EVIDENCE"

  bash scripts/test-stage-c-read-only-host-adapter.sh \\
    --observe-read-only \\
    --confirm $REQUIRED_CONFIRMATION \\
    --evidence-root "\$EVIDENCE" \\
    2>&1 | tee /tmp/acp-stage-c13-run.txt

The guarded observation uses one constrained sudo command. It obtains six typed
read-only observations and proves that all other 27 adapter operations remain
blocked. The real /run/lock/a-clockwork-plex-audio-route.lock path is not opened.
No production transaction, install, activation, failback, rollback or uninstall
action exists.
EOF
  exit 0
fi

[[ "$EUID" -ne 0 ]] || {
  echo "Run the outer Stage C13 wrapper as the normal project user, not as root." >&2
  exit 2
}
[[ "$CONFIRM" == "$REQUIRED_CONFIRMATION" ]] || {
  echo "Exact confirmation token required: $REQUIRED_CONFIRMATION" >&2
  exit 2
}
[[ -n "$EVIDENCE_ROOT" ]] || {
  echo "--evidence-root is required" >&2
  exit 2
}

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH_VALUE="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec sudo env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$PYTHONPATH_VALUE" \
  python3 -B -m stage_c_transaction.read_only_host_adapter_rehearsal \
    --confirm "$CONFIRM" \
    --evidence-root "$EVIDENCE_ROOT"
