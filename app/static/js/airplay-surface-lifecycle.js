(() => {
  if (window.__aClockworkPlexAirPlaySurfaceLifecycleLoaded) return;
  window.__aClockworkPlexAirPlaySurfaceLifecycleLoaded = true;

  const subscribers = new Set();

  function isVisible() {
    const active = String(document.body?.dataset?.activePage || '').toLowerCase() === 'airplay';
    const plexampOpen = window.ACPPlexamp?.isVisiblyOpen?.() === true;
    return active && !document.hidden && !plexampOpen;
  }

  function publish() {
    const visible = isVisible();
    for (const subscriber of subscribers) {
      try {
        subscriber(visible);
      } catch (error) {
      }
    }
  }

  function subscribe(subscriber) {
    if (typeof subscriber !== 'function') return () => {};
    subscribers.add(subscriber);
    return () => subscribers.delete(subscriber);
  }

  document.addEventListener('acp:surface-activated', publish);
  document.addEventListener('visibilitychange', publish);
  document.addEventListener('acp:surface-settled', (event) => {
    if (String(event?.detail?.surface || '').toLowerCase() === 'airplay') publish();
  });

  window.ACPAirPlaySurfaceLifecycle = Object.freeze({
    isVisible,
    subscribe,
    publish,
  });
})();
