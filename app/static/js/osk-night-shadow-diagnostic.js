(() => {
  'use strict';

  // Manual C3 evidence capture ONLY. URL opt-in avoids production Settings UI
  // clutter. No timer, storage, CSS selection or native keyboard ownership.
  if (!new URLSearchParams(window.location.search).has('c3-shadow')) return;

  const ENDPOINT = '/api/osk/c3/night-shadow/compare';
  let previousSequence = null;
  let busy = false;

  function browserAlarmVisible() {
    return window.location.pathname === '/alarm'
      || String(document.body?.dataset?.activePage || '').toLowerCase() === 'alarm'
      || Boolean(document.body?.classList.contains('mode-alarm'));
  }

  function observation() {
    const status = window.ACPDisplayDimming?.status?.();
    if (!status) throw new Error('ACP night status is unavailable');
    const fields = [
      'enabled', 'start', 'end', 'style', 'activeStyle',
      'wakeSeconds', 'scheduled', 'active', 'previewing',
      'interacting', 'effectiveStyle',
    ];
    const browserStatus = {};
    for (const key of fields) browserStatus[key] = status[key];
    return {
      browserStatus,
      browserAlarmVisible: browserAlarmVisible(),
      priorSequence: previousSequence,
    };
  }

  function install() {
    if (document.body?.dataset?.activePage !== 'settings'
        || document.getElementById('acp-c3-shadow-inspector')) return;

    const panel = document.createElement('aside');
    panel.id = 'acp-c3-shadow-inspector';
    panel.setAttribute('aria-label', 'Manual C3 night comparison');
    Object.assign(panel.style, {
      position: 'fixed', right: '16px', bottom: '62px',
      width: 'min(92vw, 500px)', maxHeight: '65vh',
      overflow: 'auto', zIndex: '10020', padding: '12px',
      background: '#111c2c', color: '#ecf4ff',
      border: '1px solid #6ea7d8', borderRadius: '12px',
      boxShadow: '0 8px 28px #0009',
    });
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Compare C3 night state (read-only)';
    button.setAttribute('aria-label', button.textContent);
    button.style.cssText = 'font-size:16px;padding:9px;max-width:100%;cursor:pointer';
    const output = document.createElement('pre');
    output.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:42vh;overflow:auto;';
    output.textContent = 'Manual one-shot only. No CSS or keyboard changes.';

    button.addEventListener('click', async () => {
      if (busy) return;
      busy = true;
      button.disabled = true;
      output.textContent = 'Comparing current browser and server observations…';
      try {
        const request = JSON.stringify(observation());
        const response = await fetch(ENDPOINT, {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
          headers: { 'Content-Type': 'application/json' },
          body: request,
        });
        const result = await response.json();
        if (response.ok && result?.ok === true) {
          previousSequence = result.inputSequence;
          output.textContent = JSON.stringify(result, null, 2);
        } else {
          previousSequence = null;
          output.textContent = 'No comparison: ' + (result?.error || response.status);
        }
      } catch (_error) {
        previousSequence = null;
        output.textContent = 'Read-only comparison unavailable; no changes made.';
      } finally {
        busy = false;
        button.disabled = false;
      }
    });

    panel.append(button, output);
    document.body.appendChild(panel);
  }

  // The explicit URL flag is the *only* entry point. No polling/event loops.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
