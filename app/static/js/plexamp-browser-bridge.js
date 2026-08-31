(() => {
  'use strict';

  if (window.__aClockworkPlexBrowserPreferenceBridgeLoaded) return;
  window.__aClockworkPlexBrowserPreferenceBridgeLoaded = true;

  const REQUEST_TYPE = 'acp-plexamp-browser-preferences-request-v1';
  const RESPONSE_TYPE = 'acp-plexamp-browser-preferences-response-v1';
  const PLAN_REQUEST_TYPE = 'acp-plexamp-browser-home-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-browser-home-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-browser-home-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-browser-home-apply-response-v1';
  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_HUB_ID = /^[A-Za-z0-9_.\/-]{1,220}$/;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const MAX_ORDER_ITEMS = 128;
  const MAX_HIDDEN_ITEMS = 128;

  function validatedList(value, limit) {
    if (!Array.isArray(value) || value.length > limit) return null;
    const result = [];
    const seen = new Set();
    for (const item of value) {
      if (typeof item !== 'string' || !SAFE_HUB_ID.test(item) || seen.has(item)) return null;
      seen.add(item);
      result.push(item);
    }
    return result;
  }

  function validateHome(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    if (Object.keys(raw).some((key) => key !== 'order' && key !== 'hidden')) return null;
    const order = raw.order === null ? null : validatedList(raw.order, MAX_ORDER_ITEMS);
    if (raw.order !== null && order === null) return null;
    const hidden = validatedList(raw.hidden || [], MAX_HIDDEN_ITEMS);
    if (hidden === null) return null;
    return { order, hidden };
  }

  function validateSnapshot(raw) {
    if (!raw || raw.schema_version !== 1 || typeof raw.status !== 'string') return null;
    if (raw.status === 'empty') {
      return { schema_version: 1, status: 'empty', home: { order: null, hidden: [] } };
    }
    if (raw.status !== 'ready') {
      return { schema_version: 1, status: raw.status };
    }

    const home = validateHome(raw.home);
    if (home === null) return null;
    return { schema_version: 1, status: 'ready', home };
  }

  function boundedCount(value, max = 512) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function validatePlan(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || raw.read_only !== true
      || typeof raw.restore_available !== 'boolean'
    ) return null;
    if (raw.status !== 'ready') {
      return {
        schema_version: 1,
        status: raw.status,
        read_only: true,
        restore_available: false,
      };
    }

    const changeCount = boundedCount(raw.change_count, 129);
    const hiddenChangeCount = boundedCount(raw.hidden_change_count, 128);
    const missingItemCount = boundedCount(raw.missing_item_count, 256);
    const targetOnlyItemCount = boundedCount(raw.target_only_item_count, 256);
    const targetKnownItemCount = boundedCount(raw.target_known_item_count, 256);
    if (
      changeCount === null
      || hiddenChangeCount === null
      || missingItemCount === null
      || targetOnlyItemCount === null
      || targetKnownItemCount === null
      || typeof raw.order_changed !== 'boolean'
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
    ) return null;

    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      restore_available: raw.restore_available,
      change_count: changeCount,
      order_changed: raw.order_changed,
      hidden_change_count: hiddenChangeCount,
      missing_item_count: missingItemCount,
      target_only_item_count: targetOnlyItemCount,
      target_known_item_count: targetKnownItemCount,
      target_fingerprint: raw.target_fingerprint,
    };
  }

  function validateApply(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || typeof raw.applied !== 'boolean'
      || typeof raw.rolled_back !== 'boolean'
    ) return null;

    const result = {
      schema_version: 1,
      status: raw.status,
      applied: raw.applied,
      rolled_back: raw.rolled_back,
    };
    if (raw.fresh_preview_required === true) result.fresh_preview_required = true;

    if (raw.applied) {
      const appliedChangeCount = boundedCount(raw.applied_change_count, 129);
      const missingItemCount = boundedCount(raw.missing_item_count, 256);
      const targetOnlyItemCount = boundedCount(raw.target_only_item_count, 256);
      if (
        raw.status !== 'applied'
        || appliedChangeCount === null
        || missingItemCount === null
        || targetOnlyItemCount === null
        || typeof raw.target_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
      ) return null;
      return {
        ...result,
        applied_change_count: appliedChangeCount,
        missing_item_count: missingItemCount,
        target_only_item_count: targetOnlyItemCount,
        target_fingerprint: raw.target_fingerprint,
      };
    }

    if ('applied_change_count' in raw) {
      const appliedChangeCount = boundedCount(raw.applied_change_count, 129);
      if (appliedChangeCount === null) return null;
      result.applied_change_count = appliedChangeCount;
    }
    if ('rollback_failure_count' in raw) {
      const rollbackFailureCount = boundedCount(raw.rollback_failure_count, 129);
      if (rollbackFailureCount === null) return null;
      result.rollback_failure_count = rollbackFailureCount;
    }
    return result;
  }

  function nonce() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    const bytes = new Uint32Array(4);
    globalThis.crypto?.getRandomValues?.(bytes);
    return Array.from(bytes, (value) => value.toString(16).padStart(8, '0')).join('');
  }

  function frameRequest(requestType, responseType, body, validator, options = {}) {
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
        if (!payload || payload.type !== responseType || payload.nonce !== requestNonce) return;
        const raw = requestType === REQUEST_TYPE ? payload.snapshot : payload.result;
        const validated = validator(raw);
        finish(validated || { schema_version: 1, status: 'invalid-response' });
      };
      const timer = window.setTimeout(
        () => finish({ schema_version: 1, status: 'timeout' }),
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
    return frameRequest(REQUEST_TYPE, RESPONSE_TYPE, {}, validateSnapshot, options);
  }

  function planHome(home, options = {}) {
    const validatedHome = validateHome(home);
    if (validatedHome === null) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', read_only: true, restore_available: false });
    }
    return frameRequest(
      PLAN_REQUEST_TYPE,
      PLAN_RESPONSE_TYPE,
      { home: validatedHome },
      validatePlan,
      options,
    );
  }

  function applyHome(home, targetFingerprint, options = {}) {
    const validatedHome = validateHome(home);
    if (validatedHome === null || typeof targetFingerprint !== 'string' || !SAFE_FINGERPRINT.test(targetFingerprint)) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', applied: false, rolled_back: false });
    }
    return frameRequest(
      APPLY_REQUEST_TYPE,
      APPLY_RESPONSE_TYPE,
      {
        home: validatedHome,
        target_fingerprint: targetFingerprint,
        confirm_restore: true,
      },
      validateApply,
      options,
    );
  }

  window.ACPPlexampBrowserPreferences = {
    applyHome,
    planHome,
    snapshot,
    validateApply,
    validateHome,
    validatePlan,
    validateSnapshot,
  };
})();
