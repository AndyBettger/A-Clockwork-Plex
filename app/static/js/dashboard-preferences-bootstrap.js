(() => {
  if (window.__aClockworkPlexDashboardPreferencesBootstrapLoaded) return;
  window.__aClockworkPlexDashboardPreferencesBootstrapLoaded = true;

  /* This script is deliberately first in <head>. Mark the document before CSS or
     body content can paint, then let page-transitions.js reveal it only after the
     active surface reports that its real layout is ready. */
  document.documentElement.classList.add('acp-document-booting');

  const MODE_KEY = 'a-clockwork-plex.startup-mode';
  const IDLE_MODE_KEY = 'a-clockwork-plex.idle-return-mode';
  const TRANSITION_STYLE_KEY = 'a-clockwork-plex.transition-style';
  const TRANSITION_DURATION_KEY = 'a-clockwork-plex.transition-duration-ms';
  const EXPLICIT_NAVIGATION_KEY = 'a-clockwork-plex.explicit-navigation';

  const modes = new Set(['clock', 'weather', 'airplay', 'plexamp']);
  const transitionStyles = new Set([
    'none',
    'grow-fade',
    'crossfade',
    'horizontal-slide',
    'vertical-lift',
    'cover-reveal',
    'zoom',
    'blur-dissolve',
  ]);

  function storageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      window.localStorage.setItem(key, String(value));
    } catch (error) {
    }
  }

  function normaliseMode(value, fallback = 'clock') {
    const mode = String(value || '').trim().toLowerCase();
    return modes.has(mode) ? mode : fallback;
  }

  function normaliseStyle(value) {
    const style = String(value || '').trim().toLowerCase();
    return transitionStyles.has(style) ? style : 'grow-fade';
  }

  function normaliseDuration(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 300;
    return Math.round(Math.max(0, Math.min(1500, numeric)) / 50) * 50;
  }

  function legacyDefault() {
    return normaliseMode(document.documentElement.dataset.legacyDefaultMode || 'clock');
  }

  function read() {
    const legacy = legacyDefault();
    const startupMode = normaliseMode(storageGet(MODE_KEY), legacy);
    const idleReturnMode = normaliseMode(storageGet(IDLE_MODE_KEY), legacy);
    const transitionStyle = normaliseStyle(storageGet(TRANSITION_STYLE_KEY));
    const transitionDurationMs = normaliseDuration(storageGet(TRANSITION_DURATION_KEY));

    if (!storageGet(MODE_KEY)) storageSet(MODE_KEY, startupMode);
    if (!storageGet(IDLE_MODE_KEY)) storageSet(IDLE_MODE_KEY, idleReturnMode);
    if (!storageGet(TRANSITION_STYLE_KEY)) storageSet(TRANSITION_STYLE_KEY, transitionStyle);
    if (!storageGet(TRANSITION_DURATION_KEY)) storageSet(TRANSITION_DURATION_KEY, transitionDurationMs);

    return { startupMode, idleReturnMode, transitionStyle, transitionDurationMs };
  }

  function apply(preferences = read()) {
    const root = document.documentElement;
    const duration = normaliseDuration(preferences.transitionDurationMs);
    const outgoing = Math.round(duration * 0.36);
    const incoming = Math.max(0, duration - outgoing);

    root.dataset.startupMode = normaliseMode(preferences.startupMode);
    root.dataset.idleReturnMode = normaliseMode(preferences.idleReturnMode);
    root.dataset.transitionStyle = normaliseStyle(preferences.transitionStyle);
    root.dataset.transitionDurationMs = String(duration);
    root.style.setProperty('--acp-transition-duration', `${duration}ms`);
    root.style.setProperty('--acp-transition-out-duration', `${outgoing}ms`);
    root.style.setProperty('--acp-transition-in-duration', `${incoming}ms`);
    return read();
  }

  function write(partial = {}) {
    const current = read();
    const next = {
      startupMode: normaliseMode(partial.startupMode ?? current.startupMode),
      idleReturnMode: normaliseMode(partial.idleReturnMode ?? current.idleReturnMode),
      transitionStyle: normaliseStyle(partial.transitionStyle ?? current.transitionStyle),
      transitionDurationMs: normaliseDuration(partial.transitionDurationMs ?? current.transitionDurationMs),
    };
    storageSet(MODE_KEY, next.startupMode);
    storageSet(IDLE_MODE_KEY, next.idleReturnMode);
    storageSet(TRANSITION_STYLE_KEY, next.transitionStyle);
    storageSet(TRANSITION_DURATION_KEY, next.transitionDurationMs);
    apply(next);
    window.dispatchEvent(new CustomEvent('acp:dashboard-preferences-changed', { detail: next }));
    return next;
  }

  function explicitNavigationTo(pathname) {
    try {
      const marker = JSON.parse(window.sessionStorage.getItem(EXPLICIT_NAVIGATION_KEY) || 'null');
      return Boolean(
        marker
        && marker.path === pathname
        && Date.now() - Number(marker.at || 0) < 8000
      );
    } catch (error) {
      return false;
    }
  }

  const preferences = apply(read());
  window.ACPDashboardPreferences = {
    read,
    write,
    apply,
    normaliseMode,
    normaliseStyle,
    normaliseDuration,
  };

  /* The server's root route currently redirects to /clock. A navigation that has
     a redirect count is therefore a kiosk/root startup, while a direct /clock
     visit remains an intentional Clock request. Redirect before first paint. */
  const navigation = window.performance?.getEntriesByType?.('navigation')?.[0];
  const arrivedFromRoot = window.location.pathname === '/clock' && Number(navigation?.redirectCount || 0) > 0;
  if (
    arrivedFromRoot
    && preferences.startupMode !== 'clock'
    && !explicitNavigationTo('/clock')
  ) {
    window.location.replace(`/${preferences.startupMode}`);
  }
})();
