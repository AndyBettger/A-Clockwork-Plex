(() => {
  if (window.__aClockworkPlexDashboardPreferencesBootstrapLoaded) return;
  window.__aClockworkPlexDashboardPreferencesBootstrapLoaded = true;

  /* This script is deliberately first in <head>. Mark the document before CSS or
     body content can paint, then let page-transitions.js reveal it only after the
     active surface reports that its real layout is ready. */
  document.documentElement.classList.add('acp-document-booting');

  const EXPLICIT_NAVIGATION_KEY = 'a-clockwork-plex.explicit-navigation';
  const LEGACY_CLOCK_FORMAT_KEY = 'a-clockwork-plex.clock-format';
  const modes = new Set(['clock', 'weather', 'news', 'airplay', 'plexamp']);
  const daytimeThemes = new Set([
    'classic_dark',
    'midnight_blue',
    'amber_terminal',
    'green_phosphor',
    'aubergine',
    'steel_cyan',
    'crimson_glow',
  ]);
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

  function normaliseMode(value, fallback = 'clock') {
    const mode = String(value || '').trim().toLowerCase();
    return modes.has(mode) ? mode : fallback;
  }

  function normaliseDaytimeTheme(value) {
    const theme = String(value || '').trim().toLowerCase();
    return daytimeThemes.has(theme) ? theme : 'classic_dark';
  }

  function normaliseStyle(value) {
    const style = String(value || '').trim().toLowerCase();
    if (style === 'instant') return 'none';
    return transitionStyles.has(style) ? style : 'grow-fade';
  }

  function normaliseDuration(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 300;
    return Math.round(Math.max(0, Math.min(2000, numeric)) / 50) * 50;
  }

  function read() {
    const root = document.documentElement;
    const legacy = normaliseMode(root.dataset.legacyDefaultMode || 'clock');
    return {
      startupMode: normaliseMode(root.dataset.serverStartupMode, legacy),
      idleReturnMode: normaliseMode(root.dataset.serverIdleReturnMode, legacy),
      daytimeTheme: normaliseDaytimeTheme(
        root.dataset.daytimeTheme || root.dataset.serverDaytimeTheme || 'classic_dark'
      ),
      transitionStyle: normaliseStyle(root.dataset.serverTransitionStyle || 'grow-fade'),
      transitionDurationMs: normaliseDuration(root.dataset.serverTransitionDurationMs || 300),
      clockFormat: String(root.dataset.serverClockFormat || '24h').toLowerCase() === '12h' ? '12h' : '24h',
    };
  }

  function mirrorClockFormat(value) {
    try {
      window.localStorage.setItem(LEGACY_CLOCK_FORMAT_KEY, value === '12h' ? '12h' : '24h');
    } catch (error) {
    }
  }

  function apply(preferences = read()) {
    const root = document.documentElement;
    const duration = normaliseDuration(preferences.transitionDurationMs);
    const outgoing = Math.round(duration * 0.36);
    const incoming = Math.max(0, duration - outgoing);

    root.dataset.startupMode = normaliseMode(preferences.startupMode);
    root.dataset.idleReturnMode = normaliseMode(preferences.idleReturnMode);
    root.dataset.daytimeTheme = normaliseDaytimeTheme(preferences.daytimeTheme);
    root.dataset.transitionStyle = normaliseStyle(preferences.transitionStyle);
    root.dataset.transitionDurationMs = String(duration);
    root.dataset.clockFormat = preferences.clockFormat === '12h' ? '12h' : '24h';
    root.style.setProperty('--acp-transition-duration', `${duration}ms`);
    root.style.setProperty('--acp-transition-out-duration', `${outgoing}ms`);
    root.style.setProperty('--acp-transition-in-duration', `${incoming}ms`);
    mirrorClockFormat(root.dataset.clockFormat);
    return {
      startupMode: root.dataset.startupMode,
      idleReturnMode: root.dataset.idleReturnMode,
      daytimeTheme: root.dataset.daytimeTheme,
      transitionStyle: root.dataset.transitionStyle,
      transitionDurationMs: duration,
      clockFormat: root.dataset.clockFormat,
    };
  }

  function write(partial = {}) {
    const current = read();
    const next = apply({
      startupMode: normaliseMode(partial.startupMode ?? current.startupMode),
      idleReturnMode: normaliseMode(partial.idleReturnMode ?? current.idleReturnMode),
      daytimeTheme: normaliseDaytimeTheme(partial.daytimeTheme ?? current.daytimeTheme),
      transitionStyle: normaliseStyle(partial.transitionStyle ?? current.transitionStyle),
      transitionDurationMs: normaliseDuration(partial.transitionDurationMs ?? current.transitionDurationMs),
      clockFormat: String(partial.clockFormat ?? current.clockFormat).toLowerCase() === '12h' ? '12h' : '24h',
    });
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
    normaliseDaytimeTheme,
    normaliseStyle,
    normaliseDuration,
  };

  /* The server's root route redirects to /clock. A redirected /clock is therefore
     appliance startup, while a direct /clock remains an intentional navigation. */
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