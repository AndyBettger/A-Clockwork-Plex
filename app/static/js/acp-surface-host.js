(() => {
  if (window.__aClockworkPlexSurfaceHostLoaded) return;
  window.__aClockworkPlexSurfaceHostLoaded = true;

  const host = document.querySelector('main.screen');
  if (!host) return;

  const registry = new Map();
  let activeSurface = String(document.body.dataset.activePage || '').trim().toLowerCase();
  let activationInFlight = false;

  function normaliseSurface(value) {
    const text = String(value || '').trim().toLowerCase();
    return text.replace(/^\/+/, '').split(/[?#]/, 1)[0];
  }

  function routeFor(surface) {
    const name = normaliseSurface(surface);
    return name ? `/${name}` : '/clock';
  }

  function motionEnabled(options = {}) {
    if (options.animate === false) return false;

    const preferences = window.ACPDashboardPreferences?.read?.() || {};
    const style = String(
      preferences.transitionStyle
      || document.documentElement.dataset.transitionStyle
      || 'grow-fade',
    ).toLowerCase();
    return !['none', 'instant'].includes(style);
  }

  function transitionEnabled(options = {}) {
    return motionEnabled(options)
      && typeof document.startViewTransition === 'function';
  }

  function nightLiveTransitionEnabled(options = {}, prepared = null) {
    if (!motionEnabled(options) || typeof prepared?.liveCommit !== 'function') return false;
    const root = document.documentElement;
    return root.classList.contains('acp-night-document-active')
      && root.classList.contains('acp-night-style-astronomy');
  }

  function updateNavigationState(surface) {
    const route = routeFor(surface);
    document.querySelectorAll('.main-nav a[href]').forEach((link) => {
      let path = '';
      try {
        path = new URL(link.href, window.location.href).pathname;
      } catch (error) {
        return;
      }
      const active = path === route;
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  function updateBodySurface(surface) {
    const previous = activeSurface;
    document.body.dataset.activePage = surface;
    Array.from(document.body.classList)
      .filter((name) => name.startsWith('mode-'))
      .forEach((name) => document.body.classList.remove(name));
    document.body.classList.add(`mode-${surface}`);
    activeSurface = surface;
    updateNavigationState(surface);
    const statusMode = document.querySelector('[data-acp-status-mode]');
    const displayName = surface === 'clock'
      ? 'Home'
      : surface.charAt(0).toUpperCase() + surface.slice(1);
    if (statusMode) statusMode.textContent = `Mode: ${displayName}`;
    return previous;
  }

  function register(surface, lifecycle) {
    const name = normaliseSurface(surface);
    if (!name) throw new Error('ACP surface name is required.');
    if (!lifecycle || typeof lifecycle.prepare !== 'function') {
      throw new Error(`ACP surface "${name}" must provide prepare().`);
    }
    registry.set(name, lifecycle);
    return () => registry.delete(name);
  }

  function canNavigate(target) {
    return registry.has(normaliseSurface(target));
  }

  async function navigate(target, options = {}) {
    const surface = normaliseSurface(target);
    const lifecycle = registry.get(surface);
    if (!lifecycle) return { handled: false, reason: 'surface-not-registered' };
    if (activationInFlight) return { handled: true, accepted: false, reason: 'activation-in-flight' };
    if (surface === activeSurface) return { handled: true, accepted: true, unchanged: true };

    activationInFlight = true;
    const from = activeSurface;
    let prepared;

    try {
      prepared = await lifecycle.prepare({
        host,
        surface,
        from,
        route: routeFor(surface),
        options,
      });
      if (!prepared || typeof prepared.commit !== 'function') {
        throw new Error(`ACP surface "${surface}" prepare() did not return commit().`);
      }

      const commit = async () => {
        prepared.commit({ host, surface, from, options });
        updateBodySurface(surface);
        if (prepared.title) document.title = String(prepared.title);
        if (typeof prepared.beforeSnapshot === 'function') {
          await prepared.beforeSnapshot({ host, surface, from, options });
        }
      };

      let transitionFinished = null;
      const spatialCommitDirection = ['forward', 'reverse'].includes(options.spatialCommitDirection)
        ? options.spatialCommitDirection
        : '';

      if (
        spatialCommitDirection
        && motionEnabled(options)
        && typeof prepared.spatialCommit === 'function'
      ) {
        // Level-B spatial motion uses the two already-mounted live surfaces.
        // Do not ask Chromium for a root View Transition snapshot here: on the
        // commissioned Pi the old-root texture is intermittently blank/white.
        await prepared.spatialCommit({
          host,
          surface,
          from,
          options,
          direction: spatialCommitDirection,
          commit,
        });
      } else if (nightLiveTransitionEnabled(options, prepared)) {
        // Chromium's named nav View Transition snapshot is painted above the
        // live astronomy overlay on the commissioned Pi. Keep shell chrome
        // genuinely live at night and animate only the ACP screen underneath.
        await prepared.liveCommit({ host, surface, from, options, commit });
      } else if (transitionEnabled(options)) {
        const transition = document.startViewTransition(commit);
        await transition.updateCallbackDone;
        transitionFinished = transition.finished.catch(() => undefined);
      } else {
        await commit();
      }

      if (typeof prepared.activate === 'function') {
        await prepared.activate({ host, surface, from, options });
      }

      if (options.history !== false) {
        const route = routeFor(surface);
        if (window.location.pathname !== route) {
          window.history.pushState({ acpSurface: surface }, '', route);
        }
      }

      document.dispatchEvent(new CustomEvent('acp:surface-changed', {
        detail: { surface, from, source: String(options.source || 'surface-navigation') },
      }));

      if (transitionFinished) {
        await transitionFinished;
      }

      document.dispatchEvent(new CustomEvent('acp:surface-settled', {
        detail: { surface, from, source: String(options.source || 'surface-navigation') },
      }));

      return { handled: true, accepted: true, surface, from };
    } catch (error) {
      console.warn('ACP same-document surface activation failed; caller may use route fallback.', error);
      return {
        handled: false,
        accepted: false,
        reason: 'activation-failed',
        error: String(error?.message || error),
      };
    } finally {
      activationInFlight = false;
    }
  }

  window.ACPSurfaceHost = {
    register,
    canNavigate,
    navigate,
    activeSurface: () => activeSurface,
    activeRoute: () => routeFor(activeSurface),
    isTransitioning: () => activationInFlight,
    supportsViewTransitions: () => typeof document.startViewTransition === 'function',
  };
})();
