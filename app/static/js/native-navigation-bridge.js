(() => {
  if (window.__ACPDevNativeNavigationBridgeLoaded) return;
  window.__ACPDevNativeNavigationBridgeLoaded = true;
  // Only the local Pi kiosk may act on its native Plexamp navigation mailbox.
  if (!['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) return;

  const STORAGE_KEY = 'a-clockwork-plex.b3-native-handoff';
  const ROUTES = new Set(['clock', 'weather', 'news', 'airplay', 'settings', 'audio']);
  const MAX_AGE_MS = 12000;
  let polling = false;
  let acknowledging = false;
  let lastSeen = 0;

  function saveHandoff(command) {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        sequence: command.sequence,
        destination: command.destination,
        at: Date.now(),
      }));
      return true;
    } catch (error) {
      return false;
    }
  }

  function pendingHandoff() {
    let command = null;
    try {
      command = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || 'null');
    } catch (error) {
      // Ignore malformed developer-only state.
    }
    if (!Number.isSafeInteger(command?.sequence) || command.sequence < 1
        || !ROUTES.has(command.destination)
        || !Number.isFinite(command.at)
        || Date.now() - command.at < 0
        || Date.now() - command.at > MAX_AGE_MS) {
      try { window.sessionStorage.removeItem(STORAGE_KEY); } catch (error) {}
      return null;
    }
    return command;
  }

  function readyForHandoff(command) {
    if (window.ACPNavigationState?.isPresenting?.()) return false;
    if (command.destination === 'audio') {
      return document.body.classList.contains('nav-audio-open');
    }
    return window.ACPNavigationState?.activeRoute?.() === '/' + command.destination;
  }

  async function acknowledgePresented() {
    if (acknowledging) return;
    const command = pendingHandoff();
    if (!command || !readyForHandoff(command)) return;
    // Open ACP's existing drawer before the native window releases focus.
    window.ACPNavDrawer?.show?.();
    if (!document.body.classList.contains('nav-open')) return;
    acknowledging = true;
    try {
      const response = await fetch('/api/native-navigation/ready', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sequence: command.sequence, destination: command.destination,
        }),
      });
      if (!response.ok) return;
      if (pendingHandoff()?.sequence === command.sequence) {
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch (error) {
      // GTK keeps native Plexamp in front if ACP never becomes ready.
    } finally {
      acknowledging = false;
    }
  }

  async function poll() {
    if (polling || typeof window.ACPNavigate !== 'function') return;
    polling = true;
    try {
      const response = await fetch('/api/native-navigation/next', { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      const command = payload?.command;
      if (!command || !Number.isSafeInteger(command.sequence)
          || command.sequence <= lastSeen || !ROUTES.has(command.destination)) return;
      lastSeen = command.sequence;
      if (!saveHandoff(command)) return;

      window.ACPNavDrawer?.show?.();
      if (command.destination === 'audio') {
        window.ACPNavDrawer?.ensureAudioPanel?.();
        const button = document.getElementById('nav-audio-button');
        if (button && !document.body.classList.contains('nav-audio-open')) button.click();
      } else {
        void window.ACPNavigate('/' + command.destination, {
          source: 'native-plexamp-b3',
        });
      }
    } catch (error) {
      // Dashboard can be unavailable during a development restart.
    } finally {
      polling = false;
    }
  }

  const pollTimer = window.setInterval(poll, 600);
  const readyTimer = window.setInterval(acknowledgePresented, 150);
  window.addEventListener('pagehide', () => {
    window.clearInterval(pollTimer);
    window.clearInterval(readyTimer);
  });
})();
