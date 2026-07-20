(() => {
  if (window.__aClockworkPlexAirPlayVolumeV2Loaded) return;
  window.__aClockworkPlexAirPlayVolumeV2Loaded = true;

  const slider = document.getElementById('airplay-volume-slider');
  const label = document.getElementById('airplay-volume-label');
  if (!slider) return;

  const endpoint = '/api/audio/live';
  let dragging = false;
  let desired = null;
  let pending = null;
  let sendInFlight = false;
  let getInFlight = false;
  let debounceTimer = null;
  let reassertTimer = null;

  const clamp = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

  function dbLabel(percent) {
    const value = clamp(percent);
    if (value <= 0) return 'Muted';
    return `${((value / 100) * 30 - 30).toFixed(1)} dB`;
  }

  function paint(percent) {
    const value = clamp(percent);
    slider.value = String(value);
    document.body.style.setProperty('--airplay-volume-percent', `${value}%`);
    if (label) label.textContent = dbLabel(value);
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
        }, 650);
      }
    } catch (error) {
      window.setTimeout(() => {
        if (!dragging && pending === null) desired = null;
      }, 1600);
    } finally {
      sendInFlight = false;
      if (pending !== null) drain();
      else window.setTimeout(refresh, 220);
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

  function stopOldHandlers(event) {
    event.stopImmediatePropagation();
  }

  slider.addEventListener('pointerdown', (event) => {
    stopOldHandlers(event);
    dragging = true;
    desired = clamp(slider.value);
    paint(desired);
  }, true);

  slider.addEventListener('input', (event) => {
    stopOldHandlers(event);
    queue(slider.value, 120);
  }, true);

  slider.addEventListener('change', (event) => {
    stopOldHandlers(event);
    dragging = false;
    queue(slider.value, 0);
  }, true);

  slider.addEventListener('pointerup', (event) => {
    stopOldHandlers(event);
    dragging = false;
    queue(slider.value, 0);
  }, true);

  slider.addEventListener('pointercancel', (event) => {
    stopOldHandlers(event);
    dragging = false;
    queue(slider.value, 0);
  }, true);

  reassertTimer = window.setInterval(() => {
    if (desired !== null) paint(desired);
  }, 90);

  window.setInterval(refresh, 2000);
  window.setTimeout(refresh, 150);
  window.addEventListener('pagehide', () => {
    window.clearInterval(reassertTimer);
    window.clearTimeout(debounceTimer);
  });
})();
