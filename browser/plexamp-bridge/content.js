(() => {
  'use strict';

  const REQUEST_TYPE = 'acp-plexamp-browser-preferences-request-v1';
  const RESPONSE_TYPE = 'acp-plexamp-browser-preferences-response-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SAFE_HUB_ID = /^[A-Za-z0-9_.-]{1,220}$/;
  const SAFE_SHAPE_KEY = /^[A-Za-z][A-Za-z0-9_.-]{0,31}$/;
  const ORDER_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):order$/;
  const HIDDEN_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):([A-Za-z0-9_.-]{1,220}):hidden$/;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_ORDER_BYTES = 16384;
  const MAX_ORDER_ITEMS = 128;

  function nestedShape(value) {
    if (value === null) return 'jnull';
    if (Array.isArray(value)) {
      const count = Math.min(value.length, 999);
      if (value.every((item) => typeof item === 'string')) return `jarr${count}s`;
      if (value.every((item) => typeof item === 'boolean')) return `jarr${count}b`;
      if (value.every((item) => typeof item === 'number')) return `jarr${count}n`;
      return `jarr${count}m`;
    }
    if (typeof value === 'object') {
      return `jobj${Math.min(Object.keys(value).length, 999)}`;
    }
    if (typeof value === 'string') return `jstr${Math.min(value.length, 99999)}`;
    if (typeof value === 'boolean') return 'jbool';
    if (typeof value === 'number') return 'jnum';
    return 'jother';
  }

  function shapeKey(key) {
    if (typeof key !== 'string') return 'key';
    if (SAFE_SHAPE_KEY.test(key)) return key;
    return `keylen${Math.min(key.length, 999)}`;
  }

  function shapeToken(raw) {
    if (typeof raw !== 'string') return 'nonstring';
    const chars = Math.min(raw.length, 99999);
    if (raw === 'true' || raw === 'false') return `bplain${chars}`;
    if (/^B(?:true|false)$/.test(raw)) return `btyped${chars}`;
    if (/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(raw)) return `num${chars}`;

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return `opaque${chars}`;
    }

    if (parsed === null) return `jnull${chars}`;
    if (Array.isArray(parsed)) {
      return `${nestedShape(parsed)}x${chars}`;
    }
    if (typeof parsed === 'object') {
      const keys = Object.keys(parsed);
      const shown = keys.slice(0, 4).map(
        (key) => `${shapeKey(key)}-${nestedShape(parsed[key])}`,
      );
      const suffix = keys.length > shown.length ? '-more' : '';
      return `jobj${Math.min(keys.length, 999)}-${shown.join('-')}${suffix}-x${chars}`;
    }
    if (typeof parsed === 'string') {
      return `jstr${Math.min(parsed.length, 99999)}x${chars}`;
    }
    if (typeof parsed === 'boolean') return `jbool${chars}`;
    if (typeof parsed === 'number') return `jnum${chars}`;
    return `json${chars}`;
  }

  function readEntries(storage) {
    const entries = [];
    const length = Math.min(Number(storage?.length || 0), MAX_STORAGE_KEYS);
    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX)) continue;
      const suffix = key.slice(MMKV_PREFIX.length);
      if (!suffix.startsWith(CUSTOM_PREFIX)) continue;

      const orderMatch = suffix.match(ORDER_RE);
      const hiddenMatch = suffix.match(HIDDEN_RE);
      if (!orderMatch && !hiddenMatch) continue;

      const value = storage.getItem(key);
      if (typeof value !== 'string') continue;
      entries.push({ orderMatch, hiddenMatch, value });
    }
    return entries;
  }

  function parseOrder(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_ORDER_BYTES) return null;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (!Array.isArray(parsed) || parsed.length > MAX_ORDER_ITEMS) return null;
    const order = [];
    for (const item of parsed) {
      if (typeof item !== 'string' || !SAFE_HUB_ID.test(item)) return null;
      order.push(item);
    }
    return order;
  }

  function scopeId(context, section) {
    return `${context}\u0000${section}`;
  }

  function buildSnapshot(storage) {
    const scopes = new Map();

    for (const entry of readEntries(storage)) {
      const { orderMatch, hiddenMatch, value } = entry;
      if (orderMatch) {
        const id = scopeId(orderMatch[1], orderMatch[2]);
        const scope = scopes.get(id) || {
          orderRaw: null,
          hidden: new Set(),
          invalidHiddenShape: null,
        };
        scope.orderRaw = value;
        scopes.set(id, scope);
        continue;
      }

      if (hiddenMatch) {
        const id = scopeId(hiddenMatch[1], hiddenMatch[2]);
        const scope = scopes.get(id) || {
          orderRaw: null,
          hidden: new Set(),
          invalidHiddenShape: null,
        };
        if (value === 'true') {
          scope.hidden.add(hiddenMatch[3]);
        } else if (value !== 'false' && scope.invalidHiddenShape === null) {
          scope.invalidHiddenShape = shapeToken(value);
        }
        scopes.set(id, scope);
      }
    }

    if (scopes.size === 0) {
      return {
        schema_version: 1,
        status: 'empty',
        home: { order: null, hidden: [] },
      };
    }
    if (scopes.size !== 1) {
      return {
        schema_version: 1,
        status: 'ambiguous-context',
        context_count: scopes.size,
      };
    }

    const scope = Array.from(scopes.values())[0];
    if (scope.invalidHiddenShape !== null) {
      const orderShape = scope.orderRaw === null ? 'none' : shapeToken(scope.orderRaw);
      return {
        schema_version: 1,
        status: `unsupported-hidden-format-${scope.invalidHiddenShape}-order-${orderShape}`,
      };
    }

    let order = null;
    if (scope.orderRaw !== null) {
      order = parseOrder(scope.orderRaw);
      if (order === null) {
        return {
          schema_version: 1,
          status: `unsupported-order-format-${shapeToken(scope.orderRaw)}`,
        };
      }
    }

    return {
      schema_version: 1,
      status: 'ready',
      home: {
        order,
        hidden: Array.from(scope.hidden).sort((a, b) => a.localeCompare(b)),
      },
    };
  }

  function install(win, storage) {
    if (!win?.addEventListener || !storage) return;
    win.addEventListener('message', (event) => {
      if (event.source !== win.parent) return;
      if (!DASHBOARD_ORIGINS.has(event.origin)) return;
      const request = event.data;
      if (!request || request.type !== REQUEST_TYPE) return;
      if (typeof request.nonce !== 'string' || request.nonce.length < 8 || request.nonce.length > 128) return;

      let snapshot;
      try {
        snapshot = buildSnapshot(storage);
      } catch (_error) {
        snapshot = { schema_version: 1, status: 'unavailable' };
      }
      win.parent.postMessage(
        {
          type: RESPONSE_TYPE,
          nonce: request.nonce,
          snapshot,
        },
        event.origin,
      );
    });
  }

  const api = { buildSnapshot, parseOrder, shapeToken };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    install(window, localStorage);
  }
})();
