(() => {
  if (window.__aClockworkPlexAirPlayHydrationLoaded) return;
  window.__aClockworkPlexAirPlayHydrationLoaded = true;

  let cycle = 0;
  let observer = null;
  let fallbackTimer = null;

  function rendered() {
    return !document.body.classList.contains('airplay-session-unresolved')
      && (
        document.body.classList.contains('airplay-session-idle')
        || document.body.classList.contains('airplay-session-active')
        || document.body.classList.contains('airplay-metadata-active')
      );
  }

  function stopWatching() {
    observer?.disconnect();
    observer = null;
    window.clearTimeout(fallbackTimer);
    fallbackTimer = null;
  }

  function signalReady(id) {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      if (id !== cycle) return;
      window.dispatchEvent(new CustomEvent('acp:page-hydrated', {
        detail: { surface: 'airplay' },
      }));
    }));
  }

  function settleCycle(timeoutMs = 1100) {
    const id = ++cycle;
    stopWatching();

    if (rendered()) {
      signalReady(id);
      return;
    }

    observer = new MutationObserver(() => {
      if (!rendered() || id !== cycle) return;
      stopWatching();
      signalReady(id);
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class'],
    });

    fallbackTimer = window.setTimeout(() => {
      if (id !== cycle) return;
      stopWatching();
      signalReady(id);
    }, timeoutMs);
  }

  function waitForReady(timeoutMs = 1400) {
    return new Promise((resolve) => {
      let resolved = false;
      let timer = null;
      const done = () => {
        if (resolved) return;
        resolved = true;
        window.clearTimeout(timer);
        window.removeEventListener('acp:page-hydrated', onHydrated);
        resolve();
      };
      const onHydrated = (event) => {
        if (String(event?.detail?.surface || '').toLowerCase() !== 'airplay') return;
        done();
      };

      window.addEventListener('acp:page-hydrated', onHydrated);
      timer = window.setTimeout(done, Math.max(200, Number(timeoutMs) || 1400));
      settleCycle(Math.max(200, Number(timeoutMs) || 1400));
    });
  }

  window.ACPAirPlayHydration = Object.freeze({
    waitForReady,
    settle: settleCycle,
  });

  if (String(document.body?.dataset?.activePage || '').toLowerCase() === 'airplay') {
    settleCycle();
  }
})();
