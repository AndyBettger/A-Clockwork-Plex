(() => {
  if (window.__aClockworkPlexAirPlayVolumeV2Loaded) return;
  window.__aClockworkPlexAirPlayVolumeV2Loaded = true;

  const previousSlider = document.getElementById('airplay-volume-slider');
  const previousLabel = document.getElementById('airplay-volume-label');
  if (!previousSlider) return;

  /* airplay-live.js loaded first and still owns references to the original
     elements. Replace them so its status painting can continue harmlessly on
     detached nodes while this controller is the only writer to the visible UI. */
  const slider = previousSlider.cloneNode(true);
  previousSlider.replaceWith(slider);
  const label = previousLabel ? previousLabel.cloneNode(true) : null;
  if (previousLabel && label) previousLabel.replaceWith(label);

  const endpoint = '/api/audio/live';
  let dragging = false;
  let desired = null;
  let pending = null;
  let sendInFlight = false;
  let getInFlight = false;
  let debounceTimer = null;
  let reassertTimer = null;
  let refreshTimer = null;

  const clamp = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

  function elevenLabel(percent) {
    const value = Math.round((clamp(percent) / 100) * 110) / 10;
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  function paint(percent) {
    const value = clamp(percent);
    const nigel = elevenLabel(value);
    slider.value = String(value);
    slider.setAttribute('aria-valuetext', `${nigel} out of 11`);
    slider.title = `${nigel} out of 11 · ${value}%`;
    document.body.style.setProperty('--airplay-volume-percent', `${value}%`);
    if (label) {
      label.textContent = nigel;
      label.title = `${value}%`;
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

  function queue(percent, delay = 120) {
    desired = clamp(percent);
    paint(desired);
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => {
      pending = desired;
      drain();
    }, delay);
  }

  async function drain() {
    if (sendInFlight || pending === null) return;
    const value = pending;
    pending = null;
    sendInFlight = true;
    try {
      const payload = await requestJson({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: 'airplay', percent: value }),
      });
      const confirmed = Number(payload?.live?.channels?.airplay?.percent);
      if (Number.isFinite(confirmed) && pending === null && !dragging) {
        paint(confirmed);
        window.setTimeout(() => {
          if (!dragging && pending === null && Number(desired) === Number(confirmed)) desired = null;
        }, 750);
      }
    } catch (error) {
      window.setTimeout(() => {
        if (!dragging && pending === null) desired = null;
      }, 1600);
    } finally {
      sendInFlight = false;
      if (pending !== null) drain();
      else window.setTimeout(refresh, 260);
    }
  }

  async function refresh() {
    if (getInFlight || sendInFlight || dragging || pending !== null) return;
    getInFlight = true;
    try {
      const payload = await requestJson();
      const channel = payload?.live?.channels?.airplay || {};
      slider.disabled = !channel.available;
      if (desired === null && Number.isFinite(Number(channel.percent))) paint(channel.percent);
    } catch (error) {
    } finally {
      getInFlight = false;
    }
  }

  slider.addEventListener('pointerdown', () => {
    dragging = true;
    desired = clamp(slider.value);
    paint(desired);
  });

  slider.addEventListener('input', () => queue(slider.value, 120));
  slider.addEventListener('change', () => {
    dragging = false;
    queue(slider.value, 0);
  });
  slider.addEventListener('pointerup', () => {
    dragging = false;
    queue(slider.value, 0);
  });
  slider.addEventListener('pointercancel', () => {
    dragging = false;
    queue(slider.value, 0);
  });

  reassertTimer = window.setInterval(() => {
    if (desired !== null) paint(desired);
  }, 90);
  refreshTimer = window.setInterval(refresh, 2000);
  window.setTimeout(refresh, 150);

  window.addEventListener('pagehide', () => {
    window.clearInterval(reassertTimer);
    window.clearInterval(refreshTimer);
    window.clearTimeout(debounceTimer);
  });
})();
