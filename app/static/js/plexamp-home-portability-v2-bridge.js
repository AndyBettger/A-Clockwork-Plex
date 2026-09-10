(() => {
  'use strict';

  // Dormant #89/#90 dashboard-side Home-v2 transport. It is intentionally not
  // loaded by Settings until the complete schema-v2 transaction is green.

  const SNAPSHOT_REQUEST_TYPE = 'acp-plexamp-home-portability-snapshot-request-v2';
  const SNAPSHOT_RESPONSE_TYPE = 'acp-plexamp-home-portability-snapshot-response-v2';
  const PLAN_REQUEST_TYPE = 'acp-plexamp-home-portability-plan-request-v2';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-home-portability-plan-response-v2';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-home-portability-apply-request-v2';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-home-portability-apply-response-v2';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-home-portability-rollback-request-v2';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-home-portability-rollback-response-v2';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-home-portability-finalize-request-v2';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-home-portability-finalize-response-v2';

  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_HUB = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_KIND = /^[A-Za-z0-9_-]{1,64}$/;
  const SAFE_REF = /^custom-[1-9][0-9]{0,5}$/;
  const SAFE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;
  const CUSTOM_HUB_RE = /^custom\.hub\.([A-Za-z0-9_-]{1,64})\.([0-9a-f-]{36})$/i;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const PRESENTATION_FIELDS = new Set(['type', 'subtype', 'size', 'limit', 'title']);
  const MAX_HOME_ITEMS = 256;
  const MAX_CUSTOM_SECTIONS = 128;
  const MAX_QUERY_CHARS = 2048;
  const MAX_TITLE_CHARS = 240;

  function plainObject(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  function cloneJson(value) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (_error) {
      return null;
    }
  }

  function safeText(value, maxChars) {
    return typeof value === 'string'
      && value.length > 0
      && value.length <= maxChars
      && !Array.from(value).some((char) => char.codePointAt(0) < 32);
  }

  function validateQuerySuffix(value) {
    if (
      typeof value !== 'string'
      || !value.startsWith('/')
      || value.length > MAX_QUERY_CHARS
      || value.includes('\\')
      || value.includes('://')
      || value.includes('#')
      || SENSITIVE_NAME.test(value)
      || /^\/library\/sections(?:\/|$)/i.test(value)
      || Array.from(value).some((char) => char.codePointAt(0) < 32)
    ) return false;
    const path = value.split('?')[0];
    return !path.split('/').some((part) => part === '..' || part === '.');
  }

  function validatePresentation(value) {
    if (!plainObject(value)) return null;
    const keys = Object.keys(value);
    if (keys.length === 0 || keys.some((key) => !PRESENTATION_FIELDS.has(key))) return null;
    const result = {};
    for (const key of keys.sort()) {
      const item = value[key];
      if (key === 'title') {
        if (!safeText(item, MAX_TITLE_CHARS)) return null;
        result.title = item;
      } else if (key === 'type' || key === 'subtype') {
        if (!safeText(item, 96)) return null;
        result[key] = item;
      } else {
        if (typeof item !== 'number' || !Number.isFinite(item) || item < 0 || item > 100000) return null;
        result[key] = item;
      }
    }
    return result;
  }

  function parseCustomHubIdentifier(value) {
    if (typeof value !== 'string') return null;
    const match = value.match(CUSTOM_HUB_RE);
    if (!match || !SAFE_KIND.test(match[1]) || !SAFE_UUID.test(match[2])) return null;
    return { kind: match[1], uuid: match[2].toLowerCase() };
  }

  function refSortKey(ref) {
    return JSON.stringify(ref);
  }

  function sortRefs(values) {
    values.sort((left, right) => refSortKey(left).localeCompare(refSortKey(right)));
    return values;
  }

  function validateLogicalRef(value, customRefs) {
    if (!plainObject(value)) return null;
    if (value.type === 'builtin') {
      if (Object.keys(value).sort().join(',') !== 'id,type') return null;
      if (!SAFE_HUB.test(value.id) || SENSITIVE_NAME.test(value.id) || parseCustomHubIdentifier(value.id)) return null;
      return { type: 'builtin', id: value.id };
    }
    if (value.type === 'custom') {
      if (Object.keys(value).sort().join(',') !== 'ref,type') return null;
      if (!SAFE_REF.test(value.ref) || !customRefs.has(value.ref)) return null;
      return { type: 'custom', ref: value.ref };
    }
    return null;
  }

  function validateHome(value) {
    if (!plainObject(value)) return null;
    const allowed = ['custom_sections', 'hidden', 'order', 'presentation', 'schema_version'];
    if (JSON.stringify(Object.keys(value).sort()) !== JSON.stringify(allowed)) return null;
    if (value.schema_version !== 2) return null;
    if (
      !Array.isArray(value.order)
      || !Array.isArray(value.hidden)
      || !Array.isArray(value.presentation)
      || !Array.isArray(value.custom_sections)
      || value.order.length > MAX_HOME_ITEMS
      || value.hidden.length > MAX_HOME_ITEMS
      || value.presentation.length > MAX_HOME_ITEMS
      || value.custom_sections.length > MAX_CUSTOM_SECTIONS
    ) return null;

    const customRefs = new Set();
    const customSections = [];
    for (const item of value.custom_sections) {
      if (!plainObject(item) || Object.keys(item).sort().join(',') !== 'kind,query_suffix,ref') return null;
      if (
        !SAFE_REF.test(item.ref)
        || customRefs.has(item.ref)
        || !SAFE_KIND.test(item.kind)
        || !validateQuerySuffix(item.query_suffix)
      ) return null;
      customRefs.add(item.ref);
      customSections.push({ ref: item.ref, kind: item.kind, query_suffix: item.query_suffix });
    }

    const validateRefList = (items, canonical = false) => {
      const result = [];
      const seen = new Set();
      for (const item of items) {
        const ref = validateLogicalRef(item, customRefs);
        if (!ref) return null;
        const encoded = refSortKey(ref);
        if (seen.has(encoded)) return null;
        seen.add(encoded);
        result.push(ref);
      }
      return canonical ? sortRefs(result) : result;
    };

    const order = validateRefList(value.order, false);
    const hidden = validateRefList(value.hidden, true);
    if (!order || !hidden) return null;

    const presentation = [];
    const seenPresentation = new Set();
    for (const row of value.presentation) {
      if (!plainObject(row) || Object.keys(row).sort().join(',') !== 'settings,target') return null;
      const target = validateLogicalRef(row.target, customRefs);
      const settings = validatePresentation(row.settings);
      if (!target || !settings) return null;
      const encoded = refSortKey(target);
      if (seenPresentation.has(encoded)) return null;
      seenPresentation.add(encoded);
      presentation.push({ target, settings });
    }
    presentation.sort((left, right) => refSortKey(left.target).localeCompare(refSortKey(right.target)));

    for (const ref of customRefs) {
      const row = presentation.find(
        (candidate) => candidate.target.type === 'custom' && candidate.target.ref === ref,
      );
      if (!row || !safeText(row.settings.title, MAX_TITLE_CHARS)) return null;
    }

    return {
      schema_version: 2,
      order,
      hidden,
      presentation,
      custom_sections: customSections,
    };
  }

  function boundedCount(value, max = 512) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function validateSnapshot(raw) {
    if (!raw || raw.schema_version !== 2 || typeof raw.status !== 'string') return null;
    if (raw.status !== 'ready') {
      return { schema_version: 2, status: raw.status, read_only: raw.read_only === true };
    }
    if (
      raw.read_only !== true
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
    ) return null;
    const home = validateHome(raw.home);
    if (!home) return null;
    return {
      schema_version: 2,
      status: 'ready',
      read_only: true,
      target_fingerprint: raw.target_fingerprint,
      home,
    };
  }

  function validatePlan(raw) {
    if (
      !raw
      || raw.schema_version !== 2
      || typeof raw.status !== 'string'
      || raw.read_only !== true
      || typeof raw.restore_available !== 'boolean'
    ) return null;
    if (raw.status !== 'ready') {
      return {
        schema_version: 2,
        status: raw.status,
        read_only: true,
        restore_available: false,
      };
    }
    const changeCount = boundedCount(raw.change_count, 1);
    const currentRecordCount = boundedCount(raw.current_record_count, 256);
    if (
      changeCount === null
      || currentRecordCount === null
      || raw.restore_available !== (changeCount > 0)
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
    ) return null;
    return {
      schema_version: 2,
      status: 'ready',
      read_only: true,
      restore_available: raw.restore_available,
      change_count: changeCount,
      current_record_count: currentRecordCount,
      target_fingerprint: raw.target_fingerprint,
    };
  }

  function validateApply(raw) {
    if (
      !raw
      || raw.schema_version !== 2
      || typeof raw.status !== 'string'
      || typeof raw.applied !== 'boolean'
      || typeof raw.rolled_back !== 'boolean'
    ) return null;
    const result = {
      schema_version: 2,
      status: raw.status,
      applied: raw.applied,
      rolled_back: raw.rolled_back,
    };
    if (raw.fresh_preview_required === true) result.fresh_preview_required = true;
    if ('applied_change_count' in raw) {
      const appliedChangeCount = boundedCount(raw.applied_change_count, 1);
      if (appliedChangeCount === null) return null;
      result.applied_change_count = appliedChangeCount;
    }
    if (raw.applied) {
      if (
        raw.status !== 'applied'
        || result.applied_change_count !== 1
        || typeof raw.target_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
        || typeof raw.rollback_token !== 'string'
        || !SAFE_ROLLBACK_TOKEN.test(raw.rollback_token)
      ) return null;
      result.target_fingerprint = raw.target_fingerprint;
      result.rollback_token = raw.rollback_token;
    }
    return result;
  }

  function validateRollback(raw) {
    if (
      !raw
      || raw.schema_version !== 2
      || typeof raw.status !== 'string'
      || typeof raw.rolled_back !== 'boolean'
      || typeof raw.verified !== 'boolean'
    ) return null;
    const result = {
      schema_version: 2,
      status: raw.status,
      rolled_back: raw.rolled_back,
      verified: raw.verified,
    };
    if (raw.fresh_preview_required === true) result.fresh_preview_required = true;
    return result;
  }

  function validateFinalize(raw) {
    if (
      !raw
      || raw.schema_version !== 2
      || typeof raw.status !== 'string'
      || typeof raw.finalized !== 'boolean'
    ) return null;
    return {
      schema_version: 2,
      status: raw.status,
      finalized: raw.finalized,
    };
  }

  function nonce() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    const bytes = new Uint32Array(4);
    globalThis.crypto?.getRandomValues?.(bytes);
    return Array.from(bytes, (value) => value.toString(16).padStart(8, '0')).join('');
  }

  function frameRequest(requestType, responseType, body, validator, options = {}) {
    if (typeof document === 'undefined' || typeof window === 'undefined') {
      return Promise.resolve({ schema_version: 2, status: 'document-unavailable' });
    }
    const frame = document.getElementById('persistent-plexamp-frame');
    if (!frame?.contentWindow) {
      return Promise.resolve({ schema_version: 2, status: 'frame-unavailable' });
    }

    let targetOrigin;
    try {
      targetOrigin = new URL(frame.src, window.location.href).origin;
    } catch (_error) {
      return Promise.resolve({ schema_version: 2, status: 'frame-origin-invalid' });
    }
    if (!ALLOWED_PLEXAMP_ORIGINS.has(targetOrigin)) {
      return Promise.resolve({ schema_version: 2, status: 'frame-origin-not-allowed' });
    }

    const requestNonce = nonce();
    const timeoutMs = Math.max(250, Math.min(5000, Number(options.timeoutMs || 1800)));
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
        if (!payload || payload.type !== responseType || payload.nonce !== requestNonce) return;
        const validated = validator(payload.result);
        finish(validated || { schema_version: 2, status: 'invalid-response' });
      };
      const timer = window.setTimeout(
        () => finish({ schema_version: 2, status: 'timeout' }),
        timeoutMs,
      );
      window.addEventListener('message', onMessage);
      frame.contentWindow.postMessage(
        { type: requestType, nonce: requestNonce, ...body },
        targetOrigin,
      );
    });
  }

  function snapshot(options = {}) {
    return frameRequest(SNAPSHOT_REQUEST_TYPE, SNAPSHOT_RESPONSE_TYPE, {}, validateSnapshot, options);
  }

  function plan(home, options = {}) {
    const desired = validateHome(home);
    if (!desired) {
      return Promise.resolve({ schema_version: 2, status: 'invalid-request', read_only: true, restore_available: false });
    }
    return frameRequest(
      PLAN_REQUEST_TYPE,
      PLAN_RESPONSE_TYPE,
      { home: desired },
      validatePlan,
      options,
    );
  }

  function apply(home, targetFingerprint, options = {}) {
    const desired = validateHome(home);
    if (!desired || typeof targetFingerprint !== 'string' || !SAFE_FINGERPRINT.test(targetFingerprint)) {
      return Promise.resolve({ schema_version: 2, status: 'invalid-request', applied: false, rolled_back: false });
    }
    return frameRequest(
      APPLY_REQUEST_TYPE,
      APPLY_RESPONSE_TYPE,
      {
        home: desired,
        target_fingerprint: targetFingerprint,
        confirm_restore: true,
      },
      validateApply,
      options,
    );
  }

  function rollback(rollbackToken, options = {}) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return Promise.resolve({ schema_version: 2, status: 'invalid-request', rolled_back: false, verified: false });
    }
    return frameRequest(
      ROLLBACK_REQUEST_TYPE,
      ROLLBACK_RESPONSE_TYPE,
      { rollback_token: rollbackToken, confirm_rollback: true },
      validateRollback,
      options,
    );
  }

  function finalize(rollbackToken, options = {}) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return Promise.resolve({ schema_version: 2, status: 'invalid-request', finalized: false });
    }
    return frameRequest(
      FINALIZE_REQUEST_TYPE,
      FINALIZE_RESPONSE_TYPE,
      { rollback_token: rollbackToken },
      validateFinalize,
      options,
    );
  }

  const api = {
    apply,
    finalize,
    plan,
    rollback,
    snapshot,
    validateApply,
    validateFinalize,
    validateHome,
    validatePlan,
    validateRollback,
    validateSnapshot,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.ACPPlexampHomePortabilityV2 = api;
})();
