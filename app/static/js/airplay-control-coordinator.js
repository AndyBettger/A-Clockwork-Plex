(() => {
  if (window.__aClockworkPlexAirPlayControlCoordinatorLoaded) return;
  window.__aClockworkPlexAirPlayControlCoordinatorLoaded = true;

  const button = document.getElementById('airplay-play-pause');
  const icon = document.getElementById('airplay-play-pause-icon');
  if (!button) return;

  let commandInFlight = false;
  let latestRemote = null;
  let latestSessionActive = false;
  let effectiveStatus = 'unknown';
  let pollTimer = null;
  let applying = false;

  function playbackStatus(remote) {
    return String(
      remote?.effective_playback_status
      || remote?.playback_status
      || 'unknown',
    ).trim().toLowerCase();
  }

  function desiredAction() {
    if (effectiveStatus === 'playing') return 'pause';
    if (effectiveStatus === 'paused' || effectiveStatus === 'stopped') return 'play';

    const label = String(button.getAttribute('aria-label') || '').toLowerCase();
    if (label.includes('pause')) return 'pause';
    return 'play';
  }

  function applyAuthoritativeRemote(remote, sessionActive = latestSessionActive) {
    if (!remote || typeof remote !== 'object') return;

    latestRemote = remote;
    latestSessionActive = sessionActive === true;
    effectiveStatus = playbackStatus(remote);

    const isPlaying = effectiveStatus === 'playing';
    const isPaused = effectiveStatus === 'paused' || effectiveStatus === 'stopped';
    const canControl = Boolean(
      latestSessionActive
      && remote.available
      && (remote.can_control || remote.can_play || remote.can_pause),
    );

    applying = true;
    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', isPaused);
    button.disabled = commandInFlight || !canControl;
    button.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');
    if (icon) icon.textContent = isPlaying ? 'Ⅱ' : '▶';
    applying = false;
  }

  async function refreshAuthoritativeStatus() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      const airplay = payload?.state?.airplay || {};
      applyAuthoritativeRemote(airplay.remote || {}, airplay.active === true);
    } catch (error) {
    }
  }

  function optimisticRemote(action) {
    return {
      ...(latestRemote || {}),
      effective_playback_status: action === 'play' ? 'playing' : 'paused',
      playback_status_source: 'explicit-dashboard-command',
    };
  }

  async function sendExplicitCommand(event) {
    event.preventDefault();
    event.stopImmediatePropagation();

    if (button.disabled || commandInFlight) return;

    const action = desiredAction();
    commandInFlight = true;
    button.dataset.airplayCommandPending = action;
    applyAuthoritativeRemote(optimisticRemote(action), true);

    try {
      const response = await fetch('/api/airplay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `AirPlay command returned ${response.status}.`);
      }
      window.dispatchEvent(new CustomEvent('acp:airplay-control-result', {
        detail: { action, remote: payload.remote || null },
      }));
    } catch (error) {
      window.dispatchEvent(new CustomEvent('acp:airplay-control-error', {
        detail: { action, message: String(error?.message || error) },
      }));
    } finally {
      commandInFlight = false;
      delete button.dataset.airplayCommandPending;
      window.setTimeout(refreshAuthoritativeStatus, 120);
      window.setTimeout(refreshAuthoritativeStatus, 500);
      window.setTimeout(refreshAuthoritativeStatus, 1200);
    }
  }

  /* airplay-live.js still renders metadata, artwork, progress and volume. This
     coordinator is the sole playback-button owner. Repair any stale raw-MPRIS
     redraw immediately from the latest effective server state. */
  if (typeof MutationObserver === 'function') {
    const observer = new MutationObserver(() => {
      if (applying || !latestRemote) return;
      window.queueMicrotask(() => applyAuthoritativeRemote(latestRemote, latestSessionActive));
    });
    observer.observe(button, { attributes: true, attributeFilter: ['aria-label', 'disabled'] });
    if (icon) observer.observe(icon, { childList: true, characterData: true, subtree: true });
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
  }

  button.addEventListener('click', sendExplicitCommand, { capture: true });
  pollTimer = window.setInterval(refreshAuthoritativeStatus, 500);
  window.setTimeout(refreshAuthoritativeStatus, 100);
  window.addEventListener('pagehide', () => window.clearInterval(pollTimer), { once: true });
})();
