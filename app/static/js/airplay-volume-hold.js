(() => {
  const playPauseButton = document.getElementById('airplay-play-pause');
  const playPauseIcon = document.getElementById('airplay-play-pause-icon');

  let heldPlaybackStatus = null;
  let heldPlaybackUntil = 0;
  let animationFrame = null;

  function iconForPlaybackStatus(status) {
    return String(status || '').toLowerCase() === 'playing' ? 'Ⅱ' : '▶';
  }

  function currentPlaybackStatusFromUi() {
    if (document.body.classList.contains('airplay-remote-playing')) return 'Playing';
    if (document.body.classList.contains('airplay-remote-paused')) return 'Paused';
    return String(playPauseIcon?.textContent || '').includes('▶') ? 'Paused' : 'Playing';
  }

  function applyHeldPlayback() {
    if (!heldPlaybackStatus || Date.now() > heldPlaybackUntil) {
      heldPlaybackStatus = null;
      return false;
    }

    const isPlaying = heldPlaybackStatus === 'Playing';
    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', !isPlaying);
    playPauseButton?.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');
    if (playPauseIcon) playPauseIcon.textContent = iconForPlaybackStatus(heldPlaybackStatus);
    return true;
  }

  function ensureLoop() {
    if (animationFrame !== null) return;
    const tick = () => {
      animationFrame = null;
      if (applyHeldPlayback()) animationFrame = window.requestAnimationFrame(tick);
    };
    animationFrame = window.requestAnimationFrame(tick);
  }

  function rememberPlaybackToggle(durationMs = 9000) {
    if (!playPauseButton || playPauseButton.disabled) return;
    heldPlaybackStatus = currentPlaybackStatusFromUi() === 'Playing' ? 'Paused' : 'Playing';
    heldPlaybackUntil = Math.max(heldPlaybackUntil, Date.now() + durationMs);
    applyHeldPlayback();
    ensureLoop();
  }

  playPauseButton?.addEventListener('click', rememberPlaybackToggle, { capture: true });
})();
