(() => {
  if (window.__ACPDevNativeNavigationBridgeLoaded) return;
  window.__ACPDevNativeNavigationBridgeLoaded = true;
  // No remote/LAN browsers may consume commands meant for local Chromium.
  if (!['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) return;

  let pending = false;
  let lastSeen = 0;
  async function poll() {
    if (pending || typeof window.ACPNavigate !== 'function') return;
    pending = true;
    try {
      const response = await fetch('/api/native-navigation/next', { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      const command = payload?.command;
      if (!command || !Number.isSafeInteger(command.sequence)
          || command.sequence <= lastSeen) return;
      lastSeen = command.sequence;
      const allowed = new Set(['clock', 'weather', 'news', 'airplay', 'settings', 'audio']);
      if (!allowed.has(command.destination)) return;

      window.ACPNavDrawer?.show?.();
      if (command.destination === 'audio') {
        window.ACPNavDrawer?.ensureAudioPanel?.();
        const button = document.getElementById('nav-audio-button');
        if (button) button.click();
      } else {
        void window.ACPNavigate('/' + command.destination, {
          source: 'native-plexamp-b3',
        });
      }
    } catch (error) {
      // Dashboard may be temporarily unavailable during development restart.
    } finally {
      pending = false;
    }
  }
  const timer = window.setInterval(poll, 600);
  window.addEventListener('pagehide', () => window.clearInterval(timer));
})();
