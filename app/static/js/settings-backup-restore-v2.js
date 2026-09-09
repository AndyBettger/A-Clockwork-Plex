(() => {
  'use strict';

  // Dormant #89/#90 orchestration core. This module deliberately contains no
  // DOM wiring and is not loaded by Settings yet. The accepted schema-v1 UI
  // remains untouched until this cross-owner transaction is automated-green.

  const SAFE_FINGERPRINT = /^[a-f0-9]{8}$/;
  const SAFE_ROLLBACK_TOKEN = /^[a-f0-9]{32}$/;

  function plainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function cloneJson(value) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (_error) {
      return null;
    }
  }

  function cleanExportReportForV2(report) {
    const source = plainObject(report) ? report : {};
    const warnings = Array.isArray(source.warnings)
      ? source.warnings
        .filter((item) => typeof item === 'string')
        .filter((item) => !/^Plexamp (?:Settings directory|preference )/i.test(item))
        .map((item) => item.slice(0, 500))
      : [];
    const omitted = Array.isArray(source.omitted)
      ? source.omitted
        .filter((item) => plainObject(item) && typeof item.section === 'string' && typeof item.reason === 'string')
        .filter((item) => item.section !== 'plexamp.browser_preferences')
        .map((item) => ({ section: item.section.slice(0, 160), reason: item.reason.slice(0, 500) }))
      : [];
    return { warnings, omitted };
  }

  function validateNativeSnapshot(snapshot) {
    if (
      !plainObject(snapshot)
      || snapshot.schema_version !== 1
      || snapshot.status !== 'ready'
      || snapshot.read_only !== true
      || typeof snapshot.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(snapshot.settings_schema_fingerprint)
      || !plainObject(snapshot.settings)
      || !Number.isInteger(snapshot.saved_setting_count)
      || snapshot.saved_setting_count < 0
      || snapshot.saved_setting_count !== Object.keys(snapshot.settings).length
    ) return null;
    return {
      schema_version: 1,
      settings_schema_fingerprint: snapshot.settings_schema_fingerprint,
      settings: cloneJson(snapshot.settings),
    };
  }

  function validateHomeSnapshot(snapshot) {
    if (
      !plainObject(snapshot)
      || snapshot.schema_version !== 2
      || snapshot.status !== 'ready'
      || snapshot.read_only !== true
      || !plainObject(snapshot.home)
      || snapshot.home.schema_version !== 2
    ) return null;
    const home = cloneJson(snapshot.home);
    if (!home) return null;
    return home;
  }

  function assembleBackupV2(serverBackup, nativeSnapshot, homeSnapshot) {
    if (!plainObject(serverBackup) || serverBackup.schema_version !== 1) {
      throw new Error('schema-v2 assembly requires the secret-safe schema-v1 server export');
    }
    if (!plainObject(serverBackup.a_clockwork_plex)) {
      throw new Error('server export is missing A Clockwork Plex portable state');
    }
    const sourcePlexamp = plainObject(serverBackup.plexamp) ? serverBackup.plexamp : {};
    if (typeof sourcePlexamp.source_version !== 'string' || !sourcePlexamp.source_version.trim()) {
      throw new Error('server export is missing the verified Plexamp source version');
    }

    const portableSettings = validateNativeSnapshot(nativeSnapshot);
    if (!portableSettings) throw new Error('live Plexamp portable-settings snapshot is unavailable');
    const home = validateHomeSnapshot(homeSnapshot);
    if (!home) throw new Error('live Plexamp Home-v2 snapshot is unavailable');

    const result = cloneJson(serverBackup);
    if (!result) throw new Error('server export could not be cloned safely');
    result.schema_version = 2;
    result.plexamp = {
      source_version: sourcePlexamp.source_version,
      portable_settings: portableSettings,
      browser_preferences: {
        schema_version: 2,
        home,
      },
    };
    result.export_report = cleanExportReportForV2(result.export_report);
    return result;
  }

  function v2DesiredFromBackup(backup) {
    if (!plainObject(backup) || backup.schema_version !== 2 || !plainObject(backup.plexamp)) return null;
    const native = backup.plexamp.portable_settings;
    const browser = backup.plexamp.browser_preferences;
    if (
      !plainObject(native)
      || native.schema_version !== 1
      || typeof native.settings_schema_fingerprint !== 'string'
      || !SAFE_FINGERPRINT.test(native.settings_schema_fingerprint)
      || !plainObject(native.settings)
      || !plainObject(browser)
      || browser.schema_version !== 2
      || !plainObject(browser.home)
      || browser.home.schema_version !== 2
    ) return null;
    return {
      native: cloneJson(native),
      home: cloneJson(browser.home),
    };
  }

  async function previewBrowserOwners(backup, nativeClient, homeClient, options = {}) {
    const desired = v2DesiredFromBackup(backup);
    if (!desired) {
      return { ok: false, schema_version: 2, status: 'invalid-backup' };
    }
    if (typeof nativeClient?.plan !== 'function' || typeof homeClient?.plan !== 'function') {
      return { ok: false, schema_version: 2, status: 'client-unavailable' };
    }
    const timeoutMs = Math.max(250, Math.min(5000, Number(options.timeoutMs || 1800)));
    const [nativePlan, homePlan] = await Promise.all([
      nativeClient.plan(desired.native, { timeoutMs }),
      homeClient.plan(desired.home, { timeoutMs }),
    ]);
    const nativeReady = plainObject(nativePlan) && nativePlan.status === 'ready' && nativePlan.read_only === true;
    const homeReady = plainObject(homePlan) && homePlan.status === 'ready' && homePlan.read_only === true;
    const nativeChanges = nativeReady && nativePlan.restore_available === true
      ? Number(nativePlan.change_count || 0)
      : 0;
    const homeChanges = homeReady && homePlan.restore_available === true
      ? Number(homePlan.change_count || 0)
      : 0;
    return {
      ok: nativeReady && homeReady,
      schema_version: 2,
      status: nativeReady && homeReady ? 'ready' : 'browser-owner-unavailable',
      desired,
      native_plan: nativePlan,
      home_plan: homePlan,
      native_change_count: nativeChanges,
      home_change_count: homeChanges,
      change_count: nativeChanges + homeChanges,
    };
  }

  function ownerFailure(owner, result) {
    const status = String(result?.status || 'unavailable').replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80) || 'unavailable';
    const error = new Error(`${owner} restore was not applied (${status})`);
    error.owner = owner;
    error.ownerStatus = status;
    error.freshPreviewRequired = result?.fresh_preview_required === true || status === 'stale-target';
    error.ownerRolledBack = result?.rolled_back === true;
    return error;
  }

  async function rollbackRetained(retained) {
    const results = [];
    let allVerified = true;
    for (const entry of retained.slice().reverse()) {
      let result;
      try {
        result = await entry.client.rollback(entry.token, { timeoutMs: 3000 });
      } catch (error) {
        result = { status: 'rollback-exception', rolled_back: false, verified: false, error: String(error?.message || error) };
      }
      const verified = result?.rolled_back === true && result?.verified === true;
      if (!verified) allVerified = false;
      results.push({ owner: entry.owner, verified, status: String(result?.status || 'unavailable') });
    }
    return { all_verified: allVerified, results };
  }

  async function finalizeRetained(retained) {
    const results = [];
    let allFinalized = true;
    for (const entry of retained.slice().reverse()) {
      let result;
      try {
        result = await entry.client.finalize(entry.token, { timeoutMs: 1800 });
      } catch (error) {
        result = { status: 'finalize-exception', finalized: false, error: String(error?.message || error) };
      }
      const finalized = result?.finalized === true && result?.status === 'finalized';
      if (!finalized) allFinalized = false;
      results.push({ owner: entry.owner, finalized, status: String(result?.status || 'unavailable') });
    }
    return { all_finalized: allFinalized, results };
  }

  async function runRestoreTransaction({
    backup,
    browserPreview,
    nativeClient,
    homeClient,
    serverApply = null,
  } = {}) {
    const desired = v2DesiredFromBackup(backup);
    if (!desired) return { ok: false, schema_version: 2, status: 'invalid-backup', mutated: false };
    if (
      !plainObject(browserPreview)
      || browserPreview.ok !== true
      || browserPreview.status !== 'ready'
      || !plainObject(browserPreview.native_plan)
      || !plainObject(browserPreview.home_plan)
    ) return { ok: false, schema_version: 2, status: 'review-required', mutated: false };

    const retained = [];
    let browserAppliedCount = 0;
    let serverResult = null;
    let failedOwner = null;
    try {
      const nativePlan = browserPreview.native_plan;
      if (nativePlan.restore_available === true) {
        if (
          typeof nativeClient?.apply !== 'function'
          || typeof nativeClient?.rollback !== 'function'
          || typeof nativeClient?.finalize !== 'function'
          || typeof nativePlan.target_fingerprint !== 'string'
          || !SAFE_FINGERPRINT.test(nativePlan.target_fingerprint)
        ) throw ownerFailure('Plexamp settings', { status: 'invalid-review' });
        const result = await nativeClient.apply(desired.native, nativePlan.target_fingerprint, { timeoutMs: 3000 });
        if (
          result?.status !== 'applied'
          || result?.applied !== true
          || typeof result.rollback_token !== 'string'
          || !SAFE_ROLLBACK_TOKEN.test(result.rollback_token)
        ) throw ownerFailure('Plexamp settings', result);
        retained.push({ owner: 'plexamp-settings', client: nativeClient, token: result.rollback_token });
        browserAppliedCount += Number(result.applied_change_count || 0);
      }

      const homePlan = browserPreview.home_plan;
      if (homePlan.restore_available === true) {
        if (
          typeof homeClient?.apply !== 'function'
          || typeof homeClient?.rollback !== 'function'
          || typeof homeClient?.finalize !== 'function'
          || typeof homePlan.target_fingerprint !== 'string'
          || !SAFE_FINGERPRINT.test(homePlan.target_fingerprint)
        ) throw ownerFailure('Plexamp Home', { status: 'invalid-review' });
        const result = await homeClient.apply(desired.home, homePlan.target_fingerprint, { timeoutMs: 3000 });
        if (
          result?.status !== 'applied'
          || result?.applied !== true
          || typeof result.rollback_token !== 'string'
          || !SAFE_ROLLBACK_TOKEN.test(result.rollback_token)
        ) throw ownerFailure('Plexamp Home', result);
        retained.push({ owner: 'plexamp-home', client: homeClient, token: result.rollback_token });
        browserAppliedCount += Number(result.applied_change_count || 0);
      }

      if (serverApply !== null) {
        if (typeof serverApply !== 'function') throw new Error('server restore participant is invalid');
        failedOwner = 'a-clockwork-plex';
        serverResult = await serverApply();
        if (!plainObject(serverResult) || serverResult.ok === false) {
          const error = new Error(String(serverResult?.error || 'server restore participant failed'));
          error.owner = 'A Clockwork Plex';
          error.ownerRolledBack = serverResult?.rolled_back === true;
          error.freshPreviewRequired = serverResult?.fresh_preview_required === true;
          throw error;
        }
        failedOwner = null;
      }

      const finalized = await finalizeRetained(retained);
      return {
        ok: true,
        schema_version: 2,
        status: 'applied',
        mutated: browserAppliedCount > 0 || serverResult !== null,
        browser_applied_change_count: browserAppliedCount,
        server_result: serverResult,
        finalization: finalized,
        warnings: finalized.all_finalized
          ? []
          : ['Restore verified, but one or more in-memory browser rollback tokens could not be finalized. Reloading the Settings page will discard them.'],
      };
    } catch (error) {
      failedOwner = failedOwner || error?.owner || 'browser-owner';
      const rollback = await rollbackRetained(retained);
      return {
        ok: false,
        schema_version: 2,
        status: error?.freshPreviewRequired === true ? 'stale-target' : 'apply-failed',
        mutated: retained.length > 0,
        failed_owner: String(failedOwner),
        error: String(error?.message || error || 'Restore failed.'),
        owner_self_rolled_back: error?.ownerRolledBack === true,
        browser_rollback: rollback,
        browser_applied_change_count: browserAppliedCount,
        server_result: serverResult,
        fresh_preview_required: error?.freshPreviewRequired === true,
      };
    }
  }

  const api = {
    assembleBackupV2,
    cleanExportReportForV2,
    previewBrowserOwners,
    runRestoreTransaction,
    v2DesiredFromBackup,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.ACPConfigurationBackupRestoreV2 = api;
})();
