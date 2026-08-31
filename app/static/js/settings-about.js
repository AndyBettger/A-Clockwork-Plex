(() => {
  const version = document.getElementById('about-version');
  const release = document.getElementById('about-release');
  const tag = document.getElementById('about-tag');
  const message = document.getElementById('about-message');
  const repositoryLink = document.getElementById('about-repository-link');
  const companionLink = document.getElementById('about-companion-link');

  if (!version || !release || !tag || !message) {
    return;
  }

  const messages = [
    'System status: Mostly harmless.',
    'The answer remains 42. The alarm clock remains under careful supervision.',
    'Towel status: regrettably unverified.',
    'Don’t panic. Unless Classic Klaxon preview is active.',
    'Plexamp connected. Vogon poetry filter unavailable.',
    'Current improbability level: inconveniently measurable.',
  ];

  const messageIndex = Math.floor(Math.random() * messages.length);
  message.textContent = messages[messageIndex] || messages[0];

  fetch('/static/app-version.json', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Version metadata returned ${response.status}`);
      }
      return response.json();
    })
    .then((metadata) => {
      version.textContent = metadata.version ? `v${metadata.version}` : 'Development build';
      release.textContent = metadata.release_name || 'Development build';
      tag.textContent = metadata.tag || 'Unreleased';

      if (repositoryLink && metadata.repository) {
        repositoryLink.href = metadata.repository;
        repositoryLink.querySelector('span').textContent = metadata.repository.replace(/^https?:\/\//, '');
      }
      if (companionLink && metadata.companion_repository) {
        companionLink.href = metadata.companion_repository;
        companionLink.querySelector('span').textContent = metadata.companion_repository.replace(/^https?:\/\//, '');
      }
    })
    .catch(() => {
      version.textContent = 'Development build';
      release.textContent = 'Metadata temporarily hiding behind the sofa';
      tag.textContent = 'Unknown';
    });
})();

(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const advanced = document.querySelector('[data-settings-section="advanced"]');
  const overview = advanced?.querySelector('[data-settings-overview="advanced"]');
  if (!advanced || !overview || advanced.querySelector('[data-settings-subpage="advanced:backup"]')) return;

  const MAX_RESTORE_FILE_BYTES = 1_000_000;
  const RESTORE_RESULT_KEY = 'acp-configuration-restore-result-v1';

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
          <p class="muted small">Download a versioned, portable copy of the user-owned appliance settings.</p>
        </div>
        <span class="settings-chip">Secret-free</span>
      </div>
      <p class="muted small">The backup includes ordinary Settings, alarms, EQ and available mixer levels plus an allow-listed set of non-authentication Plexamp preferences. When the local Plexamp browser bridge is available, Home ordering and hidden-item choices are included too. Weather Underground API keys, Plex authentication, browser sessions, hardware bindings, caches and runtime state are deliberately excluded.</p>
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
            <small>Compatible Plexamp Headless preferences plus logical Home choices. <span data-configuration-restore-headless-summary>Headless: no changes</span> · <span data-configuration-restore-browser-summary>Home: not present</span></small>
          </button>
        </div>
        <div class="settings-restore-warning" data-configuration-restore-warning-box hidden>
          <strong>Warnings</strong>
          <ul class="muted small" data-configuration-restore-warnings></ul>
        </div>
        <details class="settings-restore-details">
          <summary>Preview details</summary>
          <div class="settings-restore-detail-grid">
            <div>
              <strong>Changed sections</strong>
              <ul class="muted small" data-configuration-restore-sections></ul>
            </div>
            <div>
              <strong>Technical changed paths</strong>
              <ul class="muted small" data-configuration-restore-paths></ul>
            </div>
          </div>
        </details>
        <div data-configuration-restore-apply-zone hidden>
          <div class="settings-action-row">
            <button class="button" type="button" data-action="review-selected-restore">Review selected restore</button>
          </div>
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
        <p class="muted small settings-restore-footnote"><strong>Credentials are never restored.</strong> WU/Plex authentication stays a separate commissioning step. Plexamp Headless is exact-version/allow-list gated; Plexamp Home maps only logical order/hidden choices onto the live target context.</p>
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

  function loadPlexampBridgeClient() {
    if (
      window.ACPPlexampBrowserPreferences?.snapshot
      && window.ACPPlexampBrowserPreferences?.planHome
      && window.ACPPlexampBrowserPreferences?.applyHome
    ) return Promise.resolve(true);
    if (window.__acpPlexampBridgeClientPromise) return window.__acpPlexampBridgeClientPromise;

    window.__acpPlexampBridgeClientPromise = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = '/static/js/plexamp-browser-bridge.js?v=20260831-home-restore-v1';
      script.async = true;
      script.addEventListener('load', () => resolve(Boolean(
        window.ACPPlexampBrowserPreferences?.snapshot
        && window.ACPPlexampBrowserPreferences?.planHome
        && window.ACPPlexampBrowserPreferences?.applyHome
      )), { once: true });
      script.addEventListener('error', () => resolve(false), { once: true });
      document.head.append(script);
    });
    return window.__acpPlexampBridgeClientPromise;
  }

  function includeBrowserPreferences(backup, snapshot) {
    if (!backup || typeof backup !== 'object') return false;
    if (!snapshot || snapshot.schema_version !== 1) return false;
    if (!['ready', 'empty'].includes(snapshot.status)) return false;
    const home = snapshot.home;
    if (!home || typeof home !== 'object') return false;

    backup.plexamp = backup.plexamp && typeof backup.plexamp === 'object' ? backup.plexamp : {};
    backup.plexamp.browser_preferences = {
      schema_version: 1,
      home: {
        order: home.order === null ? null : Array.from(home.order),
        hidden: Array.from(home.hidden || []),
      },
    };

    const report = backup.export_report && typeof backup.export_report === 'object'
      ? backup.export_report
      : (backup.export_report = {});
    report.omitted = Array.isArray(report.omitted)
      ? report.omitted.filter((entry) => entry?.section !== 'plexamp.browser_preferences')
      : [];
    return true;
  }

  function recordBridgeOmission(backup, status) {
    if (!backup || typeof backup !== 'object') return;
    const report = backup.export_report && typeof backup.export_report === 'object'
      ? backup.export_report
      : (backup.export_report = {});
    report.warnings = Array.isArray(report.warnings) ? report.warnings : [];
    const safeStatus = String(status || 'unavailable').replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80) || 'unavailable';
    report.warnings.push(`Plexamp Home preferences were not included: browser bridge ${safeStatus}.`);
  }

  function replaceList(list, items, emptyText) {
    if (!list) return;
    list.replaceChildren();
    const values = Array.isArray(items) ? items : [];
    if (values.length === 0) {
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

  function browserHomeFromBackup(backup) {
    const browser = backup?.plexamp?.browser_preferences;
    if (!browser || browser.schema_version !== 1 || !browser.home || typeof browser.home !== 'object') return null;
    return browser.home;
  }

  async function previewBrowserHome(backup) {
    const home = browserHomeFromBackup(backup);
    if (!home) return null;
    const bridgeLoaded = await loadPlexampBridgeClient();
    if (!bridgeLoaded) {
      return {
        schema_version: 1,
        status: 'client-unavailable',
        read_only: true,
        restore_available: false,
      };
    }
    return window.ACPPlexampBrowserPreferences.planHome(home, { timeoutMs: 1800 });
  }

  function validateRestorePlan(plan) {
    if (
      !plan
      || plan.ok !== true
      || plan.read_only !== true
      || plan.apply_enabled !== false
      || typeof plan.restore_available !== 'boolean'
      || typeof plan.server_restore_available !== 'boolean'
      || typeof plan.plexamp_headless_restore_available !== 'boolean'
      || typeof plan.preview_token !== 'string'
      || !/^[a-f0-9]{32}$/.test(plan.preview_token)
    ) {
      throw new Error('Restore preview returned an invalid safety contract.');
    }
    return plan;
  }

  async function previewServer(backup) {
    const response = await fetch('/api/settings/restore/preview', {
      method: 'POST',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(backup),
    });
    const plan = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(plan.error || `Restore preview returned HTTP ${response.status}.`);
    }
    return validateRestorePlan(plan);
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function buildSelectedServerBackup(backup, targets) {
    const candidate = cloneJson(backup);
    if (!targets.acp) {
      candidate.a_clockwork_plex = { settings: {}, audio: {} };
    }

    const sourcePlexamp = candidate.plexamp && typeof candidate.plexamp === 'object'
      ? candidate.plexamp
      : {};
    const selectedPlexamp = {};
    if (targets.plexamp) {
      if (typeof sourcePlexamp.source_version === 'string') {
        selectedPlexamp.source_version = sourcePlexamp.source_version;
      }
      if (sourcePlexamp.headless_preferences && typeof sourcePlexamp.headless_preferences === 'object') {
        selectedPlexamp.headless_preferences = cloneJson(sourcePlexamp.headless_preferences);
      }
    }
    candidate.plexamp = selectedPlexamp;
    return candidate;
  }

  function planCounts(plan, browserPlan = null) {
    const acp = Number(plan?.server_change_count || 0);
    const headless = Number(plan?.plexamp_headless_change_count || 0);
    const headlessDetected = Number(plan?.plexamp_headless_detected_change_count || 0);
    const headlessDeferred = Number(plan?.plexamp_headless?.deferred_items || 0);
    const home = browserPlan?.status === 'ready' && browserPlan.restore_available === true
      ? Number(browserPlan.change_count || 0)
      : 0;
    return {
      acp,
      headless,
      headlessDetected,
      headlessDeferred,
      home,
      plexamp: headless + home,
      total: acp + headless + home,
    };
  }

  let selectedBackup = null;
  let fullPlan = null;
  let fullBrowserPlan = null;
  let reviewedServerBackup = null;
  let lastPlan = null;
  let reviewedBrowserPlan = null;
  let reviewedTargetSignature = '';
  let restoreInFlight = false;
  const selectedTargets = { acp: false, plexamp: false };

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
  const headlessSummary = page.querySelector('[data-configuration-restore-headless-summary]');
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

  function currentTargetSignature() {
    return `${selectedTargets.acp ? 'a' : '-'}${selectedTargets.plexamp ? 'p' : '-'}`;
  }

  function clearReviewedState({ keepStatus = false } = {}) {
    reviewedServerBackup = null;
    lastPlan = null;
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

  function invalidateReviewForSelectionChange() {
    clearReviewedState({ keepStatus: true });
    setStatus(
      reviewStatus,
      reviewPill,
      reviewMessage,
      'Selection changed',
      'Review the selected restore again before Confirm & restore becomes available.',
      'ready',
    );
  }

  function renderFullPreview(plan, browserPlan = null, { preserveSelection = false } = {}) {
    validateRestorePlan(plan);
    const counts = planCounts(plan, browserPlan);
    const previous = { ...selectedTargets };

    const acpAvailable = counts.acp > 0;
    const plexampAvailable = counts.plexamp > 0;
    setTarget(acpTarget, 'acp', acpAvailable, preserveSelection ? previous.acp : acpAvailable);
    setTarget(plexampTarget, 'plexamp', plexampAvailable, preserveSelection ? previous.plexamp : plexampAvailable);

    if (totalSummary) {
      const scope = counts.acp > 0 && counts.plexamp > 0
        ? (selectedTargets.acp && selectedTargets.plexamp ? 'Both selected' : 'Choose target')
        : (counts.acp > 0 ? 'ACP only' : (counts.plexamp > 0 ? 'Plexamp only' : 'No changes'));
      const selectedCount = (selectedTargets.acp ? counts.acp : 0) + (selectedTargets.plexamp ? counts.plexamp : 0);
      totalSummary.textContent = `${scope} · ${selectedCount} selected`;
    }
    if (acpSummary) acpSummary.textContent = counts.acp ? `${counts.acp} restorable` : 'No changes';
    if (plexampSummary) plexampSummary.textContent = counts.plexamp ? `${counts.plexamp} restorable` : 'No changes';

    if (headlessSummary) {
      if (counts.headlessDetected === 0) headlessSummary.textContent = 'Headless: no changes';
      else if (counts.headless > 0 && counts.headlessDeferred > 0) headlessSummary.textContent = `Headless: ${counts.headless} restorable, ${counts.headlessDeferred} deferred`;
      else if (counts.headless > 0) headlessSummary.textContent = `Headless: ${counts.headless} restorable`;
      else headlessSummary.textContent = `Headless: ${counts.headlessDeferred || counts.headlessDetected} deferred`;
    }

    const browser = plan.plexamp_browser && typeof plan.plexamp_browser === 'object'
      ? plan.plexamp_browser
      : {};
    if (browserSummary) {
      if (!browser.present) {
        browserSummary.textContent = 'Home: not present';
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

    const warnings = Array.isArray(plan.warnings)
      ? plan.warnings.filter((warning) => !String(warning).startsWith('Plexamp Home layout is valid and portable'))
      : [];
    if (browser.present && browserPlan) {
      if (browserPlan.status !== 'ready') {
        warnings.push(`Plexamp Home restore is unavailable: ${String(browserPlan.status).replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80) || 'unknown'}.`);
      } else {
        const missing = Number(browserPlan.missing_item_count || 0);
        const targetOnly = Number(browserPlan.target_only_item_count || 0);
        if (missing > 0) warnings.push(`${missing} saved Plexamp Home item${missing === 1 ? '' : 's'} are not present on this target and will be skipped.`);
        if (targetOnly > 0) warnings.push(`${targetOnly} target-only Plexamp Home item${targetOnly === 1 ? '' : 's'} will be retained.`);
      }
    }
    if (Array.isArray(plan.confirmations_required)) {
      plan.confirmations_required.forEach((confirmationName) => {
        warnings.push(`Restore confirmation required: ${String(confirmationName)}`);
      });
    }
    replaceList(warningsList, warnings, 'No restore warnings.');
    if (warningBox) warningBox.hidden = warnings.length === 0;

    const sections = plan.sections && typeof plan.sections === 'object'
      ? Object.entries(plan.sections)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([name, count]) => `${name}: ${Number(count || 0)}`)
      : [];
    if (counts.home > 0) sections.push(`plexamp.browser_preferences: ${counts.home}`);
    replaceList(sectionsList, sections, 'No portable changes detected.');

    const paths = Array.isArray(plan.changed_paths) ? plan.changed_paths.map((path) => String(path)) : [];
    if (browserPlan?.status === 'ready') {
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
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Ready to review',
        'Choose A Clockwork Plex, Plexamp, or both, then press Review selected restore. Nothing changes at Review.',
        'ready',
      );
    } else {
      hideStatus(reviewStatus);
    }
    if (restorePreview) restorePreview.hidden = false;
    return counts;
  }

  function restorePersistedResult() {
    let stored = null;
    try {
      stored = JSON.parse(sessionStorage.getItem(RESTORE_RESULT_KEY) || 'null');
    } catch (_error) {
      stored = null;
    }
    sessionStorage.removeItem(RESTORE_RESULT_KEY);
    if (!stored || stored.schema_version !== 1 || typeof stored.message !== 'string') return;
    if (!Number.isFinite(stored.created_at) || Date.now() - stored.created_at > 5 * 60 * 1000) return;
    setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', stored.message.slice(0, 500), 'success');
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

      const backup = await response.json();
      let browserIncluded = false;
      const bridgeLoaded = await loadPlexampBridgeClient();
      if (bridgeLoaded) {
        const browserSnapshot = await window.ACPPlexampBrowserPreferences.snapshot({ timeoutMs: 1800 });
        browserIncluded = includeBrowserPreferences(backup, browserSnapshot);
        if (!browserIncluded) recordBridgeOmission(backup, browserSnapshot?.status);
      } else {
        recordBridgeOmission(backup, 'client-unavailable');
      }

      const disposition = response.headers.get('Content-Disposition') || '';
      const filename = disposition.match(/filename="([^"]+)"/)?.[1]
        || 'A-Clockwork-Plex-backup.json';
      const blob = new Blob([`${JSON.stringify(backup, null, 2)}\n`], { type: 'application/json' });
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
        backupMessage.textContent = browserIncluded
          ? 'Backup downloaded, including Plexamp Home layout. Credentials and authentication were not included.'
          : 'Backup downloaded. Credentials were excluded; Plexamp Home layout was not available and is recorded as omitted.';
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
    if (restoreMessage) restoreMessage.classList.remove('is-conflict');
    setStatus(previewStatus, previewStatusPill, restoreMessage, 'Previewing…', 'Validating the backup and comparing portable settings.', 'busy');
    try {
      if (file.size > MAX_RESTORE_FILE_BYTES) {
        throw new Error('Backup file is larger than the 1 MB preview limit.');
      }
      const text = await file.text();
      let backup;
      try {
        backup = JSON.parse(text);
      } catch (_error) {
        throw new Error('The selected file is not valid JSON.');
      }

      const plan = await previewServer(backup);
      const browserPlan = await previewBrowserHome(backup);
      selectedBackup = backup;
      const counts = renderFullPreview(plan, browserPlan);
      const deferredCount = Number(plan.deferred_change_count || 0);
      if (counts.total === 0 && deferredCount === 0) {
        setStatus(previewStatus, previewStatusPill, restoreMessage, 'Preview complete', 'Backup is valid. No supported portable settings differ from this appliance.', 'success');
      } else if (counts.total > 0) {
        setStatus(
          previewStatus,
          previewStatusPill,
          restoreMessage,
          'Preview ready',
          `Backup is valid. ${counts.total} restorable change${counts.total === 1 ? '' : 's'} found. Choose A Clockwork Plex, Plexamp, or both below.`,
          'success',
        );
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

  function updateSelectionSummary() {
    if (!totalSummary || !fullPlan) return;
    const counts = planCounts(fullPlan, fullBrowserPlan);
    let scope = 'Choose target';
    if (selectedTargets.acp && selectedTargets.plexamp) scope = 'Both selected';
    else if (selectedTargets.acp) scope = 'ACP selected';
    else if (selectedTargets.plexamp) scope = 'Plexamp selected';
    const selectedCount = (selectedTargets.acp ? counts.acp : 0) + (selectedTargets.plexamp ? counts.plexamp : 0);
    totalSummary.textContent = `${scope} · ${selectedCount} selected`;
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
      const browserPlan = targets.plexamp ? await previewBrowserHome(selectedBackup) : null;
      const counts = planCounts(plan, browserPlan);
      if (counts.total === 0) {
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Nothing to restore', 'The selected targets already match this backup. Run Preview again if the appliance changed.', 'success');
        return;
      }

      reviewedServerBackup = serverBackup;
      lastPlan = plan;
      reviewedBrowserPlan = browserPlan;
      reviewedTargetSignature = currentTargetSignature();

      const selectedNames = [];
      if (targets.acp && counts.acp > 0) selectedNames.push('A Clockwork Plex');
      if (targets.plexamp && counts.plexamp > 0) selectedNames.push('Plexamp');
      const title = selectedNames.length === 2
        ? 'Restore A Clockwork Plex and Plexamp?'
        : `Restore ${selectedNames[0] || 'the selected configuration'}?`;
      if (confirmTitle) confirmTitle.textContent = title;

      const protectedSteps = counts.home > 0 && (counts.acp + counts.headless) > 0;
      const restartNotes = [];
      if (Array.isArray(plan.confirmations_required) && plan.confirmations_required.includes('airplay_restart')) {
        restartNotes.push('Shairport Sync will briefly restart for the restored AirPlay receiver name.');
      }
      if (counts.headless > 0) {
        restartNotes.push('Plexamp Headless will briefly restart while its allow-listed preferences are verified.');
      }
      if (confirmCopy) {
        confirmCopy.textContent = protectedSteps
          ? `One confirmation will run two protected steps: Plexamp Home first, then ACP/Headless. Each step verifies and owns its own rollback. ${restartNotes.join(' ')}`.trim()
          : `The selected owner will capture rollback state, apply only the reviewed differences and verify the result. ${restartNotes.join(' ')}`.trim();
      }

      const summary = [];
      if (targets.acp) summary.push(`A Clockwork Plex: ${counts.acp} path${counts.acp === 1 ? '' : 's'}`);
      if (targets.plexamp) {
        summary.push(`Plexamp Headless: ${counts.headless} path${counts.headless === 1 ? '' : 's'}`);
        summary.push(`Plexamp Home: ${counts.home} logical change${counts.home === 1 ? '' : 's'}`);
        if (counts.headlessDeferred > 0) summary.push(`Plexamp Headless deferred: ${counts.headlessDeferred}`);
      }
      replaceList(confirmSummary, summary, 'No selected differences remain.');
      if (confirmation) confirmation.hidden = false;
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Ready to confirm',
        `${counts.total} selected change${counts.total === 1 ? '' : 's'} reviewed. Confirm & restore is now the only mutating step.`,
        'success',
      );
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

  async function applyReviewedHome(home, browserPlan) {
    const bridgeLoaded = await loadPlexampBridgeClient();
    if (!bridgeLoaded) throw new Error('Plexamp Home bridge is unavailable. Run Preview restore again.');
    const result = await window.ACPPlexampBrowserPreferences.applyHome(
      home,
      browserPlan.target_fingerprint,
      { timeoutMs: 3000 },
    );
    if (result?.status === 'stale-target' || result?.fresh_preview_required === true) {
      throw new Error('Plexamp Home changed after Review. No Home settings were changed; run Preview restore again.');
    }
    if (!result || result.applied !== true || result.status !== 'applied') {
      if (result?.status === 'apply-failed' && result?.rolled_back === true) {
        throw new Error('Plexamp Home restore failed verification and the exact target Home state was rolled back. Run Preview restore again.');
      }
      if (result?.status === 'apply-failed') {
        throw new Error('Plexamp Home restore failed and rollback could not be fully verified. Do not retry until the Home layout is checked.');
      }
      throw new Error(`Plexamp Home restore was not applied (${String(result?.status || 'unavailable')}).`);
    }

    const verified = await window.ACPPlexampBrowserPreferences.planHome(home, { timeoutMs: 1800 });
    if (!verified || verified.status !== 'ready' || verified.restore_available !== false) {
      throw new Error('Plexamp Home write completed but the follow-up live verification did not converge.');
    }
    return Number(result.applied_change_count || 0);
  }

  async function applyReviewedServer(backup) {
    const response = await fetch('/api/settings/restore/apply', {
      method: 'POST',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        backup,
        preview_token: lastPlan.preview_token,
        confirm_restore: true,
        confirmations: Array.isArray(lastPlan.confirmations_required)
          ? lastPlan.confirmations_required
          : [],
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result.ok === false) {
      const restoreDetail = String(result.error || `Restore returned HTTP ${response.status}.`).trim();
      const error = new Error(restoreDetail);
      error.restoreBlocked = response.status === 409 && result.fresh_preview_required === true;
      error.rolledBack = result.rolled_back === true;
      throw error;
    }
    return result;
  }

  function setControlsDisabled(disabled) {
    [restoreButton, restoreFile, reviewButton, confirmButton, cancelButton, acpTarget, plexampTarget].forEach((control) => {
      if (control) control.disabled = disabled || (control === acpTarget && Number(fullPlan?.server_change_count || 0) === 0)
        || (control === plexampTarget && planCounts(fullPlan, fullBrowserPlan).plexamp === 0);
    });
  }

  confirmButton?.addEventListener('click', async () => {
    if (
      !selectedBackup
      || !reviewedServerBackup
      || !lastPlan
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

    let homeApplied = 0;
    let serverResult = null;
    try {
      const home = selectedTargets.plexamp ? browserHomeFromBackup(selectedBackup) : null;
      if (reviewedBrowserPlan?.status === 'ready' && reviewedBrowserPlan.restore_available === true) {
        if (!home) throw new Error('The reviewed Plexamp Home payload is no longer available. Run Preview restore again.');
        homeApplied = await applyReviewedHome(home, reviewedBrowserPlan);
      }

      if (Number(lastPlan.apply_change_count || 0) > 0) {
        serverResult = await applyReviewedServer(reviewedServerBackup);
      }

      const acpApplied = Number(serverResult?.server_applied_change_count || 0);
      const headlessApplied = Number(serverResult?.plexamp_headless_applied_change_count || 0);
      const totalApplied = acpApplied + headlessApplied + homeApplied;
      const parts = [];
      if (acpApplied > 0) parts.push(`${acpApplied} ACP/server`);
      if (headlessApplied > 0) parts.push(`${headlessApplied} Plexamp Headless`);
      if (homeApplied > 0) parts.push(`${homeApplied} Plexamp Home`);
      const success = `Restore verified: ${totalApplied} change${totalApplied === 1 ? '' : 's'} applied${parts.length ? ` (${parts.join(', ')})` : ''}. The live configuration now matches the selected parts of this backup.`;

      if (serverResult) {
        setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', success, 'success');
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Restore complete', 'The reviewed restore was applied and verified. Reloading Settings…', 'success');
        sessionStorage.setItem(RESTORE_RESULT_KEY, JSON.stringify({
          schema_version: 1,
          created_at: Date.now(),
          message: success,
        }));
        window.setTimeout(() => window.location.reload(), 650);
        return;
      }

      const refreshedPlan = await previewServer(selectedBackup);
      const refreshedBrowserPlan = await previewBrowserHome(selectedBackup);
      renderFullPreview(refreshedPlan, refreshedBrowserPlan);
      if (restoreMessage) restoreMessage.classList.remove('is-conflict');
      setStatus(resultStatus, resultPill, resultMessage, 'Restore complete', `${success} The live Home layout now matches this backup.`, 'success');
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Restore complete', 'The selected Plexamp restore was applied and verified.', 'success');
      const frame = document.getElementById('persistent-plexamp-frame');
      if (frame?.src) {
        window.setTimeout(() => {
          frame.src = frame.src;
        }, 350);
      }
    } catch (error) {
      const homePrefix = homeApplied > 0
        ? `Plexamp Home was restored (${homeApplied} logical change${homeApplied === 1 ? '' : 's'}), but the later ACP/Headless stage did not complete. `
        : '';
      const rollbackSuffix = error.rolledBack === true ? ' The failed server stage was rolled back.' : '';
      const blocked = error.restoreBlocked === true;
      clearReviewedState({ keepStatus: true });
      setStatus(
        resultStatus,
        resultPill,
        resultMessage,
        blocked ? 'Restore blocked' : 'Restore failed',
        `${homePrefix}${error.message || 'Restore failed.'}${rollbackSuffix} Run Preview restore again before another attempt.`,
        blocked ? 'warning' : 'error',
      );
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        blocked ? 'Restore blocked' : 'Restore failed',
        `${homePrefix}${error.message || 'Restore failed.'}${rollbackSuffix} Run Preview restore again before another attempt.`,
        blocked ? 'warning' : 'error',
      );
      if (restoreMessage) {
        restoreMessage.textContent = blocked
          ? `Restore blocked — no server settings were changed. ${error.message || ''}`.trim()
          : 'Run Preview restore again before another restore attempt.';
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