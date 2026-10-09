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
  const navigationModeTransferKey = 'a-clockwork-plex.navigation-mode-transfer';
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
    const hosted = window.ACPSurfaceHost?.activeRoute?.();
    if (hosted) return hosted;
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

  function navigationModeOpen() {
    return document.body.classList.contains('nav-open')
      && document.body.classList.contains('nav-mode');
  }

  function shouldPreserveNavigation(options = {}) {
    return !isAutomaticNavigation(options) && navigationModeOpen();
  }

  function visibleWorkspaceRoute() {
    return plexampVisiblyOpen() ? '/plexamp' : activeRoute();
  }

  function spatialPrototypeDirection(target, mainNavLink = false) {
    if (!mainNavLink || !navigationModeOpen()) return '';
    if (String(preferences().transitionStyle || '').toLowerCase() !== 'spatial-row') return '';

    const topology = window.ACPWorkspaceTopology;
    const fromRoute = visibleWorkspaceRoute();
    const toRoute = String(target?.pathname || '');
    const path = topology?.path?.(fromRoute, toRoute) || [];
    if (path.length < 2) return '';

    const acpOnly = path.every((entry) => entry.renderer === 'acp');
    const adjacentCrossRenderer = path.length === 2
      && path.some((entry) => entry.renderer === 'plexamp')
      && path.some((entry) => entry.renderer === 'acp');

    // B6b commissions only the adjacent AirPlay↔Plexamp boundary. Longer
    // Plexamp paths remain on the accepted ordinary transition backend until
    // the intermediate-workspace strip is added in the next bounded slice.
    if (!acpOnly && !adjacentCrossRenderer) return '';
    return topology.direction(fromRoute, toRoute);
  }

  function rememberNavigationMode(target) {
    if (!navigationModeOpen() || !target || target.pathname === '/alarm') return;
    try {
      window.sessionStorage.setItem(navigationModeTransferKey, JSON.stringify({
        path: target.pathname,
        at: Date.now(),
      }));
    } catch (error) {
    }
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
      settings: 1800,
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

    // Navigation is persistent shell chrome. Spatial and ordinary page
    // transitions run behind it; inactivity owns when the shell hides.
    if (target.pathname === '/alarm' || options.immediate) {
      leaving = true;
      window.location.assign(target.href);
      return;
    }

    if (target.pathname === '/plexamp' && window.ACPPlexamp) {
      const spatialAdjacent = options.spatialCommitDirection === 'forward'
        && window.ACPWorkspaceTopology?.path?.(visibleWorkspaceRoute(), '/plexamp')?.length === 2
        && typeof window.ACPPlexamp.spatialShow === 'function';
      const showPlexamp = spatialAdjacent
        ? window.ACPPlexamp.spatialShow
        : window.ACPPlexamp.show;
      const duration = Number(showPlexamp({
        updateMode: false,
        manual: false,
        preserveNavigation: shouldPreserveNavigation(options),
        source: String(options.source || 'navigation-link'),
      })) || 0;
      holdPresentation(duration);
      return;
    }

    if (!plexampVisiblyOpen() && window.ACPSurfaceHost?.canNavigate?.(target.pathname)) {
      const result = await window.ACPSurfaceHost.navigate(target.pathname, {
        ...options,
        history: true,
      });
      if (result?.handled) return;
    }

    const overlayOpen = plexampVisiblyOpen();
    if (overlayOpen) {
      const preserveNavigation = shouldPreserveNavigation(options);
      const mode = target.pathname.slice(1) || 'clock';

      if (target.pathname === activeRoute()) {
        const spatialAdjacent = options.spatialCommitDirection === 'reverse'
          && window.ACPWorkspaceTopology?.path?.('/plexamp', target.pathname)?.length === 2
          && typeof window.ACPPlexamp.spatialHide === 'function';
        const hidePlexamp = spatialAdjacent
          ? window.ACPPlexamp.spatialHide
          : window.ACPPlexamp.hide;
        const duration = Number(hidePlexamp({
          updateMode: false,
          targetMode: mode,
          preserveNavigation,
          source: String(options.source || 'navigation-link'),
        })) || 0;
        holdPresentation(duration);
        return;
      }

      // Mounted ACP destinations can be committed underneath the persistent
      // Plexamp layer before Plexamp reveals them. Keep the shell/navigation
      // DOM alive instead of falling back to a full document navigation, which
      // visibly closes and recreates the nav (most obvious on Settings).
      if (window.ACPSurfaceHost?.canNavigate?.(target.pathname)) {
        const result = await window.ACPSurfaceHost.navigate(target.pathname, {
          ...options,
          animate: false,
          history: true,
          source: String(options.source || 'plexamp-mounted-handoff'),
        });
        if (result?.handled) {
          const spatialAdjacent = options.spatialCommitDirection === 'reverse'
            && window.ACPWorkspaceTopology?.path?.('/plexamp', target.pathname)?.length === 2
            && typeof window.ACPPlexamp.spatialHide === 'function';
          const hidePlexamp = spatialAdjacent
            ? window.ACPPlexamp.spatialHide
            : window.ACPPlexamp.hide;
          const duration = Number(hidePlexamp({
            updateMode: false,
            targetMode: mode,
            preserveNavigation,
            source: String(options.source || 'navigation-link'),
          })) || 0;
          holdPresentation(duration);
          return;
        }
      }

      leaving = true;
      if (preserveNavigation) rememberNavigationMode(target);
      const delay = Number(
        window.ACPPlexamp.prepareNavigation?.({ preserveNavigation })
        ?? outgoingDelay()
      );
      window.setTimeout(() => window.location.assign(target.href), Math.max(0, delay));
      return;
    }

    leaving = true;
    if (shouldPreserveNavigation(options)) rememberNavigationMode(target);
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
    isPresenting: () => (
      manualClaimInFlight
      || presentationInFlight
      || leaving
      || window.ACPSurfaceHost?.isTransitioning?.() === true
    ),
    activeRoute,
    consumeExplicitNavigation,
  };

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== '_self') return;
    const target = sameOriginTarget(link.href);
    if (!target) return;
    const mainNavLink = Boolean(link.closest('.main-nav'));
    if (!mainNavLink && !link.hasAttribute('data-page-transition')) return;

    // A selected ACP destination is already the live mounted surface. Consume
    // the click rather than allowing the browser's default same-URL navigation
    // to hard-reload the document (which would black-flash and discard nav mode).
    if (mainNavLink && !plexampVisiblyOpen() && target.pathname === activeRoute()) {
      event.preventDefault();
      return;
    }

    const spatialCommitDirection = spatialPrototypeDirection(target, mainNavLink);

    event.preventDefault();
    void navigate(target.href, {
      source: 'navigation-link',
      ...(spatialCommitDirection ? { spatialCommitDirection } : {}),
    });
  });

  window.addEventListener('pagehide', () => {
    leaving = true;
    presentationInFlight = true;
    window.clearTimeout(presentationTimer);
  });

  scheduleReveal();
})();
