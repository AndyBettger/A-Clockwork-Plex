(() => {
  if (window.__aClockworkPlexPersistentPlexampLoaded) return;
  window.__aClockworkPlexPersistentPlexampLoaded = true;

  const shell = document.getElementById('persistent-plexamp');
  const frame = document.getElementById('persistent-plexamp-frame');
  if (!shell || !frame) return;

  const FRAME_SETTLE_MS = 1400;
  const MODE_GUARD_MS = 5000;
  const LONG_MODE_GUARD_MS = 10000;

  let frameLoaded = false;
  let frameLoadedAt = 0;
  let frameReadyTimer = null;
  let phaseTimer = null;
  let cleanupTimer = null;
  let spatialAnimations = [];
  let spatialLayers = [];
  let lifecycle = 'hidden';
  let generation = 0;
  let modeGuardUntil = 0;

  function navLinks() {
    return Array.from(document.querySelectorAll('.main-nav a[href]'));
  }

  function routeForLink(link) {
    try {
      return new URL(link.href, window.location.href).pathname;
    } catch (error) {
      return '';
    }
  }

  function transitionProfile() {
    const current = window.ACPDashboardPreferences?.read?.();
    const style = current?.transitionStyle || document.documentElement.dataset.transitionStyle || 'grow-fade';
    const total = Math.max(
      0,
      Math.min(1500, Number(current?.transitionDurationMs ?? document.documentElement.dataset.transitionDurationMs ?? 300)),
    );
    if (style === 'none' || total <= 0) {
      return { style, total: 0, outgoing: 0, incoming: 0 };
    }
    const outgoing = Math.round(total * 0.36);
    return { style, total, outgoing, incoming: Math.max(0, total - outgoing) };
  }

  function setLifecycle(next) {
    lifecycle = next;
    shell.dataset.lifecycle = next;
  }

  function spatialDurationMs() {
    const value = String(
      window.getComputedStyle(document.documentElement)
        .getPropertyValue('--acp-transition-duration')
        || '300ms',
    ).trim();
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) return 300;
    if (value.endsWith('s') && !value.endsWith('ms')) return Math.max(0, parsed * 1000);
    return Math.max(0, parsed);
  }

  function clearSpatialStyles(screen) {
    if (screen) {
      screen.style.transform = '';
      screen.style.willChange = '';
    }
    shell.style.transition = '';
    shell.style.transform = '';
    shell.style.opacity = '';
    shell.style.visibility = '';
    shell.style.pointerEvents = '';
    shell.style.filter = '';
    shell.style.clipPath = '';
    shell.style.willChange = '';
  }

  function setNavState(open) {
    const underlying = `/${String(document.body.dataset.activePage || 'clock').toLowerCase()}`;
    navLinks().forEach((link) => {
      const route = routeForLink(link);
      const active = open ? route === '/plexamp' : route === underlying;
      link.classList.toggle('is-active', active);
      if (active) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  }

  function guardMode(milliseconds = MODE_GUARD_MS) {
    modeGuardUntil = Math.max(modeGuardUntil, Date.now() + milliseconds);
  }

  function clearLifecycleTimers() {
    window.clearTimeout(phaseTimer);
    window.clearTimeout(cleanupTimer);
    phaseTimer = null;
    cleanupTimer = null;
    spatialAnimations.forEach((animation) => animation.cancel());
    spatialAnimations = [];
    spatialLayers.forEach((layer) => layer.remove());
    spatialLayers = [];
    document.body.classList.remove('acp-spatial-live-commit');
    clearSpatialStyles(document.querySelector('.screen'));
  }

  function scheduleFrameReady() {
    window.clearTimeout(frameReadyTimer);
    if (!frameLoaded) return;

    const elapsed = Math.max(0, Date.now() - frameLoadedAt);
    const delay = Math.max(0, FRAME_SETTLE_MS - elapsed);
    frameReadyTimer = window.setTimeout(() => {
      shell.classList.add('is-ready');
    }, delay);
  }

  function isVisiblyOpen() {
    return shell.classList.contains('is-open')
      && shell.getAttribute('aria-hidden') !== 'true'
      && document.body.classList.contains('plexamp-overlay-open');
  }

  function ensureVisible(options = {}) {
    if (isVisiblyOpen() && lifecycle === 'open') return 0;

    ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    guardMode();
    shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    document.body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
    document.body.classList.add('plexamp-overlay-open');
    setNavState(true);
    setLifecycle('open');
    scheduleFrameReady();
    shell.dataset.lastVisibilityRepair = String(options.source || 'projection-reconcile');
    return 0;
  }

  function finishHideVisual() {
    shell.classList.add('is-handoff-hidden');
    shell.classList.remove('is-open', 'is-closing', 'is-route-leaving');
    shell.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('plexamp-overlay-open');
    setNavState(false);
  }

  function playUnderlyingIncoming(token, incomingDuration) {
    const screen = document.querySelector('.screen');
    const body = document.body;

    body.classList.remove('acp-page-leaving', 'acp-plexamp-opening', 'plexamp-overlay-open');
    body.classList.remove('acp-page-ready');

    if (incomingDuration <= 0) {
      setLifecycle('hidden');
      return;
    }

    void screen?.offsetWidth;
    body.classList.add('acp-page-ready');
    setLifecycle('closing-underlay');
    cleanupTimer = window.setTimeout(() => {
      if (token !== generation) return;
      body.classList.remove('acp-page-ready');
      setLifecycle('hidden');
    }, incomingDuration + 60);
  }

  function show(options = {}) {
    const skipOutgoing = options.skipOutgoing === true
      || String(document.body.dataset.activePage || '').toLowerCase() === 'plexamp';

    if (['opening-page', 'opening-overlay', 'open', 'route-leaving'].includes(lifecycle)) {
      if (!isVisiblyOpen() && lifecycle === 'open') {
        ensureVisible({ source: options.source || 'show-state-repair' });
      }
      return 0;
    }

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    setNavState(true);
    guardMode();
    shell.classList.remove('is-handoff-hidden');

    const profile = transitionProfile();
    const outgoing = skipOutgoing ? 0 : profile.outgoing;
    const body = document.body;

    body.classList.remove('acp-page-ready');
    body.classList.add('acp-plexamp-opening');
    if (outgoing > 0) {
      body.classList.add('acp-page-leaving');
      setLifecycle('opening-page');
    } else {
      body.classList.remove('acp-page-leaving');
      setLifecycle('opening-overlay');
    }

    const beginOverlay = () => {
      if (token !== generation) return;

      shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
      shell.classList.add('is-open');
      shell.setAttribute('aria-hidden', 'false');
      body.classList.add('plexamp-overlay-open');
      setLifecycle(profile.incoming > 0 ? 'opening-overlay' : 'open');
      scheduleFrameReady();

      cleanupTimer = window.setTimeout(() => {
        if (token !== generation) return;
        body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
        setLifecycle('open');
      }, profile.incoming + 60);
    };

    phaseTimer = window.setTimeout(beginOverlay, outgoing);
    return outgoing + profile.incoming;
  }

  async function spatialShowPath(options = {}) {
    const path = Array.isArray(options.path) ? options.path : [];
    if (path.length <= 2) return spatialShow(options);

    const capture = window.ACPApplicationSurfaces?.captureSpatialLayers;
    const screen = window.ACPApplicationSurfaces?.screen?.() || document.querySelector('.screen');
    if (typeof capture !== 'function' || !screen) return show(options);

    const sourceSurface = String(path[0]?.id || '').toLowerCase();
    const stagedSurfaces = path.slice(0, -1).map((entry) => String(entry?.id || '').toLowerCase());

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    guardMode(LONG_MODE_GUARD_MS);

    const layers = await capture(stagedSurfaces, sourceSurface, { currentFirst: true });
    if (token !== generation) {
      layers.forEach((layer) => layer.remove());
      return 0;
    }

    spatialLayers = layers;
    document.body.classList.add('acp-spatial-live-commit');
    spatialLayers.forEach((layer) => document.body.appendChild(layer));

    setNavState(true);
    scheduleFrameReady();

    const duration = spatialDurationMs();
    const distance = path.length - 1;
    const body = document.body;

    shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
    body.classList.add('plexamp-overlay-open');
    setLifecycle(duration > 0 ? 'opening-spatial-path' : 'open');

    shell.style.transition = 'none';
    shell.style.opacity = '1';
    shell.style.visibility = 'visible';
    shell.style.pointerEvents = 'none';
    shell.style.filter = 'none';
    shell.style.clipPath = 'inset(0 0 0 0)';
    shell.style.transform = `translateX(${distance * 100}vw)`;
    shell.style.willChange = 'transform';

    spatialLayers.forEach((layer, index) => {
      layer.style.transform = `translateX(${index * 100}vw)`;
    });

    if (duration <= 0) {
      spatialLayers.forEach((layer) => layer.remove());
      spatialLayers = [];
      body.classList.remove('acp-spatial-live-commit');
      clearSpatialStyles(screen);
      setLifecycle('open');
      return 0;
    }

    const timing = {
      duration,
      easing: 'cubic-bezier(.16, .84, .24, 1)',
      fill: 'both',
    };

    spatialAnimations = spatialLayers.map((layer, index) => {
      const start = index * 100;
      const end = start - (distance * 100);
      return layer.animate(
        [
          { transform: `translateX(${start}vw)` },
          { transform: `translateX(${end}vw)` },
        ],
        timing,
      );
    });
    spatialAnimations.push(shell.animate(
      [
        { transform: `translateX(${distance * 100}vw)` },
        { transform: 'translateX(0)' },
      ],
      timing,
    ));

    Promise.all(spatialAnimations.map((animation) => animation.finished.catch(() => undefined)))
      .then(() => {
        if (token !== generation) return;
        spatialAnimations.forEach((animation) => animation.cancel());
        spatialAnimations = [];
        spatialLayers.forEach((layer) => layer.remove());
        spatialLayers = [];
        body.classList.remove('acp-spatial-live-commit');
        clearSpatialStyles(screen);
        setLifecycle('open');
      });

    return duration;
  }

  async function spatialHidePath(options = {}) {
    const path = Array.isArray(options.path) ? options.path : [];
    if (path.length <= 2) return spatialHide(options);

    const capture = window.ACPApplicationSurfaces?.captureSpatialLayers;
    const screen = window.ACPApplicationSurfaces?.screen?.() || document.querySelector('.screen');
    if (typeof capture !== 'function' || !screen || !shell.classList.contains('is-open')) {
      return hide(options);
    }

    const targetSurface = String(path[path.length - 1]?.id || '').toLowerCase();
    const stagedSurfaces = path.slice(1, -1).map((entry) => String(entry?.id || '').toLowerCase());

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    guardMode(LONG_MODE_GUARD_MS);

    const layers = await capture(stagedSurfaces, targetSurface);
    if (token !== generation) {
      layers.forEach((layer) => layer.remove());
      return 0;
    }

    spatialLayers = layers;
    document.body.classList.add('acp-spatial-live-commit');
    spatialLayers.forEach((layer) => document.body.appendChild(layer));

    const duration = spatialDurationMs();
    const distance = path.length - 1;

    document.body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
    document.body.classList.add('plexamp-overlay-open');
    shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    setLifecycle(duration > 0 ? 'closing-spatial-path' : 'hidden');

    shell.style.transition = 'none';
    shell.style.opacity = '1';
    shell.style.visibility = 'visible';
    shell.style.pointerEvents = 'none';
    shell.style.filter = 'none';
    shell.style.clipPath = 'inset(0 0 0 0)';
    shell.style.transform = 'translateX(0)';
    shell.style.willChange = 'transform';

    spatialLayers.forEach((layer, index) => {
      layer.style.transform = `translateX(${-(index + 1) * 100}vw)`;
    });
    screen.style.transform = `translateX(${-distance * 100}vw)`;
    screen.style.willChange = 'transform';

    if (duration <= 0) {
      finishHideVisual();
      spatialLayers.forEach((layer) => layer.remove());
      spatialLayers = [];
      document.body.classList.remove('acp-spatial-live-commit');
      clearSpatialStyles(screen);
      setLifecycle('hidden');
      return 0;
    }

    const timing = {
      duration,
      easing: 'cubic-bezier(.16, .84, .24, 1)',
      fill: 'both',
    };

    spatialAnimations = [
      shell.animate(
        [
          { transform: 'translateX(0)' },
          { transform: `translateX(${distance * 100}vw)` },
        ],
        timing,
      ),
      ...spatialLayers.map((layer, index) => {
        const start = -(index + 1) * 100;
        const end = start + (distance * 100);
        return layer.animate(
          [
            { transform: `translateX(${start}vw)` },
            { transform: `translateX(${end}vw)` },
          ],
          timing,
        );
      }),
      screen.animate(
        [
          { transform: `translateX(${-distance * 100}vw)` },
          { transform: 'translateX(0)' },
        ],
        timing,
      ),
    ];

    Promise.all(spatialAnimations.map((animation) => animation.finished.catch(() => undefined)))
      .then(() => {
        if (token !== generation) return;
        finishHideVisual();
        spatialAnimations.forEach((animation) => animation.cancel());
        spatialAnimations = [];
        spatialLayers.forEach((layer) => layer.remove());
        spatialLayers = [];
        document.body.classList.remove('acp-spatial-live-commit');
        clearSpatialStyles(screen);
        setLifecycle('hidden');
      });

    return duration;
  }

  function spatialShow(options = {}) {
    if (isVisiblyOpen() && lifecycle === 'open') return 0;

    const screen = document.querySelector('.screen');
    if (!screen) return show(options);

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    setNavState(true);
    guardMode();
    scheduleFrameReady();

    const duration = spatialDurationMs();
    const body = document.body;

    shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
    body.classList.add('plexamp-overlay-open');
    setLifecycle(duration > 0 ? 'opening-spatial' : 'open');

    shell.style.transition = 'none';
    shell.style.opacity = '1';
    shell.style.visibility = 'visible';
    shell.style.pointerEvents = 'none';
    shell.style.filter = 'none';
    shell.style.clipPath = 'inset(0 0 0 0)';
    shell.style.transform = 'translateX(100vw)';
    shell.style.willChange = 'transform';
    screen.style.willChange = 'transform';

    if (duration <= 0) {
      clearSpatialStyles(screen);
      setLifecycle('open');
      return 0;
    }

    const timing = {
      duration,
      easing: 'cubic-bezier(.16, .84, .24, 1)',
      fill: 'both',
    };
    const screenAnimation = screen.animate(
      [{ transform: 'translateX(0)' }, { transform: 'translateX(-100vw)' }],
      timing,
    );
    const plexampAnimation = shell.animate(
      [{ transform: 'translateX(100vw)' }, { transform: 'translateX(0)' }],
      timing,
    );
    spatialAnimations = [screenAnimation, plexampAnimation];

    Promise.all(spatialAnimations.map((animation) => animation.finished.catch(() => undefined)))
      .then(() => {
        if (token !== generation) return;
        spatialAnimations.forEach((animation) => animation.cancel());
        spatialAnimations = [];
        clearSpatialStyles(screen);
        setLifecycle('open');
      });

    return duration;
  }

  function spatialHide(options = {}) {
    const screen = document.querySelector('.screen');
    if (!screen || !shell.classList.contains('is-open')) return hide(options);

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    guardMode();

    const duration = spatialDurationMs();
    document.body.classList.remove('acp-page-leaving', 'acp-plexamp-opening');
    document.body.classList.add('plexamp-overlay-open');
    shell.classList.remove('is-handoff-hidden', 'is-closing', 'is-route-leaving');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    setLifecycle(duration > 0 ? 'closing-spatial' : 'hidden');

    shell.style.transition = 'none';
    shell.style.opacity = '1';
    shell.style.visibility = 'visible';
    shell.style.pointerEvents = 'none';
    shell.style.filter = 'none';
    shell.style.clipPath = 'inset(0 0 0 0)';
    shell.style.transform = 'translateX(0)';
    shell.style.willChange = 'transform';
    screen.style.transform = 'translateX(-100vw)';
    screen.style.willChange = 'transform';

    if (duration <= 0) {
      finishHideVisual();
      clearSpatialStyles(screen);
      setLifecycle('hidden');
      return 0;
    }

    const timing = {
      duration,
      easing: 'cubic-bezier(.16, .84, .24, 1)',
      fill: 'both',
    };
    const plexampAnimation = shell.animate(
      [{ transform: 'translateX(0)' }, { transform: 'translateX(100vw)' }],
      timing,
    );
    const screenAnimation = screen.animate(
      [{ transform: 'translateX(-100vw)' }, { transform: 'translateX(0)' }],
      timing,
    );
    spatialAnimations = [plexampAnimation, screenAnimation];

    Promise.all(spatialAnimations.map((animation) => animation.finished.catch(() => undefined)))
      .then(() => {
        if (token !== generation) return;
        finishHideVisual();
        spatialAnimations.forEach((animation) => animation.cancel());
        spatialAnimations = [];
        clearSpatialStyles(screen);
        setLifecycle('hidden');
      });

    return duration;
  }

  function hide(options = {}) {
    const profile = transitionProfile();

    guardMode();

    if (lifecycle === 'hidden' && !shell.classList.contains('is-open')) {
      finishHideVisual();
      setLifecycle('hidden');
      return 0;
    }

    const token = ++generation;
    clearLifecycleTimers();
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();

    if (!shell.classList.contains('is-open')) {
      finishHideVisual();
      playUnderlyingIncoming(token, profile.incoming);
      return profile.incoming;
    }

    shell.classList.remove('is-handoff-hidden', 'is-closing');
    shell.classList.add('is-open', 'is-route-leaving');
    shell.setAttribute('aria-hidden', 'false');
    document.body.classList.add('plexamp-overlay-open');
    setLifecycle('closing-overlay');

    phaseTimer = window.setTimeout(() => {
      if (token !== generation) return;
      finishHideVisual();
      playUnderlyingIncoming(token, profile.incoming);
    }, profile.outgoing);

    return profile.outgoing + profile.incoming;
  }

  function prepareNavigation(options = {}) {
    const profile = transitionProfile();
    ++generation;
    clearLifecycleTimers();
    window.clearTimeout(frameReadyTimer);
    if (options.preserveNavigation !== true) window.ACPNavDrawer?.hide?.();
    guardMode(LONG_MODE_GUARD_MS);

    shell.classList.remove('is-handoff-hidden', 'is-closing');
    shell.classList.add('is-open', 'is-route-leaving');
    shell.setAttribute('aria-hidden', 'false');
    document.body.classList.add('plexamp-overlay-open');
    setNavState(true);
    setLifecycle('route-leaving');
    return profile.outgoing;
  }

  function isOpen() {
    return lifecycle !== 'hidden'
      || shell.classList.contains('is-open')
      || shell.classList.contains('is-route-leaving');
  }

  function isTransitioning() {
    return !['hidden', 'open'].includes(lifecycle);
  }

  function shouldDeferModeSync() {
    return Date.now() < modeGuardUntil || isTransitioning();
  }

  frame.addEventListener('load', () => {
    frameLoaded = true;
    frameLoadedAt = Date.now();
    shell.classList.remove('is-ready');
    scheduleFrameReady();
  });

  window.setTimeout(() => {
    if (frameLoaded) return;
    frameLoaded = true;
    frameLoadedAt = Date.now() - FRAME_SETTLE_MS;
    scheduleFrameReady();
  }, 2500);

  window.ACPPlexamp = {
    show,
    hide,
    spatialShow,
    spatialHide,
    spatialShowPath,
    spatialHidePath,
    ensureVisible,
    prepareNavigation,
    isOpen,
    isVisiblyOpen,
    isTransitioning,
    shouldDeferModeSync,
    lifecycle: () => lifecycle,
    frame,
  };

  if (String(document.body.dataset.activePage || '').toLowerCase() === 'plexamp') {
    show({ updateMode: false, manual: false, skipOutgoing: true, source: 'initial-plexamp-document' });
  }
})();
