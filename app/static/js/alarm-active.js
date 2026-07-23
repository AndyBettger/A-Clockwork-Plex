(() => {
  const STATUS_ENDPOINT = '/api/alarms/active';
  const SNOOZE_ENDPOINT = '/api/alarms/snooze';
  const DISMISS_ENDPOINT = '/api/alarms/dismiss';
  const REFRESH_MS = 1000;
  const DISMISS_THRESHOLD = 0.8;
  const KEYBOARD_HOLD_MS = 1500;

  const byId = (id) => document.getElementById(id);
  const timeElement = byId('alarm-current-time');
  const dateElement = byId('alarm-current-date');
  const labelElement = byId('alarm-active-label');
  const sourceElement = byId('alarm-active-source');
  const statusElement = byId('alarm-active-status');
  const footerElement = byId('alarm-active-footer');
  const audioLockElement = document.querySelector('.alarm-audio-lock');
  const snoozeButton = byId('alarm-snooze-button');
  const snoozeDuration = byId('alarm-snooze-duration');
  const dismissTrack = byId('alarm-dismiss-track');
  const dismissHandle = byId('alarm-dismiss-handle');

  let activeOccurrence = null;
  let requestInFlight = false;
  let refreshTimer = null;
  let dragPointerId = null;
  let dragStartX = 0;
  let dragProgress = 0;
  let holdTimer = null;

  function updateClock() {
    const now = new Date();
    const timeText = new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(now);
    const dateText = new Intl.DateTimeFormat('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(now);
    if (timeElement) {
      timeElement.textContent = timeText;
      timeElement.dateTime = now.toISOString();
    }
    if (dateElement) {
      dateElement.textContent = dateText;
    }
  }

  function returnPath(clear = false) {
    let path = '/clock';
    try {
      path = window.sessionStorage.getItem('alarmReturnPath') || '/clock';
      if (clear) {
        window.sessionStorage.removeItem('alarmReturnPath');
      }
    } catch (error) {
      path = '/clock';
    }
    if (!path.startsWith('/') || path === '/alarm') {
      return '/clock';
    }
    return path;
  }

  function leaveAlarmScreen(clearReturnPath = false) {
    window.location.replace(returnPath(clearReturnPath));
  }

  function setBusy(busy, message = '') {
    requestInFlight = busy;
    if (snoozeButton) {
      snoozeButton.disabled = busy;
      snoozeButton.classList.toggle('is-busy', busy);
    }
    if (dismissHandle) {
      dismissHandle.disabled = busy;
    }
    if (message && statusElement) {
      statusElement.textContent = message;
    }
  }

  function audioDisplay(active, payload, toneLabel) {
    const audio = payload?.audio || {};
    const currentMatches = String(audio.current_occurrence_key || '') === String(active.occurrence_key || '');
    const playing = Boolean(audio.playback_active && currentMatches);
    const armed = Boolean(active.test_mode && Number(audio.armed_occurrence_count) > 0);
    const action = String(audio.last_action?.action || '');
    const finished = currentMatches && ['playback-finished', 'playback-stopped', 'playback-stop-requested'].includes(action);
    const fallback = audio.fallback_used ? ' · emergency fallback' : '';

    if (playing) {
      return {
        chip: 'Controlled audio test · sounding',
        source: `${audio.current_tone_label || toneLabel} · real local audio${fallback}`,
        status: audio.fallback_used
          ? 'The selected tone could not be used, so the Emergency Buzzer fallback is sounding.'
          : 'The controlled local-audio test is active. Snooze or Dismiss stops it immediately.',
        footer: 'Test-only audio is enabled; ordinary scheduled alarms remain unable to make sound.',
      };
    }
    if (finished) {
      return {
        chip: 'Controlled audio test · complete',
        source: `${audio.current_tone_label || toneLabel} · test cycle finished${fallback}`,
        status: audio.last_error || 'The timed audio test has finished. The alarm screen remains available for Snooze and Dismiss testing.',
        footer: 'The test cycle stopped automatically and previous audio services were restored where possible.',
      };
    }
    if (armed) {
      return {
        chip: 'Controlled audio test · starting',
        source: `${toneLabel} · local audio armed`,
        status: audio.last_error || 'The alarm screen is active and the audio manager is acquiring the output device.',
        footer: 'This occurrence was explicitly armed from Settings; scheduled alarms remain silent.',
      };
    }
    return {
      chip: active.test_mode ? 'Visual test · audio locked' : 'Scheduled alarm · audio locked',
      source: `${toneLabel} · playback disabled${active.test_mode ? ' · visual test' : ''}`,
      status: 'The alarm is active on screen. This occurrence was not explicitly armed to make sound.',
      footer: active.test_mode
        ? 'Visual test mode: dismissing or clearing this alarm will not alter its saved schedule.'
        : 'Screen takeover is active; scheduled audio remains behind the safety lock.',
    };
  }

  function renderPayload(payload) {
    const active = payload?.active;
    const screenRequired = Boolean(payload?.screen_required);
    if (!active || !screenRequired) {
      leaveAlarmScreen(false);
      return;
    }

    activeOccurrence = active;
    const snoozeMinutes = Number(active.snooze_minutes) || 8;
    const toneLabel = payload.tone_label || active?.source?.tone_id || 'Local tone';
    const snoozeCount = Number(active.snooze_count) || 0;
    const audio = audioDisplay(active, payload, toneLabel);

    if (labelElement) {
      labelElement.textContent = active.label || 'Alarm';
    }
    if (audioLockElement) {
      audioLockElement.textContent = audio.chip;
    }
    if (sourceElement) {
      sourceElement.textContent = audio.source;
    }
    if (snoozeDuration) {
      snoozeDuration.textContent = `${snoozeMinutes} min`;
    }
    if (statusElement) {
      statusElement.textContent = snoozeCount
        ? `This alarm has been snoozed ${snoozeCount} time${snoozeCount === 1 ? '' : 's'}. ${audio.status}`
        : audio.status;
    }
    if (footerElement) {
      footerElement.textContent = audio.footer;
    }
  }

  async function refreshStatus() {
    if (requestInFlight) {
      return;
    }
    try {
      const response = await fetch(STATUS_ENDPOINT, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Alarm status returned ${response.status}.`);
      }
      renderPayload(payload);
    } catch (error) {
      if (statusElement) {
        statusElement.textContent = error.message || 'Could not read the active alarm state.';
      }
    }
  }

  async function postAction(endpoint, busyMessage) {
    if (requestInFlight) {
      return null;
    }
    setBusy(true, busyMessage);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || `Alarm action returned ${response.status}.`);
      }
      return payload;
    } catch (error) {
      setBusy(false, error.message || 'Alarm action failed.');
      return null;
    }
  }

  async function snoozeAlarm() {
    const payload = await postAction(SNOOZE_ENDPOINT, 'Stopping audio and snoozing…');
    if (payload) {
      leaveAlarmScreen(false);
    }
  }

  async function dismissAlarm() {
    const payload = await postAction(DISMISS_ENDPOINT, 'Stopping audio and dismissing alarm…');
    if (!payload) {
      resetDismissHandle();
      return;
    }
    if (dismissTrack) {
      dismissTrack.classList.add('is-complete');
      dismissTrack.querySelector('.alarm-dismiss-copy').textContent = 'Alarm dismissed';
    }
    window.setTimeout(() => leaveAlarmScreen(true), 450);
  }

  function maximumHandleTravel() {
    if (!dismissTrack || !dismissHandle) {
      return 0;
    }
    const trackWidth = dismissTrack.getBoundingClientRect().width;
    const handleWidth = dismissHandle.getBoundingClientRect().width;
    return Math.max(0, trackWidth - handleWidth - 10);
  }

  function setDismissProgress(progress, immediate = false) {
    dragProgress = Math.max(0, Math.min(1, progress));
    const travel = maximumHandleTravel();
    if (dismissHandle) {
      dismissHandle.style.transition = immediate ? 'none' : '';
      dismissHandle.style.transform = `translateX(${travel * dragProgress}px)`;
    }
    if (dismissTrack) {
      dismissTrack.style.setProperty('--dismiss-progress', String(dragProgress));
    }
  }

  function resetDismissHandle() {
    if (dismissHandle) {
      dismissHandle.classList.remove('is-dragging', 'is-holding');
      dismissHandle.style.transition = '';
    }
    if (dismissTrack) {
      dismissTrack.classList.remove('is-complete');
    }
    setDismissProgress(0, false);
  }

  function beginDrag(event) {
    if (requestInFlight || !dismissHandle) {
      return;
    }
    dragPointerId = event.pointerId;
    dragStartX = event.clientX - (maximumHandleTravel() * dragProgress);
    dismissHandle.setPointerCapture?.(event.pointerId);
    dismissHandle.classList.add('is-dragging');
    event.preventDefault();
  }

  function moveDrag(event) {
    if (event.pointerId !== dragPointerId || requestInFlight) {
      return;
    }
    const travel = maximumHandleTravel();
    setDismissProgress(travel ? (event.clientX - dragStartX) / travel : 0, true);
    event.preventDefault();
  }

  function endDrag(event) {
    if (event.pointerId !== dragPointerId) {
      return;
    }
    dragPointerId = null;
    dismissHandle?.classList.remove('is-dragging');
    if (dragProgress >= DISMISS_THRESHOLD) {
      setDismissProgress(1, false);
      dismissAlarm();
    } else {
      resetDismissHandle();
    }
    event.preventDefault();
  }

  function clearKeyboardHold() {
    if (holdTimer) {
      window.clearTimeout(holdTimer);
      holdTimer = null;
    }
    dismissHandle?.classList.remove('is-holding');
  }

  function beginKeyboardHold(event) {
    if (!['Enter', ' '].includes(event.key) || event.repeat || requestInFlight) {
      return;
    }
    event.preventDefault();
    clearKeyboardHold();
    dismissHandle?.classList.add('is-holding');
    holdTimer = window.setTimeout(() => {
      holdTimer = null;
      dismissHandle?.classList.remove('is-holding');
      setDismissProgress(1, false);
      dismissAlarm();
    }, KEYBOARD_HOLD_MS);
  }

  function endKeyboardHold(event) {
    if (!['Enter', ' '].includes(event.key)) {
      return;
    }
    event.preventDefault();
    if (holdTimer) {
      clearKeyboardHold();
      resetDismissHandle();
    }
  }

  snoozeButton?.addEventListener('click', snoozeAlarm);
  dismissHandle?.addEventListener('pointerdown', beginDrag);
  dismissHandle?.addEventListener('pointermove', moveDrag);
  dismissHandle?.addEventListener('pointerup', endDrag);
  dismissHandle?.addEventListener('pointercancel', endDrag);
  dismissHandle?.addEventListener('keydown', beginKeyboardHold);
  dismissHandle?.addEventListener('keyup', endKeyboardHold);
  dismissHandle?.addEventListener('blur', () => {
    clearKeyboardHold();
    if (!requestInFlight) {
      resetDismissHandle();
    }
  });

  window.addEventListener('resize', () => setDismissProgress(dragProgress, true));
  window.addEventListener('pagehide', () => {
    clearKeyboardHold();
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
  });

  updateClock();
  window.setInterval(updateClock, 1000);
  refreshStatus();
  refreshTimer = window.setInterval(refreshStatus, REFRESH_MS);
})();
