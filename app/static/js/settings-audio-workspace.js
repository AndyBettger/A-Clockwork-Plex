(() => {
  if (window.__aClockworkPlexAudioWorkspaceLoaded) {
    return;
  }
  window.__aClockworkPlexAudioWorkspaceLoaded = true;

  const PANEL_ID = 'settings-panel-audio';
  const DEFAULTS_ENDPOINT = '/api/audio/defaults';
  const MIXER_ENDPOINT = '/api/audio/mixer';
  const MIXER_CHANNELS = ['master', 'plexamp', 'airplay', 'alarm'];
  const byId = (id) => document.getElementById(id);

  let defaultsRequestInFlight = false;
  let mixerPostInFlight = false;
  const mixerDesiredValues = new Map();
  const mixerPendingValues = new Map();
  const mixerDebounceTimers = new Map();
  const mixerDraggingChannels = new Set();

  function installStyles() {
    if (document.querySelector('link[data-audio-workspace-styles]')) {
      return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/settings-audio-workspace.css';
    link.dataset.audioWorkspaceStyles = 'true';
    document.head.appendChild(link);
  }

  function installDefaultsCard(panel) {
    if (byId('audio-airplay-default-card')) {
      return;
    }
    const card = document.createElement('section');
    card.id = 'audio-airplay-default-card';
    card.className = 'settings-card audio-airplay-default-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>AirPlay starting volume</h2>
          <p class="muted small">The sender volume applied when a new AirPlay session becomes controllable.</p>
        </div>
        <span class="settings-chip" id="audio-airplay-default-health">Loading…</span>
      </div>
      <div class="audio-default-layout">
        <label class="setting-toggle">
          <input id="audio-airplay-apply-default" type="checkbox">
          <span>
            <strong>Apply at the start of each session</strong>
            <small>Keeps a newly connected phone from arriving at an unexpectedly tiny volume.</small>
          </span>
        </label>
        <label class="setting-field audio-default-volume-field">
          <span>Starting sender volume</span>
          <div class="audio-default-volume-row">
            <input id="audio-airplay-default-volume" type="range" min="0" max="100" step="1" value="60">
            <output id="audio-airplay-default-volume-value" for="audio-airplay-default-volume">60%</output>
          </div>
          <small>This is the AirPlay/iPhone volume, not the persistent AirPlay output trim above.</small>
        </label>
      </div>
      <div class="audio-default-actions">
        <button class="button settings-secondary" id="audio-airplay-default-save" type="button">Save AirPlay default</button>
        <span class="muted small" id="audio-airplay-default-message">The value is retried briefly while Shairport establishes the remote session.</span>
      </div>
    `;
    panel.appendChild(card);

    const slider = byId('audio-airplay-default-volume');
    slider?.addEventListener('input', () => {
      byId('audio-airplay-default-volume-value').textContent = `${Math.round(Number(slider.value) || 0)}%`;
    });
    byId('audio-airplay-default-save')?.addEventListener('click', saveDefaults);
  }

  function updateMixerReading(channel, percent) {
    const value = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    const slider = byId(`audio-mixer-${channel}`);
    const output = byId(`audio-mixer-${channel}-value`);
    if (slider && slider.value !== String(value)) {
      slider.value = String(value);
    }
    if (output) {
      output.textContent = `${value}%`;
    }
  }

  function setDesiredMixerValue(channel, percent) {
    const value = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    mixerDesiredValues.set(channel, value);
    updateMixerReading(channel, value);
    return value;
  }

  function reassertDesiredMixerValues() {
    mixerDesiredValues.forEach((value, channel) => updateMixerReading(channel, value));
  }

  function releaseDesiredMixerValue(channel, confirmedValue) {
    window.setTimeout(() => {
      if (mixerDraggingChannels.has(channel) || mixerPendingValues.has(channel)) {
        return;
      }
      const desired = mixerDesiredValues.get(channel);
      if (Number(desired) === Number(confirmedValue)) {
        mixerDesiredValues.delete(channel);
      }
    }, 650);
  }

  function queueMixerChange(channel, percent, delay = 120) {
    const value = setDesiredMixerValue(channel, percent);
    window.clearTimeout(mixerDebounceTimers.get(channel));
    mixerDebounceTimers.set(channel, window.setTimeout(() => {
      mixerPendingValues.set(channel, value);
      drainMixerQueue();
    }, delay));
  }

  async function drainMixerQueue() {
    if (mixerPostInFlight || !mixerPendingValues.size) {
      return;
    }

    const [channel, percent] = mixerPendingValues.entries().next().value;
    mixerPendingValues.delete(channel);
    mixerPostInFlight = true;

    const message = byId('audio-mixer-message');
    if (message) {
      message.textContent = `Saving ${channel} at ${percent}%…`;
    }

    try {
      const payload = await requestJson(MIXER_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, percent }),
      });
      const confirmed = Number(payload?.mixer?.channels?.[channel]?.percent);
      if (Number.isFinite(confirmed) && !mixerPendingValues.has(channel)) {
        releaseDesiredMixerValue(channel, confirmed);
      }
      if (message) {
        message.textContent = Number.isFinite(confirmed)
          ? `${channel} saved at ${Math.round(confirmed)}%.`
          : (payload.message || 'Persistent output trim saved.');
      }
    } catch (error) {
      if (message) {
        message.textContent = error.message || `Could not save ${channel}.`;
      }
      window.setTimeout(() => {
        if (!mixerDraggingChannels.has(channel) && !mixerPendingValues.has(channel)) {
          mixerDesiredValues.delete(channel);
        }
      }, 1800);
    } finally {
      mixerPostInFlight = false;
      if (mixerPendingValues.size) {
        drainMixerQueue();
      }
    }
  }

  function installMixerInteractions(card) {
    if (card.dataset.audioInteractionsInstalled === 'true') {
      return;
    }
    card.dataset.audioInteractionsInstalled = 'true';

    card.addEventListener('contextmenu', (event) => {
      if (event.target.closest('[data-mixer-slider], [data-mixer-step]')) {
        event.preventDefault();
      }
    }, true);

    card.addEventListener('dragstart', (event) => {
      if (event.target.closest('[data-mixer-slider], [data-mixer-step]')) {
        event.preventDefault();
      }
    }, true);

    card.addEventListener('pointerdown', (event) => {
      const slider = event.target.closest('[data-mixer-slider]');
      if (!slider) {
        return;
      }
      const channel = slider.dataset.mixerSlider;
      mixerDraggingChannels.add(channel);
      setDesiredMixerValue(channel, slider.value);
    }, true);

    card.addEventListener('pointerup', (event) => {
      const slider = event.target.closest('[data-mixer-slider]');
      if (!slider) {
        return;
      }
      const channel = slider.dataset.mixerSlider;
      mixerDraggingChannels.delete(channel);
      queueMixerChange(channel, slider.value, 0);
    }, true);

    card.addEventListener('pointercancel', (event) => {
      const slider = event.target.closest('[data-mixer-slider]');
      if (slider) {
        mixerDraggingChannels.delete(slider.dataset.mixerSlider);
      }
    }, true);

    card.addEventListener('input', (event) => {
      const slider = event.target.closest('[data-mixer-slider]');
      if (!slider) {
        return;
      }
      event.stopImmediatePropagation();
      queueMixerChange(slider.dataset.mixerSlider, slider.value, 140);
    }, true);

    card.addEventListener('change', (event) => {
      const slider = event.target.closest('[data-mixer-slider]');
      if (!slider) {
        return;
      }
      event.stopImmediatePropagation();
      mixerDraggingChannels.delete(slider.dataset.mixerSlider);
      queueMixerChange(slider.dataset.mixerSlider, slider.value, 0);
    }, true);

    card.addEventListener('click', (event) => {
      const button = event.target.closest('[data-mixer-step]');
      if (!button) {
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      const channel = button.dataset.mixerTarget;
      const slider = byId(`audio-mixer-${channel}`);
      if (!slider || slider.disabled) {
        return;
      }
      const next = Math.max(0, Math.min(100, Number(slider.value) + Number(button.dataset.mixerStep || 0)));
      queueMixerChange(channel, next, 0);
    }, true);
  }

  function prepareMixerCard(panel) {
    const card = byId('audio-mixer-card');
    if (!card) {
      return false;
    }
    if (card.parentElement !== panel) {
      const intro = panel.querySelector('.settings-card.is-intro');
      if (intro) {
        intro.insertAdjacentElement('afterend', card);
      } else {
        panel.prepend(card);
      }
    }
    card.classList.add('is-vertical-console');

    const heading = card.querySelector('h2');
    const copy = card.querySelector('.settings-card-heading p');
    const bannerTitle = card.querySelector('.audio-mixer-banner strong');
    const bannerCopy = card.querySelector('.audio-mixer-banner span');
    if (heading) {
      heading.textContent = 'Persistent output trims';
    }
    if (copy) {
      copy.textContent = 'Per-source calibration stages stored in ALSA. Live player volume lives in the bottom Audio drawer.';
    }
    if (bannerTitle) {
      bannerTitle.textContent = 'Human-scale faders.';
    }
    if (bannerCopy) {
      bannerCopy.textContent = '50% is now about −6 dB, rather than the old raw ALSA value of roughly −25 dB.';
    }

    const labels = {
      master: ['Master', 'Persistent final output default.'],
      plexamp: ['Plexamp trim', 'Downstream of Plexamp’s own volume.'],
      airplay: ['AirPlay trim', 'Downstream of the iPhone/sender volume.'],
      alarm: ['Alarm trim', 'Ceiling after the alarm fade and target.'],
    };
    Object.entries(labels).forEach(([id, values]) => {
      const channel = card.querySelector(`[data-mixer-channel="${id}"]`);
      const title = channel?.querySelector('.audio-mixer-channel-heading strong');
      const description = channel?.querySelector('.audio-mixer-channel-heading small');
      if (title) {
        title.textContent = values[0];
      }
      if (description) {
        description.textContent = values[1];
      }
    });

    installMixerInteractions(card);
    return true;
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Audio request returned ${response.status}.`);
    }
    return payload;
  }

  function renderDefaults(defaults) {
    const volume = Math.max(0, Math.min(100, Number(defaults?.default_volume_percent) || 0));
    const slider = byId('audio-airplay-default-volume');
    if (slider) {
      slider.value = String(volume);
      slider.disabled = defaultsRequestInFlight;
    }
    byId('audio-airplay-default-volume-value').textContent = `${Math.round(volume)}%`;
    const toggle = byId('audio-airplay-apply-default');
    if (toggle) {
      toggle.checked = defaults?.apply_default_volume_on_start !== false;
      toggle.disabled = defaultsRequestInFlight;
    }
    const health = byId('audio-airplay-default-health');
    if (health) {
      health.textContent = defaults?.apply_default_volume_on_start === false ? 'Remember only' : 'Applied on connect';
      health.classList.toggle('is-warning', defaults?.apply_default_volume_on_start === false);
    }
  }

  async function loadDefaults() {
    try {
      const payload = await requestJson(DEFAULTS_ENDPOINT);
      renderDefaults(payload.defaults || {});
    } catch (error) {
      byId('audio-airplay-default-health').textContent = 'Unavailable';
      byId('audio-airplay-default-health').classList.add('is-warning');
      byId('audio-airplay-default-message').textContent = error.message || 'Could not read AirPlay defaults.';
    }
  }

  async function saveDefaults() {
    if (defaultsRequestInFlight) {
      return;
    }
    defaultsRequestInFlight = true;
    const button = byId('audio-airplay-default-save');
    if (button) {
      button.disabled = true;
      button.textContent = 'Saving…';
    }
    byId('audio-airplay-default-message').textContent = 'Saving the AirPlay starting volume…';
    try {
      const payload = await requestJson(DEFAULTS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_volume_percent: Number(byId('audio-airplay-default-volume')?.value) || 0,
          apply_default_volume_on_start: Boolean(byId('audio-airplay-apply-default')?.checked),
        }),
      });
      renderDefaults(payload.defaults || {});
      byId('audio-airplay-default-message').textContent = payload.message || 'AirPlay starting volume saved.';
    } catch (error) {
      byId('audio-airplay-default-message').textContent = error.message || 'Could not save AirPlay defaults.';
    } finally {
      defaultsRequestInFlight = false;
      if (button) {
        button.disabled = false;
        button.textContent = 'Save AirPlay default';
      }
    }
  }

  function suppressPanelContextMenus(panel) {
    panel.addEventListener('contextmenu', (event) => {
      if (event.target.closest('input[type="range"], button')) {
        event.preventDefault();
      }
    }, true);
  }

  function install() {
    installStyles();
    const panel = byId(PANEL_ID);
    if (!panel) {
      window.setTimeout(install, 100);
      return;
    }
    installDefaultsCard(panel);
    if (!prepareMixerCard(panel)) {
      window.setTimeout(install, 100);
      return;
    }
    suppressPanelContextMenus(panel);
    loadDefaults();
    window.setInterval(reassertDesiredMixerValues, 80);
  }

  window.addEventListener('pagehide', () => {
    mixerDebounceTimers.forEach((timer) => window.clearTimeout(timer));
  });

  install();
})();
