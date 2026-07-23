(() => {
  if (window.__aClockworkPlexFaderCalibrationLoaded) return;
  window.__aClockworkPlexFaderCalibrationLoaded = true;

  const installed = new WeakSet();
  const observedContainers = new WeakSet();

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function syncVisual(input) {
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const value = clamp(Number(input.value || min), min, max);
    const percent = max > min ? ((value - min) / (max - min)) * 100 : 0;
    input.style.setProperty('--acp-fader-percent', `${percent}%`);
  }

  function measure(input, container) {
    const settings = Boolean(container.classList.contains('audio-mixer-control-row'));
    const top = settings ? 4 : 0;
    const bottom = settings ? 58 : 0;
    const available = Math.max(120, container.clientHeight - top - bottom);
    const centre = top + available / 2;

    container.style.setProperty('--acp-fader-top', `${top}px`);
    container.style.setProperty('--acp-fader-bottom', `${bottom}px`);
    input.style.setProperty('--acp-fader-length', `${available}px`);
    input.style.setProperty('--acp-fader-center', `${centre}px`);
    syncVisual(input);
  }

  function install(input) {
    if (!(input instanceof HTMLInputElement) || installed.has(input)) return;
    const container = input.closest('.nav-live-fader, .audio-mixer-control-row');
    if (!container) return;

    installed.add(input);
    input.classList.add('acp-calibrated-fader');
    input.addEventListener('input', () => syncVisual(input));
    input.addEventListener('change', () => syncVisual(input));

    if (!observedContainers.has(container) && 'ResizeObserver' in window) {
      observedContainers.add(container);
      const observer = new ResizeObserver(() => {
        container.querySelectorAll('input.acp-calibrated-fader').forEach((slider) => measure(slider, container));
      });
      observer.observe(container);
    }

    measure(input, container);
    window.requestAnimationFrame(() => measure(input, container));
  }

  function scan(root = document) {
    root.querySelectorAll?.('input[data-nav-live-slider], input[data-mixer-slider]').forEach(install);
  }

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        if (node.matches('input[data-nav-live-slider], input[data-mixer-slider]')) install(node);
        scan(node);
      });
    });
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  scan();

  const syncTimer = window.setInterval(() => {
    document.querySelectorAll('input.acp-calibrated-fader').forEach((input) => {
      const container = input.closest('.nav-live-fader, .audio-mixer-control-row');
      if (container) measure(input, container);
    });
  }, 180);

  window.addEventListener('pagehide', () => {
    window.clearInterval(syncTimer);
    observer.disconnect();
  });
})();
