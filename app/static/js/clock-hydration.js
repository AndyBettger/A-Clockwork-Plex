(() => {
  if (window.__aClockworkPlexClockHydrationLoaded) return;
  window.__aClockworkPlexClockHydrationLoaded = true;

  let started = false;
  let signalled = false;

  function nextFrame() {
    return new Promise((resolve) => window.requestAnimationFrame(resolve));
  }

  function fontSettleWindow() {
    const fontReady = document.fonts?.ready;
    if (!fontReady || typeof fontReady.then !== 'function') {
      return Promise.resolve();
    }

    return Promise.race([
      fontReady.catch(() => undefined),
      new Promise((resolve) => window.setTimeout(resolve, 350)),
    ]);
  }

  function segmentsReady() {
    return ['clock-hours', 'clock-minutes', 'clock-seconds', 'clock-date']
      .every((id) => Boolean(document.getElementById(id)?.childElementCount));
  }

  async function signalReady() {
    if (started || signalled) return;
    started = true;

    await fontSettleWindow();

    for (let attempt = 0; attempt < 4 && !segmentsReady(); attempt += 1) {
      await nextFrame();
    }

    /* Clock now arrives from Flask in its final compact/composite card layout.
       These final frames are only for segment geometry and font metrics; there is
       no longer a first-load ordinary-card to composite-card DOM replacement. */
    await nextFrame();
    await nextFrame();

    if (signalled) return;
    signalled = true;
    window.dispatchEvent(new CustomEvent('acp:page-hydrated', {
      detail: { page: 'clock', source: 'server-final-layout' },
    }));
  }

  window.requestAnimationFrame(signalReady);
  window.setTimeout(signalReady, 700);
})();
