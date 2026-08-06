#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PROJECT_PY='/home/andy/A-Clockwork-Plex/venv/bin/python'
LOCAL_REPO='/home/andy/A-Clockwork-Plex'

PACKAGE='/var/tmp/a-clockwork-plex-stage-c21-activation-package-v2.R2GyTo'
BASELINE='/var/tmp/a-clockwork-plex-stage-c21-production-baseline.5m73n8ac'
STAGE_C21='/var/tmp/a-clockwork-plex-stage-c21-current-package-preparation.rLFDFg'
STAGE_C22='/var/tmp/a-clockwork-plex-stage-c22-current-package-service-quiescence.LPNDwL'
STAGE_C23='/var/tmp/a-clockwork-plex-stage-c23-current-package-managed-file-rollback.DGdgaG'
STAGE_C25='/var/tmp/a-clockwork-plex-stage-c25-current-package-route-rollback.Q4Ltus'

LOCK='/run/lock/a-clockwork-plex-audio-route.lock'
STATE_ROOT='/var/lib/a-clockwork-plex/split-bus'
TRANSACTIONS="$STATE_ROOT/transactions"
COMMITTED_ROOT="$STATE_ROOT/committed-install"
APPROVAL="$STATE_ROOT/activation-approved"
ROUTE='/etc/alsa/conf.d/99-a-clockwork-plex-shared.conf'
SPLIT_ROUTE='/etc/a-clockwork-plex/audio-routes/split-bus.conf'
EXPECTED_DIRECT_SHA='08d000933e132af4fe0d66f1f80fd6ba08d15398b98f5ea986f69709139e74b9'
EXPECTED_PACKAGE_SHA='dd4e8da82a3eb8f309b8e68c848652d806ca25ff9c0a7a3f16947e851486c2b5'
EXPECTED_C25_RESULTS=29
EXPECTED_TERMINAL_RESULTS=22

APPLICATION_UNITS=(
  plexamp.service
  shairport-sync.service
  a-clockwork-plex.service
)
MANAGED_UNITS=(
  a-clockwork-plex-audio-route.service
  a-clockwork-plex-camilladsp.service
)

fail() {
  printf 'STAGE_C_TERMINAL_PREFLIGHT_FAIL=%s\n' "$*" >&2
  exit 1
}

first_parameter() {
  local name="$1"
  local raw
  raw="$(tr -d '[:space:]' <"/sys/module/snd_aloop/parameters/$name")"
  printf '%s' "${raw%%,*}"
}

result_count() {
  local path="$1"
  local result="$2"
  awk -F $'\t' -v expected="$result" '
    NR > 1 && $2 == expected { count++ }
    END { print count + 0 }
  ' "$path"
}

total_count() {
  local path="$1"
  awk -F $'\t' 'NR > 1 { count++ } END { print count + 0 }' "$path"
}

[[ "$(id -un)" == 'andy' ]] || fail 'run as the normal user andy'
[[ "$(hostname -s)" == 'plexamp-bedroom' ]] || fail 'unexpected host'
[[ "$EUID" -ne 0 ]] || fail 'do not run the operator script as root'
[[ -d "$REPO_ROOT/.git" ]] || fail 'operator source is not a Git checkout'
[[ -x "$PROJECT_PY" ]] || fail "project Python is unavailable: $PROJECT_PY"

SOURCE_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD)"
SOURCE_STATUS="$(git -C "$REPO_ROOT" status --porcelain=v1 --untracked-files=all)"
printf 'SOURCE_HEAD=%s\n' "$SOURCE_HEAD"
[[ -z "$SOURCE_STATUS" ]] || fail 'fresh operator source is dirty'

for root in "$PACKAGE" "$BASELINE" "$STAGE_C21" "$STAGE_C22" "$STAGE_C23" "$STAGE_C25"; do
  [[ -d "$root" && ! -L "$root" ]] || fail "retained root is missing or unsafe: $root"
done

[[ -f "$STAGE_C25/results.tsv" ]] || fail 'C25 results are unavailable'
C25_TOTAL="$(total_count "$STAGE_C25/results.tsv")"
C25_PASS="$(result_count "$STAGE_C25/results.tsv" PASS)"
printf 'C25_RESULTS=%s/%s_PASS\n' "$C25_PASS" "$C25_TOTAL"
[[ "$C25_TOTAL" == "$EXPECTED_C25_RESULTS" && "$C25_PASS" == "$EXPECTED_C25_RESULTS" ]] ||
  fail 'accepted C25 result count changed'
grep -Fq $'committed\tfalse' "$STAGE_C25/identity.tsv" || fail 'C25 is not rollback-only'
grep -Fq $'reusable_for_activation\tfalse' "$STAGE_C25/identity.tsv" ||
  fail 'C25 identity boundary changed'
grep -Fq 'STAGE_C25_INTEGRATED_ROUTE_ROLLBACK=PASS' \
  /var/tmp/a-clockwork-plex-stage-c25-console.H03w3N ||
  fail 'accepted C25 console completion marker is unavailable'

