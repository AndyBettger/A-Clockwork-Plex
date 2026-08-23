(() => {
  if (window.__aClockworkPlexNavDrawerLifecycleLoaded) return;
  window.__aClockworkPlexNavDrawerLifecycleLoaded = true;

  const drawer = document.getElementById('nav-drawer');
  const handle = document.getElementById('nav-handle');

  function hide() {
    document.body.classList.remove('nav-open', 'nav-audio-open');
    drawer?.setAttribute('aria-hidden', 'true');
    handle?.setAttribute('aria-expanded', 'false');
    handle?.setAttribute('aria-label', 'Show navigation');

    const panel = document.getElementById('nav-live-mixer');
    const audioButton = document.getElementById('nav-audio-button');
    if (panel) panel.hidden = true;
    if (audioButton) {
      audioButton.setAttribute('aria-expanded', 'false');
      audioButton.classList.remove('is-active');
    }
  }

  function isOpen() {
    return document.body.classList.contains('nav-open');
  }

  window.ACPNavDrawer = { hide, isOpen };
})();
