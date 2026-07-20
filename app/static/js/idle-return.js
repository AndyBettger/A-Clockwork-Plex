(() => {
  if (window.__aClockworkPlexIdleReturnLoaded) return;
  window.__aClockworkPlexIdleReturnLoaded = true;

  const timeoutSeconds = Number(document.body.dataset.idleTimeoutSeconds || 0);
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) return;

  const timeoutMs = timeoutSeconds * 1000;
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

  function currentSurface() {
    if (window.ACPPlexamp?.isOpen?.()) return 'plexamp';
    return document.body.dataset.activePage || '';
  }

  function playing(statusPayload, livePayload) {
    if (statusPayload?.alarm_scheduler?.screen_required) return true;
    if (statusPayload?.alarm_audio?.playback_active) return true;

    const live = livePayload?.live || {};
    const plexampState = String(live?.channels?.plexamp?.playback_state || '').toLowerCase();
    const airplayState = String(live?.channels?.airplay?.remote?.playback_status || '').toLowerCase();
    return plexampState === 'playing' || airplayState === 'playing';
  }

  async function returnToClock() {
    if (returning) return;
    returning = true;
    try {
      await fetch('/api/mode/clock', { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate('/clock');
    } else {
      window.location.assign('/clock');
    }
  }

  async function check() {
    if (checking || returning || Date.now() - lastActivityAt < timeoutMs) return;
    const surface = currentSurface();
    if (!surface || surface === 'clock' || surface === 'alarm') return;

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
      if (!playing(statusPayload, livePayload)) await returnToClock();
    } catch (error) {
    } finally {
      checking = false;
    }
  }

  window.setInterval(check, 2000);
})();
