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
  let lastGoodMetadata = null;
  let progressState = null;
  let optimisticPlayback = null;
  let volumeHoldUntil = 0;
  let volumeSendTimer = null;
  let latestVolumePercent = null;
  let latestRemote = null;

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

  function isPlayingStatus(status) {
    return String(status || '').toLowerCase() === 'playing';
  }

  function activePlaybackStatus(remote) {
    if (optimisticPlayback && Date.now() < optimisticPlayback.expiresAt) {
      return optimisticPlayback.status;
    }
    return remote?.playback_status || 'Unknown';
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

  function setArtwork(url, showArtwork) {
    const shouldShow = Boolean(url && showArtwork && elements.artworkImg);
    document.body.classList.toggle('airplay-has-artwork', shouldShow);

    if (shouldShow) {
      document.body.style.setProperty('--airplay-artwork-url', `url(${JSON.stringify(url)})`);
    } else {
      document.body.style.removeProperty('--airplay-artwork-url');
    }

    if (elements.artworkImg) {
      if (shouldShow && elements.artworkImg.getAttribute('src') !== url) {
        elements.artworkImg.src = url;
      }
      elements.artworkImg.hidden = !shouldShow;
    }

    if (elements.glyph) {
      elements.glyph.hidden = shouldShow;
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

  function usefulMetadata(metadata) {
    return Boolean(metadata?.title || metadata?.artist || metadata?.album || metadata?.artwork_url);
  }

  function displayMetadataForSession(metadata, isActive, hasFreshMetadata, startedAt) {
    if (hasFreshMetadata && usefulMetadata(metadata)) {
      lastGoodMetadata = { ...metadata, rememberedAt: Date.now() };
      return metadata;
    }

    if (!isActive || !lastGoodMetadata) {
      return metadata;
    }

    const rememberedAt = parseDashboardTime(lastGoodMetadata.updated_at);
    if (startedAt && rememberedAt && rememberedAt < startedAt) {
      return metadata;
    }

    return lastGoodMetadata;
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
      updatedAt: parseDashboardTime(progress.updated_at) || null,
    };
  }

  function currentProgressSnapshot() {
    if (!progressState) {
      return null;
    }

    const playbackStatus = activePlaybackStatus(latestRemote);
    const runningSeconds = isPlayingStatus(playbackStatus)
      ? (Date.now() - progressState.baseTimeMs) / 1000
      : 0;
    const elapsedSeconds = clamp(progressState.baseElapsedSeconds + runningSeconds, 0, progressState.durationSeconds);
    const percent = progressState.durationSeconds > 0
      ? (elapsedSeconds / progressState.durationSeconds) * 100
      : progressState.percent;

    return {
      elapsedSeconds,
      durationSeconds: progressState.durationSeconds,
      percent: clamp(percent, 0, 100),
    };
  }

  function setProgressDisplay(snapshot, showProgress) {
    const shouldShow = Boolean(showProgress && snapshot);

    if (elements.progress) {
      elements.progress.hidden = !shouldShow;
    }

    if (!shouldShow) {
      document.body.style.removeProperty('--airplay-progress-percent');
      return;
    }

    document.body.style.setProperty('--airplay-progress-percent', `${snapshot.percent}%`);
    setText('progressElapsed', formatDuration(snapshot.elapsedSeconds));
    setText('progressDuration', formatDuration(snapshot.durationSeconds));
  }

  function updateProgressFromMetadata(progress, hasFreshMetadata, playbackStatus) {
    if (!hasFreshMetadata || !progress) {
      setProgressDisplay(currentProgressSnapshot(), Boolean(progressState));
      return;
    }

    const now = Date.now();
    const incomingUpdatedAt = progress.updatedAt ? progress.updatedAt.getTime() : now;
    const currentSnapshot = currentProgressSnapshot();
    const shouldAcceptIncoming = !progressState
      || incomingUpdatedAt >= progressState.sourceUpdatedAtMs
      || Math.abs(progress.elapsedSeconds - (currentSnapshot?.elapsedSeconds ?? progress.elapsedSeconds)) > 2.5;

    if (shouldAcceptIncoming) {
      progressState = {
        baseElapsedSeconds: progress.elapsedSeconds,
        durationSeconds: progress.durationSeconds,
        percent: progress.percent,
        baseTimeMs: isPlayingStatus(playbackStatus) ? now : incomingUpdatedAt,
        sourceUpdatedAtMs: incomingUpdatedAt,
      };
    }

    setProgressDisplay(currentProgressSnapshot(), true);
  }

  function updateProgressTick() {
    setProgressDisplay(currentProgressSnapshot(), Boolean(progressState));
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

  function displayVolumePercent(percent, label = null) {
    const cleanPercent = clamp(Number(percent), 0, 100);
    latestVolumePercent = cleanPercent;
    document.body.style.setProperty('--airplay-volume-percent', `${cleanPercent}%`);

    if (elements.volumeSlider) {
      elements.volumeSlider.value = String(Math.round(cleanPercent));
    }

    if (label !== null) {
      setText('volumeLabel', label);
    }
  }

  function setVolumeDisplay(metadata, remote, hasFreshMetadata) {
    const mprisPercent = Number.isFinite(Number(remote?.volume_percent)) ? Number(remote.volume_percent) : null;
    const metadataPercent = volumePercentFromDb(metadata?.volume_db);
    const volumePercent = mprisPercent ?? metadataPercent;
    const showVolume = Boolean(hasFreshMetadata && volumePercent !== null);

    if (elements.volumeStrip) {
      elements.volumeStrip.hidden = !showVolume;
    }

    if (!showVolume) {
      document.body.style.removeProperty('--airplay-volume-percent');
      return;
    }

    if (elements.volumeSlider) {
      elements.volumeSlider.disabled = remote?.can_set_volume === false;
    }

    if (Date.now() < volumeHoldUntil && latestVolumePercent !== null) {
      displayVolumePercent(latestVolumePercent, elements.volumeLabel?.textContent || null);
      return;
    }

    displayVolumePercent(volumePercent, metadata?.volume || `${Math.round(volumePercent)}%`);
  }

  function dbFromUiPercent(percent) {
    const cleanPercent = clamp(Number(percent), 0, 100);
    if (cleanPercent <= 0) {
      return 'Muted';
    }
    const db = (cleanPercent / 100) * 30 - 30;
    return `${db.toFixed(1)} dB`;
  }

  function queueVolumeSend(percent) {
    if (volumeSendTimer) {
      clearTimeout(volumeSendTimer);
    }

    volumeSendTimer = setTimeout(async () => {
      volumeSendTimer = null;
      try {
        const response = await fetch('/api/airplay/volume', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ volume_percent: Number(percent) }),
        });
        const payload = await response.json().catch(() => ({}));
        if (payload?.remote) {
          latestRemote = payload.remote;
        }
      } catch (error) {
        setText('lastUpdate', 'Volume command missed');
      } finally {
        volumeHoldUntil = Date.now() + 3000;
      }
    }, 180);
  }

  function updateElapsed() {
    if (!activeStartedAt) {
      setText('elapsed', 'Standing by');
      return;
    }

    const elapsedSeconds = (Date.now() - activeStartedAt.getTime()) / 1000;
    setText('elapsed', formatDuration(elapsedSeconds));
  }

  function setPlaybackButton(remote, isActive) {
    const status = activePlaybackStatus(remote);
    const canControl = Boolean(remote?.available && remote?.can_control && (remote?.can_play || remote?.can_pause));

    document.body.classList.toggle('airplay-remote-paused', String(status).toLowerCase() === 'paused');
    document.body.classList.toggle('airplay-remote-playing', isPlayingStatus(status));

    if (elements.playPauseButton) {
      elements.playPauseButton.disabled = !(isActive && canControl);
      elements.playPauseButton.setAttribute('aria-label', isPlayingStatus(status) ? 'Pause AirPlay' : 'Play AirPlay');
    }

    if (elements.playPauseIcon) {
      elements.playPauseIcon.textContent = isPlayingStatus(status) ? 'Ⅱ' : '▶';
    }
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
    const isActive = airplay.active === true;
    const hasFreshMetadata = isActive && metadataIsFresh(metadata, startedAt);
    const displayMetadata = displayMetadataForSession(metadata, isActive, hasFreshMetadata, startedAt);
    const hasDisplayMetadata = isActive && usefulMetadata(displayMetadata);
    const title = hasDisplayMetadata && displayMetadata.title ? displayMetadata.title : airplayName;
    const summary = hasDisplayMetadata ? metadataSummary(displayMetadata) : '';
    const source = sourceLabel(displayMetadata);
    const progress = normaliseProgress(displayMetadata.progress);
    const playbackStatus = activePlaybackStatus(remote);

    latestRemote = remote;
    lastStatusMode = mode;
    activeStartedAt = isActive ? startedAt : null;

    if (!isActive) {
      progressState = null;
      optimisticPlayback = null;
    }

    document.body.classList.toggle('airplay-session-active', isActive);
    document.body.classList.toggle('airplay-session-idle', !isActive);
    document.body.classList.toggle('airplay-metadata-active', hasDisplayMetadata);

    if (elements.liveDot) {
      elements.liveDot.setAttribute('aria-label', isActive ? 'AirPlay active' : 'AirPlay ready');
    }

    setArtwork(displayMetadata.artwork_url, hasDisplayMetadata);
    updateProgressFromMetadata(progress, hasDisplayMetadata, playbackStatus);
    setVolumeDisplay(displayMetadata, remote, hasDisplayMetadata);
    setPlaybackButton(remote, isActive);
    setText('title', title);
    setText('kicker', isActive ? (hasDisplayMetadata ? 'AirPlay now playing' : 'AirPlay route active') : 'AirPlay route ready');

    if (isActive && hasDisplayMetadata) {
      setText('status', summary || receivingText(displayMetadata));
      setText('detail', `Receiving AirPlay from ${source}. The tune tunnel is open and behaving itself.`);
    } else if (isActive) {
      setText('status', receivingText(displayMetadata));
      setText('detail', 'Waiting for track details. The metadata goblin has been politely summoned.');
    } else {
      setText('status', 'Ready for AirPlay connections.');
      setText('detail', `Choose ${airplayName} from the AirPlay menu. The airwaves are clear, the apples are polished, and the DAC is waiting.`);
    }

    const sessionLabel = isActive
      ? (isPlayingStatus(playbackStatus) ? 'Playing' : String(playbackStatus || 'Active'))
      : 'Ready';

    setText('sessionState', sessionLabel);
    setText(
      'sessionStarted',
      isActive
        ? `Started ${formatClockTime(startedAt)}`
        : endedAt
          ? `Ended ${formatClockTime(endedAt)}`
          : 'Waiting for AirPlay'
    );
    setText('thirdCardLabel', hasDisplayMetadata && displayMetadata.volume ? 'Volume' : 'Plexamp');
    setText('plexampState', hasDisplayMetadata && displayMetadata.volume ? displayMetadata.volume : isActive ? 'DAC released' : 'Available');
    setText(
      'returnState',
      hasDisplayMetadata && displayMetadata.updated_at
        ? `Metadata ${formatClockTime(parseDashboardTime(displayMetadata.updated_at))}`
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

  async function sendPlaybackToggle() {
    if (!elements.playPauseButton || elements.playPauseButton.disabled) {
      return;
    }

    const currentStatus = activePlaybackStatus(latestRemote);
    const nextStatus = isPlayingStatus(currentStatus) ? 'Paused' : 'Playing';
    const snapshot = currentProgressSnapshot();

    if (snapshot && progressState) {
      progressState.baseElapsedSeconds = snapshot.elapsedSeconds;
      progressState.baseTimeMs = Date.now();
    }

    optimisticPlayback = {
      status: nextStatus,
      expiresAt: Date.now() + 6000,
    };
    setPlaybackButton(latestRemote, true);
    updateProgressTick();

    try {
      const response = await fetch('/api/airplay/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'play_pause' }),
      });
      const payload = await response.json().catch(() => ({}));
      if (payload?.remote) {
        latestRemote = payload.remote;
        optimisticPlayback = {
          status: payload.remote.playback_status || nextStatus,
          expiresAt: Date.now() + 2500,
        };
        setPlaybackButton(latestRemote, true);
      }
    } catch (error) {
      setText('lastUpdate', 'Playback command missed');
    } finally {
      setTimeout(refreshStatus, 1200);
    }
  }

  if (elements.playPauseButton) {
    elements.playPauseButton.addEventListener('click', sendPlaybackToggle);
  }

  if (elements.volumeSlider) {
    const handleVolumeInput = () => {
      const percent = Number(elements.volumeSlider.value);
      volumeHoldUntil = Date.now() + 3500;
      displayVolumePercent(percent, dbFromUiPercent(percent));
      queueVolumeSend(percent);
    };

    elements.volumeSlider.addEventListener('pointerdown', () => {
      volumeHoldUntil = Date.now() + 4000;
    });
    elements.volumeSlider.addEventListener('input', handleVolumeInput);
    elements.volumeSlider.addEventListener('change', handleVolumeInput);
    elements.volumeSlider.addEventListener('pointerup', () => {
      volumeHoldUntil = Date.now() + 3500;
      setTimeout(refreshStatus, 1400);
    });
  }

  setInterval(refreshStatus, 2000);
  setInterval(() => {
    updateElapsed();
    updateProgressTick();
  }, 1000);
  refreshStatus();

  // A tiny safety net: if the page is left visible while the mode changes,
  // mode-watch.js will navigate away, but this gives the card immediate feedback.
  window.addEventListener('visibilitychange', () => {
    if (!document.hidden && lastStatusMode !== 'airplay') {
      refreshStatus();
    }
  });
})();
