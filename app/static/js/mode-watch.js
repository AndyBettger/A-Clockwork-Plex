(() => {
  const activePage = document.body.dataset.activePage;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    plexamp: '/plexamp',
    airplay: '/airplay',
    settings: '/settings',
  };

  if (!activePage || !(activePage in modeRoutes)) {
    return;
  }

  async function checkMode() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }

      const status = await response.json();
      const requestedMode = status?.state?.mode;
      const route = modeRoutes[requestedMode];

      if (route && requestedMode !== activePage && window.location.pathname !== route) {
        window.location.assign(route);
      }
    } catch (error) {
      // The dashboard should remain usable even if a transient status check fails.
    }
  }

  window.setInterval(checkMode, 2000);
  window.setTimeout(checkMode, 500);
})();
