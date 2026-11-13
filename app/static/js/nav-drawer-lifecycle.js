(() => {
  if (window.__aClockworkPlexNavDrawerLifecycleLoaded) return;
  window.__aClockworkPlexNavDrawerLifecycleLoaded = true;

  function fallbackHide() {
    document.body.classList.remove('nav-open', 'nav-audio-open');
    document.getElementById('nav-drawer')?.setAttribute('aria-hidden', 'true');
    const handle = document.getElementById('nav-handle');
    handle?.setAttribute('aria-expanded', 'false');
    handle?.setAttribute('aria-label', 'Show navigation');

    const panel = document.getElementById('nav-live-mixer');
    const audioButton = document.getElementById('nav-audio-button');
    if (panel) panel.setAttribute('aria-hidden', 'true');
    if (audioButton) {
      audioButton.setAttribute('aria-expanded', 'false');
      audioButton.classList.remove('is-active');
    }
  }

  function controller() {
    return window.ACPNavDrawerController;
  }

  function hide() {
    if (typeof controller()?.hide === 'function') controller().hide();
    else fallbackHide();
  }

  function show() {
    controller()?.show?.();
  }

  function toggle() {
    controller()?.toggle?.();
  }

  function ensureAudioPanel() {
    controller()?.ensureAudioPanel?.();
  }

  function isOpen() {
    return document.body.classList.contains('nav-open');
  }

  window.ACPNavDrawer = { hide, show, toggle, ensureAudioPanel, isOpen };
})();
