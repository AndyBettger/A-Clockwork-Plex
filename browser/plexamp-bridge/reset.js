(() => {
  'use strict';

  const PLAN_REQUEST_TYPE = 'acp-plexamp-home-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-home-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-home-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-home-reset-apply-response-v1';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-home-reset-rollback-request-v1';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-home-reset-rollback-response-v1';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-home-reset-finalize-request-v1';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-home-reset-finalize-response-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const MMKV_PREFIX = 'mmkv.default\\';
  const VIEW_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):([A-Za-z0-9_.:/%+@~=\-]{1,600}):viewSettings$/;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_RECORDS = 256;
  const MAX_VIEW_BYTES = 16384;
  const MAX_TITLE_CHARS = 240;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;

  const rollbackSnapshots = new Map();

  function hash32(text) {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  }

  function randomToken() {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID().replaceAll('-', '').toLowerCase();
    }
    const bytes = new Uint32Array(4);
    globalThis.crypto?.getRandomValues?.(bytes);
    const token = Array.from(bytes, (value) => value.toString(16).padStart(8, '0')).join('');
    return SAFE_ROLLBACK_TOKEN.test(token)
      ? token
      : hash32(`${Date.now()}-${Math.random()}`).repeat(4);
  }

  function safeTitle(value) {
    if (typeof value !== 'string' || !value.length || value.length > MAX_TITLE_CHARS) return null;
    if (Array.from(value).some((char) => char.codePointAt(0) < 32)) return null;
    return value;
  }

  function decodedViewSettings(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_VIEW_BYTES) return null;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') return null;

    let codec = { kind: 'direct' };
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
      codec = { kind: 'wrapped', key: outerKeys[0] };
      value = parsed[outerKeys[0]];
    }

    const title = Object.prototype.hasOwnProperty.call(value, 'title')
      ? safeTitle(value.title)
      : null;
    if (Object.prototype.hasOwnProperty.call(value, 'title') && title === null) return null;

    const targetValue = title === null ? null : { title };
    let targetRaw = null;
    if (targetValue !== null) {
      targetRaw = codec.kind === 'wrapped'
        ? JSON.stringify({ [codec.key]: targetValue })
        : JSON.stringify(targetValue);
    }
    return { targetRaw };
  }

  function collectInventory(storage) {
    const records = [];
    const contexts = new Set();
    const length = Math.min(Number(storage?.length || 0), MAX_STORAGE_KEYS);
    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX)) continue;
      const suffix = key.slice(MMKV_PREFIX.length);
      const match = suffix.match(VIEW_RE);
      if (!match) continue;
      const raw = storage.getItem(key);
      if (typeof raw !== 'string') continue;
      const decoded = decodedViewSettings(raw);
      if (!decoded) {
        return { status: 'unsupported-view-settings-format', records: [], contextCount: 1 };
      }
      contexts.add(`${match[1]}\u0000${match[2]}`);
      if (decoded.targetRaw !== raw) {
        records.push({
          key,
          raw,
          targetRaw: decoded.targetRaw,
          hub: match[3],
        });
      }
    }
    if (contexts.size > 1) {
      return { status: 'ambiguous-context', records: [], contextCount: contexts.size };
    }
    if (records.length > MAX_RECORDS) {
      return { status: 'too-many-records', records: [], contextCount: contexts.size };
    }
    return { status: 'ready', records, contextCount: contexts.size };
  }

  function fingerprint(records) {
    return hash32(JSON.stringify(records
      .map((record) => [record.key, record.raw, record.targetRaw])
      .sort(([left], [right]) => left.localeCompare(right))));
  }

  function buildResetPlan(storage) {
    const inventory = collectInventory(storage);
    if (inventory.status !== 'ready') {
      const publicPlan = {
        schema_version: 1,
        status: inventory.status,
        read_only: true,
        reset_available: false,
      };
      if (inventory.contextCount > 1) publicPlan.context_count = inventory.contextCount;
      return { public: publicPlan, records: [], fingerprint: null };
    }

    const records = inventory.records;
    const targetFingerprint = fingerprint(records);
    return {
      public: {
        schema_version: 1,
        status: 'ready',
        read_only: true,
        reset_available: records.length > 0,
        change_count: records.length,
        view_settings_record_count: records.length,
        target_fingerprint: targetFingerprint,
      },
      records,
      fingerprint: targetFingerprint,
    };
  }

  function planHomeReset(storage) {
    return buildResetPlan(storage).public;
  }

  function verifyTargets(storage, records) {
    return records.every((record) => (
      record.targetRaw === null
        ? storage.getItem(record.key) === null
        : storage.getItem(record.key) === record.targetRaw
    ));
  }

  function restoreRecords(storage, records) {
    for (const record of records) storage.setItem(record.key, record.raw);
    return records.every((record) => storage.getItem(record.key) === record.raw);
  }

  function applyHomeReset(storage, expectedFingerprint, confirmReset = false) {
    if (confirmReset !== true) {
      return {
        schema_version: 1,
        status: 'confirmation-required',
        applied: false,
        rolled_back: false,
      };
    }
    if (typeof expectedFingerprint !== 'string' || !SAFE_FINGERPRINT.test(expectedFingerprint)) {
      return {
        schema_version: 1,
        status: 'invalid-fingerprint',
        applied: false,
        rolled_back: false,
      };
    }

    const plan = buildResetPlan(storage);
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
    if (!plan.public.reset_available) {
      return {
        schema_version: 1,
        status: 'no-change',
        applied: false,
        rolled_back: false,
        applied_change_count: 0,
      };
    }

    const records = plan.records.map((record) => ({ ...record }));
    const touched = [];
    try {
      for (const record of records) {
        if (record.targetRaw === null) storage.removeItem(record.key);
        else storage.setItem(record.key, record.targetRaw);
        touched.push(record);
      }
      if (!verifyTargets(storage, records)) throw new Error('verification');
      const verified = buildResetPlan(storage);
      if (verified.public.status !== 'ready' || verified.public.reset_available) {
        throw new Error('verification');
      }

      const rollbackToken = randomToken();
      rollbackSnapshots.set(rollbackToken, { storage, records });
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: plan.public.change_count,
        view_settings_record_count: plan.public.view_settings_record_count,
        target_fingerprint: verified.fingerprint,
        rollback_token: rollbackToken,
      };
    } catch (_error) {
      let rollbackFailureCount = 0;
      try {
        if (!restoreRecords(storage, touched)) rollbackFailureCount += 1;
      } catch (_rollbackError) {
        rollbackFailureCount += 1;
      }
      return {
        schema_version: 1,
        status: 'apply-failed',
        applied: false,
        rolled_back: rollbackFailureCount === 0,
        rollback_failure_count: rollbackFailureCount,
        fresh_preview_required: true,
      };
    }
  }

  function rollbackHomeReset(rollbackToken, confirmRollback = false) {
    if (
      confirmRollback !== true
      || typeof rollbackToken !== 'string'
      || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)
    ) {
      return {
        schema_version: 1,
        status: 'invalid-request',
        rolled_back: false,
        verified: false,
      };
    }

    const entry = rollbackSnapshots.get(rollbackToken);
    if (!entry) {
      return {
        schema_version: 1,
        status: 'rollback-unavailable',
        rolled_back: false,
        verified: false,
      };
    }

    try {
      const verified = restoreRecords(entry.storage, entry.records);
      if (!verified) {
        return {
          schema_version: 1,
          status: 'rollback-failed',
          rolled_back: false,
          verified: false,
        };
      }
      rollbackSnapshots.delete(rollbackToken);
      return {
        schema_version: 1,
        status: 'rolled-back',
        rolled_back: true,
        verified: true,
      };
    } catch (_error) {
      return {
        schema_version: 1,
        status: 'rollback-failed',
        rolled_back: false,
        verified: false,
      };
    }
  }

  function finalizeHomeReset(rollbackToken) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return { schema_version: 1, status: 'invalid-request', finalized: false };
    }
    const existed = rollbackSnapshots.delete(rollbackToken);
    return {
      schema_version: 1,
      status: existed ? 'finalized' : 'rollback-unavailable',
      finalized: existed,
    };
  }

  function install(win, storage) {
    if (!win?.addEventListener || !storage) return;

    win.addEventListener('message', (event) => {
      if (event.source !== win.parent) return;
      if (!DASHBOARD_ORIGINS.has(event.origin)) return;
      const request = event.data;
      if (!request || typeof request.type !== 'string') return;
      if (
        typeof request.nonce !== 'string'
        || request.nonce.length < 8
        || request.nonce.length > 128
      ) return;

      let responseType = null;
      let result = null;
      try {
        if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = planHomeReset(storage);
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = applyHomeReset(
            storage,
            request.target_fingerprint,
            request.confirm_reset === true,
          );
        } else if (request.type === ROLLBACK_REQUEST_TYPE) {
          responseType = ROLLBACK_RESPONSE_TYPE;
          result = rollbackHomeReset(
            request.rollback_token,
            request.confirm_rollback === true,
          );
        } else if (request.type === FINALIZE_REQUEST_TYPE) {
          responseType = FINALIZE_RESPONSE_TYPE;
          result = finalizeHomeReset(request.rollback_token);
        }
      } catch (_error) {
        if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = {
            schema_version: 1,
            status: 'unavailable',
            read_only: true,
            reset_available: false,
          };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = {
            schema_version: 1,
            status: 'unavailable',
            applied: false,
            rolled_back: false,
          };
        } else if (request.type === ROLLBACK_REQUEST_TYPE) {
          responseType = ROLLBACK_RESPONSE_TYPE;
          result = {
            schema_version: 1,
            status: 'unavailable',
            rolled_back: false,
            verified: false,
          };
        } else if (request.type === FINALIZE_REQUEST_TYPE) {
          responseType = FINALIZE_RESPONSE_TYPE;
          result = {
            schema_version: 1,
            status: 'unavailable',
            finalized: false,
          };
        }
      }

      if (!responseType || !result) return;
      win.parent.postMessage(
        { type: responseType, nonce: request.nonce, result },
        event.origin,
      );
    });
  }

  function installNativeResetBridge(doc) {
    if (!doc?.documentElement) return;
    if (typeof chrome === 'undefined' || typeof chrome.runtime?.getURL !== 'function') return;
    if (doc.getElementById('acp-plexamp-native-reset-bridge')) return;

    const script = doc.createElement('script');
    script.id = 'acp-plexamp-native-reset-bridge';
    script.src = chrome.runtime.getURL('native-reset.js');
    script.async = false;
    const cleanup = () => script.remove();
    script.addEventListener('load', cleanup, { once: true });
    script.addEventListener('error', cleanup, { once: true });
    (doc.head || doc.documentElement).append(script);
  }

  const api = {
    applyHomeReset,
    finalizeHomeReset,
    planHomeReset,
    rollbackHomeReset,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    install(window, localStorage);
  }
  if (typeof document !== 'undefined') installNativeResetBridge(document);
})();