(() => {
  if (window.__aClockworkPlexPageTransitionsLoaded) return;
  window.__aClockworkPlexPageTransitionsLoaded = true;

  let leaving = false;

  function sameOriginTarget(url) {
    try {
      const target = new URL(url, window.location.href);
      return target.origin === window.location.origin ? target : null;
    } catch (error) {
      return null;
    }
  }

  function activeRoute() {
    const page = String(document.body.dataset.activePage || '').trim().toLowerCase();
    return page ? `/${page}` : window.location.pathname;
  }

  async function setMode(mode) {
    try {
      await fetch(`/api/mode/${mode}`, { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }
  }

  function navigate(url, options = {}) {
    const target = sameOriginTarget(url);
    if (!target || leaving) return;

    if (target.pathname === '/alarm' || options.immediate) {
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
      window.setTimeout(() => window.location.assign(target.href), delay);
      return;
    }

    leaving = true;
    /* Chromium performs the outgoing/incoming animation through
       @view-transition. Other browsers simply navigate and receive the entry
       fallback on the next document. */
    window.location.assign(target.href);
  }

  window.ACPNavigate = navigate;

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
})();
