(() => {
  if (window.__aClockworkPlexAlarmAudioSettingsLoaded) {
    return;
  }
  window.__aClockworkPlexAlarmAudioSettingsLoaded = true;

  const ALARM_PANEL_ID = 'settings-panel-alarms';
  const GENERAL_PANEL_ID = 'settings-panel-general';
  const STATUS_ENDPOINT = '/api/alarms/audio';
  const SETTINGS_ENDPOINT = '/api/alarms/audio/settings';
  const TEST_ENDPOINT = '/api/alarms/audio/test';
  const STOP_ENDPOINT = '/api/alarms/audio/stop';
  const MIXER_ENDPOINT = '/api/audio/mixer';
  const REFRESH_MS = 3000;
  const MIXER_ORDER = ['master', 'plexamp', 'airplay', 'alarm'];

  const byId = (id) => document.getElementById(id);
  const settingsForm = document.querySelector('.settings-form');
  let refreshTimer = null;
  let requestInFlight = false;
  let mixerRequestInFlight = false;
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

  function mixerChannelMarkup(channel) {
    const id = channel.id;
    return `
      <article class="audio-mixer-channel" data-mixer-channel="${id}">
        <div class="audio-mixer-channel-heading">
          <div>
            <strong>${channel.label}</strong>
            <small>${channel.description}</small>
          </div>
          <output id="audio-mixer-${id}-value" for="audio-mixer-${id}">--%</output>
        </div>
        <div class="audio-mixer-control-row">
          <button class="audio-mixer-step" type="button" data-mixer-step="-5" data-mixer-target="${id}" aria-label="Reduce ${channel.label} by five percent">−</button>
          <input id="audio-mixer-${id}" type="range" min="0" max="100" step="1" value="0" data-mixer-slider="${id}" aria-label="${channel.label} volume">
          <button class="audio-mixer-step" type="button" data-mixer-step="5" data-mixer-target="${id}" aria-label="Increase ${channel.label} by five percent">＋</button>
        </div>
        <small class="audio-mixer-pcm" id="audio-mixer-${id}-detail">PCM ${channel.pcm}</small>
      </article>
    `;
  }

  function installMixerCard() {
    const panel = byId(GENERAL_PANEL_ID);
    if (!panel) {
      return false;
    }
    if (byId('audio-mixer-card')) {
      return true;
    }

    const channels = [
      { id: 'master', label: 'Master output', pcm: 'acp_master', description: 'Final level for every source.' },
      { id: 'plexamp', label: 'Plexamp', pcm: 'acp_plexamp', description: 'After Plexamp’s own player volume.' },
      { id: 'airplay', label: 'AirPlay', pcm: 'acp_airplay', description: 'Shared with the sender’s volume.' },
      { id: 'alarm', label: 'Alarm', pcm: 'acp_alarm', description: 'After each alarm’s fade and target.' },
    ];

    const card = document.createElement('section');
    card.id = 'audio-mixer-card';
    card.className = 'settings-card audio-mixer-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>Shared audio mixer</h2>
          <p class="muted small">Plexamp, AirPlay and alarms remain alive and feed the same ALSA dmix output.</p>
        </div>
        <span class="settings-chip is-warning" id="audio-mixer-health">Checking…</span>
      </div>
      <div class="audio-mixer-banner">
        <strong>No more DAC handoff.</strong>
        <span>Each source has its own software level, followed by one master output.</span>
      </div>
      <div class="audio-mixer-grid">
        ${channels.map(mixerChannelMarkup).join('')}
      </div>
      <div class="audio-mixer-footer">
        <span class="muted small" id="audio-mixer-message">Waiting for shared mixer diagnostics.</span>
        <button class="button settings-secondary" id="audio-mixer-refresh" type="button">Refresh mixer</button>
      </div>
    `;

    const intro = panel.querySelector('.settings-card.is-intro');
    intro?.insertAdjacentElement('afterend', card);
    if (!intro) {
      panel.prepend(card);
    }

    card.querySelectorAll('[data-mixer-slider]').forEach((slider) => {
      slider.addEventListener('input', () => updateSliderReading(slider.dataset.mixerSlider, slider.value));
      slider.addEventListener('change', () => setMixerVolume(slider.dataset.mixerSlider, slider.value));
    });
    card.querySelectorAll('[data-mixer-step]').forEach((button) => {
      button.addEventListener('click', () => {
        const channel = button.dataset.mixerTarget;
        const slider = byId(`audio-mixer-${channel}`);
        if (!slider) {
          return;
        }
        const next = Math.max(0, Math.min(100, Number(slider.value) + Number(button.dataset.mixerStep || 0)));
        slider.value = String(next);
        updateSliderReading(channel, next);
        setMixerVolume(channel, next);
      });
    });
    byId('audio-mixer-refresh')?.addEventListener('click', refreshStatus);
    return true;
  }

  function installAlarmCard() {
    const panel = byId(ALARM_PANEL_ID);
    const lockout = panel?.querySelector('.alarm-scheduler-lockout');
    if (!panel || !lockout) {
      return false;
    }
    if (byId('alarm-audio-card')) {
      return true;
    }

    const card = document.createElement('section');
    card.id = 'alarm-audio-card';
    card.className = 'settings-card alarm-audio-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>Controlled alarm audio</h2>
          <p class="muted small">Real DAC playback through the shared mixer, available only through deliberate test controls in this pass.</p>
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

        <label class="setting-toggle alarm-audio-shared-toggle">
          <input id="alarm-audio-shared-mixer" name="alarm_audio_shared_mixer_enabled" type="checkbox">
          <span>
            <strong>Use shared ALSA mixer</strong>
            <small>Keeps Plexamp and Shairport Sync alive while the alarm plays.</small>
          </span>
        </label>

        <label class="setting-field">
          <span>Physical DAC</span>
          <input id="alarm-audio-hardware-device" name="alarm_audio_hardware_device" value="hw:CARD=Pro,DEV=0" autocomplete="off" inputmode="none" data-keyboard="text">
          <small>Installer target. Rerun <code>install-shared-audio.sh</code> after changing hardware.</small>
        </label>

        <label class="setting-field">
          <span>Alarm mixer PCM</span>
          <input id="alarm-audio-device" name="alarm_audio_device" value="acp_alarm" readonly>
          <small>44.1 kHz, 16-bit dual-mono stereo through the Alarm mixer channel.</small>
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
        <span class="muted small" id="alarm-audio-save-message">The main Save settings button saves these values too.</span>
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
          <span>Shared mixer</span>
          <strong id="alarm-audio-helper">Checking…</strong>
          <small id="alarm-audio-helper-detail">Looking for dmix and soft-volume controls.</small>
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

  function installCards() {
    installStyles();
    return installMixerCard() && installAlarmCard();
  }

  function formSettings() {
    const shared = Boolean(byId('alarm-audio-shared-mixer')?.checked);
    return {
      master_enabled: Boolean(byId('alarm-audio-master-enabled')?.checked),
      shared_mixer_enabled: shared,
      hardware_device: byId('alarm-audio-hardware-device')?.value?.trim() || 'hw:CARD=Pro,DEV=0',
      release_services: false,
      restore_services: false,
      backend: 'aplay',
      alsa_device: shared ? 'acp_alarm' : (byId('alarm-audio-device')?.value?.trim() || 'default'),
      mixer_helper_path: '/usr/local/bin/a-clockwork-plex-audio-mixer',
      test_duration_seconds: Number(byId('alarm-audio-test-duration')?.value) || 12,
    };
  }

  function setControls(settings) {
    if (!settings) {
      return;
    }
    byId('alarm-audio-master-enabled').checked = Boolean(settings.master_enabled);
    byId('alarm-audio-shared-mixer').checked = Boolean(settings.shared_mixer_enabled);
    byId('alarm-audio-hardware-device').value = settings.hardware_device || 'hw:CARD=Pro,DEV=0';
    byId('alarm-audio-device').value = settings.alsa_device || (settings.shared_mixer_enabled ? 'acp_alarm' : 'default');
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

  function updateSliderReading(channel, percent) {
    const output = byId(`audio-mixer-${channel}-value`);
    if (output) {
      output.textContent = `${Math.round(Number(percent) || 0)}%`;
    }
  }

  function renderMixer(mixer) {
    const health = byId('audio-mixer-health');
    const ready = Boolean(mixer?.available && mixer?.configured);
    if (health) {
      health.textContent = ready ? 'Shared and ready' : (mixer?.installed ? 'Needs attention' : 'Not installed');
      health.classList.toggle('is-warning', !ready);
    }

    MIXER_ORDER.forEach((channelId) => {
      const channel = mixer?.channels?.[channelId] || {};
      const slider = byId(`audio-mixer-${channelId}`);
      const buttons = document.querySelectorAll(`[data-mixer-target="${channelId}"]`);
      const available = Boolean(channel.available && channel.pcm_available);
      if (slider) {
        if (Number.isFinite(Number(channel.percent))) {
          slider.value = String(channel.percent);
          updateSliderReading(channelId, channel.percent);
        }
        slider.disabled = !available || mixerRequestInFlight;
      }
      buttons.forEach((button) => {
        button.disabled = !available || mixerRequestInFlight;
      });
      const detail = byId(`audio-mixer-${channelId}-detail`);
      if (detail) {
        detail.textContent = channel.error || `${channel.pcm || `acp_${channelId}`} · ${available ? 'ready' : 'unavailable'}`;
      }
    });

    const message = byId('audio-mixer-message');
    if (message && !mixerRequestInFlight) {
      message.textContent = mixer?.error
        || (ready
          ? `${mixer.hardware_pcm || 'Physical DAC'} · ${mixer.sample_rate_hz || 44100} Hz · ${mixer.channels_count || 2} channels`
          : 'Run sudo bash scripts/install-shared-audio.sh on the Pi.');
    }
  }

  function render(payload, { preserveControls = false } = {}) {
    lastPayload = payload;
    const settings = payload?.settings || {};
    const runtime = payload?.runtime || {};
    const helper = payload?.helper || {};
    const player = payload?.player || {};
    const mixer = payload?.mixer || {};

    if (!preserveControls) {
      setControls(settings);
      setAlarmOptions(payload?.alarm_options || []);
    }
    renderMixer(mixer);

    const health = byId('alarm-audio-health');
    const audioPathReady = settings.shared_mixer_enabled ? mixer.available : helper.available;
    if (health) {
      if (!settings.master_enabled) {
        health.textContent = 'Audio locked';
        health.classList.add('is-warning');
      } else if (!player.available || !audioPathReady) {
        health.textContent = 'Audio path unavailable';
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
    byId('alarm-audio-helper').textContent = settings.shared_mixer_enabled
      ? (mixer.available ? 'dmix ready' : 'Unavailable')
      : (helper.available ? 'Legacy helper installed' : 'Not installed');
    byId('alarm-audio-helper-detail').textContent = settings.shared_mixer_enabled
      ? (mixer.error || 'Plexamp and AirPlay services remain running during alarm playback.')
      : (helper.error || 'Legacy exclusive-DAC mode stops and restores services.');

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

    const enabled = Boolean(settings.master_enabled && player.available && audioPathReady && !requestInFlight);
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
      throw new Error(payload.error || `Audio request returned ${response.status}.`);
    }
    return payload;
  }

  async function setMixerVolume(channel, percent) {
    if (mixerRequestInFlight) {
      return;
    }
    mixerRequestInFlight = true;
    const message = byId('audio-mixer-message');
    if (message) {
      message.textContent = `Setting ${channel} to ${percent}%…`;
    }
    try {
      const payload = await fetchJson(MIXER_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, percent: Number(percent) }),
      });
      renderMixer(payload.mixer || {});
      if (message) {
        message.textContent = payload.message || 'Mixer updated.';
      }
    } catch (error) {
      if (message) {
        message.textContent = error.message || 'Could not change mixer volume.';
      }
    } finally {
      mixerRequestInFlight = false;
      window.setTimeout(refreshStatus, 250);
    }
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
    setBusy(true, 'Saving the audio safety gate and shared mixer mode…');
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
    setBusy(true, 'Stopping alarm audio…');
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
    if (requestInFlight || !installCards()) {
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
    if (!installCards()) {
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
