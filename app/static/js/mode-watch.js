(() => {
  if (window.__aClockworkPlexServiceRecoveryWatchLoaded) return;
  window.__aClockworkPlexServiceRecoveryWatchLoaded = true;

  let statusUnavailable = false;
  let plexampRecoveryTimer = null;
  let plexampRecoveryGeneration = 0;

  async function plexampPlayerReady() {
    try {
      const response = await fetch('/api/audio/state', { cache: 'no-store' });
      if (!response.ok) return false;
      const payload = await response.json();
      return payload?.audio?.channels?.plexamp?.available === true;
    } catch (error) {
      return false;
    }
  }

  function reloadPlexampFrame(generation) {
    if (generation !== plexampRecoveryGeneration) return;
    const frame = document.getElementById('persistent-plexamp-frame');
    if (!frame) return;

    const source = frame.getAttribute('src');
    if (!source) return;
    const target = new URL(source, window.location.href);
    target.searchParams.set('acp_reconnect', String(Date.now()));

    document.getElementById('persistent-plexamp')?.classList.remove('is-ready');
    frame.setAttribute('src', 'about:blank');
    plexampRecoveryTimer = window.setTimeout(() => {
      if (generation !== plexampRecoveryGeneration) return;
      frame.setAttribute('src', target.toString());
    }, 150);
  }

  function schedulePlexampFrameRecovery() {
    const generation = ++plexampRecoveryGeneration;
    const startedAt = Date.now();
    window.clearTimeout(plexampRecoveryTimer);

    const poll = async () => {
      if (generation !== plexampRecoveryGeneration) return;
      if (await plexampPlayerReady()) {
        plexampRecoveryTimer = window.setTimeout(
          () => reloadPlexampFrame(generation),
          750,
        );
        return;
      }
      if (Date.now() - startedAt >= 60000) return;
      plexampRecoveryTimer = window.setTimeout(poll, 1000);
    };

    plexampRecoveryTimer = window.setTimeout(poll, 500);
  }

  async function checkServiceRecovery() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        statusUnavailable = true;
        return;
      }

      const recoveredFromOutage = statusUnavailable;
      statusUnavailable = false;
      if (recoveredFromOutage) schedulePlexampFrameRecovery();
    } catch (error) {
      statusUnavailable = true;
    }
  }

  window.ACPServiceRecovery = Object.freeze({
    recoverPlexampFrame: schedulePlexampFrameRecovery,
    statusUnavailable: () => statusUnavailable,
  });

  window.addEventListener('pagehide', () => {
    ++plexampRecoveryGeneration;
    window.clearTimeout(plexampRecoveryTimer);
  });
  window.setInterval(checkServiceRecovery, 2000);
  window.setTimeout(checkServiceRecovery, 500);
})();
