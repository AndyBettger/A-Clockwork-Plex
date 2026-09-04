(() => {
  'use strict';

  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexResetDefaultsLoaded) return;
  window.__aClockworkPlexResetDefaultsLoaded = true;

  const advanced = document.querySelector('[data-settings-section="advanced"]');
  const overview = advanced?.querySelector('[data-settings-overview="advanced"]');
  if (!advanced || !overview || advanced.querySelector('[data-settings-subpage="advanced:reset"]')) return;

  const PREVIEW_API = '/api/settings/reset/preview';
  const APPLY_API = '/api/settings/reset/apply';
  const RESULT_KEY = 'acp-reset-defaults-result-v3';
  const HOME_BRIDGE_SRC = '/static/js/plexamp-home-reset-bridge.js?v=20260904-reset-home-v3';
  const NATIVE_BRIDGE_SRC = '/static/js/plexamp-native-reset-bridge.js?v=20260904-native-reset-v1';
  // Historical CI vocabulary retained while older wiring guards still look for it:
  // Plexamp Home customisation.

  let serverPlan = null;
  let homePlan = null;
  let nativePlan = null;
  let busy = false;

  const row = document.createElement('button');
  row.className = 'settings-subpage-row';
  row.type = 'button';
  row.dataset.settingsSubpageTarget = 'advanced:reset';
  row.innerHTML = '<span><strong>Reset to defaults</strong><small>ACP + Plexamp settings, Home and appliance commissioning</small></span><span>›</span>';
  overview.append(row);

  const page = document.createElement('section');
  page.className = 'settings-subpage';
  page.dataset.settingsSubpage = 'advanced:reset';
  page.hidden = true;
  page.innerHTML = `
    <button class="settings-back" type="button" data-settings-back="advanced">‹ Advanced</button>
    <section class="settings-card">
      <div class="settings-card-heading">
        <div>
          <h3>Reset to defaults</h3>
          <p class="muted small">Return A Clockwork Plex and Plexamp user choices to their application or appliance defaults.</p>
        </div>
        <span class="settings-chip">Preview first</span>
      </div>
      <p class="muted small"><strong>This is not a factory wipe.</strong> Plexamp keeps its login, selected library and device/account identity. Plexamp's own Reset to Defaults semantics restore ordinary Plexamp settings; Home order and visibility return to their default state; A Clockwork Plex then restores the commissioned player name and managed audio output.</p>
      <div class="settings-restore-target-grid" role="group" aria-label="Reset owners">
        <div class="settings-restore-target" aria-pressed="true" data-reset-target="acp">
          <span class="settings-restore-target-title"><strong>A Clockwork Plex + managed Plexamp</strong><span class="settings-chip" data-reset-acp-summary>Not previewed</span></span>
          <small>Dashboard, display, Weather, News, alarms, AirPlay preferences, Master EQ, persistent mixer levels and appliance Plexamp commissioning.</small>
        </div>
        <div class="settings-restore-target" aria-pressed="true" data-reset-target="plexamp">
          <span class="settings-restore-target-title"><strong>Plexamp settings + Home customisation</strong><span class="settings-chip" data-reset-plexamp-summary>Not previewed</span></span>
          <small>Plexamp's native settings defaults, default Home order and all default Home sections visible.</small>
        </div>
      </div>
      <p class="muted small"><strong>Always preserved:</strong> Plex/Plexamp login, selected library, claim/session and account/machine identity; Chromium profile outside the bounded reset records; credentials; hardware topology; installed runtimes and services.</p>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-action="preview-reset-defaults">Preview reset</button>
      </div>
      <div class="settings-restore-status" data-reset-status hidden aria-live="polite">
        <span class="settings-chip" data-reset-status-pill>Reset preview</span>
        <span data-reset-status-message></span>
      </div>
    </section>

    <section class="settings-card" data-reset-preview hidden>
      <div class="settings-card-heading">
        <div><h3>Preview</h3><p class="muted small">Nothing has changed yet. Every reset owner is inspected before Review is enabled.</p></div>
        <span class="settings-chip" data-reset-change-summary>0 selected changes</span>
      </div>
      <div class="settings-restore-warning" data-reset-warning-box hidden>
        <strong>Warnings</strong>
        <ul class="muted small" data-reset-warnings></ul>
      </div>
      <div class="settings-restore-detail-grid">
        <div>
          <strong>Selected settings that would reset</strong>
          <ul class="muted small" data-reset-sections></ul>
        </div>
        <div>
          <strong>Always preserved</strong>
          <ul class="muted small" data-reset-preserved></ul>
        </div>
      </div>
      <p class="muted small" data-reset-native-detail>Plexamp native settings have not been inspected yet.</p>
      <p class="muted small" data-reset-home-detail>Plexamp Home has not been inspected yet.</p>
      <p class="muted small" data-reset-commissioning-detail>Plexamp commissioning has not been inspected yet.</p>
      <details class="settings-restore-details">
        <summary>Technical changed paths</summary>
        <ul class="muted small" data-reset-paths></ul>
      </details>
      <div class="settings-action-row" data-reset-review-zone hidden>
        <button class="button" type="button" data-action="review-reset-defaults">Review selected reset</button>
        <span class="muted small">Review refreshes every reset owner immediately before confirmation.</span>
      </div>
      <div class="settings-restore-status" data-reset-review-status hidden aria-live="polite">
        <span class="settings-chip" data-reset-review-pill>Review</span>
        <span data-reset-review-message></span>
      </div>
      <div class="setting-field settings-restore-confirmation" data-reset-confirm hidden>
        <span>Final confirmation</span>
        <strong>Reset the selected user customisation?</strong>
        <small>Browser-owned Plexamp settings/Home are protected by stale-preview checks and retained rollback state until the server-owned reset completes.</small>
        <ul class="muted small" data-reset-confirm-summary></ul>
        <div class="settings-action-row">
          <button class="button" type="button" data-action="confirm-reset-defaults">Confirm &amp; reset</button>
          <button class="button settings-secondary" type="button" data-action="cancel-reset-defaults">Cancel</button>
        </div>
      </div>
    </section>
  `;
  advanced.append(page);

  const previewButton = page.querySelector('[data-action="preview-reset-defaults"]');
  const reviewButton = page.querySelector('[data-action="review-reset-defaults"]');
  const confirmButton = page.querySelector('[data-action="confirm-reset-defaults"]');
  const cancelButton = page.querySelector('[data-action="cancel-reset-defaults"]');
  const previewPanel = page.querySelector('[data-reset-preview]');
  const reviewZone = page.querySelector('[data-reset-review-zone]');
  const confirmZone = page.querySelector('[data-reset-confirm]');
  const status = page.querySelector('[data-reset-status]');
  const statusPill = page.querySelector('[data-reset-status-pill]');
  const statusMessage = page.querySelector('[data-reset-status-message]');
  const reviewStatus = page.querySelector('[data-reset-review-status]');
  const reviewPill = page.querySelector('[data-reset-review-pill]');
  const reviewMessage = page.querySelector('[data-reset-review-message]');
  const acpSummary = page.querySelector('[data-reset-acp-summary]');
  const plexampSummary = page.querySelector('[data-reset-plexamp-summary]');
  const nativeDetail = page.querySelector('[data-reset-native-detail]');
  const homeDetail = page.querySelector('[data-reset-home-detail]');
  const commissioningDetail = page.querySelector('[data-reset-commissioning-detail]');
  const changeSummary = page.querySelector('[data-reset-change-summary]');
  const sectionsList = page.querySelector('[data-reset-sections]');
  const preservedList = page.querySelector('[data-reset-preserved]');
  const pathsList = page.querySelector('[data-reset-paths]');
  const warningsBox = page.querySelector('[data-reset-warning-box]');
  const warningsList = page.querySelector('[data-reset-warnings]');
  const confirmSummary = page.querySelector('[data-reset-confirm-summary]');

  function showPage() {
    overview.hidden = true;
    advanced.querySelectorAll('[data-settings-subpage]').forEach((candidate) => {
      candidate.hidden = candidate !== page;
    });
    page.hidden = false;
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', '#advanced/reset');
  }

  function showOverview() {
    page.hidden = true;
    overview.hidden = false;
    document.querySelector('.settings-detail')?.scrollTo({ top: 0, behavior: 'auto' });
    history.replaceState(null, '', '#advanced');
  }

  row.addEventListener('click', showPage);
  page.querySelector('[data-settings-back="advanced"]')?.addEventListener('click', showOverview);

  function settingsHaveUnsavedChanges() {
    const saveButton = document.querySelector('#settings-unified-form button[type="submit"]');
    return Boolean(saveButton && !saveButton.disabled);
  }

  function replaceList(node, values, emptyText) {
    if (!node) return;
    node.replaceChildren();
    const items = Array.isArray(values) && values.length ? values : [emptyText];
    items.forEach((value) => {
      const item = document.createElement('li');
      item.textContent = String(value);
      node.append(item);
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

  function setBusy(value) {
    busy = value;
    [previewButton, reviewButton, confirmButton, cancelButton].forEach((button) => {
      if (button) button.disabled = value;
    });
  }

  function serverChangeCount() {
    return Number(serverPlan?.change_count || 0);
  }

  function acpChangeCount() {
    return Number(serverPlan?.acp_change_count ?? serverPlan?.change_count ?? 0);
  }

  function commissioningChangeCount() {
    return Number(serverPlan?.plexamp_commissioning_change_count || 0);
  }

  function nativeChangeCount() {
    return nativePlan?.status === 'ready' ? Number(nativePlan.change_count || 0) : 0;
  }

  function homeChangeCount() {
    return homePlan?.status === 'ready' ? Number(homePlan.change_count || 0) : 0;
  }

  function browserOwnersReady() {
    return nativePlan?.status === 'ready' && homePlan?.status === 'ready';
  }

  function selectedChangeCount() {
    return serverChangeCount() + nativeChangeCount() + homeChangeCount();
  }

  function selectedWorkAvailable() {
    return browserOwnersReady() && selectedChangeCount() > 0;
  }

  function invalidateReview() {
    confirmZone.hidden = true;
    hideStatus(reviewStatus);
  }

  function validateServerPlan(value) {
    if (
      !value
      || value.ok !== true
      || value.read_only !== true
      || value.apply_enabled !== false
      || typeof value.reset_available !== 'boolean'
      || typeof value.reset_token !== 'string'
      || !/^[a-f0-9]{32}$/.test(value.reset_token)
      || !Number.isInteger(value.change_count)
      || value.change_count < 0
    ) throw new Error('Reset preview returned an invalid server safety contract.');

    if (
      value.acp_change_count !== undefined
      && (!Number.isInteger(value.acp_change_count) || value.acp_change_count < 0)
    ) throw new Error('Reset preview returned an invalid ACP change count.');

    if (
      value.plexamp_commissioning_change_count !== undefined
      && (!Number.isInteger(value.plexamp_commissioning_change_count)
        || value.plexamp_commissioning_change_count < 0
        || value.plexamp_commissioning_change_count > 2)
    ) throw new Error('Reset preview returned an invalid Plexamp commissioning change count.');

    const acpToken = value.owner_tokens?.a_clockwork_plex;
    if (typeof acpToken !== 'string' || !/^[a-f0-9]{32}$/.test(acpToken)) {
      throw new Error('Reset preview did not include a valid ACP owner token.');
    }
    return value;
  }

  async function fetchServerPlan() {
    const response = await fetch(PREVIEW_API, {
      method: 'POST',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: '{}',
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Reset preview returned HTTP ${response.status}.`);
    }
    return validateServerPlan(payload);
  }

  function loadBridge(globalName, promiseName, src, methods) {
    if (methods.every((method) => typeof window[globalName]?.[method] === 'function')) {
      return Promise.resolve(true);
    }
    if (window[promiseName]) return window[promiseName];
    window[promiseName] = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.addEventListener('load', () => resolve(
        methods.every((method) => typeof window[globalName]?.[method] === 'function'),
      ), { once: true });
      script.addEventListener('error', () => resolve(false), { once: true });
      document.head.append(script);
    });
    return window[promiseName];
  }

  function loadHomeResetBridge() {
    return loadBridge(
      'ACPPlexampHomeReset',
      '__acpPlexampHomeResetBridgePromise',
      HOME_BRIDGE_SRC,
      ['plan', 'apply', 'rollback', 'finalize'],
    );
  }

  function loadNativeResetBridge() {
    return loadBridge(
      'ACPPlexampNativeReset',
      '__acpPlexampNativeResetBridgePromise',
      NATIVE_BRIDGE_SRC,
      ['plan', 'apply', 'rollback', 'finalize'],
    );
  }

  async function fetchHomePlan() {
    if (!(await loadHomeResetBridge())) {
      return { schema_version: 1, status: 'client-unavailable', read_only: true, reset_available: false };
    }
    const result = await window.ACPPlexampHomeReset.plan({ timeoutMs: 2200 });
    return result && typeof result.status === 'string'
      ? result
      : { schema_version: 1, status: 'invalid-response', read_only: true, reset_available: false };
  }

  async function fetchNativePlan() {
    if (!(await loadNativeResetBridge())) {
      return { schema_version: 1, status: 'client-unavailable', read_only: true, reset_available: false };
    }
    const result = await window.ACPPlexampNativeReset.plan({ timeoutMs: 2200 });
    return result && typeof result.status === 'string'
      ? result
      : { schema_version: 1, status: 'invalid-response', read_only: true, reset_available: false };
  }

  function filteredPreserved() {
    const values = Array.isArray(serverPlan?.preserved) ? serverPlan.preserved : [];
    const filtered = values.filter((value) => {
      const text = String(value);
      return !text.includes('Plexamp Headless preferences') && !text.includes('Plexamp Home layout');
    });
    return [
      ...filtered,
      'Plexamp login, selected library, claim/session, account capability and machine identity',
      'Chromium profile outside the bounded Plexamp settings/Home reset records',
    ];
  }

  function renderPlans() {
    previewPanel.hidden = false;
    invalidateReview();

    const commissioningCount = commissioningChangeCount();
    const nativeCount = nativeChangeCount();
    const homeCount = homeChangeCount();
    const selectedCount = selectedChangeCount();

    if (acpSummary) {
      const serverCount = serverChangeCount();
      acpSummary.textContent = serverCount
        ? `${serverCount} selected change${serverCount === 1 ? '' : 's'}`
        : 'Already at baselines';
    }

    if (plexampSummary) {
      plexampSummary.textContent = !browserOwnersReady()
        ? 'Inspection unavailable'
        : `${nativeCount} setting${nativeCount === 1 ? '' : 's'} · ${homeCount} Home`;
    }

    const sections = Object.entries(serverPlan?.sections || {}).map(
      ([name, total]) => `${name} · ${total}`,
    );
    if (nativeCount) sections.push(`plexamp.native-settings · ${nativeCount}`);
    if (homeCount) sections.push(`plexamp.home · ${homeCount}`);
    replaceList(sectionsList, sections, 'All supported reset owners already match their baselines.');

    replaceList(
      preservedList,
      filteredPreserved(),
      'Credential and appliance-owned identity remains preserved.',
    );

    const technicalPaths = Array.isArray(serverPlan?.changed_paths)
      ? Array.from(serverPlan.changed_paths)
      : [];
    if (nativeCount) technicalPaths.push(`plexamp.native-settings · ${nativeCount}`);
    if (homePlan?.status === 'ready') {
      if (Number(homePlan.order_record_count || 0)) technicalPaths.push('plexamp.home.order');
      if (Number(homePlan.hidden_record_count || 0)) technicalPaths.push('plexamp.home.visibility');
      if (Number(homePlan.legacy_record_count || 0)) technicalPaths.push('plexamp.home.legacy-migration-state');
    }
    replaceList(pathsList, technicalPaths, 'No supported technical paths differ.');

    const commissioning = serverPlan?.plexamp_commissioning || {};
    if (commissioningDetail) {
      if (commissioning.ready !== true) {
        commissioningDetail.textContent = commissioning.reason === 'baseline-missing'
          ? 'Plexamp commissioning: no captured player-name baseline yet. Run setup once before using full Reset.'
          : 'Plexamp commissioning could not be safely inspected.';
      } else if (!commissioningCount) {
        commissioningDetail.textContent = 'Plexamp commissioning already matches its captured player-name baseline and the managed A Clockwork Plex - Plexamp audio output.';
      } else {
        const parts = [];
        if (commissioning.player_name_changed === true) {
          parts.push('player name will return to the name captured during appliance setup');
        }
        if (commissioning.audio_output_changed === true) {
          parts.push('audio output will return to A Clockwork Plex - Plexamp');
        }
        commissioningDetail.textContent = `Plexamp commissioning: ${parts.join('; ')}.`;
      }
    }

    if (nativeDetail) {
      nativeDetail.textContent = nativePlan?.status !== 'ready'
        ? `Plexamp native settings inspection is unavailable (${String(nativePlan?.status || 'unknown').replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80)}).`
        : nativeCount
          ? `${nativeCount} ordinary Plexamp setting${nativeCount === 1 ? '' : 's'} differ from Plexamp's own defaults. Player name and audio output are handled separately by appliance commissioning.`
          : 'Ordinary Plexamp settings already match Plexamp defaults.';
    }

    if (homeDetail) {
      if (homePlan?.status !== 'ready') {
        homeDetail.textContent = `Plexamp Home inspection is unavailable (${String(homePlan?.status || 'unknown').replace(/[^A-Za-z0-9_.-]/g, '').slice(0, 80)}).`;
      } else if (homeCount) {
        homeDetail.textContent = `${homePlan.order_record_count || 0} Home order record${Number(homePlan.order_record_count || 0) === 1 ? '' : 's'} and ${homePlan.hidden_record_count || 0} visibility record${Number(homePlan.hidden_record_count || 0) === 1 ? '' : 's'} will be cleared using Plexamp's own undefined/reset semantics. Default order and all default sections will be visible afterwards.`;
      } else {
        homeDetail.textContent = 'Plexamp Home already has no current or legacy order/visibility overrides.';
      }
    }

    const warnings = Array.isArray(serverPlan?.warnings) ? Array.from(serverPlan.warnings) : [];
    if (nativePlan?.status !== 'ready') {
      warnings.push('Plexamp native reset owner is unavailable. Full Reset is blocked until the local bridge is available.');
    }
    if (homePlan?.status !== 'ready') {
      warnings.push('Plexamp Home reset owner is unavailable. Full Reset is blocked until the local bridge is available.');
    }
    warningsBox.hidden = warnings.length === 0;
    replaceList(warningsList, warnings, 'No warnings.');

    if (changeSummary) {
      changeSummary.textContent = `${selectedCount} selected change${selectedCount === 1 ? '' : 's'}`;
    }
    reviewZone.hidden = !selectedWorkAvailable();

    if (!browserOwnersReady()) {
      setStatus(
        status,
        statusPill,
        statusMessage,
        'Preview incomplete',
        'The local Plexamp browser reset owner is unavailable. Reboot Chromium after updating the bridge, then preview again.',
        'warning',
      );
    } else {
      setStatus(
        status,
        statusPill,
        statusMessage,
        selectedCount ? 'Preview ready' : 'Already at baselines',
        selectedCount
          ? `${serverChangeCount()} server-owned, ${nativeCount} Plexamp setting and ${homeCount} Plexamp Home change${selectedCount === 1 ? '' : 's'} found. Nothing has changed yet.`
          : 'A Clockwork Plex, Plexamp settings, Home order/visibility and commissioning already match their baselines.',
        'ready',
      );
    }
  }

  async function refreshPlans() {
    const [freshServer, freshHome, freshNative] = await Promise.all([
      fetchServerPlan(),
      fetchHomePlan(),
      fetchNativePlan(),
    ]);
    serverPlan = freshServer;
    homePlan = freshHome;
    nativePlan = freshNative;
    renderPlans();
  }

  async function previewReset() {
    if (busy) return;
    if (settingsHaveUnsavedChanges()) {
      setStatus(
        status,
        statusPill,
        statusMessage,
        'Save or discard first',
        'There are staged Settings changes. Save or discard them before previewing a reset.',
        'warning',
      );
      return;
    }

    setBusy(true);
    setStatus(
      status,
      statusPill,
      statusMessage,
      'Previewing…',
      'Reading ACP, Plexamp native settings, Home order/visibility and appliance commissioning.',
      'ready',
    );
    try {
      await refreshPlans();
    } catch (error) {
      serverPlan = null;
      homePlan = null;
      nativePlan = null;
      previewPanel.hidden = true;
      setStatus(
        status,
        statusPill,
        statusMessage,
        'Preview failed',
        error.message || 'Could not preview reset.',
        'error',
      );
    } finally {
      setBusy(false);
    }
  }

  async function reviewReset() {
    if (busy) return;
    if (settingsHaveUnsavedChanges()) {
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Save or discard first',
        'Staged Settings changes must be resolved before reset.',
        'warning',
      );
      return;
    }

    setBusy(true);
    setStatus(
      reviewStatus,
      reviewPill,
      reviewMessage,
      'Reviewing…',
      'Refreshing every protected reset owner.',
      'ready',
    );
    try {
      await refreshPlans();
      if (!browserOwnersReady()) {
        setStatus(
          reviewStatus,
          reviewPill,
          reviewMessage,
          'Review blocked',
          'The local Plexamp reset bridge is unavailable.',
          'warning',
        );
        return;
      }
      if (!selectedWorkAvailable()) {
        setStatus(
          reviewStatus,
          reviewPill,
          reviewMessage,
          'Nothing to reset',
          'Every supported owner now matches its baseline.',
          'ready',
        );
        return;
      }

      const summary = [];
      const acpCount = acpChangeCount();
      const commissioningCount = commissioningChangeCount();
      const nativeCount = nativeChangeCount();
      const homeCount = homeChangeCount();
      const commissioning = serverPlan?.plexamp_commissioning || {};

      summary.push(
        acpCount
          ? `${acpCount} A Clockwork Plex change${acpCount === 1 ? '' : 's'} will be reset.`
          : 'A Clockwork Plex settings already match the current defaults.',
      );

      summary.push(
        nativeCount
          ? `${nativeCount} ordinary Plexamp setting${nativeCount === 1 ? '' : 's'} will return to Plexamp's own defaults.`
          : 'Ordinary Plexamp settings already match Plexamp defaults.',
      );

      summary.push(
        homeCount
          ? 'Plexamp Home order will return to its default and all default Home sections will be visible.'
          : 'Plexamp Home order and visibility already have no resettable overrides.',
      );

      if (commissioningCount) {
        if (commissioning.player_name_changed === true) {
          summary.push('The Plexamp player name will return to the name captured when this appliance was commissioned.');
        }
        if (commissioning.audio_output_changed === true) {
          summary.push('The Plexamp audio output will return to A Clockwork Plex - Plexamp.');
        }
      } else if (commissioning.ready === true && nativeCount) {
        summary.push('Plexamp native reset may temporarily change player name/output; appliance commissioning will reapply both before completion.');
      } else if (commissioning.ready !== true) {
        summary.push('Plexamp commissioning is unavailable, so the complete multi-owner Reset is not safe to run.');
      }

      if ((serverPlan.confirmations_required || []).includes('airplay_restart')) {
        summary.push('The AirPlay receiver name will return to its default and Shairport Sync will briefly restart.');
      }
      summary.push('Plex/Plexamp login, selected library, claim/session, account/machine identity and hardware topology will be preserved.');

      replaceList(confirmSummary, summary, 'No changes are selected.');
      confirmZone.hidden = commissioning.ready !== true && nativeCount > 0;
      if (confirmZone.hidden) {
        setStatus(
          reviewStatus,
          reviewPill,
          reviewMessage,
          'Review blocked',
          'Plexamp commissioning must be available before native Plexamp settings can be reset safely.',
          'warning',
        );
      } else {
        setStatus(
          reviewStatus,
          reviewPill,
          reviewMessage,
          'Ready to confirm',
          'The fresh multi-owner reset plan is current. Confirm below to apply it.',
          'ready',
        );
      }
    } catch (error) {
      confirmZone.hidden = true;
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Review failed',
        error.message || 'Could not refresh reset plan.',
        'error',
      );
    } finally {
      setBusy(false);
    }
  }

  async function applyServerIfNeeded() {
    if (!serverPlan?.reset_available) {
      return {
        attempted: false,
        applied: false,
        count: 0,
        acpCount: 0,
        commissioningCount: 0,
      };
    }

    const response = await fetch(APPLY_API, {
      method: 'POST',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reset_token: serverPlan.reset_token,
        confirm_reset: true,
        confirmations: Array.isArray(serverPlan.confirmations_required)
          ? serverPlan.confirmations_required
          : [],
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `A Clockwork Plex reset returned HTTP ${response.status}.`);
    }

    return {
      attempted: true,
      applied: true,
      count: Number(payload.applied_change_count || 0),
      acpCount: Number(payload.acp_applied_change_count ?? payload.applied_change_count ?? 0),
      commissioningCount: Number(payload.plexamp_commissioning_applied_change_count || 0),
    };
  }

  async function rollbackBrowserOwners(tokens) {
    const failures = [];
    if (tokens.home) {
      const result = await window.ACPPlexampHomeReset.rollback(tokens.home, { timeoutMs: 2500 });
      if (result?.rolled_back !== true || result?.verified !== true) failures.push('Plexamp Home');
    }
    if (tokens.native) {
      const result = await window.ACPPlexampNativeReset.rollback(tokens.native, { timeoutMs: 2500 });
      if (result?.rolled_back !== true || result?.verified !== true) failures.push('Plexamp settings');
    }
    return failures;
  }

  async function finalizeBrowserOwners(tokens) {
    if (tokens.home) {
      await window.ACPPlexampHomeReset.finalize(tokens.home, { timeoutMs: 1800 }).catch(() => {});
    }
    if (tokens.native) {
      await window.ACPPlexampNativeReset.finalize(tokens.native, { timeoutMs: 1800 }).catch(() => {});
    }
  }

  async function applyBrowserOwners() {
    const tokens = { native: null, home: null };
    const result = { nativeCount: 0, homeCount: 0, tokens };

    try {
      if (nativePlan?.reset_available) {
        const nativeResult = await window.ACPPlexampNativeReset.apply(
          nativePlan.target_fingerprint,
          { timeoutMs: 4000 },
        );
        if (nativeResult?.status === 'stale-target') {
          throw new Error('Plexamp settings changed after Review. Preview again.');
        }
        if (nativeResult?.applied !== true || !nativeResult.rollback_token) {
          throw new Error('Plexamp native settings reset did not complete and verify.');
        }
        tokens.native = nativeResult.rollback_token;
        result.nativeCount = Number(nativeResult.applied_change_count || 0);
      }

      if (homePlan?.reset_available) {
        const homeResult = await window.ACPPlexampHomeReset.apply(
          homePlan.target_fingerprint,
          { timeoutMs: 3000 },
        );
        if (homeResult?.status === 'stale-target') {
          throw new Error('Plexamp Home changed after Review. Preview again.');
        }
        if (homeResult?.applied !== true || !homeResult.rollback_token) {
          throw new Error('Plexamp Home reset did not complete and verify.');
        }
        tokens.home = homeResult.rollback_token;
        result.homeCount = Number(homeResult.applied_change_count || 0);
      }

      return result;
    } catch (error) {
      const failures = await rollbackBrowserOwners(tokens);
      if (failures.length) {
        throw new Error(`${error.message || error} Browser rollback also failed for ${failures.join(' + ')}.`);
      }
      throw error;
    }
  }

  async function confirmReset() {
    if (busy || !selectedWorkAvailable()) return;
    if (settingsHaveUnsavedChanges()) {
      confirmZone.hidden = true;
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Reset blocked',
        'Settings changed after Review. Save or discard them and preview again.',
        'warning',
      );
      return;
    }

    setBusy(true);
    setStatus(
      reviewStatus,
      reviewPill,
      reviewMessage,
      'Resetting…',
      'Applying Plexamp browser owners, then the protected server-owned reset.',
      'ready',
    );

    let browserResult = null;
    try {
      const reviewedAcpToken = serverPlan?.owner_tokens?.a_clockwork_plex;
      browserResult = await applyBrowserOwners();

      const freshServer = await fetchServerPlan();
      if (freshServer?.owner_tokens?.a_clockwork_plex !== reviewedAcpToken) {
        throw new Error('A Clockwork Plex settings changed after Review. The browser reset will be rolled back; preview again.');
      }
      serverPlan = freshServer;

      if (nativeChangeCount() && serverPlan?.plexamp_commissioning?.ready !== true) {
        throw new Error('Plexamp commissioning became unavailable after native reset.');
      }

      const serverResult = await applyServerIfNeeded();
      await finalizeBrowserOwners(browserResult.tokens);

      const totalCount = Number(serverResult.count || 0)
        + Number(browserResult.nativeCount || 0)
        + Number(browserResult.homeCount || 0);

      window.sessionStorage?.setItem?.(RESULT_KEY, JSON.stringify({
        message: 'Selected reset completed and verified.',
        count: totalCount,
        home: browserResult.homeCount > 0,
        native: browserResult.nativeCount > 0,
        acp: serverResult.acpCount > 0,
        commissioning: serverResult.commissioningCount > 0,
      }));
      window.location.hash = 'advanced/reset';
      window.location.reload();
    } catch (error) {
      let rollbackFailures = [];
      if (browserResult?.tokens) {
        rollbackFailures = await rollbackBrowserOwners(browserResult.tokens);
      }
      confirmZone.hidden = true;
      const suffix = rollbackFailures.length
        ? ` Browser rollback failed for ${rollbackFailures.join(' + ')}.`
        : browserResult
          ? ' Browser-owned Plexamp changes were rolled back.'
          : '';
      setStatus(
        reviewStatus,
        reviewPill,
        reviewMessage,
        'Reset failed',
        `${error.message || 'The selected reset did not complete.'}${suffix}`,
        'error',
      );
    } finally {
      setBusy(false);
    }
  }

  previewButton?.addEventListener('click', previewReset);
  reviewButton?.addEventListener('click', reviewReset);
  confirmButton?.addEventListener('click', confirmReset);
  cancelButton?.addEventListener('click', () => {
    confirmZone.hidden = true;
    setStatus(
      reviewStatus,
      reviewPill,
      reviewMessage,
      'Cancelled',
      'Nothing was changed. Preview again whenever you are ready.',
      'ready',
    );
  });

  if (location.hash === '#advanced/reset') showPage();

  try {
    const saved = JSON.parse(window.sessionStorage?.getItem?.(RESULT_KEY) || 'null');
    if (saved && typeof saved === 'object') {
      window.sessionStorage?.removeItem?.(RESULT_KEY);
      showPage();
      const ownerLabels = [];
      if (saved.acp) ownerLabels.push('A Clockwork Plex');
      if (saved.native) ownerLabels.push('Plexamp settings');
      if (saved.home) ownerLabels.push('Plexamp Home');
      if (saved.commissioning) ownerLabels.push('Plexamp commissioning');
      const owners = ownerLabels.length ? ownerLabels.join(' + ') : 'Selected owners';
      setStatus(
        status,
        statusPill,
        statusMessage,
        'Reset complete',
        `${saved.message} ${Number(saved.count || 0)} change${Number(saved.count || 0) === 1 ? '' : 's'} applied across ${owners}.`,
        'ready',
      );
    }
  } catch (_error) {
    window.sessionStorage?.removeItem?.(RESULT_KEY);
  }
})();
