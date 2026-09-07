#!/usr/bin/env python3
"""Compare Local Storage key-name sets between two disposable Plexamp Chromium profiles.

This developer diagnostic is deliberately content-blind. It reads Local Storage key
names only from two loopback-debug Chromium profiles, compares the sets in memory and
emits only bounded/sanitised key-name metadata for keys unique to either profile.
Stored values are never read and browser storage is never mutated.

Use only with disposable Chromium profiles. Never enable remote debugging on the
production kiosk profile for this diagnostic.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


DEFAULT_TRACER_DEBUG_PORT = 9224
DEFAULT_CONTROL_DEBUG_PORT = 9225
DEFAULT_TIMEOUT = 5.0
MAX_STORAGE_KEYS = 2048
MAX_DELTA_KEYS = 64
SAFE_KEY_NAME = re.compile(r"^[A-Za-z0-9_.:@~+=/\\\-]{1,240}$")
SENSITIVE_NAME = re.compile(
    r"(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)",
    re.IGNORECASE,
)


RUNTIME_EXPRESSION = r"""
(() => {
  'use strict';
  const MAX_STORAGE_KEYS = 2048;
  const storage = globalThis.localStorage;
  let length;
  try {
    length = Number(storage?.length || 0);
  } catch (_error) {
    return { status: 'unavailable', key_count: null, values_read: false, keys: [] };
  }
  if (!Number.isFinite(length) || length < 0 || length > MAX_STORAGE_KEYS) {
    return {
      status: 'key-limit-exceeded',
      key_count: Number.isFinite(length) ? length : null,
      values_read: false,
      keys: [],
      max_keys: MAX_STORAGE_KEYS,
    };
  }

  const keys = [];
  for (let index = 0; index < length; index += 1) {
    let key;
    try {
      key = storage.key(index);
    } catch (_error) {
      return { status: 'key-read-failed', key_count: length, values_read: false, keys: [] };
    }
    if (typeof key !== 'string') {
      return { status: 'invalid-key', key_count: length, values_read: false, keys: [] };
    }
    keys.push(key);
  }

  return {
    status: 'ready',
    key_count: length,
    values_read: false,
    keys,
    max_keys: MAX_STORAGE_KEYS,
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
            "Compare Local Storage key names only between two disposable Plexamp Chromium "
            "profiles. Stored values are never read."
        )
    )
    parser.add_argument(
        "--tracer-debug-port",
        type=int,
        default=DEFAULT_TRACER_DEBUG_PORT,
        help=f"loopback Chromium debug port for the tracer profile (default: {DEFAULT_TRACER_DEBUG_PORT})",
    )
    parser.add_argument(
        "--control-debug-port",
        type=int,
        default=DEFAULT_CONTROL_DEBUG_PORT,
        help=f"loopback Chromium debug port for the control profile (default: {DEFAULT_CONTROL_DEBUG_PORT})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"network timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    return parser.parse_args()


def evaluate_keys(connection, probe_error) -> dict[str, object]:
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
            raise probe_error("Chromium rejected the bounded Local Storage key-name request.")
        result = response.get("result")
        if not isinstance(result, dict) or "exceptionDetails" in result:
            raise probe_error("The bounded Local Storage key-name probe failed.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the Local Storage key-name result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Local Storage key-name probe returned an unexpected result shape.")
        return value


def read_profile_keys(transport, port: int, timeout: float) -> dict[str, object]:
    target = transport.plexamp_target(transport.fetch_targets(port, timeout))
    connection = transport.connect_devtools(target, port, timeout)
    try:
        result = evaluate_keys(connection, transport.ProbeError)
    finally:
        connection.close()

    if result.get("status") != "ready":
        raise transport.ProbeError(
            f"Local Storage key-name inventory on debug port {port} was not ready: {result.get('status')}"
        )
    keys = result.get("keys")
    key_count = result.get("key_count")
    if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
        raise transport.ProbeError("Chromium returned an invalid Local Storage key-name inventory.")
    if not isinstance(key_count, int) or isinstance(key_count, bool) or key_count != len(keys):
        raise transport.ProbeError("Local Storage key count did not match the returned key-name inventory.")
    if len(keys) != len(set(keys)):
        raise transport.ProbeError("Local Storage key-name inventory unexpectedly contained duplicates.")
    return {"key_count": key_count, "keys": set(keys), "values_read": False}


def safe_key_metadata(name: str) -> dict[str, object]:
    length = min(len(name), 9999)
    if SAFE_KEY_NAME.fullmatch(name) is None or SENSITIVE_NAME.search(name):
        return {"name": None, "name_length": length, "redacted": True}
    return {"name": name, "name_length": length, "redacted": False}


def bounded_delta(names: set[str]) -> tuple[list[dict[str, object]], bool]:
    ordered = sorted(names)
    truncated = len(ordered) > MAX_DELTA_KEYS
    return [safe_key_metadata(name) for name in ordered[:MAX_DELTA_KEYS]], truncated


def main() -> int:
    args = parse_args()
    transport = load_transport_module()
    try:
        tracer_port = transport.require_safe_port(args.tracer_debug_port)
        control_port = transport.require_safe_port(args.control_debug_port)
        timeout = transport.require_safe_timeout(args.timeout)
        if tracer_port == control_port:
            raise transport.ProbeError("Tracer and control debug ports must be different.")

        tracer = read_profile_keys(transport, tracer_port, timeout)
        control = read_profile_keys(transport, control_port, timeout)
    except (transport.ProbeError, RuntimeError) as exc:
        print(f"Plexamp Local Storage key comparison: ERROR — {exc}", file=sys.stderr)
        return 1

    tracer_keys = tracer["keys"]
    control_keys = control["keys"]
    assert isinstance(tracer_keys, set)
    assert isinstance(control_keys, set)

    tracer_only_names = tracer_keys - control_keys
    control_only_names = control_keys - tracer_keys
    common_names = tracer_keys & control_keys
    tracer_only, tracer_truncated = bounded_delta(tracer_only_names)
    control_only, control_truncated = bounded_delta(control_only_names)

    result = {
        "schema_version": 1,
        "status": "ready",
        "read_only": True,
        "storage_values_read": False,
        "tracer": {
            "debug_port": tracer_port,
            "key_count": tracer["key_count"],
        },
        "control": {
            "debug_port": control_port,
            "key_count": control["key_count"],
        },
        "common_key_count": len(common_names),
        "tracer_only_count": len(tracer_only_names),
        "tracer_only": tracer_only,
        "tracer_only_truncated": tracer_truncated,
        "control_only_count": len(control_only_names),
        "control_only": control_only,
        "control_only_truncated": control_truncated,
        "max_delta_keys": MAX_DELTA_KEYS,
    }

    print("Plexamp Local Storage key-name comparison")
    print("READ-ONLY: compares key names only; Local Storage values are never read.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
