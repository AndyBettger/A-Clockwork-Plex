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
      --airplay-skip-icon-size: clamp(26px, 4.9vmin, 42px);
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

    .airplay-skip-button svg {
      display: block;
      width: var(--airplay-skip-icon-size);
      height: var(--airplay-skip-icon-size);
      overflow: visible;
      fill: currentColor;
      filter: drop-shadow(0 0 8px rgba(247, 249, 255, 0.1));
    }

    .airplay-skip-button:disabled {
      cursor: default;
      opacity: 0.28;
    }

    .airplay-skip-button:not(:disabled):active {
      transform: scale(0.95);
    }

    body.airplay-session-idle .airplay-skip-button {
      display: none;
    }

    @media (max-height: 520px), (max-width: 860px) {
      .airplay-play-pause-wrap {
        gap: clamp(14px, 2.8vmin, 26px);
      }

      .airplay-skip-button {
        --airplay-skip-icon-size: clamp(22px, 4.3vmin, 32px);
        width: clamp(44px, 7.4vmin, 60px);
      }
    }
  `;
  document.head.appendChild(style);

  function iconSvg(direction) {
    const previous = direction === 'previous';
    const barX = previous ? 6.4 : 17.6;
    const firstPoints = previous ? '17.6 5.6 10.4 12 17.6 18.4' : '6.4 5.6 13.6 12 6.4 18.4';
    const secondPoints = previous ? '11.9 5.6 4.7 12 11.9 18.4' : '12.1 5.6 19.3 12 12.1 18.4';

    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="${barX - 1.25}" y="5.4" width="2.5" height="13.2" rx="1.1"></rect>
        <polygon points="${firstPoints}"></polygon>
        <polygon points="${secondPoints}"></polygon>
      </svg>
    `;
  }

  function makeButton(id, label, direction, action) {
    const button = document.createElement('button');
    button.id = id;
    button.type = 'button';
    button.className = 'airplay-skip-button';
    button.setAttribute('aria-label', label);
    button.dataset.airplayAction = action;
    button.innerHTML = iconSvg(direction);
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
