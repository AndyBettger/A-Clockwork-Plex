(() => {
  const slider = document.getElementById('airplay-volume-slider');
  const label = document.getElementById('airplay-volume-label');
  const playPauseButton = document.getElementById('airplay-play-pause');
  const playPauseIcon = document.getElementById('airplay-play-pause-icon');

  let heldPercent = null;
  let heldLabel = null;
  let heldUntil = 0;
  let activePointer = false;
  let heldPlaybackStatus = null;
  let heldPlaybackUntil = 0;
  let animationFrame = null;

  function clamp(number, min, max) {
    return Math.min(max, Math.max(min, number));
  }

  function dbFromUiPercent(percent) {
    const cleanPercent = clamp(Number(percent), 0, 100);
    if (cleanPercent <= 0) {
      return 'Muted';
    }
    const db = (cleanPercent / 100) * 30 - 30;
    return `${db.toFixed(1)} dB`;
  }

  function ensureLoop() {
    if (animationFrame !== null) {
      return;
    }

    const tick = () => {
      animationFrame = null;
      const shouldContinue = applyHeldVolume() || applyHeldPlayback();
      if (shouldContinue) {
        animationFrame = window.requestAnimationFrame(tick);
      }
    };

    animationFrame = window.requestAnimationFrame(tick);
  }

  function rememberVolume(percent, durationMs = 22000) {
    heldPercent = clamp(Number(percent), 0, 100);
    heldLabel = dbFromUiPercent(heldPercent);
    heldUntil = Math.max(heldUntil, Date.now() + durationMs);
    applyHeldVolume();
    ensureLoop();
  }

  function applyHeldVolume() {
    if (!slider || heldPercent === null || Date.now() > heldUntil) {
      heldPercent = null;
      heldLabel = null;
      return false;
    }

    const rounded = String(Math.round(heldPercent));
    if (slider.value !== rounded) {
      slider.value = rounded;
    }

    document.body.style.setProperty('--airplay-volume-percent', `${heldPercent}%`);

    if (label && heldLabel) {
      label.textContent = heldLabel;
    }

    return activePointer || heldPercent !== null;
  }

  function iconForPlaybackStatus(status) {
    return String(status || '').toLowerCase() === 'playing' ? 'Ⅱ' : '▶';
  }

  function currentPlaybackStatusFromUi() {
    if (document.body.classList.contains('airplay-remote-playing')) {
      return 'Playing';
    }
    if (document.body.classList.contains('airplay-remote-paused')) {
      return 'Paused';
    }
    return String(playPauseIcon?.textContent || '').includes('▶') ? 'Paused' : 'Playing';
  }

  function rememberPlaybackToggle(durationMs = 9000) {
    if (!playPauseButton || playPauseButton.disabled) {
      return;
    }

    const currentStatus = currentPlaybackStatusFromUi();
    heldPlaybackStatus = currentStatus === 'Playing' ? 'Paused' : 'Playing';
    heldPlaybackUntil = Math.max(heldPlaybackUntil, Date.now() + durationMs);
    applyHeldPlayback();
    ensureLoop();
  }

  function applyHeldPlayback() {
    if (!heldPlaybackStatus || Date.now() > heldPlaybackUntil) {
      heldPlaybackStatus = null;
      return false;
    }

    const isPlaying = heldPlaybackStatus === 'Playing';
    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', !isPlaying);

    if (playPauseButton) {
      playPauseButton.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');
    }

    if (playPauseIcon) {
      playPauseIcon.textContent = iconForPlaybackStatus(heldPlaybackStatus);
    }

    return true;
  }

  if (slider) {
    slider.addEventListener('pointerdown', () => {
      activePointer = true;
      rememberVolume(slider.value, 24000);
    }, { capture: true });

    slider.addEventListener('input', () => {
      rememberVolume(slider.value, 24000);
    }, { capture: true });

    slider.addEventListener('change', () => {
      rememberVolume(slider.value, 24000);
    }, { capture: true });

    slider.addEventListener('pointerup', () => {
      activePointer = false;
      rememberVolume(slider.value, 24000);
    }, { capture: true });

    slider.addEventListener('pointercancel', () => {
      activePointer = false;
      rememberVolume(slider.value, 18000);
    }, { capture: true });
  }

  if (playPauseButton) {
    playPauseButton.addEventListener('click', rememberPlaybackToggle, { capture: true });
  }
})();
