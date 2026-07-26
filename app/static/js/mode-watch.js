(() => {
  const activePage = document.body.dataset.activePage;
  const modeRoutes = {
    clock: '/clock',
    weather: '/weather',
    plexamp: '/plexamp',
    airplay: '/airplay',
    settings: '/settings',
  };

  let statusUnavailable = false;
  let plexampRecoveryTimer = null;
  let plexampRecoveryGeneration = 0;

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

  async function plexampPlayerReady() {
    try {
      const response = await fetch('/api/audio/live', { cache: 'no-store' });
      if (!response.ok) return false;
      const payload = await response.json();
      return payload?.live?.channels?.plexamp?.available === true;
    } catch (error) {
      return false;
    }
  }

  function reloadPlexampFrame(generation) {
    if (generation !== plexampRecoveryGeneration) return;
    const frame = document.getElementById('persistent-plexamp-frame');
    if (!frame) return;

    const source = frame.getAttribute('src');
    if (!source) return;
    const target = new URL(source, window.location.href);
    target.searchParams.set('acp_reconnect', String(Date.now()));

    document.getElementById('persistent-plexamp')?.classList.remove('is-ready');
    frame.setAttribute('src', 'about:blank');
    plexampRecoveryTimer = window.setTimeout(() => {
      if (generation !== plexampRecoveryGeneration) return;
      frame.setAttribute('src', target.toString());
    }, 150);
  }

  function schedulePlexampFrameRecovery() {
    const generation = ++plexampRecoveryGeneration;
    const startedAt = Date.now();
    window.clearTimeout(plexampRecoveryTimer);

    const poll = async () => {
      if (generation !== plexampRecoveryGeneration) return;
      if (await plexampPlayerReady()) {
        plexampRecoveryTimer = window.setTimeout(
          () => reloadPlexampFrame(generation),
          750,
        );
        return;
      }
      if (Date.now() - startedAt >= 60000) return;
      plexampRecoveryTimer = window.setTimeout(poll, 1000);
    };

    plexampRecoveryTimer = window.setTimeout(poll, 500);
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
      if (!response.ok) {
        statusUnavailable = true;
        return;
      }

      const recoveredFromOutage = statusUnavailable;
      statusUnavailable = false;
      if (recoveredFromOutage) schedulePlexampFrameRecovery();

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
      const airplayActive = status?.state?.airplay?.active === true;

      /* Shairport's session-end hook returns AirPlay to Clock. If Plexamp has
         already won that completed handoff and is visibly playing, preserve the
         newer user choice and repair the stale Clock mode. Never do this while an
         AirPlay session is active: playback state can lag briefly during START. */
      if (
        window.ACPPlexamp?.isOpen?.()
        && plexampIsPlaying()
        && requestedMode === 'clock'
        && !airplayActive
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
      statusUnavailable = true;
    }
  }

  window.addEventListener('pagehide', () => {
    ++plexampRecoveryGeneration;
    window.clearTimeout(plexampRecoveryTimer);
  });
  window.setInterval(checkMode, 2000);
  window.setTimeout(checkMode, 500);
})();
