(() => {
  if (window.ACPDisplayDimming) return;

  const defaults = {
    enabled: false,
    start: '22:00',
    end: '07:00',
    levelPercent: 18,
    wakeSeconds: 30,
    nightClockMode: true,
    burnInShift: true,
  };

  let settings = { ...defaults };
  let wakeUntil = 0;
  let previewUntil = 0;
  let interval = null;
  let clickBlockUntil = 0;

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
    };
  }

  function fromDocument() {
    const root = document.documentElement;
    return normalise({
      night_dim_enabled: root.dataset.nightDimEnabled === 'true',
      night_dim_start: root.dataset.nightDimStart,
      night_dim_end: root.dataset.nightDimEnd,
      night_dim_level_percent: root.dataset.nightDimLevelPercent,
      night_dim_wake_seconds: root.dataset.nightDimWakeSeconds,
      night_clock_mode: root.dataset.nightClockMode === 'true',
      night_burn_in_shift: root.dataset.nightBurnInShift === 'true',
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

  function temporarilyAwake() {
    return Date.now() < wakeUntil;
  }

  function previewing() {
    return Date.now() < previewUntil;
  }

  function dimRequired() {
    return !alarmVisible() && !temporarilyAwake() && (scheduledNow() || previewing());
  }

  function updateBurnInShift(active) {
    const root = document.documentElement;
    if (!active || !settings.burnInShift) {
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
    const darkness = Math.max(0, Math.min(0.95, 1 - (settings.levelPercent / 100)));
    document.documentElement.style.setProperty('--acp-night-dim-opacity', String(darkness));
    document.body.classList.toggle('acp-night-dim-active', active);
    document.body.classList.toggle(
      'acp-night-clock-mode',
      active && settings.nightClockMode && document.body.dataset.activePage === 'clock',
    );
    document.body.classList.toggle('acp-night-temporarily-awake', temporarilyAwake());
    updateBurnInShift(active);
    return status();
  }

  function wake(seconds = settings.wakeSeconds) {
    wakeUntil = Date.now() + (number(seconds, settings.wakeSeconds, 5, 300) * 1000);
    previewUntil = 0;
    refresh();
    window.dispatchEvent(new CustomEvent('acp:display-woke', { detail: status() }));
  }

  function preview(seconds = 8) {
    previewUntil = Date.now() + (number(seconds, 8, 3, 30) * 1000);
    wakeUntil = 0;
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
    root.dataset.nightDimWakeSeconds = String(settings.wakeSeconds);
    root.dataset.nightClockMode = String(settings.nightClockMode);
    root.dataset.nightBurnInShift = String(settings.burnInShift);
    return refresh();
  }

  function status() {
    return {
      ...settings,
      scheduled: scheduledNow(),
      active: dimRequired(),
      temporarilyAwake: temporarilyAwake(),
      previewing: previewing(),
      wakeUntil: wakeUntil || null,
    };
  }

  function consumeWakeInteraction(event) {
    if (!dimRequired() || alarmVisible()) return;
    clickBlockUntil = Date.now() + 500;
    event.preventDefault();
    event.stopImmediatePropagation();
    wake();
  }

  function blockSyntheticClick(event) {
    if (Date.now() >= clickBlockUntil) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function install() {
    settings = fromDocument();
    document.addEventListener('pointerdown', consumeWakeInteraction, true);
    document.addEventListener('keydown', consumeWakeInteraction, true);
    document.addEventListener('click', blockSyntheticClick, true);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('pageshow', refresh);
    window.addEventListener('acp:dashboard-preferences-changed', refresh);
    interval = window.setInterval(refresh, 15000);
    refresh();
  }

  window.ACPDisplayDimming = {
    configure,
    preview,
    wake,
    refresh,
    status,
    scheduledNow,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();

  window.addEventListener('pagehide', () => {
    if (interval) window.clearInterval(interval);
  }, { once: true });
})();
