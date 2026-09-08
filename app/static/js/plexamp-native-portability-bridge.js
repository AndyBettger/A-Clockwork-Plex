(() => {
  'use strict';

  if (window.__aClockworkPlexNativePortabilityBridgeLoaded) return;
  window.__aClockworkPlexNativePortabilityBridgeLoaded = true;

  const SNAPSHOT_REQUEST_TYPE = 'acp-plexamp-native-portability-snapshot-request-v1';
  const SNAPSHOT_RESPONSE_TYPE = 'acp-plexamp-native-portability-snapshot-response-v1';
  const PLAN_REQUEST_TYPE = 'acp-plexamp-native-portability-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-native-portability-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-native-portability-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-native-portability-apply-response-v1';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-native-portability-rollback-request-v1';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-native-portability-rollback-response-v1';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-native-portability-finalize-request-v1';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-native-portability-finalize-response-v1';

  const ALLOWED_PLEXAMP_ORIGINS = new Set([
    'http://localhost:32500',
    'http://127.0.0.1:32500',
  ]);
  const SAFE_SETTING_KEY = /^[A-Za-z][A-Za-z0-9_.-]{0,127}$/;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const EXCLUDED_KEYS = new Set([
    'playerName',
    'audioDeviceUuid',
    'premium',
    'activeTab',
    'equalizerPresets',
    'equalizerValues',
  ]);
  const MAX_SETTINGS = 512;
  const MAX_CHANGED_KEYS = 96;
  const MAX_DEPTH = 5;
  const MAX_COLLECTION_ITEMS = 128;
  const MAX_OBJECT_KEYS = 128;
  const MAX_STRING_CHARS = 4096;

  function boundedCount(value, max = MAX_SETTINGS) {
    return Number.isInteger(value) && value >= 0 && value <= max ? value : null;
  }

  function plainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function validatePortableValue(value, depth = 0) {
    if (value === null || typeof value === 'boolean') return true;
    if (typeof value === 'number') return Number.isFinite(value);
    if (typeof value === 'string') return value.length <= MAX_STRING_CHARS;
    if (depth >= MAX_DEPTH || !value || typeof value !== 'object') return false;
    if (Array.isArray(value)) {
      return value.length <= MAX_COLLECTION_ITEMS
        && value.every((item) => validatePortableValue(item, depth + 1));
    }
    if (!plainObject(value) || Object.keys(value).length > MAX_OBJECT_KEYS) return false;
    return Object.entries(value).every(([key, child]) => (
      SAFE_SETTING_KEY.test(key)
      && !SENSITIVE_NAME.test(key)
      && validatePortableValue(child, depth + 1)
    ));
  }

  function validateSettingsMap(raw) {
    if (!plainObject(raw) || Object.keys(raw).length > MAX_SETTINGS) return null;
    const result = {};
    for (const key of Object.keys(raw).sort()) {
      if (
        !SAFE_SETTING_KEY.test(key)
        || key.startsWith('_')
        || SENSITIVE_NAME.test(key)
        || EXCLUDED_KEYS.has(key)
        || !validatePortableValue(raw[key])
      ) return null;
      result[key] = JSON.parse(JSON.stringify(raw[key]));
    }
    return result;
  }

  function validatePortableSnapshot(raw) {
    if (!raw || raw.schema_version !== 1 || typeof raw.status !== 'string') return null;
    if (raw.status !== 'ready') {
      return { schema_version: 1, status: raw.status, read_only: raw.read_only === true };
    }
    if (
      raw.read_only !== true
      || typeof raw.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.settings_schema_fingerprint)
    ) return null;
    const settings = validateSettingsMap(raw.settings);
    const portableKeyCount = boundedCount(raw.portable_key_count);
    const savedSettingCount = boundedCount(raw.saved_setting_count);
    if (
      settings === null
      || portableKeyCount === null
      || savedSettingCount === null
      || savedSettingCount !== Object.keys(settings).length
      || savedSettingCount > portableKeyCount
    ) return null;
    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      settings_schema_fingerprint: raw.settings_schema_fingerprint,
      portable_key_count: portableKeyCount,
      saved_setting_count: savedSettingCount,
      settings,
    };
  }

  function validateDesiredSnapshot(raw) {
    if (!raw || raw.schema_version !== 1) return null;
    if (
      typeof raw.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.settings_schema_fingerprint)
    ) return null;
    const settings = validateSettingsMap(raw.settings);
    if (settings === null) return null;
    return {
      schema_version: 1,
      settings_schema_fingerprint: raw.settings_schema_fingerprint,
      settings,
    };
  }

  function validateChangedKeys(raw, count) {
    if (!Array.isArray(raw) || raw.length > MAX_CHANGED_KEYS || raw.length > count) return null;
    const result = [];
    const seen = new Set();
    for (const key of raw) {
      if (
        typeof key !== 'string'
        || !SAFE_SETTING_KEY.test(key)
        || SENSITIVE_NAME.test(key)
        || EXCLUDED_KEYS.has(key)
        || seen.has(key)
      ) return null;
      seen.add(key);
      result.push(key);
    }
    return result;
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
      const result = {
        schema_version: 1,
        status: raw.status,
        read_only: true,
        restore_available: false,
      };
      if (typeof raw.settings_schema_fingerprint === 'string' && SAFE_FINGERPRINT.test(raw.settings_schema_fingerprint)) {
        result.settings_schema_fingerprint = raw.settings_schema_fingerprint;
      }
      return result;
    }

    const changeCount = boundedCount(raw.change_count);
    const changedKeys = validateChangedKeys(raw.changed_keys, changeCount ?? 0);
    if (
      changeCount === null
      || changedKeys === null
      || raw.restore_available !== (changeCount > 0)
      || typeof raw.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.settings_schema_fingerprint)
      || typeof raw.target_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
    ) return null;
    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      restore_available: raw.restore_available,
      change_count: changeCount,
      changed_keys: changedKeys,
      settings_schema_fingerprint: raw.settings_schema_fingerprint,
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
        || typeof raw.settings_schema_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.settings_schema_fingerprint)
        || typeof raw.target_fingerprint !== 'string'
        || !SAFE_FINGERPRINT.test(raw.target_fingerprint)
        || typeof raw.rollback_token !== 'string'
        || !SAFE_ROLLBACK_TOKEN.test(raw.rollback_token)
      ) return null;
      result.settings_schema_fingerprint = raw.settings_schema_fingerprint;
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

  function snapshot(options = {}) {
    return frameRequest(SNAPSHOT_REQUEST_TYPE, SNAPSHOT_RESPONSE_TYPE, {}, validatePortableSnapshot, options);
  }

  function plan(desiredSnapshot, options = {}) {
    const desired = validateDesiredSnapshot(desiredSnapshot);
    if (!desired) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', read_only: true, restore_available: false });
    }
    return frameRequest(
      PLAN_REQUEST_TYPE,
      PLAN_RESPONSE_TYPE,
      { snapshot: desired },
      validatePlan,
      options,
    );
  }

  function apply(desiredSnapshot, targetFingerprint, options = {}) {
    const desired = validateDesiredSnapshot(desiredSnapshot);
    if (!desired || typeof targetFingerprint !== 'string' || !SAFE_FINGERPRINT.test(targetFingerprint)) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', applied: false, rolled_back: false });
    }
    return frameRequest(
      APPLY_REQUEST_TYPE,
      APPLY_RESPONSE_TYPE,
      {
        snapshot: desired,
        target_fingerprint: targetFingerprint,
        confirm_restore: true,
      },
      validateApply,
      options,
    );
  }

  function rollback(rollbackToken, options = {}) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', rolled_back: false, verified: false });
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
      return Promise.resolve({ schema_version: 1, status: 'invalid-request', finalized: false });
    }
    return frameRequest(
      FINALIZE_REQUEST_TYPE,
      FINALIZE_RESPONSE_TYPE,
      { rollback_token: rollbackToken },
      validateFinalize,
      options,
    );
  }

  window.ACPPlexampNativePortability = {
    apply,
    finalize,
    plan,
    rollback,
    snapshot,
    validateApply,
    validateDesiredSnapshot,
    validateFinalize,
    validatePlan,
    validatePortableSnapshot,
    validateRollback,
  };
})();
