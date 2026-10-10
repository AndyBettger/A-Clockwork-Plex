(() => {
  if (window.__aClockworkPlexNavDrawerLoaded) return;
  window.__aClockworkPlexNavDrawerLoaded = true;

  const drawerNode = () => document.getElementById('nav-drawer');
  const handleNode = () => document.getElementById('nav-handle');
  const mainNavNode = () => drawerNode()?.querySelector('.main-nav');

  if (!drawerNode() || !handleNode() || !mainNavNode()) return;

  const NAVIGATION_MODE_TRANSFER_KEY = 'a-clockwork-plex.navigation-mode-transfer';
  const NAVIGATION_MODE_TRANSFER_MAX_AGE_MS = 15000;
  const SWIPE_THRESHOLD_PX = 24;
  const LIVE_ENDPOINT = '/api/audio/live';
  const MIXER_ENDPOINT = '/api/audio/mixer';
  const CHANNELS = ['master', 'plexamp', 'airplay', 'alarm'];

  let hideTimer = null;
  let touchStartY = null;
  let liveRefreshTimer = null;
  let liveGetInFlight = false;
  let liveSetInFlight = false;
  let trimSetInFlight = false;
  let reassertTimer = null;

  const liveDebounceTimers = new Map();
  const livePendingValues = new Map();
  const liveDesiredValues = new Map();
  const liveDraggingChannels = new Set();

  const trimDebounceTimers = new Map();
  const trimPendingValues = new Map();
  const trimDesiredValues = new Map();
  const trimDraggingChannels = new Set();
  const trimDragState = new Map();

  const clampPercent = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const elevenValue = (percent) => {
    const value = Math.round((clampPercent(percent) / 100) * 110) / 10;
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  };

  function trimKnobMarkup(channel, label, extraClass = '') {
    return `
      <div class="nav-trim-control ${extraClass}">
        <div
          class="nav-trim-knob"
          id="nav-trim-${channel}"
          role="slider"
          tabindex="0"
          aria-label="${label} output trim"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow="100"
          aria-valuetext="11"
          data-nav-trim-knob="${channel}"
        ><span aria-hidden="true"></span></div>
        <output id="nav-trim-${channel}-value">${label.toUpperCase()} 11</output>
      </div>
    `;
  }

  function faderMarkup(channel, label) {
    return `
      <div class="nav-live-fader">
        <span class="nav-fader-scale-label is-top" aria-hidden="true">11</span>
        <span class="nav-fader-scale-label is-bottom" aria-hidden="true">0</span>
        <input id="nav-live-${channel}" type="range" min="0" max="100" step="1" value="0" data-nav-live-slider="${channel}" aria-label="${label} live volume">
        <div class="nav-live-step-row">
          <button type="button" data-nav-live-step="-5" data-nav-live-target="${channel}" aria-label="Reduce ${label}">−</button>
          <button type="button" data-nav-live-step="5" data-nav-live-target="${channel}" aria-label="Increase ${label}">＋</button>
        </div>
      </div>
    `;
  }

  function sourceChannelMarkup(channel, label) {
    return `
      <article class="nav-live-channel nav-source-channel" data-nav-live-channel="${channel}">
        <div class="nav-live-channel-heading">
          <strong>${label}</strong>
          <output id="nav-live-${channel}-value" for="nav-live-${channel}">--%</output>
        </div>
        <div class="nav-source-knobs">
          ${trimKnobMarkup(channel, 'Trim')}
        </div>
        ${faderMarkup(channel, label)}
      </article>
    `;
  }

  function masterChannelMarkup() {
    return `
      <article class="nav-live-channel nav-master-channel" data-nav-live-channel="master">
        <div class="nav-live-channel-heading">
          <strong>Master bus</strong>
          <output id="nav-live-master-value">100%</output>
        </div>
        <div class="nav-master-console">
          ${trimKnobMarkup('alarm', 'Alarm', 'is-alarm-knob')}
          ${trimKnobMarkup('master', 'Master', 'is-master-knob')}
        </div>
      </article>
    `;
  }

  function installAudioPanel() {
    const drawer = drawerNode();
    const mainNav = mainNavNode();
    if (!drawer || !mainNav) return false;

    let audioButton = document.getElementById('nav-audio-button');
    if (!audioButton) {
      audioButton = document.createElement('button');
      audioButton.id = 'nav-audio-button';
      audioButton.type = 'button';
      audioButton.className = 'button nav-button nav-utility-button nav-audio-button';
      audioButton.setAttribute('aria-label', 'Audio');
      audioButton.setAttribute('title', 'Audio');
      audioButton.setAttribute('aria-controls', 'nav-live-mixer');
      audioButton.setAttribute('aria-expanded', 'false');
      audioButton.innerHTML = `
        <svg class="nav-utility-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M4 9.25h3.25L11.5 5.5v13l-4.25-3.75H4z"></path>
          <path d="M15 8.25a5 5 0 0 1 0 7.5"></path>
          <path d="M17.75 5.5a8.75 8.75 0 0 1 0 13"></path>
        </svg>
      `;
      const utilityGroup = mainNav.querySelector('.nav-utilities') || mainNav;
      const settingsLink = utilityGroup.querySelector('a[href="/settings"]');
      utilityGroup.insertBefore(audioButton, settingsLink || null);
    }

    let panel = document.getElementById('nav-live-mixer');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'nav-live-mixer';
      panel.className = 'nav-live-mixer';
      panel.setAttribute('aria-label', 'Audio mixer');
      panel.setAttribute('aria-hidden', 'true');
      panel.innerHTML = `
        <header class="nav-live-mixer-heading">
          <strong>Audio mixer</strong>
          <span id="nav-live-health" class="nav-live-health-dot" aria-label="Checking shared output"></span>
        </header>
        <div class="nav-live-grid">
          ${masterChannelMarkup()}
          ${sourceChannelMarkup('plexamp', 'Plexamp')}
          ${sourceChannelMarkup('airplay', 'AirPlay')}
        </div>
        <div class="nav-live-message" id="nav-live-message" role="status" hidden></div>
      `;
      document.body.appendChild(panel);
    }

    if (audioButton.dataset.navAudioInstalled !== 'true') {
      audioButton.dataset.navAudioInstalled = 'true';
      audioButton.addEventListener('click', () => {
        const currentPanel = document.getElementById('nav-live-mixer');
        if (!currentPanel) return;
        const opening = !mixerOpen();
        setMixerOpen(opening);
        if (opening) refreshLiveMixer();
      });
    }

    if (panel.dataset.navMixerInteractionsInstalled === 'true') return true;
    panel.dataset.navMixerInteractionsInstalled = 'true';

    panel.addEventListener('contextmenu', (event) => {
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step], [data-nav-trim-knob]')) {
        event.preventDefault();
      }
    }, true);

    panel.addEventListener('dragstart', (event) => {
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step], [data-nav-trim-knob]')) {
        event.preventDefault();
      }
    }, true);

    installFaderInteractions(panel);
    installTrimKnobInteractions(panel);
    return true;
  }

  function installFaderInteractions(panel) {
    panel.querySelectorAll('[data-nav-live-slider]').forEach((slider) => {
      const channel = slider.dataset.navLiveSlider;
      slider.addEventListener('pointerdown', () => {
        liveDraggingChannels.add(channel);
        setDesiredLiveValue(channel, slider.value);
        scheduleHide();
      });
      slider.addEventListener('pointerup', () => {
        liveDraggingChannels.delete(channel);
        queueLiveChange(channel, slider.value, 0);
        scheduleHide();
      });
      slider.addEventListener('pointercancel', () => liveDraggingChannels.delete(channel));
      slider.addEventListener('input', () => {
        queueLiveChange(channel, slider.value, 120);
        scheduleHide();
      });
      slider.addEventListener('change', () => {
        liveDraggingChannels.delete(channel);
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
        const next = clampPercent(Number(slider.value) + Number(button.dataset.navLiveStep || 0));
        queueLiveChange(channel, next, 0);
        scheduleHide();
      });
    });
  }

  function installTrimKnobInteractions(panel) {
    panel.querySelectorAll('[data-nav-trim-knob]').forEach((knob) => {
      const channel = knob.dataset.navTrimKnob;

      knob.addEventListener('pointerdown', (event) => {
        if (knob.getAttribute('aria-disabled') === 'true') {
          return;
        }
        event.preventDefault();
        trimDraggingChannels.add(channel);
        trimDragState.set(channel, {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          startValue: Number(trimDesiredValues.get(channel) ?? knob.getAttribute('aria-valuenow') ?? 100),
        });
        knob.classList.add('is-dragging');
        knob.setPointerCapture?.(event.pointerId);
        scheduleHide();
      });

      knob.addEventListener('pointermove', (event) => {
        const drag = trimDragState.get(channel);
        if (!drag || drag.pointerId !== event.pointerId) {
          return;
        }
        event.preventDefault();
        const directionalPixels = (event.clientX - drag.startX) + (drag.startY - event.clientY);
        const next = clampPercent(drag.startValue + directionalPixels / 2);
        queueTrimChange(channel, next, false, 90);
        scheduleHide();
      });

      const finishDrag = (event) => {
        const drag = trimDragState.get(channel);
        if (!drag || drag.pointerId !== event.pointerId) {
          return;
        }
        event.preventDefault();
        const value = Number(trimDesiredValues.get(channel) ?? knob.getAttribute('aria-valuenow') ?? 100);
        trimDraggingChannels.delete(channel);
        trimDragState.delete(channel);
        knob.classList.remove('is-dragging');
        try {
          knob.releasePointerCapture?.(event.pointerId);
        } catch (error) {
        }
        queueTrimChange(channel, value, true, 0);
        scheduleHide();
      };

      knob.addEventListener('pointerup', finishDrag);
      knob.addEventListener('pointercancel', finishDrag);
      knob.addEventListener('keydown', (event) => {
        const next = keyboardKnobValue(event, Number(trimDesiredValues.get(channel) ?? knob.getAttribute('aria-valuenow') ?? 100));
        if (next === null || knob.getAttribute('aria-disabled') === 'true') {
          return;
        }
        event.preventDefault();
        queueTrimChange(channel, next, true, 0);
      });
    });
  }

  function keyboardKnobValue(event, currentValue) {
    const keys = ['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'PageUp', 'PageDown', 'Home', 'End'];
    if (!keys.includes(event.key)) {
      return null;
    }
    let next = Number(currentValue);
    if (event.key === 'ArrowUp' || event.key === 'ArrowRight') next += 1;
    if (event.key === 'ArrowDown' || event.key === 'ArrowLeft') next -= 1;
    if (event.key === 'PageUp') next += 5;
    if (event.key === 'PageDown') next -= 5;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = 100;
    return clampPercent(next);
  }

  function mixerOpen() {
    return document.body.classList.contains('nav-audio-open');
  }

  function navigationInactivitySeconds() {
    const preferences = window.ACPDashboardPreferences?.read?.() || {};
    const raw = preferences.navigationInactivitySeconds
      ?? document.documentElement.dataset.navigationInactivitySeconds
      ?? 6;
    const numeric = Number(raw);
    if (!Number.isFinite(numeric)) return 6;
    return Math.round(Math.max(0, Math.min(30, numeric)));
  }

  function syncNavigationRevealHeight() {
    const drawer = drawerNode();
    const mainNav = mainNavNode();
    if (!drawer || !mainNav) return;

    const style = window.getComputedStyle(drawer);
    const pixels = (value) => {
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : 0;
    };
    const drawerChrome =
      pixels(style.paddingTop)
      + pixels(style.paddingBottom)
      + pixels(style.borderTopWidth)
      + pixels(style.borderBottomWidth);
    const bottomOffset = pixels(style.bottom);
    const mainNavHeight = mainNav.getBoundingClientRect().height;
    const revealHeight = Math.ceil(mainNavHeight + drawerChrome + bottomOffset);

    if (revealHeight > 0) {
      document.documentElement.style.setProperty(
        '--acp-navigation-reveal-height',
        `${revealHeight}px`,
      );
    }
  }

  function closeMixerWithoutScheduling() {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    document.body.classList.remove('nav-audio-open');
    if (panel) panel.setAttribute('aria-hidden', 'true');
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
    if (panel) panel.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (button) {
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      button.classList.toggle('is-active', open);
    }
    window.clearInterval(liveRefreshTimer);
    liveRefreshTimer = open ? window.setInterval(refreshLiveMixer, 2000) : null;
    scheduleHide();
  }

  function setExpanded(expanded) {
    const drawer = drawerNode();
    const handle = handleNode();
    const backdrop = document.getElementById('nav-backdrop');

    if (expanded) syncNavigationRevealHeight();
    document.body.classList.toggle('nav-open', expanded);
    document.body.classList.toggle('nav-mode', expanded);
    drawer?.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    backdrop?.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    handle?.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    handle?.setAttribute('aria-label', expanded ? 'Hide navigation' : 'Show navigation');
    if (!expanded) closeMixerWithoutScheduling();
  }

  function scheduleHide() {
    window.clearTimeout(hideTimer);
    hideTimer = null;
    if (mixerOpen()) return;
    const seconds = navigationInactivitySeconds();
    if (seconds <= 0) return;
    hideTimer = window.setTimeout(() => setExpanded(false), seconds * 1000);
  }

  function showDrawer() {
    setExpanded(true);
    scheduleHide();
  }

  function consumeNavigationModeTransfer() {
    try {
      const raw = window.sessionStorage.getItem(NAVIGATION_MODE_TRANSFER_KEY);
      if (!raw) return false;
      const value = JSON.parse(raw);
      const age = Date.now() - Number(value?.at || 0);
      window.sessionStorage.removeItem(NAVIGATION_MODE_TRANSFER_KEY);
      return age >= 0
        && age <= NAVIGATION_MODE_TRANSFER_MAX_AGE_MS
        && String(value?.path || '') === window.location.pathname;
    } catch (error) {
      try { window.sessionStorage.removeItem(NAVIGATION_MODE_TRANSFER_KEY); } catch (ignored) {}
      return false;
    }
  }

  function hideDrawer() {
    window.clearTimeout(hideTimer);
    setExpanded(false);
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Audio request returned ${response.status}.`);
    }
    return payload;
  }

  function showMessage(text = '', isError = false) {
    const message = document.getElementById('nav-live-message');
    if (!message) return;
    message.textContent = text;
    message.hidden = !text;
    message.classList.toggle('is-error', isError);
  }

  function updateLiveReading(channel, percent) {
    const value = clampPercent(percent);
    const slider = document.getElementById(`nav-live-${channel}`);
    const output = document.getElementById(`nav-live-${channel}-value`);
    if (slider && slider.value !== String(value)) slider.value = String(value);
    if (output) output.textContent = `${value}%`;
  }

  function setTrimVisual(channel, percent) {
    const value = clampPercent(percent);
    const knob = document.getElementById(`nav-trim-${channel}`);
    const output = document.getElementById(`nav-trim-${channel}-value`);
    const angle = -135 + (value / 100) * 270;
    if (knob) {
      knob.style.setProperty('--knob-angle', `${angle}deg`);
      knob.setAttribute('aria-valuenow', String(value));
      knob.setAttribute('aria-valuetext', elevenValue(value));
      knob.title = `${value}% · ${elevenValue(value)} out of 11`;
    }
    if (output) {
      const label = channel === 'master' ? 'MASTER' : channel === 'alarm' ? 'ALARM' : 'TRIM';
      output.textContent = `${label} ${elevenValue(value)}`;
      output.title = `${value}%`;
    }
  }

  function setDesiredLiveValue(channel, percent) {
    const value = clampPercent(percent);
    liveDesiredValues.set(channel, value);
    updateLiveReading(channel, value);
    return value;
  }

  function setDesiredTrimValue(channel, percent) {
    const value = clampPercent(percent);
    trimDesiredValues.set(channel, value);
    setTrimVisual(channel, value);
    if (channel === 'master' || channel === 'alarm') {
      updateLiveReading(channel, value);
    }
    return value;
  }

  function releaseDesiredValue(map, dragging, pending, channel, confirmedValue, delay = 650) {
    window.setTimeout(() => {
      if (dragging.has(channel) || pending.has(channel)) return;
      if (Number(map.get(channel)) === Number(confirmedValue)) map.delete(channel);
    }, delay);
  }

  function renderMixerTrims(mixer) {
    CHANNELS.forEach((id) => {
      const trim = mixer?.channels?.[id] || {};
      const knob = document.getElementById(`nav-trim-${id}`);
      const available = Boolean(trim.available && trim.pcm_available);
      if (!trimDraggingChannels.has(id) && !trimDesiredValues.has(id) && Number.isFinite(Number(trim.percent))) {
        setTrimVisual(id, trim.percent);
      } else if (trimDesiredValues.has(id)) {
        setTrimVisual(id, trimDesiredValues.get(id));
      }
      if (knob) {
        knob.setAttribute('aria-disabled', available ? 'false' : 'true');
        knob.tabIndex = available ? 0 : -1;
      }
    });
  }

  function renderLiveMixer(live) {
    const health = document.getElementById('nav-live-health');
    if (health) {
      health.classList.toggle('is-ready', Boolean(live?.available));
      health.setAttribute('aria-label', live?.available ? 'Shared output ready' : 'Shared output needs attention');
    }

    CHANNELS.forEach((id) => {
      const channel = live?.channels?.[id] || {};
      const slider = document.getElementById(`nav-live-${id}`);
      const buttons = document.querySelectorAll(`[data-nav-live-target="${id}"]`);
      const available = Boolean(channel.available);
      const locallyHeld = liveDraggingChannels.has(id) || liveDesiredValues.has(id) || livePendingValues.has(id);
      if (!locallyHeld && Number.isFinite(Number(channel.percent))) {
        updateLiveReading(id, channel.percent);
      } else if (liveDesiredValues.has(id)) {
        updateLiveReading(id, liveDesiredValues.get(id));
      }
      if (slider) slider.disabled = !available;
      buttons.forEach((button) => { button.disabled = !available; });
    });

    renderMixerTrims(live?.mixer || {});
    if (live?.error) showMessage(live.error, true);
  }

  async function refreshLiveMixer() {
    if (!mixerOpen() || liveGetInFlight || liveSetInFlight || trimSetInFlight) return;
    liveGetInFlight = true;
    try {
      const payload = await requestJson(LIVE_ENDPOINT);
      renderLiveMixer(payload.live || {});
      showMessage('');
    } catch (error) {
      showMessage(error.message || 'Could not read the audio mixer.', true);
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
    if (liveSetInFlight || !livePendingValues.size) return;
    const [channel, percent] = livePendingValues.entries().next().value;
    livePendingValues.delete(channel);
    liveSetInFlight = true;
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
        releaseDesiredValue(liveDesiredValues, liveDraggingChannels, livePendingValues, channel, confirmed);
      }
      showMessage('');
    } catch (error) {
      showMessage(error.message || `Could not change ${channel}.`, true);
      window.setTimeout(() => {
        if (!liveDraggingChannels.has(channel) && !livePendingValues.has(channel)) liveDesiredValues.delete(channel);
      }, 1800);
    } finally {
      liveSetInFlight = false;
      if (livePendingValues.size) drainLiveQueue();
      else window.setTimeout(refreshLiveMixer, 250);
    }
  }

  function queueTrimChange(channel, percent, persist, delay = 90) {
    const value = setDesiredTrimValue(channel, percent);
    window.clearTimeout(trimDebounceTimers.get(channel));
    trimDebounceTimers.set(channel, window.setTimeout(() => {
      const previous = trimPendingValues.get(channel);
      trimPendingValues.set(channel, { percent: value, persist: Boolean(persist || previous?.persist) });
      drainTrimQueue();
    }, delay));
  }

  async function drainTrimQueue() {
    if (trimSetInFlight || !trimPendingValues.size) return;
    const [channel, requestValue] = trimPendingValues.entries().next().value;
    trimPendingValues.delete(channel);
    trimSetInFlight = true;
    try {
      const payload = await requestJson(MIXER_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel,
          percent: requestValue.percent,
          persist: requestValue.persist,
        }),
      });
      const mixer = payload.mixer || {};
      renderMixerTrims(mixer);
      const confirmed = Number(mixer?.channels?.[channel]?.percent);
      if (requestValue.persist && Number.isFinite(confirmed) && !trimPendingValues.has(channel)) {
        releaseDesiredValue(trimDesiredValues, trimDraggingChannels, trimPendingValues, channel, confirmed);
      }
      showMessage('');
    } catch (error) {
      showMessage(error.message || `Could not change ${channel} trim.`, true);
      if (!trimDraggingChannels.has(channel)) trimDesiredValues.delete(channel);
    } finally {
      trimSetInFlight = false;
      if (trimPendingValues.size) drainTrimQueue();
      else window.setTimeout(refreshLiveMixer, 180);
    }
  }

  function reassertDesiredValues() {
    liveDesiredValues.forEach((value, channel) => updateLiveReading(channel, value));
    trimDesiredValues.forEach((value, channel) => setTrimVisual(channel, value));
  }

  installAudioPanel();
  syncNavigationRevealHeight();
  reassertTimer = window.setInterval(reassertDesiredValues, 90);

  let suppressHandleClickUntil = 0;
  let touchStartedOnHandle = false;

  document.addEventListener('click', (event) => {
    const destination = event.target.closest?.('#nav-drawer a.nav-button');
    if (destination && mixerOpen()) {
      closeMixerWithoutScheduling();
      scheduleHide();
    }

    if (event.target.closest?.('#nav-backdrop')) {
      event.preventDefault();
      hideDrawer();
      return;
    }

    const handle = event.target.closest?.('#nav-handle');
    if (!handle) return;
    event.preventDefault();
    if (Date.now() < suppressHandleClickUntil) return;
    if (document.body.classList.contains('nav-open')) hideDrawer();
    else showDrawer();
  });

  document.addEventListener('touchstart', (event) => {
    touchStartedOnHandle = Boolean(event.target.closest?.('#nav-handle'));
    touchStartY = touchStartedOnHandle ? (event.changedTouches[0]?.clientY ?? null) : null;
  }, { passive: true });

  document.addEventListener('touchend', (event) => {
    if (!touchStartedOnHandle) return;
    const touchEndY = event.changedTouches[0]?.clientY ?? null;
    const deltaY = touchStartY !== null && touchEndY !== null
      ? touchStartY - touchEndY
      : 0;
    const open = document.body.classList.contains('nav-open');

    if (!open && deltaY > SWIPE_THRESHOLD_PX) {
      showDrawer();
      suppressHandleClickUntil = Date.now() + 500;
    } else if (open && deltaY < -SWIPE_THRESHOLD_PX) {
      hideDrawer();
      suppressHandleClickUntil = Date.now() + 500;
    }

    touchStartY = null;
    touchStartedOnHandle = false;
  }, { passive: true });

  document.addEventListener('touchcancel', () => {
    touchStartY = null;
    touchStartedOnHandle = false;
  }, { passive: true });

  document.addEventListener('pointerdown', (event) => {
    if (event.target.closest?.('#nav-drawer, #nav-live-mixer')) scheduleHide();
  });
  document.addEventListener('focusin', (event) => {
    if (event.target.closest?.('#nav-drawer, #nav-live-mixer')) scheduleHide();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideDrawer();
  });

  document.addEventListener('acp:surface-settled', () => {
    installAudioPanel();
    syncNavigationRevealHeight();
    const expanded = document.body.classList.contains('nav-open');
    setExpanded(expanded);
  });

  window.addEventListener('resize', syncNavigationRevealHeight);
  window.addEventListener('acp:dashboard-preferences-changed', () => {
    if (document.body.classList.contains('nav-open')) scheduleHide();
  });

  window.ACPNavDrawerController = Object.freeze({
    show: showDrawer,
    hide: hideDrawer,
    toggle: () => {
      if (document.body.classList.contains('nav-open')) hideDrawer();
      else showDrawer();
    },
    ensureAudioPanel: installAudioPanel,
  });

  window.addEventListener('pagehide', () => {
    window.clearInterval(liveRefreshTimer);
    window.clearInterval(reassertTimer);
    liveDebounceTimers.forEach((timer) => window.clearTimeout(timer));
    trimDebounceTimers.forEach((timer) => window.clearTimeout(timer));
  });

  const restoreNavigationMode = consumeNavigationModeTransfer();
  setExpanded(restoreNavigationMode);
  if (restoreNavigationMode) scheduleHide();
})();
