(() => {
  const activePage = document.body.dataset.activePage;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    plexamp: '/plexamp',
    airplay: '/airplay',
    settings: '/settings',
  };

  const navigate = (route, immediate = false, updateMode = true) => {
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, { immediate, updateMode });
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
        navigate('/alarm', true, false);
        return;
      }

      if (!activePage || !(activePage in modeRoutes)) return;
      const requestedMode = status?.state?.mode;
      const route = modeRoutes[requestedMode];
      if (!route) return;

      if (requestedMode === 'plexamp' && window.ACPPlexamp) {
        if (!window.ACPPlexamp.isOpen()) window.ACPPlexamp.show({ updateMode: false });
        return;
      }

      if (window.ACPPlexamp?.isOpen?.()) {
        if (requestedMode === activePage) {
          window.ACPPlexamp.hide();
          return;
        }
        navigate(route, false, false);
        return;
      }

      if (requestedMode !== activePage && window.location.pathname !== route) {
        navigate(route, false, false);
      }
    } catch (error) {
    }
  }

  window.setInterval(checkMode, 2000);
  window.setTimeout(checkMode, 500);
})();
