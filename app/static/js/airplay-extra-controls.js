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
    }
  `;
  document.head.appendChild(style);

  function iconMarkup(direction) {
    const className = direction === 'previous' ? 'is-previous' : 'is-next';
    return `
      <span class="airplay-skip-icon ${className}" aria-hidden="true">
        <span class="airplay-skip-bar"></span>
        <span class="airplay-skip-triangle one"></span>
        <span class="airplay-skip-triangle two"></span>
      </span>
    `;
  }

  function makeButton(id, label, direction, action) {
    const button = document.createElement('button');
    button.id = id;
    button.type = 'button';
    button.className = 'airplay-skip-button';
    button.setAttribute('aria-label', label);
    button.dataset.airplayAction = action;
    button.innerHTML = iconMarkup(direction);
    button.disabled = playButton.disabled;
    return button;
  }

  const backButton = makeButton('airplay-skip-back', 'Previous AirPlay item', 'previous', 'previous');
  const forwardButton = makeButton('airplay-skip-forward', 'Next AirPlay item', 'next', 'next');

  wrap.insertBefore(backButton, playButton);
  wrap.appendChild(forwardButton);

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

  backButton.addEventListener('click', () => sendControl('previous'));
  forwardButton.addEventListener('click', () => sendControl('next'));

  window.setInterval(syncDisabledState, 1000);
  syncDisabledState();
})();