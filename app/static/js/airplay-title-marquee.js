(() => {
  if (window.__aClockworkPlexAirPlayTitleMarqueeLoaded) return;
  window.__aClockworkPlexAirPlayTitleMarqueeLoaded = true;

  const title = document.getElementById('airplay-title');
  if (!title) return;

  let frameOne = null;
  let frameTwo = null;

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

  function measure() {
    clearFrames();
    reset();

    if (!document.body.classList.contains('airplay-metadata-active')) return;

    frameOne = requestAnimationFrame(() => {
      frameTwo = requestAnimationFrame(() => {
        const overflow = Math.max(0, Math.ceil(title.scrollWidth - title.clientWidth));
        if (overflow <= 8) return;

        const textLength = String(title.textContent || '').trim().length;
        title.style.setProperty('--airplay-title-overflow', `${overflow + 10}px`);
        title.style.setProperty(
          '--airplay-title-scroll-duration',
          `${Math.max(16, Math.min(38, Math.ceil(textLength / 2.7)))}s`,
        );
        title.classList.add('is-overflowing');
      });
    });
  }

  const observer = new MutationObserver(measure);
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  window.addEventListener('resize', measure);
  window.addEventListener('pageshow', measure);
  measure();
})();