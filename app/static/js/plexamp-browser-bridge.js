(() => {
  'use strict';

  if (window.__aClockworkPlexBrowserPreferenceBridgeLoaded) return;
  window.__aClockworkPlexBrowserPreferenceBridgeLoaded = true;

  const REQUEST_TYPE = 'acp-plexamp-browser-preferences-request-v1';
  const RESPONSE_TYPE = 'acp-plexamp-browser-preferences-response-v1';
  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_HUB_ID = /^[A-Za-z0-9_.\/-]{1,220}$/;
  const MAX_ORDER_ITEMS = 128;
  const MAX_HIDDEN_ITEMS = 128;

  function validatedList(value, limit) {
    if (!Array.isArray(value) || value.length > limit) return null;
    const result = [];
    for (const item of value) {
      if (typeof item !== 'string' || !SAFE_HUB_ID.test(item)) return null;
      result.push(item);
    }
    return result;
  }

  function validateSnapshot(raw) {
    if (!raw || raw.schema_version !== 1 || typeof raw.status !== 'string') return null;
    if (raw.status === 'empty') {
      return { schema_version: 1, status: 'empty', home: { order: null, hidden: [] } };
    }
    if (raw.status !== 'ready') {
      return { schema_version: 1, status: raw.status };
    }

    const home = raw.home;
    if (!home || typeof home !== 'object') return null;
    let order = null;
    if (home.order !== null) {
      order = validatedList(home.order, MAX_ORDER_ITEMS);
      if (order === null) return null;
    }
    const hidden = validatedList(home.hidden, MAX_HIDDEN_ITEMS);
    if (hidden === null) return null;

    return {
      schema_version: 1,
      status: 'ready',
      home: { order, hidden },
    };
  }

  function nonce() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    const bytes = new Uint32Array(4);
    globalThis.crypto?.getRandomValues?.(bytes);
    return Array.from(bytes, (value) => value.toString(16).padStart(8, '0')).join('');
  }

  function snapshot(options = {}) {
    const frame = document.getElementById('persistent-plexamp-frame');
    if (!frame?.contentWindow) {
      return Promise.resolve({ schema_version: 1, status: 'frame-unavailable' });
    }

    let targetOrigin;
    try {
      targetOrigin = new URL(frame.src, window.location.href).origin;
    } catch (_error) {
      return Promise.resolve({ schema_version: 1, status: 'frame-origin-invalid' });
    }
    if (!ALLOWED_PLEXAMP_ORIGINS.has(targetOrigin)) {
      return Promise.resolve({ schema_version: 1, status: 'frame-origin-not-allowed' });
    }

    const requestNonce = nonce();
    const timeoutMs = Math.max(250, Math.min(4000, Number(options.timeoutMs || 1500)));

    return new Promise((resolve) => {
      let finished = false;
      const finish = (result) => {
        if (finished) return;
        finished = true;
        window.clearTimeout(timer);
        window.removeEventListener('message', onMessage);
        resolve(result);
      };
      const onMessage = (event) => {
        if (event.source !== frame.contentWindow || event.origin !== targetOrigin) return;
        const payload = event.data;
        if (!payload || payload.type !== RESPONSE_TYPE || payload.nonce !== requestNonce) return;
        const validated = validateSnapshot(payload.snapshot);
        finish(validated || { schema_version: 1, status: 'invalid-response' });
      };
      const timer = window.setTimeout(
        () => finish({ schema_version: 1, status: 'timeout' }),
        timeoutMs,
      );

      window.addEventListener('message', onMessage);
      frame.contentWindow.postMessage(
        { type: REQUEST_TYPE, nonce: requestNonce },
        targetOrigin,
      );
    });
  }

  window.ACPPlexampBrowserPreferences = { snapshot, validateSnapshot };
})();
