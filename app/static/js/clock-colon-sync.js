(() => {
  if (window.__aClockworkPlexClockColonSyncLoaded) return;
  window.__aClockworkPlexClockColonSyncLoaded = true;

  const clock = document.getElementById('clock-time');
  if (!clock) return;

  let timer = null;

  function update() {
    const now = new Date();
    clock.classList.toggle('is-colon-off', now.getSeconds() % 2 === 1);

    // Re-align every tick to the next wall-clock second boundary rather than
    // allowing a free-running interval to drift away from the displayed time.
    const delay = Math.max(20, 1000 - (Date.now() % 1000) + 8);
    timer = window.setTimeout(update, delay);
  }

  update();

  window.addEventListener('pagehide', () => {
    if (timer) window.clearTimeout(timer);
  }, { once: true });
})();
