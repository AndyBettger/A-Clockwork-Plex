(() => {
  if (window.__aClockworkPlexAudioPolishLoaded) return;
  window.__aClockworkPlexAudioPolishLoaded = true;

  const rawFetch = window.fetch.bind(window);
  const pendingKey = 'a-clockwork-plex.pending-airplay-defaults';
  const defaultsEndpoint = '/api/audio/defaults';
  const liveEndpoint = '/api/audio/live';
  const statusEndpoint = '/api/status';
  const legacyVolumeEndpoint = '/api/airplay/volume';
  const AIRPLAY_DB_FLOOR = -30;

  let sessionCheckPromise = null;
  let lastSessionCheckAt = 0;
  let lastSessionActive = false;
  let inactiveSince = null;
  let flushInFlight = false;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const requestUrl = (input) => new URL(typeof input === 'string' ? input : (input?.url || ''), window.location.href);

  function uiToSenderPercent(percent) {
    const ui = clamp(Number(percent) || 0, 0, 100);
    if (ui <= 0) return 0;
    const db = 20 * Math.log10(ui / 100);
    return Math.round(clamp(100 * (1 + db / Math.abs(AIRPLAY_DB_FLOOR)), 1, 100));
  }

  function senderToUiPercent(percent) {
    const sender = clamp(Number(percent) || 0, 0, 100);
    if (sender <= 0) return 0;
    const db = AIRPLAY_DB_FLOOR * (1 - sender / 100);
    return Math.round(clamp(100 * Math.pow(10, db / 20), 0, 100));
  }

  window.ACPAirPlayVolumeScale = {
    uiToSenderPercent,
    senderToUiPercent,
    dbFloor: AIRPLAY_DB_FLOOR,
  };

  function pendingDefaults() {
    try {
      const value = JSON.parse(window.localStorage.getItem(pendingKey) || 'null');
      return value && typeof value === 'object' ? value : null;
    } catch (error) {
      return null;
    }
  }

  function storePendingDefaults(payload) {
    const value = {
      default_volume_percent: clamp(Math.round(Number(payload.default_volume_percent) || 0), 0, 100),
      apply_default_volume_on_start: payload.apply_default_volume_on_start !== false,
      saved_at: Date.now(),
    };
    try { window.localStorage.setItem(pendingKey, JSON.stringify(value)); } catch (error) {}
    return value;
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

  function transformRemote(remote) {
    if (!remote || typeof remote !== 'object') return remote;
    const raw = Number(remote.volume_percent);
    if (Number.isFinite(raw)) {
      remote.sender_volume_percent = raw;
      remote.volume_percent = senderToUiPercent(raw);
      if (Number.isFinite(Number(remote.volume))) remote.sender_volume = Number(remote.volume);
      remote.volume = remote.volume_percent / 100;
      remote.volume_scale = 'perceptual-amplitude';
    }
    return remote;
  }

  function transformDefaults(defaults) {
    if (!defaults || typeof defaults !== 'object') return defaults;
    const raw = Number(defaults.default_volume_percent);
    if (Number.isFinite(raw)) {
      defaults.sender_default_volume_percent = raw;
      defaults.default_volume_percent = senderToUiPercent(raw);
      defaults.volume_scale = 'perceptual-amplitude';
    }
    return defaults;
  }

  function transformApplication(application) {
    if (!application || typeof application !== 'object') return application;
    ['target_percent', 'last_confirmed_percent'].forEach((key) => {
      const raw = Number(application[key]);
      if (!Number.isFinite(raw)) return;
      application[`sender_${key}`] = raw;
      application[key] = senderToUiPercent(raw);
    });
    return application;
  }

  function transformPayload(payload) {
    if (!payload || typeof payload !== 'object') return payload;

    if (payload.defaults) transformDefaults(payload.defaults);
    if (payload.application) transformApplication(payload.application);
    if (payload.remote) transformRemote(payload.remote);

    const live = payload.live;
    if (live && typeof live === 'object') {
      if (live.defaults) transformDefaults(live.defaults);
      if (live.airplay_default_application) transformApplication(live.airplay_default_application);
      const airplay = live.channels?.airplay;
      if (airplay && typeof airplay === 'object') {
        const raw = Number(airplay.percent);
        if (Number.isFinite(raw)) {
          airplay.sender_percent = raw;
          airplay.percent = senderToUiPercent(raw);
          airplay.scale = 'perceptual-amplitude';
        }
        if (airplay.remote) transformRemote(airplay.remote);
      }
    }

    const stateRemote = payload.state?.airplay?.remote;
    if (stateRemote) transformRemote(stateRemote);
    return payload;
  }

  function overlayPending(payload) {
    const pending = pendingDefaults();
    if (!pending || !payload || typeof payload !== 'object') return payload;

    const application = {
      status: 'saved-for-next-session',
      in_progress: false,
      target_percent: pending.default_volume_percent,
      reason: 'deferred-during-active-session',
      last_error: null,
    };

    if (payload.defaults) payload.defaults = { ...payload.defaults, ...pending, volume_scale: 'perceptual-amplitude' };
    if (payload.application) payload.application = { ...payload.application, ...application };
    if (payload.live) {
      payload.live.defaults = { ...(payload.live.defaults || {}), ...pending, volume_scale: 'perceptual-amplitude' };
      payload.live.airplay_default_application = {
        ...(payload.live.airplay_default_application || {}),
        ...application,
      };
    }
    return payload;
  }

  async function transformedResponse(response) {
    const payload = await response.clone().json().catch(() => null);
    if (!payload || typeof payload !== 'object') return response;
    transformPayload(payload);
    overlayPending(payload);
    return jsonResponse(payload, response);
  }

  async function sessionIsActive(force = false) {
    if (!force && Date.now() - lastSessionCheckAt < 700) return lastSessionActive;
    if (sessionCheckPromise) return sessionCheckPromise;

    sessionCheckPromise = rawFetch(statusEndpoint, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Status returned ${response.status}.`);
        const payload = await response.json();
        lastSessionActive = payload?.state?.airplay?.active === true;
        lastSessionCheckAt = Date.now();
        if (lastSessionActive) {
          inactiveSince = null;
        } else if (inactiveSince === null) {
          inactiveSince = Date.now();
        }
        return lastSessionActive;
      })
      .catch(() => pendingDefaults() ? true : lastSessionActive)
      .finally(() => { sessionCheckPromise = null; });

    return sessionCheckPromise;
  }

  function parseJsonBody(init) {
    try { return JSON.parse(String(init?.body || '{}')); } catch (error) { return null; }
  }

  function withJsonBody(init, payload) {
    return {
      ...init,
      headers: { ...(init?.headers || {}), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    };
  }

  window.fetch = async (input, init = {}) => {
    const url = requestUrl(input);
    const method = String(init.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
    const local = url.origin === window.location.origin;

    if (local && method === 'POST' && url.pathname === defaultsEndpoint) {
      const submitted = parseJsonBody(init);
      if (submitted && await sessionIsActive(true)) {
        const pending = storePendingDefaults(submitted);
        return jsonResponse({
          ok: true,
          defaults: pending,
          application: {
            status: 'saved-for-next-session',
            in_progress: false,
            target_percent: pending.default_volume_percent,
            reason: 'deferred-during-active-session',
          },
          message: 'AirPlay starting volume saved for the next session.',
        });
      }

      if (submitted) {
        const senderPayload = {
          ...submitted,
          default_volume_percent: uiToSenderPercent(submitted.default_volume_percent),
        };
        const response = await rawFetch(input, withJsonBody(init, senderPayload));
        if (response.ok) clearPendingDefaults();
        return transformedResponse(response);
      }
    }

    if (local && method === 'POST' && url.pathname === liveEndpoint) {
      const submitted = parseJsonBody(init);
      if (submitted?.channel === 'airplay') {
        const response = await rawFetch(input, withJsonBody(init, {
          ...submitted,
          percent: uiToSenderPercent(submitted.percent),
        }));
        return transformedResponse(response);
      }
    }

    if (local && method === 'POST' && url.pathname === legacyVolumeEndpoint) {
      const submitted = parseJsonBody(init);
      if (submitted) {
        const key = Object.prototype.hasOwnProperty.call(submitted, 'volume_percent') ? 'volume_percent' : 'volume';
        const response = await rawFetch(input, withJsonBody(init, {
          ...submitted,
          [key]: uiToSenderPercent(submitted[key]),
        }));
        return transformedResponse(response);
      }
    }

    const response = await rawFetch(input, init);
    if (local && method === 'GET' && [defaultsEndpoint, liveEndpoint, statusEndpoint].includes(url.pathname)) {
      return transformedResponse(response);
    }
    return response;
  };

  async function flushDeferredDefaults() {
    const pending = pendingDefaults();
    if (!pending || flushInFlight || await sessionIsActive(true)) return;
    if (inactiveSince === null || Date.now() - inactiveSince < 3000) return;

    flushInFlight = true;
    try {
      const response = await rawFetch(defaultsEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...pending,
          default_volume_percent: uiToSenderPercent(pending.default_volume_percent),
        }),
      });
      if (response.ok) clearPendingDefaults();
    } catch (error) {
    } finally {
      flushInFlight = false;
    }
  }

  window.setInterval(flushDeferredDefaults, 1500);
  window.setTimeout(flushDeferredDefaults, 700);

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
