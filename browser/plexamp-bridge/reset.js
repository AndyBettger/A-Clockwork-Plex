(() => {
  'use strict';

  const PLAN_REQUEST_TYPE = 'acp-plexamp-home-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-home-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-home-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-home-reset-apply-response-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const ORDER_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):order$/;
  const HIDDEN_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):([A-Za-z0-9_.\/-]{1,220}):hidden$/;
  const BASELINE_CANDIDATE_RE = /^discovery:customizations:([A-Za-z0-9_-]{1,128})::\/library\/sections\/([0-9]{1,10}):c$/;
  const MAX_STORAGE_KEYS = 2048;
  const MAX_RECORDS = 129;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;

  function hash32(text) {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, '0');
  }

  function scopeId(context, section) {
    return `${context}\u0000${section}`;
  }

  function collectInventory(storage) {
    const scopes = new Map();
    const baselineCandidateScopes = new Set();
    let baselineCandidateRecordCount = 0;
    const length = Math.min(Number(storage?.length || 0), MAX_STORAGE_KEYS);
    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      if (typeof key !== 'string' || !key.startsWith(MMKV_PREFIX)) continue;
      const suffix = key.slice(MMKV_PREFIX.length);
      if (!suffix.startsWith(CUSTOM_PREFIX)) continue;

      const baselineCandidateMatch = suffix.match(BASELINE_CANDIDATE_RE);
      if (baselineCandidateMatch) {
        baselineCandidateRecordCount += 1;
        baselineCandidateScopes.add(scopeId(baselineCandidateMatch[1], baselineCandidateMatch[2]));
        // Deliberately name-only: never open the value of an unclassified :c record.
        continue;
      }

      const orderMatch = suffix.match(ORDER_RE);
      const hiddenMatch = suffix.match(HIDDEN_RE);
      const match = orderMatch || hiddenMatch;
      if (!match) continue;
      const raw = storage.getItem(key);
      if (typeof raw !== 'string') continue;
      const id = scopeId(match[1], match[2]);
      const scope = scopes.get(id) || {
        context: match[1],
        section: match[2],
        records: [],
      };
      scope.records.push({
        key,
        raw,
        kind: orderMatch ? 'order' : 'hidden',
      });
      scopes.set(id, scope);
    }
    return {
      scopes,
      baselineCandidateRecordCount,
      baselineCandidateScopeCount: baselineCandidateScopes.size,
    };
  }

  function recordFingerprint(scope) {
    if (!scope) return hash32(JSON.stringify({ scope: null, records: [] }));
    const records = scope.records
      .map((record) => [record.key, record.raw])
      .sort(([left], [right]) => left.localeCompare(right));
    return hash32(JSON.stringify({
      context: scope.context,
      section: scope.section,
      records,
    }));
  }

  function buildResetPlan(storage) {
    const inventory = collectInventory(storage);
    const { scopes } = inventory;
    const baselineDiagnostics = {
      baseline_candidate_record_count: inventory.baselineCandidateRecordCount,
      baseline_candidate_scope_count: inventory.baselineCandidateScopeCount,
    };
    if (scopes.size > 1) {
      return {
        public: {
          schema_version: 1,
          status: 'ambiguous-context',
          read_only: true,
          reset_available: false,
          context_count: scopes.size,
          ...baselineDiagnostics,
        },
        scope: null,
        fingerprint: null,
      };
    }

    const scope = scopes.size === 1 ? Array.from(scopes.values())[0] : null;
    if (scope && scope.records.length > MAX_RECORDS) {
      return {
        public: {
          schema_version: 1,
          status: 'too-many-records',
          read_only: true,
          reset_available: false,
          ...baselineDiagnostics,
        },
        scope: null,
        fingerprint: null,
      };
    }

    const records = scope?.records || [];
    const orderRecordCount = records.filter((record) => record.kind === 'order').length;
    const hiddenRecordCount = records.filter((record) => record.kind === 'hidden').length;
    const fingerprint = recordFingerprint(scope);
    return {
      public: {
        schema_version: 1,
        status: 'ready',
        read_only: true,
        reset_available: records.length > 0,
        change_count: records.length,
        order_record_count: orderRecordCount,
        hidden_record_count: hiddenRecordCount,
        target_fingerprint: fingerprint,
        ...baselineDiagnostics,
      },
      scope,
      fingerprint,
    };
  }

  function planHomeReset(storage) {
    return buildResetPlan(storage).public;
  }

  function verifyRaw(storage, records) {
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

    const records = plan.scope.records.map((record) => ({ ...record }));
    const touched = [];
    try {
      for (const record of records) {
        storage.removeItem(record.key);
        touched.push(record);
      }
      const verified = buildResetPlan(storage);
      if (verified.public.status !== 'ready' || verified.public.reset_available) {
        throw new Error('verification');
      }
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: plan.public.change_count,
        order_record_count: plan.public.order_record_count,
        hidden_record_count: plan.public.hidden_record_count,
        target_fingerprint: verified.fingerprint,
      };
    } catch (_error) {
      let rollbackFailureCount = 0;
      for (const record of [...touched].reverse()) {
        try {
          storage.setItem(record.key, record.raw);
        } catch (_rollbackError) {
          rollbackFailureCount += 1;
        }
      }
      try {
        if (!verifyRaw(storage, touched)) rollbackFailureCount += 1;
      } catch (_verificationError) {
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
        }
      } catch (_error) {
        if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', read_only: true, reset_available: false };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', applied: false, rolled_back: false };
        }
      }
      if (!responseType || !result) return;
      win.parent.postMessage(
        { type: responseType, nonce: request.nonce, result },
        event.origin,
      );
    });
  }

  const api = {
    applyHomeReset,
    planHomeReset,
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
    install(window, localStorage);
  }
})();