(() => {
  'use strict';
  if (window.ACPC3ThemeSync) return;

  // Experimental C3 ONLY. This client cannot start or own Squeekboard. The
  // server writes a private stylesheet only while a user explicitly opted into
  // --start --theme-sync (180s with independent 240s stock restore).
  const STATUS = '/api/osk/c3/theme-sync/status';
  const APPLY = '/api/osk/c3/theme-sync';
  const PERIOD_MS = 5000;
  // Settings-only diagnostic mode, stored solely in this browser document.
  // Observe the EXISTING five-second callback rather than introducing another
  // timer or second CSS writer. No network/log/storage of samples.
  const TRACE_ENABLED = window.location.pathname === '/settings'
    && new URLSearchParams(window.location.search).has('c3-shadow');
  const TRACE_WINDOW_MS = 15 * 60 * 1000;
  const TRACE_MAX_SAMPLES = 256;
  const traceStartedAt = TRACE_ENABLED ? Date.now() : null;
  const traceSamples = [];
  let lastIntervalAt = null;
  let inFlight = false;
  let lastApplied = null;
  let enabled = false;

  function currentState() {
    const preferences = window.ACPDashboardPreferences?.read?.();
    const night = window.ACPDisplayDimming?.status?.();
    // Do not invent night mode from the clock, CSS classes or screen visibility.
    if (!preferences || !night || typeof night.active !== 'boolean'
        || typeof night.interacting !== 'boolean'
        || !['classic', 'astronomy'].includes(night.effectiveStyle)) return null;
    return {
      daytimeTheme: preferences.daytimeTheme || 'classic_dark',
      night: {
        active: night.active,
        interacting: night.interacting,
        effectiveStyle: night.effectiveStyle,
      },
    };
  }

  function observeTick(event) {
    if (!TRACE_ENABLED) return;
    const now = Date.now();
    if (now - traceStartedAt > TRACE_WINDOW_MS) return;
    const source = event && typeof event.type === 'string' ? event.type : 'interval';
    const previousInterval = source === 'interval' ? lastIntervalAt : null;
    if (source === 'interval') lastIntervalAt = now;
    const elapsedMs = now - traceStartedAt;
    traceSamples.push({
      elapsedSeconds: Math.round(elapsedMs / 1000),
      source,
      timerGapMs: previousInterval === null ? null : Math.max(0, now - previousInterval),
      visibility: document.visibilityState,
      skippedWhileInFlight: inFlight,
    });
    if (traceSamples.length > TRACE_MAX_SAMPLES) traceSamples.shift();
  }

  function timingReport() {
    if (!TRACE_ENABLED) return null;
    const timerIntervals = traceSamples.filter(
      sample => sample.source === 'interval' && sample.timerGapMs !== null,
    );
    const largest = [...timerIntervals].sort(
      (a, b) => b.timerGapMs - a.timerGapMs,
    );
    return {
      diagnosticOnly: true,
      existingThemeCallbackOnly: true,
      noCssOrKeyboardChanges: true,
      expectedIntervalMs: PERIOD_MS,
      recordingWindowSeconds: TRACE_WINDOW_MS / 1000,
      elapsedSeconds: Math.round((Date.now() - traceStartedAt) / 1000),
      sampleCount: traceSamples.length,
      timerIntervalCount: timerIntervals.length,
      maximumTimerGapMs: largest.length ? largest[0].timerGapMs : null,
      intervalsOver15Seconds: timerIntervals.filter(s => s.timerGapMs > 15000).length,
      hiddenSamples: traceSamples.filter(s => s.visibility === 'hidden').length,
      skippedWhileInFlight: traceSamples.filter(s => s.skippedWhileInFlight).length,
      largestTimerGaps: largest.slice(0, 10),
      recentSamples: traceSamples.slice(-16),
      limitations: [
        'Only the existing C3 timer callback is sampled; it may be throttled or suspended.',
        'Window occlusion by native Plexamp may not set Chromium visibility to hidden.',
        'No proof of CSS repaint, schedule boundary delivery, or uninterrupted typing.',
        'All evidence is page-memory only and disappears on reload/navigation.',
      ],
    };
  }

  async function tick(event) {
    observeTick(event);
    if (inFlight) return;
    inFlight = true;
    try {
      const response = await fetch(STATUS, {
        method: 'GET', credentials: 'same-origin', cache: 'no-store',
      });
      if (!response.ok) {
        enabled = false;
        window.ACPKeyboardChoice?.setSystemActive?.(false);
        lastApplied = null;
        return;
      }
      const status = await response.json();
      enabled = status?.ok === true && status?.enabled === true;
      // This is the SAME existing status request: no second poller. Only an
      // active C3 session may suppress ACP's HTML keyboard. Changing the
      // selection also activates the existing Settings focus-reveal logic.
      window.ACPKeyboardChoice?.setSystemActive?.(enabled);
      if (!enabled) {
        lastApplied = null;
        return;
      }
      const state = currentState();
      if (!state) return;
      const canonical = JSON.stringify(state);
      if (canonical === lastApplied) return; // no redundant filesystem writes
      const update = await fetch(APPLY, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: canonical,
      });
      if (!update.ok) return;
      const result = await update.json();
      if (result?.ok === true && result?.enabled === true) {
        lastApplied = canonical;
      } else {
        enabled = false;
        lastApplied = null;
      }
    } catch (_error) {
      enabled = false; // connectivity/status errors must never touch the OSK
      // Preserve a running native keyboard during transient dashboard errors;
      // a *confirmed* disabled status above hands input back to ACP.
      lastApplied = null;
    } finally {
      inFlight = false;
    }
  }

  // A true night-boundary is re-evaluated from status() on each poll even when
  // a native Plexamp input is focused. DOM/focus/OSK ownership is never edited.
  const events = [
    'acp:dashboard-preferences-changed',
    'acp:display-night-interaction',
    'acp:display-night-interaction-ended',
    'acp:display-night-preview-started',
    'acp:display-night-preview-ended',
    'acp:surface-activated',
    'acp:surface-settled',
  ];
  for (const event of events) window.addEventListener(event, tick);
  window.addEventListener('pageshow', tick);
  window.setInterval(tick, PERIOD_MS);
  window.ACPC3ThemeSync = {
    status: () => ({ enabled, lastApplied }),
    // Read-only inspection hooks; no manual theme override is provided.
    currentState,
    timingReport,
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick, { once: true });
  } else {
    tick();
  }
})();
