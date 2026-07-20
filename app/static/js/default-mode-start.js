(() => {
  if (window.__aClockworkPlexDefaultModeStartLoaded) return;
  window.__aClockworkPlexDefaultModeStartLoaded = true;

  const routes = {
    clock: '/clock',
    weather: '/weather',
    airplay: '/airplay',
    plexamp: '/plexamp',
  };
  const activePage = String(document.body.dataset.activePage || '').toLowerCase();
  const defaultMode = String(document.body.dataset.defaultMode || 'clock').toLowerCase();
  if (activePage !== 'clock' || !(defaultMode in routes) || defaultMode === 'clock') return;

  const markerKey = 'a-clockwork-plex.explicit-navigation';
  let explicitClockVisit = false;
  try {
    const marker = JSON.parse(window.sessionStorage.getItem(markerKey) || 'null');
    window.sessionStorage.removeItem(markerKey);
    explicitClockVisit = Boolean(
      marker
      && marker.path === window.location.pathname
      && Date.now() - Number(marker.at || 0) < 8000
    );
  } catch (error) {
  }
  if (explicitClockVisit) return;

  let cancelledByUser = false;
  const cancel = () => { cancelledByUser = true; };
  ['pointerdown', 'touchstart', 'keydown', 'wheel'].forEach((eventName) => {
    window.addEventListener(eventName, cancel, { capture: true, passive: true, once: true });
  });

  window.setTimeout(async () => {
    if (cancelledByUser) return;
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (response.ok) {
        const status = await response.json();
        if (status?.alarm_scheduler?.screen_required) return;
      }
      await fetch(`/api/mode/${defaultMode}`, { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }

    const route = routes[defaultMode];
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, { updateMode: false });
    } else {
      window.location.assign(route);
    }
  }, 320);
})();
