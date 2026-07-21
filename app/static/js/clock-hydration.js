(() => {
  if (window.__aClockworkPlexClockHydrationLoaded) return;
  window.__aClockworkPlexClockHydrationLoaded = true;

  const weatherContent = document.getElementById('clock-weather-content');
  let signalled = false;
  let fallbackTimer = null;
  let observer = null;

  function nextFrame() {
    return new Promise((resolve) => window.requestAnimationFrame(resolve));
  }

  async function signalReady() {
    if (signalled) return;
    signalled = true;
    window.clearTimeout(fallbackTimer);
    observer?.disconnect();

    try {
      await document.fonts?.ready;
    } catch (error) {
    }

    /* The first frame commits the rebuilt composite cards. The second lets the
       browser resolve their final grid, segment sizes and font metrics. */
    await nextFrame();
    await nextFrame();
    window.setTimeout(() => {
      window.dispatchEvent(new CustomEvent('acp:page-hydrated', {
        detail: { page: 'clock' },
      }));
    }, 24);
  }

  if (weatherContent && typeof MutationObserver === 'function') {
    observer = new MutationObserver((mutations) => {
      const rebuilt = mutations.some((mutation) => mutation.type === 'childList');
      if (rebuilt) signalReady();
    });
    observer.observe(weatherContent, { childList: true, subtree: true });
  } else {
    signalReady();
  }

  /* A failed or unusually slow status request must never leave Clock hidden.
     The fallback is deliberately longer than a normal local API round trip. */
  fallbackTimer = window.setTimeout(signalReady, 1800);
})();
