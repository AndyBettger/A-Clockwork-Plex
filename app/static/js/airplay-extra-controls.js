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
      gap: clamp(22px, 4vmin, 42px);
    }

    .airplay-skip-button {
      display: grid;
      place-items: center;
      width: clamp(54px, 8.8vmin, 78px);
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
      --skip-triangle-width: clamp(8px, 1.45vmin, 13px);
      --skip-triangle-height: clamp(9px, 1.72vmin, 15px);
      position: relative;
      display: block;
      width: clamp(25px, 4.65vmin, 40px);
      height: clamp(19px, 3.55vmin, 31px);
      filter: drop-shadow(0 0 8px rgba(247, 249, 255, 0.1));
      transform: translateY(-0.02em);
    }

    .airplay-skip-icon span {
      position: absolute;
      display: block;
      top: 50%;
      transform: translateY(-50%);
    }

    .airplay-skip-bar {
      top: 10%;
      bottom: 10%;
      width: var(--skip-bar-width);
      border-radius: 999px;
      background: currentColor;
      transform: none;
    }

    .airplay-skip-triangle {
      width: 0;
      height: 0;
      border-top: var(--skip-triangle-height) solid transparent;
      border-bottom: var(--skip-triangle-height) solid transparent;
    }

    .airplay-skip-icon.is-previous .airplay-skip-bar {
      left: 0;
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle {
      border-right: var(--skip-triangle-width) solid currentColor;
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle.one {
      left: calc(var(--skip-bar-width) + clamp(3px, 0.58vmin, 5px));
    }

    .airplay-skip-icon.is-previous .airplay-skip-triangle.two {
      left: calc(var(--skip-bar-width) + var(--skip-triangle-width) + clamp(5px, 0.92vmin, 8px));
    }

    .airplay-skip-icon.is-next .airplay-skip-bar {
      right: 0;
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle {
      border-left: var(--skip-triangle-width) solid currentColor;
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle.one {
      right: calc(var(--skip-bar-width) + clamp(3px, 0.58vmin, 5px));
    }

    .airplay-skip-icon.is-next .airplay-skip-triangle.two {
      right: calc(var(--skip-bar-width) + var(--skip-triangle-width) + clamp(5px, 0.92vmin, 8px));
    }

    body.airplay-session-idle .airplay-skip-button {
      display: none;
    }

    @media (max-height: 520px), (max-width: 860px) {
      .airplay-play-pause-wrap {
        gap: clamp(14px, 2.8vmin, 26px);
      }

      .airplay-skip-button {
        width: clamp(44px, 7.4vmin, 60px);
      }

      .airplay-skip-icon {
        width: clamp(21px, 4.1vmin, 31px);
        height: clamp(16px, 3.05vmin, 24px);
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