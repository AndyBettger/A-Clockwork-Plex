(() => {
  const activePage = document.body.dataset.activePage;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    plexamp: '/plexamp',
    airplay: '/airplay',
    settings: '/settings',
  };

  const navigate = (route, immediate = false) => {
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, { immediate });
    } else {
      window.location.assign(route);
    }
  };

  async function checkMode() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) return;

      const status = await response.json();
      const alarmScreenRequired = Boolean(status?.alarm_scheduler?.screen_required);
      if (alarmScreenRequired && window.location.pathname !== '/alarm') {
        try {
          const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
          window.sessionStorage.setItem('alarmReturnPath', currentPath || '/clock');
        } catch (error) {
        }
        navigate('/alarm', true);
        return;
      }

      if (!activePage || !(activePage in modeRoutes)) return;
      const requestedMode = status?.state?.mode;
      const route = modeRoutes[requestedMode];
      if (route && requestedMode !== activePage && window.location.pathname !== route) {
        navigate(route);
      }
    } catch (error) {
    }
  }

  window.setInterval(checkMode, 2000);
  window.setTimeout(checkMode, 500);
})();
