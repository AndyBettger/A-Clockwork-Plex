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
    thirdCardLabel: document.getElementById('airplay-third-card-label'),
    plexampState: document.getElementById('airplay-plexamp-state'),
    returnState: document.getElementById('airplay-return-state'),
    liveDot: document.getElementById('airplay-live-dot'),
    artwork: document.getElementById('airplay-artwork'),
    artworkImg: document.getElementById('airplay-artwork-img'),
    glyph: document.getElementById('airplay-glyph'),
    progress: document.getElementById('airplay-progress'),
    progressElapsed: document.getElementById('airplay-progress-elapsed'),
    progressDuration: document.getElementById('airplay-progress-duration'),
    progressFill: document.getElementById('airplay-progress-fill'),
    volumeStrip: document.getElementById('airplay-volume-strip'),
    volumeSlider: document.getElementById('airplay-volume-slider'),
    volumeLabel: document.getElementById('airplay-volume-label'),
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
    if (!Number.isFinite(totalSeconds)) {
      return '—';
    }

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

  function clamp(number, min, max) {
    return Math.min(max, Math.max(min, number));
  }

  function sourceLabel(metadata) {
    const candidates = [
      metadata?.source_name,
      metadata?.source_model,
      metadata?.player_name,
    ];

    const firstUseful = candidates
      .map((value) => String(value || '').trim())
      .find((value) => value && !/^airplay\//i.test(value));

    if (firstUseful) {
      return firstUseful;
    }

    const userAgent = String(metadata?.source_user_agent || '');
    if (/airplay/i.test(userAgent)) {
      return 'iPhone';
    }

    // Most real use here is iPhone → Pi. If Shairport later gives us a friendly
    // source name, the candidates above will win and this fallback disappears.
    return 'iPhone';
  }

  function receivingText(metadata) {
    return `Receiving AirPlay from ${sourceLabel(metadata)}.`;
  }

  function setArtwork(url, hasFreshMetadata) {
    const showArtwork = Boolean(url && hasFreshMetadata && elements.artworkImg);
    document.body.classList.toggle('airplay-has-artwork', showArtwork);

    if (showArtwork) {
      document.body.style.setProperty('--airplay-artwork-url', `url(${JSON.stringify(url)})`);
    } else {
      document.body.style.removeProperty('--airplay-artwork-url');
    }

    if (elements.artworkImg) {
      if (showArtwork && elements.artworkImg.getAttribute('src') !== url) {
        elements.artworkImg.src = url;
      }
      elements.artworkImg.hidden = !showArtwork;
    }

    if (elements.glyph) {
      elements.glyph.hidden = showArtwork;
    }
  }

  function metadataIsFresh(metadata, startedAt) {
    if (!metadata || !metadata.available) {
      return false;
    }

    const updatedAt = parseDashboardTime(metadata.updated_at);
    if (!updatedAt) {
      return false;
    }

    return !startedAt || updatedAt >= startedAt;
  }

  function metadataSummary(metadata) {
    const artist = metadata.artist || metadata.album_artist || '';
    const album = metadata.album || '';
    const genre = metadata.genre || '';
    const parts = [];

    if (artist) {
      parts.push(artist);
    }
    if (album) {
      parts.push(album);
    }
    if (!artist && !album && genre) {
      parts.push(genre);
    }

    return parts.join(' · ');
  }

  function normaliseProgress(progress) {
    if (!progress || typeof progress !== 'object') {
      return null;
    }

    const percent = Number(progress.percent);
    const elapsedSeconds = Number(progress.elapsed_seconds);
    const durationSeconds = Number(progress.duration_seconds);

    if (!Number.isFinite(percent) || !Number.isFinite(elapsedSeconds) || !Number.isFinite(durationSeconds) || durationSeconds <= 0) {
      return null;
    }

    return {
      percent: clamp(percent, 0, 100),
      elapsedSeconds: clamp(elapsedSeconds, 0, durationSeconds),
      durationSeconds,
    };
  }

  function setProgress(progress, hasFreshMetadata) {
    const showProgress = Boolean(hasFreshMetadata && progress);

    if (elements.progress) {
      elements.progress.hidden = !showProgress;
    }

    if (!showProgress) {
      document.body.style.removeProperty('--airplay-progress-percent');
      return;
    }

    document.body.style.setProperty('--airplay-progress-percent', `${progress.percent}%`);
    setText('progressElapsed', formatDuration(progress.elapsedSeconds));
    setText('progressDuration', formatDuration(progress.durationSeconds));
  }

  function volumePercentFromDb(volumeDb) {
    const db = Number(volumeDb);
    if (!Number.isFinite(db)) {
      return null;
    }
    if (db <= -96) {
      return 0;
    }
    if (db >= 0) {
      return 100;
    }

    // AirPlay reports volume in dB below full scale. This is a display mapping,
    // not a claim that the iPhone slider is perfectly linear.
    return Math.round(clamp(((db + 30) / 30) * 100, 0, 100));
  }

  function setVolumeDisplay(metadata, hasFreshMetadata) {
    const volumePercent = volumePercentFromDb(metadata?.volume_db);
    const showVolume = Boolean(hasFreshMetadata && volumePercent !== null && metadata?.volume);

    if (elements.volumeStrip) {
      elements.volumeStrip.hidden = !showVolume;
    }

    if (!showVolume) {
      document.body.style.removeProperty('--airplay-volume-percent');
      return;
    }

    document.body.style.setProperty('--airplay-volume-percent', `${volumePercent}%`);

    if (elements.volumeSlider) {
      elements.volumeSlider.value = String(volumePercent);
    }

    setText('volumeLabel', metadata.volume);
  }

  function updateElapsed() {
    if (!activeStartedAt) {
      setText('elapsed', 'Standing by');
      return;
    }

    const elapsedSeconds = (Date.now() - activeStartedAt.getTime()) / 1000;
    setText('elapsed', formatDuration(elapsedSeconds));
  }

  function renderStatus(payload) {
    const state = payload?.state ?? {};
    const config = payload?.config ?? {};
    const airplay = state.airplay ?? {};
    const metadata = airplay.metadata ?? {};
    const airplayName = config?.airplay?.display_name || 'A Clockwork Plex';
    const mode = state.mode || 'unknown';
    const startedAt = parseDashboardTime(airplay.started_at);
    const endedAt = parseDashboardTime(airplay.ended_at);
    const isActive = airplay.active === true;
    const hasFreshMetadata = isActive && metadataIsFresh(metadata, startedAt);
    const title = hasFreshMetadata && metadata.title ? metadata.title : airplayName;
    const summary = hasFreshMetadata ? metadataSummary(metadata) : '';
    const source = sourceLabel(metadata);
    const progress = normaliseProgress(metadata.progress);

    lastStatusMode = mode;
    activeStartedAt = isActive ? startedAt : null;

    document.body.classList.toggle('airplay-session-active', isActive);
    document.body.classList.toggle('airplay-session-idle', !isActive);
    document.body.classList.toggle('airplay-metadata-active', hasFreshMetadata);

    if (elements.liveDot) {
      elements.liveDot.setAttribute('aria-label', isActive ? 'AirPlay active' : 'AirPlay ready');
    }

    setArtwork(metadata.artwork_url, hasFreshMetadata);
    setProgress(progress, hasFreshMetadata);
    setVolumeDisplay(metadata, hasFreshMetadata);
    setText('title', title);
    setText('kicker', isActive ? (hasFreshMetadata ? 'AirPlay now playing' : 'AirPlay route active') : 'AirPlay route ready');

    if (isActive && hasFreshMetadata) {
      setText('status', summary || receivingText(metadata));
      setText('detail', `Receiving AirPlay from ${source}. The tune tunnel is open and behaving itself.`);
    } else if (isActive) {
      setText('status', receivingText(metadata));
      setText('detail', 'Waiting for track details. The metadata goblin has been politely summoned.');
    } else {
      setText('status', 'Ready for AirPlay connections.');
      setText('detail', `Choose ${airplayName} from the AirPlay menu. The airwaves are clear, the apples are polished, and the DAC is waiting.`);
    }

    setText('sessionState', isActive ? 'Active' : 'Ready');
    setText(
      'sessionStarted',
      isActive
        ? `Started ${formatClockTime(startedAt)}`
        : endedAt
          ? `Ended ${formatClockTime(endedAt)}`
          : 'Waiting for AirPlay'
    );
    setText('thirdCardLabel', hasFreshMetadata && metadata.volume ? 'Volume' : 'Plexamp');
    setText('plexampState', hasFreshMetadata && metadata.volume ? metadata.volume : isActive ? 'DAC released' : 'Available');
    setText(
      'returnState',
      hasFreshMetadata && metadata.updated_at
        ? `Metadata ${formatClockTime(parseDashboardTime(metadata.updated_at))}`
        : isActive
          ? 'Clock returns after stop'
          : `Pick ${airplayName} to begin`
    );
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
