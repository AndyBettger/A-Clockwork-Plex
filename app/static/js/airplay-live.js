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
    playPauseButton: document.getElementById('airplay-play-pause'),
    playPauseIcon: document.getElementById('airplay-play-pause-icon'),
  };

  let activeStartedAt = null;
  let lastStatusMode = null;
  let latestProgress = null;
  let latestProgressUpdatedAt = null;
  let latestPlaybackStatus = null;
  let volumeDragActive = false;
  let volumeCommitTimer = null;

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

  function liveProgress(progress) {
    if (!progress) {
      return null;
    }

    let elapsedSeconds = progress.elapsedSeconds;
    if (latestPlaybackStatus === 'Playing' && latestProgressUpdatedAt) {
      elapsedSeconds += (Date.now() - latestProgressUpdatedAt.getTime()) / 1000;
    }

    elapsedSeconds = clamp(elapsedSeconds, 0, progress.durationSeconds);
    return {
      elapsedSeconds,
      durationSeconds: progress.durationSeconds,
      percent: progress.durationSeconds > 0 ? clamp((elapsedSeconds / progress.durationSeconds) * 100, 0, 100) : progress.percent,
    };
  }

  function renderProgress() {
    const progress = liveProgress(latestProgress);
    const showProgress = Boolean(progress);

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

  function setProgress(progress, hasFreshMetadata, metadataUpdatedAt) {
    latestProgress = hasFreshMetadata ? progress : null;
    latestProgressUpdatedAt = metadataUpdatedAt || null;
    renderProgress();
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

  function displayVolumePercent(metadata, remote) {
    if (remote && Number.isFinite(Number(remote.volume_percent))) {
      return Number(remote.volume_percent);
    }
    return volumePercentFromDb(metadata?.volume_db);
  }

  function setVolumeDisplay(metadata, remote, hasFreshMetadata) {
    const volumePercent = displayVolumePercent(metadata, remote);
    const volumeLabel = metadata?.volume || (Number.isFinite(volumePercent) ? `${Math.round(volumePercent)}%` : '');
    const showVolume = Boolean(hasFreshMetadata && volumePercent !== null && volumeLabel);

    if (elements.volumeStrip) {
      elements.volumeStrip.hidden = !showVolume;
    }

    if (!showVolume) {
      document.body.style.removeProperty('--airplay-volume-percent');
      return;
    }

    const clampedPercent = clamp(Number(volumePercent), 0, 100);
    document.body.style.setProperty('--airplay-volume-percent', `${clampedPercent}%`);

    if (elements.volumeSlider && !volumeDragActive) {
      elements.volumeSlider.disabled = false;
      elements.volumeSlider.value = String(Math.round(clampedPercent));
    }

    setText('volumeLabel', volumeLabel);
  }

  function updatePlaybackControls(isActive, remote) {
    latestPlaybackStatus = remote?.playback_status || null;
    const isPlaying = latestPlaybackStatus === 'Playing';
    const canControl = Boolean(isActive && remote?.available && remote?.can_control);

    document.body.classList.toggle('airplay-remote-playing', isPlaying);
    document.body.classList.toggle('airplay-remote-paused', latestPlaybackStatus === 'Paused');

    if (elements.playPauseButton) {
      elements.playPauseButton.disabled = !canControl;
      elements.playPauseButton.setAttribute('aria-label', isPlaying ? 'Pause AirPlay' : 'Play AirPlay');
      elements.playPauseButton.title = isPlaying ? 'Pause AirPlay' : 'Play AirPlay';
    }

    if (elements.playPauseIcon) {
      elements.playPauseIcon.textContent = isPlaying ? '⏸' : '▶';
    }
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
    const remote = airplay.remote ?? {};
    const airplayName = config?.airplay?.display_name || 'A Clockwork Plex';
    const mode = state.mode || 'unknown';
    const startedAt = parseDashboardTime(airplay.started_at);
    const endedAt = parseDashboardTime(airplay.ended_at);
    const metadataUpdatedAt = parseDashboardTime(metadata.updated_at);
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

    updatePlaybackControls(isActive, remote);
    setArtwork(metadata.artwork_url, hasFreshMetadata);
    setProgress(progress, hasFreshMetadata, metadataUpdatedAt);
    setVolumeDisplay(metadata, remote, hasFreshMetadata);
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

    setText('sessionState', isActive ? (remote?.playback_status || 'Active') : 'Ready');
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

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    return response.json();
  }

  async function sendPlayPause() {
    if (!elements.playPauseButton || elements.playPauseButton.disabled) {
      return;
    }

    elements.playPauseButton.disabled = true;
    try {
      await postJson('/api/airplay/control', { action: 'play_pause' });
      setTimeout(refreshStatus, 250);
    } catch (error) {
      setText('lastUpdate', 'Play/pause command failed');
    } finally {
      setTimeout(() => {
        refreshStatus();
      }, 900);
    }
  }

  function commitVolume(value) {
    const volumePercent = clamp(Number(value), 0, 100);
    document.body.style.setProperty('--airplay-volume-percent', `${volumePercent}%`);
    if (elements.volumeSlider) {
      elements.volumeSlider.value = String(Math.round(volumePercent));
    }
    setText('volumeLabel', `${Math.round(volumePercent)}%`);

    clearTimeout(volumeCommitTimer);
    volumeCommitTimer = setTimeout(async () => {
      try {
        await postJson('/api/airplay/volume', { volume_percent: volumePercent });
        setTimeout(refreshStatus, 350);
      } catch (error) {
        setText('volumeLabel', 'Volume failed');
      }
    }, 180);
  }

  if (elements.playPauseButton) {
    elements.playPauseButton.addEventListener('click', sendPlayPause);
  }

  if (elements.volumeSlider) {
    elements.volumeSlider.addEventListener('pointerdown', () => {
      volumeDragActive = true;
    });
    elements.volumeSlider.addEventListener('pointerup', () => {
      volumeDragActive = false;
      commitVolume(elements.volumeSlider.value);
    });
    elements.volumeSlider.addEventListener('pointercancel', () => {
      volumeDragActive = false;
      refreshStatus();
    });
    elements.volumeSlider.addEventListener('input', () => {
      commitVolume(elements.volumeSlider.value);
    });
    elements.volumeSlider.addEventListener('change', () => {
      volumeDragActive = false;
      commitVolume(elements.volumeSlider.value);
    });
  }

  setInterval(refreshStatus, 2000);
  setInterval(updateElapsed, 1000);
  setInterval(renderProgress, 1000);
  refreshStatus();

  // A tiny safety net: if the page is left visible while the mode changes,
  // mode-watch.js will navigate away, but this gives the card immediate feedback.
  window.addEventListener('visibilitychange', () => {
    if (!document.hidden && lastStatusMode !== 'airplay') {
      refreshStatus();
    }
  });
})();
