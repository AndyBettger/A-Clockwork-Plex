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

  function plexampIsPlaying() {
    const live = window.ACPLiveAudioSnapshot?.live || {};
    const state = String(live?.channels?.plexamp?.playback_state || '').toLowerCase();
    return state === 'playing';
  }

  async function reassertPlexampMode() {
    try {
      await fetch('/api/mode/plexamp', {
        method: 'POST',
        cache: 'no-store',
      });
    } catch (error) {
    }
  }

  async function checkMode() {
    try {
      if (window.ACPNavigationState?.isLeaving?.()) return;

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

      /* Shairport's session-end hook returns AirPlay to Clock. If Plexamp has
         already won the handoff and is visibly playing, preserve the newer user
         choice and repair the server mode instead of closing the Plexamp layer. */
      if (
        window.ACPPlexamp?.isOpen?.()
        && plexampIsPlaying()
        && requestedMode !== 'plexamp'
      ) {
        await reassertPlexampMode();
        return;
      }

      /* Local Plexamp show/hide operations update mode asynchronously. Ignore the
         stale status response while that transaction or its animation is active,
         otherwise the watcher can close and reopen the overlay mid-transition. */
      if (window.ACPPlexamp?.shouldDeferModeSync?.(requestedMode, activePage)) {
        return;
      }

      if (requestedMode === 'plexamp' && window.ACPPlexamp) {
        if (!window.ACPPlexamp.isOpen()) {
          window.ACPPlexamp.show({ updateMode: false });
        }
        return;
      }

      if (window.ACPPlexamp?.isOpen?.()) {
        if (requestedMode === activePage) {
          window.ACPPlexamp.hide({ updateMode: false, targetMode: activePage });
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
