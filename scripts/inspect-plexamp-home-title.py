#!/usr/bin/env python3
r"""Read-only Plexamp Home title matcher for disposable Chromium profiles.

This developer diagnostic reads only bounded, structurally validated Plexamp Home
`viewSettings` Local Storage records and inspects only their optional validated
`title` field. It never emits stored titles, raw Local Storage values, raw keys,
context identifiers or hub identifiers, and it never mutates browser storage.

Use only with a disposable Chromium profile launched manually with loopback-only
remote debugging. The production kiosk Chromium profile is not a target.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


DEFAULT_DEBUG_PORT = 9228
DEFAULT_TIMEOUT = 5.0
MAX_TITLE_CHARS = 240


RUNTIME_TEMPLATE = r"""
(() => {
  'use strict';

  const EXPECTED_TITLE = __EXPECTED_TITLE__;
  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SECTION_MARKER = '::/library/sections/';
  const VIEW_FAMILY_SUFFIX = ':viewSettings';
  const VIEW_RE = /^discovery:customizations:([A-Za-z0-9_.:/%+@~=\-]{1,600})::\/library\/sections\/([0-9]{1,10}):([A-Za-z0-9_.:/%+@~=\-]{1,600}):viewSettings$/;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_VIEW_RECORDS = 256;
  const MAX_VIEW_BYTES = 16384;
  const MAX_TITLE_CHARS = 240;

  function safeTitle(value) {
    if (typeof value !== 'string' || !value.length || value.length > MAX_TITLE_CHARS) return null;
    if (Array.from(value).some((char) => char.codePointAt(0) < 32)) return null;
    return value;
  }

  function looksLikeViewSettingsFamily(suffix) {
    return typeof suffix === 'string'
      && suffix.startsWith(CUSTOM_PREFIX)
      && suffix.includes(SECTION_MARKER)
      && suffix.endsWith(VIEW_FAMILY_SUFFIX);
  }

  function decodeTitle(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_VIEW_BYTES) {
      return { ok: false, hasTitle: false, title: null };
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return { ok: false, hasTitle: false, title: null };
    }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      return { ok: false, hasTitle: false, title: null };
    }

    let value = parsed;
    const outerKeys = Object.keys(parsed);
    if (
      outerKeys.length === 1
      && typeof outerKeys[0] === 'string'
      && outerKeys[0].length <= 32
      && parsed[outerKeys[0]]
      && !Array.isArray(parsed[outerKeys[0]])
      && typeof parsed[outerKeys[0]] === 'object'
    ) {
      value = parsed[outerKeys[0]];
    }

    if (!Object.prototype.hasOwnProperty.call(value, 'title')) {
      return { ok: true, hasTitle: false, title: null };
    }
    const title = safeTitle(value.title);
    if (title === null) return { ok: false, hasTitle: true, title: null };
    return { ok: true, hasTitle: true, title };
  }

  let storage;
  let storageLength = 0;
  try {
    storage = globalThis.localStorage;
    storageLength = Number(storage?.length || 0);
  } catch (_error) {
    return {
      schema_version: 1,
      status: 'local-storage-unavailable',
      read_only: true,
      storage_values_read: true,
      value_scope: 'validated-viewSettings-title-only',
      titles_emitted: false,
    };
  }

  if (!Number.isFinite(storageLength) || storageLength < 0 || storageLength > MAX_STORAGE_KEYS) {
    return {
      schema_version: 1,
      status: 'storage-key-limit-exceeded',
      read_only: true,
      storage_values_read: true,
      value_scope: 'validated-viewSettings-title-only',
      titles_emitted: false,
      max_storage_keys: MAX_STORAGE_KEYS,
    };
  }

  let viewSettingsRecords = 0;
  let titledRecords = 0;
  let untitledRecords = 0;
  let expectedMatches = 0;
  let unsupportedRecords = 0;
  let unclassifiedViewKeys = 0;
  const contexts = new Set();
  const sections = new Set();

  for (let index = 0; index < storageLength; index += 1) {
    let key;
    try {
      key = storage.key(index);
    } catch (_error) {
      return {
        schema_version: 1,
        status: 'storage-key-read-failed',
        read_only: true,
        storage_values_read: true,
        value_scope: 'validated-viewSettings-title-only',
        titles_emitted: false,
      };
    }
    if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX)) continue;

    const suffix = key.slice(MMKV_PREFIX.length);
    const match = suffix.match(VIEW_RE);
    if (!match) {
      if (looksLikeViewSettingsFamily(suffix)) unclassifiedViewKeys += 1;
      continue;
    }

    viewSettingsRecords += 1;
    if (viewSettingsRecords > MAX_VIEW_RECORDS) {
      return {
        schema_version: 1,
        status: 'view-settings-record-limit-exceeded',
        read_only: true,
        storage_values_read: true,
        value_scope: 'validated-viewSettings-title-only',
        titles_emitted: false,
        max_view_settings_records: MAX_VIEW_RECORDS,
      };
    }

    contexts.add(`${match[1]}\u0000${match[2]}`);
    sections.add(`${match[1]}\u0000${match[2]}\u0000${match[3]}`);

    let raw;
    try {
      raw = storage.getItem(key);
    } catch (_error) {
      unsupportedRecords += 1;
      continue;
    }
    const decoded = decodeTitle(raw);
    if (!decoded.ok) {
      unsupportedRecords += 1;
      continue;
    }
    if (!decoded.hasTitle) {
      untitledRecords += 1;
      continue;
    }
    titledRecords += 1;
    if (decoded.title === EXPECTED_TITLE) expectedMatches += 1;
  }

  let status = 'ready';
  if (unclassifiedViewKeys > 0) status = 'unclassified-view-settings-key';
  else if (unsupportedRecords > 0) status = 'unsupported-view-settings-format';

  return {
    schema_version: 1,
    status,
    read_only: true,
    storage_values_read: true,
    value_scope: 'validated-viewSettings-title-only',
    titles_emitted: false,
    raw_values_emitted: false,
    raw_keys_emitted: false,
    expected_title_emitted: false,
    expected_title_length: EXPECTED_TITLE.length,
    view_settings_record_count: viewSettingsRecords,
    titled_view_settings_count: titledRecords,
    untitled_view_settings_count: untitledRecords,
    expected_title_match_count: expectedMatches,
    nonmatching_titled_view_settings_count: Math.max(0, titledRecords - expectedMatches),
    context_count: contexts.size,
    section_hub_count: sections.size,
    unclassified_view_settings_key_count: unclassifiedViewKeys,
    unsupported_view_settings_record_count: unsupportedRecords,
  };
})()
""".strip()


def require_expected_title(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_TITLE_CHARS:
        raise ValueError(f"expected title must contain 1-{MAX_TITLE_CHARS} characters")
    if any(ord(char) < 32 for char in value):
        raise ValueError("expected title must not contain control characters")
    return value


def build_runtime_expression(expected_title: str) -> str:
    title = require_expected_title(expected_title)
    return RUNTIME_TEMPLATE.replace("__EXPECTED_TITLE__", json.dumps(title, ensure_ascii=True), 1)


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
            "Compare one expected title against only validated Plexamp Home viewSettings.title "
            "fields through a disposable loopback Chromium DevTools endpoint. Stored titles "
            "and raw Local Storage values are never emitted."
        )
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=DEFAULT_DEBUG_PORT,
        help=f"loopback Chromium remote-debugging port (default: {DEFAULT_DEBUG_PORT})",
    )
    parser.add_argument(
        "--expected-title",
        required=True,
        help="known title to compare against; the title itself is not printed in probe output",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"network timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    return parser.parse_args()


def evaluate_probe(connection, probe_error, expression: str):
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
            raise probe_error("Chromium rejected the bounded Home-title Runtime.evaluate request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise probe_error("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise probe_error("The bounded Plexamp Home-title probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise probe_error("Chromium did not return the Home-title probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise probe_error("Plexamp Home-title probe returned an unexpected result shape.")
        return value


def main() -> int:
    args = parse_args()
    transport = load_transport_module()
    try:
        expected_title = require_expected_title(args.expected_title)
        expression = build_runtime_expression(expected_title)
        port = transport.require_safe_port(args.debug_port)
        timeout = transport.require_safe_timeout(args.timeout)
        target = transport.plexamp_target(transport.fetch_targets(port, timeout))
        connection = transport.connect_devtools(target, port, timeout)
        try:
            result = evaluate_probe(connection, transport.ProbeError, expression)
        finally:
            connection.close()
    except (transport.ProbeError, RuntimeError, ValueError) as exc:
        print(f"Plexamp Home title probe: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp Home title matcher")
    print(
        "READ-ONLY: reads only validated viewSettings values to compare their optional title field; "
        "stored titles/raw values/raw keys are never emitted."
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
