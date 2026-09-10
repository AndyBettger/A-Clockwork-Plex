(() => {
  'use strict';

  if (window.__aClockworkPlexHomeResetBridgeLoaded) return;
  window.__aClockworkPlexHomeResetBridgeLoaded = true;

  const PLAN_REQUEST_TYPE = 'acp-plexamp-home-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-home-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-home-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-home-reset-apply-response-v1';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-home-reset-rollback-request-v1';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-home-reset-rollback-response-v1';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-home-reset-finalize-request-v1';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-home-reset-finalize-response-v1';
  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;

  function boundedCount(value, max = 256) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function validateFamilyCounts(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    const familyCounts = {};
    for (const name of ['order', 'hidden', 'viewSettings', 'editing', 'customHubs', 'other']) {
      const count = boundedCount(raw[name], 256);
      if (count === null) return null;
      familyCounts[name] = count;
    }
    return familyCounts;
  }

  function validatePlan(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || raw.read_only !== true
      || typeof raw.reset_available !== 'boolean'
    ) return null;

    const familyCounts = validateFamilyCounts(raw.family_counts);
    const contextCount = boundedCount(raw.context_count, 64);
    const sectionContextCount = boundedCount(raw.section_context_count, 256);
    const structurallyInvalidCount = boundedCount(raw.structurally_invalid_count, 256);
    if (
      familyCounts === null
      || contextCount === null
      || sectionContextCount === null
      || structurallyInvalidCount === null
    ) return null;

    if (raw.status !== 'ready') {
      return {
        schema_version: 1,
        status: raw.status,
        read_only: true,
        reset_available: false,
        family_counts: familyCounts,
        context_count: contextCount,
        section_context_count: sectionContextCount,
        structurally_invalid_count: structurallyInvalidCount,
      };
    }

    const changeCount = boundedCount(raw.change_count, 256);
    const homeRecordCount = boundedCount(raw.home_record_count, 256);
    const durableCount = familyCounts.order
      + familyCounts.hidden
      + familyCounts.viewSettings
      + familyCounts.customHubs;
    if (
      changeCount === null
      || homeRecordCount === null
      || changeCount !== homeRecordCount
      || changeCount !== durableCount
      || familyCounts.editing !== 0
      || familyCounts.other !== 0
      || structurallyInvalidCount !== 0
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
      || raw.reset_available !== (changeCount > 0)
    ) return null;

    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      reset_available: raw.reset_available,
      change_count: changeCount,
      home_record_count: homeRecordCount,
      family_counts: familyCounts,
      context_count: contextCount,
      section_context_count: sectionContextCount,
      structurally_invalid_count: structurallyInvalidCount,
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
    if ('rollback_failure_count' in raw) {
      const rollbackFailureCount = boundedCount(raw.rollback_failure_count, 256);
      if (rollbackFailureCount === null) return null;
      result.rollback_failure_count = rollbackFailureCount;
    }
    if ('applied_change_count' in raw) {
      const appliedChangeCount = boundedCount(raw.applied_change_count, 256);
      if (appliedChangeCount === null) return null;
      result.applied_change_count = appliedChangeCount;
    }
    if (raw.applied) {
      const homeRecordCount = boundedCount(raw.home_record_count, 256);
      const familyCounts = validateFamilyCounts(raw.family_counts);
      if (
        raw.status !== 'applied'
        || homeRecordCount === null
        || familyCounts === null
        || homeRecordCount !== familyCounts.order
          + familyCounts.hidden
          + familyCounts.viewSettings
          + familyCounts.customHubs
        || familyCounts.editing !== 0
        || familyCounts.other !== 0
        || result.applied_change_count !== homeRecordCount
        || typeof raw.target_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
        || typeof raw.rollback_token !== 'string'
        || !SAFE_ROLLBACK_TOKEN.test(raw.rollback_token)
      ) return null;
      result.home_record_count = homeRecordCount;
      result.family_counts = familyCounts;
      result.target_fingerprint = raw.target_fingerprint;
      result.rollback_token = raw.rollback_token;
    }
    return result;
  }

  function validateRollback(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || typeof raw.rolled_back !== 'boolean'
      || typeof raw.verified !== 'boolean'
    ) return null;
    const result = {
      schema_version: 1,
      status: raw.status,
      rolled_back: raw.rolled_back,
      verified: raw.verified,
    };
    if ('restored_record_count' in raw) {
      const restoredRecordCount = boundedCount(raw.restored_record_count, 256);
      if (restoredRecordCount === null) return null;
      result.restored_record_count = restoredRecordCount;
    }
    if ('target_fingerprint' in raw) {
      if (typeof raw.target_fingerprint !== 'string' || !SAFE_FINGERPRINT.test(raw.target_fingerprint)) {
        return null;
      }
      result.target_fingerprint = raw.target_fingerprint;
    }
    return result;
  }

  function validateFinalize(raw) {
    if (
      !raw
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || typeof raw.finalized !== 'boolean'
    ) return null;
    return {
      schema_version: 1,
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
      return Promise.resolve({
        schema_version: 1,
        status: 'invalid-request',
        applied: false,
        rolled_back: false,
      });
    }
    return frameRequest(
      APPLY_REQUEST_TYPE,
      APPLY_RESPONSE_TYPE,
      { target_fingerprint: targetFingerprint, confirm_reset: true },
      validateApply,
      options,
    );
  }

  function rollback(rollbackToken, options = {}) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return Promise.resolve({
        schema_version: 1,
        status: 'invalid-request',
        rolled_back: false,
        verified: false,
      });
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
      return Promise.resolve({
        schema_version: 1,
        status: 'invalid-request',
        finalized: false,
      });
    }
    return frameRequest(
      FINALIZE_REQUEST_TYPE,
      FINALIZE_RESPONSE_TYPE,
      { rollback_token: rollbackToken },
      validateFinalize,
      options,
    );
  }

  window.ACPPlexampHomeReset = {
    apply,
    finalize,
    plan,
    rollback,
    validateApply,
    validateFinalize,
    validatePlan,
    validateRollback,
  };
})();
