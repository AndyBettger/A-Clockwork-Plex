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
    window.ACPNavDrawer?.hide?.();
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
    window.ACPNavDrawer?.hide?.();
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
    window.ACPNavDrawer?.hide?.();

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

  function prepareNavigation() {
    const profile = transitionProfile();
    ++generation;
    clearLifecycleTimers();
    window.clearTimeout(frameReadyTimer);
    window.ACPNavDrawer?.hide?.();
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
