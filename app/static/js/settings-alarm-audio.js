(() => {
  if (window.__aClockworkPlexAlarmAudioSettingsLoaded) {
    return;
  }
  window.__aClockworkPlexAlarmAudioSettingsLoaded = true;

  const PANEL_ID = 'settings-panel-alarms';
  const STATUS_ENDPOINT = '/api/alarms/audio';
  const SETTINGS_ENDPOINT = '/api/alarms/audio/settings';
  const TEST_ENDPOINT = '/api/alarms/audio/test';
  const STOP_ENDPOINT = '/api/alarms/audio/stop';
  const REFRESH_MS = 3000;

  const byId = (id) => document.getElementById(id);
  const settingsForm = document.querySelector('.settings-form');
  let refreshTimer = null;
  let requestInFlight = false;
  let lastPayload = null;
  let skipNextFormSave = false;

  function installStyles() {
    if (document.querySelector('link[data-alarm-audio-styles]')) {
      return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/settings-alarm-audio.css';
    link.dataset.alarmAudioStyles = 'true';
    document.head.appendChild(link);
  }

  function installCard() {
    const panel = byId(PANEL_ID);
    const lockout = panel?.querySelector('.alarm-scheduler-lockout');
    if (!panel || !lockout) {
      return false;
    }
    if (byId('alarm-audio-card')) {
      return true;
    }

    installStyles();
    const card = document.createElement('section');
    card.id = 'alarm-audio-card';
    card.className = 'settings-card alarm-audio-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>Controlled alarm audio</h2>
          <p class="muted small">Real DAC playback, available only through deliberate test controls in this pass.</p>
        </div>
        <span class="settings-chip is-warning" id="alarm-audio-health">Loading…</span>
      </div>

      <div class="alarm-audio-safety-banner">
        <strong>Scheduled alarms are still silent.</strong>
        <span>The master switch permits tests only. Normal alarm occurrences cannot yet start audio.</span>
      </div>

      <div class="alarm-audio-grid">
        <label class="setting-toggle alarm-audio-master">
          <input id="alarm-audio-master-enabled" name="alarm_audio_master_enabled" type="checkbox">
          <span>
            <strong>Enable alarm audio tests</strong>
            <small>Explicit safety gate. Save before any test can make sound.</small>
          </span>
        </label>

        <label class="setting-toggle">
          <input id="alarm-audio-release-services" name="alarm_audio_release_services" type="checkbox">
          <span>
            <strong>Release Plexamp and AirPlay</strong>
            <small>Uses the restricted root helper before playback.</small>
          </span>
        </label>

        <label class="setting-toggle">
          <input id="alarm-audio-restore-services" name="alarm_audio_restore_services" type="checkbox">
          <span>
            <strong>Restore services afterwards</strong>
            <small>Plexamp returns paused; Shairport Sync becomes available again.</small>
          </span>
        </label>

        <label class="setting-field">
          <span>ALSA output device</span>
          <input
            id="alarm-audio-device"
            name="alarm_audio_device"
            value="default"
            autocomplete="off"
            inputmode="none"
            data-keyboard="text"
          >
          <small>Bedroom DAC example: <code>plughw:CARD=Pro,DEV=0</code>. The generated alarm is 44.1 kHz stereo.</small>
        </label>

        <label class="setting-field">
          <span>Test duration</span>
          <select id="alarm-audio-test-duration" name="alarm_audio_test_duration_seconds">
            <option value="5">5 seconds</option>
            <option value="10">10 seconds</option>
            <option value="12">12 seconds</option>
            <option value="15">15 seconds</option>
            <option value="20">20 seconds</option>
            <option value="30">30 seconds</option>
          </select>
          <small>Every test stops automatically, even if nobody intervenes heroically.</small>
        </label>
      </div>

      <div class="alarm-audio-save-row">
        <button class="button settings-secondary" id="alarm-audio-save" type="button">Save audio safety settings</button>
        <span class="muted small" id="alarm-audio-save-message">The main Save settings button now saves these values too.</span>
      </div>

      <div class="alarm-audio-test-panel">
        <label class="setting-field">
          <span>Alarm used for the test</span>
          <select id="alarm-audio-alarm-select"></select>
          <small>Uses that alarm’s tone, fallback, start volume, target volume and fade.</small>
        </label>
        <div class="alarm-audio-test-actions">
          <button class="button alarm-audio-test-button" id="alarm-audio-test-now" type="button">Test tone now</button>
          <button class="button settings-secondary" id="alarm-audio-test-screen" type="button">Test full alarm in 10 sec</button>
          <button class="button alarm-audio-stop-button" id="alarm-audio-stop" type="button">Stop alarm audio</button>
        </div>
      </div>

      <div class="alarm-audio-readings">
        <div class="alarm-audio-reading">
          <span>Player</span>
          <strong id="alarm-audio-player">Checking…</strong>
          <small id="alarm-audio-player-detail">Looking for aplay.</small>
        </div>
        <div class="alarm-audio-reading">
          <span>Ownership helper</span>
          <strong id="alarm-audio-helper">Checking…</strong>
          <small id="alarm-audio-helper-detail">Looking for the restricted helper.</small>
        </div>
        <div class="alarm-audio-reading">
          <span>Current playback</span>
          <strong id="alarm-audio-current">Idle</strong>
          <small id="alarm-audio-current-detail">No tone is playing.</small>
        </div>
        <div class="alarm-audio-reading">
          <span>Last action</span>
          <strong id="alarm-audio-last-action">Not yet</strong>
          <small id="alarm-audio-last-error">No playback errors recorded.</small>
        </div>
      </div>
    `;
    panel.insertBefore(card, lockout);

    byId('alarm-audio-save')?.addEventListener('click', saveSettings);
    byId('alarm-audio-test-now')?.addEventListener('click', () => runTest(false));
    byId('alarm-audio-test-screen')?.addEventListener('click', () => runTest(true));
    byId('alarm-audio-stop')?.addEventListener('click', stopAudio);
    return true;
  }

  function formSettings() {
    return {
      master_enabled: Boolean(byId('alarm-audio-master-enabled')?.checked),
      release_services: Boolean(byId('alarm-audio-release-services')?.checked),
      restore_services: Boolean(byId('alarm-audio-restore-services')?.checked),
      backend: 'aplay',
      alsa_device: byId('alarm-audio-device')?.value?.trim() || 'default',
      test_duration_seconds: Number(byId('alarm-audio-test-duration')?.value) || 12,
    };
  }

  function setControls(settings) {
    if (!settings) {
      return;
    }
    byId('alarm-audio-master-enabled').checked = Boolean(settings.master_enabled);
    byId('alarm-audio-release-services').checked = settings.release_services !== false;
    byId('alarm-audio-restore-services').checked = settings.restore_services !== false;
    byId('alarm-audio-device').value = settings.alsa_device || 'default';
    byId('alarm-audio-test-duration').value = String(settings.test_duration_seconds || 12);
  }

  function setAlarmOptions(options, selectedValue = '') {
    const select = byId('alarm-audio-alarm-select');
    if (!select || !Array.isArray(options)) {
      return;
    }
    const previous = selectedValue || select.value;
    select.replaceChildren();
    options.forEach((alarm) => {
      const option = document.createElement('option');
      option.value = alarm.id || '';
      option.textContent = `${alarm.label || 'Alarm'} · ${alarm.tone_label || 'Local tone'}`;
      select.appendChild(option);
    });
    if (!options.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Built-in Classic Klaxon test';
      select.appendChild(option);
    } else if (options.some((alarm) => alarm.id === previous)) {
      select.value = previous;
    }
  }

  function render(payload, { preserveControls = false } = {}) {
    lastPayload = payload;
    const settings = payload?.settings || {};
    const runtime = payload?.runtime || {};
    const helper = payload?.helper || {};
    const player = payload?.player || {};

    if (!preserveControls) {
      setControls(settings);
      setAlarmOptions(payload?.alarm_options || []);
    }

    const health = byId('alarm-audio-health');
    if (health) {
      if (!settings.master_enabled) {
        health.textContent = 'Audio locked';
        health.classList.add('is-warning');
      } else if (!player.available) {
        health.textContent = 'Player missing';
        health.classList.add('is-warning');
      } else if (runtime.playback_active) {
        health.textContent = 'Playing test';
        health.classList.remove('is-warning');
      } else {
        health.textContent = 'Tests enabled';
        health.classList.remove('is-warning');
      }
    }

    byId('alarm-audio-player').textContent = player.available ? 'aplay ready' : 'Unavailable';
    const format = player.format;
    const formatText = format
      ? ` · ${format.sample_rate_hz / 1000} kHz ${format.channel_layout || `${format.channels} ch`}`
      : '';
    byId('alarm-audio-player-detail').textContent = player.error || `Device: ${settings.alsa_device || 'default'}${formatText}`;
    byId('alarm-audio-helper').textContent = helper.available ? 'Installed' : 'Not installed';
    byId('alarm-audio-helper-detail').textContent = helper.error || `Plexamp ${helper.plexamp_active ? 'active' : 'idle'} · AirPlay ${helper.shairport_active ? 'active' : 'idle'}`;

    byId('alarm-audio-current').textContent = runtime.playback_active
      ? (runtime.current_tone_label || runtime.current_tone_id || 'Alarm tone')
      : 'Idle';
    const fallback = runtime.fallback_used ? ' · emergency fallback in use' : '';
    byId('alarm-audio-current-detail').textContent = runtime.playback_active
      ? `Output ${runtime.alsa_device || settings.alsa_device || 'default'}${fallback}`
      : 'No tone is playing.';

    const action = runtime.last_action;
    byId('alarm-audio-last-action').textContent = action?.action
      ? action.action.replaceAll('-', ' ')
      : 'Not yet';
    byId('alarm-audio-last-error').textContent = runtime.last_error || 'No playback errors recorded.';

    const enabled = Boolean(settings.master_enabled && player.available && !requestInFlight);
    byId('alarm-audio-test-now').disabled = !enabled;
    byId('alarm-audio-test-screen').disabled = !enabled;
    byId('alarm-audio-stop').disabled = !runtime.playback_active || requestInFlight;
  }

  function setBusy(busy, message = '') {
    requestInFlight = busy;
    ['alarm-audio-save', 'alarm-audio-test-now', 'alarm-audio-test-screen', 'alarm-audio-stop'].forEach((id) => {
      const button = byId(id);
      if (button) {
        button.disabled = busy;
      }
    });
    if (message) {
      byId('alarm-audio-save-message').textContent = message;
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

  async function persistSettings() {
    const payload = await fetchJson(SETTINGS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formSettings()),
    });
    render(payload);
    return payload;
  }

  async function saveSettings() {
    if (requestInFlight) {
      return;
    }
    setBusy(true, 'Saving the audio safety gate and DAC device…');
    try {
      const payload = await persistSettings();
      byId('alarm-audio-save-message').textContent = payload.message || 'Audio safety settings saved.';
    } catch (error) {
      byId('alarm-audio-save-message').textContent = error.message || 'Could not save audio settings.';
    } finally {
      requestInFlight = false;
      if (lastPayload) {
        render(lastPayload, { preserveControls: true });
      }
    }
  }

  async function runTest(fullScreen) {
    if (requestInFlight) {
      return;
    }
    setBusy(true, fullScreen ? 'Arming the full alarm audio test…' : 'Starting the tone test…');
    try {
      const payload = await fetchJson(TEST_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alarm_id: byId('alarm-audio-alarm-select')?.value || null,
          full_screen: fullScreen,
          delay_seconds: fullScreen ? 10 : 0,
        }),
      });
      render(payload);
      byId('alarm-audio-save-message').textContent = payload.message || 'Alarm audio test started.';
    } catch (error) {
      byId('alarm-audio-save-message').textContent = error.message || 'Could not start the audio test.';
    } finally {
      requestInFlight = false;
      window.setTimeout(refreshStatus, 250);
    }
  }

  async function stopAudio() {
    if (requestInFlight) {
      return;
    }
    setBusy(true, 'Stopping alarm audio and restoring services…');
    try {
      const payload = await fetchJson(STOP_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      render(payload);
      byId('alarm-audio-save-message').textContent = payload.message || 'Alarm audio stopped.';
    } catch (error) {
      byId('alarm-audio-save-message').textContent = error.message || 'Could not stop alarm audio.';
    } finally {
      requestInFlight = false;
      window.setTimeout(refreshStatus, 250);
    }
  }

  async function refreshStatus() {
    if (requestInFlight || !installCard()) {
      return;
    }
    try {
      const payload = await fetchJson(STATUS_ENDPOINT);
      render(payload, { preserveControls: Boolean(lastPayload) });
    } catch (error) {
      const health = byId('alarm-audio-health');
      if (health) {
        health.textContent = 'Unavailable';
        health.classList.add('is-warning');
      }
      byId('alarm-audio-last-error').textContent = error.message || 'Could not read alarm audio status.';
    }
  }

  settingsForm?.addEventListener('submit', async (event) => {
    if (skipNextFormSave) {
      skipNextFormSave = false;
      return;
    }
    if (!byId('alarm-audio-card')) {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    if (requestInFlight) {
      byId('alarm-audio-save-message').textContent = 'Please wait for the current audio action to finish.';
      return;
    }

    const submitter = event.submitter;
    setBusy(true, 'Saving audio settings before the rest of Settings…');
    try {
      await persistSettings();
      byId('alarm-audio-save-message').textContent = 'Audio settings saved; continuing with the main Settings save…';
      skipNextFormSave = true;
      if (submitter instanceof HTMLElement && settingsForm.contains(submitter)) {
        settingsForm.requestSubmit(submitter);
      } else {
        settingsForm.requestSubmit();
      }
    } catch (error) {
      byId('alarm-audio-save-message').textContent = error.message || 'Could not save audio settings.';
    } finally {
      requestInFlight = false;
      if (lastPayload) {
        render(lastPayload, { preserveControls: true });
      }
    }
  }, true);

  function start() {
    if (!installCard()) {
      window.setTimeout(start, 100);
      return;
    }
    refreshStatus();
    refreshTimer = window.setInterval(refreshStatus, REFRESH_MS);
  }

  window.addEventListener('pagehide', () => {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
  });

  start();
})();