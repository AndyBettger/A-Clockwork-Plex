#!/usr/bin/env python3
"""Read-only Plexamp Home runtime-shape probe for a disposable Chromium profile.

This development diagnostic connects only to a loopback Chromium DevTools endpoint,
selects only the local Plexamp page on port 32500, and evaluates one hard-coded,
read-only object-shape inspection expression. It never accepts arbitrary JavaScript,
never reads primitive values from the Plexamp object graph, never invokes getters,
and never calls mutating CDP domains.

The intended target is a disposable Chromium profile such as:

    /var/tmp/plexamp-chromium-profile

launched manually with a loopback-only --remote-debugging-port. Production kiosk
Chromium is not launched with remote debugging and is not the target of this tool.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse


DEFAULT_DEBUG_PORT = 9224
DEFAULT_TIMEOUT = 5.0
PLEXAMP_HOSTS = {"localhost", "127.0.0.1"}
MAX_HTTP_BYTES = 1_000_000
MAX_WS_MESSAGE_BYTES = 4_000_000


RUNTIME_EXPRESSION = r"""
(() => {
  'use strict';

  const ROOT_CANDIDATES = [
    globalThis.global?.app?.rootStore,
    globalThis.app?.rootStore,
  ];
  const root = ROOT_CANDIDATES.find((value) => value && typeof value === 'object');
  if (!root) {
    return {
      schema_version: 1,
      status: 'root-store-unavailable',
      read_only: true,
      values_exposed: false,
    };
  }

  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const HOME_NAME = /(home|hub|discovery|section|customi|source|recommend|dashboard|library)/i;
  const MAX_DEPTH = 6;
  const MAX_NODES = 1800;
  const MAX_KEYS_PER_OBJECT = 180;
  const MAX_ARRAY_ITEMS = 24;
  const MAX_CANDIDATES = 240;
  const seen = new WeakSet();
  const candidates = [];
  let visited_nodes = 0;
  let truncated = false;

  function safeDescriptors(value) {
    try {
      return Object.getOwnPropertyDescriptors(value);
    } catch (_error) {
      return null;
    }
  }

  function objectKind(value) {
    if (Array.isArray(value)) return 'array';
    if (typeof value === 'function') return 'function';
    if (!value || typeof value !== 'object') return typeof value;
    let constructorName = null;
    try {
      const descriptor = Object.getOwnPropertyDescriptor(value, 'constructor');
      if (descriptor && Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
        const ctor = descriptor.value;
        if (typeof ctor === 'function' && typeof ctor.name === 'string') {
          constructorName = ctor.name.slice(0, 120);
        }
      }
    } catch (_error) {
      constructorName = null;
    }
    return constructorName ? `object:${constructorName}` : 'object';
  }

  function memberShape(descriptors) {
    if (!descriptors) return [];
    const names = Object.keys(descriptors)
      .filter((name) => !SENSITIVE_NAME.test(name))
      .sort((left, right) => left.localeCompare(right))
      .slice(0, 100);
    return names.map((name) => {
      const descriptor = descriptors[name];
      if (!descriptor) return { name, kind: 'unknown' };
      if (!Object.prototype.hasOwnProperty.call(descriptor, 'value')) {
        return { name, kind: 'accessor' };
      }
      const value = descriptor.value;
      if (Array.isArray(value)) return { name, kind: 'array', length: Math.min(value.length, 9999) };
      if (value && typeof value === 'object') return { name, kind: objectKind(value) };
      return { name, kind: typeof value };
    });
  }

  function recordCandidate(path, value, descriptors) {
    if (candidates.length >= MAX_CANDIDATES) {
      truncated = true;
      return;
    }
    const entry = {
      path,
      kind: objectKind(value),
      members: memberShape(descriptors),
    };
    if (Array.isArray(value)) entry.length = Math.min(value.length, 9999);
    candidates.push(entry);
  }

  function walk(value, path, depth, matchedPath = false) {
    if (visited_nodes >= MAX_NODES || depth > MAX_DEPTH) {
      truncated = true;
      return;
    }
    if (!value || (typeof value !== 'object' && typeof value !== 'function')) return;
    if (seen.has(value)) return;
    seen.add(value);
    visited_nodes += 1;

    const descriptors = safeDescriptors(value);
    if (!descriptors) return;
    if (matchedPath) recordCandidate(path, value, descriptors);

    const names = Object.keys(descriptors).slice(0, MAX_KEYS_PER_OBJECT);
    if (Object.keys(descriptors).length > MAX_KEYS_PER_OBJECT) truncated = true;

    for (const name of names) {
      if (SENSITIVE_NAME.test(name)) continue;
      const descriptor = descriptors[name];
      if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, 'value')) continue;
      const child = descriptor.value;
      if (!child || (typeof child !== 'object' && typeof child !== 'function')) continue;
      const matched = matchedPath || HOME_NAME.test(name);
      const childPath = `${path}.${name}`;
      walk(child, childPath, depth + 1, matched);

      if (Array.isArray(child) && depth + 1 < MAX_DEPTH) {
        const limit = Math.min(child.length, MAX_ARRAY_ITEMS);
        if (child.length > limit) truncated = true;
        for (let index = 0; index < limit; index += 1) {
          const itemDescriptor = Object.getOwnPropertyDescriptor(child, String(index));
          if (!itemDescriptor || !Object.prototype.hasOwnProperty.call(itemDescriptor, 'value')) continue;
          const item = itemDescriptor.value;
          if (!item || (typeof item !== 'object' && typeof item !== 'function')) continue;
          walk(item, `${childPath}[${index}]`, depth + 2, matched);
        }
      }
    }
  }

  const topDescriptors = safeDescriptors(root) || {};
  const top_level_members = memberShape(topDescriptors);
  walk(root, 'rootStore', 0, false);

  return {
    schema_version: 1,
    status: 'ready',
    read_only: true,
    values_exposed: false,
    getters_invoked: false,
    top_level_members,
    candidate_count: candidates.length,
    visited_nodes,
    truncated,
    candidates,
  };
})()
""".strip()


class ProbeError(RuntimeError):
    """Expected, user-facing diagnostic failure."""


@dataclass
class WebSocketConnection:
    sock: socket.socket

    def send_json(self, payload: dict[str, object]) -> None:
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        if len(text) > MAX_WS_MESSAGE_BYTES:
            raise ProbeError("Outgoing DevTools request exceeded the diagnostic size limit.")
        self._send_frame(0x1, text)

    def recv_json(self) -> dict[str, object]:
        fragments = bytearray()
        started = False
        while True:
            fin, opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise ProbeError("Chromium closed the DevTools connection before replying.")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x1:
                fragments = bytearray(payload)
                started = True
            elif opcode == 0x0 and started:
                fragments.extend(payload)
            else:
                continue
            if len(fragments) > MAX_WS_MESSAGE_BYTES:
                raise ProbeError("DevTools response exceeded the diagnostic size limit.")
            if fin:
                try:
                    decoded = json.loads(fragments.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProbeError("Chromium returned an invalid DevTools JSON message.") from exc
                if not isinstance(decoded, dict):
                    raise ProbeError("Chromium returned an unexpected DevTools response shape.")
                return decoded

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        self.sock.close()

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        first = 0x80 | (opcode & 0x0F)
        mask_key = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes((first, 0x80 | length))
        elif length <= 0xFFFF:
            header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
        else:
            header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
        masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(header + mask_key + masked)

    def _recv_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.sock.recv(length - len(chunks))
            if not chunk:
                raise ProbeError("DevTools WebSocket closed unexpectedly.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _recv_frame(self) -> tuple[bool, int, bytes]:
        first, second = self._recv_exact(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        if length > MAX_WS_MESSAGE_BYTES:
            raise ProbeError("DevTools WebSocket frame exceeded the diagnostic size limit.")
        mask_key = self._recv_exact(4) if masked else None
        payload = self._recv_exact(length)
        if mask_key is not None:
            payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        return fin, opcode, payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect only the shape/names of Home-related objects beneath Plexamp's live "
            "rootStore through a loopback DevTools endpoint. No Plexamp values are emitted."
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


def require_safe_port(port: int) -> int:
    if port < 1024 or port > 65535:
        raise ProbeError("Debug port must be an unprivileged TCP port between 1024 and 65535.")
    return port


def require_safe_timeout(timeout: float) -> float:
    if timeout <= 0 or timeout > 30:
        raise ProbeError("Timeout must be greater than 0 and no more than 30 seconds.")
    return timeout


def fetch_targets(port: int, timeout: float) -> list[dict[str, object]]:
    url = f"http://127.0.0.1:{port}/json/list"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_HTTP_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProbeError(
            f"Could not reach disposable Chromium DevTools on 127.0.0.1:{port}."
        ) from exc
    if len(raw) > MAX_HTTP_BYTES:
        raise ProbeError("Chromium target list exceeded the diagnostic size limit.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError("Chromium returned an invalid target list.") from exc
    if not isinstance(payload, list):
        raise ProbeError("Chromium returned an unexpected target-list shape.")
    return [item for item in payload if isinstance(item, dict)]


def plexamp_target(targets: list[dict[str, object]]) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for target in targets:
        if target.get("type") != "page":
            continue
        url = target.get("url")
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in PLEXAMP_HOSTS or parsed.port != 32500:
            continue
        matches.append(target)
    if len(matches) != 1:
        raise ProbeError(
            "Expected exactly one disposable Chromium page at http://localhost:32500; "
            f"found {len(matches)}."
        )
    return matches[0]


def connect_devtools(target: dict[str, object], debug_port: int, timeout: float) -> WebSocketConnection:
    websocket_url = target.get("webSocketDebuggerUrl")
    if not isinstance(websocket_url, str):
        raise ProbeError("Plexamp target did not expose a DevTools WebSocket URL.")
    parsed = urlparse(websocket_url)
    if parsed.scheme != "ws" or parsed.hostname not in PLEXAMP_HOSTS:
        raise ProbeError("DevTools WebSocket is not loopback-scoped.")
    if parsed.port != debug_port:
        raise ProbeError("DevTools WebSocket escaped the selected loopback debug port.")
    if not parsed.path.startswith("/devtools/page/"):
        raise ProbeError("DevTools target is not a page endpoint.")

    try:
        sock = socket.create_connection(("127.0.0.1", debug_port), timeout=timeout)
        sock.settimeout(timeout)
    except OSError as exc:
        raise ProbeError("Could not open the loopback DevTools WebSocket.") from exc

    key = base64.b64encode(os.urandom(16)).decode("ascii")
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{debug_port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("ascii")
    sock.sendall(request)

    response = bytearray()
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            sock.close()
            raise ProbeError("Chromium closed the WebSocket handshake unexpectedly.")
        response.extend(chunk)
        if len(response) > 64_000:
            sock.close()
            raise ProbeError("Chromium WebSocket handshake exceeded the size limit.")

    header_text = response.decode("latin-1", errors="strict")
    status_line, *header_lines = header_text.split("\r\n")
    if " 101 " not in status_line:
        sock.close()
        raise ProbeError(f"Chromium rejected the DevTools WebSocket handshake: {status_line}")
    headers: dict[str, str] = {}
    for line in header_lines:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    expected_accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    if headers.get("sec-websocket-accept") != expected_accept:
        sock.close()
        raise ProbeError("Chromium returned an invalid WebSocket accept key.")
    return WebSocketConnection(sock=sock)


def evaluate_probe(connection: WebSocketConnection) -> dict[str, object]:
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
            raise ProbeError("Chromium rejected the bounded Runtime.evaluate request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ProbeError("Chromium returned no Runtime.evaluate result.")
        if "exceptionDetails" in result:
            raise ProbeError("The bounded Plexamp runtime probe raised an exception.")
        remote = result.get("result")
        if not isinstance(remote, dict) or "value" not in remote:
            raise ProbeError("Chromium did not return the probe result by value.")
        value = remote.get("value")
        if not isinstance(value, dict):
            raise ProbeError("Plexamp runtime probe returned an unexpected result shape.")
        return value


def main() -> int:
    args = parse_args()
    try:
        port = require_safe_port(args.debug_port)
        timeout = require_safe_timeout(args.timeout)
        target = plexamp_target(fetch_targets(port, timeout))
        connection = connect_devtools(target, port, timeout)
        try:
            result = evaluate_probe(connection)
        finally:
            connection.close()
    except ProbeError as exc:
        print(f"Plexamp Home runtime probe: ERROR — {exc}", file=sys.stderr)
        return 1

    print("Plexamp Home runtime probe")
    print("READ-ONLY: names/shapes only; primitive values are not emitted; getters are not invoked.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
