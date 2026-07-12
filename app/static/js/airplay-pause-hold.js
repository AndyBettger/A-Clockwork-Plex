(() => {
  const button = document.getElementById('airplay-play-pause');

  if (!button) {
    return;
  }

  const HEARTBEAT_MS = 1500;
  const MAX_HOLD_MS = 20 * 60 * 1000;
  const CLEAR_DELAY_MS = 3500;
  const RESUME_GRACE_MS = 6500;

  let heartbeatTimer = null;
  let clearTimer = null;
  let stopAt = 0;
  let startedAt = 0;

  function parseDashboardTime(value) {
    if (!value) {
      return null;
    }

    const text = String(value).trim();
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(text);
    const date = new Date(hasTimezone ? text : text.replace(' ', 'T'));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function metadataPlaybackStatus(payload) {
    const event = String(payload?.state?.airplay?.metadata?.last_event || '').toLowerCase();
    if (event === 'pause') {
      return 'paused';
    }
    if (['resume', 'play_resume', 'play_start'].includes(event)) {
      return 'playing';
    }
    if (['play_end', 'active_state_end'].includes(event)) {
      return 'stopped';
    }
    return '';
  }

  function metadataUpdatedAfterHoldStarted(payload) {
    const updatedAt = parseDashboardTime(payload?.state?.airplay?.metadata?.updated_at);
    return Boolean(updatedAt && startedAt && updatedAt.getTime() >= startedAt - 1000);
  }

  function sessionLooksResumedAfterDashboardPause(payload) {
    if (Date.now() - startedAt < RESUME_GRACE_MS) {
      return false;
    }

    return metadataPlaybackStatus(payload) === 'playing' && metadataUpdatedAfterHoldStarted(payload);
  }

  async function statusPayload() {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) {
      return null;
    }
    return response.json();
  }

  async function pingAirPlayMode() {
    if (stopAt && Date.now() > stopAt) {
      stopHold();
      return;
    }

    try {
      await fetch('/api/mode/airplay', {
        method: 'POST',
        cache: 'no-store',
      });

      const payload = await statusPayload();
      if (payload && sessionLooksResumedAfterDashboardPause(payload)) {
        stopHold();
      }
    } catch (error) {
    }
  }

  function stopHold() {
    if (heartbeatTimer) {
      window.clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    if (clearTimer) {
      window.clearTimeout(clearTimer);
      clearTimer = null;
    }
    stopAt = 0;
    startedAt = 0;
    document.body.classList.remove('airplay-dashboard-pause-hold');
  }

  function stopHoldSoon() {
    if (clearTimer) {
      window.clearTimeout(clearTimer);
    }
    clearTimer = window.setTimeout(stopHold, CLEAR_DELAY_MS);
  }

  function startHold() {
    startedAt = Date.now();
    stopAt = startedAt + MAX_HOLD_MS;
    document.body.classList.add('airplay-dashboard-pause-hold');
    if (clearTimer) {
      window.clearTimeout(clearTimer);
      clearTimer = null;
    }
    pingAirPlayMode();
    if (!heartbeatTimer) {
      heartbeatTimer = window.setInterval(pingAirPlayMode, HEARTBEAT_MS);
    }
  }

  function buttonIsCurrentlyPause() {
    const label = String(button.getAttribute('aria-label') || '').toLowerCase();
    return label.includes('pause') || document.body.classList.contains('airplay-remote-playing');
  }

  button.addEventListener('click', () => {
    if (button.disabled) {
      return;
    }

    if (buttonIsCurrentlyPause()) {
      startHold();
    } else {
      stopHoldSoon();
    }
  }, { capture: true });

  window.addEventListener('beforeunload', stopHold);
})();