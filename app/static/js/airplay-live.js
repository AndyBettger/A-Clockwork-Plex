(() => {
  const elements = {
    kicker: document.getElementById('airplay-state-kicker'),
    title: document.getElementById('airplay-title'),
    status: document.getElementById('airplay-status'),
    detail: document.getElementById('airplay-detail'),
    sessionState: document.getElementById('airplay-session-state'),
    sessionStarted: document.getElementById('airplay-session-started'),
    elapsed: document.getElementById('airplay-elapsed'),
    lastUpdate: document.getElementById('airplay-last-update'),
    plexampState: document.getElementById('airplay-plexamp-state'),
    returnState: document.getElementById('airplay-return-state'),
    liveDot: document.getElementById('airplay-live-dot'),
  };

  let activeStartedAt = null;
  let lastStatusMode = null;

  function parseDashboardTime(value) {
    if (!value) {
      return null;
    }

    const text = String(value).trim();
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(text);
    const date = new Date(hasTimezone ? text : text.replace(' ', 'T'));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatClockTime(date) {
    if (!date) {
      return '—';
    }

    return date.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  function formatDuration(totalSeconds) {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
    }

    return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`;
  }

  function setText(name, value) {
    if (elements[name]) {
      elements[name].textContent = value;
    }
  }

  function updateElapsed() {
    if (!activeStartedAt) {
      setText('elapsed', '—');
      return;
    }

    const elapsedSeconds = (Date.now() - activeStartedAt.getTime()) / 1000;
    setText('elapsed', formatDuration(elapsedSeconds));
  }

  function renderStatus(payload) {
    const state = payload?.state ?? {};
    const config = payload?.config ?? {};
    const airplayName = config?.airplay?.display_name || 'A Clockwork Plex';
    const mode = state.mode || 'unknown';
    const modeChangedAt = parseDashboardTime(state.last_mode_change);
    const isActive = mode === 'airplay';

    lastStatusMode = mode;
    activeStartedAt = isActive ? modeChangedAt : null;

    document.body.classList.toggle('airplay-session-active', isActive);
    document.body.classList.toggle('airplay-session-idle', !isActive);

    if (elements.liveDot) {
      elements.liveDot.setAttribute('aria-label', isActive ? 'AirPlay active' : 'AirPlay idle');
    }

    setText('title', airplayName);
    setText('kicker', isActive ? 'AirPlay route active' : 'AirPlay route idle');
    setText('status', isActive ? 'Receiving AirPlay audio now.' : 'AirPlay is not currently active.');
    setText(
      'detail',
      isActive
        ? 'Plexamp has been paused and stopped so Shairport Sync can use the DAC without a tug-of-war.'
        : 'The route is ready. Start AirPlay from the sending device and this screen will come alive.'
    );
    setText('sessionState', isActive ? 'Active' : 'Idle');
    setText('sessionStarted', isActive ? `Started at ${formatClockTime(modeChangedAt)}` : `Last mode: ${mode}`);
    setText('plexampState', isActive ? 'Stopped for DAC' : 'Ready to resume');
    setText('returnState', isActive ? 'Clock returns after stop' : 'Waiting for AirPlay');
    setText('lastUpdate', `Updated ${formatClockTime(new Date())}`);

    updateElapsed();
  }

  async function refreshStatus() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }

      renderStatus(await response.json());
    } catch (error) {
      setText('lastUpdate', 'Status update missed');
    }
  }

  setInterval(refreshStatus, 2000);
  setInterval(updateElapsed, 1000);
  refreshStatus();

  // A tiny safety net: if the page is left visible while the mode changes,
  // mode-watch.js will navigate away, but this gives the card immediate feedback.
  window.addEventListener('visibilitychange', () => {
    if (!document.hidden && lastStatusMode !== 'airplay') {
      refreshStatus();
    }
  });
})();
