(() => {
  if (window.__aClockworkPlexAudioPolishLoaded) return;
  window.__aClockworkPlexAudioPolishLoaded = true;

  const rawFetch = window.fetch.bind(window);
  const pendingKey = 'a-clockwork-plex.pending-airplay-defaults';
  const defaultsEndpoint = '/api/audio/defaults';
  const liveEndpoint = '/api/audio/live';
  let lastAirplayCheckAt = 0;
  let lastAirplayActive = false;
  let airplayCheckPromise = null;
  let flushInFlight = false;

  const requestUrl = (input) => new URL(typeof input === 'string' ? input : (input?.url || ''), window.location.href);

  function pendingDefaults() {
    try {
      const value = JSON.parse(window.localStorage.getItem(pendingKey) || 'null');
      return value && typeof value === 'object' ? value : null;
    } catch (error) {
      return null;
    }
  }

  function storePendingDefaults(payload) {
    try { window.localStorage.setItem(pendingKey, JSON.stringify(payload)); } catch (error) {}
  }

  function clearPendingDefaults() {
    try { window.localStorage.removeItem(pendingKey); } catch (error) {}
  }

  function jsonResponse(payload, source = null) {
    return new Response(JSON.stringify(payload), {
      status: source?.status || 200,
      statusText: source?.statusText || 'OK',
      headers: { 'Content-Type': 'application/json' },
    });
  }

  async function airplayIsActive(force = false) {
    if (!force && Date.now() - lastAirplayCheckAt < 700) return lastAirplayActive;
    if (airplayCheckPromise) return airplayCheckPromise;
    airplayCheckPromise = rawFetch(liveEndpoint, { cache: 'no-store' })
      .then((response) => response.json())
      .then((payload) => {
        const remote = payload?.live?.channels?.airplay?.remote || {};
        const status = String(remote.playback_status || '').toLowerCase();
        lastAirplayActive = Boolean(remote.available && ['playing', 'paused'].includes(status));
        lastAirplayCheckAt = Date.now();
        return lastAirplayActive;
      })
      .catch(() => lastAirplayActive)
      .finally(() => { airplayCheckPromise = null; });
    return airplayCheckPromise;
  }

  async function mergePending(response, kind) {
    const pending = pendingDefaults();
    if (!pending) return response;
    const payload = await response.clone().json().catch(() => null);
    if (!payload || typeof payload !== 'object') return response;
    const application = {
      status: 'saved-for-next-session',
      in_progress: false,
      target_percent: pending.default_volume_percent,
      reason: 'deferred-during-active-session',
    };
    if (kind === 'defaults') {
      payload.defaults = { ...(payload.defaults || {}), ...pending };
      payload.application = { ...(payload.application || {}), ...application };
    } else if (payload.live) {
      payload.live.defaults = { ...(payload.live.defaults || {}), ...pending };
      payload.live.airplay_default_application = { ...(payload.live.airplay_default_application || {}), ...application };
    }
    return jsonResponse(payload, response);
  }

  window.fetch = async (input, init = {}) => {
    const url = requestUrl(input);
    const method = String(init.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();

    if (url.origin === window.location.origin && url.pathname === defaultsEndpoint && method === 'POST') {
      let payload = null;
      try { payload = JSON.parse(String(init.body || '{}')); } catch (error) {}
      if (payload && await airplayIsActive(true)) {
        storePendingDefaults(payload);
        return jsonResponse({
          ok: true,
          defaults: payload,
          application: {
            status: 'saved-for-next-session',
            in_progress: false,
            target_percent: payload.default_volume_percent,
            reason: 'deferred-during-active-session',
          },
          message: 'AirPlay starting volume saved for the next session.',
        });
      }
      clearPendingDefaults();
    }

    const response = await rawFetch(input, init);
    if (url.origin === window.location.origin && method === 'GET') {
      if (url.pathname === defaultsEndpoint) return mergePending(response, 'defaults');
      if (url.pathname === liveEndpoint) return mergePending(response, 'live');
    }
    return response;
  };

  async function flushDeferredDefaults() {
    const pending = pendingDefaults();
    if (!pending || flushInFlight || await airplayIsActive(true)) return;
    flushInFlight = true;
    try {
      const response = await rawFetch(defaultsEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pending),
      });
      if (response.ok) clearPendingDefaults();
    } catch (error) {
    } finally {
      flushInFlight = false;
    }
  }

  window.setInterval(flushDeferredDefaults, 1500);
  window.setTimeout(flushDeferredDefaults, 500);

  function installDrawerMotion() {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    if (!panel || !button) {
      window.setTimeout(installDrawerMotion, 100);
      return;
    }
    if (panel.dataset.polishMotionInstalled === 'true') return;
    panel.dataset.polishMotionInstalled = 'true';

    const reveal = () => {
      if (panel.hidden) return;
      panel.classList.remove('is-audio-closing', 'is-audio-visible');
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => panel.classList.add('is-audio-visible')));
    };
    new MutationObserver(reveal).observe(panel, { attributes: true, attributeFilter: ['hidden'] });

    document.addEventListener('click', (event) => {
      if (event.target.closest('#nav-audio-button') !== button || panel.hidden) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      panel.classList.remove('is-audio-visible');
      panel.classList.add('is-audio-closing');
      window.setTimeout(() => {
        panel.hidden = true;
        panel.classList.remove('is-audio-closing');
        document.body.classList.remove('nav-audio-open');
        button.classList.remove('is-active');
        button.setAttribute('aria-expanded', 'false');
      }, 225);
    }, true);
  }

  installDrawerMotion();
})();
