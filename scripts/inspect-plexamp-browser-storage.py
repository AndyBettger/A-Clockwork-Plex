#!/usr/bin/env python3
"""Read-only Plexamp browser-storage surface inventory for disposable Chromium.

This developer diagnostic inventories browser-local persistence *metadata only* for
Plexamp's disposable Chromium profile. It reports bounded Local Storage and Session
Storage key-family counts plus IndexedDB database/object-store names. Web Storage
values and IndexedDB records are never read, IndexedDB transactions are never opened,
and the page never opens/creates an IndexedDB database.

IndexedDB schema metadata is obtained through Chrome DevTools Protocol's read-only
IndexedDB metadata commands (`requestDatabaseNames` / `requestDatabase`), not the
page-level IndexedDB API.

Use only with a disposable Chromium profile launched manually with loopback-only
remote debugging. The production kiosk Chromium profile is not a target.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_DEBUG_PORT = 9224
DEFAULT_TIMEOUT = 5.0
MAX_DATABASES = 32
MAX_OBJECT_STORES = 64
SAFE_METADATA_NAME = re.compile(r"^[A-Za-z0-9_.:@~+=\/-]{1,160}$")
SENSITIVE_NAME = re.compile(
    r"(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)",
    re.IGNORECASE,
)


RUNTIME_EXPRESSION = r"""
(() => {
  'use strict';

  const MMKV_PREFIX = 'mmkv.default\\\\';
  const SAFE_FAMILY = /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_FAMILIES = 64;

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

  return {
    schema_version: 1,
    read_only: true,
    web_storage_values_read: false,
    local_storage: inspectWebStorage(globalThis.localStorage),
    session_storage: inspectWebStorage(globalThis.sessionStorage),
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


def cdp_call(connection, request_id: int, method: str, params: dict[str, object], probe_error):
    connection.send_json(
        {
            "id": request_id,
            "method": method,
            "params": params,
        }
    )
    while True:
        response = connection.recv_json()
        if response.get("id") != request_id:
            continue
        if "error" in response:
            raise probe_error(f"Chromium rejected the bounded {method} metadata request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error(f"Chromium returned an unexpected result for {method}.")
        return result


def evaluate_web_storage(connection, probe_error):
    request_id = 1
    connection.send_json(
        {
            "id": request_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": RUNTIME_EXPRESSION,
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
            raise probe_error("Chromium rejected the bounded Web Storage metadata request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Plexamp Web Storage probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the Web Storage probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Plexamp Web Storage probe returned an unexpected result shape.")
        return value


def target_security_origin(target: dict[str, object], probe_error) -> str:
    raw_url = target.get("url")
    if not isinstance(raw_url, str):
        raise probe_error("Plexamp target did not expose a page URL.")
    parsed = urlparse(raw_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port != 32500:
        raise probe_error("Plexamp target escaped the expected loopback origin.")
    return f"http://{parsed.hostname}:32500"


def bounded_metadata_name(name: object) -> dict[str, object]:
    if not isinstance(name, str):
        return {"name": None, "name_length": 0, "redacted": True}
    length = min(len(name), 9999)
    if SAFE_METADATA_NAME.fullmatch(name) is None or SENSITIVE_NAME.search(name):
        return {"name": None, "name_length": length, "redacted": True}
    return {"name": name, "name_length": length, "redacted": False}


def inspect_indexeddb(connection, security_origin: str, probe_error) -> dict[str, object]:
    cdp_call(connection, 2, "IndexedDB.enable", {}, probe_error)
    names_result = cdp_call(
        connection,
        3,
        "IndexedDB.requestDatabaseNames",
        {"securityOrigin": security_origin},
        probe_error,
    )
    database_names = names_result.get("databaseNames")
    if not isinstance(database_names, list) or any(not isinstance(name, str) for name in database_names):
        raise probe_error("Chromium returned an unexpected IndexedDB database-name inventory.")
    if len(database_names) > MAX_DATABASES:
        return {
            "status": "database-limit-exceeded",
            "records_read": False,
            "transactions_opened": False,
            "page_database_opened": False,
            "database_count": len(database_names),
            "databases": [],
            "max_databases": MAX_DATABASES,
            "max_object_stores": MAX_OBJECT_STORES,
        }

    databases: list[dict[str, object]] = []
    next_request_id = 4
    for raw_name in database_names:
        metadata_result = cdp_call(
            connection,
            next_request_id,
            "IndexedDB.requestDatabase",
            {"securityOrigin": security_origin, "databaseName": raw_name},
            probe_error,
        )
        next_request_id += 1
        database = metadata_result.get("databaseWithObjectStores")
        if not isinstance(database, dict):
            raise probe_error("Chromium returned an unexpected IndexedDB database metadata shape.")
        object_stores = database.get("objectStores")
        if not isinstance(object_stores, list):
            raise probe_error("Chromium returned an unexpected IndexedDB object-store inventory.")
        if len(object_stores) > MAX_OBJECT_STORES:
            databases.append(
                {
                    **bounded_metadata_name(raw_name),
                    "version": None,
                    "object_store_count": len(object_stores),
                    "object_stores": [],
                    "metadata_status": "object-store-limit-exceeded",
                }
            )
            continue

        store_names: list[dict[str, object]] = []
        for store in object_stores:
            if not isinstance(store, dict):
                raise probe_error("Chromium returned a malformed IndexedDB object-store entry.")
            store_names.append(bounded_metadata_name(store.get("name")))

        version = database.get("version")
        if not isinstance(version, (int, float)) or isinstance(version, bool):
            version = None
        databases.append(
            {
                **bounded_metadata_name(raw_name),
                "version": version,
                "object_store_count": len(object_stores),
                "object_stores": store_names,
                "metadata_status": "ready",
            }
        )

    return {
        "status": "ready",
        "records_read": False,
        "transactions_opened": False,
        "page_database_opened": False,
        "database_count": len(database_names),
        "databases": databases,
        "max_databases": MAX_DATABASES,
        "max_object_stores": MAX_OBJECT_STORES,
    }


def main() -> int:
    args = parse_args()
    transport = load_transport_module()
    try:
        port = transport.require_safe_port(args.debug_port)
        timeout = transport.require_safe_timeout(args.timeout)
        target = transport.plexamp_target(transport.fetch_targets(port, timeout))
        security_origin = target_security_origin(target, transport.ProbeError)
        connection = transport.connect_devtools(target, port, timeout)
        try:
            web_storage = evaluate_web_storage(connection, transport.ProbeError)
            indexed_db = inspect_indexeddb(connection, security_origin, transport.ProbeError)
        finally:
            connection.close()
    except (transport.ProbeError, RuntimeError) as exc:
        print(f"Plexamp browser-storage probe: ERROR — {exc}", file=sys.stderr)
        return 1

    local_storage = web_storage.get("local_storage")
    session_storage = web_storage.get("session_storage")
    statuses = [
        local_storage.get("status") if isinstance(local_storage, dict) else None,
        session_storage.get("status") if isinstance(session_storage, dict) else None,
        indexed_db.get("status"),
    ]
    status = "ready" if all(value == "ready" for value in statuses) else "partial"
    result = {
        "schema_version": 1,
        "status": status,
        "read_only": True,
        "web_storage_values_read": False,
        "indexeddb_records_read": False,
        "indexeddb_transactions_opened": False,
        "indexeddb_page_database_opened": False,
        "local_storage": local_storage,
        "session_storage": session_storage,
        "indexed_db": indexed_db,
    }

    print("Plexamp browser-storage surface probe")
    print("READ-ONLY: metadata only; Web Storage values and IndexedDB records are never read.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status in {"ready", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
