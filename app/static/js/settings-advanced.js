(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const mount = document.getElementById('settings-advanced-alarm-diagnostics');
  if (!mount) return;

  const endpoints = {
    status: '/api/alarms/scheduler',
    test: '/api/alarms/audio/test',
    cancel: '/api/alarms/test/cancel',
    preview: '/api/alarms/audio/preview',
    audioStop: '/api/alarms/audio/stop',
  };
  const PASSIVE_REFRESH_MS = 30000;
  const PREVIEW_COPY = 'Fixed at 15% through the appliance alarm output and capped independently from the scheduled alarm volume.';
  let requestInFlight = false;
  let timer = null;
  let hasRendered = false;
  let previewButton = null;
  let previewResetTimer = null;

  function pageVisible() {
    const page = mount.closest('[data-settings-subpage]');
    return Boolean(page && !page.hidden && !document.hidden);
  }

  function formatTime(value, fallback = 'Not yet') {
    if (!value) return fallback;
    return window.ACPTime?.formatDateTime?.(value, { seconds: true, weekday: 'short' })
      || fallback;
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Alarm runtime returned HTTP ${response.status}.`);
    }
    return payload;
  }

  function activeSummary(scheduler = {}, audio = {}) {
    const active = scheduler.active_occurrence;
    if (!active) return ['Idle', 'No active, snoozed or pending alarm.'];
    if (scheduler.snoozed_until) {
      return [
        `${active.label || 'Alarm'} · snoozed`,
        `Returns ${formatTime(scheduler.snoozed_until)} · snooze ${active.snooze_count || 0}`,
      ];
    }
    if (audio.playback_active) {
      return [
        `${active.label || 'Alarm'} · screen and sound active`,
        audio.current_tone_label || active?.source?.tone_id || 'Local tone',
      ];
    }
    return [
      `${active.label || 'Alarm'} · screen active`,
      active.test_mode ? 'Alarm test' : 'Scheduled occurrence',
    ];
  }

  function reading(label, value, detail = '') {
    const wrapper = document.createElement('div');
    wrapper.className = 'settings-status-reading';
    const labelNode = document.createElement('span');
    labelNode.textContent = label;
    const valueNode = document.createElement('strong');
    valueNode.textContent = value;
    const detailNode = document.createElement('small');
    detailNode.textContent = detail;
    wrapper.append(labelNode, valueNode, detailNode);
    return wrapper;
  }

  function render(payload) {
    const scheduler = payload.scheduler || {};
    const audio = payload.audio || {};
    const next = scheduler.next_occurrence;
    const [activeTitle, activeDetail] = activeSummary(scheduler, audio);
    const card = document.createElement('section');
    card.className = 'settings-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h3>Alarm runtime</h3>
          <p class="muted small">Scheduler state, screen takeover, duplicate protection and controlled tests.</p>
        </div>
        <span class="settings-chip${scheduler.running ? '' : ' is-warning'}" data-alarm-runtime-health>${scheduler.running ? 'Running' : 'Stopped'}</span>
      </div>
      <div class="settings-status-grid" data-alarm-runtime-readings></div>
      <div class="settings-action-row">
        <button class="button settings-secondary" type="button" data-alarm-runtime-action="recalculate">Recalculate now</button>
        <button class="button" type="button" data-alarm-runtime-action="test">Test alarm in 10 seconds</button>
        <button class="button settings-secondary" type="button" data-alarm-runtime-action="cancel">Clear alarm test</button>
        <span class="muted small" data-alarm-runtime-message></span>
      </div>
    `;
    const readings = card.querySelector('[data-alarm-runtime-readings]');
    readings.append(
      reading(
        'Next alarm',
        next ? `${next.label || 'Alarm'} · ${formatTime(next.scheduled_for)}` : 'No enabled alarms',
        next ? `${next.wall_time || ''} · ${next.timezone || scheduler.timezone || 'Local time'}` : 'The scheduler is enjoying the silence.',
      ),
      reading('Runtime state', activeTitle, activeDetail),
      reading('Last checked', formatTime(scheduler.last_check_at), `Scheduler interval ${scheduler.poll_seconds || 15}s`),
      reading('Queued', `${scheduler.queued_occurrence_count || 0} alarm${Number(scheduler.queued_occurrence_count || 0) === 1 ? '' : 's'}`, `${scheduler.duplicate_protection_count || 0} protected occurrence keys`),
      reading('Scheduled sound', audio.scheduled_playback_enabled ? 'Enabled' : 'Safety locked', audio.playback_lockout_reason || 'Two-key sound safety'),
      reading('Last occurrence', scheduler.last_observed_occurrence?.label || 'None recorded', scheduler.last_observed_occurrence ? formatTime(scheduler.last_observed_occurrence.scheduled_for) : 'No scheduler occurrence observed yet'),
    );
    mount.replaceChildren(card);
    hasRendered = true;
    card.querySelectorAll('[data-alarm-runtime-action]').forEach((button) => {
      button.addEventListener('click', () => runAction(button.dataset.alarmRuntimeAction));
    });
  }

  function setBusy(busy, message = '') {
    requestInFlight = busy;
    mount.querySelectorAll('[data-alarm-runtime-action]').forEach((button) => { button.disabled = busy; });
    const output = mount.querySelector('[data-alarm-runtime-message]');
    if (output && message) output.textContent = message;
  }

  async function refresh(recalculate = false, force = false) {
    if (requestInFlight || (!force && !pageVisible())) return;
    setBusy(true, recalculate ? 'Recalculating…' : hasRendered ? 'Refreshing…' : 'Loading…');
    try {
      const payload = await requestJson(endpoints.status, { method: recalculate ? 'POST' : 'GET' });
      render(payload);
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = payload.message || 'Alarm runtime status refreshed.';
    } catch (error) {
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = error.message || 'Alarm runtime unavailable.';
    } finally {
      setBusy(false);
    }
  }

  function actionAudioState(payload) {
    if (payload.audio && typeof payload.audio === 'object') return payload.audio;
    const runtime = payload.runtime && typeof payload.runtime === 'object' ? payload.runtime : {};
    return { ...runtime, ...payload };
  }

  async function runAction(action) {
    if (action === 'recalculate') return refresh(true, true);
    if (requestInFlight) return;
    const endpoint = action === 'cancel' ? endpoints.cancel : endpoints.test;
    const label = action === 'cancel' ? 'Clearing alarm test…' : 'Arming screen and sound test…';
    setBusy(true, label);
    try {
      const payload = await requestJson(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'test' ? { full_screen: true, delay_seconds: 10 } : {}),
      });
      render({ scheduler: payload.scheduler, audio: actionAudioState(payload) });
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = payload.message || 'Alarm runtime action completed.';
    } catch (error) {
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = error.message || 'Alarm runtime action failed.';
    } finally {
      setBusy(false);
    }
  }

  function resetPreviewButton(button = previewButton) {
    window.clearTimeout(previewResetTimer);
    previewResetTimer = null;
    if (button) {
      button.disabled = false;
      button.textContent = 'Preview tone';
      button.setAttribute('aria-pressed', 'false');
    }
    if (button === previewButton) previewButton = null;
  }

  function toneIdForPreview(button) {
    return button.closest('.alarm-sound-grid')?.querySelector('select')?.value || '';
  }

  function updatePreviewCopy(root = document) {
    root.querySelectorAll?.('.alarm-preview-row small').forEach((node) => {
      if (node.textContent !== PREVIEW_COPY) node.textContent = PREVIEW_COPY;
    });
  }

  async function stopAppliancePreview(button = previewButton) {
    try {
      await requestJson(endpoints.audioStop, { method: 'POST' });
    } finally {
      resetPreviewButton(button);
    }
  }

  async function runAppliancePreview(button) {
    if (previewButton === button) {
      button.disabled = true;
      await stopAppliancePreview(button).catch(() => resetPreviewButton(button));
      return;
    }

    if (previewButton) {
      await stopAppliancePreview(previewButton).catch(() => resetPreviewButton(previewButton));
    }

    const toneId = toneIdForPreview(button);
    if (!toneId) {
      button.textContent = 'Preview unavailable';
      window.setTimeout(() => resetPreviewButton(button), 1800);
      return;
    }

    button.disabled = true;
    button.textContent = 'Starting…';
    try {
      const payload = await requestJson(endpoints.preview, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tone_id: toneId }),
      });
      previewButton = button;
      button.disabled = false;
      button.textContent = 'Stop preview';
      button.setAttribute('aria-pressed', 'true');
      const seconds = Math.max(3, Math.min(8, Number(payload.preview?.duration_seconds || 8)));
      previewResetTimer = window.setTimeout(() => resetPreviewButton(button), (seconds * 1000) + 700);
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message || 'Preview unavailable';
      window.setTimeout(() => resetPreviewButton(button), 2200);
    }
  }

  document.addEventListener('click', (event) => {
    const button = event.target?.closest?.('.alarm-tone-preview-button');
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    updatePreviewCopy(button.closest('.alarm-preview-row') || document);
    runAppliancePreview(button);
  }, true);

  document.addEventListener('change', (event) => {
    if (!previewButton) return;
    const select = event.target?.closest?.('.alarm-sound-grid select');
    if (!select) return;
    stopAppliancePreview(previewButton).catch(() => resetPreviewButton(previewButton));
  }, true);

  updatePreviewCopy();
  const previewObserver = new MutationObserver(() => updatePreviewCopy());
  previewObserver.observe(document.body, { childList: true, subtree: true });

  document.querySelector('[data-settings-subpage-target="advanced:alarm"]')?.addEventListener('click', () => {
    window.setTimeout(() => refresh(false, true), 0);
  });
  window.addEventListener('acp:clock-format-changed', () => {
    if (pageVisible()) refresh(false, true);
  });
  document.addEventListener('visibilitychange', () => {
    if (pageVisible()) refresh(false, true);
  });

  timer = window.setInterval(() => refresh(false, false), PASSIVE_REFRESH_MS);
  window.addEventListener('pagehide', () => {
    window.clearInterval(timer);
    window.clearTimeout(previewResetTimer);
    previewObserver.disconnect();
  }, { once: true });
})();

