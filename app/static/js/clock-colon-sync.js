(() => {
  const clock = document.getElementById('clock-time');
  if (!clock) return;

  function displayedSecond() {
    const label = String(clock.getAttribute('aria-label') || '');
    const match = label.match(/:(\d{2})(?:\s+(?:AM|PM))?$/i);
    if (!match) return null;
    const second = Number(match[1]);
    return Number.isInteger(second) && second >= 0 && second <= 59 ? second : null;
  }

  function paint() {
    const second = displayedSecond();
    if (second === null) return;
    clock.classList.toggle('is-colon-off', second % 2 === 1);
  }

  const observer = new MutationObserver((mutations) => {
    if (mutations.some((mutation) => mutation.type === 'attributes' && mutation.attributeName === 'aria-label')) {
      paint();
    }
  });

  observer.observe(clock, { attributes: true, attributeFilter: ['aria-label'] });
  paint();

  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
})();
