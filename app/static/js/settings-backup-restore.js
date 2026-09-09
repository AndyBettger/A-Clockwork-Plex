(() => {
  'use strict';

  // Complete #89/#90 Settings owner. Kept dormant until its source/transaction
  // integration gate is green; settings-about.js remains the production v1
  // owner until the deliberate activation commit.
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexBackupRestoreLoaded) return;
  window.__aClockworkPlexBackupRestoreLoaded = true;

  const advanced = document.querySelector('[data-settings-section="advanced"]');
  const overview = advanced?.querySelector('[data-settings-overview="advanced"]');
  if (!advanced || !overview || advanced.querySelector('[data-settings-subpage="advanced:backup"]')) return;

  const MAX_RESTORE_FILE_BYTES = 1_000_000;
  const RESTORE_RESULT_KEY = 'acp-configuration-restore-result-v1';
  const SCRIPT_PROMISES = new Map();

  function plainObject(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function safeStatus(value) {
    return String(value || 'unavailable').replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80) || 'unavailable';
  }

  function loadScript(src, ready) {
    if (ready()) return Promise.resolve(true);
    if (SCRIPT_PROMISES.has(src)) return SCRIPT_PROMISES.get(src);
    const promise = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.addEventListener('load', () => resolve(Boolean(ready())), { once: true });
      script.addEventListener('error', () => resolve(false), { once: true });
      document.head.append(script);
    });
    SCRIPT_PROMISES.set(src, promise);
    return promise;
  }

  function v1Ready() {
    return Boolean(
      window.ACPPlexampBrowserPreferences?.snapshot
      && window.ACPPlexampBrowserPreferences?.planHome
      && window.ACPPlexampBrowserPreferences?.applyHome
    );
  }

  async function loadV1Client() {
    return loadScript(
      '/static/js/plexamp-browser-bridge.js?v=20260831-home-restore-v1',
      v1Ready,
    );
  }

  function v2Ready() {
    return Boolean(
      window.ACPConfigurationBackupRestoreV2?.assembleBackupV2
      && window.ACPConfigurationBackupRestoreV2?.previewBrowserOwners
      && window.ACPConfigurationBackupRestoreV2?.runRestoreTransaction
      && window.ACPPlexampNativePortability?.snapshot
      && window.ACPPlexampNativePortability?.plan
      && window.ACPPlexampNativePortability?.apply
      && window.ACPPlexampNativePortability?.rollback
      && window.ACPPlexampNativePortability?.finalize
      && window.ACPPlexampHomePortabilityV2?.snapshot
      && window.ACPPlexampHomePortabilityV2?.plan
      && window.ACPPlexampHomePortabilityV2?.apply
      && window.ACPPlexampHomePortabilityV2?.rollback
      && window.ACPPlexampHomePortabilityV2?.finalize
    );
  }

  async function loadV2Stack() {
    if (v2Ready()) return true;
    const core = await loadScript(
      '/static/js/settings-backup-restore-v2.js?v=20260910-v2-transaction-v1',
      () => Boolean(window.ACPConfigurationBackupRestoreV2?.runRestoreTransaction),
    );
    if (!core) return false;
    const native = await loadScript(
      '/static/js/plexamp-native-portability-bridge.js?v=20260910-portability-v1',
      () => Boolean(window.ACPPlexampNativePortability?.snapshot),
    );
    if (!native) return false;
    const home = await loadScript(
      '/static/js/plexamp-home-portability-v2-bridge.js?v=20260910-portability-v1',
      () => Boolean(window.ACPPlexampHomePortabilityV2?.snapshot),
    );
    return home && v2Ready();
  }

  const row = document.createElement('button');
  row.className = 'settings-subpage-row';
  row.type = 'button';
  row.dataset.settingsSubpageTarget = 'advanced:backup';
  row.innerHTML = '<span><strong>Backup &amp; restore</strong><small>Portable appliance configuration</small></span><span>›</span>';
  overview.append(row);

  const page = document.createElement('section');
  page.className = 'settings-subpage';
  page.dataset.settingsSubpage = 'advanced:backup';
  page.hidden = true;
  page.innerHTML = `
    <button class="settings-back" type="button" data-settings-back="advanced">‹ Advanced</button>
    <section class="settings-card">
      <div class="settings-card-heading">
        <div>
          <h3>Configuration backup</h3>
          <p class="muted small">Download a versioned, portable copy of user-owned appliance and Plexamp choices.</p>
        </div>
        <span class="settings-chip">Secret-free</span>
      </div>
      <p class="muted small">A complete backup includes ordinary Settings, alarms, EQ and mixer levels plus portable Plexamp settings and logical Home customisation when the local bridge is available. Weather Underground API keys, Plex authentication, browser sessions, player/device identity, hardware bindings, caches and runtime state are deliberately excluded.</p>
      <div class="settings-action-row">
        <button class="button" type="button" data-action="download-configuration-backup">Download backup</button>
        <span class="muted small" data-configuration-backup-message>Ready to create a portable backup.</span>
      </div>
    </section>
    <section class="settings-card">
      <div class="settings-card-heading">
        <div>
          <h3>Restore</h3>
          <p class="muted small">Choose a backup, preview it, choose what to restore, review the selected work, then confirm once.</p>
        </div>
        <span class="settings-chip">Rollback protected</span>
      </div>
      <p class="muted small"><strong>Preview and Review never change the appliance.</strong> Only the final Confirm &amp; restore action can apply supported configuration.</p>
      <label class="setting-field">
        <span>Backup file</span>
        <input type="file" accept=".json,application/json" data-configuration-restore-file>
        <small data-configuration-restore-file-status>Select an A Clockwork Plex JSON backup, up to 1 MB.</small>
      </label>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-action="preview-configuration-restore" disabled>Preview restore</button>
      </div>
      <div class="settings-restore-status" data-configuration-restore-preview-status hidden aria-live="polite">
        <span class="settings-chip" data-configuration-restore-status-pill>Preview</span>
        <span data-configuration-restore-message>No file selected.</span>
      </div>
      <div data-configuration-restore-preview hidden>
        <div class="settings-restore-target-heading">
          <div>
            <h4>Choose what to restore</h4>
            <p class="muted small">Select A Clockwork Plex, Plexamp, or both. Only currently restorable differences are applied.</p>
          </div>
          <span class="settings-chip" data-configuration-restore-total-summary>0 restorable</span>
        </div>
        <div class="settings-restore-target-grid" role="group" aria-label="Restore targets">
          <button class="settings-restore-target" type="button" data-configuration-restore-target="acp" aria-pressed="false" disabled>
            <span class="settings-restore-target-title"><strong>A Clockwork Plex</strong><span class="settings-chip" data-configuration-restore-acp-summary data-configuration-restore-server-count>No changes</span></span>
            <small>Settings, alarms, Master EQ and persistent mixer.</small>
          </button>
          <button class="settings-restore-target" type="button" data-configuration-restore-target="plexamp" aria-pressed="false" disabled>
            <span class="settings-restore-target-title"><strong>Plexamp</strong><span class="settings-chip" data-configuration-restore-plexamp-summary>No changes</span></span>
            <small>Portable Plexamp settings plus logical Home choices. <span data-configuration-restore-headless-summary>Settings: no changes</span> · <span data-configuration-restore-browser-summary>Home: not present</span></small>
          </button>
        </div>
        <div class="settings-restore-warning" data-configuration-restore-warning-box hidden>
          <strong>Warnings</strong>
          <ul class="muted small" data-configuration-restore-warnings></ul>
        </div>
        <details class="settings-restore-details">
          <summary>Preview details</summary>
          <div class="settings-restore-detail-grid">
            <div><strong>Changed sections</strong><ul class="muted small" data-configuration-restore-sections></ul></div>
            <div><strong>Technical changed paths</strong><ul class="muted small" data-configuration-restore-paths></ul></div>
          </div>
        </details>
        <div data-configuration-restore-apply-zone hidden>
          <div class="settings-action-row"><button class="button" type="button" data-action="review-selected-restore">Review selected restore</button></div>
          <div class="settings-restore-status" data-configuration-restore-review-status hidden aria-live="polite">
            <span class="settings-chip" data-configuration-restore-review-pill>Ready to review</span>
            <span data-configuration-restore-review-message>Choose what to restore, then review it. Nothing changes at this step.</span>
          </div>
          <div class="setting-field settings-restore-confirmation" data-configuration-restore-confirm hidden>
            <span>Final confirmation</span>
            <strong data-configuration-restore-confirm-title>Restore the selected configuration?</strong>
            <small data-configuration-restore-confirm-copy>The selected owners will capture rollback state before changing anything.</small>
            <ul class="muted small" data-configuration-restore-confirm-summary></ul>
            <div class="settings-action-row">
              <button class="button" type="button" data-action="confirm-configuration-restore">Confirm &amp; restore</button>
              <button class="button settings-secondary" type="button" data-action="cancel-configuration-restore">Cancel</button>
            </div>
          </div>
        </div>
        <p class="muted small settings-restore-footnote"><strong>Credentials are never restored.</strong> WU/Plex authentication stays separately commissioned. Schema-v1 backups retain their accepted Headless/order/hidden compatibility path; schema-v2 uses retained native/Home rollback through the complete transaction.</p>
      </div>
      <div class="settings-restore-status" data-configuration-restore-result-status hidden aria-live="polite">
        <span class="settings-chip" data-configuration-restore-result-pill>Restore status</span>
        <span data-configuration-restore-result-message></span>
      </div>
    </section>
  `;
  advanced.append(page);

  const showPage = () => {
    overview.hidden = true;
    advanced.querySelectorAll('[data-settings-subpage]').forEach((candidate) => {
      candidate.hidden = candidate !== page;
    });
    page.hidden = false;
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', '#advanced/backup');
  };
  const showOverview = () => {
    page.hidden = true;
    overview.hidden = false;
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', '#advanced');
  };
  row.addEventListener('click', showPage);
  page.querySelector('[data-settings-back="advanced"]')?.addEventListener('click', showOverview);

  const backupMessage = page.querySelector('[data-configuration-backup-message]');
  const backupButton = page.querySelector('[data-action="download-configuration-backup"]');
  const restoreFile = page.querySelector('[data-configuration-restore-file]');
  const restoreFileStatus = page.querySelector('[data-configuration-restore-file-status]');
  const restoreButton = page.querySelector('[data-action="preview-configuration-restore"]');
  const restorePreview = page.querySelector('[data-configuration-restore-preview]');
  const previewStatus = page.querySelector('[data-configuration-restore-preview-status]');
  const previewStatusPill = page.querySelector('[data-configuration-restore-status-pill]');
  const restoreMessage = page.querySelector('[data-configuration-restore-message]');
  const totalSummary = page.querySelector('[data-configuration-restore-total-summary]');
  const acpTarget = page.querySelector('[data-configuration-restore-target="acp"]');
  const plexampTarget = page.querySelector('[data-configuration-restore-target="plexamp"]');
  const acpSummary = page.querySelector('[data-configuration-restore-acp-summary]');
  const plexampSummary = page.querySelector('[data-configuration-restore-plexamp-summary]');
  const settingsSummary = page.querySelector('[data-configuration-restore-headless-summary]');
  const browserSummary = page.querySelector('[data-configuration-restore-browser-summary]');
  const warningBox = page.querySelector('[data-configuration-restore-warning-box]');
  const warningsList = page.querySelector('[data-configuration-restore-warnings]');
  const sectionsList = page.querySelector('[data-configuration-restore-sections]');
  const pathsList = page.querySelector('[data-configuration-restore-paths]');
  const applyZone = page.querySelector('[data-configuration-restore-apply-zone]');
  const reviewButton = page.querySelector('[data-action="review-selected-restore"]');
  const reviewStatus = page.querySelector('[data-configuration-restore-review-status]');
  const reviewPill = page.querySelector('[data-configuration-restore-review-pill]');
  const reviewMessage = page.querySelector('[data-configuration-restore-review-message]');
  const confirmation = page.querySelector('[data-configuration-restore-confirm]');
  const resultStatus = page.querySelector('[data-configuration-restore-result-status]');
  const resultPill = page.querySelector('[data-configuration-restore-result-pill]');
  const resultMessage = page.querySelector('[data-configuration-restore-result-message]');
  const confirmTitle = page.querySelector('[data-configuration-restore-confirm-title]');
  const confirmCopy = page.querySelector('[data-configuration-restore-confirm-copy]');
  const confirmSummary = page.querySelector('[data-configuration-restore-confirm-summary]');
  const confirmButton = page.querySelector('[data-action="confirm-configuration-restore"]');
  const cancelButton = page.querySelector('[data-action="cancel-configuration-restore"]');

  function replaceList(list, items, emptyText) {
    if (!list) return;
    list.replaceChildren();
    const values = Array.isArray(items) ? items : [];
    if (!values.length) {
      const item = document.createElement('li');
      item.textContent = emptyText;
      list.append(item);
      return;
    }
    values.forEach((value) => {
      const item = document.createElement('li');
      item.textContent = String(value);
      list.append(item);
    });
  }

  function setStatus(container, pill, message, label, text, state = 'ready') {
    if (!container) return;
    container.hidden = false;
    container.dataset.status = state;
    if (pill) pill.textContent = label;
    if (message) message.textContent = text;
  }

  function hideStatus(container) {
    if (!container) return;
    container.hidden = true;
    delete container.dataset.status;
  }

  function settingsHaveUnsavedChanges() {
    const saveButton = document.querySelector('#settings-unified-form button[type="submit"]');
    return Boolean(saveButton && !saveButton.disabled);
  }

  function validateServerPlan(plan) {
    if (
      !plainObject(plan)
      || plan.ok !== true
      || ![1, 2].includes(plan.schema_version)
      || plan.read_only !== true
      || plan.apply_enabled !== false
      || typeof plan.restore_available !== 'boolean'
      || typeof plan.server_restore_available !== 'boolean'
      || typeof plan.plexamp_headless_restore_available !== 'boolean'
      || typeof plan.preview_token !== 'string'
      || !/^[a-f0-9]{32}$/.test(plan.preview_token)
    ) throw new Error('Restore preview returned an invalid safety contract.');
    return plan;
  }

  async function previewServer(backup) {
    const response = await fetch('/api/settings/restore/preview', {
      method: 'POST',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(backup),
    });
    const plan = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(plan.error || `Restore preview returned HTTP ${response.status}.`);
    return validateServerPlan(plan);
  }

  function schemaVersion(backup) {
    return Number(backup?.schema_version || 0);
  }

  function v1HomeFromBackup(backup) {
    const browser = backup?.plexamp?.browser_preferences;
    if (!browser || browser.schema_version !== 1 || !plainObject(browser.home)) return null;
    return browser.home;
  }

  async function previewV1Home(backup) {
    const home = v1HomeFromBackup(backup);
    if (!home) return null;
    if (!await loadV1Client()) {
      return { schema_version: 1, status: 'client-unavailable', read_only: true, restore_available: false };
    }
    return window.ACPPlexampBrowserPreferences.planHome(home, { timeoutMs: 1800 });
  }

  async function previewBrowser(backup) {
    if (schemaVersion(backup) === 1) return previewV1Home(backup);
    if (schemaVersion(backup) !== 2) return null;
    if (!await loadV2Stack()) {
      return { ok: false, schema_version: 2, status: 'client-unavailable', change_count: 0 };
    }
    return window.ACPConfigurationBackupRestoreV2.previewBrowserOwners(
      backup,
      window.ACPPlexampNativePortability,
      window.ACPPlexampHomePortabilityV2,
      { timeoutMs: 1800 },
    );
  }

  function includeV1BrowserPreferences(backup, snapshot) {
    if (!plainObject(backup) || !plainObject(snapshot) || snapshot.schema_version !== 1) return false;
    if (!['ready', 'empty'].includes(snapshot.status) || !plainObject(snapshot.home)) return false;
    backup.plexamp = plainObject(backup.plexamp) ? backup.plexamp : {};
    backup.plexamp.browser_preferences = {
      schema_version: 1,
      home: {
        order: snapshot.home.order === null ? null : Array.from(snapshot.home.order),
        hidden: Array.from(snapshot.home.hidden || []),
      },
    };
    const report = plainObject(backup.export_report) ? backup.export_report : (backup.export_report = {});
    report.omitted = Array.isArray(report.omitted)
      ? report.omitted.filter((entry) => entry?.section !== 'plexamp.browser_preferences')
      : [];
    return true;
  }

  function recordCompatibilityFallback(backup, reason) {
    if (!plainObject(backup)) return;
    const report = plainObject(backup.export_report) ? backup.export_report : (backup.export_report = {});
    report.warnings = Array.isArray(report.warnings) ? report.warnings : [];
    report.warnings.push(`Complete Plexamp portability was unavailable (${safeStatus(reason)}); this file uses the schema-v1 compatibility scope.`);
  }

  async function buildDownloadBackup(serverBackup) {
    if (await loadV2Stack()) {
      const [nativeSnapshot, homeSnapshot] = await Promise.all([
        window.ACPPlexampNativePortability.snapshot({ timeoutMs: 1800 }),
        window.ACPPlexampHomePortabilityV2.snapshot({ timeoutMs: 1800 }),
      ]);
      if (nativeSnapshot?.status === 'ready' && homeSnapshot?.status === 'ready') {
        try {
          return {
            backup: window.ACPConfigurationBackupRestoreV2.assembleBackupV2(
              serverBackup,
              nativeSnapshot,
              homeSnapshot,
            ),
            complete: true,
          };
        } catch (_error) {
          // Fall through to the accepted schema-v1 compatibility export.
        }
      }
      recordCompatibilityFallback(
        serverBackup,
        `${safeStatus(nativeSnapshot?.status)}-${safeStatus(homeSnapshot?.status)}`,
      );
    } else {
      recordCompatibilityFallback(serverBackup, 'v2-client-unavailable');
    }

    let homeIncluded = false;
    if (await loadV1Client()) {
      const snapshot = await window.ACPPlexampBrowserPreferences.snapshot({ timeoutMs: 1800 });
      homeIncluded = includeV1BrowserPreferences(serverBackup, snapshot);
    }
    return { backup: serverBackup, complete: false, homeIncluded };
  }

  function buildSelectedServerBackup(backup, targets) {
    const candidate = cloneJson(backup);
    if (!targets.acp) candidate.a_clockwork_plex = { settings: {}, audio: {} };
    const sourcePlexamp = plainObject(candidate.plexamp) ? candidate.plexamp : {};
    if (schemaVersion(candidate) === 1) {
      const selectedPlexamp = {};
      if (targets.plexamp) {
        if (typeof sourcePlexamp.source_version === 'string') selectedPlexamp.source_version = sourcePlexamp.source_version;
        if (plainObject(sourcePlexamp.headless_preferences)) {
          selectedPlexamp.headless_preferences = cloneJson(sourcePlexamp.headless_preferences);
        }
      }
      candidate.plexamp = selectedPlexamp;
      return candidate;
    }
    if (schemaVersion(candidate) === 2 && !targets.plexamp) {
      candidate.plexamp = typeof sourcePlexamp.source_version === 'string'
        ? { source_version: sourcePlexamp.source_version }
        : {};
    }
    return candidate;
  }

  function planCounts(plan, browserPlan, backup) {
    const acp = Number(plan?.server_change_count || 0);
    if (schemaVersion(backup) === 2) {
      const browserReady = browserPlan?.ok === true && browserPlan.status === 'ready';
      const native = browserReady ? Number(browserPlan.native_change_count || 0) : 0;
      const home = browserReady ? Number(browserPlan.home_change_count || 0) : 0;
      return { acp, native, home, deferred: 0, plexamp: native + home, total: acp + native + home };
    }
    const native = Number(plan?.plexamp_headless_change_count || 0);
    const detected = Number(plan?.plexamp_headless_detected_change_count || 0);
    const deferred = Number(plan?.plexamp_headless?.deferred_items || 0);
    const home = browserPlan?.status === 'ready' && browserPlan.restore_available === true
      ? Number(browserPlan.change_count || 0)
      : 0;
    return { acp, native, home, detected, deferred, plexamp: native + home, total: acp + native + home };
  }

  let selectedBackup = null;
  let fullPlan = null;
  let fullBrowserPlan = null;
  let reviewedServerBackup = null;
  let reviewedPlan = null;
  let reviewedBrowserPlan = null;
  let reviewedTargetSignature = '';
  let restoreInFlight = false;
  const selectedTargets = { acp: false, plexamp: false };

  function currentTargetSignature() {
    return `${selectedTargets.acp ? 'a' : '-'}${selectedTargets.plexamp ? 'p' : '-'}:${schemaVersion(selectedBackup)}`;
  }

  function clearReviewedState({ keepStatus = false } = {}) {
    reviewedServerBackup = null;
    reviewedPlan = null;
    reviewedBrowserPlan = null;
    reviewedTargetSignature = '';
    if (confirmation) confirmation.hidden = true;
    if (!keepStatus) hideStatus(reviewStatus);
  }

  function resetRestoreState() {
    selectedBackup = null;
    fullPlan = null;
    fullBrowserPlan = null;
    selectedTargets.acp = false;
    selectedTargets.plexamp = false;
    clearReviewedState();
    if (restorePreview) restorePreview.hidden = true;
    if (applyZone) applyZone.hidden = true;
    hideStatus(resultStatus);
    [acpTarget, plexampTarget].forEach((button) => {
      if (!button) return;
      button.disabled = true;
      button.setAttribute('aria-pressed', 'false');
    });
  }

  function setTarget(button, key, available, selected) {
    if (!button) return;
    button.disabled = !available;
    selectedTargets[key] = available && selected;
    button.setAttribute('aria-pressed', selectedTargets[key] ? 'true' : 'false');
  }

  function renderFullPreview(plan, browserPlan, backup, { preserveSelection = false } = {}) {
    validateServerPlan(plan);
    const counts = planCounts(plan, browserPlan, backup);
    const previous = { ...selectedTargets };
    setTarget(acpTarget, 'acp', counts.acp > 0, preserveSelection ? previous.acp : counts.acp > 0);
    setTarget(plexampTarget, 'plexamp', counts.plexamp > 0, preserveSelection ? previous.plexamp : counts.plexamp > 0);

    const selectedCount = (selectedTargets.acp ? counts.acp : 0) + (selectedTargets.plexamp ? counts.plexamp : 0);
    let scope = 'No changes';
    if (counts.acp > 0 && counts.plexamp > 0) scope = selectedTargets.acp && selectedTargets.plexamp ? 'Both selected' : 'Choose target';
    else if (counts.acp > 0) scope = 'ACP only';
    else if (counts.plexamp > 0) scope = 'Plexamp only';
    if (totalSummary) totalSummary.textContent = `${scope} · ${selectedCount} selected`;
    if (acpSummary) acpSummary.textContent = counts.acp ? `${counts.acp} restorable` : 'No changes';
    if (plexampSummary) plexampSummary.textContent = counts.plexamp ? `${counts.plexamp} restorable` : 'No changes';

    if (settingsSummary) {
      if (schemaVersion(backup) === 2) {
        settingsSummary.textContent = counts.native ? `Settings: ${counts.native} restorable` : 'Settings: no changes';
      } else if (Number(counts.detected || 0) === 0) {
        settingsSummary.textContent = 'Headless: no changes';
      } else if (counts.native > 0 && counts.deferred > 0) {
        settingsSummary.textContent = `Headless: ${counts.native} restorable, ${counts.deferred} deferred`;
      } else if (counts.native > 0) {
        settingsSummary.textContent = `Headless: ${counts.native} restorable`;
      } else {
        settingsSummary.textContent = `Headless: ${counts.deferred || counts.detected} deferred`;
      }
    }

    if (browserSummary) {
      const browserPresent = plan.plexamp_browser?.present === true;
      if (!browserPresent) browserSummary.textContent = 'Home: not present';
      else if (schemaVersion(backup) === 2) {
        if (browserPlan?.ok !== true || browserPlan.status !== 'ready') browserSummary.textContent = 'Home: unavailable';
        else browserSummary.textContent = counts.home ? `Home: ${counts.home} logical change` : 'Home: no changes';
      } else if (!browserPlan || browserPlan.status !== 'ready') {
        browserSummary.textContent = 'Home: unavailable';
      } else if (browserPlan.restore_available) {
        const missing = Number(browserPlan.missing_item_count || 0);
        browserSummary.textContent = `Home: ${Number(browserPlan.change_count || 0)} restorable${missing ? `, ${missing} unavailable` : ''}`;
      } else {
        const missing = Number(browserPlan.missing_item_count || 0);
        browserSummary.textContent = missing ? `Home: no changes, ${missing} unavailable` : 'Home: no changes';
      }
    }

    const warnings = Array.isArray(plan.warnings) ? Array.from(plan.warnings) : [];
    if (schemaVersion(backup) === 2) {
      for (let index = warnings.length - 1; index >= 0; index -= 1) {
        if (
          warnings[index].startsWith('Portable Plexamp settings are valid')
          || warnings[index].startsWith('Plexamp Home customisation is valid and portable')
        ) warnings.splice(index, 1);
      }
      if (plan.plexamp_portable_settings?.present && (browserPlan?.ok !== true || browserPlan.status !== 'ready')) {
        warnings.push(`Plexamp schema-v2 restore is unavailable: ${safeStatus(browserPlan?.status)}.`);
      }
    } else if (plan.plexamp_browser?.present && browserPlan) {
      if (browserPlan.status !== 'ready') {
        warnings.push(`Plexamp Home restore is unavailable: ${safeStatus(browserPlan.status)}.`);
      } else {
        const missing = Number(browserPlan.missing_item_count || 0);
        const targetOnly = Number(browserPlan.target_only_item_count || 0);
        if (missing > 0) warnings.push(`${missing} saved Plexamp Home item${missing === 1 ? '' : 's'} are not present on this target and will be skipped.`);
        if (targetOnly > 0) warnings.push(`${targetOnly} target-only Plexamp Home item${targetOnly === 1 ? '' : 's'} will be retained.`);
      }
    }
    if (Array.isArray(plan.confirmations_required)) {
      plan.confirmations_required.forEach((name) => warnings.push(`Restore confirmation required: ${String(name)}`));
    }
    replaceList(warningsList, warnings, 'No restore warnings.');
    if (warningBox) warningBox.hidden = warnings.length === 0;

    const sections = plainObject(plan.sections)
      ? Object.entries(plan.sections).sort(([left], [right]) => left.localeCompare(right)).map(([name, count]) => `${name}: ${Number(count || 0)}`)
      : [];
    if (schemaVersion(backup) === 2) {
      if (counts.native > 0) sections.push(`plexamp.portable_settings: ${counts.native}`);
      if (counts.home > 0) sections.push(`plexamp.browser_preferences: ${counts.home}`);
    } else if (counts.home > 0) sections.push(`plexamp.browser_preferences: ${counts.home}`);
    replaceList(sectionsList, sections, 'No portable changes detected.');

    const paths = Array.isArray(plan.changed_paths) ? plan.changed_paths.map(String) : [];
    if (schemaVersion(backup) === 2 && browserPlan?.ok === true) {
      const nativeKeys = Array.isArray(browserPlan.native_plan?.changed_keys) ? browserPlan.native_plan.changed_keys : [];
      nativeKeys.forEach((key) => paths.push(`plexamp.portable_settings.settings.${key}`));
      if (counts.home > 0) paths.push('plexamp.browser_preferences.home');
    } else if (browserPlan?.status === 'ready') {
      if (browserPlan.order_changed) paths.push('plexamp.browser_preferences.home.order');
      if (Number(browserPlan.hidden_change_count || 0) > 0) paths.push('plexamp.browser_preferences.home.hidden');
    }
    if (plan.changed_paths_truncated) paths.push('…additional changed paths omitted from preview');
    replaceList(pathsList, paths, 'No changed portable paths.');

    fullPlan = plan;
    fullBrowserPlan = browserPlan;
    clearReviewedState();
    if (applyZone) applyZone.hidden = counts.total === 0;
    if (counts.total > 0) {
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Ready to review', 'Choose A Clockwork Plex, Plexamp, or both, then press Review selected restore. Nothing changes at Review.', 'ready');
    } else hideStatus(reviewStatus);
    if (restorePreview) restorePreview.hidden = false;
    return counts;
  }

  function updateSelectionSummary() {
    if (!totalSummary || !fullPlan || !selectedBackup) return;
    const counts = planCounts(fullPlan, fullBrowserPlan, selectedBackup);
    let scope = 'Choose target';
    if (selectedTargets.acp && selectedTargets.plexamp) scope = 'Both selected';
    else if (selectedTargets.acp) scope = 'ACP selected';
    else if (selectedTargets.plexamp) scope = 'Plexamp selected';
    const selectedCount = (selectedTargets.acp ? counts.acp : 0) + (selectedTargets.plexamp ? counts.plexamp : 0);
    totalSummary.textContent = `${scope} · ${selectedCount} selected`;
  }

  function invalidateReviewForSelectionChange() {
    clearReviewedState({ keepStatus: true });
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Selection changed', 'Review the selected restore again before Confirm & restore becomes available.', 'ready');
  }

  function toggleTarget(key, button) {
    if (!button || button.disabled || restoreInFlight) return;
    selectedTargets[key] = !selectedTargets[key];
    button.setAttribute('aria-pressed', selectedTargets[key] ? 'true' : 'false');
    updateSelectionSummary();
    invalidateReviewForSelectionChange();
  }
  acpTarget?.addEventListener('click', () => toggleTarget('acp', acpTarget));
  plexampTarget?.addEventListener('click', () => toggleTarget('plexamp', plexampTarget));

  async function applyServer(backup, plan) {
    const response = await fetch('/api/settings/restore/apply', {
      method: 'POST',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        backup,
        preview_token: plan.preview_token,
        confirm_restore: true,
        confirmations: Array.isArray(plan.confirmations_required) ? plan.confirmations_required : [],
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      const error = new Error(String(result.error || `Restore returned HTTP ${response.status}.`).trim());
      error.restoreBlocked = response.status === 409 && result.fresh_preview_required === true;
      error.rolledBack = result.rolled_back === true;
      error.freshPreviewRequired = result.fresh_preview_required === true;
      error.ownerRolledBack = result.rolled_back === true;
      throw error;
    }
    return result;
  }

  async function applyV1Home(home, browserPlan) {
    if (!await loadV1Client()) throw new Error('Plexamp Home bridge is unavailable. Run Preview restore again.');
    const result = await window.ACPPlexampBrowserPreferences.applyHome(home, browserPlan.target_fingerprint, { timeoutMs: 3000 });
    if (result?.status === 'stale-target' || result?.fresh_preview_required === true) {
      const error = new Error('Plexamp Home changed after Review. No Home settings were changed; run Preview restore again.');
      error.restoreBlocked = true;
      throw error;
    }
    if (!result || result.applied !== true || result.status !== 'applied') {
      if (result?.status === 'apply-failed' && result?.rolled_back === true) {
        throw new Error('Plexamp Home restore failed verification and the exact target Home state was rolled back. Run Preview restore again.');
      }
      throw new Error(`Plexamp Home restore was not applied (${safeStatus(result?.status)}).`);
    }
    const verified = await window.ACPPlexampBrowserPreferences.planHome(home, { timeoutMs: 1800 });
    if (!verified || verified.status !== 'ready' || verified.restore_available !== false) {
      throw new Error('Plexamp Home write completed but the follow-up live verification did not converge.');
    }
    return Number(result.applied_change_count || 0);
  }

  function setControlsDisabled(disabled) {
    const counts = fullPlan && selectedBackup ? planCounts(fullPlan, fullBrowserPlan, selectedBackup) : { acp: 0, plexamp: 0 };
    [restoreButton, restoreFile, reviewButton, confirmButton, cancelButton].forEach((control) => {
      if (control) control.disabled = disabled;
    });
    if (acpTarget) acpTarget.disabled = disabled || counts.acp === 0;
    if (plexampTarget) plexampTarget.disabled = disabled || counts.plexamp === 0;
  }

  function storeAndReloadSuccess(message, backupSchema) {
    sessionStorage.setItem(RESTORE_RESULT_KEY, JSON.stringify({
      schema_version: backupSchema,
      created_at: Date.now(),
      message,
    }));
    window.setTimeout(() => window.location.reload(), 650);
  }

  function restorePersistedResult() {
    let stored = null;
    try {
      stored = JSON.parse(sessionStorage.getItem(RESTORE_RESULT_KEY) || 'null');
    } catch (_error) {
      stored = null;
    }
    sessionStorage.removeItem(RESTORE_RESULT_KEY);
    if (!stored || ![1, 2].includes(stored.schema_version) || typeof stored.message !== 'string') return;
    if (!Number.isFinite(stored.created_at) || Date.now() - stored.created_at > 5 * 60 * 1000) return;
    setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', stored.message.slice(0, 800), 'success');
  }

  backupButton?.addEventListener('click', async () => {
    backupButton.disabled = true;
    if (backupMessage) backupMessage.textContent = 'Building portable backup…';
    try {
      const response = await fetch('/api/settings/backup', { cache: 'no-store' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Backup returned HTTP ${response.status}.`);
      }
      const serverBackup = await response.json();
      const built = await buildDownloadBackup(serverBackup);
      const disposition = response.headers.get('Content-Disposition') || '';
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] || 'A-Clockwork-Plex-backup.json';
      const blob = new Blob([`${JSON.stringify(built.backup, null, 2)}\n`], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (backupMessage) {
        backupMessage.textContent = built.complete
          ? 'Complete schema-v2 backup downloaded, including portable Plexamp settings and Home customisation. Credentials and authentication were not included.'
          : `Schema-v1 compatibility backup downloaded${built.homeIncluded ? ', including Home order/hidden choices' : ''}. Credentials and authentication were not included.`;
      }
    } catch (error) {
      if (backupMessage) backupMessage.textContent = error.message || 'Could not create the backup.';
    } finally {
      backupButton.disabled = false;
    }
  });

  restoreFile?.addEventListener('change', () => {
    resetRestoreState();
    if (restoreMessage) restoreMessage.classList.remove('is-conflict');
    hideStatus(previewStatus);
    hideStatus(resultStatus);
    const file = restoreFile.files?.[0] || null;
    if (!file) {
      if (restoreFileStatus) restoreFileStatus.textContent = 'Select an A Clockwork Plex JSON backup, up to 1 MB.';
      if (restoreButton) restoreButton.disabled = true;
      return;
    }
    if (file.size > MAX_RESTORE_FILE_BYTES) {
      if (restoreFileStatus) restoreFileStatus.textContent = `${file.name} is larger than the 1 MB preview limit.`;
      if (restoreButton) restoreButton.disabled = true;
      setStatus(previewStatus, previewStatusPill, restoreMessage, 'File too large', 'Choose a backup no larger than 1 MB.', 'error');
      return;
    }
    if (restoreFileStatus) restoreFileStatus.textContent = `${file.name} · ${file.size.toLocaleString()} bytes`;
    if (restoreButton) restoreButton.disabled = false;
    setStatus(previewStatus, previewStatusPill, restoreMessage, 'Ready to preview', 'Press Preview restore. Nothing will be changed.', 'ready');
  });

  restoreButton?.addEventListener('click', async () => {
    const file = restoreFile?.files?.[0] || null;
    if (!file || restoreInFlight) return;
    restoreButton.disabled = true;
    resetRestoreState();
    setStatus(previewStatus, previewStatusPill, restoreMessage, 'Previewing…', 'Validating the backup and comparing portable settings.', 'busy');
    try {
      if (file.size > MAX_RESTORE_FILE_BYTES) throw new Error('Backup file is larger than the 1 MB preview limit.');
      let backup;
      try {
        backup = JSON.parse(await file.text());
      } catch (_error) {
        throw new Error('The selected file is not valid JSON.');
      }
      if (![1, 2].includes(schemaVersion(backup))) throw new Error('This backup schema is not supported.');
      const plan = await previewServer(backup);
      const browserPlan = await previewBrowser(backup);
      selectedBackup = backup;
      const counts = renderFullPreview(plan, browserPlan, backup);
      const deferred = Number(plan.deferred_change_count || 0);
      if (counts.total === 0 && deferred === 0) {
        setStatus(previewStatus, previewStatusPill, restoreMessage, 'Preview complete', 'Backup is valid. No supported portable settings differ from this appliance.', 'success');
      } else if (counts.total > 0) {
        setStatus(previewStatus, previewStatusPill, restoreMessage, 'Preview ready', `Backup is valid. ${counts.total} restorable change${counts.total === 1 ? '' : 's'} found. Choose A Clockwork Plex, Plexamp, or both below.`, 'success');
      } else {
        setStatus(previewStatus, previewStatusPill, restoreMessage, 'Preview complete', 'Backup is valid. Only deferred Plexamp changes remain.', 'warning');
      }
    } catch (error) {
      resetRestoreState();
      setStatus(previewStatus, previewStatusPill, restoreMessage, 'Preview failed', error.message || 'Could not preview this backup.', 'error');
    } finally {
      restoreButton.disabled = false;
    }
  });

  reviewButton?.addEventListener('click', async () => {
    if (!selectedBackup || !fullPlan || restoreInFlight) return;
    if (!selectedTargets.acp && !selectedTargets.plexamp) {
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Choose a target', 'Select A Clockwork Plex, Plexamp, or both before Review.', 'warning');
      return;
    }
    if (settingsHaveUnsavedChanges()) {
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Unsaved Settings', 'Save or discard staged Settings changes before reviewing a restore.', 'warning');
      return;
    }

    reviewButton.disabled = true;
    clearReviewedState({ keepStatus: true });
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Reviewing…', 'Refreshing the selected owners and confirmation boundary. Nothing is changing.', 'busy');
    try {
      const targets = { ...selectedTargets };
      const serverBackup = buildSelectedServerBackup(selectedBackup, targets);
      const plan = await previewServer(serverBackup);
      const browserPlan = targets.plexamp ? await previewBrowser(serverBackup) : null;
      if (schemaVersion(serverBackup) === 2 && targets.plexamp && (browserPlan?.ok !== true || browserPlan.status !== 'ready')) {
        throw new Error(`Plexamp schema-v2 owners are not ready (${safeStatus(browserPlan?.status)}). Nothing changed.`);
      }
      const counts = planCounts(plan, browserPlan, serverBackup);
      if (counts.total === 0) {
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Nothing to restore', 'The selected targets already match this backup. Run Preview again if the appliance changed.', 'success');
        return;
      }

      reviewedServerBackup = serverBackup;
      reviewedPlan = plan;
      reviewedBrowserPlan = browserPlan;
      reviewedTargetSignature = currentTargetSignature();

      const selectedNames = [];
      if (targets.acp && counts.acp > 0) selectedNames.push('A Clockwork Plex');
      if (targets.plexamp && counts.plexamp > 0) selectedNames.push('Plexamp');
      if (confirmTitle) confirmTitle.textContent = selectedNames.length === 2
        ? 'Restore A Clockwork Plex and Plexamp?'
        : `Restore ${selectedNames[0] || 'the selected configuration'}?`;

      const summary = [];
      if (targets.acp) summary.push(`A Clockwork Plex: ${counts.acp} path${counts.acp === 1 ? '' : 's'}`);
      if (targets.plexamp) {
        summary.push(`${schemaVersion(serverBackup) === 2 ? 'Plexamp settings' : 'Plexamp Headless'}: ${counts.native} change${counts.native === 1 ? '' : 's'}`);
        summary.push(`Plexamp Home: ${counts.home} logical change${counts.home === 1 ? '' : 's'}`);
        if (counts.deferred > 0) summary.push(`Plexamp Headless deferred: ${counts.deferred}`);
      }
      replaceList(confirmSummary, summary, 'No selected differences remain.');

      if (confirmCopy) {
        if (schemaVersion(serverBackup) === 2 && targets.plexamp) {
          confirmCopy.textContent = targets.acp && counts.acp > 0
            ? 'One confirmation will apply Plexamp settings, then coordinated Home customisation, then A Clockwork Plex. Browser rollback is retained until the later ACP stage verifies; any later failure rolls browser owners back in reverse order.'
            : 'One confirmation will apply and verify the selected Plexamp owners. Exact browser rollback is retained until every selected owner commits.';
        } else {
          const restarts = [];
          if (Array.isArray(plan.confirmations_required) && plan.confirmations_required.includes('airplay_restart')) restarts.push('Shairport Sync will briefly restart for the restored AirPlay receiver name.');
          if (counts.native > 0) restarts.push('Plexamp Headless will briefly restart while its allow-listed preferences are verified.');
          confirmCopy.textContent = `The accepted schema-v1 compatibility owners will apply only the reviewed differences and verify their own rollback boundaries. ${restarts.join(' ')}`.trim();
        }
      }
      if (confirmation) confirmation.hidden = false;
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Ready to confirm', `${counts.total} selected change${counts.total === 1 ? '' : 's'} reviewed. Confirm & restore is now the only mutating step.`, 'success');
    } catch (error) {
      clearReviewedState({ keepStatus: true });
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Review failed', error.message || 'Could not review the selected restore.', 'error');
    } finally {
      reviewButton.disabled = false;
    }
  });

  cancelButton?.addEventListener('click', () => {
    clearReviewedState({ keepStatus: true });
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Review cancelled', 'Nothing changed. Press Review selected restore again when you are ready.', 'ready');
  });

  async function confirmV1() {
    let homeApplied = 0;
    let serverResult = null;
    const home = selectedTargets.plexamp ? v1HomeFromBackup(selectedBackup) : null;
    if (reviewedBrowserPlan?.status === 'ready' && reviewedBrowserPlan.restore_available === true) {
      if (!home) throw new Error('The reviewed Plexamp Home payload is no longer available. Run Preview restore again.');
      homeApplied = await applyV1Home(home, reviewedBrowserPlan);
    }
    if (Number(reviewedPlan.apply_change_count || 0) > 0) serverResult = await applyServer(reviewedServerBackup, reviewedPlan);

    const acpApplied = Number(serverResult?.server_applied_change_count || 0);
    const nativeApplied = Number(serverResult?.plexamp_headless_applied_change_count || 0);
    const total = acpApplied + nativeApplied + homeApplied;
    const parts = [];
    if (acpApplied) parts.push(`${acpApplied} ACP/server`);
    if (nativeApplied) parts.push(`${nativeApplied} Plexamp Headless`);
    if (homeApplied) parts.push(`${homeApplied} Plexamp Home`);
    const success = `Restore verified: ${total} change${total === 1 ? '' : 's'} applied${parts.length ? ` (${parts.join(', ')})` : ''}. The live configuration now matches the selected parts of this backup.`;
    return { success, serverResult, homeApplied };
  }

  async function confirmV2() {
    if (selectedTargets.plexamp) {
      if (!await loadV2Stack()) throw new Error('Plexamp schema-v2 restore clients are unavailable. Run Preview restore again.');
      const serverApply = selectedTargets.acp && Number(reviewedPlan.server_change_count || 0) > 0
        ? () => applyServer(reviewedServerBackup, reviewedPlan)
        : null;
      const result = await window.ACPConfigurationBackupRestoreV2.runRestoreTransaction({
        backup: reviewedServerBackup,
        browserPreview: reviewedBrowserPlan,
        nativeClient: window.ACPPlexampNativePortability,
        homeClient: window.ACPPlexampHomePortabilityV2,
        serverApply,
      });
      if (!result?.ok) {
        const error = new Error(result?.error || 'Schema-v2 restore failed.');
        error.restoreBlocked = result?.fresh_preview_required === true || result?.status === 'stale-target';
        error.v2Result = result;
        throw error;
      }
      const acpApplied = Number(result.server_result?.server_applied_change_count || 0);
      const nativeApplied = Number(result.native_applied_change_count || 0);
      const homeApplied = Number(result.home_applied_change_count || 0);
      const total = acpApplied + nativeApplied + homeApplied;
      const parts = [];
      if (acpApplied) parts.push(`${acpApplied} ACP/server`);
      if (nativeApplied) parts.push(`${nativeApplied} Plexamp settings`);
      if (homeApplied) parts.push(`${homeApplied} Plexamp Home`);
      const warning = Array.isArray(result.warnings) && result.warnings.length ? ` ${result.warnings.join(' ')}` : '';
      return {
        success: `Restore verified: ${total} change${total === 1 ? '' : 's'} applied${parts.length ? ` (${parts.join(', ')})` : ''}. The live configuration now matches the selected parts of this backup.${warning}`,
        result,
      };
    }

    const serverResult = await applyServer(reviewedServerBackup, reviewedPlan);
    const acpApplied = Number(serverResult?.server_applied_change_count || 0);
    return {
      success: `Restore verified: ${acpApplied} ACP/server change${acpApplied === 1 ? '' : 's'} applied. The live configuration now matches the selected A Clockwork Plex part of this backup.`,
      result: { server_result: serverResult },
    };
  }

  confirmButton?.addEventListener('click', async () => {
    if (
      !selectedBackup
      || !reviewedServerBackup
      || !reviewedPlan
      || restoreInFlight
      || reviewedTargetSignature !== currentTargetSignature()
    ) return;
    if (settingsHaveUnsavedChanges()) {
      clearReviewedState({ keepStatus: true });
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Unsaved Settings', 'Save or discard staged Settings changes, then Review selected restore again.', 'warning');
      return;
    }

    restoreInFlight = true;
    if (confirmation) confirmation.hidden = true;
    setControlsDisabled(true);
    hideStatus(resultStatus);
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Restoring…', 'Applying the reviewed owners and verifying each protected step.', 'busy');
    try {
      if (schemaVersion(selectedBackup) === 2) {
        const outcome = await confirmV2();
        setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', outcome.success, 'success');
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Restore complete', 'The reviewed schema-v2 transaction was applied and verified. Reloading Settings…', 'success');
        storeAndReloadSuccess(outcome.success, 2);
        return;
      }

      const outcome = await confirmV1();
      if (outcome.serverResult) {
        setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', outcome.success, 'success');
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Restore complete', 'The reviewed restore was applied and verified. Reloading Settings…', 'success');
        storeAndReloadSuccess(outcome.success, 1);
        return;
      }
      const refreshedPlan = await previewServer(selectedBackup);
      const refreshedBrowser = await previewBrowser(selectedBackup);
      renderFullPreview(refreshedPlan, refreshedBrowser, selectedBackup);
      setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', `${outcome.success} The live Home layout now matches this backup.`, 'success');
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Restore complete', 'The selected Plexamp restore was applied and verified.', 'success');
      const frame = document.getElementById('persistent-plexamp-frame');
      if (frame?.src) window.setTimeout(() => { frame.src = frame.src; }, 350);
    } catch (error) {
      const blocked = error.restoreBlocked === true;
      const v2Result = error.v2Result;
      let message = error.message || 'Restore failed.';
      if (v2Result) {
        if (v2Result.browser_rollback?.all_verified === true && Number(v2Result.browser_applied_change_count || 0) > 0) {
          message += ' Earlier Plexamp browser changes were rolled back and verified.';
        } else if (v2Result.browser_rollback?.all_verified === false) {
          message += ' Browser rollback could not be fully verified; do not retry until the Plexamp settings/Home state has been inspected.';
        }
        if (v2Result.owner_self_rolled_back === true) message += ' The failed owner also reported its own rollback complete.';
      }
      clearReviewedState({ keepStatus: true });
      setStatus(resultStatus, resultPill, resultMessage, blocked ? 'Restore blocked' : 'Restore failed', `${message} Run Preview restore again before another attempt.`, blocked ? 'warning' : 'error');
      setStatus(reviewStatus, reviewPill, reviewMessage, blocked ? 'Restore blocked' : 'Restore failed', `${message} Run Preview restore again before another attempt.`, blocked ? 'warning' : 'error');
      if (restoreMessage) {
        restoreMessage.textContent = blocked ? `Restore blocked — ${message}` : 'Run Preview restore again before another restore attempt.';
        restoreMessage.classList.toggle('is-conflict', blocked);
      }
    } finally {
      restoreInFlight = false;
      setControlsDisabled(false);
    }
  });

  if (location.hash === '#advanced/backup') showPage();
  restorePersistedResult();
})();
