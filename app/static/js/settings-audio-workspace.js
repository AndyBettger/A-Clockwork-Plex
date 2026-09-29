(() => {
  if (window.__aClockworkPlexAudioWorkspaceLoaded) {
    return;
  }
  window.__aClockworkPlexAudioWorkspaceLoaded = true;

  const PANEL_ID = 'settings-panel-audio';
  const MIXER_ENDPOINT = '/api/audio/mixer';
  const MIXER_CHANNELS = ['master', 'plexamp', 'airplay', 'alarm'];
  const AUDIO_PATH_POLL_MS = 2500;
  const byId = (id) => document.getElementById(id);

  let mixerPostInFlight = false;
  let audioPathTimer = null;
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
          : (payload.message || 'Persistent output level saved.');
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
      heading.textContent = 'Persistent output levels';
    }
    if (copy) {
      copy.textContent = 'Source calibration stages and the alarm safety ceiling stored in ALSA. Live player volume lives in the bottom Audio drawer.';
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
      alarm: ['Maximum alarm volume', 'Global ceiling after each alarm’s target and fade.'],
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

  function rateLabel(rate) {
    const value = Number(rate);
    if (!Number.isFinite(value) || value <= 0) {
      return null;
    }
    const khz = value / 1000;
    return `${Number.isInteger(khz) ? khz.toFixed(0) : khz.toFixed(1)} kHz`;
  }

  function stageLabel(stage, { dac = false } = {}) {
    if (dac && stage?.available === true && stage?.open === false) {
      return 'Idle / closed';
    }
    if (stage?.available !== true) {
      return 'Not reported';
    }
    const bits = [];
    if (stage?.format) bits.push(String(stage.format));
    const rate = rateLabel(stage?.rate_hz);
    if (rate) bits.push(rate);
    return bits.length ? bits.join(' · ') : 'Available';
  }

  function ensureAudioPathCard(panel) {
    let card = byId('audio-path-card');
    if (card) {
      return card;
    }
    card = document.createElement('section');
    card.id = 'audio-path-card';
    card.className = 'settings-card audio-path-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>Audio path</h2>
          <p>Truthful live format/rate diagnostics. Processing and DAC are measured separately; source rate is shown only when a source observer actually reports it.</p>
        </div>
      </div>
      <div class="audio-path-grid">
        <article class="audio-path-stage">
          <span>Source</span>
          <strong id="audio-path-source">Not reported</strong>
          <small id="audio-path-source-note">Current source observers do not expose a trustworthy format/rate.</small>
        </article>
        <article class="audio-path-stage">
          <span>Processing</span>
          <strong id="audio-path-processing">Unavailable</strong>
          <small id="audio-path-processing-note">Active ALSA route</small>
        </article>
        <article class="audio-path-stage">
          <span>DAC</span>
          <strong id="audio-path-dac">Idle / closed</strong>
          <small id="audio-path-dac-note">Live ALSA hw_params</small>
        </article>
      </div>
    `;
    const mixerCard = byId('audio-mixer-card');
    if (mixerCard?.parentElement === panel) {
      mixerCard.insertAdjacentElement('afterend', card);
    } else {
      panel.appendChild(card);
    }
    return card;
  }

  function renderAudioPath(path) {
    const source = path?.source || {};
    const processing = path?.processing || {};
    const dac = path?.dac || {};
    const sourceValue = byId('audio-path-source');
    const sourceNote = byId('audio-path-source-note');
    const processingValue = byId('audio-path-processing');
    const processingNote = byId('audio-path-processing-note');
    const dacValue = byId('audio-path-dac');
    const dacNote = byId('audio-path-dac-note');

    if (sourceValue) sourceValue.textContent = stageLabel(source);
    if (sourceNote) sourceNote.textContent = source.note || 'Source format/rate is not reported.';
    if (processingValue) processingValue.textContent = stageLabel(processing);
    if (processingNote) {
      const mode = String(path?.route_mode || '');
      processingNote.textContent = mode === 'direct-failback'
        ? 'Direct failback · active ALSA route'
        : (mode === 'split-bus-selected'
          ? 'Managed split bus · active ALSA route'
          : 'Active ALSA route');
    }
    if (dacValue) dacValue.textContent = stageLabel(dac, { dac: true });
    if (dacNote) {
      dacNote.textContent = dac?.open === false
        ? 'Physical DAC is currently closed.'
        : 'Physical DAC · live ALSA hw_params';
    }
  }

  async function refreshAudioPath() {
    const panel = byId(PANEL_ID);
    if (!panel || panel.hidden || document.hidden) {
      return;
    }
    try {
      const payload = await requestJson(MIXER_ENDPOINT);
      renderAudioPath(payload?.mixer?.audio_path || {});
    } catch (error) {
      const processingValue = byId('audio-path-processing');
      const dacValue = byId('audio-path-dac');
      if (processingValue) processingValue.textContent = 'Unavailable';
      if (dacValue) dacValue.textContent = 'Unavailable';
    }
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Audio request returned ${response.status}.`);
    }
    return payload;
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
    if (!prepareMixerCard(panel)) {
      window.setTimeout(install, 100);
      return;
    }
    ensureAudioPathCard(panel);
    suppressPanelContextMenus(panel);
    window.setInterval(reassertDesiredMixerValues, 80);
    refreshAudioPath();
    window.clearInterval(audioPathTimer);
    audioPathTimer = window.setInterval(refreshAudioPath, AUDIO_PATH_POLL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshAudioPath();
  });

  window.addEventListener('pagehide', () => {
    mixerDebounceTimers.forEach((timer) => window.clearTimeout(timer));
    window.clearInterval(audioPathTimer);
  });

  install();
})();
