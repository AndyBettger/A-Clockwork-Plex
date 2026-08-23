(() => {
  if (window.__aClockworkPlexScheduledAlarmSettingsLoaded) return;
  window.__aClockworkPlexScheduledAlarmSettingsLoaded = true;

  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const STATUS_ENDPOINT = '/api/alarms/audio';
  const SETTINGS_ENDPOINT = '/api/alarms/audio/settings';
  const POLL_MS = 3000;

  const byId = (id) => document.getElementById(id);
  let refreshTimer = null;
  let requestInFlight = false;

  function install() {
    const card = byId('alarm-audio-card');
    const grid = card?.querySelector('.alarm-audio-grid');
    const master = byId('alarm-audio-master-enabled');
    if (!card || !grid || !master) return false;
    if (byId('alarm-audio-scheduled-enabled')) return true;

    const control = document.createElement('label');
    control.className = 'setting-toggle alarm-audio-scheduled-toggle';
    control.innerHTML = `
      <input id="alarm-audio-scheduled-enabled" type="checkbox">
      <span>
        <strong>Enable scheduled alarm sound</strong>
        <small>Second safety key. Normal enabled alarms may make sound only when this and the master switch are both saved.</small>
      </span>
    `;

    const saveRow = document.createElement('div');
    saveRow.className = 'alarm-audio-save-row alarm-audio-scheduled-save-row';
    saveRow.innerHTML = `
      <button class="button settings-secondary" id="alarm-audio-scheduled-save" type="button">Save scheduled playback</button>
      <span class="muted small" id="alarm-audio-scheduled-message">Scheduled alarms remain silent.</span>
    `;

    const masterControl = master.closest('.setting-toggle');
    masterControl?.insertAdjacentElement('afterend', control);
    card.querySelector('.alarm-audio-save-row')?.insertAdjacentElement('afterend', saveRow);

    master.addEventListener('change', updateAvailability);
    byId('alarm-audio-scheduled-save')?.addEventListener('click', saveScheduledSetting);
    return true;
  }

  function updateAvailability() {
    const master = byId('alarm-audio-master-enabled');
    const scheduled = byId('alarm-audio-scheduled-enabled');
    const button = byId('alarm-audio-scheduled-save');
    if (!master || !scheduled || !button) return;

    scheduled.disabled = !master.checked || requestInFlight;
    button.disabled = requestInFlight;
    if (!master.checked) scheduled.checked = false;
  }

  function render(payload) {
    const settings = payload?.settings || {};
    const scheduled = byId('alarm-audio-scheduled-enabled');
    const message = byId('alarm-audio-scheduled-message');
    const banner = document.querySelector('#alarm-audio-card .alarm-audio-safety-banner');
    const enabled = Boolean(settings.master_enabled && settings.scheduled_enabled);

    if (scheduled && !requestInFlight) scheduled.checked = enabled;
    updateAvailability();

    if (message && !requestInFlight) {
      message.textContent = enabled
        ? 'Scheduled alarm sound is enabled through acp_alarm.'
        : 'Scheduled alarms remain silent.';
    }

    if (banner) {
      const strong = banner.querySelector('strong');
      const detail = banner.querySelector('span');
      if (strong) strong.textContent = enabled
        ? 'Scheduled alarm sound is enabled.'
        : 'Scheduled alarms are silent.';
      if (detail) detail.textContent = enabled
        ? 'Snooze, Dismiss, leaving the ringing phase, or disabling either safety switch stops playback.'
        : 'Enable both safety switches to let normal scheduled occurrences use the shared alarm mixer.';
      banner.classList.toggle('is-enabled', enabled);
    }
  }

  async function fetchJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Alarm audio request returned ${response.status}.`);
    }
    return payload;
  }

  async function refresh() {
    if (requestInFlight || !install()) return;
    try {
      render(await fetchJson(STATUS_ENDPOINT));
    } catch (error) {
      const message = byId('alarm-audio-scheduled-message');
      if (message) message.textContent = error.message || 'Could not read scheduled audio state.';
    }
  }

  async function saveScheduledSetting() {
    if (requestInFlight) return;
    const scheduled = byId('alarm-audio-scheduled-enabled');
    const message = byId('alarm-audio-scheduled-message');
    requestInFlight = true;
    updateAvailability();
    if (message) message.textContent = 'Saving scheduled playback safety state…';

    try {
      const payload = await fetchJson(SETTINGS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_enabled: Boolean(scheduled?.checked) }),
      });
      render(payload);
      if (message) message.textContent = payload.message || 'Scheduled playback setting saved.';
    } catch (error) {
      if (message) message.textContent = error.message || 'Could not save scheduled playback.';
    } finally {
      requestInFlight = false;
      updateAvailability();
      window.setTimeout(refresh, 250);
    }
  }

  function start() {
    if (!install()) {
      window.setTimeout(start, 100);
      return;
    }
    refresh();
    refreshTimer = window.setInterval(refresh, POLL_MS);
  }

  window.addEventListener('pagehide', () => {
    if (refreshTimer) window.clearInterval(refreshTimer);
  });

  start();
})();
