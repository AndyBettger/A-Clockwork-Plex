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
          <p class="muted small">Preview first. Only a fresh, explicitly confirmed preview can restore supported configuration.</p>
        </div>
        <span class="settings-chip">Rollback protected</span>
      </div>
      <p class="muted small"><strong>Preview never changes the appliance.</strong> The selected JSON file is parsed in the browser and checked in memory. The preview reports configuration paths and counts only; it does not display saved values.</p>
      <label class="setting-field">
        <span>Backup file</span>
        <input type="file" accept=".json,application/json" data-configuration-restore-file>
        <small data-configuration-restore-file-status>Select an A Clockwork Plex JSON backup, up to 1 MB.</small>
      </label>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-action="preview-configuration-restore" disabled>Preview restore</button>
        <span class="muted small" data-configuration-restore-message>No file selected.</span>
      </div>
      <div data-configuration-restore-preview hidden>
        <div class="settings-grid two-col">
          <div class="setting-field"><span>Restorable now</span><strong data-configuration-restore-change-count>0</strong><small>Total supported paths across the server and live-browser transactions in this fresh preview.</small></div>
          <div class="setting-field"><span>ACP / server</span><strong data-configuration-restore-server-count>0</strong><small>Settings, Master EQ and persistent mixer paths that differ from this appliance.</small></div>
          <div class="setting-field"><span>Plexamp Headless</span><strong data-configuration-restore-headless-summary>No changes</strong><small>Only the eight typed allow-listed preferences can be restored, and only when the installed Plexamp version is an exact match.</small></div>
          <div class="setting-field"><span>Plexamp Home layout</span><strong data-configuration-restore-browser-summary>Not present</strong><small>Compared against the commissioned target library and restored separately through the local browser owner.</small></div>
        </div>
        <div class="settings-grid two-col">
          <div class="setting-field">
            <span>Changed sections</span>
            <ul class="muted small" data-configuration-restore-sections></ul>
          </div>
          <div class="setting-field">
            <span>Warnings and confirmations</span>
            <ul class="muted small" data-configuration-restore-warnings></ul>
          </div>
        </div>
        <details>
          <summary>Technical changed paths</summary>
          <ul class="muted small" data-configuration-restore-paths></ul>
        </details>
        <div data-configuration-restore-apply-zone hidden>
          <p class="muted small"><strong>This transaction applies only the server/Headless owners marked restorable in the preview.</strong> ACP Settings/EQ/mixer use their existing transaction owners. Compatible Plexamp Headless preferences use the narrow version-aware preference owner and briefly restart Plexamp.</p>
          <div class="settings-action-row">
            <button class="button" type="button" data-action="apply-configuration-restore">Restore supported settings</button>
            <span class="muted small" data-configuration-restore-apply-message>A fresh preview is required immediately before restore.</span>
          </div>
          <div class="setting-field" data-configuration-restore-confirm hidden>
            <span>Confirm restore</span>
            <strong data-configuration-restore-confirm-title>Apply the previewed server changes?</strong>
            <small data-configuration-restore-confirm-copy>A rollback snapshot will be captured before the first owner changes.</small>
            <div class="settings-action-row">
              <button class="button" type="button" data-action="confirm-configuration-restore">Confirm restore</button>
              <button class="button settings-secondary" type="button" data-action="cancel-configuration-restore">Cancel</button>
            </div>
          </div>
        </div>
        <div data-configuration-browser-restore-zone hidden>
          <p class="muted small"><strong>Plexamp Home uses its own live-browser transaction.</strong> The target's current Home context is discovered locally; source account/library keys are never transplanted. Unknown saved hubs are skipped and target-only hubs are retained.</p>
          <div class="settings-action-row">
            <button class="button" type="button" data-action="apply-plexamp-home-restore">Review Plexamp Home restore</button>
            <span class="muted small" data-configuration-browser-restore-message>A fresh live-browser preview is required.</span>
          </div>
          <div class="setting-field" data-configuration-browser-restore-confirm hidden>
            <span>Confirm Plexamp Home restore</span>
            <strong>Apply the previewed Home layout?</strong>
            <small>The browser owner captures the exact target Local Storage values it will touch and restores them if write or verification fails.</small>
            <div class="settings-action-row">
              <button class="button" type="button" data-action="confirm-plexamp-home-restore">Confirm Home restore</button>
              <button class="button settings-secondary" type="button" data-action="cancel-plexamp-home-restore">Cancel</button>
            </div>
          </div>
        </div>
        <p class="muted small"><strong>Credentials are never restored.</strong> WU/Plex authentication stays a separate commissioning step. Plexamp Headless restore is exact-version and allow-list gated; Plexamp Home restore maps only logical order/hidden choices onto the live target context.</p>
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

  let selectedBackup = null;
  let lastPlan = null;
  let lastBrowserPlan = null;
  let restoreInFlight = false;
  let browserRestoreInFlight = false;

  function resetApplyState() {
    const applyZone = page.querySelector('[data-configuration-restore-apply-zone]');
    const confirmation = page.querySelector('[data-configuration-restore-confirm]');
    const applyMessage = page.querySelector('[data-configuration-restore-apply-message]');
    const browserZone = page.querySelector('[data-configuration-browser-restore-zone]');
    const browserConfirmation = page.querySelector('[data-configuration-browser-restore-confirm]');
    const browserMessage = page.querySelector('[data-configuration-browser-restore-message]');
    if (applyZone) applyZone.hidden = true;
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) applyMessage.textContent = 'A fresh preview is required immediately before restore.';
    if (browserZone) browserZone.hidden = true;
    if (browserConfirmation) browserConfirmation.hidden = true;
    if (browserMessage) browserMessage.textContent = 'A fresh live-browser preview is required.';
    lastPlan = null;
    lastBrowserPlan = null;
  }

  function renderRestorePreview(plan, browserPlan = null) {
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

    const container = page.querySelector('[data-configuration-restore-preview]');
    const changeCount = page.querySelector('[data-configuration-restore-change-count]');
    const serverCount = page.querySelector('[data-configuration-restore-server-count]');
    const headlessSummary = page.querySelector('[data-configuration-restore-headless-summary]');
    const browserSummary = page.querySelector('[data-configuration-restore-browser-summary]');
    const sectionsList = page.querySelector('[data-configuration-restore-sections]');
    const warningsList = page.querySelector('[data-configuration-restore-warnings]');
    const pathsList = page.querySelector('[data-configuration-restore-paths]');
    const applyZone = page.querySelector('[data-configuration-restore-apply-zone]');
    const confirmation = page.querySelector('[data-configuration-restore-confirm]');
    const applyMessage = page.querySelector('[data-configuration-restore-apply-message]');
    const browserZone = page.querySelector('[data-configuration-browser-restore-zone]');
    const browserConfirmation = page.querySelector('[data-configuration-browser-restore-confirm]');
    const browserMessage = page.querySelector('[data-configuration-browser-restore-message]');

    const serverApplyCount = Number(plan.apply_change_count || 0);
    const browserApplyCount = browserPlan?.status === 'ready' && browserPlan.restore_available === true
      ? Number(browserPlan.change_count || 0)
      : 0;
    if (changeCount) changeCount.textContent = String(serverApplyCount + browserApplyCount);
    if (serverCount) serverCount.textContent = String(Number(plan.server_change_count || 0));

    const headless = plan.plexamp_headless && typeof plan.plexamp_headless === 'object'
      ? plan.plexamp_headless
      : {};
    if (headlessSummary) {
      const detected = Number(plan.plexamp_headless_detected_change_count || 0);
      const restorable = Number(headless.restorable_items || 0);
      const deferred = Number(headless.deferred_items || 0);
      if (detected === 0) headlessSummary.textContent = 'No changes';
      else if (restorable > 0 && deferred > 0) headlessSummary.textContent = `${restorable} restorable · ${deferred} deferred`;
      else if (restorable > 0) headlessSummary.textContent = `${restorable} restorable`;
      else headlessSummary.textContent = `${deferred || detected} deferred`;
    }

    const browser = plan.plexamp_browser && typeof plan.plexamp_browser === 'object'
      ? plan.plexamp_browser
      : {};
    if (browserSummary) {
      if (!browser.present) {
        browserSummary.textContent = 'Not present';
      } else if (!browserPlan || browserPlan.status !== 'ready') {
        browserSummary.textContent = 'Unavailable';
      } else if (browserPlan.restore_available) {
        const missing = Number(browserPlan.missing_item_count || 0);
        browserSummary.textContent = `${Number(browserPlan.change_count || 0)} restorable${missing ? ` · ${missing} unavailable` : ''}`;
      } else {
        const missing = Number(browserPlan.missing_item_count || 0);
        browserSummary.textContent = missing ? `No changes · ${missing} unavailable` : 'No changes';
      }
    }

    const sections = plan.sections && typeof plan.sections === 'object'
      ? Object.entries(plan.sections)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([name, count]) => `${name}: ${Number(count || 0)}`)
      : [];
    if (browserApplyCount > 0) sections.push(`plexamp.browser_preferences: ${browserApplyCount}`);
    replaceList(sectionsList, sections, 'No portable changes detected.');

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
    replaceList(warningsList, warnings, 'No restore warnings or confirmations.');

    const paths = Array.isArray(plan.changed_paths) ? plan.changed_paths : [];
    const pathLines = paths.map((path) => String(path));
    if (browserPlan?.status === 'ready') {
      if (browserPlan.order_changed) pathLines.push('plexamp.browser_preferences.home.order');
      if (Number(browserPlan.hidden_change_count || 0) > 0) pathLines.push('plexamp.browser_preferences.home.hidden');
    }
    if (plan.changed_paths_truncated) pathLines.push('…additional changed paths omitted from preview');
    replaceList(pathsList, pathLines, 'No changed portable paths.');

    lastPlan = plan;
    lastBrowserPlan = browserPlan;
    if (applyZone) applyZone.hidden = plan.restore_available !== true || serverApplyCount === 0;
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) {
      applyMessage.textContent = plan.restore_available
        ? (browserApplyCount > 0
          ? 'Preview is current. Restore Plexamp Home first, then confirm the server/Headless transaction.'
          : 'Preview is current. Restore still requires explicit confirmation.')
        : 'No server/Headless changes need restoring.';
    }
    if (browserZone) browserZone.hidden = !(browserPlan?.status === 'ready' && browserPlan.restore_available === true);
    if (browserConfirmation) browserConfirmation.hidden = true;
    if (browserMessage) {
      if (browserPlan?.status === 'ready' && browserPlan.restore_available === true) {
        browserMessage.textContent = 'Live target preview is current. Home restore still requires explicit confirmation.';
      } else if (browser.present && browserPlan?.status === 'ready') {
        browserMessage.textContent = 'The saved Home layout already matches the restorable target context.';
      } else {
        browserMessage.textContent = 'No live-browser Home changes are currently restorable.';
      }
    }
    if (container) container.hidden = false;
  }

  const backupMessage = page.querySelector('[data-configuration-backup-message]');
  const backupButton = page.querySelector('[data-action="download-configuration-backup"]');
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

  const restoreFile = page.querySelector('[data-configuration-restore-file]');
  const restoreFileStatus = page.querySelector('[data-configuration-restore-file-status]');
  const restoreMessage = page.querySelector('[data-configuration-restore-message]');
  const restoreButton = page.querySelector('[data-action="preview-configuration-restore"]');
  const restorePreview = page.querySelector('[data-configuration-restore-preview]');
  const applyButton = page.querySelector('[data-action="apply-configuration-restore"]');
  const confirmButton = page.querySelector('[data-action="confirm-configuration-restore"]');
  const cancelButton = page.querySelector('[data-action="cancel-configuration-restore"]');
  const confirmation = page.querySelector('[data-configuration-restore-confirm]');
  const confirmCopy = page.querySelector('[data-configuration-restore-confirm-copy]');
  const applyMessage = page.querySelector('[data-configuration-restore-apply-message]');
  const browserApplyButton = page.querySelector('[data-action="apply-plexamp-home-restore"]');
  const browserConfirmButton = page.querySelector('[data-action="confirm-plexamp-home-restore"]');
  const browserCancelButton = page.querySelector('[data-action="cancel-plexamp-home-restore"]');
  const browserConfirmation = page.querySelector('[data-configuration-browser-restore-confirm]');
  const browserMessage = page.querySelector('[data-configuration-browser-restore-message]');

  restoreFile?.addEventListener('change', () => {
    selectedBackup = null;
    resetApplyState();
    if (restoreMessage) restoreMessage.classList.remove('is-conflict');
    if (restorePreview) restorePreview.hidden = true;
    const file = restoreFile.files?.[0] || null;
    if (!file) {
      if (restoreFileStatus) restoreFileStatus.textContent = 'Select an A Clockwork Plex JSON backup, up to 1 MB.';
      if (restoreMessage) restoreMessage.textContent = 'No file selected.';
      if (restoreButton) restoreButton.disabled = true;
      return;
    }
    if (file.size > MAX_RESTORE_FILE_BYTES) {
      if (restoreFileStatus) restoreFileStatus.textContent = `${file.name} is larger than the 1 MB preview limit.`;
      if (restoreMessage) restoreMessage.textContent = 'Choose a smaller backup file.';
      if (restoreButton) restoreButton.disabled = true;
      return;
    }
    if (restoreFileStatus) restoreFileStatus.textContent = `${file.name} · ${file.size.toLocaleString()} bytes`;
    if (restoreMessage) restoreMessage.textContent = 'Ready for a read-only preview.';
    if (restoreButton) restoreButton.disabled = false;
  });

  restoreButton?.addEventListener('click', async () => {
    const file = restoreFile?.files?.[0] || null;
    if (!file || restoreInFlight || browserRestoreInFlight) return;
    restoreButton.disabled = true;
    selectedBackup = null;
    resetApplyState();
    if (restoreMessage) restoreMessage.classList.remove('is-conflict');
    if (restorePreview) restorePreview.hidden = true;
    if (restoreMessage) restoreMessage.textContent = 'Validating backup and comparing portable settings…';
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
      const browserPlan = await previewBrowserHome(backup);
      selectedBackup = backup;
      renderRestorePreview(plan, browserPlan);
      const serverApplyCount = Number(plan.apply_change_count || 0);
      const browserApplyCount = browserPlan?.status === 'ready' && browserPlan.restore_available === true
        ? Number(browserPlan.change_count || 0)
        : 0;
      const totalApplyCount = serverApplyCount + browserApplyCount;
      const deferredCount = Number(plan.deferred_change_count || 0);
      const serverCount = Number(plan.server_change_count || 0);
      const headlessCount = Number(plan.plexamp_headless_change_count || 0);
      if (restoreMessage) {
        if (totalApplyCount === 0 && deferredCount === 0) {
          restoreMessage.textContent = 'Backup is valid. No supported portable settings differ from this appliance.';
        } else if (totalApplyCount > 0) {
          restoreMessage.textContent = `Backup is valid. ${totalApplyCount} supported path${totalApplyCount === 1 ? '' : 's'} can be restored now (${serverCount} ACP/server, ${headlessCount} Plexamp Headless, ${browserApplyCount} Plexamp Home).`;
        } else {
          restoreMessage.textContent = 'Backup is valid. Only deferred Plexamp changes remain.';
        }
      }
    } catch (error) {
      selectedBackup = null;
      resetApplyState();
      if (restoreMessage) restoreMessage.textContent = error.message || 'Could not preview this backup.';
    } finally {
      restoreButton.disabled = false;
    }
  });

  browserApplyButton?.addEventListener('click', () => {
    if (
      !selectedBackup
      || !lastPlan
      || !lastBrowserPlan
      || lastBrowserPlan.status !== 'ready'
      || lastBrowserPlan.restore_available !== true
      || restoreInFlight
      || browserRestoreInFlight
    ) return;
    if (browserConfirmation) browserConfirmation.hidden = false;
    if (browserMessage) browserMessage.textContent = 'Review the Home confirmation below. Nothing has changed yet.';
  });

  browserCancelButton?.addEventListener('click', () => {
    if (browserConfirmation) browserConfirmation.hidden = true;
    if (browserMessage) browserMessage.textContent = 'Plexamp Home restore cancelled. The live preview remains available.';
  });

  browserConfirmButton?.addEventListener('click', async () => {
    const home = browserHomeFromBackup(selectedBackup);
    if (
      !home
      || !lastPlan
      || !lastBrowserPlan
      || lastBrowserPlan.status !== 'ready'
      || lastBrowserPlan.restore_available !== true
      || restoreInFlight
      || browserRestoreInFlight
    ) return;

    browserRestoreInFlight = true;
    if (browserConfirmation) browserConfirmation.hidden = true;
    if (browserApplyButton) browserApplyButton.disabled = true;
    if (browserConfirmButton) browserConfirmButton.disabled = true;
    if (applyButton) applyButton.disabled = true;
    if (restoreButton) restoreButton.disabled = true;
    if (restoreFile) restoreFile.disabled = true;
    if (browserMessage) browserMessage.textContent = 'Capturing target Home rollback state and applying the live-browser transaction…';

    try {
      const bridgeLoaded = await loadPlexampBridgeClient();
      if (!bridgeLoaded) throw new Error('Plexamp Home bridge is unavailable. Run Preview restore again.');
      const result = await window.ACPPlexampBrowserPreferences.applyHome(
        home,
        lastBrowserPlan.target_fingerprint,
        { timeoutMs: 3000 },
      );
      if (result?.status === 'stale-target' || result?.fresh_preview_required === true) {
        throw new Error('Plexamp Home changed after Preview. No Home settings were changed; run Preview restore again.');
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
      renderRestorePreview(lastPlan, verified);
      if (browserMessage) {
        const count = Number(result.applied_change_count || 0);
        browserMessage.textContent = `Plexamp Home restore verified: ${count} logical change${count === 1 ? '' : 's'} applied. Reloading the Plexamp surface…`;
      }
      const frame = document.getElementById('persistent-plexamp-frame');
      if (frame?.src) {
        window.setTimeout(() => {
          frame.src = frame.src;
        }, 350);
      }
    } catch (error) {
      lastBrowserPlan = null;
      const browserZone = page.querySelector('[data-configuration-browser-restore-zone]');
      if (browserZone) browserZone.hidden = true;
      if (browserMessage) browserMessage.textContent = error.message || 'Plexamp Home restore failed.';
      if (restoreMessage) restoreMessage.textContent = 'Run Preview restore again before another Plexamp Home restore attempt.';
    } finally {
      browserRestoreInFlight = false;
      if (browserApplyButton) browserApplyButton.disabled = false;
      if (browserConfirmButton) browserConfirmButton.disabled = false;
      if (applyButton) applyButton.disabled = false;
      if (restoreButton) restoreButton.disabled = false;
      if (restoreFile) restoreFile.disabled = false;
    }
  });

  applyButton?.addEventListener('click', () => {
    if (!selectedBackup || !lastPlan || lastPlan.restore_available !== true || restoreInFlight || browserRestoreInFlight) return;
    if (lastBrowserPlan?.status === 'ready' && lastBrowserPlan.restore_available === true) {
      if (applyMessage) applyMessage.textContent = 'Restore the separately previewed Plexamp Home layout first, then confirm the server/Headless transaction.';
      return;
    }
    if (settingsHaveUnsavedChanges()) {
      if (applyMessage) applyMessage.textContent = 'Save or discard the staged Settings changes before restoring a backup.';
      return;
    }
    const confirmations = Array.isArray(lastPlan.confirmations_required)
      ? lastPlan.confirmations_required
      : [];
    const headlessCount = Number(lastPlan.plexamp_headless_change_count || 0);
    if (confirmCopy) {
      if (confirmations.includes('airplay_restart')) {
        confirmCopy.textContent = headlessCount > 0
          ? 'A rollback snapshot will be captured first. Shairport Sync and Plexamp will each briefly restart while their explicitly previewed settings are applied.'
          : 'A rollback snapshot will be captured first. This restore also changes the AirPlay receiver name, so Shairport Sync will briefly restart.';
      } else if (headlessCount > 0) {
        confirmCopy.textContent = 'A rollback snapshot will be captured first. Compatible Plexamp Headless preferences will be applied through the narrow owner, so Plexamp will briefly restart.';
      } else {
        confirmCopy.textContent = 'A rollback snapshot will be captured before Settings, EQ or mixer state is changed.';
      }
    }
    if (confirmation) confirmation.hidden = false;
    if (applyMessage) applyMessage.textContent = 'Review the confirmation below. Nothing has changed yet.';
  });

  cancelButton?.addEventListener('click', () => {
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) applyMessage.textContent = 'Restore cancelled. The preview remains available.';
  });

  confirmButton?.addEventListener('click', async () => {
    if (!selectedBackup || !lastPlan || restoreInFlight || browserRestoreInFlight) return;
    if (lastBrowserPlan?.status === 'ready' && lastBrowserPlan.restore_available === true) {
      if (confirmation) confirmation.hidden = true;
      if (applyMessage) applyMessage.textContent = 'Restore Plexamp Home first, then review the server/Headless confirmation again.';
      return;
    }
    if (settingsHaveUnsavedChanges()) {
      if (confirmation) confirmation.hidden = true;
      if (applyMessage) applyMessage.textContent = 'Save or discard the staged Settings changes before restoring a backup.';
      return;
    }

    restoreInFlight = true;
    if (confirmation) confirmation.hidden = true;
    if (applyButton) applyButton.disabled = true;
    if (confirmButton) confirmButton.disabled = true;
    if (browserApplyButton) browserApplyButton.disabled = true;
    if (restoreButton) restoreButton.disabled = true;
    if (restoreFile) restoreFile.disabled = true;
    if (applyMessage) applyMessage.textContent = 'Capturing rollback state and restoring supported configuration…';

    let restoreRetryMessage = 'Restore failed. Run Preview restore again before any retry.';
    let restoreWasBlocked = false;
    try {
      const response = await fetch('/api/settings/restore/apply', {
        method: 'POST',
        cache: 'no-store',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          backup: selectedBackup,
          preview_token: lastPlan.preview_token,
          confirm_restore: true,
          confirmations: Array.isArray(lastPlan.confirmations_required)
            ? lastPlan.confirmations_required
            : [],
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.ok === false) {
        const restoreDetail = String(
          result.error || `Restore returned HTTP ${response.status}.`,
        ).trim();
        const rollbackText = result.rolled_back === true
          ? ' Previous supported state was rolled back.'
          : '';
        if (response.status === 409 && result.fresh_preview_required === true) {
          restoreWasBlocked = true;
          restoreRetryMessage = `Restore blocked — no settings were changed. ${restoreDetail}`;
        } else if (result.fresh_preview_required === true) {
          restoreRetryMessage = `Restore failed. ${restoreDetail} Run Preview restore again before any retry.`;
        }
        throw new Error(`${restoreDetail}${rollbackText}`);
      }
      selectedBackup = null;
      lastPlan = null;
      lastBrowserPlan = null;
      if (applyMessage) {
        const count = Number(result.applied_change_count || 0);
        const serverApplied = Number(result.server_applied_change_count || 0);
        const headlessApplied = Number(result.plexamp_headless_applied_change_count || 0);
        applyMessage.textContent = `Restore verified: ${count} path${count === 1 ? '' : 's'} applied (${serverApplied} ACP/server, ${headlessApplied} Plexamp Headless). Reloading Settings…`;
      }
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      if (applyMessage) applyMessage.textContent = error.message || 'Restore failed.';
      resetApplyState();
      if (restoreMessage) {
        restoreMessage.textContent = restoreRetryMessage;
        restoreMessage.classList.toggle('is-conflict', restoreWasBlocked);
      }
    } finally {
      restoreInFlight = false;
      if (applyButton) applyButton.disabled = false;
      if (confirmButton) confirmButton.disabled = false;
      if (browserApplyButton) browserApplyButton.disabled = false;
      if (restoreButton) restoreButton.disabled = false;
      if (restoreFile) restoreFile.disabled = false;
    }
  });

  if (location.hash === '#advanced/backup') showPage();
})();
