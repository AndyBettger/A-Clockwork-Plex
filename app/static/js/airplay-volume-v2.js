(() => {
  if (window.__aClockworkPlexAirPlayVolumeV2Loaded) return;
  window.__aClockworkPlexAirPlayVolumeV2Loaded = true;

  const previousStrip = document.getElementById('airplay-volume-strip');
  if (!previousStrip || !previousStrip.parentNode) return;

  /* airplay-live.js still owns metadata, artwork and progress. Replace the
     complete visible strip so only MixerController can paint or hide volume. */
  const strip = previousStrip.cloneNode(true);
  previousStrip.replaceWith(strip);
  const slider = strip.querySelector('#airplay-volume-slider');
  const label = strip.querySelector('#airplay-volume-label');
  if (!slider) return;

  const endpoint = '/api/audio/state';
  const detail = document.getElementById('airplay-detail');
  let dragging = false;
  let sendInFlight = false;
  let getInFlight = false;
  let sendTimer = null;
  let refreshTimer = null;

  const clamp = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

  function elevenLabel(percent) {
    const value = Math.round((clamp(percent) / 100) * 110) / 10;
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  function paint(percent, channel = {}) {
    const value = clamp(percent);
    const nigel = elevenLabel(value);
    slider.value = String(value);
    slider.setAttribute('aria-valuetext', `${nigel} out of 11`);
    slider.title = `${nigel} out of 11 · ${value}% · ${channel.state_source || 'mixer-controller'}`;
    document.body.style.setProperty('--airplay-volume-percent', `${value}%`);
    if (label) {
      label.textContent = nigel;
      label.title = `${value}%`;
    }
  }

  function airplayChannel(payload) {
    return payload?.audio?.channels?.airplay || {};
  }

  function render(payload) {
    const channel = airplayChannel(payload);
    const available = channel.available === true;
    strip.hidden = !available;
    slider.disabled = !available || sendInFlight;
    if (!dragging && Number.isFinite(Number(channel.effective_percent))) {
      paint(channel.effective_percent, channel);
    }
  }

  async function requestJson(options = {}) {
    const response = await fetch(endpoint, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `AirPlay volume returned ${response.status}.`);
    }
    return payload;
  }

  async function refresh() {
    if (getInFlight || sendInFlight || dragging) return;
    getInFlight = true;
    try {
      render(await requestJson());
    } catch (error) {
      strip.hidden = true;
      slider.disabled = true;
    } finally {
      getInFlight = false;
    }
  }

  async function send(percent) {
    if (sendInFlight) return;
    sendInFlight = true;
    slider.disabled = true;
    try {
      const payload = await requestJson({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: 'airplay', percent: clamp(percent) }),
      });
      render(payload);
    } catch (error) {
      if (detail) {
        detail.textContent = error.message || 'The AirPlay volume command was not accepted.';
      }
    } finally {
      sendInFlight = false;
      window.setTimeout(refresh, 250);
    }
  }

  function queueFinalSend() {
    dragging = false;
    window.clearTimeout(sendTimer);
    sendTimer = window.setTimeout(() => send(slider.value), 80);
  }

  slider.addEventListener('pointerdown', () => {
    dragging = true;
  });
  slider.addEventListener('input', () => {
    dragging = true;
    paint(slider.value, { state_source: 'touchscreen-preview' });
  });
  slider.addEventListener('change', queueFinalSend);
  slider.addEventListener('pointerup', queueFinalSend);
  slider.addEventListener('pointercancel', () => {
    dragging = false;
    refresh();
  });

  refreshTimer = window.setInterval(refresh, 1000);
  window.setTimeout(refresh, 100);

  window.addEventListener('pagehide', () => {
    window.clearInterval(refreshTimer);
    window.clearTimeout(sendTimer);
  });
})();
