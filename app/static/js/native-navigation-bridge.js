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
  let reportingPaint = false;
  let lastSeen = 0;
  let lastPaletteAttemptAt = 0;
  let palettePublishing = false;

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

  function weatherContentReady() {
    // Header/title is present long before forecast panels finish loading.
    // Only inspect the *active* mounted Weather surface, never a cached hidden
    // wrapper; a missing optional forecast may still show station panels.
    const active = document.querySelector(
      '.acp-mounted-surface-weather:not([hidden])',
    );
    const page = active?.querySelector('.weather-detail-page')
      || (document.body.dataset.activePage === 'weather'
        ? document.querySelector('main.screen .weather-detail-page')
        : null);
    if (!page || page.dataset.acpForecastSettled !== 'true') return false;
    if (document.body.classList.contains('acp-page-booting')) return false;
    if (document.documentElement.classList.contains('acp-document-booting')) return false;
    const panel = page.querySelector(
      '.weather-forecast-panel .weather-forecast-card, '
      + '.weather-detail-grid .detail-panel, .weather-panel',
    );
    if (!panel) return false;
    const rect = panel.getBoundingClientRect();
    return rect.width > 12 && rect.height > 12
      && window.getComputedStyle(page).visibility !== 'hidden';
  }

  function contentReadyForPaint(command) {
    if (command.destination === 'weather') return weatherContentReady();
    return true;
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
      // Keep this short-lived command until Chromium gets actual foreground
      // focus and has a chance to draw; route-ready is not paint-ready.
    } catch (error) {
      // GTK keeps native Plexamp in front if ACP never becomes ready.
    } finally {
      acknowledging = false;
    }
  }

  async function reportPainted() {
    if (reportingPaint || !document.hasFocus()) return;
    const command = pendingHandoff();
    if (!command || !readyForHandoff(command) || !contentReadyForPaint(command)) return;
    reportingPaint = true;
    try {
      // Rendering while fully occluded can be throttled. Wait until Chromium
      // has compositor focus, then allow two actual animation-frame callbacks
      // before releasing the native GTK handoff curtain.
      await new Promise((resolve) => {
        window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
      });
      if (!document.hasFocus() || !readyForHandoff(command)
          || !contentReadyForPaint(command)) return;
      const response = await fetch('/api/native-navigation/painted', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sequence: command.sequence, destination: command.destination,
        }),
      });
      if (response.ok && pendingHandoff()?.sequence === command.sequence) {
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch (error) {
      // Bounded GTK preview will release the curtain on its own deadline.
    } finally {
      reportingPaint = false;
    }
  }

  async function publishPalette() {
    // Reuse the existing B3 polling callback, not a second background timer.
    // All values come from the currently computed ACP CSS, including night mode.
    const now = Date.now();
    if (palettePublishing || now - lastPaletteAttemptAt < 4000) return;
    lastPaletteAttemptAt = now;
    const drawer = document.querySelector('#nav-drawer');
    const button = drawer?.querySelector('.nav-workspaces .nav-button');
    const active = drawer?.querySelector('.nav-button.is-active');
    const handle = document.querySelector('#nav-handle span');
    const utilities = drawer?.querySelector('.nav-utilities');
    if (!drawer || !button || !active || !handle || !utilities) return;
    const styles = [drawer, button, active, handle, utilities].map(
      (node) => window.getComputedStyle(node),
    );
    const payload = {
      drawer_background: styles[0].backgroundColor,
      drawer_border: styles[0].borderTopColor,
      button_background: styles[1].backgroundColor,
      button_border: styles[1].borderTopColor,
      button_text: styles[1].color,
      active_background: styles[2].backgroundColor,
      active_text: styles[2].color,
      handle_color: styles[3].backgroundColor,
      utility_border: styles[4].borderLeftColor,
    };
    palettePublishing = true;
    try {
      await fetch('/api/native-navigation/palette', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      // Best-effort observational channel; never block navigation or the C3 OSK.
    } finally {
      palettePublishing = false;
    }
  }

  async function poll() {
    void publishPalette();
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
        // Native Plexamp is still foreground. A browser View Transition may
        // defer its rendering lifecycle while Chromium is occluded; stage the
        // destination *without* that animation, then wait for route readiness.
        // Normal ACP-to-ACP navigations still use the user's selected style.
        void window.ACPNavigate('/' + command.destination, {
          source: 'native-plexamp-b3',
          animate: false,
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
  const paintTimer = window.setInterval(reportPainted, 120);
  window.addEventListener('focus', reportPainted);
  window.addEventListener('pagehide', () => {
    window.clearInterval(pollTimer);
    window.clearInterval(readyTimer);
    window.clearInterval(paintTimer);
    window.removeEventListener('focus', reportPainted);
  });
})();
