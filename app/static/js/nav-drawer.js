(() => {
  const drawer = document.getElementById('nav-drawer');
  const handle = document.getElementById('nav-handle');

  if (!drawer || !handle) {
    return;
  }

  const AUTO_HIDE_MS = 6000;
  const SWIPE_THRESHOLD_PX = 24;
  let hideTimer = null;
  let touchStartY = null;

  function setExpanded(expanded) {
    document.body.classList.toggle('nav-open', expanded);
    drawer.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    handle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    handle.setAttribute('aria-label', expanded ? 'Hide navigation' : 'Show navigation');
  }

  function scheduleHide() {
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => setExpanded(false), AUTO_HIDE_MS);
  }

  function showDrawer() {
    setExpanded(true);
    scheduleHide();
  }

  function hideDrawer() {
    window.clearTimeout(hideTimer);
    setExpanded(false);
  }

  handle.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) {
      hideDrawer();
    } else {
      showDrawer();
    }
  });

  handle.addEventListener('touchstart', (event) => {
    touchStartY = event.changedTouches[0]?.clientY ?? null;
  }, { passive: true });

  handle.addEventListener('touchend', (event) => {
    const touchEndY = event.changedTouches[0]?.clientY ?? null;
    if (touchStartY === null || touchEndY === null) {
      return;
    }

    if (touchStartY - touchEndY > SWIPE_THRESHOLD_PX) {
      showDrawer();
    }
    touchStartY = null;
  }, { passive: true });

  drawer.addEventListener('pointerdown', scheduleHide);
  drawer.addEventListener('focusin', scheduleHide);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      hideDrawer();
    }
  });

  setExpanded(false);
})();
