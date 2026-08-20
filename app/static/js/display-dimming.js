(() => {
  if (window.ACPDisplayDimming) return;

  const INTERACTION_STORAGE_KEY = 'a-clockwork-plex.night-interaction-until';
  const MAX_INTERACTION_SECONDS = 300;
  const BOOT_TRANSITION_GUARD_MS = 400;

  const defaults = {
    enabled: false,
    start: '22:00',
    end: '07:00',
    levelPercent: 18,
    activeLevelPercent: 35,
    wakeSeconds: 30,
    nightClockMode: true,
    burnInShift: true,
    style: 'classic',
    activeStyle: 'same',
  };

  let settings = { ...defaults };
  let interactionUntil = 0;
  let previewUntil = 0;
  let refreshInterval = null;
  let activityInterval = null;
  let interactionTimer = null;
  let previewTimer = null;
  let bootTransitionTimer = null;
  let activityRequestInFlight = false;
  let lastInputSequence = null;

  function number(value, fallback, minimum, maximum) {
    const parsed = Number(value);
    return Number.isFinite(parsed)
      ? Math.max(minimum, Math.min(maximum, parsed))
      : fallback;
  }

  function time(value, fallback) {
    const candidate = String(value || '').trim();
    return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(candidate) ? candidate : fallback;
  }

  function style(value, fallback = 'classic', { allowSame = false } = {}) {
    const candidate = String(value || '').trim().toLowerCase();
    const allowed = allowSame ? ['same', 'classic', 'astronomy'] : ['classic', 'astronomy'];
    return allowed.includes(candidate) ? candidate : fallback;
  }

  function booleanValue(source, modernKey, legacyKey, fallback) {
    if (Object.prototype.hasOwnProperty.call(source, modernKey)) return source[modernKey] === true;
    if (Object.prototype.hasOwnProperty.call(source, legacyKey)) return source[legacyKey] === true;
    return fallback;
  }

  function normalise(source = {}, fallback = defaults) {
    return {
      enabled: booleanValue(source, 'enabled', 'night_dim_enabled', fallback.enabled),
      start: time(source.start ?? source.night_dim_start, fallback.start),
      end: time(source.end ?? source.night_dim_end, fallback.end),
      levelPercent: number(
        source.levelPercent ?? source.night_dim_level_percent,
        fallback.levelPercent,
        5,
        80,
      ),
      activeLevelPercent: number(
        source.activeLevelPercent ?? source.night_dim_active_level_percent,
        fallback.activeLevelPercent,
        5,
        80,
      ),
      wakeSeconds: number(
        source.wakeSeconds ?? source.night_dim_wake_seconds,
        fallback.wakeSeconds,
        5,
        MAX_INTERACTION_SECONDS,
      ),
      nightClockMode: booleanValue(
        source,
        'nightClockMode',
        'night_clock_mode',
        fallback.nightClockMode,
      ),
      burnInShift: booleanValue(
        source,
        'burnInShift',
        'night_burn_in_shift',
        fallback.burnInShift,
      ),
      style: style(source.style ?? source.night_dim_style, fallback.style),
      activeStyle: style(
        source.activeStyle ?? source.night_dim_active_style,
        fallback.activeStyle,
        { allowSame: true },
      ),
    };
  }

  function fromDocument() {
    const root = document.documentElement;
    return normalise({
      night_dim_enabled: root.dataset.nightDimEnabled === 'true',
      night_dim_start: root.dataset.nightDimStart,
      night_dim_end: root.dataset.nightDimEnd,
      night_dim_level_percent: root.dataset.nightDimLevelPercent,
      night_dim_active_level_percent: root.dataset.nightDimActiveLevelPercent,
      night_dim_wake_seconds: root.dataset.nightDimWakeSeconds,
      night_clock_mode: root.dataset.nightClockMode === 'true',
      night_burn_in_shift: root.dataset.nightBurnInShift === 'true',
      night_dim_style: root.dataset.nightDimStyle,
      night_dim_active_style: root.dataset.nightDimActiveStyle,
    });
  }

  function minutes(value) {
    const [hour, minute] = String(value).split(':').map(Number);
    return (hour * 60) + minute;
  }

  function scheduledNow(date = new Date()) {
    if (!settings.enabled) return false;
    const start = minutes(settings.start);
    const end = minutes(settings.end);
    const current = (date.getHours() * 60) + date.getMinutes();
    if (start === end) return true;
    if (start < end) return current >= start && current < end;
    return current >= start || current < end;
  }

  function alarmVisible() {
    return window.location.pathname === '/alarm'
      || String(document.body?.dataset?.activePage || '').toLowerCase() === 'alarm'
      || document.body?.classList.contains('mode-alarm');
  }

  function clearStoredInteraction() {
    try {
      window.sessionStorage.removeItem(INTERACTION_STORAGE_KEY);
    } catch (_error) {
    }
  }

  function storeInteractionUntil(deadline) {
    if (!Number.isFinite(deadline) || deadline <= Date.now()) {
      clearStoredInteraction();
      return;
    }
    try {
      window.sessionStorage.setItem(INTERACTION_STORAGE_KEY, String(Math.round(deadline)));
    } catch (_error) {
    }
  }

  function readStoredInteractionUntil() {
    try {
      const deadline = Number(window.sessionStorage.getItem(INTERACTION_STORAGE_KEY));
      const remaining = deadline - Date.now();
      if (
        !Number.isFinite(deadline)
        || remaining <= 0
        || remaining > (MAX_INTERACTION_SECONDS * 1000) + 2000
      ) {
        clearStoredInteraction();
        return 0;
      }
      return deadline;
    } catch (_error) {
      return 0;
    }
  }

  function expireInteractionIfNeeded() {
    if (!interactionUntil || Date.now() < interactionUntil) return false;
    interactionUntil = 0;
    clearStoredInteraction();
    if (interactionTimer) {
      window.clearTimeout(interactionTimer);
      interactionTimer = null;
    }
    return true;
  }

  function interacting() {
    expireInteractionIfNeeded();
    return Date.now() < interactionUntil;
  }

  function previewing() {
    return Date.now() < previewUntil;
  }

  function dimRequired() {
    return !alarmVisible() && (scheduledNow() || previewing());
  }

  function effectiveStyle() {
    if (!interacting() || settings.activeStyle === 'same') return settings.style;
    return settings.activeStyle;
  }

  function effectiveLevelPercent() {
    return interacting() ? settings.activeLevelPercent : settings.levelPercent;
  }

  function scheduleInteractionExpiry() {
    if (interactionTimer) window.clearTimeout(interactionTimer);
    interactionTimer = null;
    const remaining = interactionUntil - Date.now();
    if (remaining <= 0) {
      if (interactionUntil) {
        interactionUntil = 0;
        clearStoredInteraction();
      }
      return;
    }
    interactionTimer = window.setTimeout(() => {
      interactionTimer = null;
      interactionUntil = 0;
      clearStoredInteraction();
      refresh();
      window.dispatchEvent(new CustomEvent('acp:display-night-interaction-ended', {
        detail: status(),
      }));
    }, remaining + 20);
  }

  function clearPreviewTimer() {
    if (!previewTimer) return;
    window.clearTimeout(previewTimer);
    previewTimer = null;
  }

  function schedulePreviewExpiry() {
    clearPreviewTimer();
    const remaining = previewUntil - Date.now();
    if (remaining <= 0) {
      previewUntil = 0;
      return;
    }

    previewTimer = window.setTimeout(() => {
      previewTimer = null;
      previewUntil = 0;
      interactionUntil = 0;
      clearStoredInteraction();
      scheduleInteractionExpiry();
      refresh();
      window.dispatchEvent(new CustomEvent('acp:display-night-preview-ended', {
        detail: status(),
      }));
    }, remaining);
  }

  function restoreStoredInteraction() {
    const stored = readStoredInteractionUntil();
    interactionUntil = stored > Date.now() ? stored : 0;
    scheduleInteractionExpiry();
    return interactionUntil;
  }

  function updateBurnInShift(active) {
    const root = document.documentElement;
    if (!active || interacting() || !settings.burnInShift) {
      root.style.removeProperty('--acp-night-shift-x');
      root.style.removeProperty('--acp-night-shift-y');
      return;
    }
    const phase = Math.floor(Date.now() / 300000) % 9;
    const offsets = [
      [0, 0], [3, -2], [-3, 2], [2, 3], [-2, -3],
      [4, 1], [-4, -1], [1, -4], [-1, 4],
    ];
    const [x, y] = offsets[phase];
    root.style.setProperty('--acp-night-shift-x', `${x}px`);
    root.style.setProperty('--acp-night-shift-y', `${y}px`);
  }

  function applyDocumentNightBackground(active) {
    const root = document.documentElement;
    root.classList.toggle('acp-night-document-active', active);
    if (active) root.style.backgroundColor = '#000';
    else root.style.removeProperty('background-color');
  }

  function applyEffectiveVariables() {
    const selectedStyle = effectiveStyle();
    const level = number(effectiveLevelPercent(), settings.levelPercent, 5, 80);
    const brightness = Math.max(0.05, Math.min(0.8, level / 100));
    const classicDarkness = Math.max(0.2, Math.min(0.95, 1 - brightness));
    const root = document.documentElement;
    root.style.setProperty('--acp-night-brightness', String(brightness));
    root.style.setProperty(
      '--acp-night-dim-opacity',
      String(selectedStyle === 'astronomy' ? 1 : classicDarkness),
    );
    return { selectedStyle, level };
  }

  function primeDocumentNightState() {
    if (alarmVisible() || !scheduledNow()) return;
    const root = document.documentElement;
    root.classList.add('acp-night-no-transition');
    applyDocumentNightBackground(true);
    applyEffectiveVariables();
  }

  function releaseBootTransitionGuard() {
    if (bootTransitionTimer) window.clearTimeout(bootTransitionTimer);
    bootTransitionTimer = window.setTimeout(() => {
      document.documentElement.classList.remove('acp-night-no-transition');
      document.body?.classList.remove('acp-night-no-transition');
      bootTransitionTimer = null;
    }, BOOT_TRANSITION_GUARD_MS);
  }

  function refresh() {
    if (!document.body) return status();
    const active = dimRequired();
    const interactionActive = interacting();
    const { selectedStyle } = applyEffectiveVariables();

    applyDocumentNightBackground(active);
    document.body.classList.toggle('acp-night-dim-active', active);
    document.body.classList.toggle('acp-night-style-classic', selectedStyle === 'classic');
    document.body.classList.toggle('acp-night-style-astronomy', selectedStyle === 'astronomy');
    document.body.classList.toggle('acp-night-interacting', active && interactionActive);
    document.body.classList.toggle(
      'acp-night-clock-mode',
      active
        && !interactionActive
        && settings.nightClockMode
        && document.body.dataset.activePage === 'clock',
    );
    updateBurnInShift(active);
    return status();
  }

  function interact(seconds = settings.wakeSeconds, source = 'browser-interaction') {
    if (!dimRequired() || alarmVisible()) return status();
    const duration = number(seconds, settings.wakeSeconds, 5, MAX_INTERACTION_SECONDS);
    const requestedUntil = Date.now() + (duration * 1000);
    const previewActive = previewing();

    interactionUntil = previewActive
      ? Math.min(previewUntil, requestedUntil)
      : requestedUntil;

    if (previewActive) clearStoredInteraction();
    else storeInteractionUntil(interactionUntil);

    scheduleInteractionExpiry();
    refresh();
    window.dispatchEvent(new CustomEvent('acp:display-night-interaction', {
      detail: { ...status(), source },
    }));
    return status();
  }

  // Kept as a compatibility alias for older callers. It no longer removes the
  // night treatment; it enters the configured night-safe interaction state.
  function wake(seconds = settings.wakeSeconds) {
    return interact(seconds, 'wake-alias');
  }

  function preview(seconds = 8) {
    previewUntil = Date.now() + (number(seconds, 8, 3, 30) * 1000);
    interactionUntil = 0;
    clearStoredInteraction();
    scheduleInteractionExpiry();
    schedulePreviewExpiry();
    refresh();
    return status();
  }

  function configure(source = {}) {
    settings = normalise(source, settings);
    const root = document.documentElement;
    root.dataset.nightDimEnabled = String(settings.enabled);
    root.dataset.nightDimStart = settings.start;
    root.dataset.nightDimEnd = settings.end;
    root.dataset.nightDimLevelPercent = String(settings.levelPercent);
    root.dataset.nightDimActiveLevelPercent = String(settings.activeLevelPercent);
    root.dataset.nightDimWakeSeconds = String(settings.wakeSeconds);
    root.dataset.nightClockMode = String(settings.nightClockMode);
    root.dataset.nightBurnInShift = String(settings.burnInShift);
    root.dataset.nightDimStyle = settings.style;
    root.dataset.nightDimActiveStyle = settings.activeStyle;
    return refresh();
  }

  function status() {
    const interactionActive = interacting();
    return {
      ...settings,
      scheduled: scheduledNow(),
      active: dimRequired(),
      interacting: interactionActive,
      previewing: previewing(),
      effectiveStyle: effectiveStyle(),
      effectiveLevelPercent: effectiveLevelPercent(),
      interactionUntil: interactionUntil || null,
      interactionRemainingSeconds: interactionActive
        ? Math.max(0, Math.ceil((interactionUntil - Date.now()) / 1000))
        : 0,
      wakeUntil: interactionUntil || null,
      temporarilyAwake: false,
    };
  }

  function observeLocalInteraction() {
    if (!dimRequired() || alarmVisible()) return;
    interact(settings.wakeSeconds, 'document-input');
  }

  async function pollLinuxInputActivity() {
    if (
      activityRequestInFlight
      || !settings.enabled
      || alarmVisible()
      || (!scheduledNow() && !previewing())
    ) return;

    activityRequestInFlight = true;
    try {
      const surface = String(document.body?.dataset?.activePage || 'clock');
      const response = await fetch(
        `/api/screen/state?visible_surface=${encodeURIComponent(surface)}`,
        { cache: 'no-store' },
      );
      if (!response.ok) return;
      const payload = await response.json();
      const raw = payload?.screen?.input_activity?.sequence;
      const sequence = Number(raw);
      if (!Number.isFinite(sequence)) return;
      if (lastInputSequence === null || sequence < lastInputSequence) {
        lastInputSequence = sequence;
        return;
      }
      if (sequence > lastInputSequence) {
        lastInputSequence = sequence;
        // The OS input stream reports the same physical tap that launched a
        // Settings preview. Browser-local input remains authoritative during
        // preview so that tap is not replayed one second later as an activation.
        if (previewing()) return;
        interact(settings.wakeSeconds, 'linux-input-monitor');
      }
    } catch (_error) {
      // Local document events still provide a complete fallback for every
      // dashboard-owned surface. The server monitor adds cross-origin iframe
      // coverage for Plexamp when it is available.
    } finally {
      activityRequestInFlight = false;
    }
  }

  function restoreAndRefresh() {
    restoreStoredInteraction();
    refresh();
  }

  function install() {
    settings = fromDocument();
    restoreStoredInteraction();
    if (dimRequired()) {
      document.documentElement.classList.add('acp-night-no-transition');
      document.body.classList.add('acp-night-no-transition');
    }
    document.addEventListener('pointerdown', observeLocalInteraction, true);
    document.addEventListener('keydown', observeLocalInteraction, true);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', restoreAndRefresh);
    window.addEventListener('pageshow', restoreAndRefresh);
    window.addEventListener('acp:dashboard-preferences-changed', refresh);
    refreshInterval = window.setInterval(refresh, 15000);
    activityInterval = window.setInterval(pollLinuxInputActivity, 1000);
    pollLinuxInputActivity();
    refresh();
    releaseBootTransitionGuard();
  }

  settings = fromDocument();
  restoreStoredInteraction();
  primeDocumentNightState();

  window.ACPDisplayDimming = {
    configure,
    preview,
    interact,
    wake,
    refresh,
    status,
    scheduledNow,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();

  window.addEventListener('pagehide', () => {
    if (refreshInterval) window.clearInterval(refreshInterval);
    if (activityInterval) window.clearInterval(activityInterval);
    if (interactionTimer) window.clearTimeout(interactionTimer);
    clearPreviewTimer();
    if (bootTransitionTimer) window.clearTimeout(bootTransitionTimer);
  }, { once: true });
})();