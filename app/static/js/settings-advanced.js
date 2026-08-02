(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const mount = document.getElementById('settings-advanced-alarm-diagnostics');
  if (!mount) return;

  const endpoints = {
    status: '/api/alarms/scheduler',
    test: '/api/alarms/test',
    cancel: '/api/alarms/test/cancel',
  };
  let requestInFlight = false;
  let timer = null;

  function formatTime(value, fallback = 'Not yet') {
    if (!value) return fallback;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return fallback;
    return parsed.toLocaleString('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
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
      active.test_mode ? 'Visual test' : 'Scheduled occurrence',
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
        <button class="button" type="button" data-alarm-runtime-action="test">Test screen in 10 seconds</button>
        <button class="button settings-secondary" type="button" data-alarm-runtime-action="cancel">Clear visual test</button>
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
      reading('Last checked', formatTime(scheduler.last_check_at), `Poll ${scheduler.poll_seconds || 15}s`),
      reading('Queued', `${scheduler.queued_occurrence_count || 0} alarm${Number(scheduler.queued_occurrence_count || 0) === 1 ? '' : 's'}`, `${scheduler.duplicate_protection_count || 0} protected occurrence keys`),
      reading('Scheduled sound', audio.scheduled_playback_enabled ? 'Enabled' : 'Safety locked', audio.playback_lockout_reason || 'Two-key sound safety'),
      reading('Last occurrence', scheduler.last_observed_occurrence?.label || 'None recorded', scheduler.last_observed_occurrence ? formatTime(scheduler.last_observed_occurrence.scheduled_for) : 'No scheduler occurrence observed yet'),
    );
    mount.replaceChildren(card);
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

  async function refresh(recalculate = false) {
    if (requestInFlight) return;
    setBusy(true, recalculate ? 'Recalculating…' : 'Refreshing…');
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

  async function runAction(action) {
    if (action === 'recalculate') return refresh(true);
    if (requestInFlight) return;
    const endpoint = action === 'cancel' ? endpoints.cancel : endpoints.test;
    const label = action === 'cancel' ? 'Clearing visual test…' : 'Arming visual test…';
    setBusy(true, label);
    try {
      const payload = await requestJson(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'test' ? { delay_seconds: 10 } : {}),
      });
      render({ scheduler: payload.scheduler, audio: payload.audio });
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = payload.message || 'Alarm runtime action completed.';
    } catch (error) {
      const output = mount.querySelector('[data-alarm-runtime-message]');
      if (output) output.textContent = error.message || 'Alarm runtime action failed.';
    } finally {
      setBusy(false);
    }
  }

  refresh(false);
  timer = window.setInterval(() => refresh(false), 5000);
  window.addEventListener('pagehide', () => window.clearInterval(timer));
})();