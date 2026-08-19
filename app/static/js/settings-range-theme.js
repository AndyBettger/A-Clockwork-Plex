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

  document.addEventListener('input', (event) => paint(event.target), true);
  document.addEventListener('change', (event) => paint(event.target), true);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        if (node.matches?.('input[type="range"]:not(.acp-calibrated-fader)')) paint(node);
        paintAll(node);
      });
    });
  });

  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
  paintAll();
})();