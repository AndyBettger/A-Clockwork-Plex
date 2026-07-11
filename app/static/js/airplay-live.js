(() => {
  const elements = {
    kicker: document.getElementById('airplay-state-kicker'),
    title: document.getElementById('airplay-title'),
    primaryMeta: document.getElementById('airplay-primary-meta'),
    sourceTitle: document.getElementById('airplay-source-title'),
    detail: document.getElementById('airplay-detail'),
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
    miniClock: document.getElementById('airplay-mini-clock'),
    miniHours: document.getElementById('airplay-mini-hours'),
    miniMinutes: document.getElementById('airplay-mini-minutes'),
    miniSeconds: document.getElementById('airplay-mini-seconds'),
    miniDate: document.getElementById('airplay-mini-date'),
    outsideNow: document.getElementById('airplay-outside-now'),
    outsideDetail: document.getElementById('airplay-outside-detail'),
    barometerLabel: document.getElementById('airplay-barometer-label'),
    barometerNow: document.getElementById('airplay-barometer-now'),
    barometerDetail: document.getElementById('airplay-barometer-detail'),
  };

  const SEGMENTS = {
    '0': ['a', 'b', 'c', 'd', 'e', 'f'],
    '1': ['b', 'c'],
    '2': ['a', 'b', 'g', 'e', 'd'],
    '3': ['a', 'b', 'g', 'c', 'd'],
    '4': ['f', 'g', 'b', 'c'],
    '5': ['a', 'f', 'g', 'c', 'd'],
    '6': ['a', 'f', 'g', 'e', 'c', 'd'],
    '7': ['a', 'b', 'c'],
    '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    '9': ['a', 'b', 'c', 'd', 'f', 'g'],
  };

  let activeStartedAt = null;
  let lastStatusMode = null;
  let lastGoodMetadata = null;
  let lastTrackKey = null;
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

  function isUsefulValue(value) {
    const text = String(value || '').trim();
    return Boolean(text && text !== '—' && text.toLowerCase() !== 'none');
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

    return 'iPhone';
  }

  function receivingText(metadata) {
    return `Receiving AirPlay from ${sourceLabel(metadata)}.`;
  }

  function cleanDisplayTitle(value) {
    const title = String(value || '').trim();
    if (!title) {
      return title;
    }

    const timeChunk = String.raw`(?:\d+\s*(?:h|hr|hrs|hour|hours)\s*)?(?:\d+\s*(?:m|min|mins|minute|minutes)\s*)?(?:\d+\s*(?:s|sec|secs|second|seconds)\s*)?`;
    const remainingSuffixes = [
      new RegExp(String.raw`\s*[\(\[]\s*(?:about\s+)?${timeChunk}remaining\s*[\)\]]\s*$`, 'i'),
      new RegExp(String.raw`\s*[—–-]\s*(?:about\s+)?${timeChunk}remaining\s*$`, 'i'),
    ];

    return remainingSuffixes
      .reduce((text, pattern) => text.replace(pattern, ''), title)
      .trim();
  }

  function creatorText(metadata) {
    return String(
      metadata?.artist
      || metadata?.album_artist
      || metadata?.composer
      || metadata?.genre
      || ''
    ).trim();
  }

  function sourceTitleText(metadata, cleanTitle) {
    const candidates = [metadata?.album, metadata?.genre, metadata?.format]
      .map((value) => cleanDisplayTitle(value))
      .filter(Boolean)
      .filter((value) => value !== cleanTitle);
    return candidates[0] || '';
  }

  function setScrollingText(element, value) {
    if (!element) {
      return;
    }

    const text = String(value || '').trim();
    const container = element.parentElement;
    element.textContent = text;

    if (!container) {
      return;
    }

    container.hidden = !text;
    container.classList.remove('is-overflowing');
    container.style.removeProperty('--airplay-source-overflow');

    if (!text) {
      return;
    }

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const measuredOverflow = Math.max(0, element.scrollWidth - container.clientWidth);
        const estimatedOverflow = Math.max(0, Math.ceil(text.length * 11.5) - container.clientWidth);
        const overflow = Math.max(measuredOverflow, estimatedOverflow);

        if (overflow > 8 || text.length > 34) {
          container.style.setProperty('--airplay-source-overflow', `${Math.max(overflow, 48)}px`);
          container.classList.add('is-overflowing');
        }
      });
    });
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

  function usefulMetadata(metadata) {
    return Boolean(metadata?.title || metadata?.artist || metadata?.album || metadata?.artwork_url);
  }

  function trackKeyForMetadata(metadata) {
    if (!usefulMetadata(metadata)) {
      return null;
    }

    return [cleanDisplayTitle(metadata?.title), metadata?.artist || metadata?.album_artist, metadata?.album]
      .map((value) => String(value || '').trim())
      .join('\u0001');
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

    const sourceKey = String(
      progress.raw
      || `${progress.start ?? ''}/${progress.current ?? elapsedSeconds}/${progress.end ?? durationSeconds}`
    );

    return {
      percent: clamp(percent, 0, 100),
      elapsedSeconds: clamp(elapsedSeconds, 0, durationSeconds),
      durationSeconds,
      sourceKey,
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
      remainingSeconds: Math.max(0, progressState.durationSeconds - elapsedSeconds),
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
    setText('progressDuration', `-${formatDuration(snapshot.remainingSeconds)}`);
  }

  function updateProgressFromMetadata(progress, hasFreshMetadata, playbackStatus) {
    if (!hasFreshMetadata || !progress) {
      setProgressDisplay(currentProgressSnapshot(), Boolean(progressState));
      return;
    }

    const now = Date.now();
    const incomingUpdatedAt = progress.updatedAt ? progress.updatedAt.getTime() : now;
    const shouldAcceptIncoming = !progressState
      || progress.sourceKey !== progressState.sourceKey
      || Math.abs(progress.durationSeconds - progressState.durationSeconds) > 1;

    if (shouldAcceptIncoming) {
      progressState = {
        sourceKey: progress.sourceKey,
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
        setText('detail', 'Volume command missed. The volume goblin looked busy.');
      } finally {
        volumeHoldUntil = Date.now() + 3000;
      }
    }, 180);
  }

  function makeDigit(value) {
    const digit = document.createElement('span');
    digit.className = 'digital-digit';
    digit.setAttribute('aria-hidden', 'true');

    for (const segment of ['a', 'b', 'c', 'd', 'e', 'f', 'g']) {
      const element = document.createElement('span');
      element.className = `segment segment-${segment}`;
      if (SEGMENTS[value].includes(segment)) {
        element.classList.add('is-on');
      }
      digit.appendChild(element);
    }

    return digit;
  }

  function setDigits(element, value) {
    if (!element) {
      return;
    }
    element.replaceChildren(...value.split('').map(makeDigit));
  }

  function updateMiniClock() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const weekday = now.toLocaleDateString('en-GB', { weekday: 'short' });
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const year = now.getFullYear();
    const date = `${weekday} ${day}/${month}/${year}`;

    setDigits(elements.miniHours, hours);
    setDigits(elements.miniMinutes, minutes);
    setDigits(elements.miniSeconds, seconds);
    if (elements.miniClock) {
      elements.miniClock.setAttribute('aria-label', `${hours}:${minutes}:${seconds}`);
    }
    setText('miniDate', date);
  }

  function updateWeatherGlance(payload) {
    const detail = payload?.weather_detail || {};
    const conditionRows = Array.isArray(detail.condition_rows) ? detail.condition_rows : [];
    const outdoor = conditionRows.find((row) => String(row?.location || '').toLowerCase() === 'outdoor') || conditionRows[0] || {};
    const temp = outdoor?.temperature?.current;
    const humidity = outdoor?.humidity?.current;
    const outsideParts = [temp, humidity].filter(isUsefulValue);

    setText('outsideNow', outsideParts.length ? outsideParts.join(' · ') : 'Waiting');
    setText('outsideDetail', '');

    const barometer = detail.barometer || {};
    const forecast = isUsefulValue(barometer.forecast_title) ? barometer.forecast_title : '';
    const pressure = barometer.pressure?.value;
    const trend = barometer.trend;

    setText('barometerLabel', forecast ? `Barometer · ${forecast}` : 'Barometer');
    setText('barometerNow', isUsefulValue(pressure) ? pressure : forecast || 'Waiting');
    setText('barometerDetail', isUsefulValue(trend) ? trend : 'Pressure data pending');
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
    const isActive = airplay.active === true;
    const hasFreshMetadata = isActive && metadataIsFresh(metadata, startedAt);
    const displayMetadata = displayMetadataForSession(metadata, isActive, hasFreshMetadata, startedAt);
    const hasDisplayMetadata = isActive && usefulMetadata(displayMetadata);
    const title = hasDisplayMetadata && displayMetadata.title ? cleanDisplayTitle(displayMetadata.title) : airplayName;
    const creator = hasDisplayMetadata ? creatorText(displayMetadata) : '';
    const sourceTitle = hasDisplayMetadata ? sourceTitleText(displayMetadata, title) : '';
    const source = sourceLabel(displayMetadata);
    const progress = normaliseProgress(displayMetadata.progress);
    const playbackStatus = activePlaybackStatus(remote);
    const trackKey = hasDisplayMetadata ? trackKeyForMetadata(displayMetadata) : null;

    latestRemote = remote;
    lastStatusMode = mode;
    activeStartedAt = isActive ? startedAt : null;

    if (!isActive) {
      progressState = null;
      optimisticPlayback = null;
      lastTrackKey = null;
    } else if (trackKey && lastTrackKey && trackKey !== lastTrackKey) {
      progressState = null;
    }

    if (trackKey) {
      lastTrackKey = trackKey;
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
    updateWeatherGlance(payload);

    setText('title', title || airplayName);
    setText('kicker', isActive ? (hasDisplayMetadata ? 'AirPlay now playing' : 'AirPlay route active') : 'AirPlay route ready');

    if (isActive && hasDisplayMetadata) {
      setText('primaryMeta', creator || receivingText(displayMetadata));
      setScrollingText(elements.sourceTitle, sourceTitle);
      setText('detail', `Receiving AirPlay from ${source}. The tune tunnel is open and behaving itself.`);
    } else if (isActive) {
      setText('primaryMeta', receivingText(displayMetadata));
      setScrollingText(elements.sourceTitle, '');
      setText('detail', 'Waiting for track details. The metadata goblin has been politely summoned.');
    } else {
      setText('primaryMeta', 'Ready for AirPlay connections.');
      setScrollingText(elements.sourceTitle, '');
      setText('detail', `Choose ${airplayName} from the AirPlay menu. The airwaves are clear, the apples are polished, and the DAC is waiting.`);
    }
  }

  async function refreshStatus() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (!response.ok) {
        return;
      }

      renderStatus(await response.json());
    } catch (error) {
      setText('detail', 'Status update missed. The AirPlay goblin may be stretching its legs.');
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
      setText('detail', 'Playback command missed. The iPhone may have wandered off.');
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
    updateMiniClock();
    updateProgressTick();
  }, 1000);
  updateMiniClock();
  refreshStatus();

  window.addEventListener('visibilitychange', () => {
    if (!document.hidden && lastStatusMode !== 'airplay') {
      refreshStatus();
    }
  });
})();