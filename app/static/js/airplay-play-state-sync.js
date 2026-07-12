(() => {
  const button = document.getElementById('airplay-play-pause');
  const icon = document.getElementById('airplay-play-pause-icon');

  if (!button) {
    return;
  }

  function eventPlaybackStatus(payload) {
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

  function remotePlaybackStatus(payload) {
    return String(payload?.state?.airplay?.remote?.playback_status || '').toLowerCase();
  }

  function syncButton(payload) {
    const active = payload?.state?.airplay?.active === true;
    const remote = payload?.state?.airplay?.remote || {};
    const eventStatus = eventPlaybackStatus(payload);
    const remoteStatus = remotePlaybackStatus(payload);
    const status = eventStatus || remoteStatus;
    const isPlaying = status === 'playing';
    const isPaused = status === 'paused' || status === 'stopped';
    const canControl = Boolean(active && (remote.can_control || remote.available));

    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', isPaused);

    button.disabled = !canControl;
    button.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');

    if (icon) {
      icon.textContent = isPlaying ? 'Ⅱ' : '▶';
    }
  }

  async function poll() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }
      syncButton(await response.json());
    } catch (error) {
    }
  }

  window.setInterval(poll, 1000);
  window.setTimeout(poll, 350);
})();