(() => {
  if (window.ACPTime) return;

  let clockFormat = String(
    document.documentElement?.dataset?.clockFormat
    || document.documentElement?.dataset?.serverClockFormat
    || document.body?.dataset?.clockFormat
    || '24h'
  ).toLowerCase() === '12h' ? '12h' : '24h';

  function normaliseDate(value = new Date()) {
    if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
    const text = String(value || '').trim();
    if (!text) return null;
    const normalised = /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T12:00:00` : text;
    const parsed = new Date(normalised);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function formatter(options = {}) {
    return new Intl.DateTimeFormat('en-GB', {
      ...options,
      hour12: clockFormat === '12h',
    });
  }

  function tidyPeriod(text) {
    return clockFormat === '12h'
      ? String(text).replace(/\b(am|pm)\b/gi, (value) => value.toUpperCase())
      : String(text);
  }

  function formatTime(value = new Date(), { seconds = false } = {}) {
    const parsed = normaliseDate(value);
    if (!parsed) return String(value || '');
    return tidyPeriod(formatter({
      hour: '2-digit',
      minute: '2-digit',
      ...(seconds ? { second: '2-digit' } : {}),
    }).format(parsed));
  }

  function formatDateTime(value, { seconds = true, weekday = 'short' } = {}) {
    const parsed = normaliseDate(value);
    if (!parsed) return String(value || '');
    return tidyPeriod(formatter({
      ...(weekday ? { weekday } : {}),
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(seconds ? { second: '2-digit' } : {}),
    }).format(parsed));
  }

  function formatWallTime(value, { seconds = false } = {}) {
    const text = String(value || '').trim();
    const match = text.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (!match) return text;
    const date = new Date(2000, 0, 1, Number(match[1]), Number(match[2]), Number(match[3] || 0));
    return formatTime(date, { seconds: seconds || Boolean(match[3]) });
  }

  function setFormat(value, { announce = true } = {}) {
    const next = String(value || '').toLowerCase() === '12h' ? '12h' : '24h';
    const changed = next !== clockFormat;
    clockFormat = next;
    document.documentElement.dataset.clockFormat = next;
    if (document.body) document.body.dataset.clockFormat = next;
    if (changed && announce) {
      window.dispatchEvent(new CustomEvent('acp:clock-format-changed', {
        detail: { clockFormat: next },
      }));
    }
    refreshMarkedTimes();
    refreshAlarmClock();
    return next;
  }

  function refreshMarkedTimes(root = document) {
    root.querySelectorAll?.('[data-acp-datetime]').forEach((element) => {
      const source = element.dataset.acpDatetime || element.getAttribute('datetime');
      const next = formatDateTime(source, {
        seconds: element.dataset.acpSeconds !== 'false',
        weekday: element.dataset.acpWeekday === 'false' ? '' : 'short',
      });
      if (next && element.textContent !== next) element.textContent = next;
    });
    root.querySelectorAll?.('[data-acp-wall-time]').forEach((element) => {
      const source = element.dataset.acpWallTime;
      const next = formatWallTime(source, { seconds: element.dataset.acpSeconds === 'true' });
      if (next && element.textContent !== next) element.textContent = next;
    });
  }

  function refreshAlarmClock() {
    const element = document.getElementById('alarm-current-time');
    if (!element) return;
    const next = formatTime(new Date());
    if (element.textContent !== next) element.textContent = next;
  }

  function installAlarmClockCompatibility() {
    const element = document.getElementById('alarm-current-time');
    if (!element || element.dataset.acpClockFormatObserver === 'true') return;
    element.dataset.acpClockFormatObserver = 'true';
    let normalising = false;
    const observer = new MutationObserver(() => {
      if (normalising) return;
      normalising = true;
      refreshAlarmClock();
      normalising = false;
    });
    observer.observe(element, { childList: true, characterData: true, subtree: true });
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
    refreshAlarmClock();
  }

  window.ACPTime = {
    get clockFormat() { return clockFormat; },
    setFormat,
    formatTime,
    formatDateTime,
    formatWallTime,
    normaliseDate,
    refresh: refreshMarkedTimes,
  };

  window.addEventListener('acp:dashboard-preferences-changed', (event) => {
    if (event.detail?.clockFormat) setFormat(event.detail.clockFormat);
  });
  window.addEventListener('acp:clock-format-changed', () => refreshMarkedTimes());

  const start = () => {
    setFormat(clockFormat, { announce: false });
    refreshMarkedTimes();
    installAlarmClockCompatibility();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
