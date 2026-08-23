(() => {
  if (window.__aClockworkPlexAirPlayTitleMarqueeLoaded) return;
  window.__aClockworkPlexAirPlayTitleMarqueeLoaded = true;

  const title = document.getElementById('airplay-title');
  if (!title) return;

  /* The source/book/album line already has a physically proven marquee based on
     a clipped container plus translateX on the moving child. Give the episode
     title the same geometry instead of maintaining a separate text-indent
     animation. airplay-live may continue writing title.textContent normally. */
  let shell = title.parentElement;
  if (!shell?.classList.contains('airplay-title-scroll-shell')) {
    shell = document.createElement('div');
    shell.className = 'airplay-title-scroll-shell';
    title.parentNode?.insertBefore(shell, title);
    shell.appendChild(title);
  }

  let frameOne = null;
  let frameTwo = null;
  let lastText = null;
  let lastWidth = null;

  function clearFrames() {
    if (frameOne !== null) cancelAnimationFrame(frameOne);
    if (frameTwo !== null) cancelAnimationFrame(frameTwo);
    frameOne = null;
    frameTwo = null;
  }

  function reset() {
    shell.classList.remove('is-overflowing');
    shell.style.removeProperty('--airplay-source-overflow');
    shell.style.removeProperty('--airplay-scroll-duration');
  }

  function measure({ force = false } = {}) {
    const text = String(title.textContent || '').trim();
    const width = shell.clientWidth;

    /* /api/status repaints can write the same text every two seconds. The
       working secondary-title marquee leaves identical text alone, so do the
       same here: no DOM reset means no animation restart. */
    if (!force && text === lastText && width === lastWidth) return;

    lastText = text;
    lastWidth = width;
    clearFrames();
    reset();

    if (!text || !document.body.classList.contains('airplay-metadata-active')) return;

    frameOne = requestAnimationFrame(() => {
      frameTwo = requestAnimationFrame(() => {
        const measuredOverflow = Math.max(0, title.scrollWidth - shell.clientWidth);
        const estimatedOverflow = Math.max(0, Math.ceil(text.length * 24) - shell.clientWidth);
        const overflow = Math.max(measuredOverflow, estimatedOverflow);

        if (overflow > 8 || text.length > 34) {
          shell.style.setProperty('--airplay-source-overflow', `${Math.max(overflow, 72)}px`);
          shell.style.setProperty(
            '--airplay-scroll-duration',
            `${Math.max(18, Math.min(38, Math.ceil(text.length / 2.7)))}s`,
          );
          shell.classList.add('is-overflowing');
        }
      });
    });
  }

  const observer = new MutationObserver(() => measure());
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  window.addEventListener('resize', () => measure({ force: true }));
  window.addEventListener('pageshow', () => measure({ force: true }));
  measure({ force: true });
})();