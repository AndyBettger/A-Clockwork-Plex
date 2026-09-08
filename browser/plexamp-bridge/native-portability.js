(() => {
  'use strict';

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

  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
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
  const MAX_DEPTH = 5;
  const MAX_COLLECTION_ITEMS = 128;
  const MAX_OBJECT_KEYS = 128;
  const MAX_STRING_CHARS = 4096;
  const MAX_PUBLIC_CHANGED_KEYS = 96;

  const rollbackSnapshots = new Map();
  let cachedSettings = null;

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

  function plainObject(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  function clonePortable(value, depth = 0, seen = new WeakSet()) {
    if (value === null) return { ok: true, value: null };
    if (typeof value === 'boolean') return { ok: true, value };
    if (typeof value === 'number') {
      return Number.isFinite(value) ? { ok: true, value } : { ok: false, value: null };
    }
    if (typeof value === 'string') {
      return value.length <= MAX_STRING_CHARS
        ? { ok: true, value }
        : { ok: false, value: null };
    }
    if (depth >= MAX_DEPTH || !value || typeof value !== 'object' || seen.has(value)) {
      return { ok: false, value: null };
    }

    seen.add(value);
    try {
      if (Array.isArray(value)) {
        if (value.length > MAX_COLLECTION_ITEMS) return { ok: false, value: null };
        const result = [];
        for (const item of value) {
          const cloned = clonePortable(item, depth + 1, seen);
          if (!cloned.ok) return { ok: false, value: null };
          result.push(cloned.value);
        }
        return { ok: true, value: result };
      }

      if (!plainObject(value)) return { ok: false, value: null };
      const keys = Object.keys(value);
      if (keys.length > MAX_OBJECT_KEYS) return { ok: false, value: null };
      const result = {};
      for (const key of keys.sort()) {
        if (!SAFE_SETTING_KEY.test(key) || SENSITIVE_NAME.test(key)) {
          return { ok: false, value: null };
        }
        const cloned = clonePortable(value[key], depth + 1, seen);
        if (!cloned.ok) return { ok: false, value: null };
        result[key] = cloned.value;
      }
      return { ok: true, value: result };
    } finally {
      seen.delete(value);
    }
  }

  function encodedPortable(value) {
    const cloned = clonePortable(value);
    return cloned.ok ? JSON.stringify(cloned.value) : null;
  }

  function candidateKey(key, currentValue, defaultValue) {
    if (
      typeof key !== 'string'
      || key.startsWith('_')
      || !SAFE_SETTING_KEY.test(key)
      || SENSITIVE_NAME.test(key)
      || EXCLUDED_KEYS.has(key)
      || typeof currentValue === 'function'
      || typeof defaultValue === 'function'
    ) return false;
    return clonePortable(currentValue).ok && clonePortable(defaultValue).ok;
  }

  function constructDefaults(settings) {
    if (!settings || typeof settings.resetToDefaults !== 'function' || typeof settings.constructor !== 'function') {
      return null;
    }
    try {
      return new settings.constructor();
    } catch (_error) {
      return null;
    }
  }

  function portableModel(settings) {
    const defaults = constructDefaults(settings);
    if (!defaults) return null;

    const keys = Object.keys(settings || {})
      .filter((key) => Object.prototype.hasOwnProperty.call(defaults, key))
      .filter((key) => candidateKey(key, settings[key], defaults[key]))
      .sort()
      .slice(0, MAX_SETTINGS);

    const defaultRows = [];
    const currentRows = [];
    const deviations = {};
    for (const key of keys) {
      const current = clonePortable(settings[key]);
      const baseline = clonePortable(defaults[key]);
      if (!current.ok || !baseline.ok) continue;
      const currentEncoded = JSON.stringify(current.value);
      const defaultEncoded = JSON.stringify(baseline.value);
      defaultRows.push([key, baseline.value]);
      currentRows.push([key, current.value]);
      if (currentEncoded !== defaultEncoded) deviations[key] = current.value;
    }

    return {
      defaults,
      keys: defaultRows.map(([key]) => key),
      defaultRows,
      currentRows,
      deviations,
      settingsSchemaFingerprint: hash32(JSON.stringify(defaultRows)),
      stateFingerprint: hash32(JSON.stringify(currentRows)),
    };
  }

  function buildPortableSnapshot(settings) {
    const model = portableModel(settings);
    if (!model) {
      return {
        schema_version: 1,
        status: 'settings-unavailable',
        read_only: true,
      };
    }
    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      settings_schema_fingerprint: model.settingsSchemaFingerprint,
      portable_key_count: model.keys.length,
      saved_setting_count: Object.keys(model.deviations).length,
      settings: model.deviations,
    };
  }

  function validateDesiredSnapshot(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    const allowed = new Set(['schema_version', 'settings_schema_fingerprint', 'settings']);
    if (Object.keys(value).some((key) => !allowed.has(key))) return null;
    if (value.schema_version !== 1) return null;
    if (
      typeof value.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(value.settings_schema_fingerprint)
      || !plainObject(value.settings)
      || Object.keys(value.settings).length > MAX_SETTINGS
    ) return null;

    const settings = {};
    for (const key of Object.keys(value.settings).sort()) {
      if (
        !SAFE_SETTING_KEY.test(key)
        || key.startsWith('_')
        || SENSITIVE_NAME.test(key)
        || EXCLUDED_KEYS.has(key)
      ) return null;
      const cloned = clonePortable(value.settings[key]);
      if (!cloned.ok) return null;
      settings[key] = cloned.value;
    }
    return {
      schema_version: 1,
      settings_schema_fingerprint: value.settings_schema_fingerprint,
      settings,
    };
  }

  function publicChangedKeys(keys) {
    return keys
      .filter((key) => SAFE_SETTING_KEY.test(key))
      .slice(0, MAX_PUBLIC_CHANGED_KEYS);
  }

  function buildPortablePlan(settings, desiredSnapshot) {
    const desired = validateDesiredSnapshot(desiredSnapshot);
    if (!desired) {
      return {
        schema_version: 1,
        status: 'invalid-request',
        read_only: true,
        restore_available: false,
      };
    }
    const model = portableModel(settings);
    if (!model) {
      return {
        schema_version: 1,
        status: 'settings-unavailable',
        read_only: true,
        restore_available: false,
      };
    }
    if (model.settingsSchemaFingerprint !== desired.settings_schema_fingerprint) {
      return {
        schema_version: 1,
        status: 'settings-schema-mismatch',
        read_only: true,
        restore_available: false,
        settings_schema_fingerprint: model.settingsSchemaFingerprint,
      };
    }

    const keySet = new Set(model.keys);
    if (Object.keys(desired.settings).some((key) => !keySet.has(key))) {
      return {
        schema_version: 1,
        status: 'unsupported-setting',
        read_only: true,
        restore_available: false,
      };
    }

    const defaultsByKey = new Map(model.defaultRows);
    const currentByKey = new Map(model.currentRows);
    const changed = [];
    for (const key of model.keys) {
      const wanted = Object.prototype.hasOwnProperty.call(desired.settings, key)
        ? desired.settings[key]
        : defaultsByKey.get(key);
      if (JSON.stringify(currentByKey.get(key)) !== JSON.stringify(wanted)) changed.push(key);
    }

    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      restore_available: changed.length > 0,
      change_count: changed.length,
      changed_keys: publicChangedKeys(changed),
      settings_schema_fingerprint: model.settingsSchemaFingerprint,
      target_fingerprint: model.stateFingerprint,
    };
  }

  function captureExactSnapshot(settings) {
    const values = new Map();
    for (const key of Object.keys(settings || {})) {
      if (typeof settings[key] === 'function') continue;
      values.set(key, settings[key]);
    }
    const rows = Array.from(values.entries())
      .map(([key, value]) => [key, encodedPortable(value) || `opaque:${Object.prototype.toString.call(value)}`])
      .sort(([left], [right]) => left.localeCompare(right));
    return { values, fingerprint: hash32(JSON.stringify(rows)) };
  }

  function exactSnapshotFingerprint(settings, snapshot) {
    const rows = Array.from(snapshot.values.keys())
      .map((key) => {
        const value = settings[key];
        return [key, encodedPortable(value) || `opaque:${Object.prototype.toString.call(value)}`];
      })
      .sort(([left], [right]) => left.localeCompare(right));
    return hash32(JSON.stringify(rows));
  }

  function restoreExactSnapshot(settings, snapshot) {
    for (const [key, value] of snapshot.values.entries()) settings[key] = value;
    return exactSnapshotFingerprint(settings, snapshot) === snapshot.fingerprint;
  }

  function restoreNonPortable(settings, snapshot, portableKeys) {
    for (const [key, value] of snapshot.values.entries()) {
      if (!portableKeys.has(key)) settings[key] = value;
    }
  }

  function applyPortableSettings(settings, desiredSnapshot, expectedFingerprint, confirmRestore = false) {
    if (confirmRestore !== true) {
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

    const desired = validateDesiredSnapshot(desiredSnapshot);
    const plan = buildPortablePlan(settings, desiredSnapshot);
    if (!desired || plan.status !== 'ready') {
      return {
        schema_version: 1,
        status: plan.status || 'invalid-request',
        applied: false,
        rolled_back: false,
      };
    }
    if (plan.target_fingerprint !== expectedFingerprint) {
      return {
        schema_version: 1,
        status: 'stale-target',
        applied: false,
        rolled_back: false,
        fresh_preview_required: true,
      };
    }
    if (!plan.restore_available) {
      return {
        schema_version: 1,
        status: 'no-change',
        applied: false,
        rolled_back: false,
        applied_change_count: 0,
      };
    }

    const model = portableModel(settings);
    if (!model) {
      return {
        schema_version: 1,
        status: 'settings-unavailable',
        applied: false,
        rolled_back: false,
      };
    }
    const snapshot = captureExactSnapshot(settings);
    const portableKeys = new Set(model.keys);

    try {
      settings.resetToDefaults();
      restoreNonPortable(settings, snapshot, portableKeys);
      for (const [key, value] of Object.entries(desired.settings)) settings[key] = value;

      const verified = buildPortablePlan(settings, desired);
      if (verified.status !== 'ready' || verified.restore_available) throw new Error('verification');

      const rollbackToken = randomToken();
      rollbackSnapshots.set(rollbackToken, { settings, snapshot });
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: plan.change_count,
        settings_schema_fingerprint: verified.settings_schema_fingerprint,
        target_fingerprint: verified.target_fingerprint,
        rollback_token: rollbackToken,
      };
    } catch (_error) {
      let rolledBack = false;
      try {
        rolledBack = restoreExactSnapshot(settings, snapshot);
      } catch (_rollbackError) {
        rolledBack = false;
      }
      return {
        schema_version: 1,
        status: 'apply-failed',
        applied: false,
        rolled_back: rolledBack,
        fresh_preview_required: true,
      };
    }
  }

  function rollbackPortableSettings(rollbackToken, confirmRollback = false) {
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
      const verified = restoreExactSnapshot(entry.settings, entry.snapshot);
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

  function finalizePortableSettings(rollbackToken) {
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

  function locateSettings(win) {
    if (cachedSettings && typeof cachedSettings.resetToDefaults === 'function') return cachedSettings;
    const candidates = [
      win?.app?.rootStore?.settings,
      win?.global?.app?.rootStore?.settings,
    ];
    for (const settings of candidates) {
      if (settings && typeof settings.resetToDefaults === 'function') {
        cachedSettings = settings;
        return settings;
      }
    }
    return null;
  }

  function install(win) {
    if (!win?.addEventListener) return;
    win.addEventListener('message', (event) => {
      if (event.source !== win.parent || !DASHBOARD_ORIGINS.has(event.origin)) return;
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
        const settings = locateSettings(win);
        if (request.type === SNAPSHOT_REQUEST_TYPE) {
          responseType = SNAPSHOT_RESPONSE_TYPE;
          result = settings
            ? buildPortableSnapshot(settings)
            : { schema_version: 1, status: 'runtime-unavailable', read_only: true };
        } else if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = settings
            ? buildPortablePlan(settings, request.snapshot)
            : { schema_version: 1, status: 'runtime-unavailable', read_only: true, restore_available: false };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = settings
            ? applyPortableSettings(
                settings,
                request.snapshot,
                request.target_fingerprint,
                request.confirm_restore === true,
              )
            : { schema_version: 1, status: 'runtime-unavailable', applied: false, rolled_back: false };
        } else if (request.type === ROLLBACK_REQUEST_TYPE) {
          responseType = ROLLBACK_RESPONSE_TYPE;
          result = rollbackPortableSettings(
            request.rollback_token,
            request.confirm_rollback === true,
          );
        } else if (request.type === FINALIZE_REQUEST_TYPE) {
          responseType = FINALIZE_RESPONSE_TYPE;
          result = finalizePortableSettings(request.rollback_token);
        }
      } catch (_error) {
        if (request.type === SNAPSHOT_REQUEST_TYPE) {
          responseType = SNAPSHOT_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', read_only: true };
        } else if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', read_only: true, restore_available: false };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', applied: false, rolled_back: false };
        } else if (request.type === ROLLBACK_REQUEST_TYPE) {
          responseType = ROLLBACK_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', rolled_back: false, verified: false };
        } else if (request.type === FINALIZE_REQUEST_TYPE) {
          responseType = FINALIZE_RESPONSE_TYPE;
          result = { schema_version: 1, status: 'unavailable', finalized: false };
        }
      }

      if (!responseType || !result) return;
      win.parent.postMessage({ type: responseType, nonce: request.nonce, result }, event.origin);
    });
  }

  const api = {
    applyPortableSettings,
    buildPortablePlan,
    buildPortableSnapshot,
    finalizePortableSettings,
    locateSettings,
    rollbackPortableSettings,
    validateDesiredSnapshot,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') install(window);
})();
