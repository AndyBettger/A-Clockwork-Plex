(() => {
  if (window.__aClockworkPlexAudioPolishLoaded) return;
  window.__aClockworkPlexAudioPolishLoaded = true;

  function installDrawerMotion() {
    const panel = document.getElementById('nav-live-mixer');
    const button = document.getElementById('nav-audio-button');
    if (!panel || !button) {
      window.setTimeout(installDrawerMotion, 100);
      return;
    }
    if (panel.dataset.polishMotionInstalled === 'true') return;
    panel.dataset.polishMotionInstalled = 'true';

    const reveal = () => {
      if (panel.hidden) return;
      panel.classList.remove('is-audio-closing', 'is-audio-visible');
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => panel.classList.add('is-audio-visible')));
    };
    new MutationObserver(reveal).observe(panel, { attributes: true, attributeFilter: ['hidden'] });

    document.addEventListener('click', (event) => {
      if (event.target.closest('#nav-audio-button') !== button || panel.hidden) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      panel.classList.remove('is-audio-visible');
      panel.classList.add('is-audio-closing');
      window.setTimeout(() => {
        panel.hidden = true;
        panel.classList.remove('is-audio-closing');
        document.body.classList.remove('nav-audio-open');
        button.classList.remove('is-active');
        button.setAttribute('aria-expanded', 'false');
      }, 225);
    }, true);
  }

  installDrawerMotion();
})();