TEST_LOG="$(mktemp /var/tmp/a-clockwork-plex-stage-c-terminal-tests.XXXXXX)"
chmod 0600 "$TEST_LOG"

(
  cd "$REPO_ROOT"
  "$PROJECT_PY" -m py_compile \
    scripts/stage_c_transaction/current_package_terminal_install_adapter_v15.py \
    scripts/stage_c_transaction/current_package_terminal_install_adapter_v16.py \
    scripts/stage_c_transaction/current_package_terminal_install_v16.py
  bash -n scripts/install-and-enable-stage-c-eq.sh
  bash -n scripts/run-stage-c-terminal-install-verified.sh
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
    "$PROJECT_PY" -m unittest discover -s tests -q
) >"$TEST_LOG" 2>&1 || {
  printf '%s\n' '--- TERMINAL REPOSITORY TEST FAILURE ---'
  cat "$TEST_LOG"
  printf 'TEST_LOG=%s\n' "$TEST_LOG"
  fail 'complete repository suite failed before physical mutation'
}

printf '%s\n' '--- terminal repository tests passed ---'
tail -n 20 "$TEST_LOG"
printf 'TEST_LOG=%s\n' "$TEST_LOG"

sudo -v

sudo test ! -e "$LOCK" || fail 'production lock already exists'
sudo test ! -e "$APPROVAL" || fail 'activation approval already exists'
sudo test ! -e "$COMMITTED_ROOT" || fail 'committed Stage C install already exists'

if sudo test -d "$TRANSACTIONS"; then
  TRANSACTION_ENTRIES="$(
    sudo find "$TRANSACTIONS" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort
  )"
  [[ -z "$TRANSACTION_ENTRIES" ]] || fail 'authoritative transaction already exists'
fi

for unit in "${APPLICATION_UNITS[@]}"; do
  [[ "$(systemctl is-active "$unit" 2>/dev/null || true)" == 'active' ]] ||
    fail "$unit is not active"
  [[ "$(systemctl is-enabled "$unit" 2>/dev/null || true)" == 'enabled' ]] ||
    fail "$unit is not enabled"
done

if [[ ! -r /sys/module/snd_aloop/parameters/index ]]; then
  printf '%s\n' 'STAGE_C_TERMINAL_TEMPORARY_LOOPBACK_LOAD_BEGIN'
  sudo modprobe snd_aloop index=7 id=ACP_Loopback pcm_substreams=2 pcm_notify=1
  printf '%s\n' 'STAGE_C_TERMINAL_TEMPORARY_LOOPBACK_LOAD_COMPLETE'
fi

[[ "$(first_parameter index)" == '7' ]] || fail 'snd_aloop first index is not 7'
[[ "$(first_parameter id)" == 'ACP_Loopback' ]] || fail 'snd_aloop first ID changed'
[[ "$(first_parameter pcm_substreams)" == '2' ]] || fail 'snd_aloop substreams changed'
[[ "$(first_parameter pcm_notify)" == '1' ]] || fail 'snd_aloop pcm_notify changed'
[[ "$(first_parameter enable)" == 'Y' ]] || fail 'snd_aloop first card is disabled'

DIRECT_SHA="$(sudo sha256sum "$ROUTE" | awk '{print $1}')"
printf 'DIRECT_ROUTE_SHA256=%s\n' "$DIRECT_SHA"
[[ "$DIRECT_SHA" == "$EXPECTED_DIRECT_SHA" ]] || fail 'accepted direct route changed'

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts" \
"$PROJECT_PY" - "$PACKAGE" "$EXPECTED_PACKAGE_SHA" <<'PY'
from pathlib import Path
import sys

from scripts.stage_c_transaction.current_package_contract_v7 import (
    validate_current_package_v7,
)

package = validate_current_package_v7(Path(sys.argv[1]))
print(f"PACKAGE_FINGERPRINT={package.sha256}")
if package.sha256 != sys.argv[2]:
    raise SystemExit("accepted package fingerprint changed")
PY

EVIDENCE_ROOT="$(
  mktemp -d /var/tmp/a-clockwork-plex-stage-c-terminal-install.XXXXXX
)"
CONSOLE_LOG="$(
  mktemp /var/tmp/a-clockwork-plex-stage-c-terminal-console.XXXXXX
)"
chmod 0700 "$EVIDENCE_ROOT"
chmod 0600 "$CONSOLE_LOG"

printf 'EVIDENCE_ROOT=%s\n' "$EVIDENCE_ROOT"
printf 'CONSOLE_LOG=%s\n' "$CONSOLE_LOG"
printf '%s\n' 'STAGE_C_TERMINAL_GUARDED_INVOCATION_BEGIN'

INSTALL_CMD=(
  bash
  scripts/install-and-enable-stage-c-eq.sh
  --confirm
  INSTALL-AND-ENABLE-STAGE-C-EQ
  --package-root
  "$PACKAGE"
  --baseline-root
  "$BASELINE"
  --stage-c21-root
  "$STAGE_C21"
  --stage-c22-root
  "$STAGE_C22"
  --stage-c23-root
  "$STAGE_C23"
  --stage-c25-root
  "$STAGE_C25"
  --evidence-root
  "$EVIDENCE_ROOT"
)

