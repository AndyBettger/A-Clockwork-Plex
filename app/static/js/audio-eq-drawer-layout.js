(() => {
  if (window.__aClockworkPlexEqDrawerLayoutLoaded) return;
  window.__aClockworkPlexEqDrawerLayoutLoaded = true;

  let retryTimer = null;
  let observer = null;

  function placeMasterEq() {
    const mixer = document.getElementById('nav-live-mixer');
    const strip = document.getElementById('acp-eq-strip');
    const master = mixer?.querySelector('.nav-master-channel');
    const masterConsole = master?.querySelector('.nav-master-console');

    if (!mixer || !strip || !master || !masterConsole) return false;

    if (strip.parentElement !== master || strip.nextElementSibling !== masterConsole) {
      masterConsole.insertAdjacentElement('beforebegin', strip);
    }

    // Alarm trim is deliberately a persistent Settings control rather than a
    // quick-access control. Removing it here leaves the Master knob comfortably
    // visible on the 1280x800 bedside display.
    masterConsole.querySelector('.nav-trim-control.is-alarm-knob')?.remove();

    strip.classList.add('acp-eq-strip--drawer');
    master.classList.add('has-master-eq');
    masterConsole.classList.add('is-master-only');

    const heading = strip.querySelector('.acp-eq-heading strong');
    if (heading) heading.textContent = 'EQ';

    observer?.disconnect();
    observer = null;
    window.clearTimeout(retryTimer);
    retryTimer = null;
    return true;
  }

  function retry() {
    if (placeMasterEq()) return;
    window.clearTimeout(retryTimer);
    retryTimer = window.setTimeout(retry, 100);
  }

  observer = new MutationObserver(() => placeMasterEq());
  observer.observe(document.body, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', retry, { once: true });
  } else {
    retry();
  }

  window.addEventListener('pagehide', () => {
    observer?.disconnect();
    window.clearTimeout(retryTimer);
  });
})();
