(() => {
  'use strict';

  if (window.__aClockworkPlexHomeResetBridgeLoaded) return;
  window.__aClockworkPlexHomeResetBridgeLoaded = true;

  const PLAN_REQUEST_TYPE = 'acp-plexamp-home-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-home-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-home-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-home-reset-apply-response-v1';
  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;

  function boundedCount(value, max = 256) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function validateBaselineDiagnostics(raw, result) {
    const recordCount = boundedCount(raw.baseline_candidate_record_count, 2048);
    const scopeCount = boundedCount(raw.baseline_candidate_scope_count, 2048);
    if (recordCount === null || scopeCount === null || scopeCount > recordCount) return false;
    result.baseline_candidate_record_count = recordCount;
    result.baseline_candidate_scope_count = scopeCount;
    return true;
  }

  function validatePlan(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || raw.read_only !== true
      || typeof raw.reset_available !== 'boolean'
    ) return null;
    if (raw.status !== 'ready') {
      const result = {
        schema_version: 1,
        status: raw.status,
        read_only: true,
        reset_available: false,
      };
      if (Number.isInteger(raw.context_count) && raw.context_count >= 0 && raw.context_count <= 32) {
        result.context_count = raw.context_count;
      }
      if (
        'baseline_candidate_record_count' in raw
        || 'baseline_candidate_scope_count' in raw
      ) {
        if (!validateBaselineDiagnostics(raw, result)) return null;
      }
      return result;
    }

    const changeCount = boundedCount(raw.change_count, 129);
    const orderRecordCount = boundedCount(raw.order_record_count, 1);
    const hiddenRecordCount = boundedCount(raw.hidden_record_count, 128);
    const result = {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      reset_available: raw.reset_available,
    };
    if (
      changeCount === null
      || orderRecordCount === null
      || hiddenRecordCount === null
      || changeCount !== orderRecordCount + hiddenRecordCount
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
      || !validateBaselineDiagnostics(raw, result)
    ) return null;
    result.change_count = changeCount;
    result.order_record_count = orderRecordCount;
    result.hidden_record_count = hiddenRecordCount;
    result.target_fingerprint = raw.target_fingerprint;
    return result;
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
    if ('rollback_failure_count' in raw) {
      const rollbackFailureCount = boundedCount(raw.rollback_failure_count, 129);
      if (rollbackFailureCount === null) return null;
      result.rollback_failure_count = rollbackFailureCount;
    }
    if ('applied_change_count' in raw) {
      const appliedChangeCount = boundedCount(raw.applied_change_count, 129);
      if (appliedChangeCount === null) return null;
      result.applied_change_count = appliedChangeCount;
    }
    if (raw.applied) {
      const orderRecordCount = boundedCount(raw.order_record_count, 1);
      const hiddenRecordCount = boundedCount(raw.hidden_record_count, 128);
      if (
        raw.status !== 'applied'
        || orderRecordCount === null
        || hiddenRecordCount === null
        || typeof raw.target_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
      ) return null;
      result.order_record_count = orderRecordCount;
      result.hidden_record_count = hiddenRecordCount;
      result.target_fingerprint = raw.target_fingerprint;
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
        const validated = validator(payload.result);
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

  function plan(options = {}) {
    return frameRequest(PLAN_REQUEST_TYPE, PLAN_RESPONSE_TYPE, {}, validatePlan, options);
  }

  function apply(targetFingerprint, options = {}) {
    if (typeof targetFingerprint !== 'string' || !SAFE_FINGERPRINT.test(targetFingerprint)) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', applied: false, rolled_back: false });
    }
    return frameRequest(
      APPLY_REQUEST_TYPE,
      APPLY_RESPONSE_TYPE,
      { target_fingerprint: targetFingerprint, confirm_reset: true },
      validateApply,
      options,
    );
  }

  window.ACPPlexampHomeReset = {
    apply,
    plan,
    validateApply,
    validatePlan,
  };
})();