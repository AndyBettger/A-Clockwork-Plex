(() => {
  const wrap = document.querySelector('.airplay-play-pause-wrap');
  const playButton = document.getElementById('airplay-play-pause');

  if (!wrap || !playButton || document.getElementById('airplay-skip-back')) {
    return;
  }

  const style = document.createElement('style');
  style.textContent = `
    .airplay-play-pause-wrap {
      grid-template-columns: auto auto auto;
      gap: clamp(48px, 7.2vmin, 86px);
    }

    .airplay-skip-button {
      display: grid;
      place-items: center;
      width: clamp(62px, 9.8vmin, 88px);
      aspect-ratio: 1;
      border: 1px solid rgba(247, 249, 255, 0.18);
      border-radius: 50%;
      color: rgba(247, 249, 255, 0.9);
      background:
        radial-gradient(circle at 45% 32%, rgba(247, 249, 255, 0.17), rgba(247, 249, 255, 0.055) 58%, rgba(7, 17, 31, 0.18) 100%);
      box-shadow:
        inset 0 0 0 1px rgba(247, 249, 255, 0.08),
        inset 0 -10px 26px rgba(0, 0, 0, 0.18),
        0 12px 34px rgba(0, 0, 0, 0.24),
        0 0 24px rgba(143, 211, 255, 0.1);
      cursor: pointer;
      touch-action: manipulation;
      user-select: none;
    }

    .airplay-skip-button:disabled {
      cursor: default;
      opacity: 0.28;
    }

    .airplay-skip-button:not(:disabled):active {
      transform: scale(0.95);
    }

    .airplay-skip-icon {
      --skip-bar-width: clamp(3px, 0.56vmin, 5px);
      --skip-triangle-width: clamp(9px, 1.55vmin, 14px);
      --skip-icon-height: clamp(17px, 3.08vmin, 27px);
      display: flex;
      align-items: center;
      justify-content: center;
      width: clamp(31px, 5.25vmin, 45px);
      height: var(--skip-icon-height);
      filter: drop-shadow(0 0 8px rgba(247, 249, 255, 0.1));
      transform: translateY(-0.02em);
    }

    .airplay-skip-icon span {
      display: block;
      flex: 0 0 auto;
      background: currentColor;
    }

    .airplay-skip-bar {
      width: var(--skip-bar-width);
      height: calc(var(--skip-icon-height) * 0.96);
      border-radius: 0;
    }

    .airplay-skip-triangle {
      width: var(--skip-triangle-width);
      height: var(--skip-icon-height);
      margin-inline: -0.4px;
    }

    .airplay-skip-icon.is-previous .airplay-skip-bar {
      order: 1;
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle {
      clip-path: polygon(100% 0, 100% 100%, 0 50%);
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle.one {
      order: 2;
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle.two {
      order: 3;
    }

    .airplay-skip-icon.is-next .airplay-skip-bar {
      order: 3;
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle {
      clip-path: polygon(0 0, 0 100%, 100% 50%);
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle.one {
      order: 1;
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle.two {
      order: 2;
    }

    .airplay-spoken-icon {
      position: relative;
      display: grid;
      place-items: center;
      width: clamp(40px, 6.35vmin, 54px);
      aspect-ratio: 1;
      filter: drop-shadow(0 0 8px rgba(247, 249, 255, 0.1));
      transform: translateY(-0.02em);
    }

    .airplay-spoken-svg {
      position: absolute;
      inset: 0;
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
      fill: none;
    }

    .airplay-spoken-arc {
      fill: none;
      stroke: currentColor;
      stroke-width: 4.1;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .airplay-spoken-arrowhead {
      fill: currentColor;
      stroke: none;
    }

    .airplay-spoken-number {
      position: relative;
      z-index: 1;
      color: currentColor;
      font-size: clamp(0.72rem, 1.58vmin, 0.96rem);
      font-weight: 950;
      letter-spacing: -0.05em;
      line-height: 1;
      transform: translateY(0.03em);
    }

    body.airplay-session-idle .airplay-skip-button {
      display: none;
    }

    @media (max-height: 520px), (max-width: 860px) {
      .airplay-play-pause-wrap {
        gap: clamp(32px, 5.4vmin, 56px);
      }

      .airplay-skip-button {
        width: clamp(50px, 8.2vmin, 68px);
      }

      .airplay-skip-icon {
        width: clamp(25px, 4.55vmin, 35px);
        --skip-icon-height: clamp(15px, 2.9vmin, 23px);
      }

      .airplay-spoken-icon {
        width: clamp(34px, 5.65vmin, 44px);
      }
    }
  `;
  document.head.appendChild(style);

  const spokenAppPattern = /\b(prologue|podcasts?|apple podcasts|overcast|pocket casts?|audible|audiobooks?|bookplayer|castro|downcast|libby|borrowbox)\b/i;
  const musicAppPattern = /\b(plexamp|apple music|music|spotify|tidal|qobuz|deezer)\b/i;
  const spokenTextPattern = /\b(podcast|audiobook|audio book|spoken word|chapter|episode|part\s+\d+|book\s+\d+|narrated by|unabridged)\b/i;
  const explicitSpokenPattern = /\b(podcast|audiobook|audio book|spoken word|prologue|audible|overcast|pocket casts?)\b/i;
  const LONG_SPOKEN_SECONDS = 30 * 60;
  const VERY_LONG_SPOKEN_SECONDS = 40 * 60;

  let skipMode = 'track';

  function trackIconMarkup(direction) {
    const className = direction === 'previous' ? 'is-previous' : 'is-next';
    return `
      <span class="airplay-skip-icon ${className}" aria-hidden="true">
        <span class="airplay-skip-bar"></span>
        <span class="airplay-skip-triangle one"></span>
        <span class="airplay-skip-triangle two"></span>
      </span>
    `;
  }

  function spokenIconMarkup(direction) {
    const back = direction === 'previous';
    const className = back ? 'is-back' : 'is-forward';
    const arc = back
      ? 'M18 18 A23 23 0 1 0 46 18'
      : 'M46 18 A23 23 0 1 1 18 18';
    const arrowhead = back
      ? 'M18 18 L31 7 L29 26 Z'
      : 'M46 18 L33 7 L35 26 Z';

    return `
      <span class="airplay-spoken-icon ${className}" aria-hidden="true">
        <svg class="airplay-spoken-svg" viewBox="0 0 64 64" focusable="false">
          <path class="airplay-spoken-arc" d="${arc}"></path>
          <path class="airplay-spoken-arrowhead" d="${arrowhead}"></path>
        </svg>
        <span class="airplay-spoken-number">15</span>
      </span>
    `;
  }

  function buttonMarkup(direction, mode) {
    return mode === 'spoken' ? spokenIconMarkup(direction) : trackIconMarkup(direction);
  }

  function makeButton(id, direction, action) {
    const button = document.createElement('button');
    button.id = id;
    button.type = 'button';
    button.className = 'airplay-skip-button';
    button.dataset.airplayDirection = direction;
    button.dataset.airplayAction = action;
    button.innerHTML = buttonMarkup(direction, skipMode);
    button.disabled = playButton.disabled;
    return button;
  }

  const backButton = makeButton('airplay-skip-back', 'previous', 'previous');
  const forwardButton = makeButton('airplay-skip-forward', 'next', 'next');

  wrap.insertBefore(backButton, playButton);
  wrap.appendChild(forwardButton);

  function textFromValues(values) {
    return values
      .map((value) => String(value || '').trim())
      .filter(Boolean)
      .join(' · ');
  }

  function secondsFromProgress(progress) {
    const value = Number(progress?.duration_seconds);
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  function looksLikeSpokenAudio(payload) {
    const state = payload?.state || {};
    const airplay = state.airplay || {};
    const metadata = airplay.metadata || {};
    const appText = textFromValues([
      metadata.source_name,
      metadata.player_name,
      metadata.source_model,
      metadata.source_user_agent,
    ]);
    const mediaText = textFromValues([
      metadata.genre,
      metadata.format,
      metadata.album,
      metadata.title,
      metadata.artist,
      metadata.album_artist,
      metadata.composer,
    ]);
    const duration = secondsFromProgress(metadata.progress);
    const explicitMusicApp = musicAppPattern.test(appText);

    if (explicitSpokenPattern.test(appText)) {
      return true;
    }

    if (explicitMusicApp && !explicitSpokenPattern.test(mediaText)) {
      return false;
    }

    let score = 0;

    if (spokenAppPattern.test(appText)) {
      score += 5;
    }
    if (explicitSpokenPattern.test(mediaText)) {
      score += 4;
    }
    if (spokenTextPattern.test(mediaText)) {
      score += 2;
    }
    if (duration !== null && duration >= LONG_SPOKEN_SECONDS && !explicitMusicApp) {
      score += 3;
    }
    if (duration !== null && duration >= VERY_LONG_SPOKEN_SECONDS && !explicitMusicApp) {
      score += 1;
    }
    if (duration !== null && duration >= 20 * 60 && spokenTextPattern.test(mediaText)) {
      score += 2;
    }
    if (duration !== null && duration >= 35 * 60 && !metadata.artist) {
      score += 1;
    }

    return score >= 3;
  }

  function setButtonMode(mode) {
    const nextMode = mode === 'spoken' ? 'spoken' : 'track';
    if (skipMode === nextMode && backButton.dataset.airplaySkipMode === nextMode) {
      return;
    }

    skipMode = nextMode;
    for (const button of [backButton, forwardButton]) {
      const direction = button.dataset.airplayDirection;
      button.dataset.airplaySkipMode = nextMode;
      button.classList.toggle('airplay-skip-spoken', nextMode === 'spoken');
      button.innerHTML = buttonMarkup(direction, nextMode);
    }

    backButton.setAttribute('aria-label', nextMode === 'spoken' ? 'Rewind AirPlay 15 seconds' : 'Previous AirPlay item');
    forwardButton.setAttribute('aria-label', nextMode === 'spoken' ? 'Skip AirPlay forward 15 seconds' : 'Next AirPlay item');
  }

  async function sendControl(action) {
    for (const button of [backButton, forwardButton]) {
      button.disabled = true;
    }

    try {
      await fetch('/api/airplay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      window.setTimeout(() => {
        window.dispatchEvent(new Event('airplay-control-sent'));
      }, 350);
    } catch (error) {
    } finally {
      window.setTimeout(syncDisabledState, 900);
    }
  }

  function syncDisabledState() {
    const disabled = playButton.disabled || document.body.classList.contains('airplay-session-idle');
    backButton.disabled = disabled;
    forwardButton.disabled = disabled;
  }

  async function refreshSkipMode() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      setButtonMode(looksLikeSpokenAudio(payload) ? 'spoken' : 'track');
    } catch (error) {
    } finally {
      syncDisabledState();
    }
  }

  backButton.addEventListener('click', () => sendControl(backButton.dataset.airplayAction));
  forwardButton.addEventListener('click', () => sendControl(forwardButton.dataset.airplayAction));
  window.addEventListener('airplay-control-sent', refreshSkipMode);

  window.setInterval(syncDisabledState, 1000);
  window.setInterval(refreshSkipMode, 2500);
  setButtonMode('track');
  syncDisabledState();
  refreshSkipMode();
})();
