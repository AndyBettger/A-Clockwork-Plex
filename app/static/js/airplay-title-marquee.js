(() => {
  if (window.__aClockworkPlexAirPlayTitleMarqueeLoaded) return;
  window.__aClockworkPlexAirPlayTitleMarqueeLoaded = true;

  const title = document.getElementById('airplay-title');
  if (!title) return;

  let frameOne = null;
  let frameTwo = null;
  let lastMeasuredText = null;
  let lastMeasuredWidth = null;

  function clearFrames() {
    if (frameOne !== null) cancelAnimationFrame(frameOne);
    if (frameTwo !== null) cancelAnimationFrame(frameTwo);
    frameOne = null;
    frameTwo = null;
  }

  function reset() {
    title.classList.remove('is-overflowing');
    title.style.removeProperty('--airplay-title-overflow');
    title.style.removeProperty('--airplay-title-scroll-duration');
  }

  function measure({ force = false } = {}) {
    const text = String(title.textContent || '').trim();
    const width = title.clientWidth;

    /* airplay-live refreshes status every two seconds. Some metadata providers
       repaint an identical title during those refreshes, which raises a DOM
       mutation even though nothing visible changed. Do not reset the CSS
       animation for that no-op repaint: otherwise the marquee spends its life
       repeatedly moving a few pixels and snapping back to the beginning. */
    if (!force && text === lastMeasuredText && width === lastMeasuredWidth) {
      return;
    }

    lastMeasuredText = text;
    lastMeasuredWidth = width;
    clearFrames();
    reset();

    if (!document.body.classList.contains('airplay-metadata-active')) return;

    frameOne = requestAnimationFrame(() => {
      frameTwo = requestAnimationFrame(() => {
        const overflow = Math.max(0, Math.ceil(title.scrollWidth - title.clientWidth));
        if (overflow <= 8) return;

        title.style.setProperty('--airplay-title-overflow', `${overflow + 10}px`);
        title.style.setProperty(
          '--airplay-title-scroll-duration',
          `${Math.max(16, Math.min(38, Math.ceil(text.length / 2.7)))}s`,
        );
        title.classList.add('is-overflowing');
      });
    });
  }

  const observer = new MutationObserver(() => measure());
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  window.addEventListener('resize', () => measure({ force: true }));
  window.addEventListener('pageshow', () => measure({ force: true }));
  measure({ force: true });
})();