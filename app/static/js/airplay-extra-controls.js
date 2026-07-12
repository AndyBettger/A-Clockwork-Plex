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
      gap: clamp(18px, 3.4vmin, 34px);
    }

    .airplay-skip-button {
      display: grid;
      place-items: center;
      width: clamp(50px, 8vmin, 74px);
      aspect-ratio: 1;
      border: 0;
      border-radius: 50%;
      color: rgba(247, 249, 255, 0.92);
      background: rgba(247, 249, 255, 0.11);
      box-shadow:
        inset 0 0 0 1px rgba(247, 249, 255, 0.16),
        0 12px 32px rgba(0, 0, 0, 0.22),
        0 0 24px rgba(143, 211, 255, 0.12);
      font-size: clamp(1.25rem, 3.4vmin, 2rem);
      font-weight: 950;
      line-height: 1;
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

    body.airplay-session-idle .airplay-skip-button {
      display: none;
    }

    @media (max-height: 520px), (max-width: 860px) {
      .airplay-play-pause-wrap {
        gap: clamp(12px, 2.5vmin, 22px);
      }

      .airplay-skip-button {
        width: clamp(42px, 7vmin, 58px);
        font-size: clamp(1.05rem, 3vmin, 1.55rem);
      }
    }
  `;
  document.head.appendChild(style);

  function makeButton(id, label, text, action) {
    const button = document.createElement('button');
    button.id = id;
    button.type = 'button';
    button.className = 'airplay-skip-button';
    button.setAttribute('aria-label', label);
    button.dataset.airplayAction = action;
    button.textContent = text;
    button.disabled = playButton.disabled;
    return button;
  }

  const backButton = makeButton('airplay-skip-back', 'Previous AirPlay item', '⏮', 'previous');
  const forwardButton = makeButton('airplay-skip-forward', 'Next AirPlay item', '⏭', 'next');

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