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
  // Retry the same consumed command after an ACP screen lease becomes idle.
  const STAGE_RETRY_MS = 1200;
  const MAX_STAGE_ATTEMPTS = 6;
  let staging = null;

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

    // A matching URL/route is not enough. During native Plexamp handoff the
    // background browser may still have a stale Clock surface, a visible
    // Chromium Plexamp overlay, or a screen-projection recommendation that
    // disagrees with the requested destination. Never focus until the same
    // existing control service that owns ACP's manual page selection confirms
    // this surface's lease and the mounted destination is actually visible.
    const destination = command.destination;
    const route = '/' + destination;
    if (window.ACPNavigationState?.activeRoute?.() !== route
        || window.ACPSurfaceHost?.activeRoute?.() !== route
        || window.ACPPlexamp?.isVisiblyOpen?.() === true) return false;

    const projection = window.ACPScreenProjection?.state?.();
    if (projection?.recommended_screen !== destination
        || projection?.lease?.active !== true
        || projection?.lease?.manual_surface !== destination) return false;

    return Boolean(document.querySelector(
      '.acp-mounted-surface-' + destination + ':not([hidden])',
    ));
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
    const button = drawer?.querySelector('.nav-workspaces .nav-button:not(.is-active)');
    const active = drawer?.querySelector('.nav-button.is-active');
    const handle = document.querySelector('#nav-handle span');
    const utilities = drawer?.querySelector('.nav-utilities');
    if (!drawer || !button || !active || !handle || !utilities) return;
    const styles = [drawer, button, active, handle, utilities].map(
      (node) => window.getComputedStyle(node),
    );
    // The effective ACP CSS defines exact hover and press colours.
    const root = window.getComputedStyle(document.documentElement);
    const astronomyNight = document.body.classList.contains('acp-night-dim-active')
      && document.body.classList.contains('acp-night-style-astronomy')
      && !document.body.classList.contains('mode-alarm')
      && document.body.dataset.activePage !== 'alarm';
    const buttonHover = styles[1].getPropertyValue('--acp-nav-hover-fill').trim();
    const buttonPressed = styles[1].getPropertyValue('--acp-nav-pressed-fill').trim();
    // The page's CSS owns the curtain hue, including Astronomy Red; send only
    // one opaque colour token rather than copying gradients or accepting CSS.
    const curtainFill = window.getComputedStyle(document.body)
      .getPropertyValue('--acp-b3-curtain-fill').trim();
    if (!buttonHover || !buttonPressed || !curtainFill) return;
    const payload = {
      curtain_background: curtainFill,
      drawer_background: styles[0].backgroundColor,
      drawer_border: styles[0].borderTopColor,
      button_background: styles[1].backgroundColor,
      button_hover_background: buttonHover,
      button_pressed_background: buttonPressed,
      button_border: styles[1].borderTopColor,
      button_text: styles[1].color,
      active_background: styles[2].backgroundColor,
      active_text: styles[2].color,
      handle_color: styles[3].backgroundColor,
      utility_border: styles[4].borderLeftColor,
    };
    // Geometry and night brightness remain a separate, opt-in snapshot;
    // hover and press colours are read-only styling, not preferences.
    const px = (value) => Number.parseFloat(value) || 0;
    const rawBrightness = px(root.getPropertyValue('--acp-night-brightness'));
    const presentation = {
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      drawer_width: drawer.getBoundingClientRect().width,
      drawer_height: drawer.getBoundingClientRect().height,
      drawer_bottom: px(styles[0].bottom),
      drawer_padding: px(styles[0].paddingTop),
      workspace_gap: px(window.getComputedStyle(drawer.querySelector('.nav-workspaces')).gap),
      utility_gap: px(window.getComputedStyle(utilities).gap),
      button_height: button.getBoundingClientRect().height,
      utility_size: utilities.querySelector('.nav-utility-button')?.getBoundingClientRect().width || 0,
      font_size: px(styles[1].fontSize),
      night_brightness: astronomyNight
        ? Math.min(1, Math.max(0.05, rawBrightness || 0.18)) : 1,
      astronomy_night: astronomyNight,
    };
    // Fail closed on missing nodes or nonsensical dimensions.
    const validMeasurements = Number.isFinite(presentation.drawer_width)
      && presentation.drawer_width >= 200
      && presentation.drawer_height >= 40
      && presentation.utility_size >= 24;
    palettePublishing = true;
    try {
      await fetch('/api/native-navigation/palette', {
        method: 'POST',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (validMeasurements) {
        await fetch('/api/native-navigation/presentation', {
          method: 'POST',
          cache: 'no-store',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(presentation),
        });
      }
    } catch (error) {
      // Best-effort observational channel; never block navigation or the C3 OSK.
    } finally {
      palettePublishing = false;
    }
  }

  function stagePendingHandoff() {
    const command = pendingHandoff();
    if (!command || typeof window.ACPNavigate !== 'function') return;
    if (!staging || staging.sequence !== command.sequence) {
      staging = { sequence: command.sequence, lastAttemptAt: 0, attempts: 0, inFlight: false };
    }
    if (readyForHandoff(command) || staging.inFlight
        || window.ACPNavigationState?.isPresenting?.()
        || staging.attempts >= MAX_STAGE_ATTEMPTS
        || Date.now() - staging.lastAttemptAt < STAGE_RETRY_MS) return;
    staging.attempts++;
    staging.lastAttemptAt = Date.now();
    staging.inFlight = true;
    window.ACPNavDrawer?.show?.();
    void (async () => {
      try {
        if (command.destination === 'audio') {
          window.ACPNavDrawer?.ensureAudioPanel?.();
          const button = document.getElementById('nav-audio-button');
          if (button && !document.body.classList.contains('nav-audio-open')) button.click();
        } else {
          await window.ACPNavigate('/' + command.destination, {
            source: 'native-plexamp-b3', animate: false,
          });
        }
      } catch (error) {
        console.warn('ACP B3 native staging failed', error);
      } finally {
        if (staging?.sequence === command.sequence) staging.inFlight = false;
      }
    })();
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

      stagePendingHandoff();
    } catch (error) {
      // Dashboard can be unavailable during a development restart.
    } finally {
      polling = false;
    }
  }

  const pollTimer = window.setInterval(poll, 600);
  const readyTimer = window.setInterval(() => {
    stagePendingHandoff();
    void acknowledgePresented();
  }, 150);
  const paintTimer = window.setInterval(reportPainted, 120);
  window.addEventListener('focus', reportPainted);
  window.addEventListener('pagehide', () => {
    window.clearInterval(pollTimer);
    window.clearInterval(readyTimer);
    window.clearInterval(paintTimer);
    window.removeEventListener('focus', reportPainted);
  });
})();
