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

    /* Height owns the square whenever the right pane can still retain a useful
       title/control width. This gives the cover equal top, bottom and left gaps. */
    const minimumCopyWidth = Math.max(430, Math.min(680, innerWidth * 0.42));
    const widthLimit = Math.max(260, innerWidth - gap - minimumCopyWidth);
    const size = Math.floor(Math.max(260, Math.min(innerHeight, widthLimit, 720)));
    card.style.setProperty('--airplay-media-size', `${size}px`);

    /* The media square is vertically centred only when width is the limiting
       constraint. Work from the resulting real centre and grow each route wave
       until it passes the farthest card corner. */
    const mediaTop = paddingTop + Math.max(0, (innerHeight - size) / 2);
    const pulseX = paddingLeft + (size * 0.5);
    const pulseY = mediaTop + (size * 0.505);
    const distances = [
      Math.hypot(pulseX, pulseY),
      Math.hypot(card.clientWidth - pulseX, pulseY),
      Math.hypot(pulseX, card.clientHeight - pulseY),
      Math.hypot(card.clientWidth - pulseX, card.clientHeight - pulseY),
    ];
    const targetRadius = Math.max(...distances) * 1.06;
    const baseDiameter = Math.max(1, size * 0.17);
    const finalScale = Math.max(8, (targetRadius * 2) / baseDiameter);
    card.style.setProperty('--airplay-wave-scale', finalScale.toFixed(2));
  }

  const observer = typeof ResizeObserver === 'function'
    ? new ResizeObserver(calibrate)
    : null;
  observer?.observe(card);

  if (typeof MutationObserver === 'function') {
    new MutationObserver(calibrate).observe(document.body, {
      attributes: true,
      attributeFilter: ['class'],
    });
  }

  window.addEventListener('resize', calibrate, { passive: true });
  window.requestAnimationFrame(calibrate);
  window.setTimeout(calibrate, 180);
  window.setTimeout(calibrate, 800);
})();
