(() => {
  const originalButton = document.getElementById('airplay-play-pause');
  if (!originalButton || !originalButton.parentNode) {
    return;
  }

  // airplay-live.js still owns metadata, artwork, progress and volume. It keeps
  // references to the original transport elements, so replace the visible node
  // and leave those legacy references detached and harmless.
  const button = originalButton.cloneNode(true);
  originalButton.replaceWith(button);

  const icon = button.querySelector('#airplay-play-pause-icon');
  const detail = document.getElementById('airplay-detail');
  const STATE_URL = '/api/playback/state';
  const CONTROL_URL = '/api/airplay/control';
  const POLL_MS = 750;
  const OPTIMISTIC_MS = 15000;

  let commandPending = false;
  let latestCoordinatorState = null;
  let optimisticState = null;

  function normaliseState(value) {
    const state = String(value || '').trim().toLowerCase();
    if (state === 'playing' || state === 'paused' || state === 'connected' || state === 'disconnected') {
      return state;
    }
    return 'unknown';
  }

  function setDetail(message) {
    if (detail && message) {
      detail.textContent = message;
    }
  }

  function effectiveState(coordinatorState) {
    const current = normaliseState(coordinatorState);
    if (!optimisticState) {
      return current;
    }
    if (current === optimisticState.state || current === 'disconnected') {
      optimisticState = null;
      return current;
    }
    if (Date.now() >= optimisticState.expiresAt) {
      optimisticState = null;
      return current;
    }
    return optimisticState.state;
  }

  function render(playback) {
    const source = playback?.sources?.airplay || {};
    const observed = source.observed || {};
    const connected = source.connected === true;
    const coordinatorState = normaliseState(source.state);
    const state = effectiveState(coordinatorState);
    const serviceCanControl = observed.can_control === true
      || observed.can_play === true
      || observed.can_pause === true;
    const canControl = connected && serviceCanControl;
    const action = state === 'playing' ? 'pause' : 'play';

    latestCoordinatorState = coordinatorState;
    button.dataset.playbackAction = action;
    button.dataset.coordinatorState = coordinatorState;
    button.disabled = commandPending || !canControl;
    button.setAttribute('aria-label', action === 'pause' ? 'Pause AirPlay' : 'Play AirPlay');
    button.setAttribute('aria-busy', commandPending ? 'true' : 'false');

    if (icon) {
      icon.textContent = action === 'pause' ? 'Ⅱ' : '▶';
    }

    document.body.classList.toggle('airplay-remote-playing', state === 'playing');
    document.body.classList.toggle('airplay-remote-paused', state === 'paused');
  }

  async function refresh() {
    try {
      const response = await fetch(STATE_URL, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      render(payload?.playback || {});
    } catch (error) {
      button.disabled = true;
      button.setAttribute('aria-busy', 'false');
      setDetail('Playback state is temporarily unavailable. No transport guess was made.');
    }
  }

  async function sendExplicitCommand() {
    if (button.disabled || commandPending) {
      return;
    }

    const action = button.dataset.playbackAction === 'pause' ? 'pause' : 'play';
    const targetState = action === 'pause' ? 'paused' : 'playing';
    commandPending = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(CONTROL_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.ok !== true) {
        throw new Error(payload?.error || `HTTP ${response.status}`);
      }

      optimisticState = {
        state: targetState,
        expiresAt: Date.now() + OPTIMISTIC_MS,
      };
      render({
        sources: {
          airplay: {
            connected: true,
            state: latestCoordinatorState,
            observed: payload?.remote || { can_control: true },
          },
        },
      });
    } catch (error) {
      optimisticState = null;
      setDetail(`AirPlay ${action} command was not accepted. The coordinator state was left unchanged.`);
    } finally {
      commandPending = false;
      setTimeout(refresh, 250);
    }
  }

  button.addEventListener('click', sendExplicitCommand);
  window.setInterval(refresh, POLL_MS);
  window.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      refresh();
    }
  });

  window.AirPlayPlaybackStateClient = Object.freeze({ refresh });
  refresh();
})();
