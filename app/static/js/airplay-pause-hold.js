(() => {
  const button = document.getElementById('airplay-play-pause');

  if (!button) {
    return;
  }

  const HEARTBEAT_MS = 2000;
  const MAX_HOLD_MS = 20 * 60 * 1000;
  const CLEAR_DELAY_MS = 3500;
  const RESUME_GRACE_MS = 6500;

  let heartbeatTimer = null;
  let clearTimer = null;
  let stopAt = 0;
  let startedAt = 0;

  function metadataPlaybackStatus(payload) {
    const event = String(payload?.state?.airplay?.metadata?.last_event || '').toLowerCase();
    if (['pause'].includes(event)) {
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

  function remotePlaybackStatus(payload) {
    return String(payload?.state?.airplay?.remote?.playback_status || '').toLowerCase();
  }

  function sessionLooksPlaying(payload) {
    return metadataPlaybackStatus(payload) === 'playing' || remotePlaybackStatus(payload) === 'playing';
  }

  function sessionLooksGone(payload) {
    const airplay = payload?.state?.airplay || {};
    const remote = airplay.remote || {};
    return airplay.active === false || remote.available === false || metadataPlaybackStatus(payload) === 'stopped';
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
      if (!payload || Date.now() - startedAt < RESUME_GRACE_MS) {
        return;
      }

      if (sessionLooksPlaying(payload)) {
        stopHold();
        return;
      }

      if (sessionLooksGone(payload)) {
        stopHold();
        await fetch('/api/airplay/end', { method: 'POST', cache: 'no-store' });
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