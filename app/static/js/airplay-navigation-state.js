(() => {
  const legacyBack = document.getElementById('airplay-skip-back');
  const legacyForward = document.getElementById('airplay-skip-forward');
  if (!legacyBack?.parentNode || !legacyForward?.parentNode) return;

  // airplay-extra-controls.js remains the presentation classifier for now. Clone
  // its buttons so the visible controls have no legacy command listeners, while
  // the detached originals continue choosing track-skip or spoken ±15s artwork.
  const backButton = legacyBack.cloneNode(true);
  const forwardButton = legacyForward.cloneNode(true);
  legacyBack.replaceWith(backButton);
  legacyForward.replaceWith(forwardButton);

  const buttons = [backButton, forwardButton];
  const presentationPairs = [
    [legacyBack, backButton],
    [legacyForward, forwardButton],
  ];
  const detail = document.getElementById('airplay-detail');
  const STATE_URL = '/api/playback/state';
  const COMMAND_URL = '/api/playback/command';
  const POLL_MS = 750;

  let commandPending = false;
  let connected = false;
  let canNavigate = false;
  let refreshTimer = null;

  function copyPresentation(legacy, visible) {
    visible.className = legacy.className;
    visible.innerHTML = legacy.innerHTML;
    visible.dataset.airplayDirection = legacy.dataset.airplayDirection || '';
    visible.dataset.airplayAction = legacy.dataset.airplayAction || '';
    visible.dataset.airplaySkipMode = legacy.dataset.airplaySkipMode || 'track';
    const label = legacy.getAttribute('aria-label');
    if (label) visible.setAttribute('aria-label', label);
  }

  for (const [legacy, visible] of presentationPairs) {
    copyPresentation(legacy, visible);
  }

  const observers = presentationPairs.map(([legacy, visible]) => {
    const observer = new MutationObserver(() => copyPresentation(legacy, visible));
    observer.observe(legacy, {
      attributes: true,
      childList: true,
      subtree: true,
      characterData: true,
      attributeFilter: ['class', 'aria-label', 'data-airplay-skip-mode'],
    });
    return observer;
  });

  function setDetail(message) {
    if (detail && message) detail.textContent = message;
  }

  function syncDisabledState() {
    for (const button of buttons) {
      button.disabled = commandPending || !connected || !canNavigate;
      button.setAttribute('aria-busy', commandPending ? 'true' : 'false');
    }
  }

  function render(playback) {
    const source = playback?.sources?.airplay || {};
    const observed = source.observed || {};
    const capabilities = playback?.command_capabilities || {};
    const navigation = playback?.commands?.airplay_navigation || {};

    connected = source.connected === true;
    canNavigate = capabilities.airplay_navigation === true
      && observed.available === true
      && observed.can_control !== false;

    for (const button of buttons) {
      button.hidden = !connected;
      const action = button.dataset.airplayAction || '';
      button.title = navigation.action === action && navigation.status !== 'idle'
        ? `AirPlay ${action}: ${navigation.status}`
        : '';
    }
    syncDisabledState();
  }

  async function refresh() {
    try {
      const response = await fetch(STATE_URL, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      render(payload?.playback || {});
    } catch (error) {
      connected = false;
      canNavigate = false;
      syncDisabledState();
    }
  }

  async function sendNavigation(action) {
    if (commandPending || !connected || !canNavigate) return;
    if (action !== 'previous' && action !== 'next') return;

    commandPending = true;
    syncDisabledState();
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
      window.dispatchEvent(new Event('airplay-control-sent'));
    } catch (error) {
      setDetail(`AirPlay ${action} command was not accepted. ${error.message || 'Coordinator state was left unchanged.'}`);
    } finally {
      commandPending = false;
      syncDisabledState();
      window.setTimeout(refresh, 250);
    }
  }

  backButton.addEventListener('click', () => sendNavigation('previous'));
  forwardButton.addEventListener('click', () => sendNavigation('next'));

  refreshTimer = window.setInterval(refresh, POLL_MS);
  window.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
  });
  window.addEventListener('pagehide', () => {
    window.clearInterval(refreshTimer);
    for (const observer of observers) observer.disconnect();
  });

  window.AirPlayNavigationStateClient = Object.freeze({ refresh });
  refresh();
})();
