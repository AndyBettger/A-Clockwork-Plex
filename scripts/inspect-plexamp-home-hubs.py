#!/usr/bin/env python3
"""Read-only Plexamp effective-Home hub-shape probe for a disposable Chromium profile.

This is a deliberately narrower follow-up to inspect-plexamp-home-runtime.py. It
uses the previously discovered MobX backing path for Plexamp's live discovery hubs
and emits only object/member names, kinds and bounded collection lengths. Primitive
values are never emitted, accessors/getters are never invoked, and the DevTools
transport remains loopback-only and restricted to the local Plexamp page.

Use only with a disposable Chromium profile launched manually with a loopback-only
remote-debugging port. The production kiosk Chromium profile is not a target.
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

  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const MAX_HUBS = 24;
  const MAX_MEMBERS = 100;
  const MISSING = Symbol('missing');

  function ownDataValue(object, name) {
    if (!object || (typeof object !== 'object' && typeof object !== 'function')) return MISSING;
    let descriptor;
    try {
      descriptor = Object.getOwnPropertyDescriptor(object, name);
    } catch (_error) {
      return MISSING;
    }
    if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) return MISSING;
    return descriptor.value;
  }

  function objectKind(value) {
    if (value === MISSING) return 'missing';
    if (Array.isArray(value)) return 'array';
    if (value === null) return 'null';
    if (typeof value === 'function') return 'function';
    if (typeof value !== 'object') return typeof value;
    return 'object';
  }

  function safeDescriptors(value) {
    if (!value || (typeof value !== 'object' && typeof value !== 'function')) return null;
    try {
      return Object.getOwnPropertyDescriptors(value);
    } catch (_error) {
      return null;
    }
  }

  function memberShape(value) {
    const descriptors = safeDescriptors(value);
    if (!descriptors) return [];
    return Object.keys(descriptors)
      .filter((name) => !SENSITIVE_NAME.test(name))
      .sort((left, right) => left.localeCompare(right))
      .slice(0, MAX_MEMBERS)
      .map((name) => {
        const descriptor = descriptors[name];
        if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
          return { name, kind: 'accessor' };
        }
        const child = descriptor.value;
        const entry = { name, kind: objectKind(child) };
        if (Array.isArray(child)) entry.length = Math.min(child.length, 9999);
        return entry;
      });
  }

  function observableValueShapes(host) {
    const mobx = ownDataValue(host, '$mobx');
    const values = ownDataValue(mobx, 'values');
    if (!values || values === MISSING || typeof values !== 'object') return [];
    const descriptors = safeDescriptors(values);
    if (!descriptors) return [];

    return Object.keys(descriptors)
      .filter((name) => !SENSITIVE_NAME.test(name))
      .sort((left, right) => left.localeCompare(right))
      .slice(0, MAX_MEMBERS)
      .map((name) => {
        const observable = ownDataValue(values, name);
        const entry = {
          name,
          observable_kind: objectKind(observable),
        };
        if (observable === MISSING) return entry;
        const value = ownDataValue(observable, 'value');
        entry.value_kind = objectKind(value);
        if (Array.isArray(value)) {
          entry.value_length = Math.min(value.length, 9999);
        } else if (value && value !== MISSING && typeof value === 'object') {
          entry.value_members = memberShape(value);
        }
        return entry;
      });
  }

  function nestedObjectShapes(host) {
    const descriptors = safeDescriptors(host);
    if (!descriptors) return [];
    const nested = [];
    for (const name of Object.keys(descriptors).sort((a, b) => a.localeCompare(b))) {
      if (name === '$mobx' || SENSITIVE_NAME.test(name)) continue;
      const descriptor = descriptors[name];
      if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) continue;
      const value = descriptor.value;
      if (!value || typeof value !== 'object') continue;
      const entry = { name, kind: objectKind(value), members: memberShape(value) };
      if (Array.isArray(value)) entry.length = Math.min(value.length, 9999);
      nested.push(entry);
      if (nested.length >= 24) break;
    }
    return nested;
  }

  const globalObject = ownDataValue(globalThis, 'global');
  const globalApp = ownDataValue(globalObject, 'app');
  const globalRoot = ownDataValue(globalApp, 'rootStore');
  const directApp = ownDataValue(globalThis, 'app');
  const directRoot = ownDataValue(directApp, 'rootStore');
  const root = globalRoot !== MISSING ? globalRoot : directRoot;

  if (!root || root === MISSING || typeof root !== 'object') {
    return {
      schema_version: 1,
      status: 'root-store-unavailable',
      read_only: true,
      values_exposed: false,
      getters_invoked: false,
    };
  }

  const discovery = ownDataValue(root, 'discovery');
  const discoveryMobx = ownDataValue(discovery, '$mobx');
  const discoveryValues = ownDataValue(discoveryMobx, 'values');
  const hubsObservable = ownDataValue(discoveryValues, 'hubs');
  const observableArray = ownDataValue(hubsObservable, 'value');
  const arrayMobx = ownDataValue(observableArray, '$mobx');
  const hubs = ownDataValue(arrayMobx, 'values');

  if (!Array.isArray(hubs)) {
    return {
      schema_version: 1,
      status: 'discovery-hubs-unavailable',
      read_only: true,
      values_exposed: false,
      getters_invoked: false,
      authority_path: 'rootStore.discovery.$mobx.values.hubs.value.$mobx.values',
      authority_kind: objectKind(hubs),
    };
  }

  if (hubs.length > MAX_HUBS) {
    return {
      schema_version: 1,
      status: 'hub-count-exceeded',
      read_only: true,
      values_exposed: false,
      getters_invoked: false,
      hub_count: hubs.length,
      max_hubs: MAX_HUBS,
    };
  }

  const hub_shapes = [];
  for (let index = 0; index < hubs.length; index += 1) {
    const descriptor = Object.getOwnPropertyDescriptor(hubs, String(index));
    if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
      hub_shapes.push({ index, kind: 'accessor-or-missing' });
      continue;
    }
    const hub = descriptor.value;
    hub_shapes.push({
      index,
      kind: objectKind(hub),
      members: memberShape(hub),
      observable_values: observableValueShapes(hub),
      nested_objects: nestedObjectShapes(hub),
    });
  }

  return {
    schema_version: 1,
    status: 'ready',
    read_only: true,
    values_exposed: false,
    getters_invoked: false,
    authority_path: 'rootStore.discovery.$mobx.values.hubs.value.$mobx.values',
    hub_count: hubs.length,
    hub_shapes,
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
            "Inspect only bounded names/shapes for the live Plexamp discovery-hub collection "
            "through a disposable loopback Chromium DevTools endpoint."
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
            raise probe_error("Chromium rejected the bounded discovery-hub Runtime.evaluate request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Plexamp discovery-hub probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the discovery-hub probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Plexamp discovery-hub probe returned an unexpected result shape.")
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
        print(f"Plexamp Home discovery-hub probe: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp Home discovery-hub probe")
    print("READ-ONLY: names/shapes only; primitive values are not emitted; getters are not invoked.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
