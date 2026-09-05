#!/usr/bin/env python3
"""Read-only Plexamp Home-customisation key-family probe for disposable Chromium.

This developer diagnostic inventories only Local Storage *key names* beneath Plexamp's
`mmkv.default\\discovery:customizations:` namespace. It never calls getItem(), never
emits raw keys/context/hub identifiers, and never reads stored values. The result is a
bounded family/count summary used to compare an untouched disposable Home with the
same disposable profile after deliberate Home edits.

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
(() => {
  'use strict';

  const MMKV_PREFIX = 'mmkv.default\\\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SECTION_MARKER = '::/library/sections/';
  const SAFE_IDENTIFIER = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_SECTION = /^[0-9]{1,10}$/;
  const SAFE_TERMINAL = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_MATCHES = 512;
  const MAX_OTHER_TERMINALS = 24;

  const families = {
    order: 0,
    hidden: 0,
    viewSettings: 0,
    editing: 0,
    customHubs: 0,
    other: 0,
  };
  const contexts = new Set();
  const sections = new Set();
  const otherTerminals = new Map();
  let matchingKeys = 0;
  let structurallyInvalid = 0;
  let storageLength = 0;

  let storage;
  try {
    storage = globalThis.localStorage;
    storageLength = Number(storage?.length || 0);
  } catch (_error) {
    return {
      schema_version: 1,
      status: 'local-storage-unavailable',
      read_only: true,
      key_names_only: true,
      storage_values_read: false,
    };
  }

  if (!Number.isFinite(storageLength) || storageLength < 0 || storageLength > MAX_STORAGE_KEYS) {
    return {
      schema_version: 1,
      status: 'storage-key-limit-exceeded',
      read_only: true,
      key_names_only: true,
      storage_values_read: false,
      max_storage_keys: MAX_STORAGE_KEYS,
    };
  }

  function classifySuffix(suffix) {
    if (!suffix.startsWith(CUSTOM_PREFIX)) return null;
    const markerIndex = suffix.indexOf(SECTION_MARKER, CUSTOM_PREFIX.length);
    if (markerIndex < 0) return { family: 'other', valid: false, context: null, section: null, terminal: null };

    const context = suffix.slice(CUSTOM_PREFIX.length, markerIndex);
    const rest = suffix.slice(markerIndex + SECTION_MARKER.length);
    const colonIndex = rest.indexOf(':');
    if (!SAFE_IDENTIFIER.test(context) || colonIndex < 1) {
      return { family: 'other', valid: false, context: null, section: null, terminal: null };
    }

    const section = rest.slice(0, colonIndex);
    const tail = rest.slice(colonIndex + 1);
    if (!SAFE_SECTION.test(section) || !tail) {
      return { family: 'other', valid: false, context: null, section: null, terminal: null };
    }

    if (tail === 'order') return { family: 'order', valid: true, context, section, terminal: 'order' };
    if (tail === 'customHubs') return { family: 'customHubs', valid: true, context, section, terminal: 'customHubs' };

    const finalColon = tail.lastIndexOf(':');
    if (finalColon < 1) {
      const terminal = SAFE_TERMINAL.test(tail) && !SENSITIVE_NAME.test(tail) ? tail : null;
      return { family: 'other', valid: terminal !== null, context, section, terminal };
    }

    const hub = tail.slice(0, finalColon);
    const terminal = tail.slice(finalColon + 1);
    if (!SAFE_IDENTIFIER.test(hub) || !SAFE_TERMINAL.test(terminal) || SENSITIVE_NAME.test(terminal)) {
      return { family: 'other', valid: false, context: null, section: null, terminal: null };
    }

    if (terminal === 'hidden') return { family: 'hidden', valid: true, context, section, terminal };
    if (terminal === 'viewSettings') return { family: 'viewSettings', valid: true, context, section, terminal };
    if (terminal === 'editing') return { family: 'editing', valid: true, context, section, terminal };
    return { family: 'other', valid: true, context, section, terminal };
  }

  for (let index = 0; index < storageLength; index += 1) {
    let key;
    try {
      key = storage.key(index);
    } catch (_error) {
      return {
        schema_version: 1,
        status: 'storage-key-read-failed',
        read_only: true,
        key_names_only: true,
        storage_values_read: false,
      };
    }
    if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX + CUSTOM_PREFIX)) continue;
    matchingKeys += 1;
    if (matchingKeys > MAX_MATCHES) {
      return {
        schema_version: 1,
        status: 'customization-key-limit-exceeded',
        read_only: true,
        key_names_only: true,
        storage_values_read: false,
        max_matching_keys: MAX_MATCHES,
      };
    }

    const suffix = key.slice(MMKV_PREFIX.length);
    const classified = classifySuffix(suffix);
    if (!classified) continue;
    families[classified.family] += 1;
    if (!classified.valid) {
      structurallyInvalid += 1;
      continue;
    }
    contexts.add(classified.context);
    sections.add(`${classified.context}\u0000${classified.section}`);
    if (classified.family === 'other' && classified.terminal) {
      otherTerminals.set(
        classified.terminal,
        (otherTerminals.get(classified.terminal) || 0) + 1,
      );
    }
  }

  const other_terminal_families = Array.from(otherTerminals.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .slice(0, MAX_OTHER_TERMINALS)
    .map(([name, count]) => ({ name, count }));

  return {
    schema_version: 1,
    status: structurallyInvalid > 0 ? 'unclassified-customization-keys' : 'ready',
    read_only: true,
    key_names_only: true,
    storage_values_read: false,
    namespace: 'mmkv.default\\\\discovery:customizations:*',
    matching_key_count: matchingKeys,
    context_count: contexts.size,
    section_context_count: sections.size,
    family_counts: families,
    structurally_invalid_count: structurallyInvalid,
    other_terminal_families,
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
            "Inventory only bounded Plexamp Home customisation Local Storage key families "
            "through a disposable loopback Chromium DevTools endpoint. Stored values are never read."
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
            raise probe_error("Chromium rejected the bounded Home-customisation Runtime.evaluate request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Plexamp Home-customisation probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the Home-customisation probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Plexamp Home-customisation probe returned an unexpected result shape.")
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
        print(f"Plexamp Home customisation probe: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp Home customisation key-family probe")
    print("READ-ONLY: Local Storage key names/families only; stored values are never read.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())