set +e
(
  cd "$REPO_ROOT"
  "${INSTALL_CMD[@]}"
) 2>&1 | tee "$CONSOLE_LOG"
INSTALL_STATUS="${PIPESTATUS[0]}"
set -e

printf 'terminal_install_status=%s\n' "$INSTALL_STATUS"
FINAL_STATUS="$INSTALL_STATUS"

if sudo test -e "$LOCK"; then
  printf '%s\n' 'production_lock=present'
  FINAL_STATUS=1
else
  printf '%s\n' 'production_lock=absent'
fi

TRANSACTION_ENTRIES=''
if sudo test -d "$TRANSACTIONS"; then
  TRANSACTION_ENTRIES="$(
    sudo find "$TRANSACTIONS" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort
  )"
fi
if [[ -n "$TRANSACTION_ENTRIES" ]]; then
  printf '%s\n' 'authoritative_transactions=present'
  printf '%s\n' "$TRANSACTION_ENTRIES"
  FINAL_STATUS=1
else
  printf '%s\n' 'authoritative_transactions=absent'
fi

for unit in "${APPLICATION_UNITS[@]}"; do
  active="$(systemctl is-active "$unit" 2>/dev/null || true)"
  enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
  printf 'APPLICATION unit=%s active=%s enabled=%s\n' "$unit" "$active" "$enabled"
  [[ "$active" == 'active' && "$enabled" == 'enabled' ]] || FINAL_STATUS=1
done

if [[ "$INSTALL_STATUS" == '0' ]]; then
  sudo test -f "$APPROVAL" || FINAL_STATUS=1
  sudo test -d "$COMMITTED_ROOT" || FINAL_STATUS=1
  for unit in "${MANAGED_UNITS[@]}"; do
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    printf 'MANAGED unit=%s active=%s enabled=%s\n' "$unit" "$active" "$enabled"
    [[ "$active" == 'active' && "$enabled" == 'enabled' ]] || FINAL_STATUS=1
  done
  if sudo test -f "$SPLIT_ROUTE"; then
    ACTIVE_SHA="$(sudo sha256sum "$ROUTE" | awk '{print $1}')"
    SPLIT_SHA="$(sudo sha256sum "$SPLIT_ROUTE" | awk '{print $1}')"
    printf 'ACTIVE_ROUTE_SHA256=%s\n' "$ACTIVE_SHA"
    printf 'SPLIT_ROUTE_SHA256=%s\n' "$SPLIT_SHA"
    [[ "$ACTIVE_SHA" == "$SPLIT_SHA" ]] || FINAL_STATUS=1
  else
    printf '%s\n' 'split_route=missing'
    FINAL_STATUS=1
  fi
fi

if [[ -f "$EVIDENCE_ROOT/results.tsv" ]]; then
  TERMINAL_TOTAL="$(total_count "$EVIDENCE_ROOT/results.tsv")"
  TERMINAL_PASS="$(result_count "$EVIDENCE_ROOT/results.tsv" PASS)"
  printf 'TERMINAL_RESULTS=%s/%s_PASS\n' "$TERMINAL_PASS" "$TERMINAL_TOTAL"
  cat "$EVIDENCE_ROOT/results.tsv"
  if [[ "$INSTALL_STATUS" == '0' ]]; then
    [[ "$TERMINAL_TOTAL" == "$EXPECTED_TERMINAL_RESULTS" && \
       "$TERMINAL_PASS" == "$EXPECTED_TERMINAL_RESULTS" ]] || FINAL_STATUS=1
  fi
else
  printf '%s\n' 'terminal_results=missing'
  FINAL_STATUS=1
fi

for file in activation-execution.json identity.tsv report.txt evidence-manifest.tsv; do
  if [[ -f "$EVIDENCE_ROOT/$file" ]]; then
    printf '%s\n' "--- $file ---"
    cat "$EVIDENCE_ROOT/$file"
  fi
done

printf 'SOURCE_ROOT=%s\n' "$REPO_ROOT"
printf 'TEST_LOG=%s\n' "$TEST_LOG"
printf 'CONSOLE_LOG=%s\n' "$CONSOLE_LOG"
printf 'EVIDENCE_ROOT=%s\n' "$EVIDENCE_ROOT"
printf 'STAGE_C_TERMINAL_FINAL_STATUS=%s\n' "$FINAL_STATUS"

if [[ "$FINAL_STATUS" != '0' ]]; then
  if sudo test -e "$LOCK" || [[ -n "$TRANSACTION_ENTRIES" ]]; then
    printf '%s\n' 'STAGE_C_TERMINAL_RETAINED_STATE=INSPECT_DO_NOT_CLEAN_OR_RERUN'
  else
    printf '%s\n' 'STAGE_C_TERMINAL_NOT_COMMITTED=BASELINE_OR_EXACT_ROLLBACK_EXPECTED'
  fi
  exit "$FINAL_STATUS"
fi

printf '%s\n' 'STAGE_C_EQ_INSTALLED_AND_ENABLED=PASS'
