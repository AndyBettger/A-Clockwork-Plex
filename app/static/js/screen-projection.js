(() => {
  if (window.__aClockworkPlexScreenProjectionLoaded) return;
  window.__aClockworkPlexScreenProjectionLoaded = true;

  const timeoutSeconds = Math.max(5, Number(document.body.dataset.idleTimeoutSeconds || 180));
  const timeoutMs = timeoutSeconds * 1000;
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
  let frameEngaged = false;
  let idleDetector = null;
  let idlePermissionAttempted = false;
  let idleUserState = 'unknown';
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

  async function ensureIdleDetector() {
    if (idlePermissionAttempted || idleDetector || !('IdleDetector' in window)) return;
    if (navigator.userActivation?.isActive !== true) {
      idleUserState = 'awaiting-user-gesture';
      return;
    }
    idlePermissionAttempted = true;
    try {
      const permission = await window.IdleDetector.requestPermission();
      if (permission !== 'granted') {
        idleUserState = 'permission-denied';
        return;
      }
      idleDetector = new window.IdleDetector();
      idleDetector.addEventListener('change', () => {
        idleUserState = String(idleDetector.userState || 'unknown');
        if (idleUserState === 'active' && currentSurface() === 'plexamp' && frameEngaged) {
          markActivity('idle-detector-active', { force: true, surface: 'plexamp' });
        }
      });
      await idleDetector.start({ threshold: Math.max(60000, timeoutMs) });
      idleUserState = String(idleDetector.userState || 'active');
    } catch (error) {
      idlePermissionAttempted = false;
      idleUserState = 'unavailable';
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
    if (surface === 'plexamp') ensureIdleDetector();
  }

  function navigate(target) {
    const route = routes[target];
    if (!route) return;
    if (target === 'plexamp' && window.ACPPlexamp) {
      window.ACPPlexamp.show({ updateMode: false });
      return;
    }
    if (typeof window.ACPNavigate === 'function') {
      window.ACPNavigate(route, { updateMode: false });
    } else {
      window.location.assign(route);
    }
  }

  async function applyProjection(snapshot) {
    if (applying || !snapshot?.should_apply) return;
    const target = String(snapshot.recommended_screen || '').toLowerCase();
    if (!(target in routes)) return;
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
      document.documentElement.dataset.plexampIdleDetection = idleUserState;
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
      manual: surface === 'plexamp',
      surface,
    });
  });

  window.addEventListener('acp:dashboard-preferences-changed', () => {
    post('preferences', { source: 'dashboard-preferences-changed' });
  });

  if (frame) {
    frame.addEventListener('pointerenter', () => {
      frameEngaged = true;
      markActivity('plexamp-frame-pointerenter', { force: true, surface: 'plexamp' });
    });
    frame.addEventListener('pointerleave', () => {
      frameEngaged = false;
    });
    frame.addEventListener('focus', () => {
      frameEngaged = true;
      markActivity('plexamp-frame-focus', { force: true, surface: 'plexamp' });
    });
    window.addEventListener('blur', () => {
      window.setTimeout(() => {
        if (document.activeElement === frame) {
          frameEngaged = true;
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
        frameEngaged = false;
      }
    };
    new MutationObserver(observeOpenState).observe(shell, {
      attributes: true,
      attributeFilter: ['class', 'aria-hidden'],
    });
    observeOpenState();
  }

  const heartbeatMs = Math.min(30000, Math.max(5000, Math.round(timeoutMs / 4)));
  window.setInterval(() => {
    if (
      currentSurface() === 'plexamp'
      && frameEngaged
      && idleDetector
      && idleUserState === 'active'
    ) {
      markActivity('plexamp-frame-active-heartbeat', { force: true, surface: 'plexamp' });
    }
  }, heartbeatMs);

  window.ACPScreenProjection = {
    markActivity,
    state: () => state,
    shouldDeferModeSync: () => applying || Date.now() < modeGuardUntil,
    idleDetectorState: () => idleUserState,
  };

  post('preferences', { source: 'screen-projection-start' });
  window.setTimeout(() => {
    if (currentSurface() === 'plexamp') {
      markActivity('initial-plexamp-surface', { force: true, manual: true, surface: 'plexamp' });
    }
  }, 100);
  window.setInterval(check, 2000);
  window.setTimeout(check, 700);
})();
