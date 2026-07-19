(() => {
  const PANEL_ID = 'settings-panel-alarms';
  const STATUS_ENDPOINT = '/api/alarms/scheduler';
  const TEST_ENDPOINT = '/api/alarms/test';
  const CLEAR_TEST_ENDPOINT = '/api/alarms/test/cancel';
  const REFRESH_MS = 5000;

  let refreshTimer = null;
  let refreshInFlight = false;

  const byId = (id) => document.getElementById(id);

  function formatTimestamp(value, fallback = 'Not yet') {
    if (!value) {
      return fallback;
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return fallback;
    }
    return new Intl.DateTimeFormat('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(parsed);
  }

  function formatNextOccurrence(occurrence) {
    if (!occurrence) {
      return {
        title: 'No enabled alarms',
        detail: 'The scheduler is enjoying the silence.',
      };
    }
    return {
      title: `${occurrence.label || 'Alarm'} · ${formatTimestamp(occurrence.scheduled_for, 'Unknown time')}`,
      detail: `${occurrence.wall_time || ''} · ${occurrence.timezone || 'Local time'}`,
    };
  }

  function formatActiveState(scheduler) {
    const active = scheduler.active_occurrence;
    const pending = scheduler.pending_test_occurrence;
    if (active) {
      if (scheduler.snoozed_until) {
        return {
          title: `${active.label || 'Alarm'} · snoozed`,
          detail: `Returns ${formatTimestamp(scheduler.snoozed_until)} · snooze ${active.snooze_count || 0}`,
        };
      }
      return {
        title: `${active.label || 'Alarm'} · screen active`,
        detail: `${active.test_mode ? 'Visual test · ' : ''}audio remains locked`,
      };
    }
    if (pending) {
      return {
        title: 'Visual test armed',
        detail: `Screen takeover ${formatTimestamp(pending.trigger_at)}`,
      };
    }
    return {
      title: 'Idle',
      detail: 'No active, snoozed or pending alarm.',
    };
  }

  function installCard() {
    const panel = byId(PANEL_ID);
    const lockout = panel?.querySelector('.alarm-scheduler-lockout');
    if (!panel || !lockout) {
      return false;
    }

    const intro = panel.querySelector('.settings-card.is-intro');
    const introChip = intro?.querySelector('.settings-chip');
    const introCopy = intro?.querySelector('p');
    if (introChip) {
      introChip.textContent = 'Active runtime';
    }
    if (introCopy) {
      introCopy.textContent = 'Create and organise alarms while the persistent runtime handles screen takeover, snooze and dismiss. Audio remains deliberately locked.';
    }

    const lockoutTitle = lockout.querySelector('strong');
    const lockoutCopy = lockout.querySelector('span');
    if (lockoutTitle) {
      lockoutTitle.textContent = 'Audio playback lockout active';
    }
    if (lockoutCopy) {
      lockoutCopy.textContent = 'Scheduled or test alarms may take over the touchscreen, but this pass cannot play any sound.';
    }

    if (byId('alarm-scheduler-status-card')) {
      return true;
    }

    const card = document.createElement('section');
    card.id = 'alarm-scheduler-status-card';
    card.className = 'settings-card alarm-scheduler-status-card';
    card.innerHTML = `
      <div class="settings-card-heading">
        <div>
          <h2>Active alarm runtime</h2>
          <p class="muted small">Persistent screen takeover, snooze, dismiss, restart recovery and duplicate protection.</p>
        </div>
        <span class="settings-chip" id="alarm-scheduler-health">Loading…</span>
      </div>

      <div class="alarm-scheduler-grid">
        <div class="alarm-scheduler-reading is-wide">
          <span>Next alarm</span>
          <strong id="alarm-scheduler-next">Calculating…</strong>
          <small id="alarm-scheduler-next-detail">Waiting for the first scheduler heartbeat.</small>
        </div>
        <div class="alarm-scheduler-reading is-wide">
          <span>Runtime state</span>
          <strong id="alarm-runtime-active">Loading…</strong>
          <small id="alarm-runtime-active-detail">Checking active and snoozed state.</small>
        </div>
        <div class="alarm-scheduler-reading">
          <span>Timezone</span>
          <strong id="alarm-scheduler-timezone">—</strong>
          <small>Uses the Raspberry Pi local timezone.</small>
        </div>
        <div class="alarm-scheduler-reading">
          <span>Last checked</span>
          <strong id="alarm-scheduler-last-check">Not yet</strong>
          <small id="alarm-scheduler-check-detail">Polling every 15 seconds.</small>
        </div>
        <div class="alarm-scheduler-reading">
          <span>Duplicate protection</span>
          <strong id="alarm-scheduler-duplicates">0 recorded</strong>
          <small>One occurrence key per alarm, date and wall-clock time.</small>
        </div>
        <div class="alarm-scheduler-reading">
          <span>Queued</span>
          <strong id="alarm-runtime-queued">0 alarms</strong>
          <small>Simultaneous alarms wait here rather than being lost.</small>
        </div>
      </div>

      <div class="alarm-scheduler-observed" id="alarm-scheduler-observed">
        No alarm occurrences have been observed yet. Long may this continue.
      </div>

      <div class="alarm-scheduler-actions">
        <button class="button settings-secondary" id="alarm-scheduler-refresh" type="button">Recalculate now</button>
        <button class="button" id="alarm-runtime-test" type="button">Test screen in 10 seconds</button>
        <button class="button settings-secondary" id="alarm-runtime-clear-test" type="button">Clear visual test</button>
        <span class="muted small" id="alarm-scheduler-message">The screen can activate; audio cannot.</span>
      </div>
    `;
    panel.insertBefore(card, lockout);

    byId('alarm-scheduler-refresh')?.addEventListener('click', () => refreshStatus(true));
    byId('alarm-runtime-test')?.addEventListener('click', scheduleVisualTest);
    byId('alarm-runtime-clear-test')?.addEventListener('click', clearVisualTest);
    return true;
  }

  function renderStatus(payload) {
    const scheduler = payload?.scheduler;
    if (!scheduler) {
      throw new Error('Scheduler status response was incomplete.');
    }

    const health = byId('alarm-scheduler-health');
    const isRunning = scheduler.running && scheduler.health === 'running-ui-ready';
    if (health) {
      health.textContent = isRunning ? 'Screen runtime ready' : scheduler.last_error ? 'Needs attention' : 'Stopped';
      health.classList.toggle('is-warning', !isRunning);
    }

    const next = formatNextOccurrence(scheduler.next_occurrence);
    byId('alarm-scheduler-next').textContent = next.title;
    byId('alarm-scheduler-next-detail').textContent = next.detail;

    const active = formatActiveState(scheduler);
    byId('alarm-runtime-active').textContent = active.title;
    byId('alarm-runtime-active-detail').textContent = active.detail;

    byId('alarm-scheduler-timezone').textContent = scheduler.timezone || 'Local time';
    byId('alarm-scheduler-last-check').textContent = formatTimestamp(scheduler.last_check_at);

    const pollSeconds = Number(scheduler.poll_seconds) || 15;
    const graceMinutes = Number(scheduler.missed_alarm_grace_minutes) || 10;
    byId('alarm-scheduler-check-detail').textContent = `Poll ${pollSeconds}s · restart grace ${graceMinutes} min`;

    const protectedCount = Number(scheduler.duplicate_protection_count) || 0;
    byId('alarm-scheduler-duplicates').textContent = `${protectedCount} recorded`;

    const queuedCount = Number(scheduler.queued_occurrence_count) || 0;
    byId('alarm-runtime-queued').textContent = `${queuedCount} alarm${queuedCount === 1 ? '' : 's'}`;

    const observed = scheduler.last_observed_occurrence;
    const observedElement = byId('alarm-scheduler-observed');
    if (observedElement) {
      if (observed) {
        const recovery = observed.recovered_after_restart ? ' · recovered after restart' : '';
        observedElement.textContent = `Last observed: ${observed.label || 'Alarm'} at ${formatTimestamp(observed.scheduled_for)}${recovery}. Current status: ${observed.status || 'recorded'}; playback was not attempted.`;
      } else {
        observedElement.textContent = 'No alarm occurrences have been observed yet. Long may this continue.';
      }
    }

    const message = byId('alarm-scheduler-message');
    if (message) {
      message.textContent = scheduler.last_error || 'Screen takeover, snooze and dismiss are active; audio playback remains locked.';
      message.classList.toggle('is-error', Boolean(scheduler.last_error));
    }
  }

  async function requestJson(endpoint, options = {}) {
    const response = await fetch(endpoint, {
      cache: 'no-store',
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `Alarm runtime returned ${response.status}.`);
    }
    return payload;
  }

  async function refreshStatus(recalculate = false) {
    if (refreshInFlight || !installCard()) {
      return;
    }
    refreshInFlight = true;
    const button = byId('alarm-scheduler-refresh');
    if (button) {
      button.disabled = true;
      button.textContent = recalculate ? 'Recalculating…' : 'Refreshing…';
    }

    try {
      const payload = await requestJson(STATUS_ENDPOINT, {
        method: recalculate ? 'POST' : 'GET',
      });
      renderStatus(payload);
    } catch (error) {
      const health = byId('alarm-scheduler-health');
      if (health) {
        health.textContent = 'Unavailable';
        health.classList.add('is-warning');
      }
      const message = byId('alarm-scheduler-message');
      if (message) {
        message.textContent = error.message || 'Could not read scheduler status.';
        message.classList.add('is-error');
      }
    } finally {
      refreshInFlight = false;
      if (button) {
        button.disabled = false;
        button.textContent = 'Recalculate now';
      }
    }
  }

  async function scheduleVisualTest() {
    const button = byId('alarm-runtime-test');
    if (button) {
      button.disabled = true;
      button.textContent = 'Arming screen…';
    }
    try {
      const payload = await requestJson(TEST_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delay_seconds: 10 }),
      });
      renderStatus({ scheduler: payload.scheduler });
      const message = byId('alarm-scheduler-message');
      if (message) {
        message.textContent = payload.message || 'Visual alarm test armed.';
        message.classList.remove('is-error');
      }
    } catch (error) {
      const message = byId('alarm-scheduler-message');
      if (message) {
        message.textContent = error.message || 'Could not schedule the visual test.';
        message.classList.add('is-error');
      }
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Test screen in 10 seconds';
      }
    }
  }

  async function clearVisualTest() {
    const button = byId('alarm-runtime-clear-test');
    if (button) {
      button.disabled = true;
      button.textContent = 'Clearing…';
    }
    try {
      const payload = await requestJson(CLEAR_TEST_ENDPOINT, { method: 'POST' });
      renderStatus({ scheduler: payload.scheduler });
      const message = byId('alarm-scheduler-message');
      if (message) {
        message.textContent = payload.message || 'Visual alarm test cleared.';
        message.classList.remove('is-error');
      }
    } catch (error) {
      const message = byId('alarm-scheduler-message');
      if (message) {
        message.textContent = error.message || 'Could not clear the visual test.';
        message.classList.add('is-error');
      }
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Clear visual test';
      }
    }
  }

  function start() {
    if (!installCard()) {
      window.setTimeout(start, 100);
      return;
    }
    refreshStatus(false);
    refreshTimer = window.setInterval(() => refreshStatus(false), REFRESH_MS);
  }

  window.addEventListener('pagehide', () => {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
  });

  start();
})();
