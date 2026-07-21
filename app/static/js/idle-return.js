(() => {
  if (window.__aClockworkPlexIdleReturnLoaded) return;
  window.__aClockworkPlexIdleReturnLoaded = true;

  const timeoutSeconds = Number(document.body.dataset.idleTimeoutSeconds || 0);
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) return;

  const timeoutMs = timeoutSeconds * 1000;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    airplay: '/airplay',
    plexamp: '/plexamp',
  };

  let lastActivityAt = Date.now();
  let checking = false;
  let returning = false;

  const markActive = () => {
    lastActivityAt = Date.now();
    returning = false;
  };

  ['pointerdown', 'touchstart', 'keydown', 'wheel', 'input'].forEach((eventName) => {
    window.addEventListener(eventName, markActive, { passive: true, capture: true });
  });

  function normaliseMode(value) {
    const mode = String(value || '').trim().toLowerCase();
    return mode in modeRoutes ? mode : 'clock';
  }

  function idleReturnMode() {
    const preferences = window.ACPDashboardPreferences?.read?.();
    return normaliseMode(
      preferences?.idleReturnMode
      || document.documentElement.dataset.idleReturnMode
      || document.body.dataset.defaultMode
      || 'clock',
    );
  }

  function currentSurface() {
    if (window.ACPPlexamp?.isOpen?.()) return 'plexamp';
    return String(document.body.dataset.activePage || '').trim().toLowerCase();
  }

  function playing(statusPayload, livePayload) {
    if (statusPayload?.alarm_scheduler?.screen_required) return true;
    if (statusPayload?.alarm_audio?.playback_active) return true;

    const live = livePayload?.live || {};
    const plexampState = String(live?.channels?.plexamp?.playback_state || '').toLowerCase();
    const airplayState = String(live?.channels?.airplay?.remote?.playback_status || '').toLowerCase();
    return plexampState === 'playing' || airplayState === 'playing';
  }

  async function returnToMode(mode) {
    const targetMode = normaliseMode(mode);
    const route = modeRoutes[targetMode];
    if (returning || !route) return;

    const surface = currentSurface();
    if (surface === targetMode) {
      markActive();
      return;
    }

    returning = true;
    try {
      await fetch(`/api/mode/${targetMode}`, { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }

    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, { updateMode: false });
    } else {
      window.location.assign(route);
    }
  }

  async function check() {
    if (checking || returning) return;
    const surface = currentSurface();
    if (!surface || surface === 'alarm') return;

    checking = true;
    try {
      const [statusResponse, liveResponse] = await Promise.all([
        fetch('/api/status', { cache: 'no-store' }),
        fetch('/api/audio/live', { cache: 'no-store' }),
      ]);
      if (!statusResponse.ok || !liveResponse.ok) return;

      const [statusPayload, livePayload] = await Promise.all([
        statusResponse.json(),
        liveResponse.json(),
      ]);

      /* Playback counts as activity continuously. Pausing starts a complete fresh
         timeout, regardless of how long the player had already been open. */
      if (playing(statusPayload, livePayload)) {
        markActive();
        return;
      }

      if (Date.now() - lastActivityAt < timeoutMs) return;
      await returnToMode(idleReturnMode());
    } catch (error) {
    } finally {
      checking = false;
    }
  }

  window.addEventListener('acp:dashboard-preferences-changed', () => {
    returning = false;
  });

  window.setInterval(check, 2000);
  window.setTimeout(check, 800);
})();
