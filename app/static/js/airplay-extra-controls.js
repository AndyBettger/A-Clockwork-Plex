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
      font-family: "Segoe UI Symbol", "Noto Sans Symbols 2", "Apple Symbols", system-ui, sans-serif;
      font-size: clamp(1.35rem, 3.6vmin, 2.1rem);
      font-weight: 900;
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

    .airplay-skip-glyph {
      display: block;
      transform: translateY(-0.03em);
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
        font-size: clamp(1.08rem, 3.1vmin, 1.55rem);
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

    const glyph = document.createElement('span');
    glyph.className = 'airplay-skip-glyph';
    glyph.setAttribute('aria-hidden', 'true');
    glyph.textContent = text;
    button.appendChild(glyph);

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
