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
  const frame = document.getElementById('persistent-plexamp-frame');

  let checking = false;
  let applying = false;
  let lastPostAt = 0;
  let modeGuardUntil = 0;
  let state = null;
  let queuedNonApplyPosts = 0;
  let postTail = Promise.resolve();

  function plexampVisiblyOpen() {
    if (typeof window.ACPPlexamp?.isVisiblyOpen === 'function') {
      return window.ACPPlexamp.isVisiblyOpen();
    }
    return Boolean(window.ACPPlexamp?.isOpen?.());
  }

  function currentSurface() {
    if (plexampVisiblyOpen()) return 'plexamp';
    return String(document.body.dataset.activePage || 'clock').trim().toLowerCase();
  }

  function idleReturnMode() {
    return window.ACPDashboardPreferences?.read?.().idleReturnMode
      || document.documentElement.dataset.idleReturnMode
      || document.body.dataset.defaultMode
      || 'clock';
  }

  async function performPost(action, options = {}) {
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
    }
  }

  function post(action, options = {}) {
    if (action === 'apply') return performPost(action, options);

    const guaranteed = action === 'open' || options.guaranteed === true;
    if (!guaranteed && queuedNonApplyPosts > 0) return Promise.resolve(null);

    queuedNonApplyPosts += 1;
    const task = postTail
      .catch(() => null)
      .then(() => performPost(action, options));
    postTail = task.catch(() => null);
    return task.finally(() => {
      queuedNonApplyPosts = Math.max(0, queuedNonApplyPosts - 1);
    });
  }

  async function openSurface(surface, source = 'manual-screen-open') {
    const target = String(surface || '').trim().toLowerCase();
    if (!(target in routes) || target === 'alarm') return null;
    modeGuardUntil = Date.now() + 5000;
    lastPostAt = Date.now();
    return post('open', {
      surface: target,
      source,
      guaranteed: true,
    });
  }

  function markActivity(source, options = {}) {
    const now = Date.now();
    const force = options.force === true;
    const surface = options.surface || currentSurface();
    if (!force && now - lastPostAt < 1000) return Promise.resolve(null);
    lastPostAt = now;
    if (options.manual === true) {
      return openSurface(surface, source);
    }
    return post('interaction', {
      surface,
      source,
    });
  }

  function navigate(target) {
    const route = routes[target];
    if (!route) return;
    if (target === 'plexamp' && window.ACPPlexamp) {
      window.ACPPlexamp.show({
        updateMode: false,
        manual: false,
        source: 'screen-projection',
      });
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

  function reconcilePlexampVisual(snapshot) {
    const current = String(snapshot?.current_screen || '').toLowerCase();
    const recommended = String(snapshot?.recommended_screen || '').toLowerCase();
    if (current !== 'plexamp' || recommended !== 'plexamp') return;
    if (plexampVisiblyOpen()) return;
    window.ACPPlexamp?.ensureVisible?.({ source: 'screen-projection-state-repair' });
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
      reconcilePlexampVisual(state);
      await applyProjection(state);
    } catch (error) {
    } finally {
      checking = false;
    }
  }

  function isNavigationGesture(event) {
    return Boolean(event?.target?.closest?.('.main-nav a[href], a[data-page-transition]'));
  }

  function anotherSurfaceOwnsLease() {
    const lease = state?.lease || {};
    return lease.active === true
      && Boolean(lease.manual_surface)
      && String(lease.manual_surface).toLowerCase() !== 'plexamp';
  }

  function plexampActivityAllowed() {
    return !anotherSurfaceOwnsLease() && plexampVisiblyOpen();
  }

  ['pointerdown', 'touchstart', 'keydown', 'wheel', 'input'].forEach((eventName) => {
    window.addEventListener(eventName, (event) => {
      if (isNavigationGesture(event)) return;
      markActivity(`outer-${eventName}`);
    }, {
      passive: true,
      capture: true,
    });
  });

  window.addEventListener('acp:manual-screen-open', (event) => {
    const surface = String(event?.detail?.surface || 'plexamp').toLowerCase();
    openSurface(
      surface,
      String(event?.detail?.source || 'manual-screen-open'),
    );
  });

  window.addEventListener('acp:dashboard-preferences-changed', () => {
    post('preferences', { source: 'dashboard-preferences-changed' });
  });

  if (frame) {
    frame.addEventListener('pointerenter', () => {
      if (!plexampActivityAllowed()) return;
      markActivity('plexamp-frame-pointerenter', { force: true, surface: 'plexamp' });
    });
    frame.addEventListener('focus', () => {
      if (!plexampActivityAllowed()) return;
      markActivity('plexamp-frame-focus', { force: true, surface: 'plexamp' });
    });
    window.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (document.activeElement === frame && plexampActivityAllowed()) {
          markActivity('plexamp-frame-window-focus', { force: true, surface: 'plexamp' });
        }
      }, 0);
    });
  }

  window.ACPScreenProjection = {
    markActivity,
    openSurface,
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

    await post('preferences', { source: 'screen-projection-start' });
    if (shouldOpenLease && surface !== 'alarm') {
      await openSurface(
        surface,
        explicitNavigation
          ? `explicit-navigation-arrival:${explicitNavigation.source || 'navigation'}`
          : 'initial-settings-surface',
      );
    }
  }

  initialise().finally(() => {
    window.setInterval(check, 2000);
    window.setTimeout(check, 700);
  });
})();
