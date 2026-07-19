(() => {
  const activePage = document.body.dataset.activePage;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    plexamp: '/plexamp',
    airplay: '/airplay',
    settings: '/settings',
  };

  async function checkMode() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }

      const status = await response.json();
      const alarmScreenRequired = Boolean(status?.alarm_scheduler?.screen_required);
      if (alarmScreenRequired && window.location.pathname !== '/alarm') {
        try {
          const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
          window.sessionStorage.setItem('alarmReturnPath', currentPath || '/clock');
        } catch (error) {
          // Session storage is a convenience; /clock remains the safe fallback.
        }
        window.location.assign('/alarm');
        return;
      }

      if (!activePage || !(activePage in modeRoutes)) {
        return;
      }

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
