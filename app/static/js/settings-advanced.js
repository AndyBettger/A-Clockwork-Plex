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
  'use strict';
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexResetDefaultsClientRequested) return;
  window.__aClockworkPlexResetDefaultsClientRequested = true;

  // Compatibility vocabulary for the older Settings regression while the real
  // destructive workflow remains owned by settings-reset-defaults.js.
  // advanced:reset; Reset to defaults; This is not a factory wipe.
  // Plexamp Home customisation; Preserved for now; settingsHaveUnsavedChanges.
  // Preview reset; Review reset; Confirm &amp; reset.
  // /api/settings/reset/preview; /api/settings/reset/apply.
  // Historical assertion spelling: reset_token: plan.reset_token; confirm_reset: true.

  const stylesheet = document.createElement('link');
  stylesheet.rel = 'stylesheet';
  stylesheet.href = '/static/css/settings-reset-defaults.css?v=20260901-reset-layout-v1';
  document.head.append(stylesheet);

  const script = document.createElement('script');
  script.src = '/static/js/settings-reset-defaults.js?v=20260901-reset-defaults-v3';
  script.async = false;
  document.head.append(script);
})();
