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
      display: grid;
      place-items: center;
      width: clamp(42px, 6.65vmin, 56px);
      aspect-ratio: 1;
      filter: drop-shadow(0 0 8px rgba(247, 249, 255, 0.1));
      transform: translateY(-0.02em);
    }

    .airplay-spoken-svg {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
      color: currentColor;
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
        width: clamp(35px, 5.85vmin, 46px);
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

  // Sourced SVG paths, replacing the earlier hand-drawn geometry:
  // Replay:  https://upload.wikimedia.org/wikipedia/commons/6/6f/VK_icons_replay_15_36.svg
  // Forward: https://upload.wikimedia.org/wikipedia/commons/a/aa/VK_icons_forward_15_28.svg
  function spokenIconMarkup(direction) {
    if (direction === 'previous') {
      return `
        <span class="airplay-spoken-icon is-back" aria-hidden="true">
          <svg class="airplay-spoken-svg" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 36 36" focusable="false">
            <path d="M17.444 5.025c0-.41-.45-.662-.8-.447L10.19 8.544a.525.525 0 0 0 0 .894l6.453 3.966c.35.216.8-.036.8-.447v-2.84a9.375 9.375 0 0 1 0 18.75 9.378 9.378 0 0 1-9.213-7.63 1.125 1.125 0 0 0-2.211.417 11.628 11.628 0 0 0 11.424 9.462c6.42 0 11.625-5.205 11.625-11.625S23.864 7.866 17.444 7.866v-2.84Z"/>
            <path d="M13.5 23.841a.525.525 0 0 1-.525-.525V17.95l-1.301.511a.42.42 0 0 1-.574-.39v-.73c0-.211.126-.402.32-.484l2.768-1.17a.525.525 0 0 1 .73.483v7.147c0 .29-.236.525-.525.525H13.5Zm3.371-2.317a.904.904 0 0 0-.215.61c0 .322.126.625.377.912.251.287.595.518 1.03.692.436.175.916.262 1.442.262.64 0 1.202-.123 1.686-.37a2.67 2.67 0 0 0 1.121-1.044c.263-.45.395-.97.395-1.564 0-.534-.11-1.003-.327-1.409a2.344 2.344 0 0 0-.915-.944c-.392-.225-.846-.337-1.36-.337-.345 0-.665.057-.959.171-.294.115-.512.266-.653.455h-.1l.13-1.781h2.954c.286 0 .505-.068.656-.202.151-.134.227-.326.227-.575 0-.252-.077-.449-.23-.59-.153-.14-.37-.21-.653-.21h-3.343c-.734 0-1.123.323-1.166.969l-.194 2.924a1.01 1.01 0 0 0 .103.53.87.87 0 0 0 .347.364 1.02 1.02 0 0 0 .868.06c.114-.046.242-.125.383-.238.177-.128.36-.227.55-.298.19-.07.376-.105.556-.105.244 0 .463.053.657.16.194.106.345.255.453.448.108.192.162.413.162.662 0 .26-.057.491-.17.692a1.21 1.21 0 0 1-.475.469c-.202.112-.43.169-.685.169a1.48 1.48 0 0 1-.73-.184 2.2 2.2 0 0 1-.636-.569 1.129 1.129 0 0 0-.338-.288.822.822 0 0 0-.386-.09.706.706 0 0 0-.562.249Z"/>
          </svg>
        </span>
      `;
    }

    return `
      <span class="airplay-spoken-icon is-forward" aria-hidden="true">
        <svg class="airplay-spoken-svg" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 28 28" focusable="false">
          <g fill="currentColor">
            <path d="m13.7084 6.11809v-2.2097c0-.07549.0209-.14951.0604-.21382.1181-.19213.3696-.25214.5617-.13405l5.0186 3.0847c.0545.03355.1005.07947.134.13405.1181.19212.0581.4436-.134.56169l-5.0186 3.08474c-.0643.0395-.1383.0604-.2138.0604-.2255 0-.4083-.1828-.4083-.4083v-2.20971c-4.02712 0-7.29171 3.26461-7.29171 7.29171 0 4.027 3.26459 7.2916 7.29171 7.2916 3.5211 0 6.5218-2.5144 7.1655-5.9333.0894-.4749.5469-.7874 1.0218-.698.4749.0895.7874.5469.698 1.0218-.7987 4.2423-4.5188 7.3595-8.8853 7.3595-4.99362 0-9.04171-4.0481-9.04171-9.0416 0-4.9936 4.04809-9.04171 9.04171-9.04171z"/>
            <path d="m10.9422 18.5431c-.2256 0-.4084-.1828-.4084-.4083v-4.1745l-1.01222.3976c-.21429.0842-.4461-.0738-.4461-.304v-.5677c0-.164.09818-.3121.24928-.376l2.15254-.9104c.2692-.1139.5674.0837.5674.376v5.559c0 .2255-.1828.4083-.4083.4083z"/>
            <path d="m13.5642 16.7408c-.1114.1295-.1671.2879-.1671.4751 0 .2496.0976.4859.293.709.1953.2231.4623.4025.8011.5382.3387.1357.7125.2036 1.1215.2036.4974 0 .9346-.096 1.3115-.2879.3769-.1918.6676-.4625.8721-.8119.2044-.3495.3067-.7551.3067-1.2169 0-.4149-.0847-.78-.2541-1.0951s-.4067-.56-.7118-.7347c-.3052-.1748-.6577-.2621-1.0575-.2621-.2685 0-.5173.0444-.7462.1334-.2288.0889-.3982.2067-.5081.3533h-.0778l.1007-1.3853h2.298c.2228 0 .3929-.0523.5104-.1568s.1763-.2535.1763-.4469c0-.1966-.0595-.3495-.1786-.4587-.119-.1092-.2883-.1638-.5081-.1638h-2.6001c-.5707 0-.8728.2512-.9064.7535l-.1511 2.2745c-.0091.1529.0176.2902.0801.4119.0626.1216.1526.216.2701.2831s.251.1006.4006.1006c.0946 0 .1861-.0179.2746-.0538s.1877-.0975.2976-.1849c.1373-.0998.28-.177.428-.2316s.2922-.0819.4326-.0819c.1892 0 .3593.0413.5104.124s.2686.1989.3525.3487c.0839.1497.1259.3213.1259.5148 0 .2028-.0443.3822-.1328.5382s-.2113.2777-.3685.365c-.1571.0874-.3349.1311-.5333.1311-.2075 0-.3967-.0476-.5676-.1428-.1709-.0951-.3357-.2426-.4944-.4422-.0855-.103-.1732-.1779-.2632-.2247-.0901-.0468-.19-.0702-.2999-.0702-.18 0-.3257.0648-.4371.1942z"/>
          </g>
        </svg>
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