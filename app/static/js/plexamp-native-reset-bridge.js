(() => {
  'use strict';

  if (window.__aClockworkPlexNativeResetBridgeLoaded) return;
  window.__aClockworkPlexNativeResetBridgeLoaded = true;

  const PLAN_REQUEST_TYPE = 'acp-plexamp-native-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-native-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-native-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-native-reset-apply-response-v1';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-native-reset-rollback-request-v1';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-native-reset-rollback-response-v1';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-native-reset-finalize-request-v1';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-native-reset-finalize-response-v1';
  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;
  const SAFE_SETTING_KEY = /^[A-Za-z][A-Za-z0-9_.-]{0,127}$/;
  const MAX_CHANGED_KEYS = 64;

  function boundedCount(value, max = 512) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function validatedChangedKeys(raw, changeCount) {
    if (!Array.isArray(raw) || raw.length > MAX_CHANGED_KEYS || raw.length > changeCount) return null;
    const result = [];
    const seen = new Set();
    for (const value of raw) {
      if (typeof value !== 'string' || !SAFE_SETTING_KEY.test(value) || seen.has(value)) return null;
      seen.add(value);
      result.push(value);
    }
    return result;
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
      return {
        schema_version: 1,
        status: raw.status,
        read_only: true,
        reset_available: false,
      };
    }

    const changeCount = boundedCount(raw.change_count);
    const changedKeys = validatedChangedKeys(raw.changed_keys, changeCount ?? 0);
    if (
      changeCount === null
      || changedKeys === null
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
      changed_keys: changedKeys,
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
    if ('applied_change_count' in raw) {
      const count = boundedCount(raw.applied_change_count);
      if (count === null) return null;
      result.applied_change_count = count;
    }
    if (raw.applied) {
      if (
        raw.status !== 'applied'
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
      || raw.schema_version !== 1
      || typeof raw.status !== 'string'
      || typeof raw.rolled_back !== 'boolean'
      || typeof raw.verified !== 'boolean'
    ) return null;
    return {
      schema_version: 1,
      status: raw.status,
      rolled_back: raw.rolled_back,
      verified: raw.verified,
    };
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

  window.ACPPlexampNativeReset = {
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
