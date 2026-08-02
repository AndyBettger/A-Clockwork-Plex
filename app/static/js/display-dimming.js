(() => {
  if (window.ACPDisplayDimming) return;

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
        300,
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
    return String(document.body?.dataset?.activePage || '').toLowerCase() === 'alarm'
      || document.body?.classList.contains('mode-alarm');
  }

  function interacting() {
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

  function refresh() {
    if (!document.body) return status();
    const active = dimRequired();
    const interactionActive = interacting();
    const selectedStyle = effectiveStyle();
    const level = number(effectiveLevelPercent(), settings.levelPercent, 5, 80);
    const brightness = Math.max(0.05, Math.min(0.8, level / 100));
    const classicDarkness = Math.max(0.2, Math.min(0.95, 1 - brightness));

    document.documentElement.style.setProperty('--acp-night-brightness', String(brightness));
    document.documentElement.style.setProperty(
      '--acp-night-dim-opacity',
      String(selectedStyle === 'astronomy' ? 1 : classicDarkness),
    );
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
    interactionUntil = Date.now() + (number(seconds, settings.wakeSeconds, 5, 300) * 1000);
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
    return {
      ...settings,
      scheduled: scheduledNow(),
      active: dimRequired(),
      interacting: interacting(),
      previewing: previewing(),
      effectiveStyle: effectiveStyle(),
      effectiveLevelPercent: effectiveLevelPercent(),
      interactionUntil: interactionUntil || null,
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

  function install() {
    settings = fromDocument();
    document.addEventListener('pointerdown', observeLocalInteraction, true);
    document.addEventListener('keydown', observeLocalInteraction, true);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('pageshow', refresh);
    window.addEventListener('acp:dashboard-preferences-changed', refresh);
    refreshInterval = window.setInterval(refresh, 15000);
    activityInterval = window.setInterval(pollLinuxInputActivity, 1000);
    pollLinuxInputActivity();
    refresh();
  }

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
  }, { once: true });
})();
