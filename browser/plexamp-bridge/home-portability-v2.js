(() => {
  'use strict';

  // Dormant #89/#90 Home-v2 owner. This file is intentionally not loaded by
  // the production extension manifest until the complete transaction has
  // automated and commissioned-Pi acceptance.

  const MMKV_PREFIX = 'mmkv.default\\';
  const CUSTOM_PREFIX = 'discovery:customizations:';
  const LIBRARY_RE = /^\/library\/sections\/([0-9]{1,10})$/;
  const SAFE_CONTEXT = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_HUB = /^[A-Za-z0-9_.:/%+@~=\-]{1,600}$/;
  const SAFE_KIND = /^[A-Za-z0-9_-]{1,64}$/;
  const SAFE_REF = /^custom-[1-9][0-9]{0,5}$/;
  const SAFE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;
  const CUSTOM_HUB_RE = /^custom\.hub\.([A-Za-z0-9_-]{1,64})\.([0-9a-f-]{36})$/i;
  const SENSITIVE_NAME = /(token|auth|account|session|cookie|credential|password|secret|claim|machine|clientidentifier|email)/i;
  const PRESENTATION_FIELDS = new Set(['type', 'subtype', 'size', 'limit', 'title']);

  const MAX_STORAGE_KEYS = 2048;
  const MAX_RECORDS = 256;
  const MAX_RECORD_BYTES = 32768;
  const MAX_TOTAL_BYTES = 262144;
  const MAX_ORDER_ITEMS = 256;
  const MAX_CUSTOM_HUBS = 128;
  const MAX_QUERY_CHARS = 2048;
  const MAX_TITLE_CHARS = 240;

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

  function plainObject(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  function jsonClone(value) {
    try {
      const encoded = JSON.stringify(value);
      if (typeof encoded !== 'string') return null;
      return JSON.parse(encoded);
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

  function deriveTargetScope(rootStore) {
    const server = rootStore?.app?.server;
    const library = rootStore?.app?.library;
    const libraryMatch = typeof library === 'string' ? library.match(LIBRARY_RE) : null;
    if (
      typeof server !== 'string'
      || !SAFE_CONTEXT.test(server)
      || SENSITIVE_NAME.test(server)
      || !libraryMatch
    ) return null;

    const section = libraryMatch[1];
    const structureContext = server;
    const presentationContext = `${CUSTOM_PREFIX}${server}`;
    if (!SAFE_CONTEXT.test(presentationContext)) return null;

    const structureBaseKey = `${MMKV_PREFIX}${CUSTOM_PREFIX}${structureContext}::${library}`;
    const presentationBaseKey = `${MMKV_PREFIX}${CUSTOM_PREFIX}${presentationContext}::${library}`;
    return {
      section,
      library,
      structureContext,
      presentationContext,
      structureBaseKey,
      presentationBaseKey,
    };
  }

  function decodeMmkv(raw) {
    if (typeof raw !== 'string' || raw.length > MAX_RECORD_BYTES) return { ok: false, value: null };
    try {
      const parsed = JSON.parse(raw);
      if (!plainObject(parsed)) return { ok: false, value: null };
      const keys = Object.keys(parsed);
      if (keys.length !== 1 || keys[0] !== '_') return { ok: false, value: null };
      const value = jsonClone(parsed._);
      return value === null && parsed._ !== null
        ? { ok: false, value: null }
        : { ok: true, value };
    } catch (_error) {
      return { ok: false, value: null };
    }
  }

  function encodeMmkv(value) {
    const cloned = jsonClone(value);
    if (cloned === null && value !== null) return null;
    const raw = JSON.stringify({ _: cloned });
    return raw.length <= MAX_RECORD_BYTES ? raw : null;
  }

  function parseScopedKey(key, scope) {
    if (typeof key !== 'string') return null;
    let role = null;
    let tail = null;
    if (key === `${scope.structureBaseKey}:order`) {
      return { role: 'structure', family: 'order', hub: null };
    }
    if (key === `${scope.structureBaseKey}:customHubs`) {
      return { role: 'structure', family: 'customHubs', hub: null };
    }
    if (key.startsWith(`${scope.structureBaseKey}:`)) {
      role = 'structure';
      tail = key.slice(scope.structureBaseKey.length + 1);
    } else if (key.startsWith(`${scope.presentationBaseKey}:`)) {
      role = 'presentation';
      tail = key.slice(scope.presentationBaseKey.length + 1);
    } else {
      return null;
    }

    const colon = tail.lastIndexOf(':');
    if (colon < 1) return { role, family: 'other', hub: null };
    const hub = tail.slice(0, colon);
    const terminal = tail.slice(colon + 1);
    if (!SAFE_HUB.test(hub) || SENSITIVE_NAME.test(terminal)) {
      return { role, family: 'other', hub: null };
    }
    if (role === 'structure' && terminal === 'hidden') return { role, family: 'hidden', hub };
    if (role === 'structure' && terminal === 'editing') return { role, family: 'editing', hub };
    if (role === 'presentation' && terminal === 'viewSettings') {
      return { role, family: 'viewSettings', hub };
    }
    return { role, family: 'other', hub };
  }

  function parseCustomHubIdentifier(value) {
    if (typeof value !== 'string') return null;
    const match = value.match(CUSTOM_HUB_RE);
    if (!match || !SAFE_KIND.test(match[1]) || !SAFE_UUID.test(match[2])) return null;
    return { kind: match[1], uuid: match[2].toLowerCase() };
  }

  function normalizeQuerySuffix(fullKey, library) {
    if (typeof fullKey !== 'string' || !fullKey.startsWith(library)) return null;
    const suffix = fullKey.slice(library.length);
    if (
      !suffix.startsWith('/')
      || suffix.length > MAX_QUERY_CHARS
      || suffix.includes('\\')
      || suffix.includes('://')
      || suffix.includes('#')
      || SENSITIVE_NAME.test(suffix)
      || Array.from(suffix).some((char) => char.codePointAt(0) < 32)
    ) return null;
    const path = suffix.split('?', 1)[0];
    if (path.split('/').some((part) => part === '..' || part === '.')) return null;
    return suffix;
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
      || Array.from(value).some((char) => char.codePointAt(0) < 32)
    ) return false;
    const path = value.split('?', 1)[0];
    return !path.split('/').some((part) => part === '..' || part === '.');
  }

  function validatePresentation(value) {
    if (!plainObject(value)) return null;
    const keys = Object.keys(value);
    if (keys.some((key) => !PRESENTATION_FIELDS.has(key))) return null;
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

  function collectScope(storage, scope) {
    const records = [];
    const decoded = [];
    let totalBytes = 0;
    const length = Number(storage?.length || 0);
    if (!Number.isFinite(length) || length < 0 || length > MAX_STORAGE_KEYS) {
      return { status: 'storage-key-limit-exceeded', records: [], decoded: [], fingerprint: null };
    }

    for (let index = 0; index < length; index += 1) {
      const key = storage.key(index);
      const classified = parseScopedKey(key, scope);
      if (!classified) continue;
      if (classified.family === 'other') {
        return { status: 'unclassified-customization-key', records: [], decoded: [], fingerprint: null };
      }
      if (classified.family === 'editing') {
        return { status: 'editing-active', records: [], decoded: [], fingerprint: null };
      }
      if (records.length >= MAX_RECORDS) {
        return { status: 'record-limit-exceeded', records: [], decoded: [], fingerprint: null };
      }
      const raw = storage.getItem(key);
      if (typeof raw !== 'string') {
        return { status: 'storage-value-unavailable', records: [], decoded: [], fingerprint: null };
      }
      if (raw.length > MAX_RECORD_BYTES) {
        return { status: 'record-size-limit-exceeded', records: [], decoded: [], fingerprint: null };
      }
      totalBytes += raw.length;
      if (totalBytes > MAX_TOTAL_BYTES) {
        return { status: 'total-size-limit-exceeded', records: [], decoded: [], fingerprint: null };
      }
      const value = decodeMmkv(raw);
      if (!value.ok) {
        return { status: 'unsupported-mmkv-wrapper', records: [], decoded: [], fingerprint: null };
      }
      records.push({ key, raw });
      decoded.push({ ...classified, key, value: value.value });
    }

    records.sort((left, right) => left.key.localeCompare(right.key));
    decoded.sort((left, right) => left.key.localeCompare(right.key));
    return {
      status: 'ready',
      records,
      decoded,
      fingerprint: hash32(JSON.stringify(records.map((record) => [record.key, record.raw]))),
    };
  }

  function logicalRef(hub, customById) {
    if (customById.has(hub)) return { type: 'custom', ref: customById.get(hub).ref };
    if (parseCustomHubIdentifier(hub)) return null;
    if (!SAFE_HUB.test(hub) || SENSITIVE_NAME.test(hub)) return null;
    return { type: 'builtin', id: hub };
  }

  function buildLogicalHome(inventory, scope) {
    if (inventory.status !== 'ready') return { status: inventory.status, home: null };

    const orderRows = inventory.decoded.filter((row) => row.family === 'order');
    const customRows = inventory.decoded.filter((row) => row.family === 'customHubs');
    if (orderRows.length > 1 || customRows.length > 1) return { status: 'duplicate-singleton-family', home: null };

    const customItems = customRows.length ? customRows[0].value : [];
    if (!Array.isArray(customItems) || customItems.length > MAX_CUSTOM_HUBS) {
      return { status: 'unsupported-custom-hubs', home: null };
    }

    const customById = new Map();
    const customSections = [];
    for (let index = 0; index < customItems.length; index += 1) {
      const item = customItems[index];
      if (!plainObject(item)) return { status: 'unsupported-custom-hub-item', home: null };
      const keys = Object.keys(item).sort();
      if (JSON.stringify(keys) !== JSON.stringify(['hubIdentifier', 'key', 'source'])) {
        return { status: 'unsupported-custom-hub-item', home: null };
      }
      const parsedId = parseCustomHubIdentifier(item.hubIdentifier);
      const querySuffix = normalizeQuerySuffix(item.key, scope.library);
      if (!parsedId || !querySuffix || item.source !== scope.structureContext || customById.has(item.hubIdentifier)) {
        return { status: 'unsupported-custom-hub-item', home: null };
      }
      const ref = `custom-${index + 1}`;
      const section = { ref, kind: parsedId.kind, query_suffix: querySuffix };
      customById.set(item.hubIdentifier, section);
      customSections.push(section);
    }

    let order = [];
    if (orderRows.length) {
      const value = orderRows[0].value;
      if (!Array.isArray(value) || value.length > MAX_ORDER_ITEMS) return { status: 'unsupported-order', home: null };
      const seen = new Set();
      for (const hub of value) {
        if (typeof hub !== 'string' || seen.has(hub)) return { status: 'unsupported-order', home: null };
        seen.add(hub);
        const ref = logicalRef(hub, customById);
        if (!ref) return { status: 'dangling-custom-reference', home: null };
        order.push(ref);
      }
    }

    const hidden = [];
    const hiddenSeen = new Set();
    for (const row of inventory.decoded.filter((item) => item.family === 'hidden')) {
      if (row.value !== true || hiddenSeen.has(row.hub)) return { status: 'unsupported-hidden', home: null };
      hiddenSeen.add(row.hub);
      const ref = logicalRef(row.hub, customById);
      if (!ref) return { status: 'dangling-custom-reference', home: null };
      hidden.push(ref);
    }

    const presentation = [];
    const presentationSeen = new Set();
    for (const row of inventory.decoded.filter((item) => item.family === 'viewSettings')) {
      if (presentationSeen.has(row.hub)) return { status: 'duplicate-presentation', home: null };
      presentationSeen.add(row.hub);
      const ref = logicalRef(row.hub, customById);
      const settings = validatePresentation(row.value);
      if (!ref || !settings || Object.keys(settings).length === 0) {
        return { status: 'unsupported-view-settings', home: null };
      }
      presentation.push({ target: ref, settings });
    }

    for (const custom of customSections) {
      if (!presentation.some((row) => row.target.type === 'custom' && row.target.ref === custom.ref)) {
        return { status: 'custom-presentation-missing', home: null };
      }
    }

    return {
      status: 'ready',
      home: {
        schema_version: 2,
        order,
        hidden,
        presentation,
        custom_sections: customSections,
      },
    };
  }

  function buildPortableSnapshot(storage, rootStore) {
    const scope = deriveTargetScope(rootStore);
    if (!scope) {
      return { schema_version: 2, status: 'target-context-unavailable', read_only: true };
    }
    const inventory = collectScope(storage, scope);
    const logical = buildLogicalHome(inventory, scope);
    if (logical.status !== 'ready') {
      return { schema_version: 2, status: logical.status, read_only: true };
    }
    return {
      schema_version: 2,
      status: 'ready',
      read_only: true,
      target_fingerprint: inventory.fingerprint,
      home: logical.home,
    };
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

  function validatePortableHome(value) {
    if (!plainObject(value)) return null;
    const allowed = ['custom_sections', 'hidden', 'order', 'presentation', 'schema_version'];
    if (JSON.stringify(Object.keys(value).sort()) !== JSON.stringify(allowed)) return null;
    if (value.schema_version !== 2) return null;
    if (
      !Array.isArray(value.order)
      || !Array.isArray(value.hidden)
      || !Array.isArray(value.presentation)
      || !Array.isArray(value.custom_sections)
      || value.order.length > MAX_ORDER_ITEMS
      || value.hidden.length > MAX_ORDER_ITEMS
      || value.presentation.length > MAX_ORDER_ITEMS
      || value.custom_sections.length > MAX_CUSTOM_HUBS
    ) return null;

    const customRefs = new Set();
    const customSections = [];
    for (const item of value.custom_sections) {
      if (!plainObject(item) || Object.keys(item).sort().join(',') !== 'kind,query_suffix,ref') return null;
      if (!SAFE_REF.test(item.ref) || customRefs.has(item.ref) || !SAFE_KIND.test(item.kind) || !validateQuerySuffix(item.query_suffix)) {
        return null;
      }
      customRefs.add(item.ref);
      customSections.push({ ref: item.ref, kind: item.kind, query_suffix: item.query_suffix });
    }

    const parseRefList = (items) => {
      const result = [];
      const seen = new Set();
      for (const item of items) {
        const ref = validateLogicalRef(item, customRefs);
        if (!ref) return null;
        const encoded = JSON.stringify(ref);
        if (seen.has(encoded)) return null;
        seen.add(encoded);
        result.push(ref);
      }
      return result;
    };

    const order = parseRefList(value.order);
    const hidden = parseRefList(value.hidden);
    if (!order || !hidden) return null;

    const presentation = [];
    const seenPresentation = new Set();
    for (const row of value.presentation) {
      if (!plainObject(row) || Object.keys(row).sort().join(',') !== 'settings,target') return null;
      const target = validateLogicalRef(row.target, customRefs);
      const settings = validatePresentation(row.settings);
      if (!target || !settings || Object.keys(settings).length === 0) return null;
      const encoded = JSON.stringify(target);
      if (seenPresentation.has(encoded)) return null;
      seenPresentation.add(encoded);
      presentation.push({ target, settings });
    }

    for (const ref of customRefs) {
      if (!presentation.some((row) => row.target.type === 'custom' && row.target.ref === ref)) return null;
    }

    return {
      schema_version: 2,
      order,
      hidden,
      presentation,
      custom_sections: customSections,
    };
  }

  function makeCustomHubIdentifier(kind, uuidFactory) {
    if (!SAFE_KIND.test(kind) || typeof uuidFactory !== 'function') return null;
    let uuid;
    try {
      uuid = String(uuidFactory()).toLowerCase();
    } catch (_error) {
      return null;
    }
    if (!SAFE_UUID.test(uuid)) return null;
    return `custom.hub.${kind}.${uuid}`;
  }

  function resolveLogicalRef(ref, customIds) {
    if (ref.type === 'builtin') return ref.id;
    return customIds.get(ref.ref) || null;
  }

  function materializePortableHome(value, rootStore, uuidFactory = () => globalThis.crypto.randomUUID()) {
    const home = validatePortableHome(value);
    const scope = deriveTargetScope(rootStore);
    if (!home || !scope) return { status: 'invalid-request', records: [] };

    const customIds = new Map();
    const customItems = [];
    for (const section of home.custom_sections) {
      const hubIdentifier = makeCustomHubIdentifier(section.kind, uuidFactory);
      if (!hubIdentifier || customIds.has(section.ref)) return { status: 'uuid-unavailable', records: [] };
      customIds.set(section.ref, hubIdentifier);
      customItems.push({
        key: `${scope.library}${section.query_suffix}`,
        hubIdentifier,
        source: scope.structureContext,
      });
    }

    const records = [];
    const add = (key, value) => {
      const raw = encodeMmkv(value);
      if (raw === null) return false;
      records.push({ key, raw });
      return true;
    };

    if (customItems.length && !add(`${scope.structureBaseKey}:customHubs`, customItems)) {
      return { status: 'serialization-failed', records: [] };
    }

    if (home.order.length) {
      const order = home.order.map((ref) => resolveLogicalRef(ref, customIds));
      if (order.some((hub) => !hub) || !add(`${scope.structureBaseKey}:order`, order)) {
        return { status: 'serialization-failed', records: [] };
      }
    }

    for (const ref of home.hidden) {
      const hub = resolveLogicalRef(ref, customIds);
      if (!hub || !add(`${scope.structureBaseKey}:${hub}:hidden`, true)) {
        return { status: 'serialization-failed', records: [] };
      }
    }

    for (const row of home.presentation) {
      const hub = resolveLogicalRef(row.target, customIds);
      if (!hub || !add(`${scope.presentationBaseKey}:${hub}:viewSettings`, row.settings)) {
        return { status: 'serialization-failed', records: [] };
      }
    }

    if (records.length > MAX_RECORDS) return { status: 'record-limit-exceeded', records: [] };
    records.sort((left, right) => left.key.localeCompare(right.key));
    const totalBytes = records.reduce((total, record) => total + record.raw.length, 0);
    if (totalBytes > MAX_TOTAL_BYTES) return { status: 'total-size-limit-exceeded', records: [] };

    return { status: 'ready', records };
  }

  function logicalEqual(left, right) {
    return JSON.stringify(left) === JSON.stringify(right);
  }

  function buildRestorePlan(storage, rootStore, desiredHome) {
    const desired = validatePortableHome(desiredHome);
    const current = buildPortableSnapshot(storage, rootStore);
    if (!desired) {
      return { schema_version: 2, status: 'invalid-request', read_only: true, restore_available: false };
    }
    if (current.status !== 'ready') {
      return { schema_version: 2, status: current.status, read_only: true, restore_available: false };
    }
    const changed = !logicalEqual(current.home, desired);
    return {
      schema_version: 2,
      status: 'ready',
      read_only: true,
      restore_available: changed,
      target_fingerprint: current.target_fingerprint,
      current_record_count: collectScope(storage, deriveTargetScope(rootStore)).records.length,
    };
  }

  function exactFingerprint(records) {
    return hash32(JSON.stringify(
      records.slice().sort((left, right) => left.key.localeCompare(right.key)).map((record) => [record.key, record.raw]),
    ));
  }

  function removeRecords(storage, records) {
    for (const record of records) storage.removeItem(record.key);
  }

  function restoreExactRecords(storage, rootStore, records, expectedCurrentFingerprint = null) {
    const scope = deriveTargetScope(rootStore);
    if (!scope) return false;
    const current = collectScope(storage, scope);
    if (current.status !== 'ready') return false;
    if (expectedCurrentFingerprint && current.fingerprint !== expectedCurrentFingerprint) return false;
    removeRecords(storage, current.records);
    const emptied = collectScope(storage, scope);
    if (emptied.status !== 'ready' || emptied.records.length !== 0) return false;
    for (const record of records) storage.setItem(record.key, record.raw);
    const restored = collectScope(storage, scope);
    return restored.status === 'ready' && restored.fingerprint === exactFingerprint(records);
  }

  function applyPortableHome(
    storage,
    rootStore,
    desiredHome,
    expectedFingerprint,
    confirmRestore = false,
    uuidFactory = () => globalThis.crypto.randomUUID(),
  ) {
    if (confirmRestore !== true) {
      return { schema_version: 2, status: 'confirmation-required', applied: false, rolled_back: false };
    }
    if (typeof expectedFingerprint !== 'string' || !SAFE_FINGERPRINT.test(expectedFingerprint)) {
      return { schema_version: 2, status: 'invalid-fingerprint', applied: false, rolled_back: false };
    }

    const plan = buildRestorePlan(storage, rootStore, desiredHome);
    if (plan.status !== 'ready') {
      return { schema_version: 2, status: plan.status, applied: false, rolled_back: false };
    }
    if (plan.target_fingerprint !== expectedFingerprint) {
      return {
        schema_version: 2,
        status: 'stale-target',
        applied: false,
        rolled_back: false,
        fresh_preview_required: true,
      };
    }
    if (!plan.restore_available) {
      return { schema_version: 2, status: 'no-change', applied: false, rolled_back: false };
    }

    const scope = deriveTargetScope(rootStore);
    const before = collectScope(storage, scope);
    const materialized = materializePortableHome(desiredHome, rootStore, uuidFactory);
    if (before.status !== 'ready' || materialized.status !== 'ready') {
      return {
        schema_version: 2,
        status: materialized.status === 'ready' ? before.status : materialized.status,
        applied: false,
        rolled_back: false,
      };
    }

    try {
      removeRecords(storage, before.records);
      const empty = collectScope(storage, scope);
      if (empty.status !== 'ready' || empty.records.length !== 0) throw new Error('clear-verification');
      for (const record of materialized.records) storage.setItem(record.key, record.raw);

      const verified = buildPortableSnapshot(storage, rootStore);
      if (verified.status !== 'ready' || !logicalEqual(verified.home, validatePortableHome(desiredHome))) {
        throw new Error('logical-verification');
      }
      const after = collectScope(storage, scope);
      if (after.status !== 'ready') throw new Error('target-verification');

      const rollbackToken = randomToken();
      rollbackSnapshots.set(rollbackToken, {
        storage,
        rootStore,
        beforeRecords: before.records,
        appliedFingerprint: after.fingerprint,
      });
      return {
        schema_version: 2,
        status: 'applied',
        applied: true,
        rolled_back: false,
        target_fingerprint: after.fingerprint,
        rollback_token: rollbackToken,
      };
    } catch (_error) {
      let rolledBack = false;
      try {
        const current = collectScope(storage, scope);
        rolledBack = current.status === 'ready'
          && restoreExactRecords(storage, rootStore, before.records, current.fingerprint);
      } catch (_rollbackError) {
        rolledBack = false;
      }
      return {
        schema_version: 2,
        status: 'apply-failed',
        applied: false,
        rolled_back: rolledBack,
        fresh_preview_required: true,
      };
    }
  }

  function rollbackPortableHome(rollbackToken, confirmRollback = false) {
    if (
      confirmRollback !== true
      || typeof rollbackToken !== 'string'
      || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)
    ) {
      return { schema_version: 2, status: 'invalid-request', rolled_back: false, verified: false };
    }
    const entry = rollbackSnapshots.get(rollbackToken);
    if (!entry) {
      return { schema_version: 2, status: 'rollback-unavailable', rolled_back: false, verified: false };
    }
    const scope = deriveTargetScope(entry.rootStore);
    const current = scope ? collectScope(entry.storage, scope) : { status: 'scope-unavailable' };
    if (current.status !== 'ready' || current.fingerprint !== entry.appliedFingerprint) {
      return {
        schema_version: 2,
        status: 'rollback-stale-target',
        rolled_back: false,
        verified: false,
        fresh_preview_required: true,
      };
    }
    const verified = restoreExactRecords(
      entry.storage,
      entry.rootStore,
      entry.beforeRecords,
      entry.appliedFingerprint,
    );
    if (!verified) {
      return { schema_version: 2, status: 'rollback-failed', rolled_back: false, verified: false };
    }
    rollbackSnapshots.delete(rollbackToken);
    return { schema_version: 2, status: 'rolled-back', rolled_back: true, verified: true };
  }

  function finalizePortableHome(rollbackToken) {
    if (typeof rollbackToken !== 'string' || !SAFE_ROLLBACK_TOKEN.test(rollbackToken)) {
      return { schema_version: 2, status: 'invalid-request', finalized: false };
    }
    const existed = rollbackSnapshots.delete(rollbackToken);
    return {
      schema_version: 2,
      status: existed ? 'finalized' : 'rollback-unavailable',
      finalized: existed,
    };
  }

  const api = {
    applyPortableHome,
    buildPortableSnapshot,
    buildRestorePlan,
    collectScope,
    decodeMmkv,
    deriveTargetScope,
    encodeMmkv,
    finalizePortableHome,
    materializePortableHome,
    parseCustomHubIdentifier,
    rollbackPortableHome,
    validatePortableHome,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();