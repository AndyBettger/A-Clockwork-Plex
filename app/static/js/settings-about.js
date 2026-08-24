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
          <p class="muted small">Preview first. Only a fresh, explicitly confirmed preview can restore supported server-owned settings.</p>
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
          <div class="setting-field"><span>Restorable now</span><strong data-configuration-restore-change-count>0</strong><small>ACP Settings, Master EQ and persistent mixer paths that differ from this appliance.</small></div>
          <div class="setting-field"><span>Plexamp Home layout</span><strong data-configuration-restore-browser-summary>Not present</strong><small>Validated here; comparison/application belongs to the later live-browser restore stage.</small></div>
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
          <p class="muted small"><strong>This phase restores ACP Settings, Master EQ and the four persistent mixer levels only.</strong> Plexamp Headless preferences and Home layout remain deferred and are not written by this button.</p>
          <div class="settings-action-row">
            <button class="button" type="button" data-action="apply-configuration-restore">Restore server settings</button>
            <span class="muted small" data-configuration-restore-apply-message>A fresh preview is required immediately before restore.</span>
          </div>
          <div class="setting-field" data-configuration-restore-confirm hidden>
            <span>Confirm restore</span>
            <strong data-configuration-restore-confirm-title>Apply the previewed changes?</strong>
            <small data-configuration-restore-confirm-copy>A rollback snapshot will be captured before the first owner changes.</small>
            <div class="settings-action-row">
              <button class="button" type="button" data-action="confirm-configuration-restore">Confirm restore</button>
              <button class="button settings-secondary" type="button" data-action="cancel-configuration-restore">Cancel</button>
            </div>
          </div>
        </div>
        <p class="muted small"><strong>Credentials are never restored.</strong> WU/Plex authentication stays a separate commissioning step, and Plexamp preference/layout restore remains disabled until its own owner-specific stages are implemented.</p>
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
    if (window.ACPPlexampBrowserPreferences?.snapshot) return Promise.resolve(true);
    if (window.__acpPlexampBridgeClientPromise) return window.__acpPlexampBridgeClientPromise;

    window.__acpPlexampBridgeClientPromise = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = '/static/js/plexamp-browser-bridge.js?v=20260824-home-backup-v2';
      script.async = true;
      script.addEventListener('load', () => resolve(Boolean(window.ACPPlexampBrowserPreferences?.snapshot)), { once: true });
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

  let selectedBackup = null;
  let lastPlan = null;
  let restoreInFlight = false;

  function resetApplyState() {
    const applyZone = page.querySelector('[data-configuration-restore-apply-zone]');
    const confirmation = page.querySelector('[data-configuration-restore-confirm]');
    const applyMessage = page.querySelector('[data-configuration-restore-apply-message]');
    if (applyZone) applyZone.hidden = true;
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) applyMessage.textContent = 'A fresh preview is required immediately before restore.';
    lastPlan = null;
  }

  function renderRestorePreview(plan) {
    if (
      !plan
      || plan.ok !== true
      || plan.read_only !== true
      || plan.apply_enabled !== false
      || typeof plan.server_restore_available !== 'boolean'
      || typeof plan.preview_token !== 'string'
      || !/^[a-f0-9]{32}$/.test(plan.preview_token)
    ) {
      throw new Error('Restore preview returned an invalid safety contract.');
    }

    const container = page.querySelector('[data-configuration-restore-preview]');
    const changeCount = page.querySelector('[data-configuration-restore-change-count]');
    const browserSummary = page.querySelector('[data-configuration-restore-browser-summary]');
    const sectionsList = page.querySelector('[data-configuration-restore-sections]');
    const warningsList = page.querySelector('[data-configuration-restore-warnings]');
    const pathsList = page.querySelector('[data-configuration-restore-paths]');
    const applyZone = page.querySelector('[data-configuration-restore-apply-zone]');
    const confirmation = page.querySelector('[data-configuration-restore-confirm]');
    const applyMessage = page.querySelector('[data-configuration-restore-apply-message]');

    if (changeCount) changeCount.textContent = String(Number(plan.apply_change_count || 0));

    const browser = plan.plexamp_browser && typeof plan.plexamp_browser === 'object'
      ? plan.plexamp_browser
      : {};
    if (browserSummary) {
      browserSummary.textContent = browser.present
        ? `${Number(browser.order_items || 0)} ordered · ${Number(browser.hidden_items || 0)} hidden`
        : 'Not present';
    }

    const sections = plan.sections && typeof plan.sections === 'object'
      ? Object.entries(plan.sections)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([name, count]) => `${name}: ${Number(count || 0)}`)
      : [];
    replaceList(sectionsList, sections, 'No portable changes detected.');

    const warnings = Array.isArray(plan.warnings) ? Array.from(plan.warnings) : [];
    if (Array.isArray(plan.confirmations_required)) {
      plan.confirmations_required.forEach((confirmationName) => {
        warnings.push(`Restore confirmation required: ${String(confirmationName)}`);
      });
    }
    replaceList(warningsList, warnings, 'No restore warnings or confirmations.');

    const paths = Array.isArray(plan.changed_paths) ? plan.changed_paths : [];
    const pathLines = paths.map((path) => String(path));
    if (plan.changed_paths_truncated) pathLines.push('…additional changed paths omitted from preview');
    replaceList(pathsList, pathLines, 'No changed portable paths.');

    lastPlan = plan;
    if (applyZone) applyZone.hidden = plan.server_restore_available !== true || Number(plan.apply_change_count || 0) === 0;
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) {
      applyMessage.textContent = plan.server_restore_available
        ? 'Preview is current. Restore still requires explicit confirmation.'
        : 'No currently supported server-owned changes need restoring.';
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

  restoreFile?.addEventListener('change', () => {
    selectedBackup = null;
    resetApplyState();
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
    if (!file || restoreInFlight) return;
    restoreButton.disabled = true;
    selectedBackup = null;
    resetApplyState();
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
      selectedBackup = backup;
      renderRestorePreview(plan);
      const applyCount = Number(plan.apply_change_count || 0);
      const deferredCount = Number(plan.deferred_change_count || 0);
      if (restoreMessage) {
        if (applyCount === 0 && deferredCount === 0) {
          restoreMessage.textContent = 'Backup is valid. No supported server-owned portable settings differ from this appliance.';
        } else if (applyCount > 0) {
          restoreMessage.textContent = `Backup is valid. ${applyCount} server-owned setting path${applyCount === 1 ? '' : 's'} can be restored now.`;
        } else {
          restoreMessage.textContent = 'Backup is valid. Only deferred Plexamp preference changes remain.';
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

  applyButton?.addEventListener('click', () => {
    if (!selectedBackup || !lastPlan || lastPlan.server_restore_available !== true || restoreInFlight) return;
    if (settingsHaveUnsavedChanges()) {
      if (applyMessage) applyMessage.textContent = 'Save or discard the staged Settings changes before restoring a backup.';
      return;
    }
    const confirmations = Array.isArray(lastPlan.confirmations_required)
      ? lastPlan.confirmations_required
      : [];
    if (confirmCopy) {
      confirmCopy.textContent = confirmations.includes('airplay_restart')
        ? 'A rollback snapshot will be captured first. This restore also changes the AirPlay receiver name, so Shairport Sync will briefly restart.'
        : 'A rollback snapshot will be captured before Settings, EQ or mixer state is changed.';
    }
    if (confirmation) confirmation.hidden = false;
    if (applyMessage) applyMessage.textContent = 'Review the confirmation below. Nothing has changed yet.';
  });

  cancelButton?.addEventListener('click', () => {
    if (confirmation) confirmation.hidden = true;
    if (applyMessage) applyMessage.textContent = 'Restore cancelled. The preview remains available.';
  });

  confirmButton?.addEventListener('click', async () => {
    if (!selectedBackup || !lastPlan || restoreInFlight) return;
    if (settingsHaveUnsavedChanges()) {
      if (confirmation) confirmation.hidden = true;
      if (applyMessage) applyMessage.textContent = 'Save or discard the staged Settings changes before restoring a backup.';
      return;
    }

    restoreInFlight = true;
    if (confirmation) confirmation.hidden = true;
    if (applyButton) applyButton.disabled = true;
    if (confirmButton) confirmButton.disabled = true;
    if (restoreButton) restoreButton.disabled = true;
    if (restoreFile) restoreFile.disabled = true;
    if (applyMessage) applyMessage.textContent = 'Capturing rollback state and restoring supported server-owned settings…';

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
        const rollbackText = result.rolled_back === true
          ? ' Previous server-owned state was rolled back.'
          : '';
        throw new Error(`${result.error || `Restore returned HTTP ${response.status}.`}${rollbackText}`);
      }
      selectedBackup = null;
      lastPlan = null;
      if (applyMessage) {
        const count = Number(result.applied_change_count || 0);
        applyMessage.textContent = `Restore verified: ${count} server-owned path${count === 1 ? '' : 's'} applied. Reloading Settings…`;
      }
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      if (applyMessage) applyMessage.textContent = error.message || 'Restore failed.';
      resetApplyState();
      if (restoreMessage) restoreMessage.textContent = 'Run Preview restore again before any retry.';
    } finally {
      restoreInFlight = false;
      if (applyButton) applyButton.disabled = false;
      if (confirmButton) confirmButton.disabled = false;
      if (restoreButton) restoreButton.disabled = false;
      if (restoreFile) restoreFile.disabled = false;
    }
  });

  if (location.hash === '#advanced/backup') showPage();
})();
