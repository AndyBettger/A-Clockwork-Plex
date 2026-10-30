(() => {
  if (window.__ACPSharedNativeNavOwnerLoaded) return;
  window.__ACPSharedNativeNavOwnerLoaded = true;
  // The browser merely follows a short-lived local GTK lease; it cannot
  // grant a lease, start GTK, turn on the OSK or change compositor focus.
  if (!['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) return;

  const CLASS = 'acp-b4-gtk-owned';
  const ENDPOINT = '/api/native-navigation/chrome-owner';
  const POLL_MS = 700;
  let checking = false;
  let disposed = false;

  function release() {
    document.body.classList.remove(CLASS);
  }

  async function check() {
    if (disposed || checking) return;
    // Only a foreground ACP document should surrender its browser chrome.
    // If an audio panel or alarm has ownership, retain the known-good UI.
    if (!document.hasFocus()
        || document.body.classList.contains('nav-audio-open')
        || document.body.classList.contains('mode-alarm')
        || document.body.dataset.activePage === 'alarm') {
      release();
      return;
    }
    checking = true;
    try {
      const response = await fetch(ENDPOINT, { cache: 'no-store' });
      const body = response.ok ? await response.json() : null;
      if (!response.ok || body?.ok !== true || body?.active !== true
          || !document.hasFocus() || disposed) {
        release();
        return;
      }
      // Remove any open browser drawer and its nav-mode presentation BEFORE
      // hiding its handle. This does not mutate the current ACP page route.
      if (document.body.classList.contains('nav-open')) {
        window.ACPNavDrawer?.hide?.();
      }
      document.body.classList.add(CLASS);
    } catch (error) {
      // Server restart, GTK death/timeout or connection failure: browser wins.
      release();
    } finally {
      checking = false;
    }
  }

  const timer = window.setInterval(() => { void check(); }, POLL_MS);
  window.addEventListener('focus', () => { void check(); });
  window.addEventListener('blur', release);
  window.addEventListener('pagehide', () => {
    disposed = true;
    window.clearInterval(timer);
    release();
  });
  void check();
})();
