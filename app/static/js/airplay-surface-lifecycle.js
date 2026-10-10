(() => {
  if (window.__aClockworkPlexAirPlaySurfaceLifecycleLoaded) return;
  window.__aClockworkPlexAirPlaySurfaceLifecycleLoaded = true;

  const subscribers = new Set();
  let lastVisible = null;

  function isVisible() {
    const active = String(document.body?.dataset?.activePage || '').toLowerCase() === 'airplay';
    const plexampOpen = window.ACPPlexamp?.isVisiblyOpen?.() === true;
    return active && !document.hidden && !plexampOpen;
  }

  function publish({ force = false } = {}) {
    const visible = isVisible();
    if (!force && visible === lastVisible) return;
    lastVisible = visible;
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

  if (typeof MutationObserver === 'function' && document.body) {
    new MutationObserver(() => publish()).observe(document.body, {
      attributes: true,
      attributeFilter: ['class', 'data-active-page'],
    });
  }

  lastVisible = isVisible();

  window.ACPAirPlaySurfaceLifecycle = Object.freeze({
    isVisible,
    subscribe,
    publish,
  });
})();
