(() => {
  if (window.__aClockworkPlexAirPlayLayoutV3Loaded) return;
  window.__aClockworkPlexAirPlayLayoutV3Loaded = true;

  const card = document.querySelector('.airplay-now-card');
  if (!card) return;

  function number(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function calibrate() {
    const style = window.getComputedStyle(card);
    const paddingTop = number(style.paddingTop);
    const paddingBottom = number(style.paddingBottom);
    const paddingLeft = number(style.paddingLeft);
    const paddingRight = number(style.paddingRight);
    const gap = number(style.columnGap || style.gap);

    const innerHeight = Math.max(0, card.clientHeight - paddingTop - paddingBottom);
    const innerWidth = Math.max(0, card.clientWidth - paddingLeft - paddingRight);

    /* Preserve enough width for long titles, transport controls and their
       right margin. Height remains the primary artwork constraint. */
    const minimumCopyWidth = Math.max(520, Math.min(760, innerWidth * 0.49));
    const widthLimit = Math.max(240, innerWidth - gap - minimumCopyWidth);
    const size = Math.floor(Math.max(240, Math.min(innerHeight, widthLimit, 680)));

    card.style.setProperty('--airplay-media-size', `${size}px`);
  }

  const observer = typeof ResizeObserver === 'function'
    ? new ResizeObserver(calibrate)
    : null;
  observer?.observe(card);
  window.addEventListener('resize', calibrate, { passive: true });
  window.requestAnimationFrame(calibrate);
  window.setTimeout(calibrate, 180);
})();
