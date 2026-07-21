(() => {
  if (window.__aClockworkPlexPersistentPlexampLoaded) return;
  window.__aClockworkPlexPersistentPlexampLoaded = true;

  const shell = document.getElementById('persistent-plexamp');
  const frame = document.getElementById('persistent-plexamp-frame');
  if (!shell || !frame) return;

  const FRAME_SETTLE_MS = 1400;
  const MODE_GUARD_MS = 5000;
  const LONG_MODE_GUARD_MS = 10000;
  const HANDOFF_REARM_MS = 30000;

  let frameLoaded = false;
  let frameLoadedAt = 0;
  let frameReadyTimer = null;
  let phaseTimer = null;
  let cleanupTimer = null;
  let handoffTimer = null;
  let handoffArmInFlight = false;
  let notifyInFlight = false;
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

  async function updateServerMode(mode) {
    const target = String(mode || '').trim().toLowerCase();
    if (!['clock', 'weather', 'airplay', 'plexamp', 'settings'].includes(target)) return;

    guardMode();
    notifyInFlight = true;
    try {
      await fetch(`/api/mode/${target}`, {
        method: 'POST',
        cache: 'no-store',
      });
    } catch (error) {
    } finally {
      notifyInFlight = false;
      guardMode(1400);
    }
  }

  async function armAirplayHandoff() {
    if (handoffArmInFlight || lifecycle === 'hidden' || lifecycle === 'route-leaving') return;
    handoffArmInFlight = true;
    try {
      /* The /plexamp route owns the server-side watcher that waits for Plexamp
         to enter Playing and then pauses (or stops) an active AirPlay sender.
         HEAD runs that route without replacing or reloading the persistent iframe. */
      await fetch('/plexamp', {
        method: 'HEAD',
        cache: 'no-store',
      });
    } catch (error) {
    } finally {
      handoffArmInFlight = false;
    }
  }

  function startAirplayHandoffWatch() {
    window.clearInterval(handoffTimer);
    handoffTimer = null;
    armAirplayHandoff();
    handoffTimer = window.setInterval(() => {
      if (lifecycle !== 'hidden' && lifecycle !== 'route-leaving') {
        armAirplayHandoff();
      }
    }, HANDOFF_REARM_MS);
  }

  function stopAirplayHandoffWatch() {
    window.clearInterval(handoffTimer);
    handoffTimer = null;
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

  function finishHideVisual() {
    stopAirplayHandoffWatch();
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

    /* Restart the existing incoming keyframes after the opaque Plexamp curtain has
       completed its outgoing half. The forced layout read is deliberate and tiny. */
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
    const updateMode = options.updateMode !== false;
    const skipOutgoing = options.skipOutgoing === true
      || String(document.body.dataset.activePage || '').toLowerCase() === 'plexamp';

    if (['opening-page', 'opening-overlay', 'open', 'route-leaving'].includes(lifecycle)) {
      if (updateMode && !notifyInFlight) updateServerMode('plexamp');
      if (lifecycle !== 'route-leaving') startAirplayHandoffWatch();
      return 0;
    }

    const token = ++generation;
    clearLifecycleTimers();
    window.ACPNavDrawer?.hide?.();
    setNavState(true);
    guardMode();
    if (updateMode) updateServerMode('plexamp');

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
    startAirplayHandoffWatch();

    const beginOverlay = () => {
      if (token !== generation) return;

      shell.classList.remove('is-closing', 'is-route-leaving');
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
    const updateMode = options.updateMode === true;
    const targetMode = String(options.targetMode || document.body.dataset.activePage || 'clock').toLowerCase();
    const profile = transitionProfile();

    guardMode();
    if (updateMode) updateServerMode(targetMode);

    if (lifecycle === 'hidden' && !shell.classList.contains('is-open')) {
      finishHideVisual();
      setLifecycle('hidden');
      return 0;
    }

    const token = ++generation;
    clearLifecycleTimers();
    window.ACPNavDrawer?.hide?.();
    stopAirplayHandoffWatch();

    /* A tap back to the underlying page during the first outgoing half can be
       cancelled without exposing or reloading Plexamp. */
    if (!shell.classList.contains('is-open')) {
      finishHideVisual();
      playUnderlyingIncoming(token, profile.incoming);
      return profile.incoming;
    }

    /* Keep the shell opaque while only its visible contents perform the outgoing
       half. Once complete, remove the shell and play the underlying incoming half. */
    shell.classList.remove('is-closing');
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
    stopAirplayHandoffWatch();
    guardMode(LONG_MODE_GUARD_MS);

    /* A different dashboard document is about to replace this one. Keep the shell
       itself as an opaque handover curtain and animate only the Plexamp contents. */
    shell.classList.remove('is-closing');
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
    return notifyInFlight || Date.now() < modeGuardUntil || isTransitioning();
  }

  frame.addEventListener('load', () => {
    frameLoaded = true;
    frameLoadedAt = Date.now();
    shell.classList.remove('is-ready');
    scheduleFrameReady();
  });

  /* A cached iframe can occasionally complete before this listener is attached.
     The fallback avoids leaving the preparation curtain up forever in that case. */
  window.setTimeout(() => {
    if (frameLoaded) return;
    frameLoaded = true;
    frameLoadedAt = Date.now() - FRAME_SETTLE_MS;
    scheduleFrameReady();
  }, 2500);

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    let target;
    try {
      target = new URL(link.href, window.location.href);
    } catch (error) {
      return;
    }
    if (target.origin !== window.location.origin || target.pathname !== '/plexamp') return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    show();
  }, true);

  window.addEventListener('pagehide', stopAirplayHandoffWatch);

  window.ACPPlexamp = {
    show,
    hide,
    prepareNavigation,
    isOpen,
    isTransitioning,
    shouldDeferModeSync,
    lifecycle: () => lifecycle,
    frame,
  };

  if (String(document.body.dataset.activePage || '').toLowerCase() === 'plexamp') {
    show({ updateMode: false, skipOutgoing: true });
  }
})();
