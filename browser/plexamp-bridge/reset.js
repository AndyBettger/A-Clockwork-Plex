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
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const SECTION_MARKER = '::/library/sections/';
  const SAFE_IDENTIFIER = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_SECTION = /^[0-9]{1,10}$/;
  const SAFE_TERMINAL = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const DURABLE_FAMILIES = new Set(['order', 'hidden', 'viewSettings', 'customHubs']);
  const MAX_STORAGE_KEYS = 2048;
  const MAX_RECORDS = 256;
  const MAX_RECORD_BYTES = 32768;
  const MAX_TOTAL_BYTES = 262144;
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

  function classifySuffix(suffix) {
    if (typeof suffix !== 'string' || !suffix.startsWith(CUSTOM_PREFIX)) return null;
    const markerIndex = suffix.indexOf(SECTION_MARKER, CUSTOM_PREFIX.length);
    if (markerIndex < 0) {
      return { family: 'other', valid: false, context: null, section: null };
    }

    const context = suffix.slice(CUSTOM_PREFIX.length, markerIndex);
    const rest = suffix.slice(markerIndex + SECTION_MARKER.length);
    const colonIndex = rest.indexOf(':');
    if (!SAFE_IDENTIFIER.test(context) || colonIndex < 1) {
      return { family: 'other', valid: false, context: null, section: null };
    }

    const section = rest.slice(0, colonIndex);
    const tail = rest.slice(colonIndex + 1);
    if (!SAFE_SECTION.test(section) || !tail) {
      return { family: 'other', valid: false, context: null, section: null };
    }

    if (tail === 'order') return { family: 'order', valid: true, context, section };
    if (tail === 'customHubs') return { family: 'customHubs', valid: true, context, section };

    const finalColon = tail.lastIndexOf(':');
    if (finalColon < 1) {
      return {
        family: 'other',
        valid: SAFE_TERMINAL.test(tail) && !SENSITIVE_NAME.test(tail),
        context,
        section,
      };
    }

    const hub = tail.slice(0, finalColon);
    const terminal = tail.slice(finalColon + 1);
    if (!SAFE_IDENTIFIER.test(hub) || !SAFE_TERMINAL.test(terminal) || SENSITIVE_NAME.test(terminal)) {
      return { family: 'other', valid: false, context: null, section: null };
    }
    if (terminal === 'hidden') return { family: 'hidden', valid: true, context, section };
    if (terminal === 'viewSettings') return { family: 'viewSettings', valid: true, context, section };
    if (terminal === 'editing') return { family: 'editing', valid: true, context, section };
    return { family: 'other', valid: true, context, section };
  }

  function collectInventory(storage) {
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
    const records = [];
    let structurallyInvalid = 0;
    let totalBytes = 0;

    const length = Number(storage?.length || 0);
    if (!Number.isFinite(length) || length < 0 || length > MAX_STORAGE_KEYS) {
      return {
        status: 'storage-key-limit-exceeded',
        families,
        contexts,
        sections,
        records: [],
        structurallyInvalid,
        totalBytes,
        fingerprint: null,
      };
    }

    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX + CUSTOM_PREFIX)) continue;
      const suffix = key.slice(MMKV_PREFIX.length);
      const classified = classifySuffix(suffix);
      if (!classified) continue;

      families[classified.family] += 1;
      if (!classified.valid) structurallyInvalid += 1;
      if (classified.context) contexts.add(classified.context);
      if (classified.context && classified.section) {
        sections.add(`${classified.context}\u0000${classified.section}`);
      }

      if (!classified.valid || !DURABLE_FAMILIES.has(classified.family)) continue;
      if (records.length >= MAX_RECORDS) {
        return {
          status: 'record-limit-exceeded',
          families,
          contexts,
          sections,
          records: [],
          structurallyInvalid,
          totalBytes,
          fingerprint: null,
        };
      }

      const raw = storage.getItem(key);
      if (typeof raw !== 'string') {
        return {
          status: 'storage-value-unavailable',
          families,
          contexts,
          sections,
          records: [],
          structurallyInvalid,
          totalBytes,
          fingerprint: null,
        };
      }
      if (raw.length > MAX_RECORD_BYTES) {
        return {
          status: 'record-size-limit-exceeded',
          families,
          contexts,
          sections,
          records: [],
          structurallyInvalid,
          totalBytes,
          fingerprint: null,
        };
      }
      totalBytes += raw.length;
      if (totalBytes > MAX_TOTAL_BYTES) {
        return {
          status: 'total-size-limit-exceeded',
          families,
          contexts,
          sections,
          records: [],
          structurallyInvalid,
          totalBytes,
          fingerprint: null,
        };
      }
      records.push({ key, raw, family: classified.family });
    }

    records.sort((left, right) => left.key.localeCompare(right.key));
    let status = 'ready';
    if (structurallyInvalid > 0 || families.other > 0) status = 'unclassified-customization-keys';
    else if (families.editing > 0) status = 'editing-active';

    const fingerprint = hash32(JSON.stringify(records.map((record) => [record.key, record.raw])));
    return {
      status,
      families,
      contexts,
      sections,
      records,
      structurallyInvalid,
      totalBytes,
      fingerprint,
    };
  }

  function publicPlan(inventory) {
    const changeCount = inventory.status === 'ready' ? inventory.records.length : 0;
    return {
      schema_version: 1,
      status: inventory.status,
      read_only: true,
      reset_available: inventory.status === 'ready' && changeCount > 0,
      change_count: changeCount,
      home_record_count: changeCount,
      family_counts: { ...inventory.families },
      context_count: inventory.contexts.size,
      section_context_count: inventory.sections.size,
      structurally_invalid_count: inventory.structurallyInvalid,
      target_fingerprint: inventory.status === 'ready' ? inventory.fingerprint : null,
    };
  }

  function buildResetPlan(storage) {
    const inventory = collectInventory(storage);
    return {
      public: publicPlan(inventory),
      inventory,
      records: inventory.status === 'ready' ? inventory.records : [],
      fingerprint: inventory.status === 'ready' ? inventory.fingerprint : null,
    };
  }

  function planHomeReset(storage) {
    return buildResetPlan(storage).public;
  }

  function verifyRecordsAbsent(storage, records) {
    return records.every((record) => storage.getItem(record.key) === null);
  }

  function verifyRecordsExact(storage, records) {
    return records.every((record) => storage.getItem(record.key) === record.raw);
  }

  function restoreExactIntoEmpty(storage, records, expectedFingerprint) {
    const current = collectInventory(storage);
    if (
      current.status !== 'ready'
      || current.records.length !== 0
      || current.families.editing !== 0
      || current.families.other !== 0
      || current.structurallyInvalid !== 0
    ) {
      return { ok: false, status: 'rollback-target-not-empty' };
    }

    const touched = [];
    try {
      for (const record of records) {
        storage.setItem(record.key, record.raw);
        touched.push(record);
      }
      if (!verifyRecordsExact(storage, records)) throw new Error('verification');
      const after = collectInventory(storage);
      if (after.status !== 'ready' || after.fingerprint !== expectedFingerprint) {
        throw new Error('verification');
      }
      return { ok: true, status: 'rolled-back' };
    } catch (_error) {
      let cleaned = true;
      for (const record of touched) {
        try {
          storage.removeItem(record.key);
        } catch (_removeError) {
          cleaned = false;
        }
      }
      if (cleaned) cleaned = verifyRecordsAbsent(storage, touched);
      return { ok: false, status: cleaned ? 'rollback-failed' : 'rollback-cleanup-failed' };
    }
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
        storage.removeItem(record.key);
        touched.push(record);
      }
      if (!verifyRecordsAbsent(storage, records)) throw new Error('verification');

      const after = collectInventory(storage);
      if (
        after.status !== 'ready'
        || after.records.length !== 0
        || after.contexts.size !== 0
        || after.sections.size !== 0
        || Object.values(after.families).some((count) => count !== 0)
      ) {
        throw new Error('verification');
      }

      const rollbackToken = randomToken();
      rollbackSnapshots.set(rollbackToken, {
        storage,
        records,
        fingerprint: plan.fingerprint,
      });
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: records.length,
        home_record_count: records.length,
        family_counts: { ...plan.inventory.families },
        target_fingerprint: after.fingerprint,
        rollback_token: rollbackToken,
      };
    } catch (_error) {
      let rollbackFailureCount = 0;
      try {
        for (const record of touched) storage.setItem(record.key, record.raw);
        if (!verifyRecordsExact(storage, records)) rollbackFailureCount += 1;
        const restored = collectInventory(storage);
        if (restored.status !== 'ready' || restored.fingerprint !== plan.fingerprint) {
          rollbackFailureCount += 1;
        }
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

    const restored = restoreExactIntoEmpty(entry.storage, entry.records, entry.fingerprint);
    if (!restored.ok) {
      return {
        schema_version: 1,
        status: restored.status,
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
      restored_record_count: entry.records.length,
      target_fingerprint: entry.fingerprint,
    };
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
