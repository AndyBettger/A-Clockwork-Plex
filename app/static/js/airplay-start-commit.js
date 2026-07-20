(() => {
  if (window.__aClockworkPlexAirPlayStartCommitLoaded) return;
  window.__aClockworkPlexAirPlayStartCommitLoaded = true;

  const pendingKey = 'a-clockwork-plex.pending-airplay-defaults';
  const statusEndpoint = '/api/status';
  const defaultsEndpoint = '/api/audio/defaults';
  let previousActive = null;
  let commitInFlight = false;
  let timer = null;

  function pendingDefaults() {
    try {
      const value = JSON.parse(window.localStorage.getItem(pendingKey) || 'null');
      return value && typeof value === 'object' ? value : null;
    } catch (error) {
      return null;
    }
  }

  function clearPending() {
    try { window.localStorage.removeItem(pendingKey); } catch (error) {}
  }

  function uiToSenderPercent(percent) {
    const converter = window.ACPAirPlayVolumeScale?.uiToSenderPercent;
    if (typeof converter === 'function') return converter(percent);
    const ui = Math.max(0, Math.min(100, Number(percent) || 0));
    if (ui <= 0) return 0;
    const db = 20 * Math.log10(ui / 100);
    return Math.round(Math.max(1, Math.min(100, 100 * (1 + db / 30))));
  }

  function xhrJson(method, url, payload = null) {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open(method, url, true);
      request.setRequestHeader('Accept', 'application/json');
      if (payload !== null) request.setRequestHeader('Content-Type', 'application/json');
      request.timeout = 2500;
      request.onload = () => {
        let body = {};
        try { body = JSON.parse(request.responseText || '{}'); } catch (error) {}
        if (request.status >= 200 && request.status < 300 && body.ok !== false) resolve(body);
        else reject(new Error(body.error || `Request returned ${request.status}.`));
      };
      request.onerror = () => reject(new Error('AirPlay START request failed.'));
      request.ontimeout = () => reject(new Error('AirPlay START request timed out.'));
      request.send(payload === null ? null : JSON.stringify(payload));
    });
  }

  async function commitPending(pending) {
    if (!pending || commitInFlight) return false;
    commitInFlight = true;
    try {
      await xhrJson('POST', defaultsEndpoint, {
        default_volume_percent: uiToSenderPercent(pending.default_volume_percent),
        apply_default_volume_on_start: pending.apply_default_volume_on_start !== false,
      });
      clearPending();
      window.dispatchEvent(new CustomEvent('acp-airplay-start-committed', {
        detail: { default_volume_percent: pending.default_volume_percent },
      }));
      return true;
    } catch (error) {
      return false;
    } finally {
      commitInFlight = false;
    }
  }

  async function checkSession() {
    const pending = pendingDefaults();
    try {
      const status = await xhrJson('GET', statusEndpoint);
      const active = status?.state?.airplay?.active === true;
      const disconnected = previousActive === true && active === false;
      const newlyConnected = previousActive === false && active === true;

      if (pending && (disconnected || newlyConnected || active === false)) {
        await commitPending(pending);
      }
      previousActive = active;
    } catch (error) {
    } finally {
      const delay = pendingDefaults() ? 150 : 900;
      timer = window.setTimeout(checkSession, delay);
    }
  }

  window.addEventListener('pagehide', () => window.clearTimeout(timer));
  window.setTimeout(checkSession, 100);
})();
