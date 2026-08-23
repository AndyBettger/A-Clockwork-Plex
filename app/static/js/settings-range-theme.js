(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexSettingsRangeThemeLoaded) return;
  window.__aClockworkPlexSettingsRangeThemeLoaded = true;

  function paint(range) {
    if (!(range instanceof HTMLInputElement)) return;
    if (range.type !== 'range' || range.classList.contains('acp-calibrated-fader')) return;

    const min = Number(range.min || 0);
    const max = Number(range.max || 100);
    const value = Number(range.value || 0);
    const span = max - min;
    const percent = Number.isFinite(span) && span > 0
      ? Math.min(100, Math.max(0, ((value - min) / span) * 100))
      : 0;
    range.style.setProperty('--acp-range-percent', `${percent}%`);
  }

  function paintAll(root = document) {
    root.querySelectorAll?.('input[type="range"]:not(.acp-calibrated-fader)').forEach(paint);
  }

  let refreshQueued = false;
  function queuePaintAll() {
    if (refreshQueued) return;
    refreshQueued = true;
    window.requestAnimationFrame(() => {
      refreshQueued = false;
      paintAll();
    });
  }

  document.addEventListener('input', (event) => paint(event.target), true);
  document.addEventListener('change', (event) => paint(event.target), true);

  const observer = new MutationObserver((mutations) => {
    let refreshAll = false;
    mutations.forEach((mutation) => {
      if (mutation.type !== 'childList') return;
      refreshAll = true;
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        if (node.matches?.('input[type="range"]:not(.acp-calibrated-fader)')) paint(node);
        paintAll(node);
      });
    });

    // Settings hydration changes input.value properties rather than attributes,
    // but also refreshes their visible output text. That child-list mutation is
    // our deterministic signal to repaint every custom range from its real value.
    if (refreshAll) queuePaintAll();
  });

  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('pageshow', queuePaintAll);
  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });

  window.ACPSettingsRangeTheme = {
    paint,
    refresh: paintAll,
  };

  paintAll();
  queuePaintAll();
})();