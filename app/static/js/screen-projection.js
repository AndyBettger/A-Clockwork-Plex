(() => {
  if (window.__aClockworkPlexScreenProjectionLoaded) return;
  window.__aClockworkPlexScreenProjectionLoaded = true;

  const routes = {
    alarm: '/alarm',
    airplay: '/airplay',
    clock: '/clock',
    plexamp: '/plexamp',
    settings: '/settings',
    weather: '/weather',
  };
  const shell = document.getElementById('persistent-plexamp');
  const frame = document.getElementById('persistent-plexamp-frame');

  let checking = false;
  let applying = false;
  let posting = false;
  let lastPostAt = 0;
  let modeGuardUntil = 0;
  let state = null;
  let observedPlexampOpen = false;

  function currentSurface() {
    if (window.ACPPlexamp?.isOpen?.()) return 'plexamp';
    return String(document.body.dataset.activePage || 'clock').trim().toLowerCase();
  }

  function idleReturnMode() {
    return window.ACPDashboardPreferences?.read?.().idleReturnMode
      || document.documentElement.dataset.idleReturnMode
      || document.body.dataset.defaultMode
      || 'clock';
  }

  async function post(action, options = {}) {
    if (posting && action !== 'apply') return null;
    if (action !== 'apply') posting = true;
    try {
      const response = await fetch('/api/screen/state', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          surface: options.surface || currentSurface(),
          source: options.source || 'screen-projection-client',
          idle_return_mode: idleReturnMode(),
        }),
      });
      if (!response.ok) return null;
      const payload = await response.json();
      if (payload?.screen) state = payload.screen;
      return payload?.screen || null;
    } catch (error) {
      return null;
    } finally {
      if (action !== 'apply') posting = false;
    }
  }

  function markActivity(source, options = {}) {
    const now = Date.now();
    const force = options.force === true;
    const surface = options.surface || currentSurface();
    if (!force && now - lastPostAt < 1000) return;
    lastPostAt = now;
    post(options.manual === true ? 'open' : 'interaction', {
      surface,
      source,
    });
  }

  function navigate(target) {
    const route = routes[target];
    if (!route) return;
    if (target === 'plexamp' && window.ACPPlexamp) {
      window.ACPPlexamp.show({ updateMode: false });
      return;
    }
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, {
        updateMode: false,
        automatic: true,
        source: 'screen-projection',
      });
    } else {
      window.location.assign(route);
    }
  }

  async function applyProjection(snapshot) {
    if (applying || !snapshot?.should_apply) return;
    const target = String(snapshot.recommended_screen || '').toLowerCase();
    if (!(target in routes)) return;
    if (target === 'alarm') {
      if (window.location.pathname !== routes.alarm) {
        modeGuardUntil = Date.now() + 6000;
        navigate('alarm');
      }
      return;
    }
    applying = true;
    modeGuardUntil = Date.now() + 6000;
    try {
      const applied = await post('apply', { source: 'screen-projection-apply' });
      const appliedTarget = String(applied?.applied_screen || applied?.recommended_screen || target).toLowerCase();
      navigate(appliedTarget);
    } finally {
      window.setTimeout(() => {
        applying = false;
        modeGuardUntil = Date.now() + 1200;
      }, 500);
    }
  }

  async function check() {
    if (checking || applying || window.ACPNavigationState?.isLeaving?.()) return;
    checking = true;
    try {
      const response = await fetch('/api/screen/state', { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      state = payload?.screen || null;
      if (!state) return;
      document.documentElement.dataset.screenProjectionReason = String(state.decision_reason || 'unknown');
      document.documentElement.dataset.screenLeaseActive = state?.lease?.active === true ? 'true' : 'false';
      document.documentElement.dataset.screenInputAuthority = String(
        state?.input_activity?.authority || 'browser-fallback',
      );
      await applyProjection(state);
    } catch (error) {
    } finally {
      checking = false;
    }
  }

  ['pointerdown', 'touchstart', 'keydown', 'wheel', 'input'].forEach((eventName) => {
    window.addEventListener(eventName, () => markActivity(`outer-${eventName}`), {
      passive: true,
      capture: true,
    });
  });

  window.addEventListener('acp:manual-screen-open', (event) => {
    const surface = String(event?.detail?.surface || 'plexamp').toLowerCase();
    markActivity(String(event?.detail?.source || 'manual-screen-open'), {
      force: true,
      manual: true,
      surface,
    });
  });

  window.addEventListener('acp:dashboard-preferences-changed', () => {
    post('preferences', { source: 'dashboard-preferences-changed' });
  });

  if (frame) {
    frame.addEventListener('pointerenter', () => {
      markActivity('plexamp-frame-pointerenter', { force: true, surface: 'plexamp' });
    });
    frame.addEventListener('focus', () => {
      markActivity('plexamp-frame-focus', { force: true, surface: 'plexamp' });
    });
    window.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (document.activeElement === frame) {
          markActivity('plexamp-frame-window-focus', { force: true, surface: 'plexamp' });
        }
      }, 0);
    });
  }

  if (shell) {
    const observeOpenState = () => {
      const open = shell.classList.contains('is-open') && shell.getAttribute('aria-hidden') !== 'true';
      if (open && !observedPlexampOpen) {
        observedPlexampOpen = true;
        markActivity('plexamp-surface-opened', { force: true, manual: true, surface: 'plexamp' });
      } else if (!open) {
        observedPlexampOpen = false;
      }
    };
    new MutationObserver(observeOpenState).observe(shell, {
      attributes: true,
      attributeFilter: ['class', 'aria-hidden'],
    });
    observeOpenState();
  }

  window.ACPScreenProjection = {
    markActivity,
    state: () => state,
    shouldDeferModeSync: () => applying || Date.now() < modeGuardUntil,
    inputAuthority: () => state?.input_activity?.authority || 'browser-fallback',
  };

  async function initialise() {
    const surface = currentSurface();
    const explicitNavigation = window.ACPNavigationState?.consumeExplicitNavigation?.(
      window.location.pathname,
    );
    const shouldOpenLease = Boolean(explicitNavigation) || surface === 'settings';

    if (shouldOpenLease && surface !== 'alarm') {
      modeGuardUntil = Date.now() + 4000;
      await post('preferences', { source: 'screen-projection-start' });
      lastPostAt = Date.now();
      await post('open', {
        surface,
        source: explicitNavigation
          ? `explicit-navigation-arrival:${explicitNavigation.source || 'navigation'}`
          : 'initial-settings-surface',
      });
      return;
    }

    await post('preferences', { source: 'screen-projection-start' });
    if (surface === 'plexamp') {
      markActivity('initial-plexamp-surface', { force: true, manual: true, surface: 'plexamp' });
    }
  }

  initialise();
  window.setInterval(check, 2000);
  window.setTimeout(check, 700);
})();
