(() => {
  const button = document.getElementById('airplay-play-pause');

  if (!button) {
    return;
  }

  const HEARTBEAT_MS = 2000;
  const MAX_HOLD_MS = 20 * 60 * 1000;
  const CLEAR_DELAY_MS = 3500;

  let heartbeatTimer = null;
  let clearTimer = null;
  let stopAt = 0;

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
  }

  function stopHoldSoon() {
    if (clearTimer) {
      window.clearTimeout(clearTimer);
    }
    clearTimer = window.setTimeout(stopHold, CLEAR_DELAY_MS);
  }

  function startHold() {
    stopAt = Date.now() + MAX_HOLD_MS;
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
