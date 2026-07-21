(() => {
  if (window.__aClockworkPlexPageTransitionsLoaded) return;
  window.__aClockworkPlexPageTransitionsLoaded = true;

  let leaving = false;
  let revealed = false;
  const explicitNavigationKey = 'a-clockwork-plex.explicit-navigation';

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

  function rememberNavigation(target) {
    try {
      window.sessionStorage.setItem(explicitNavigationKey, JSON.stringify({
        path: target.pathname,
        at: Date.now(),
      }));
    } catch (error) {
    }
  }

  async function setMode(mode) {
    try {
      await fetch(`/api/mode/${mode}`, { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }
  }

  function revealPage() {
    if (revealed) return;
    revealed = true;
    document.body.classList.remove('acp-page-booting');
    document.body.classList.add('acp-page-ready');
  }

  function scheduleReveal() {
    const activePage = String(document.body.dataset.activePage || '').toLowerCase();
    if (activePage === 'airplay') {
      window.addEventListener('acp:page-hydrated', revealPage, { once: true });
      window.setTimeout(revealPage, 1300);
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

  function navigate(url, options = {}) {
    const target = sameOriginTarget(url);
    if (!target || leaving) return;

    if (target.pathname === '/alarm' || options.immediate) {
      rememberNavigation(target);
      window.location.assign(target.href);
      return;
    }

    if (target.pathname === '/plexamp' && window.ACPPlexamp) {
      window.ACPPlexamp.show({ updateMode: options.updateMode !== false });
      return;
    }

    const overlayOpen = Boolean(window.ACPPlexamp?.isOpen?.());
    if (overlayOpen) {
      const delay = Number(window.ACPPlexamp.hide?.() || 0);
      if (target.pathname === activeRoute()) {
        if (options.updateMode !== false) {
          const mode = target.pathname.slice(1) || 'clock';
          setMode(mode);
        }
        return;
      }
      leaving = true;
      rememberNavigation(target);
      window.setTimeout(() => window.location.assign(target.href), delay);
      return;
    }

    leaving = true;
    rememberNavigation(target);
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

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== '_self') return;
    const target = sameOriginTarget(link.href);
    if (!target || target.href === window.location.href) return;
    if (!link.closest('.main-nav') && !link.hasAttribute('data-page-transition')) return;
    event.preventDefault();
    navigate(target.href);
  });

  scheduleReveal();
})();
