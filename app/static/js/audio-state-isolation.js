(() => {
  if (window.__aClockworkPlexAudioStateIsolationLoaded) return;
  window.__aClockworkPlexAudioStateIsolationLoaded = true;

  const previousFetch = window.fetch.bind(window);
  const liveEndpoint = '/api/audio/live';
  const defaultsEndpoint = '/api/audio/defaults';
  let stableAirplay = null;
  let stableDefaults = null;
  let stableApplication = null;
  let freezeAirplayUntil = 0;

  const copy = (value) => {
    if (value === undefined || value === null) return value;
    try { return JSON.parse(JSON.stringify(value)); } catch (error) { return value; }
  };

  function requestUrl(input) {
    try {
      return new URL(typeof input === 'string' ? input : (input?.url || ''), window.location.href);
    } catch (error) {
      return null;
    }
  }

  function requestMethod(input, init) {
    return String(init?.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
  }

  function requestBody(init) {
    try { return JSON.parse(String(init?.body || '{}')); } catch (error) { return {}; }
  }

  function jsonResponse(payload, response) {
    return new Response(JSON.stringify(payload), {
      status: response.status,
      statusText: response.statusText,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  function publishDefaults(defaults) {
    const value = Number(defaults?.default_volume_percent);
    if (!Number.isFinite(value)) return;
    const slider = document.getElementById('audio-airplay-default-volume');
    const output = document.getElementById('audio-airplay-default-volume-value');
    if (slider && document.activeElement !== slider && !slider.matches(':active')) {
      slider.value = String(Math.max(0, Math.min(100, Math.round(value))));
    }
    if (output) output.textContent = `${Math.max(0, Math.min(100, Math.round(value)))}%`;
    window.dispatchEvent(new CustomEvent('acp-airplay-defaults-changed', { detail: copy(defaults) }));
  }

  function rememberDefaults(payload) {
    const defaults = payload?.defaults || payload?.live?.defaults;
    const application = payload?.application || payload?.live?.airplay_default_application;
    if (defaults && typeof defaults === 'object') {
      stableDefaults = copy(defaults);
      publishDefaults(stableDefaults);
    }
    if (application && typeof application === 'object') stableApplication = copy(application);
  }

  function rememberAirplay(payload) {
    const airplay = payload?.live?.channels?.airplay;
    if (airplay && typeof airplay === 'object') stableAirplay = copy(airplay);
  }

  function preserveDefaults(payload) {
    if (!payload?.live) return;
    if (stableDefaults) payload.live.defaults = copy(stableDefaults);
    else if (payload.live.defaults) stableDefaults = copy(payload.live.defaults);
    if (stableApplication) payload.live.airplay_default_application = copy(stableApplication);
    else if (payload.live.airplay_default_application) stableApplication = copy(payload.live.airplay_default_application);
  }

  function preserveAirplay(payload) {
    if (!payload?.live?.channels) return;
    if (stableAirplay) payload.live.channels.airplay = copy(stableAirplay);
    else if (payload.live.channels.airplay) stableAirplay = copy(payload.live.channels.airplay);
  }

  window.fetch = async (input, init = {}) => {
    const url = requestUrl(input);
    const method = requestMethod(input, init);
    const local = Boolean(url && url.origin === window.location.origin);
    const body = method === 'POST' ? requestBody(init) : {};

    if (local && url.pathname === liveEndpoint && method === 'POST' && body.channel !== 'airplay') {
      freezeAirplayUntil = Date.now() + 1600;
    }

    const response = await previousFetch(input, init);
    if (!local || !response.ok || ![liveEndpoint, defaultsEndpoint].includes(url.pathname)) return response;

    const payload = await response.clone().json().catch(() => null);
    if (!payload || typeof payload !== 'object') return response;

    if (url.pathname === defaultsEndpoint) {
      rememberDefaults(payload);
      return jsonResponse(payload, response);
    }

    preserveDefaults(payload);

    if (method === 'POST') {
      if (body.channel === 'airplay') {
        rememberAirplay(payload);
      } else {
        preserveAirplay(payload);
      }
    } else if (Date.now() < freezeAirplayUntil) {
      preserveAirplay(payload);
    } else {
      rememberAirplay(payload);
    }

    return jsonResponse(payload, response);
  };
})();