(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexResetDefaultsLoaded) return;
  window.__aClockworkPlexResetDefaultsLoaded = true;

  const advanced = document.querySelector('[data-settings-section="advanced"]');
  const overview = advanced?.querySelector('[data-settings-overview="advanced"]');
  if (!advanced || !overview || advanced.querySelector('[data-settings-subpage="advanced:reset"]')) return;

  const PREVIEW_API = '/api/settings/reset/preview';
  const APPLY_API = '/api/settings/reset/apply';
  const RESULT_KEY = 'acp-reset-defaults-result-v1';
  let plan = null;
  let busy = false;

  const row = document.createElement('button');
  row.className = 'settings-subpage-row';
  row.type = 'button';
  row.dataset.settingsSubpageTarget = 'advanced:reset';
  row.innerHTML = '<span><strong>Reset to defaults</strong><small>User settings only; credentials and appliance ownership are preserved</small></span><span>›</span>';
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
          <p class="muted small">Return A Clockwork Plex user-owned settings to the defaults shipped with this version.</p>
        </div>
        <span class="settings-chip">Preview first</span>
      </div>
      <p class="muted small"><strong>This is not a factory wipe.</strong> The reset target is generated by the server from the current application defaults; the browser cannot submit replacement values.</p>
      <div class="settings-restore-target-grid" aria-label="Reset target">
        <div class="settings-restore-target" aria-pressed="true">
          <span class="settings-restore-target-title"><strong>A Clockwork Plex</strong><span class="settings-chip" data-reset-acp-summary>Not previewed</span></span>
          <small>Dashboard, display, Weather, News, alarms, AirPlay preferences, Master EQ and available persistent mixer levels.</small>
        </div>
        <div class="settings-restore-target" aria-pressed="false">
          <span class="settings-restore-target-title"><strong>Plexamp Home customisation</strong><span class="settings-chip">Preserved for now</span></span>
          <small>This will become an optional browser-owned reset target. Login, claim, player identity and Headless preferences remain outside reset.</small>
        </div>
      </div>
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
        <div><h3>Preview</h3><p class="muted small">Nothing has changed yet. Review what would reset and what will be preserved.</p></div>
        <span class="settings-chip" data-reset-change-summary>0 changes</span>
      </div>
      <div class="settings-restore-warning" data-reset-warning-box hidden>
        <strong>Warnings</strong>
        <ul class="muted small" data-reset-warnings></ul>
      </div>
      <div class="settings-restore-detail-grid">
        <div>
          <strong>Settings that would reset</strong>
          <ul class="muted small" data-reset-sections></ul>
        </div>
        <div>
          <strong>Always preserved</strong>
          <ul class="muted small" data-reset-preserved></ul>
        </div>
      </div>
      <details class="settings-restore-details">
        <summary>Technical changed paths</summary>
        <ul class="muted small" data-reset-paths></ul>
      </details>
      <div class="settings-action-row" data-reset-review-zone hidden>
        <button class="button" type="button" data-action="review-reset-defaults">Review reset</button>
        <span class="muted small">Review refreshes the read-only plan immediately before confirmation.</span>
      </div>
      <div class="settings-restore-status" data-reset-review-status hidden aria-live="polite">
        <span class="settings-chip" data-reset-review-pill>Review</span>
        <span data-reset-review-message></span>
      </div>
      <div class="setting-field settings-restore-confirmation" data-reset-confirm hidden>
        <span>Final confirmation</span>
        <strong>Reset A Clockwork Plex settings?</strong>
        <small data-reset-confirm-copy>The existing owners will capture rollback state, apply current application defaults and verify the result. Credentials and Plexamp authentication stay untouched.</small>
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

  function validatePlan(value) {
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
    ) throw new Error('Reset preview returned an invalid safety contract.');
    return value;
  }

  async function fetchPlan() {
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
    return validatePlan(payload);
  }

  function renderPlan(next) {
    plan = next;
    previewPanel.hidden = false;
    confirmZone.hidden = true;
    hideStatus(reviewStatus);
    const count = Number(next.change_count || 0);
    if (acpSummary) acpSummary.textContent = count ? `${count} change${count === 1 ? '' : 's'}` : 'Already at defaults';
    if (changeSummary) changeSummary.textContent = count ? `${count} change${count === 1 ? '' : 's'}` : 'No changes';
    replaceList(
      sectionsList,
      Object.entries(next.sections || {}).map(([name, total]) => `${name} · ${total}`),
      'No user-owned Settings differ from the current defaults.',
    );
    replaceList(preservedList, next.preserved, 'Credential and appliance-owned state remains preserved.');
    replaceList(pathsList, next.changed_paths, 'No technical paths differ.');
    const warnings = Array.isArray(next.warnings) ? next.warnings : [];
    warningsBox.hidden = warnings.length === 0;
    replaceList(warningsList, warnings, 'No warnings.');
    reviewZone.hidden = !next.reset_available;
    if (next.reset_available) {
      setStatus(status, statusPill, statusMessage, 'Preview ready', `${count} user-owned setting${count === 1 ? '' : 's'} would return to the defaults shipped with this version. Nothing has changed yet.`, 'ready');
    } else {
      setStatus(status, statusPill, statusMessage, 'Already at defaults', 'No currently supported user-owned settings need resetting.', 'ready');
    }
  }

  function setBusy(value) {
    busy = value;
    [previewButton, reviewButton, confirmButton, cancelButton].forEach((button) => {
      if (button) button.disabled = value;
    });
  }

  async function previewReset() {
    if (busy) return;
    if (settingsHaveUnsavedChanges()) {
      setStatus(status, statusPill, statusMessage, 'Save or discard first', 'There are staged Settings changes. Save or discard them before previewing a reset.', 'warning');
      return;
    }
    setBusy(true);
    setStatus(status, statusPill, statusMessage, 'Previewing…', 'Reading the current appliance state and application defaults.', 'ready');
    try {
      renderPlan(await fetchPlan());
    } catch (error) {
      plan = null;
      previewPanel.hidden = true;
      setStatus(status, statusPill, statusMessage, 'Preview failed', error.message || 'Could not preview reset.', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function reviewReset() {
    if (busy || !plan?.reset_available) return;
    if (settingsHaveUnsavedChanges()) {
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Save or discard first', 'Staged Settings changes must be resolved before reset.', 'warning');
      return;
    }
    setBusy(true);
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Reviewing…', 'Refreshing the read-only reset plan.', 'ready');
    try {
      const fresh = await fetchPlan();
      renderPlan(fresh);
      if (!fresh.reset_available) {
        setStatus(reviewStatus, reviewPill, reviewMessage, 'Nothing to reset', 'The appliance now matches the current defaults.', 'ready');
        return;
      }
      replaceList(
        confirmSummary,
        [
          `${fresh.change_count} user-owned change${fresh.change_count === 1 ? '' : 's'} will be reset.`,
          ...(fresh.confirmations_required || []).includes('airplay_restart')
            ? ['The AirPlay receiver name will return to its default and Shairport Sync will briefly restart.']
            : [],
          'Plex/Plexamp authentication, claim/session data, player identity and hardware topology will be preserved.',
          'Plexamp Home customisation is not part of this reset target yet.',
        ],
        'No changes are selected.',
      );
      confirmZone.hidden = false;
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Ready to confirm', 'The fresh reset plan is still current. Confirm below to apply it.', 'ready');
    } catch (error) {
      confirmZone.hidden = true;
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Review failed', error.message || 'Could not refresh reset plan.', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function confirmReset() {
    if (busy || !plan?.reset_available) return;
    if (settingsHaveUnsavedChanges()) {
      confirmZone.hidden = true;
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Reset blocked', 'Settings changed after Review. Save or discard them and preview again.', 'warning');
      return;
    }
    setBusy(true);
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Resetting…', 'Applying application defaults through the existing rollback-protected owners.', 'ready');
    try {
      const response = await fetch(APPLY_API, {
        method: 'POST',
        cache: 'no-store',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reset_token: plan.reset_token,
          confirm_reset: true,
          confirmations: Array.isArray(plan.confirmations_required) ? plan.confirmations_required : [],
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Reset returned HTTP ${response.status}.`);
      }
      window.sessionStorage?.setItem?.(RESULT_KEY, JSON.stringify({
        message: payload.message || 'Reset complete.',
        count: Number(payload.applied_change_count || 0),
      }));
      window.location.hash = 'advanced/reset';
      window.location.reload();
    } catch (error) {
      confirmZone.hidden = true;
      setStatus(reviewStatus, reviewPill, reviewMessage, 'Reset failed', error.message || 'No reset was completed.', 'error');
    } finally {
      setBusy(false);
    }
  }

  previewButton?.addEventListener('click', previewReset);
  reviewButton?.addEventListener('click', reviewReset);
  confirmButton?.addEventListener('click', confirmReset);
  cancelButton?.addEventListener('click', () => {
    confirmZone.hidden = true;
    setStatus(reviewStatus, reviewPill, reviewMessage, 'Cancelled', 'Nothing was changed. Preview again whenever you are ready.', 'ready');
  });

  if (location.hash === '#advanced/reset') showPage();

  try {
    const saved = JSON.parse(window.sessionStorage?.getItem?.(RESULT_KEY) || 'null');
    if (saved && typeof saved === 'object') {
      window.sessionStorage?.removeItem?.(RESULT_KEY);
      showPage();
      setStatus(status, statusPill, statusMessage, 'Reset complete', `${saved.message} ${Number(saved.count || 0)} change${Number(saved.count || 0) === 1 ? '' : 's'} applied.`, 'ready');
    }
  } catch (_error) {
    window.sessionStorage?.removeItem?.(RESULT_KEY);
  }
})();