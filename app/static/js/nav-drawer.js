(() => {
  const drawer = document.getElementById('nav-drawer');
  const handle = document.getElementById('nav-handle');
  const mainNav = drawer?.querySelector('.main-nav');

  if (!drawer || !handle || !mainNav) {
    return;
  }

  const NORMAL_AUTO_HIDE_MS = 6000;
  const MIXER_AUTO_HIDE_MS = 60000;
  const SWIPE_THRESHOLD_PX = 24;
  const LIVE_ENDPOINT = '/api/audio/live';
  const MIXER_ENDPOINT = '/api/audio/mixer';
  const DEFAULTS_ENDPOINT = '/api/audio/defaults';
  const CHANNELS = ['master', 'plexamp', 'airplay', 'alarm'];

  let hideTimer = null;
  let touchStartY = null;
  let liveRefreshTimer = null;
  let liveGetInFlight = false;
  let liveSetInFlight = false;
  let trimSetInFlight = false;
  let startSaveInFlight = false;
  let reassertTimer = null;
  let airplayApplyDefault = true;
  let airplayStartDesired = null;
  let airplayStartPending = null;
  let airplayStartDrag = null;

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

  function airplayStartKnobMarkup() {
    return `
      <div class="nav-trim-control nav-start-control">
        <div
          class="nav-trim-knob nav-start-knob"
          id="nav-start-airplay"
          role="slider"
          tabindex="0"
          aria-label="AirPlay starting sender volume"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow="60"
          aria-valuetext="6.6"
          data-nav-start-knob
        ><span aria-hidden="true"></span></div>
        <output id="nav-start-airplay-value">START 6.6</output>
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

  function sourceChannelMarkup(channel, label, includeStartKnob = false) {
    return `
      <article class="nav-live-channel nav-source-channel" data-nav-live-channel="${channel}">
        <div class="nav-live-channel-heading">
          <strong>${label}</strong>
          <output id="nav-live-${channel}-value" for="nav-live-${channel}">--%</output>
        </div>
        <div class="nav-source-knobs ${includeStartKnob ? 'has-two-knobs' : ''}">
          ${trimKnobMarkup(channel, 'Trim')}
          ${includeStartKnob ? airplayStartKnobMarkup() : ''}
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
      panel.setAttribute('aria-label', 'Audio mixer');
      panel.innerHTML = `
        <header class="nav-live-mixer-heading">
          <strong>Audio mixer</strong>
          <span id="nav-live-health" class="nav-live-health-dot" aria-label="Checking shared output"></span>
        </header>
        <div class="nav-live-grid">
          ${masterChannelMarkup()}
          ${sourceChannelMarkup('plexamp', 'Plexamp')}
          ${sourceChannelMarkup('airplay', 'AirPlay', true)}
        </div>
        <div class="nav-live-message" id="nav-live-message" role="status" hidden></div>
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
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step], [data-nav-trim-knob], [data-nav-start-knob]')) {
        event.preventDefault();
      }
    }, true);

    panel.addEventListener('dragstart', (event) => {
      if (event.target.closest('[data-nav-live-slider], [data-nav-live-step], [data-nav-trim-knob], [data-nav-start-knob]')) {
        event.preventDefault();
      }
    }, true);

    installFaderInteractions(panel);
    installTrimKnobInteractions(panel);
    installStartKnobInteraction(panel);
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

  function installStartKnobInteraction(panel) {
    const knob = panel.querySelector('[data-nav-start-knob]');
    if (!knob) {
      return;
    }

    knob.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      airplayStartDrag = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        startValue: Number(airplayStartDesired ?? knob.getAttribute('aria-valuenow') ?? 60),
      };
      knob.classList.add('is-dragging');
      knob.setPointerCapture?.(event.pointerId);
      scheduleHide();
    });

    knob.addEventListener('pointermove', (event) => {
      if (!airplayStartDrag || airplayStartDrag.pointerId !== event.pointerId) {
        return;
      }
      event.preventDefault();
      const directionalPixels = (event.clientX - airplayStartDrag.startX) + (airplayStartDrag.startY - event.clientY);
      airplayStartDesired = clampPercent(airplayStartDrag.startValue + directionalPixels / 2);
      setAirplayStartVisual(airplayStartDesired);
      scheduleHide();
    });

    const finish = (event) => {
      if (!airplayStartDrag || airplayStartDrag.pointerId !== event.pointerId) {
        return;
      }
      event.preventDefault();
      const value = clampPercent(airplayStartDesired ?? knob.getAttribute('aria-valuenow') ?? 60);
      airplayStartDrag = null;
      knob.classList.remove('is-dragging');
      try {
        knob.releasePointerCapture?.(event.pointerId);
      } catch (error) {
      }
      queueAirplayStartSave(value);
      scheduleHide();
    };

    knob.addEventListener('pointerup', finish);
    knob.addEventListener('pointercancel', finish);
    knob.addEventListener('keydown', (event) => {
      const next = keyboardKnobValue(event, Number(airplayStartDesired ?? knob.getAttribute('aria-valuenow') ?? 60));
      if (next === null) {
        return;
      }
      event.preventDefault();
      airplayStartDesired = next;
      setAirplayStartVisual(next);
      queueAirplayStartSave(next);
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

  function closeMixerWithoutScheduling() {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    document.body.classList.remove('nav-audio-open');
    if (panel) panel.hidden = true;
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
    if (panel) panel.hidden = !open;
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
    if (!expanded) closeMixerWithoutScheduling();
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

  function setAirplayStartVisual(percent) {
    const value = clampPercent(percent);
    const knob = document.getElementById('nav-start-airplay');
    const output = document.getElementById('nav-start-airplay-value');
    const angle = -135 + (value / 100) * 270;
    if (knob) {
      knob.style.setProperty('--knob-angle', `${angle}deg`);
      knob.setAttribute('aria-valuenow', String(value));
      knob.setAttribute('aria-valuetext', elevenValue(value));
      knob.title = `${value}% starting sender volume`;
    }
    if (output) {
      output.textContent = `START ${elevenValue(value)}`;
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

  function renderAirplayDefaults(live) {
    const defaults = live?.defaults || {};
    airplayApplyDefault = defaults.apply_default_volume_on_start !== false;
    const value = Number(defaults.default_volume_percent);
    if (!airplayStartDrag && airplayStartDesired === null && Number.isFinite(value)) {
      setAirplayStartVisual(value);
    } else if (airplayStartDesired !== null) {
      setAirplayStartVisual(airplayStartDesired);
    }
    const knob = document.getElementById('nav-start-airplay');
    if (knob) {
      knob.classList.toggle('is-bypassed', !airplayApplyDefault);
      knob.setAttribute('aria-description', airplayApplyDefault ? 'Applied when AirPlay connects' : 'Saved but apply-on-connect is disabled');
    }
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
    renderAirplayDefaults(live);
    if (live?.error) showMessage(live.error, true);
  }

  async function refreshLiveMixer() {
    if (!mixerOpen() || liveGetInFlight || liveSetInFlight || trimSetInFlight || startSaveInFlight) return;
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

  function queueAirplayStartSave(percent) {
    airplayStartDesired = clampPercent(percent);
    airplayStartPending = airplayStartDesired;
    setAirplayStartVisual(airplayStartDesired);
    drainAirplayStartSave();
  }

  async function drainAirplayStartSave() {
    if (startSaveInFlight || airplayStartPending === null) {
      return;
    }
    const value = airplayStartPending;
    airplayStartPending = null;
    startSaveInFlight = true;
    try {
      const payload = await requestJson(DEFAULTS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_volume_percent: value,
          apply_default_volume_on_start: airplayApplyDefault,
        }),
      });
      const confirmed = Number(payload?.defaults?.default_volume_percent);
      if (Number.isFinite(confirmed) && airplayStartPending === null) {
        setAirplayStartVisual(confirmed);
        window.setTimeout(() => {
          if (airplayStartPending === null && !airplayStartDrag) {
            airplayStartDesired = null;
          }
        }, 650);
      }
      showMessage('');
    } catch (error) {
      showMessage(error.message || 'Could not save AirPlay starting volume.', true);
    } finally {
      startSaveInFlight = false;
      if (airplayStartPending !== null) {
        drainAirplayStartSave();
      } else {
        window.setTimeout(refreshLiveMixer, 180);
      }
    }
  }

  function reassertDesiredValues() {
    liveDesiredValues.forEach((value, channel) => updateLiveReading(channel, value));
    trimDesiredValues.forEach((value, channel) => setTrimVisual(channel, value));
    if (airplayStartDesired !== null) setAirplayStartVisual(airplayStartDesired);
  }

  installAudioPanel();
  reassertTimer = window.setInterval(reassertDesiredValues, 90);

  handle.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) hideDrawer();
    else showDrawer();
  });

  handle.addEventListener('touchstart', (event) => {
    touchStartY = event.changedTouches[0]?.clientY ?? null;
  }, { passive: true });

  handle.addEventListener('touchend', (event) => {
    const touchEndY = event.changedTouches[0]?.clientY ?? null;
    if (touchStartY !== null && touchEndY !== null && touchStartY - touchEndY > SWIPE_THRESHOLD_PX) {
      showDrawer();
    }
    touchStartY = null;
  }, { passive: true });

  drawer.addEventListener('pointerdown', scheduleHide);
  drawer.addEventListener('focusin', scheduleHide);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideDrawer();
  });

  window.addEventListener('pagehide', () => {
    window.clearInterval(liveRefreshTimer);
    window.clearInterval(reassertTimer);
    liveDebounceTimers.forEach((timer) => window.clearTimeout(timer));
    trimDebounceTimers.forEach((timer) => window.clearTimeout(timer));
  });

  setExpanded(false);
})();
