(() => {
  'use strict';

  const REQUEST_TYPE = 'acp-plexamp-browser-preferences-request-v1';
  const RESPONSE_TYPE = 'acp-plexamp-browser-preferences-response-v1';
  const PLAN_REQUEST_TYPE = 'acp-plexamp-browser-home-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-browser-home-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-browser-home-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-browser-home-apply-response-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SAFE_HUB_ID = /^[A-Za-z0-9_.\/-]{1,220}$/;
  const SAFE_HUB_CHAR = /^[A-Za-z0-9_.\/-]$/;
  const SAFE_SHAPE_KEY = /^[A-Za-z][A-Za-z0-9_.-]{0,31}$/;
  const ORDER_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):order$/;
  const HIDDEN_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):([A-Za-z0-9_.\/-]{1,220}):hidden$/;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_ORDER_BYTES = 16384;
  const MAX_ORDER_ITEMS = 128;
  const MAX_HIDDEN_BYTES = 256;

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
      entries.push({ key, orderMatch, hiddenMatch, value });
    }
    return entries;
  }

  function unwrapSingleProperty(raw) {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return { ok: false, key: null, value: null };
    }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      return { ok: false, key: null, value: null };
    }
    const keys = Object.keys(parsed);
    if (keys.length !== 1) return { ok: false, key: null, value: null };
    return { ok: true, key: keys[0], value: parsed[keys[0]] };
  }

  function extractOrderCandidate(raw) {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === 'object') {
      const keys = Object.keys(parsed);
      if (keys.length === 1) return parsed[keys[0]];
    }
    return null;
  }

  function validateOrderList(value) {
    if (!Array.isArray(value) || value.length > MAX_ORDER_ITEMS) return null;
    const order = [];
    const seen = new Set();
    for (const item of value) {
      if (typeof item !== 'string' || !SAFE_HUB_ID.test(item) || seen.has(item)) return null;
      seen.add(item);
      order.push(item);
    }
    return order;
  }

  function validateHiddenList(value) {
    if (!Array.isArray(value) || value.length > MAX_ORDER_ITEMS) return null;
    const hidden = [];
    const seen = new Set();
    for (const item of value) {
      if (typeof item !== 'string' || !SAFE_HUB_ID.test(item) || seen.has(item)) return null;
      seen.add(item);
      hidden.push(item);
    }
    return hidden;
  }

  function orderListDiagnostic(raw) {
    const candidate = extractOrderCandidate(raw);
    if (!Array.isArray(candidate)) return shapeToken(raw);

    let maxLength = 0;
    let empty = 0;
    let over = 0;
    let nonString = 0;
    const badCodes = new Set();

    for (const item of candidate) {
      if (typeof item !== 'string') {
        nonString += 1;
        continue;
      }
      maxLength = Math.max(maxLength, item.length);
      if (item.length === 0) empty += 1;
      if (item.length > 220) over += 1;
      for (const char of item) {
        if (SAFE_HUB_CHAR.test(char)) continue;
        if (badCodes.size >= 6) continue;
        badCodes.add(char.codePointAt(0).toString(16));
      }
    }

    const bad = Array.from(badCodes).sort().join('.') || 'none';
    return [
      `items${Math.min(candidate.length, 999)}`,
      `max${Math.min(maxLength, 9999)}`,
      `empty${Math.min(empty, 999)}`,
      `over${Math.min(over, 999)}`,
      `nonstring${Math.min(nonString, 999)}`,
      `bad${bad}`,
    ].join('-');
  }

  function parseOrder(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_ORDER_BYTES) return null;
    return validateOrderList(extractOrderCandidate(raw));
  }

  function parseHidden(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_HIDDEN_BYTES) return null;
    if (raw === 'true' || raw === 'Btrue') return true;
    if (raw === 'false' || raw === 'Bfalse') return false;

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (typeof parsed === 'boolean') return parsed;

    const wrapped = unwrapSingleProperty(raw);
    if (wrapped.ok && typeof wrapped.value === 'boolean') return wrapped.value;
    return null;
  }

  function orderCodec(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_ORDER_BYTES) return null;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (Array.isArray(parsed)) return { kind: 'array' };
    const wrapped = unwrapSingleProperty(raw);
    if (
      wrapped.ok
      && typeof wrapped.key === 'string'
      && wrapped.key.length <= 32
      && Array.isArray(wrapped.value)
    ) {
      return { kind: 'wrapped', key: wrapped.key };
    }
    return null;
  }

  function hiddenCodec(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_HIDDEN_BYTES) return null;
    if (raw === 'true' || raw === 'false') return { kind: 'plain' };
    if (raw === 'Btrue' || raw === 'Bfalse') return { kind: 'typed' };
    const wrapped = unwrapSingleProperty(raw);
    if (
      wrapped.ok
      && typeof wrapped.key === 'string'
      && wrapped.key.length <= 32
      && typeof wrapped.value === 'boolean'
    ) {
      return { kind: 'wrapped', key: wrapped.key };
    }
    return null;
  }

  function encodeOrder(codec, value) {
    if (!codec || !Array.isArray(value)) return null;
    if (codec.kind === 'array') return JSON.stringify(value);
    if (codec.kind === 'wrapped') return JSON.stringify({ [codec.key]: value });
    return null;
  }

  function encodeHidden(codec, value) {
    if (!codec || typeof value !== 'boolean') return null;
    if (codec.kind === 'plain') return value ? 'true' : 'false';
    if (codec.kind === 'typed') return value ? 'Btrue' : 'Bfalse';
    if (codec.kind === 'wrapped') return JSON.stringify({ [codec.key]: value });
    return null;
  }

  function scopeId(context, section) {
    return `${context}\u0000${section}`;
  }

  function collectScopes(storage) {
    const scopes = new Map();
    for (const entry of readEntries(storage)) {
      const { key, orderMatch, hiddenMatch, value } = entry;
      const match = orderMatch || hiddenMatch;
      const id = scopeId(match[1], match[2]);
      const scope = scopes.get(id) || {
        context: match[1],
        section: match[2],
        orderKey: null,
        orderRaw: null,
        hiddenRecords: new Map(),
      };
      if (orderMatch) {
        scope.orderKey = key;
        scope.orderRaw = value;
      } else {
        scope.hiddenRecords.set(hiddenMatch[3], {
          key,
          raw: value,
          value: parseHidden(value),
          codec: hiddenCodec(value),
        });
      }
      scopes.set(id, scope);
    }
    return scopes;
  }

  function inspectSingleScope(storage) {
    const scopes = collectScopes(storage);
    if (scopes.size === 0) {
      return { ok: false, status: 'empty', scope: null, home: { order: null, hidden: [] } };
    }
    if (scopes.size !== 1) {
      return { ok: false, status: 'ambiguous-context', scope: null, contextCount: scopes.size };
    }

    const scope = Array.from(scopes.values())[0];
    for (const record of scope.hiddenRecords.values()) {
      if (record.value === null || record.codec === null) {
        const orderShape = scope.orderRaw === null ? 'none' : shapeToken(scope.orderRaw);
        return {
          ok: false,
          status: `unsupported-hidden-format-${shapeToken(record.raw)}-order-${orderShape}`,
          scope: null,
        };
      }
    }

    let order = null;
    if (scope.orderRaw !== null) {
      order = parseOrder(scope.orderRaw);
      if (order === null || orderCodec(scope.orderRaw) === null) {
        return {
          ok: false,
          status: `unsupported-order-format-${orderListDiagnostic(scope.orderRaw)}`,
          scope: null,
        };
      }
    }

    const hidden = [];
    const known = new Set(order || []);
    for (const [hubId, record] of scope.hiddenRecords.entries()) {
      known.add(hubId);
      if (record.value === true) hidden.push(hubId);
    }
    hidden.sort((a, b) => a.localeCompare(b));

    return {
      ok: true,
      status: 'ready',
      scope,
      known,
      home: { order, hidden },
    };
  }

  function buildSnapshot(storage) {
    const inspected = inspectSingleScope(storage);
    if (!inspected.ok) {
      if (inspected.status === 'empty') {
        return {
          schema_version: 1,
          status: 'empty',
          home: { order: null, hidden: [] },
        };
      }
      const result = { schema_version: 1, status: inspected.status };
      if (typeof inspected.contextCount === 'number') result.context_count = inspected.contextCount;
      return result;
    }

    return {
      schema_version: 1,
      status: 'ready',
      home: {
        order: inspected.home.order === null ? null : Array.from(inspected.home.order),
        hidden: Array.from(inspected.home.hidden),
      },
    };
  }

  function validateDesiredHome(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    const keys = Object.keys(value);
    if (keys.some((key) => key !== 'order' && key !== 'hidden')) return null;
    const order = value.order === null ? null : validateOrderList(value.order);
    if (value.order !== null && order === null) return null;
    const hidden = validateHiddenList(value.hidden || []);
    if (hidden === null) return null;
    return { order, hidden };
  }

  function sameList(left, right) {
    if (left === null || right === null) return left === right;
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return false;
    return left.every((value, index) => value === right[index]);
  }

  function hash32(text) {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  }

  function preferredOrderCodec(scope) {
    if (scope.orderRaw !== null) return orderCodec(scope.orderRaw);
    for (const record of scope.hiddenRecords.values()) {
      if (record.codec?.kind === 'wrapped') {
        return { kind: 'wrapped', key: record.codec.key };
      }
    }
    if (scope.hiddenRecords.size > 0) return { kind: 'array' };
    return null;
  }

  function preferredHiddenCodec(scope) {
    for (const record of scope.hiddenRecords.values()) {
      if (record.codec) return { ...record.codec };
    }
    const codec = preferredOrderCodec(scope);
    if (codec?.kind === 'wrapped') return { kind: 'wrapped', key: codec.key };
    if (codec?.kind === 'array') return { kind: 'plain' };
    return null;
  }

  function targetFingerprint(inspected) {
    const scope = inspected.scope;
    const known = Array.from(inspected.known || []).sort((a, b) => a.localeCompare(b));
    const hiddenShapes = Array.from(scope.hiddenRecords.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([hubId, record]) => [hubId, record.codec?.kind || 'invalid', record.codec?.key || null]);
    return hash32(JSON.stringify({
      home: inspected.home,
      known,
      orderShape: scope.orderRaw === null ? null : orderCodec(scope.orderRaw),
      hiddenShapes,
    }));
  }

  function buildHomePlan(storage, requestedHome) {
    const desired = validateDesiredHome(requestedHome);
    if (desired === null) {
      return { public: { schema_version: 1, status: 'invalid-request', read_only: true, restore_available: false } };
    }

    const inspected = inspectSingleScope(storage);
    if (!inspected.ok) {
      return {
        public: {
          schema_version: 1,
          status: inspected.status === 'empty' ? 'target-context-unavailable' : inspected.status,
          read_only: true,
          restore_available: false,
        },
      };
    }

    const { scope, known, home: current } = inspected;
    const desiredUniverse = new Set([...(desired.order || []), ...desired.hidden]);
    const missing = Array.from(desiredUniverse).filter((hubId) => !known.has(hubId));
    const targetOnly = Array.from(known).filter((hubId) => !desiredUniverse.has(hubId));

    let effectiveOrder = null;
    let orderReady = true;
    if (desired.order !== null) {
      if (current.order === null) {
        orderReady = false;
      } else {
        const desiredKnown = desired.order.filter((hubId) => known.has(hubId));
        const desiredKnownSet = new Set(desiredKnown);
        const retained = current.order.filter((hubId) => !desiredKnownSet.has(hubId));
        effectiveOrder = [...desiredKnown, ...retained];
      }
    }

    const currentHidden = new Set(current.hidden);
    const desiredHidden = new Set(desired.hidden);
    const effectiveHidden = new Set(current.hidden);
    for (const hubId of desiredUniverse) {
      if (!known.has(hubId)) continue;
      if (desiredHidden.has(hubId)) effectiveHidden.add(hubId);
      else effectiveHidden.delete(hubId);
    }
    const effectiveHiddenList = Array.from(effectiveHidden).sort((a, b) => a.localeCompare(b));

    const orderChanged = orderReady && !sameList(current.order, desired.order === null ? null : effectiveOrder);
    const hiddenChanged = Array.from(new Set([...currentHidden, ...effectiveHidden]))
      .filter((hubId) => currentHidden.has(hubId) !== effectiveHidden.has(hubId))
      .sort((a, b) => a.localeCompare(b));

    let formatReady = true;
    if (orderChanged && desired.order !== null && preferredOrderCodec(scope) === null) formatReady = false;
    if (hiddenChanged.some((hubId) => !scope.hiddenRecords.has(hubId)) && preferredHiddenCodec(scope) === null) {
      formatReady = false;
    }

    const status = !orderReady
      ? 'target-order-unavailable'
      : (!formatReady ? 'target-format-unavailable' : 'ready');
    const changeCount = status === 'ready' ? Number(orderChanged) + hiddenChanged.length : 0;
    const fingerprint = targetFingerprint(inspected);

    return {
      public: {
        schema_version: 1,
        status,
        read_only: true,
        restore_available: status === 'ready' && changeCount > 0,
        change_count: changeCount,
        order_changed: status === 'ready' && orderChanged,
        hidden_change_count: status === 'ready' ? hiddenChanged.length : 0,
        missing_item_count: missing.length,
        target_only_item_count: targetOnly.length,
        target_known_item_count: known.size,
        target_fingerprint: fingerprint,
      },
      desired,
      inspected,
      effective: {
        order: desired.order === null ? null : effectiveOrder,
        hidden: effectiveHiddenList,
      },
      orderChanged,
      hiddenChanged,
      fingerprint,
    };
  }

  function planHome(storage, requestedHome) {
    return buildHomePlan(storage, requestedHome).public;
  }

  function orderKeyForScope(scope) {
    return scope.orderKey || `${MMKV_PREFIX}${CUSTOM_PREFIX}${scope.context}::/library/sections/${scope.section}:order`;
  }

  function hiddenKeyForScope(scope, hubId) {
    return `${MMKV_PREFIX}${CUSTOM_PREFIX}${scope.context}::/library/sections/${scope.section}:${hubId}:hidden`;
  }

  function buildMutations(plan) {
    const mutations = [];
    const { scope } = plan.inspected;

    if (plan.orderChanged) {
      const key = orderKeyForScope(scope);
      const before = storageValue(scope.orderRaw);
      if (plan.effective.order === null) {
        mutations.push({ key, before, after: { present: false, value: null } });
      } else {
        const encoded = encodeOrder(preferredOrderCodec(scope), plan.effective.order);
        if (encoded === null) throw new Error('order-format');
        mutations.push({ key, before, after: { present: true, value: encoded } });
      }
    }

    const defaultHiddenCodec = preferredHiddenCodec(scope);
    const effectiveHidden = new Set(plan.effective.hidden);
    for (const hubId of plan.hiddenChanged) {
      const existing = scope.hiddenRecords.get(hubId) || null;
      const codec = existing?.codec || defaultHiddenCodec;
      const encoded = encodeHidden(codec, effectiveHidden.has(hubId));
      if (encoded === null) throw new Error('hidden-format');
      mutations.push({
        key: existing?.key || hiddenKeyForScope(scope, hubId),
        before: storageValue(existing?.raw ?? null),
        after: { present: true, value: encoded },
      });
    }

    return mutations;
  }

  function storageValue(raw) {
    return typeof raw === 'string'
      ? { present: true, value: raw }
      : { present: false, value: null };
  }

  function writeStorage(storage, mutation, useBefore = false) {
    const state = useBefore ? mutation.before : mutation.after;
    if (state.present) storage.setItem(mutation.key, state.value);
    else storage.removeItem(mutation.key);
  }

  function verifyRawRollback(storage, mutations) {
    for (const mutation of mutations) {
      const actual = storage.getItem(mutation.key);
      if (mutation.before.present) {
        if (actual !== mutation.before.value) return false;
      } else if (actual !== null) {
        return false;
      }
    }
    return true;
  }

  function applyHome(storage, requestedHome, expectedFingerprint, confirmRestore = false) {
    if (confirmRestore !== true) {
      return {
        schema_version: 1,
        status: 'confirmation-required',
        applied: false,
        rolled_back: false,
      };
    }
    if (typeof expectedFingerprint !== 'string' || !/^[a-f0-9]{8}$/.test(expectedFingerprint)) {
      return {
        schema_version: 1,
        status: 'invalid-fingerprint',
        applied: false,
        rolled_back: false,
      };
    }

    const plan = buildHomePlan(storage, requestedHome);
    if (plan.public.status !== 'ready') {
      return {
        schema_version: 1,
        status: plan.public.status,
        applied: false,
        rolled_back: false,
      };
    }
    if (plan.fingerprint !== expectedFingerprint) {
      return {
        schema_version: 1,
        status: 'stale-target',
        applied: false,
        rolled_back: false,
        fresh_preview_required: true,
      };
    }
    if (!plan.public.restore_available) {
      return {
        schema_version: 1,
        status: 'no-change',
        applied: false,
        rolled_back: false,
        applied_change_count: 0,
      };
    }

    let mutations = [];
    try {
      mutations = buildMutations(plan);
      for (const mutation of mutations) writeStorage(storage, mutation, false);
      const verified = buildHomePlan(storage, requestedHome);
      if (verified.public.status !== 'ready' || verified.public.restore_available) {
        throw new Error('verification');
      }
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: plan.public.change_count,
        missing_item_count: plan.public.missing_item_count,
        target_only_item_count: plan.public.target_only_item_count,
        target_fingerprint: verified.fingerprint,
      };
    } catch (_error) {
      let rollbackFailures = 0;
      for (const mutation of [...mutations].reverse()) {
        try {
          writeStorage(storage, mutation, true);
        } catch (_rollbackError) {
          rollbackFailures += 1;
        }
      }
      try {
        if (!verifyRawRollback(storage, mutations)) rollbackFailures += 1;
      } catch (_verificationError) {
        rollbackFailures += 1;
      }
      return {
        schema_version: 1,
        status: 'apply-failed',
        applied: false,
        rolled_back: rollbackFailures === 0,
        rollback_failure_count: rollbackFailures,
        fresh_preview_required: true,
      };
    }
  }

  function install(win, storage) {
    if (!win?.addEventListener || !storage) return;
    win.addEventListener('message', (event) => {
      if (event.source !== win.parent) return;
      if (!DASHBOARD_ORIGINS.has(event.origin)) return;
      const request = event.data;
      if (!request || typeof request.type !== 'string') return;
      if (typeof request.nonce !== 'string' || request.nonce.length < 8 || request.nonce.length > 128) return;

      let responseType = null;
      let result = null;
      try {
        if (request.type === REQUEST_TYPE) {
          responseType = RESPONSE_TYPE;
          result = buildSnapshot(storage);
        } else if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = planHome(storage, request.home);
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = applyHome(
            storage,
            request.home,
            request.target_fingerprint,
            request.confirm_restore === true,
          );
        }
      } catch (_error) {
        if (request.type === REQUEST_TYPE) {
          responseType = RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable' };
        } else if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', read_only: true, restore_available: false };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', applied: false, rolled_back: false };
        }
      }
      if (!responseType || !result) return;
      win.parent.postMessage(
        {
          type: responseType,
          nonce: request.nonce,
          result,
          snapshot: request.type === REQUEST_TYPE ? result : undefined,
        },
        event.origin,
      );
    });
  }

  const api = {
    applyHome,
    buildSnapshot,
    orderListDiagnostic,
    parseHidden,
    parseOrder,
    planHome,
    shapeToken,
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    install(window, localStorage);
  }
})();
