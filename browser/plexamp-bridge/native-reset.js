(() => {
  'use strict';

  const PLAN_REQUEST_TYPE = 'acp-plexamp-native-reset-plan-request-v1';
  const PLAN_RESPONSE_TYPE = 'acp-plexamp-native-reset-plan-response-v1';
  const APPLY_REQUEST_TYPE = 'acp-plexamp-native-reset-apply-request-v1';
  const APPLY_RESPONSE_TYPE = 'acp-plexamp-native-reset-apply-response-v1';
  const ROLLBACK_REQUEST_TYPE = 'acp-plexamp-native-reset-rollback-request-v1';
  const ROLLBACK_RESPONSE_TYPE = 'acp-plexamp-native-reset-rollback-response-v1';
  const FINALIZE_REQUEST_TYPE = 'acp-plexamp-native-reset-finalize-request-v1';
  const FINALIZE_RESPONSE_TYPE = 'acp-plexamp-native-reset-finalize-response-v1';
  const DASHBOARD_ORIGINS = new Set([
    'http://localhost:8088',
    'http://127.0.0.1:8088',
  ]);
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;
  const EXCLUDED_COMMISSIONING_KEYS = new Set(['playerName', 'audioDeviceUuid']);
  const MAX_SETTINGS = 512;
  const MAX_DEPTH = 5;
  const MAX_COLLECTION_ITEMS = 128;
  const MAX_OBJECT_KEYS = 128;
  const MAX_STRING_CHARS = 4096;

  const rollbackSnapshots = new Map();
  let cachedWebpackRequire = null;
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

  function comparableKey(key, value, includeCommissioning = false) {
    if (typeof key !== 'string' || key.startsWith('_') || key === 'premium') return false;
    if (!includeCommissioning && EXCLUDED_COMMISSIONING_KEYS.has(key)) return false;
    return typeof value !== 'function';
  }

  function canonicalize(value, depth = 0, seen = new WeakSet()) {
    if (value === null) return ['null'];
    const kind = typeof value;
    if (kind === 'undefined') return ['undefined'];
    if (kind === 'boolean' || kind === 'number') return [kind, Number.isNaN(value) ? 'NaN' : value];
    if (kind === 'string') return ['string', value.slice(0, MAX_STRING_CHARS), value.length];
    if (kind === 'bigint') return ['bigint', value.toString()];
    if (kind === 'function' || kind === 'symbol') return [kind];
    if (depth >= MAX_DEPTH) return ['depth', Object.prototype.toString.call(value)];
    if (seen.has(value)) return ['circular'];
    seen.add(value);

    try {
      if (Array.isArray(value)) {
        return ['array', value.length, value.slice(0, MAX_COLLECTION_ITEMS).map(
          (item) => canonicalize(item, depth + 1, seen),
        )];
      }
      if (value instanceof Date) return ['date', value.toISOString()];
      if (value instanceof Map || (typeof value.entries === 'function' && Number.isInteger(value.size))) {
        const entries = [];
        let count = 0;
        for (const [key, item] of value.entries()) {
          if (count >= MAX_COLLECTION_ITEMS) break;
          entries.push([
            canonicalize(key, depth + 1, seen),
            canonicalize(item, depth + 1, seen),
          ]);
          count += 1;
        }
        return ['map', Number(value.size || entries.length), entries];
      }
      if (value instanceof Set || (typeof value.values === 'function' && Number.isInteger(value.size))) {
        const items = [];
        let count = 0;
        for (const item of value.values()) {
          if (count >= MAX_COLLECTION_ITEMS) break;
          items.push(canonicalize(item, depth + 1, seen));
          count += 1;
        }
        return ['set', Number(value.size || items.length), items];
      }
      if (typeof value.toJSON === 'function') {
        try {
          const jsonValue = value.toJSON();
          if (jsonValue !== value) return ['json', canonicalize(jsonValue, depth + 1, seen)];
        } catch (_error) {
          // Fall through to bounded own-property inspection.
        }
      }
      const keys = Object.keys(value)
        .filter((key) => typeof value[key] !== 'function')
        .sort();
      return ['object', keys.length, keys.slice(0, MAX_OBJECT_KEYS).map(
        (key) => [key, canonicalize(value[key], depth + 1, seen)],
      )];
    } catch (_error) {
      return ['opaque', Object.prototype.toString.call(value)];
    } finally {
      seen.delete(value);
    }
  }

  function encodedValue(value) {
    return JSON.stringify(canonicalize(value));
  }

  function settingKeys(settings, includeCommissioning = false) {
    return Object.keys(settings || {})
      .filter((key) => comparableKey(key, settings[key], includeCommissioning))
      .sort()
      .slice(0, MAX_SETTINGS);
  }

  function stateFingerprint(settings, includeCommissioning = false) {
    const keys = settingKeys(settings, includeCommissioning);
    return hash32(JSON.stringify(keys.map((key) => [key, encodedValue(settings[key])])));
  }

  function buildResetPlan(settings) {
    if (!settings || typeof settings.resetToDefaults !== 'function' || typeof settings.constructor !== 'function') {
      return {
        schema_version: 1,
        status: 'settings-unavailable',
        read_only: true,
        reset_available: false,
      };
    }

    let defaults;
    try {
      defaults = new settings.constructor();
    } catch (_error) {
      return {
        schema_version: 1,
        status: 'defaults-unavailable',
        read_only: true,
        reset_available: false,
      };
    }

    const keys = settingKeys(settings, false);
    const changed = keys.filter((key) => encodedValue(settings[key]) !== encodedValue(defaults[key]));
    return {
      schema_version: 1,
      status: 'ready',
      read_only: true,
      reset_available: changed.length > 0,
      change_count: changed.length,
      target_fingerprint: stateFingerprint(settings, false),
    };
  }

  function captureSnapshot(settings) {
    const values = new Map();
    for (const key of Object.keys(settings || {})) {
      if (typeof key !== 'string' || key.startsWith('_') || key === 'premium') continue;
      if (typeof settings[key] === 'function') continue;
      values.set(key, settings[key]);
    }
    return {
      values,
      fingerprint: stateFingerprint(settings, true),
    };
  }

  function restoreSnapshot(settings, snapshot) {
    for (const [key, value] of snapshot.values.entries()) settings[key] = value;
    return stateFingerprint(settings, true) === snapshot.fingerprint;
  }

  function applySettingsReset(settings, expectedFingerprint, confirmReset = false) {
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

    const plan = buildResetPlan(settings);
    if (plan.status !== 'ready') {
      return {
        schema_version: 1,
        status: plan.status,
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
    if (!plan.reset_available) {
      return {
        schema_version: 1,
        status: 'no-change',
        applied: false,
        rolled_back: false,
        applied_change_count: 0,
      };
    }

    const snapshot = captureSnapshot(settings);
    try {
      settings.resetToDefaults();
      const verified = buildResetPlan(settings);
      if (verified.status !== 'ready' || verified.reset_available) throw new Error('verification');
      const rollbackToken = randomToken();
      rollbackSnapshots.set(rollbackToken, { settings, snapshot });
      return {
        schema_version: 1,
        status: 'applied',
        applied: true,
        rolled_back: false,
        applied_change_count: plan.change_count,
        target_fingerprint: verified.target_fingerprint,
        rollback_token: rollbackToken,
      };
    } catch (_error) {
      let rolledBack = false;
      try {
        rolledBack = restoreSnapshot(settings, snapshot);
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

  function rollbackSettingsReset(rollbackToken, confirmRollback = false) {
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
      const verified = restoreSnapshot(entry.settings, entry.snapshot);
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

  function finalizeSettingsReset(rollbackToken) {
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

  function webpackRequire(win) {
    if (cachedWebpackRequire?.c) return cachedWebpackRequire;
    const names = Object.keys(win || {}).filter((name) => name.startsWith('webpackChunk'));
    for (const name of names) {
      const chunks = win[name];
      if (!Array.isArray(chunks) || typeof chunks.push !== 'function') continue;
      let candidate = null;
      try {
        const chunkId = Math.floor(1000000000 + Math.random() * 1000000000);
        chunks.push([[chunkId], {}, (runtime) => { candidate = runtime; }]);
      } catch (_error) {
        candidate = null;
      }
      if (candidate?.c && typeof candidate.c === 'object') {
        cachedWebpackRequire = candidate;
        return candidate;
      }
    }
    return null;
  }

  function locateSettings(win) {
    if (cachedSettings && typeof cachedSettings.resetToDefaults === 'function') return cachedSettings;
    const runtime = webpackRequire(win);
    if (!runtime?.c) return null;
    for (const module of Object.values(runtime.c)) {
      const exported = module?.exports;
      const candidates = [exported, exported?.default];
      for (const candidate of candidates) {
        const settings = candidate?.rootStore?.settings;
        if (settings && typeof settings.resetToDefaults === 'function') {
          cachedSettings = settings;
          return settings;
        }
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
        if (request.type === PLAN_REQUEST_TYPE) {
          responseType = PLAN_RESPONSE_TYPE;
          const settings = locateSettings(win);
          result = settings
            ? buildResetPlan(settings)
            : {
                schema_version: 1,
                status: 'runtime-unavailable',
                read_only: true,
                reset_available: false,
              };
        } else if (request.type === APPLY_REQUEST_TYPE) {
          responseType = APPLY_RESPONSE_TYPE;
          const settings = locateSettings(win);
          result = settings
            ? applySettingsReset(
                settings,
                request.target_fingerprint,
                request.confirm_reset === true,
              )
            : {
                schema_version: 1,
                status: 'runtime-unavailable',
                applied: false,
                rolled_back: false,
              };
        } else if (request.type === ROLLBACK_REQUEST_TYPE) {
          responseType = ROLLBACK_RESPONSE_TYPE;
          result = rollbackSettingsReset(
            request.rollback_token,
            request.confirm_rollback === true,
          );
        } else if (request.type === FINALIZE_REQUEST_TYPE) {
          responseType = FINALIZE_RESPONSE_TYPE;
          result = finalizeSettingsReset(request.rollback_token);
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
      win.parent.postMessage({ type: responseType, nonce: request.nonce, result }, event.origin);
    });
  }

  const api = {
    applySettingsReset,
    buildResetPlan,
    finalizeSettingsReset,
    locateSettings,
    rollbackSettingsReset,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') install(window);
})();
