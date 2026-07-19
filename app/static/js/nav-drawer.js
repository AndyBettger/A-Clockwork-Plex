(() => {
  const drawer = document.getElementById('nav-drawer');
  const handle = document.getElementById('nav-handle');
  const mainNav = drawer?.querySelector('.main-nav');

  if (!drawer || !handle || !mainNav) {
    return;
  }

  const NORMAL_AUTO_HIDE_MS = 6000;
  const MIXER_AUTO_HIDE_MS = 30000;
  const SWIPE_THRESHOLD_PX = 24;
  const LIVE_ENDPOINT = '/api/audio/live';
  const LIVE_ORDER = ['master', 'plexamp', 'airplay', 'alarm'];

  let hideTimer = null;
  let touchStartY = null;
  let liveRefreshTimer = null;
  let liveGetInFlight = false;
  let liveSetInFlight = false;
  const liveDebounceTimers = new Map();
  const livePendingValues = new Map();
  const liveDesiredValues = new Map();
  const draggingChannels = new Set();

  function liveChannelMarkup(id, label, detail) {
    return `
      <article class="nav-live-channel" data-nav-live-channel="${id}">
        <div class="nav-live-channel-heading">
          <strong>${label}</strong>
          <output id="nav-live-${id}-value" for="nav-live-${id}">--%</output>
        </div>
        <small class="nav-live-channel-source" id="nav-live-${id}-source">${detail}</small>
        <div class="nav-live-fader">
          <button type="button" data-nav-live-step="5" data-nav-live-target="${id}" aria-label="Increase ${label}">＋</button>
          <input id="nav-live-${id}" type="range" min="0" max="100" step="1" value="0" data-nav-live-slider="${id}" aria-label="${label} live volume">
          <button type="button" data-nav-live-step="-5" data-nav-live-target="${id}" aria-label="Reduce ${label}">−</button>
        </div>
        <small class="nav-live-channel-detail" id="nav-live-${id}-detail">Checking…</small>
      </article>
    `;
  }

  function installAudioPanel() {
    let audioButton = document.getElementById('nav-audio-button');
    if (!audioButton) {
      audioButton = document.createElement('button');
      audioButton.id = 'nav-audio-button';
      audioButton.type = 'button';
      audioButton.className = 'button nav-button nav-audio-button';
      audioButton.textContent = 'Audio';
      audioButton.setAttribute('aria-controls', 'nav-live-mixer');
      audioButton.setAttribute('aria-expanded', 'false');
      const settingsLink = mainNav.querySelector('a[href="/settings"]');
      mainNav.insertBefore(audioButton, settingsLink || null);
    }

    let panel = document.getElementById('nav-live-mixer');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'nav-live-mixer';
      panel.className = 'nav-live-mixer';
      panel.hidden = true;
      panel.setAttribute('aria-label', 'Live audio mixer');
      panel.innerHTML = `
        <header class="nav-live-mixer-heading">
          <div>
            <strong>Live audio mixer</strong>
            <small>Immediate controls. Persistent trims live under Settings → Audio.</small>
          </div>
          <span id="nav-live-health">Opening…</span>
        </header>
        <div class="nav-live-grid">
          ${liveChannelMarkup('master', 'Master', 'Shared output')}
          ${liveChannelMarkup('plexamp', 'Plexamp', 'Player volume')}
          ${liveChannelMarkup('airplay', 'AirPlay', 'Connected sender')}
          ${liveChannelMarkup('alarm', 'Alarm', 'Output ceiling')}
        </div>
        <div class="nav-live-message" id="nav-live-message">Open the panel to read live player levels.</div>
      `;
      drawer.appendChild(panel);
    }

    audioButton.addEventListener('click', () => {
      const opening = panel.hidden;
      setMixerOpen(opening);
      if (opening) {
        refreshLiveMixer();
      }
    });

    panel.addEventListener('contextmenu', (event) => {
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step]')) {
        event.preventDefault();
      }
    }, true);

    panel.addEventListener('dragstart', (event) => {
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step]')) {
        event.preventDefault();
      }
    }, true);

    panel.querySelectorAll('[data-nav-live-slider]').forEach((slider) => {
      const channel = slider.dataset.navLiveSlider;

      slider.addEventListener('pointerdown', () => {
        draggingChannels.add(channel);
        setDesiredLiveValue(channel, slider.value);
        scheduleHide();
      });

      slider.addEventListener('pointerup', () => {
        draggingChannels.delete(channel);
        queueLiveChange(channel, slider.value, 0);
        scheduleHide();
      });

      slider.addEventListener('pointercancel', () => {
        draggingChannels.delete(channel);
      });

      slider.addEventListener('input', () => {
        queueLiveChange(channel, slider.value, 120);
        scheduleHide();
      });

      slider.addEventListener('change', () => {
        draggingChannels.delete(channel);
        queueLiveChange(channel, slider.value, 0);
      });
    });

    panel.querySelectorAll('[data-nav-live-step]').forEach((button) => {
      button.addEventListener('click', () => {
        const channel = button.dataset.navLiveTarget;
        const slider = document.getElementById(`nav-live-${channel}`);
        if (!slider || slider.disabled) {
          return;
        }
        const next = Math.max(0, Math.min(100, Number(slider.value) + Number(button.dataset.navLiveStep || 0)));
        queueLiveChange(channel, next, 0);
        scheduleHide();
      });
    });
  }

  function mixerOpen() {
    return document.body.classList.contains('nav-audio-open');
  }

  function closeMixerWithoutScheduling() {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    document.body.classList.remove('nav-audio-open');
    if (panel) {
      panel.hidden = true;
    }
    if (button) {
      button.setAttribute('aria-expanded', 'false');
      button.classList.remove('is-active');
    }
    window.clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
  }

  function setMixerOpen(open) {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    document.body.classList.toggle('nav-audio-open', open);
    if (panel) {
      panel.hidden = !open;
    }
    if (button) {
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      button.classList.toggle('is-active', open);
    }
    window.clearInterval(liveRefreshTimer);
    liveRefreshTimer = open ? window.setInterval(refreshLiveMixer, 2000) : null;
    scheduleHide();
  }

  function setExpanded(expanded) {
    document.body.classList.toggle('nav-open', expanded);
    drawer.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    handle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    handle.setAttribute('aria-label', expanded ? 'Hide navigation' : 'Show navigation');
    if (!expanded) {
      closeMixerWithoutScheduling();
    }
  }

  function scheduleHide() {
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(
      () => setExpanded(false),
      mixerOpen() ? MIXER_AUTO_HIDE_MS : NORMAL_AUTO_HIDE_MS,
    );
  }

  function showDrawer() {
    setExpanded(true);
    scheduleHide();
  }

  function hideDrawer() {
    window.clearTimeout(hideTimer);
    setExpanded(false);
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Live audio returned ${response.status}.`);
    }
    return payload;
  }

  function updateLiveReading(channel, percent) {
    const value = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    const slider = document.getElementById(`nav-live-${channel}`);
    const output = document.getElementById(`nav-live-${channel}-value`);
    if (slider && slider.value !== String(value)) {
      slider.value = String(value);
    }
    if (output) {
      output.textContent = `${value}%`;
    }
  }

  function setDesiredLiveValue(channel, percent) {
    const value = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    liveDesiredValues.set(channel, value);
    updateLiveReading(channel, value);
    return value;
  }

  function releaseDesiredLiveValue(channel, confirmedValue) {
    window.setTimeout(() => {
      if (draggingChannels.has(channel) || livePendingValues.has(channel)) {
        return;
      }
      if (Number(liveDesiredValues.get(channel)) === Number(confirmedValue)) {
        liveDesiredValues.delete(channel);
      }
    }, 600);
  }

  function renderLiveMixer(live) {
    const health = document.getElementById('nav-live-health');
    if (health) {
      health.textContent = live?.available ? 'Shared output ready' : 'Needs attention';
      health.classList.toggle('is-warning', !live?.available);
    }

    LIVE_ORDER.forEach((id) => {
      const channel = live?.channels?.[id] || {};
      const slider = document.getElementById(`nav-live-${id}`);
      const source = document.getElementById(`nav-live-${id}-source`);
      const detail = document.getElementById(`nav-live-${id}-detail`);
      const buttons = document.querySelectorAll(`[data-nav-live-target="${id}"]`);
      const available = Boolean(channel.available);
      const locallyHeld = draggingChannels.has(id) || liveDesiredValues.has(id) || livePendingValues.has(id);

      if (slider) {
        if (!locallyHeld && Number.isFinite(Number(channel.percent))) {
          updateLiveReading(id, channel.percent);
        } else if (liveDesiredValues.has(id)) {
          updateLiveReading(id, liveDesiredValues.get(id));
        }
        slider.disabled = !available;
      }

      buttons.forEach((button) => {
        button.disabled = !available;
      });

      if (source) {
        source.textContent = channel.detail || channel.source || 'Live audio';
      }

      if (detail) {
        if (channel.error) {
          detail.textContent = channel.error;
        } else if (id === 'airplay' && !available) {
          detail.textContent = `Idle · next session starts at ${live?.defaults?.default_volume_percent ?? 60}%`;
        } else {
          const trimPercent = channel.trim?.percent;
          detail.textContent = Number.isFinite(Number(trimPercent))
            ? `Output trim ${trimPercent}%`
            : 'Live control ready';
        }
      }
    });

    const message = document.getElementById('nav-live-message');
    if (message && !liveSetInFlight) {
      message.textContent = live?.error || 'Plexamp and AirPlay use their real player volumes; Master and Alarm are immediate shared-output controls.';
    }
  }

  async function refreshLiveMixer() {
    if (!mixerOpen() || liveGetInFlight || liveSetInFlight) {
      return;
    }
    liveGetInFlight = true;
    try {
      const payload = await requestJson(LIVE_ENDPOINT);
      renderLiveMixer(payload.live || {});
    } catch (error) {
      const health = document.getElementById('nav-live-health');
      if (health) {
        health.textContent = 'Unavailable';
        health.classList.add('is-warning');
      }
      const message = document.getElementById('nav-live-message');
      if (message) {
        message.textContent = error.message || 'Could not read the live mixer.';
      }
    } finally {
      liveGetInFlight = false;
    }
  }

  function queueLiveChange(channel, percent, delay = 120) {
    const value = setDesiredLiveValue(channel, percent);
    window.clearTimeout(liveDebounceTimers.get(channel));
    liveDebounceTimers.set(channel, window.setTimeout(() => {
      livePendingValues.set(channel, value);
      drainLiveQueue();
    }, delay));
  }

  async function drainLiveQueue() {
    if (liveSetInFlight || !livePendingValues.size) {
      return;
    }

    const [channel, percent] = livePendingValues.entries().next().value;
    livePendingValues.delete(channel);
    liveSetInFlight = true;

    const message = document.getElementById('nav-live-message');
    if (message) {
      message.textContent = `Setting ${channel} to ${percent}%…`;
    }

    try {
      const payload = await requestJson(LIVE_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, percent }),
      });
      const live = payload.live || {};
      renderLiveMixer(live);
      const confirmed = Number(live?.channels?.[channel]?.percent);
      if (Number.isFinite(confirmed) && !livePendingValues.has(channel)) {
        releaseDesiredLiveValue(channel, confirmed);
      }
      if (message) {
        message.textContent = Number.isFinite(confirmed)
          ? `${channel} is now ${Math.round(confirmed)}%.`
          : (payload.message || 'Live audio level changed.');
      }
    } catch (error) {
      if (message) {
        message.textContent = error.message || `Could not change ${channel}.`;
      }
      window.setTimeout(() => {
        if (!draggingChannels.has(channel) && !livePendingValues.has(channel)) {
          liveDesiredValues.delete(channel);
        }
      }, 1800);
    } finally {
      liveSetInFlight = false;
      if (livePendingValues.size) {
        drainLiveQueue();
      } else {
        window.setTimeout(refreshLiveMixer, 250);
      }
    }
  }

  function reassertDesiredLiveValues() {
    liveDesiredValues.forEach((value, channel) => updateLiveReading(channel, value));
  }

  installAudioPanel();
  window.setInterval(reassertDesiredLiveValues, 80);

  handle.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) {
      hideDrawer();
    } else {
      showDrawer();
    }
  });

  handle.addEventListener('touchstart', (event) => {
    touchStartY = event.changedTouches[0]?.clientY ?? null;
  }, { passive: true });

  handle.addEventListener('touchend', (event) => {
    const touchEndY = event.changedTouches[0]?.clientY ?? null;
    if (touchStartY === null || touchEndY === null) {
      return;
    }

    if (touchStartY - touchEndY > SWIPE_THRESHOLD_PX) {
      showDrawer();
    }
    touchStartY = null;
  }, { passive: true });

  drawer.addEventListener('pointerdown', scheduleHide);
  drawer.addEventListener('focusin', scheduleHide);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hideDrawer();
    }
  });

  window.addEventListener('pagehide', () => {
    window.clearInterval(liveRefreshTimer);
    liveDebounceTimers.forEach((timer) => window.clearTimeout(timer));
  });

  setExpanded(false);
})();
