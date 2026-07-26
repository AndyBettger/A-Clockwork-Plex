(() => {
  const originalButton = document.getElementById('airplay-play-pause');
  if (!originalButton || !originalButton.parentNode) {
    return;
  }

  // airplay-live.js still owns metadata, artwork and progress. It keeps
  // references to the original transport elements, so replace the visible node
  // and leave those legacy references detached and harmless.
  const button = originalButton.cloneNode(true);
  originalButton.replaceWith(button);

  const icon = button.querySelector('#airplay-play-pause-icon');
  const detail = document.getElementById('airplay-detail');
  const STATE_URL = '/api/playback/state';
  const COMMAND_URL = '/api/playback/command';
  const POLL_MS = 750;

  let commandPending = false;

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

  function render(playback) {
    const source = playback?.sources?.airplay || {};
    const observed = source.observed || {};
    const command = playback?.commands?.airplay || {};
    const capabilities = playback?.command_capabilities || {};
    const connected = source.connected === true;
    const state = normaliseState(source.state);
    const serviceCanControl = observed.can_control === true
      || observed.can_play === true
      || observed.can_pause === true;
    const coordinatorCanControl = capabilities.airplay_transport === true;
    const canControl = connected && serviceCanControl && coordinatorCanControl;
    const action = state === 'playing' ? 'pause' : 'play';

    button.dataset.playbackAction = action;
    button.dataset.coordinatorState = state;
    button.dataset.commandStatus = String(command.status || 'idle');
    button.disabled = commandPending || !canControl;
    button.setAttribute('aria-label', action === 'pause' ? 'Pause AirPlay' : 'Play AirPlay');
    button.setAttribute('aria-busy', commandPending ? 'true' : 'false');
    button.title = command.status && command.status !== 'idle'
      ? `AirPlay ${command.action || action}: ${command.status}`
      : '';

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
    commandPending = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(COMMAND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'airplay', action }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.ok !== true) {
        throw new Error(payload?.error || `HTTP ${response.status}`);
      }
      render(payload?.playback || {});
    } catch (error) {
      setDetail(`AirPlay ${action} command was not accepted. ${error.message || 'Coordinator state was left unchanged.'}`);
    } finally {
      commandPending = false;
      button.setAttribute('aria-busy', 'false');
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
