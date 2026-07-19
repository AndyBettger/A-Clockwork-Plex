(() => {
  if (window.__aClockworkPlexAudioWorkspaceLoaded) {
    return;
  }
  window.__aClockworkPlexAudioWorkspaceLoaded = true;

  const PANEL_ID = 'settings-panel-audio';
  const DEFAULTS_ENDPOINT = '/api/audio/defaults';
  const byId = (id) => document.getElementById(id);
  let defaultsRequestInFlight = false;

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
    return true;
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Audio defaults returned ${response.status}.`);
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
    loadDefaults();
  }

  install();
})();
