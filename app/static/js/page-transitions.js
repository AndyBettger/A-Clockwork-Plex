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

  function navigate(url, options = {}) {
    const target = sameOriginTarget(url);
    if (!target || leaving) return;
    if (target.pathname === '/alarm' || options.immediate) {
      window.location.assign(target.href);
      return;
    }
    leaving = true;
    document.body.classList.add('acp-page-leaving');
    window.setTimeout(() => window.location.assign(target.href), 175);
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
