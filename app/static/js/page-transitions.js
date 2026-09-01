(() => {
  if (window.__aClockworkPlexPageTransitionsLoaded) return;
  window.__aClockworkPlexPageTransitionsLoaded = true;

  let leaving = false;
  let revealed = false;
  let readyTimer = null;
  let manualClaimInFlight = false;
  let presentationInFlight = false;
  let presentationTimer = null;
  const explicitNavigationKey = 'a-clockwork-plex.explicit-navigation';
  const explicitNavigationMaxAgeMs = 15000;
  const leasableRoutes = new Set(['/airplay', '/clock', '/news', '/plexamp', '/settings', '/weather']);

  function sameOriginTarget(url) {
    try {
      const target = new URL(url, window.location.href);
      return target.origin === window.location.origin ? target : null;
    } catch (error) {
      return null;
    }
  }

  function preferences() {
    return window.ACPDashboardPreferences?.read?.() || {
      transitionStyle: document.documentElement.dataset.transitionStyle || 'grow-fade',
      transitionDurationMs: Number(document.documentElement.dataset.transitionDurationMs || 300),
    };
  }

  function activeRoute() {
    const page = String(document.body.dataset.activePage || '').trim().toLowerCase();
    return page ? `/${page}` : window.location.pathname;
  }

  function plexampVisiblyOpen() {
    return Boolean(
      window.ACPPlexamp?.isVisiblyOpen?.()
      ?? window.ACPPlexamp?.isOpen?.(),
    );
  }

  function isAutomaticNavigation(options = {}) {
    return options.automatic === true || options.source === 'screen-projection';
  }

  function preserveNightInteraction(options = {}) {
    if (isAutomaticNavigation(options)) return;
    window.ACPDisplayDimming?.interact?.(undefined, 'dashboard-navigation');
  }

  function rememberNavigation(target, options = {}) {
    if (isAutomaticNavigation(options) || !leasableRoutes.has(target.pathname)) return;
    try {
      window.sessionStorage.setItem(explicitNavigationKey, JSON.stringify({
        path: target.pathname,
        at: Date.now(),
        source: String(options.source || 'explicit-navigation'),
      }));
    } catch (error) {
    }
  }

  function consumeExplicitNavigation(path = window.location.pathname) {
    try {
      const raw = window.sessionStorage.getItem(explicitNavigationKey);
      if (!raw) return null;
      const value = JSON.parse(raw);
      const age = Date.now() - Number(value?.at || 0);
      if (age < 0 || age > explicitNavigationMaxAgeMs) {
        window.sessionStorage.removeItem(explicitNavigationKey);
        return null;
      }
      if (String(value?.path || '') !== String(path || '')) return null;
      window.sessionStorage.removeItem(explicitNavigationKey);
      return value;
    } catch (error) {
      try { window.sessionStorage.removeItem(explicitNavigationKey); } catch (ignored) {}
      return null;
    }
  }

  async function claimManualSurface(target, options = {}) {
    if (isAutomaticNavigation(options) || !leasableRoutes.has(target.pathname)) return true;
    const surface = target.pathname.slice(1) || 'clock';
    if (typeof window.ACPScreenProjection?.openSurface !== 'function') {
      rememberNavigation(target, options);
      return true;
    }

    const accepted = await window.ACPScreenProjection.openSurface(
      surface,
      String(options.source || 'navigation-link'),
    );
    if (!accepted) {
      rememberNavigation(target, options);
      return true;
    }
    if (accepted.recommended_screen === 'alarm' && surface !== 'alarm') {
      return false;
    }
    return accepted?.lease?.active === true
      && String(accepted?.lease?.manual_surface || '').toLowerCase() === surface;
  }

  function revealPage() {
    if (revealed) return;
    revealed = true;
    document.documentElement.classList.remove('acp-document-booting');
    document.body.classList.remove('acp-page-booting');
    document.body.classList.add('acp-page-ready');

    const current = preferences();
    const duration = current.transitionStyle === 'none'
      ? 0
      : Math.max(0, Math.min(1500, Number(current.transitionDurationMs) || 0));
    window.clearTimeout(readyTimer);
    readyTimer = window.setTimeout(() => {
      document.body.classList.remove('acp-page-ready');
    }, Math.max(30, Math.round(duration * 0.64) + 50));
  }

  function scheduleReveal() {
    const activePage = String(document.body.dataset.activePage || '').toLowerCase();
    const hydratedFallbacks = {
      airplay: 1500,
      clock: 900,
    };

    if (activePage in hydratedFallbacks) {
      window.addEventListener('acp:page-hydrated', revealPage, { once: true });
      window.setTimeout(revealPage, hydratedFallbacks[activePage]);
      return;
    }

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => window.setTimeout(revealPage, 35));
    });
  }

  function outgoingDelay() {
    const current = preferences();
    const duration = Math.max(0, Math.min(1500, Number(current.transitionDurationMs) || 0));
    if (current.transitionStyle === 'none' || duration <= 0) return 0;
    return Math.round(duration * 0.36);
  }

  function holdPresentation(duration = 0) {
    presentationInFlight = true;
    window.clearTimeout(presentationTimer);
    presentationTimer = window.setTimeout(() => {
      presentationInFlight = false;
    }, Math.max(0, Number(duration) || 0) + 80);
  }

  async function navigate(url, options = {}) {
    const target = sameOriginTarget(url);
    if (!target || leaving || manualClaimInFlight || presentationInFlight) return;

    preserveNightInteraction(options);

    if (!isAutomaticNavigation(options) && leasableRoutes.has(target.pathname)) {
      manualClaimInFlight = true;
      let accepted = false;
      try {
        accepted = await claimManualSurface(target, options);
      } finally {
        manualClaimInFlight = false;
      }
      if (!accepted || leaving) return;
    }

    if (target.pathname === '/alarm' || options.immediate) {
      leaving = true;
      window.location.assign(target.href);
      return;
    }

    if (target.pathname === '/plexamp' && window.ACPPlexamp) {
      const duration = Number(window.ACPPlexamp.show({
        updateMode: false,
        manual: false,
        source: String(options.source || 'navigation-link'),
      })) || 0;
      holdPresentation(duration);
      return;
    }

    const overlayOpen = plexampVisiblyOpen();
    if (overlayOpen) {
      if (target.pathname === activeRoute()) {
        const mode = target.pathname.slice(1) || 'clock';
        const duration = Number(window.ACPPlexamp.hide?.({
          updateMode: false,
          targetMode: mode,
          source: String(options.source || 'navigation-link'),
        })) || 0;
        holdPresentation(duration);
        return;
      }

      leaving = true;
      const delay = Number(
        window.ACPPlexamp.prepareNavigation?.()
        ?? outgoingDelay()
      );
      window.setTimeout(() => window.location.assign(target.href), Math.max(0, delay));
      return;
    }

    leaving = true;
    const delay = outgoingDelay();
    if (delay <= 0) {
      window.location.assign(target.href);
      return;
    }

    document.body.classList.add('acp-page-leaving');
    window.setTimeout(() => window.location.assign(target.href), delay);
  }

  window.ACPNavigate = navigate;
  window.ACPPageReady = revealPage;
  window.ACPNavigationState = {
    isLeaving: () => leaving,
    isPresenting: () => manualClaimInFlight || presentationInFlight || leaving,
    activeRoute,
    consumeExplicitNavigation,
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== '_self') return;
    const target = sameOriginTarget(link.href);
    if (!target) return;
    if (target.href === window.location.href && !plexampVisiblyOpen()) return;
    if (!link.closest('.main-nav') && !link.hasAttribute('data-page-transition')) return;
    event.preventDefault();
    void navigate(target.href, { source: 'navigation-link' });
  });

  window.addEventListener('pagehide', () => {
    leaving = true;
    presentationInFlight = true;
    window.clearTimeout(presentationTimer);
  });

  scheduleReveal();
})();
