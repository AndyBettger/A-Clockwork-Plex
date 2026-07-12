(() => {
  const button = document.getElementById('airplay-play-pause');
  const icon = document.getElementById('airplay-play-pause-icon');

  if (!button) {
    return;
  }

  const EVENT_FRESH_MS = 60 * 1000;

  function parseDashboardTime(value) {
    if (!value) {
      return null;
    }

    const text = String(value).trim();
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(text);
    const date = new Date(hasTimezone ? text : text.replace(' ', 'T'));
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function eventAgeMs(payload) {
    const updatedAt = parseDashboardTime(payload?.state?.airplay?.metadata?.updated_at);
    return updatedAt ? Date.now() - updatedAt.getTime() : Number.POSITIVE_INFINITY;
  }

  function eventPlaybackStatus(payload) {
    const event = String(payload?.state?.airplay?.metadata?.last_event || '').toLowerCase();
    if (event === 'pause') {
      return 'paused';
    }
    if (['resume', 'play_resume', 'play_start', 'active_state_start', 'metadata_start'].includes(event)) {
      return 'playing';
    }
    if (['play_end', 'active_state_end'].includes(event)) {
      return 'stopped';
    }
    return '';
  }

  function remotePlaybackStatus(payload) {
    return String(payload?.state?.airplay?.remote?.playback_status || '').toLowerCase();
  }

  function activeStartedAfterMetadataEvent(payload) {
    const airplay = payload?.state?.airplay || {};
    if (airplay.active !== true) {
      return false;
    }

    const startedAt = parseDashboardTime(airplay.started_at);
    const metadataUpdatedAt = parseDashboardTime(airplay.metadata?.updated_at);

    return Boolean(startedAt && metadataUpdatedAt && startedAt.getTime() >= metadataUpdatedAt.getTime() - 500);
  }

  function resolvedPlaybackStatus(payload) {
    const eventStatus = eventPlaybackStatus(payload);
    const remoteStatus = remotePlaybackStatus(payload);
    const freshEvent = eventAgeMs(payload) <= EVENT_FRESH_MS;

    // When the iPhone resumes after a dashboard pause, Shairport fires the start hook
    // and /api/airplay/start refreshes airplay.started_at, but the last metadata event
    // can still be active_state_end. Treat a newer active start as the winning signal.
    if (activeStartedAfterMetadataEvent(payload) && ['paused', 'stopped'].includes(eventStatus)) {
      return 'playing';
    }

    // Pauses from the iPhone often arrive as metadata before MPRIS stops reporting
    // Playing, so a fresh pause/stopped event should win briefly and avoid icon flicker.
    if (freshEvent && ['paused', 'stopped'].includes(eventStatus)) {
      return 'paused';
    }

    if (remoteStatus === 'playing') {
      return 'playing';
    }

    if (freshEvent && eventStatus === 'playing') {
      return 'playing';
    }

    return eventStatus || remoteStatus;
  }

  function syncButton(payload) {
    const active = payload?.state?.airplay?.active === true;
    const remote = payload?.state?.airplay?.remote || {};
    const status = resolvedPlaybackStatus(payload);
    const isPlaying = status === 'playing';
    const isPaused = status === 'paused' || status === 'stopped';
    const canControl = Boolean(active && (remote.can_control || remote.available));

    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', isPaused);

    button.disabled = !canControl;
    button.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');

    if (icon) {
      icon.textContent = isPlaying ? 'Ⅱ' : '▶';
    }
  }

  async function poll() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }
      syncButton(await response.json());
    } catch (error) {
    }
  }

  window.setInterval(poll, 500);
  window.setTimeout(poll, 250);
})();
