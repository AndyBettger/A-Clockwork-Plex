(() => {
  'use strict';
  if (window.ACPC3ThemeSync) return;

  // Experimental C3 ONLY. This client cannot start or own Squeekboard. The
  // server writes a private stylesheet only while a user explicitly opted into
  // --start --theme-sync (180s with independent 240s stock restore).
  const STATUS = '/api/osk/c3/theme-sync/status';
  const APPLY = '/api/osk/c3/theme-sync';
  const PERIOD_MS = 5000;
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

  async function tick() {
    if (inFlight) return;
    inFlight = true;
    try {
      const response = await fetch(STATUS, {
        method: 'GET', credentials: 'same-origin', cache: 'no-store',
      });
      if (!response.ok) {
        enabled = false;
        lastApplied = null;
        return;
      }
      const status = await response.json();
      enabled = status?.ok === true && status?.enabled === true;
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
    // Read-only inspection hook; manual theme override is intentionally absent.
    currentState,
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick, { once: true });
  } else {
    tick();
  }
})();
