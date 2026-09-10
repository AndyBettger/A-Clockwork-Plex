#!/usr/bin/env python3
r"""Rehearse a reversible Plexamp Home customisation scrub on disposable Chromium only.

This developer tool is intentionally NOT part of the production Reset bridge. It connects
only to a loopback Chromium DevTools endpoint whose single page is local Plexamp, refuses
the preserved 9224-9229 evidence profiles, and mutates only the already-classified
`mmkv.default\discovery:customizations:` Home families.

The supported rehearsal is:

    plan     read/validate the bounded Home-owned records and emit counts/fingerprint only;
    apply    capture exact raw Home-owned records to a mode-0600 /var/tmp snapshot, then
             remove only order/hidden/viewSettings/customHubs records with stale checking;
    rollback restore that exact snapshot only when the current bounded Home state is empty.

An `editing` record, unknown family, structurally invalid key, oversized record, stale
fingerprint, existing snapshot, or non-empty state at rollback makes the tool fail closed.
Raw keys/values are never printed. The snapshot contains Home customisation bytes only;
it never reads cookies, authentication/session storage, IndexedDB or unrelated Local Storage.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DEBUG_PORT = 9230
DEFAULT_TIMEOUT = 5.0
PROTECTED_SPECIMEN_PORTS = frozenset(range(9224, 9230))
SNAPSHOT_ROOT = Path("/var/tmp")
SNAPSHOT_PREFIX = "plexamp-home-scrub-"
SNAPSHOT_SUFFIX = ".json"
SAFE_FINGERPRINT = re.compile(r"^[a-f0-9]{8}$")
SAFE_IDENTIFIER = r"[A-Za-z0-9_.:/%+@~=\-]{1,600}"
SAFE_SECTION = r"[0-9]{1,10}"
ORDER_KEY_RE = re.compile(
    rf"^mmkv\.default\\discovery:customizations:{SAFE_IDENTIFIER}::/library/sections/{SAFE_SECTION}:order$"
)
CUSTOM_HUBS_KEY_RE = re.compile(
    rf"^mmkv\.default\\discovery:customizations:{SAFE_IDENTIFIER}::/library/sections/{SAFE_SECTION}:customHubs$"
)
HUB_KEY_RE = re.compile(
    rf"^mmkv\.default\\discovery:customizations:{SAFE_IDENTIFIER}::/library/sections/{SAFE_SECTION}:"
    rf"{SAFE_IDENTIFIER}:(hidden|viewSettings|editing)$"
)
DURABLE_FAMILIES = frozenset({"order", "hidden", "viewSettings", "customHubs"})
MAX_STORAGE_KEYS = 2048
MAX_RECORDS = 512
MAX_RECORD_BYTES = 65536
MAX_TOTAL_BYTES = 524288
MAX_KEY_CHARS = 1800


RUNTIME_TEMPLATE = r"""
(() => {
  'use strict';

  const ACTION = __ACTION__;
  const EXPECTED_FINGERPRINT = __EXPECTED_FINGERPRINT__;
  const RESTORE_RECORDS = __RESTORE_RECORDS__;
  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SECTION_MARKER = '::/library/sections/';
  const SAFE_IDENTIFIER = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_SECTION = /^[0-9]{1,10}$/;
  const SAFE_TERMINAL = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const DURABLE = new Set(['order', 'hidden', 'viewSettings', 'customHubs']);
  const MAX_STORAGE_KEYS = 2048;
  const MAX_RECORDS = 512;
  const MAX_RECORD_BYTES = 65536;
  const MAX_TOTAL_BYTES = 524288;

  function hash32(text) {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  }

  function classifySuffix(suffix) {
    if (!suffix.startsWith(CUSTOM_PREFIX)) return null;
    const markerIndex = suffix.indexOf(SECTION_MARKER, CUSTOM_PREFIX.length);
    if (markerIndex < 0) return { family: 'other', valid: false, context: null, section: null };

    const context = suffix.slice(CUSTOM_PREFIX.length, markerIndex);
    const rest = suffix.slice(markerIndex + SECTION_MARKER.length);
    const colonIndex = rest.indexOf(':');
    if (!SAFE_IDENTIFIER.test(context) || colonIndex < 1) {
      return { family: 'other', valid: false, context: null, section: null };
    }

    const section = rest.slice(0, colonIndex);
    const tail = rest.slice(colonIndex + 1);
    if (!SAFE_SECTION.test(section) || !tail) {
      return { family: 'other', valid: false, context: null, section: null };
    }

    if (tail === 'order') return { family: 'order', valid: true, context, section };
    if (tail === 'customHubs') return { family: 'customHubs', valid: true, context, section };

    const finalColon = tail.lastIndexOf(':');
    if (finalColon < 1) {
      const terminal = SAFE_TERMINAL.test(tail) && !SENSITIVE_NAME.test(tail) ? tail : null;
      return { family: 'other', valid: terminal !== null, context, section };
    }

    const hub = tail.slice(0, finalColon);
    const terminal = tail.slice(finalColon + 1);
    if (!SAFE_IDENTIFIER.test(hub) || !SAFE_TERMINAL.test(terminal) || SENSITIVE_NAME.test(terminal)) {
      return { family: 'other', valid: false, context: null, section: null };
    }
    if (terminal === 'hidden') return { family: 'hidden', valid: true, context, section };
    if (terminal === 'viewSettings') return { family: 'viewSettings', valid: true, context, section };
    if (terminal === 'editing') return { family: 'editing', valid: true, context, section };
    return { family: 'other', valid: true, context, section };
  }

  function collectInventory(storage, includeRecords) {
    const families = { order: 0, hidden: 0, viewSettings: 0, editing: 0, customHubs: 0, other: 0 };
    const contexts = new Set();
    const sections = new Set();
    const records = [];
    let structurallyInvalid = 0;
    let totalBytes = 0;
    const length = Number(storage?.length || 0);
    if (!Number.isFinite(length) || length < 0 || length > MAX_STORAGE_KEYS) {
      return { status: 'storage-key-limit-exceeded', families, contexts, sections, records, structurallyInvalid, totalBytes };
    }

    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX + CUSTOM_PREFIX)) continue;
      const suffix = key.slice(MMKV_PREFIX.length);
      const classified = classifySuffix(suffix);
      if (!classified) continue;
      families[classified.family] += 1;
      if (!classified.valid) structurallyInvalid += 1;
      if (classified.context) contexts.add(classified.context);
      if (classified.context && classified.section) {
        sections.add(`${classified.context}\u0000${classified.section}`);
      }
      if (!classified.valid || !DURABLE.has(classified.family)) continue;
      if (records.length >= MAX_RECORDS) {
        return { status: 'record-limit-exceeded', families, contexts, sections, records: [], structurallyInvalid, totalBytes };
      }
      const raw = storage.getItem(key);
      if (typeof raw !== 'string') {
        return { status: 'storage-value-unavailable', families, contexts, sections, records: [], structurallyInvalid, totalBytes };
      }
      if (raw.length > MAX_RECORD_BYTES) {
        return { status: 'record-size-limit-exceeded', families, contexts, sections, records: [], structurallyInvalid, totalBytes };
      }
      totalBytes += raw.length;
      if (totalBytes > MAX_TOTAL_BYTES) {
        return { status: 'total-size-limit-exceeded', families, contexts, sections, records: [], structurallyInvalid, totalBytes };
      }
      records.push({ key, raw, family: classified.family });
    }

    let status = 'ready';
    if (structurallyInvalid > 0 || families.other > 0) status = 'unclassified-customization-keys';
    else if (families.editing > 0) status = 'editing-active';

    records.sort((left, right) => left.key.localeCompare(right.key));
    const fingerprint = hash32(JSON.stringify(records.map((record) => [record.key, record.raw])));
    return {
      status,
      families,
      contexts,
      sections,
      records: includeRecords ? records : [],
      internalRecords: records,
      structurallyInvalid,
      totalBytes,
      fingerprint,
    };
  }

  function publicInventory(inventory, extra = {}) {
    const records = inventory.internalRecords || [];
    return {
      schema_version: 1,
      status: inventory.status,
      disposable_rehearsal: true,
      storage_values_read: true,
      raw_keys_emitted: false,
      raw_values_emitted: false,
      family_counts: inventory.families,
      context_count: inventory.contexts.size,
      section_context_count: inventory.sections.size,
      structurally_invalid_count: inventory.structurallyInvalid,
      scrub_record_count: records.length,
      snapshot_value_chars: inventory.totalBytes,
      target_fingerprint: inventory.fingerprint || null,
      ...extra,
    };
  }

  function validateRestoreRecords(records) {
    if (!Array.isArray(records) || records.length > MAX_RECORDS) return null;
    const seen = new Set();
    const validated = [];
    let totalBytes = 0;
    for (const record of records) {
      if (!record || typeof record !== 'object' || Array.isArray(record)) return null;
      if (typeof record.key !== 'string' || typeof record.raw !== 'string' || typeof record.family !== 'string') return null;
      if (seen.has(record.key) || record.raw.length > MAX_RECORD_BYTES) return null;
      if (!record.key.startsWith(MMKV_PREFIX + CUSTOM_PREFIX)) return null;
      const classified = classifySuffix(record.key.slice(MMKV_PREFIX.length));
      if (!classified?.valid || !DURABLE.has(classified.family) || classified.family !== record.family) return null;
      totalBytes += record.raw.length;
      if (totalBytes > MAX_TOTAL_BYTES) return null;
      seen.add(record.key);
      validated.push({ key: record.key, raw: record.raw, family: record.family });
    }
    validated.sort((left, right) => left.key.localeCompare(right.key));
    return validated;
  }

  let storage;
  try {
    storage = globalThis.localStorage;
  } catch (_error) {
    return { schema_version: 1, status: 'local-storage-unavailable', disposable_rehearsal: true };
  }

  const inventory = collectInventory(storage, ACTION === 'capture');
  if (ACTION === 'plan') return publicInventory(inventory, { read_only: true });
  if (ACTION === 'capture') {
    const result = publicInventory(inventory, { read_only: true });
    if (inventory.status === 'ready') result.records = inventory.records;
    return result;
  }

  if (ACTION === 'scrub') {
    if (inventory.status !== 'ready') return publicInventory(inventory, { applied: false, rolled_back: false });
    if (typeof EXPECTED_FINGERPRINT !== 'string' || inventory.fingerprint !== EXPECTED_FINGERPRINT) {
      return publicInventory(inventory, { status: 'stale-target', applied: false, rolled_back: false, fresh_plan_required: true });
    }
    const records = inventory.internalRecords;
    if (records.length === 0) return publicInventory(inventory, { status: 'no-change', applied: false, rolled_back: false });

    const touched = [];
    try {
      for (const record of records) {
        storage.removeItem(record.key);
        touched.push(record);
      }
      if (records.some((record) => storage.getItem(record.key) !== null)) throw new Error('verification');
      const after = collectInventory(storage, false);
      if (after.status !== 'ready' || (after.internalRecords || []).length !== 0) throw new Error('verification');
      return publicInventory(after, {
        status: 'scrubbed',
        applied: true,
        rolled_back: false,
        removed_record_count: records.length,
        before_fingerprint: inventory.fingerprint,
        after_fingerprint: after.fingerprint,
      });
    } catch (_error) {
      let rollbackOk = true;
      for (const record of touched) {
        try { storage.setItem(record.key, record.raw); } catch (_restoreError) { rollbackOk = false; }
      }
      if (rollbackOk) {
        rollbackOk = touched.every((record) => storage.getItem(record.key) === record.raw);
      }
      return publicInventory(collectInventory(storage, false), {
        status: 'scrub-failed',
        applied: false,
        rolled_back: rollbackOk,
        fresh_plan_required: true,
      });
    }
  }

  if (ACTION === 'restore') {
    if (inventory.status !== 'ready') return publicInventory(inventory, { restored: false, rolled_back: false });
    if ((inventory.internalRecords || []).length !== 0) {
      return publicInventory(inventory, { status: 'target-not-empty', restored: false, rolled_back: false });
    }
    const records = validateRestoreRecords(RESTORE_RECORDS);
    if (records === null) return publicInventory(inventory, { status: 'invalid-snapshot-records', restored: false, rolled_back: false });
    const restoreFingerprint = hash32(JSON.stringify(records.map((record) => [record.key, record.raw])));
    if (typeof EXPECTED_FINGERPRINT !== 'string' || restoreFingerprint !== EXPECTED_FINGERPRINT) {
      return publicInventory(inventory, { status: 'snapshot-fingerprint-mismatch', restored: false, rolled_back: false });
    }

    const touched = [];
    try {
      for (const record of records) {
        storage.setItem(record.key, record.raw);
        touched.push(record);
      }
      if (records.some((record) => storage.getItem(record.key) !== record.raw)) throw new Error('verification');
      const after = collectInventory(storage, false);
      if (after.status !== 'ready' || after.fingerprint !== EXPECTED_FINGERPRINT) throw new Error('verification');
      return publicInventory(after, {
        status: 'restored',
        restored: true,
        rolled_back: false,
        restored_record_count: records.length,
      });
    } catch (_error) {
      let rollbackOk = true;
      for (const record of touched) {
        try { storage.removeItem(record.key); } catch (_removeError) { rollbackOk = false; }
      }
      if (rollbackOk) rollbackOk = touched.every((record) => storage.getItem(record.key) === null);
      return publicInventory(collectInventory(storage, false), {
        status: 'restore-failed',
        restored: false,
        rolled_back: rollbackOk,
      });
    }
  }

  return { schema_version: 1, status: 'invalid-action', disposable_rehearsal: true };
})()
""".strip()


class RehearsalError(RuntimeError):
    """Expected, user-facing rehearsal failure."""


def load_transport_module():
    module_path = Path(__file__).with_name("inspect-plexamp-home-runtime.py")
    spec = importlib.util.spec_from_file_location("acp_plexamp_home_scrub_transport", module_path)
    if spec is None or spec.loader is None:
        raise RehearsalError("Could not load the bounded Plexamp Home DevTools transport.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_rehearsal_port(port: int, transport) -> int:
    checked = transport.require_safe_port(port)
    if checked in PROTECTED_SPECIMEN_PORTS:
        raise RehearsalError(
            f"Debug port {checked} is a preserved 9224-9229 evidence profile; use a fresh disposable port such as 9230."
        )
    return checked


def default_snapshot_path(port: int) -> Path:
    return SNAPSHOT_ROOT / f"{SNAPSHOT_PREFIX}{port}{SNAPSHOT_SUFFIX}"


def require_snapshot_path(value: str | None, port: int) -> Path:
    path = Path(value) if value else default_snapshot_path(port)
    expected = default_snapshot_path(port)
    if not path.is_absolute() or path.parent != SNAPSHOT_ROOT or path.name != expected.name:
        raise RehearsalError(f"Snapshot path must be exactly {expected} for debug port {port}.")
    return path


def classify_snapshot_key(key: str) -> str | None:
    if not isinstance(key, str) or len(key) > MAX_KEY_CHARS:
        return None
    if ORDER_KEY_RE.fullmatch(key):
        return "order"
    if CUSTOM_HUBS_KEY_RE.fullmatch(key):
        return "customHubs"
    match = HUB_KEY_RE.fullmatch(key)
    return match.group(1) if match else None


def validate_records(records: object) -> list[dict[str, str]]:
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise RehearsalError("Snapshot record list is missing or exceeds the rehearsal record limit.")
    seen: set[str] = set()
    total_bytes = 0
    validated: list[dict[str, str]] = []
    for item in records:
        if not isinstance(item, dict):
            raise RehearsalError("Snapshot contains a malformed Home record.")
        key = item.get("key")
        raw = item.get("raw")
        family = item.get("family")
        if not isinstance(key, str) or not isinstance(raw, str) or not isinstance(family, str):
            raise RehearsalError("Snapshot Home record fields have invalid types.")
        classified = classify_snapshot_key(key)
        if classified not in DURABLE_FAMILIES or classified != family:
            raise RehearsalError("Snapshot contains an unclassified or non-durable Home family.")
        if key in seen:
            raise RehearsalError("Snapshot contains duplicate Home keys.")
        if len(raw) > MAX_RECORD_BYTES:
            raise RehearsalError("Snapshot contains an oversized Home value.")
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise RehearsalError("Snapshot Home values exceed the total rehearsal size limit.")
        seen.add(key)
        validated.append({"key": key, "raw": raw, "family": family})
    validated.sort(key=lambda item: item["key"])
    return validated


def validate_snapshot(payload: object, port: int) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RehearsalError("Snapshot has an unsupported schema.")
    if payload.get("debug_port") != port:
        raise RehearsalError("Snapshot was captured from a different debug port.")
    fingerprint = payload.get("target_fingerprint")
    if not isinstance(fingerprint, str) or SAFE_FINGERPRINT.fullmatch(fingerprint) is None:
        raise RehearsalError("Snapshot fingerprint is invalid.")
    records = validate_records(payload.get("records"))
    return {
        "schema_version": 1,
        "debug_port": port,
        "target_fingerprint": fingerprint,
        "records": records,
        "created_at": payload.get("created_at") if isinstance(payload.get("created_at"), str) else None,
    }


def write_snapshot(path: Path, payload: dict[str, object]) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise RehearsalError(f"Snapshot already exists: {path}; refuse to overwrite rollback evidence.") from exc
    except OSError as exc:
        raise RehearsalError(f"Could not create mode-0600 snapshot at {path}.") from exc
    try:
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_snapshot(path: Path, port: int) -> dict[str, object]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise RehearsalError(f"Could not open rollback snapshot {path}.") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (stat.S_IMODE(info.st_mode) & 0o077):
            raise RehearsalError("Rollback snapshot must be a regular file with no group/other permissions.")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=True) as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise RehearsalError("Rollback snapshot is not valid JSON.") from exc
    return validate_snapshot(payload, port)


def build_runtime_expression(
    action: str,
    *,
    expected_fingerprint: str | None = None,
    restore_records: list[dict[str, str]] | None = None,
) -> str:
    if action not in {"plan", "capture", "scrub", "restore"}:
        raise ValueError("unsupported rehearsal action")
    if expected_fingerprint is not None and SAFE_FINGERPRINT.fullmatch(expected_fingerprint) is None:
        raise ValueError("invalid fingerprint")
    records = restore_records or []
    if action == "restore":
        records = validate_records(records)
    expression = RUNTIME_TEMPLATE.replace("__ACTION__", json.dumps(action))
    expression = expression.replace("__EXPECTED_FINGERPRINT__", json.dumps(expected_fingerprint))
    expression = expression.replace("__RESTORE_RECORDS__", json.dumps(records, separators=(",", ":"), ensure_ascii=True))
    return expression


def evaluate_action(connection, expression: str, probe_error) -> dict[str, object]:
    request_id = 1
    connection.send_json(
        {
            "id": request_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
                "silent": True,
                "disableBreaks": True,
                "userGesture": False,
            },
        }
    )
    while True:
        response = connection.recv_json()
        if response.get("id") != request_id:
            continue
        if "error" in response:
            raise probe_error("Chromium rejected the bounded Home-scrub rehearsal request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Home-scrub rehearsal raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the Home-scrub result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Home-scrub rehearsal returned an unexpected result shape.")
        return value


def public_result(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if key != "records"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rehearse an exact-snapshot, bounded Plexamp Home customisation scrub/rollback "
            "against a fresh disposable loopback Chromium profile."
        )
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("plan", "apply", "rollback"):
        sub = subparsers.add_parser(action)
        sub.add_argument("--debug-port", type=int, default=DEFAULT_DEBUG_PORT)
        sub.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
        sub.add_argument("--snapshot", default=None)
        if action == "apply":
            sub.add_argument("--confirm-scrub", action="store_true")
        if action == "rollback":
            sub.add_argument("--confirm-rollback", action="store_true")
    return parser.parse_args()


def connect(args: argparse.Namespace, transport):
    port = require_rehearsal_port(args.debug_port, transport)
    timeout = transport.require_safe_timeout(args.timeout)
    target = transport.plexamp_target(transport.fetch_targets(port, timeout))
    connection = transport.connect_devtools(target, port, timeout)
    return port, connection


def main() -> int:
    args = parse_args()
    try:
        transport = load_transport_module()
        port = require_rehearsal_port(args.debug_port, transport)
        snapshot_path = require_snapshot_path(args.snapshot, port)

        if args.action == "apply" and not args.confirm_scrub:
            raise RehearsalError("Apply requires --confirm-scrub; no Home state was changed.")
        if args.action == "rollback" and not args.confirm_rollback:
            raise RehearsalError("Rollback requires --confirm-rollback; no Home state was changed.")

        timeout = transport.require_safe_timeout(args.timeout)
        target = transport.plexamp_target(transport.fetch_targets(port, timeout))
        connection = transport.connect_devtools(target, port, timeout)
        try:
            if args.action == "plan":
                result = evaluate_action(connection, build_runtime_expression("plan"), transport.ProbeError)
            elif args.action == "apply":
                capture = evaluate_action(connection, build_runtime_expression("capture"), transport.ProbeError)
                if capture.get("status") != "ready":
                    result = capture
                else:
                    records = validate_records(capture.get("records"))
                    fingerprint = capture.get("target_fingerprint")
                    if not isinstance(fingerprint, str) or SAFE_FINGERPRINT.fullmatch(fingerprint) is None:
                        raise RehearsalError("Capture returned an invalid target fingerprint.")
                    if not records:
                        result = {**public_result(capture), "status": "no-change", "applied": False}
                    else:
                        payload = {
                            "schema_version": 1,
                            "debug_port": port,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "target_fingerprint": fingerprint,
                            "records": records,
                        }
                        write_snapshot(snapshot_path, payload)
                        result = evaluate_action(
                            connection,
                            build_runtime_expression("scrub", expected_fingerprint=fingerprint),
                            transport.ProbeError,
                        )
                        result = {**public_result(result), "snapshot_path": str(snapshot_path), "snapshot_preserved": True}
            else:
                snapshot = read_snapshot(snapshot_path, port)
                result = evaluate_action(
                    connection,
                    build_runtime_expression(
                        "restore",
                        expected_fingerprint=snapshot["target_fingerprint"],
                        restore_records=snapshot["records"],
                    ),
                    transport.ProbeError,
                )
                result = {**public_result(result), "snapshot_path": str(snapshot_path), "snapshot_preserved": True}
        finally:
            connection.close()
    except (RehearsalError, RuntimeError, ValueError, OSError) as exc:
        print(f"Plexamp Home scrub rehearsal: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp Home scrub rehearsal")
    print("DISPOSABLE PROFILE ONLY: bounded Home customisation state; raw keys/values are never printed.")
    print(json.dumps(public_result(result), indent=2, sort_keys=True))
    return 0 if result.get("status") in {"ready", "scrubbed", "restored", "no-change"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
