(() => {
  if (window.__aClockworkPlexAirPlayControlCoordinatorLoaded) return;
  window.__aClockworkPlexAirPlayControlCoordinatorLoaded = true;

  const button = document.getElementById('airplay-play-pause');
  const icon = document.getElementById('airplay-play-pause-icon');
  if (!button) return;

  let commandInFlight = false;

  function desiredAction() {
    const label = String(button.getAttribute('aria-label') || '').toLowerCase();
    if (label.includes('pause')) return 'pause';
    if (label.includes('play')) return 'play';

    const iconText = String(icon?.textContent || '').trim();
    if (iconText === 'Ⅱ' || iconText === '||') return 'pause';
    return 'play';
  }

  function applyAuthoritativeRemote(remote) {
    if (!remote || typeof remote !== 'object') return;

    const status = String(remote.playback_status || '').toLowerCase();
    const isPlaying = status === 'playing';
    const isPaused = status === 'paused' || status === 'stopped';
    const canControl = Boolean(
      remote.available
      && (remote.can_control || remote.can_play || remote.can_pause),
    );

    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', isPaused);
    button.disabled = !canControl;
    button.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');
    if (icon) icon.textContent = isPlaying ? 'Ⅱ' : '▶';
  }

  async function sendExplicitCommand(event) {
    event.preventDefault();
    event.stopImmediatePropagation();

    if (button.disabled || commandInFlight) return;

    const action = desiredAction();
    commandInFlight = true;
    button.dataset.airplayCommandPending = action;
    button.disabled = true;

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
      applyAuthoritativeRemote(payload.remote);
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
      window.setTimeout(() => {
        if (button.disabled) button.disabled = false;
      }, 1200);
    }
  }

  /* airplay-live.js still renders the authoritative MPRIS state. This capture
     listener owns the command so its older bubbling toggle handler cannot also
     fire and invert a stale button state. */
  button.addEventListener('click', sendExplicitCommand, { capture: true });
})();
