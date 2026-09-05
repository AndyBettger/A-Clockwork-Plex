#!/usr/bin/env python3
"""Read-only Plexamp browser-storage surface inventory for disposable Chromium.

This developer diagnostic inventories browser-local persistence *metadata only* for
Plexamp's disposable Chromium profile. It reports bounded Local Storage and Session
Storage key-family counts plus IndexedDB database/object-store names. It never reads
Web Storage values, never reads IndexedDB records, never opens an IndexedDB
transaction, and never mutates browser storage.

Use only with a disposable Chromium profile launched manually with loopback-only
remote debugging. The production kiosk Chromium profile is not a target.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


DEFAULT_DEBUG_PORT = 9224
DEFAULT_TIMEOUT = 5.0


RUNTIME_EXPRESSION = r"""
(async () => {
  'use strict';

  const MMKV_PREFIX = 'mmkv.default\\\\';
  const SAFE_FAMILY = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
  const SAFE_DB_NAME = /^[A-Za-z0-9_.:@~+=\/-]{1,160}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_FAMILIES = 64;
  const MAX_DATABASES = 32;
  const MAX_OBJECT_STORES = 64;

  function boundedName(name) {
    if (typeof name !== 'string') return { name: null, name_length: 0, redacted: true };
    const length = Math.min(name.length, 9999);
    if (!SAFE_DB_NAME.test(name) || SENSITIVE_NAME.test(name)) {
      return { name: null, name_length: length, redacted: true };
    }
    return { name, name_length: length, redacted: false };
  }

  function keyFamily(key) {
    if (typeof key !== 'string' || key.length === 0) return 'other';
    let value = key;
    if (value.startsWith(MMKV_PREFIX)) value = value.slice(MMKV_PREFIX.length);
    const parts = value.split(':');
    const first = parts[0];
    if (!SAFE_FAMILY.test(first) || SENSITIVE_NAME.test(first)) return 'other';
    if (parts.length < 2) return first;
    const second = parts[1];
    if (!SAFE_FAMILY.test(second) || SENSITIVE_NAME.test(second)) return first;
    return `${first}:${second}`;
  }

  function inspectWebStorage(storage) {
    let length;
    try {
      length = Number(storage?.length || 0);
    } catch (_error) {
      return { status: 'unavailable', key_count: null, values_read: false, family_counts: [] };
    }
    if (!Number.isFinite(length) || length < 0 || length > MAX_STORAGE_KEYS) {
      return {
        status: 'key-limit-exceeded',
        key_count: Number.isFinite(length) ? length : null,
        values_read: false,
        family_counts: [],
        max_keys: MAX_STORAGE_KEYS,
      };
    }

    const families = new Map();
    for (let index = 0; index < length; index += 1) {
      let key;
      try {
        key = storage.key(index);
      } catch (_error) {
        return { status: 'key-read-failed', key_count: length, values_read: false, family_counts: [] };
      }
      const family = keyFamily(key);
      families.set(family, (families.get(family) || 0) + 1);
    }

    const family_counts = Array.from(families.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .slice(0, MAX_FAMILIES)
      .map(([family, count]) => ({ family, count }));

    return {
      status: families.size > MAX_FAMILIES ? 'family-limit-exceeded' : 'ready',
      key_count: length,
      values_read: false,
      family_counts,
      max_families: MAX_FAMILIES,
    };
  }

  async function inspectIndexedDb() {
    if (!globalThis.indexedDB || typeof globalThis.indexedDB.databases !== 'function') {
      return {
        status: 'databases-api-unavailable',
        records_read: false,
        transactions_opened: false,
        database_count: null,
        databases: [],
      };
    }

    let databaseInfo;
    try {
      databaseInfo = await globalThis.indexedDB.databases();
    } catch (_error) {
      return {
        status: 'database-list-failed',
        records_read: false,
        transactions_opened: false,
        database_count: null,
        databases: [],
      };
    }

    if (!Array.isArray(databaseInfo) || databaseInfo.length > MAX_DATABASES) {
      return {
        status: 'database-limit-exceeded',
        records_read: false,
        transactions_opened: false,
        database_count: Array.isArray(databaseInfo) ? databaseInfo.length : null,
        databases: [],
        max_databases: MAX_DATABASES,
      };
    }

    const databases = [];
    for (const info of databaseInfo) {
      const rawName = typeof info?.name === 'string' ? info.name : null;
      if (!rawName) {
        databases.push({ ...boundedName(rawName), version: null, object_store_count: null, object_stores: [], metadata_status: 'unnamed' });
        continue;
      }

      const objectStores = await new Promise((resolve) => {
        let request;
        try {
          request = globalThis.indexedDB.open(rawName);
        } catch (_error) {
          resolve({ status: 'open-failed', names: [] });
          return;
        }
        request.onerror = () => resolve({ status: 'open-failed', names: [] });
        request.onblocked = () => resolve({ status: 'blocked', names: [] });
        request.onsuccess = () => {
          const db = request.result;
          try {
            const names = Array.from(db.objectStoreNames || []);
            if (names.length > MAX_OBJECT_STORES) {
              resolve({ status: 'object-store-limit-exceeded', names: [] });
            } else {
              resolve({ status: 'ready', names });
            }
          } finally {
            db.close();
          }
        };
      });

      databases.push({
        ...boundedName(rawName),
        version: Number.isFinite(Number(info?.version)) ? Number(info.version) : null,
        object_store_count: objectStores.status === 'ready' ? objectStores.names.length : null,
        object_stores: objectStores.names.map((name) => boundedName(name)),
        metadata_status: objectStores.status,
      });
    }

    return {
      status: 'ready',
      records_read: false,
      transactions_opened: false,
      database_count: databaseInfo.length,
      databases,
      max_databases: MAX_DATABASES,
      max_object_stores: MAX_OBJECT_STORES,
    };
  }

  const local_storage = inspectWebStorage(globalThis.localStorage);
  const session_storage = inspectWebStorage(globalThis.sessionStorage);
  const indexed_db = await inspectIndexedDb();

  const statuses = [local_storage.status, session_storage.status, indexed_db.status];
  const status = statuses.every((value) => value === 'ready') ? 'ready' : 'partial';

  return {
    schema_version: 1,
    status,
    read_only: true,
    web_storage_values_read: false,
    indexeddb_records_read: false,
    indexeddb_transactions_opened: false,
    local_storage,
    session_storage,
    indexed_db,
  };
})()
""".strip()


def load_transport_module():
    module_path = Path(__file__).with_name("inspect-plexamp-home-runtime.py")
    spec = importlib.util.spec_from_file_location("acp_plexamp_home_runtime_probe", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the bounded Plexamp Home runtime probe transport.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory bounded Plexamp browser-storage metadata through a disposable "
            "loopback Chromium DevTools endpoint. Stored values/records are never read."
        )
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=DEFAULT_DEBUG_PORT,
        help=f"loopback Chromium remote-debugging port (default: {DEFAULT_DEBUG_PORT})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"network timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    return parser.parse_args()


def evaluate_probe(connection, probe_error):
    request_id = 1
    connection.send_json(
        {
            "id": request_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": RUNTIME_EXPRESSION,
                "returnByValue": True,
                "awaitPromise": True,
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
            raise probe_error("Chromium rejected the bounded browser-storage Runtime.evaluate request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Plexamp browser-storage probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the browser-storage probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Plexamp browser-storage probe returned an unexpected result shape.")
        return value


def main() -> int:
    args = parse_args()
    transport = load_transport_module()
    try:
        port = transport.require_safe_port(args.debug_port)
        timeout = transport.require_safe_timeout(args.timeout)
        target = transport.plexamp_target(transport.fetch_targets(port, timeout))
        connection = transport.connect_devtools(target, port, timeout)
        try:
            result = evaluate_probe(connection, transport.ProbeError)
        finally:
            connection.close()
    except (transport.ProbeError, RuntimeError) as exc:
        print(f"Plexamp browser-storage probe: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp browser-storage surface probe")
    print("READ-ONLY: storage metadata only; Web Storage values and IndexedDB records are never read.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"ready", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
