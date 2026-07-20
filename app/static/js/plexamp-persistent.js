(() => {
  if (window.__aClockworkPlexPersistentPlexampLoaded) return;
  window.__aClockworkPlexPersistentPlexampLoaded = true;

  const shell = document.getElementById('persistent-plexamp');
  const frame = document.getElementById('persistent-plexamp-frame');
  if (!shell || !frame) return;

  let frameLoaded = false;
  let revealTimer = null;
  let closingTimer = null;

  function setNavState(open) {
    document.querySelectorAll('.main-nav a[href="/plexamp"]').forEach((link) => {
      link.classList.toggle('is-active', open);
    });
  }

  async function setMode() {
    try {
      await fetch('/api/mode/plexamp', { method: 'POST', cache: 'no-store' });
    } catch (error) {
    }
  }

  function revealFrameSoon() {
    window.clearTimeout(revealTimer);
    revealTimer = window.setTimeout(() => {
      if (frameLoaded) shell.classList.add('is-ready');
    }, 650);
  }

  function show(options = {}) {
    window.clearTimeout(closingTimer);
    shell.classList.remove('is-closing');
    shell.classList.add('is-open');
    shell.setAttribute('aria-hidden', 'false');
    document.body.classList.add('plexamp-overlay-open');
    setNavState(true);
    if (frameLoaded) revealFrameSoon();
    if (options.updateMode !== false) setMode();
  }

  function hide(options = {}) {
    const immediate = options.immediate === true;
    window.clearTimeout(closingTimer);
    if (immediate) {
      shell.classList.remove('is-open', 'is-closing');
      shell.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('plexamp-overlay-open');
      setNavState(false);
      return 0;
    }
    shell.classList.add('is-closing');
    shell.classList.remove('is-open');
    closingTimer = window.setTimeout(() => {
      shell.classList.remove('is-closing');
      shell.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('plexamp-overlay-open');
      setNavState(false);
    }, 220);
    return 220;
  }

  function isOpen() {
    return shell.classList.contains('is-open') || shell.classList.contains('is-closing');
  }

  frame.addEventListener('load', () => {
    frameLoaded = true;
    revealFrameSoon();
  });

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

  window.ACPPlexamp = { show, hide, isOpen, frame };

  if (document.body.dataset.activePage === 'plexamp') {
    show({ updateMode: false });
  }
})();
