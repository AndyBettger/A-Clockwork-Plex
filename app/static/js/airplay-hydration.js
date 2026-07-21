(() => {
  if (window.__aClockworkPlexAirPlayHydrationLoaded) return;
  window.__aClockworkPlexAirPlayHydrationLoaded = true;

  let signalled = false;
  function ready() {
    if (signalled) return;
    signalled = true;
    window.dispatchEvent(new CustomEvent('acp:page-hydrated'));
  }

  function rendered() {
    return document.body.classList.contains('airplay-session-idle')
      || document.body.classList.contains('airplay-session-active')
      || document.body.classList.contains('airplay-metadata-active');
  }

  if (rendered()) {
    window.requestAnimationFrame(() => window.requestAnimationFrame(ready));
    return;
  }

  const observer = new MutationObserver(() => {
    if (!rendered()) return;
    observer.disconnect();
    window.requestAnimationFrame(() => window.requestAnimationFrame(ready));
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  window.setTimeout(() => {
    observer.disconnect();
    ready();
  }, 1100);
})();
