(() => {
  if (window.__aClockworkPlexAlarmWorkspaceLoaded) return;
  window.__aClockworkPlexAlarmWorkspaceLoaded = true;

  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;

  const form = document.querySelector('.settings-form');
  const alarmPanel = document.getElementById('settings-panel-alarms');
  const advancedPanel = document.getElementById('settings-panel-advanced');
  if (!form || !alarmPanel || !advancedPanel) return;

  let reconcileTimer = null;
  let saveListenersInstalled = false;

  const byId = (id) => document.getElementById(id);

  function installStyles() {
    if (document.querySelector('link[data-alarm-workspace-styles]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/settings-alarm-workspace.css';
    link.dataset.alarmWorkspaceStyles = 'true';
    document.head.appendChild(link);
  }

  function updateAlarmIntro() {
    const intro = alarmPanel.querySelector('.settings-card.is-intro');
    const chip = intro?.querySelector('.settings-chip');
    const copy = intro?.querySelector('p');
    if (chip) chip.textContent = 'Scheduled alarms';
    if (copy) {
      copy.textContent = 'Create and organise alarms while the persistent runtime handles timing, screen takeover, sound, Snooze and Dismiss.';
    }
    return Boolean(intro);
  }

  function saveMessage(text, tone = 'info') {
    const message = byId('alarm-workspace-save-message');
    if (!message) return;
    message.textContent = text;
    message.classList.toggle('is-error', tone === 'error');
    message.classList.toggle('is-dirty', tone === 'dirty');
  }

  function installSaveListeners() {
    if (saveListenersInstalled) return;
    saveListenersInstalled = true;

    const marksAlarmModel = (target) => Boolean(
      target?.closest?.('#alarm-model-defaults, #alarm-list, #alarm-add-button')
    );

    alarmPanel.addEventListener('input', (event) => {
      if (marksAlarmModel(event.target)) saveMessage('Unsaved alarm changes.', 'dirty');
    });
    alarmPanel.addEventListener('change', (event) => {
      if (marksAlarmModel(event.target)) saveMessage('Unsaved alarm changes.', 'dirty');
    });
    alarmPanel.addEventListener('click', (event) => {
      if (event.target.closest('#alarm-add-button, .alarm-day-button, .alarm-card-actions button')) {
        saveMessage('Unsaved alarm changes.', 'dirty');
      }
    });

    form.addEventListener('submit', (event) => {
      if (event.submitter?.id !== 'alarm-workspace-save') return;
      saveMessage('Saving alarm schedule…');
      const button = byId('alarm-workspace-save');
      if (button) {
        button.disabled = true;
        window.setTimeout(() => { button.disabled = false; }, 5000);
      }
    });
  }

  function ensureAlarmSaveCard() {
    if (!byId('alarm-list') || !byId('alarm-model-defaults')) return false;
    if (byId('alarm-workspace-save-card')) return true;

    const card = document.createElement('section');
    card.id = 'alarm-workspace-save-card';
    card.className = 'settings-card alarm-workspace-save-card';
    card.innerHTML = `
      <div>
        <h2>Save alarm schedule</h2>
        <p class="muted small">Alarm cards are validated and saved together as one schedule.</p>
      </div>
      <div class="alarm-workspace-save-actions">
        <span class="muted small" id="alarm-workspace-save-message">No unsaved alarm changes.</span>
        <button
          class="button settings-save"
          id="alarm-workspace-save"
          type="submit"
          data-dedicated-settings-save="alarms"
        >Save alarms</button>
      </div>
    `;

    const configuredCard = byId('alarm-list')?.closest('.settings-card');
    if (configuredCard) configuredCard.insertAdjacentElement('afterend', card);
    else alarmPanel.appendChild(card);
    installSaveListeners();
    return true;
  }

  function ensureAdvancedWorkspace() {
    const intro = advancedPanel.querySelector('.settings-card.is-intro');
    const chip = intro?.querySelector('.settings-chip');
    const copy = intro?.querySelector('p');
    if (chip) chip.textContent = 'Live tools';
    if (copy) copy.textContent = 'Alarm testing, runtime diagnostics and hardware controls, kept away from everyday alarm editing.';

    advancedPanel.querySelector('.settings-card.is-placeholder')?.remove();

    let workspace = byId('alarm-advanced-workspace');
    if (!workspace) {
      workspace = document.createElement('div');
      workspace.id = 'alarm-advanced-workspace';
      workspace.className = 'alarm-advanced-workspace';
      advancedPanel.appendChild(workspace);
    }
    return workspace;
  }

  function moveSchedulerDiagnostics(workspace) {
    const card = byId('alarm-scheduler-status-card');
    if (!card) return false;
    if (card.parentElement !== workspace) workspace.appendChild(card);
    return true;
  }

  function reshapeAlarmAudio(workspace) {
    const card = byId('alarm-audio-card');
    const scheduledToggle = byId('alarm-audio-scheduled-enabled');
    if (!card || !scheduledToggle) return false;

    const heading = card.querySelector('.settings-card-heading h2');
    const headingCopy = card.querySelector('.settings-card-heading p');
    if (heading) heading.textContent = 'Alarm sound safety';
    if (headingCopy) {
      headingCopy.textContent = 'Two deliberate safety keys control whether scheduled alarms may use the shared alarm output.';
    }

    const masterCopy = card.querySelector('.alarm-audio-master span');
    const masterTitle = masterCopy?.querySelector('strong');
    const masterDetail = masterCopy?.querySelector('small');
    if (masterTitle) masterTitle.textContent = 'Enable alarm sound';
    if (masterDetail) masterDetail.textContent = 'Master safety key for scheduled alarms and deliberate audio tests.';

    let advancedCard = byId('alarm-audio-advanced-card');
    if (!advancedCard) {
      advancedCard = document.createElement('section');
      advancedCard.id = 'alarm-audio-advanced-card';
      advancedCard.className = 'settings-card alarm-audio-advanced-card';
      advancedCard.innerHTML = `
        <div class="settings-card-heading">
          <div>
            <h2>Alarm testing and audio diagnostics</h2>
            <p class="muted small">Controlled tests, shared-mixer configuration and the physical alarm path.</p>
          </div>
          <span class="settings-chip">Advanced</span>
        </div>
        <div class="alarm-audio-grid alarm-audio-advanced-grid"></div>
      `;
      workspace.appendChild(advancedCard);
    }

    const normalGrid = card.querySelector('.alarm-audio-grid');
    const advancedGrid = advancedCard.querySelector('.alarm-audio-advanced-grid');
    if (normalGrid && advancedGrid) {
      [...normalGrid.children].forEach((child) => {
        if (child.matches('.alarm-audio-master, .alarm-audio-scheduled-toggle')) return;
        advancedGrid.appendChild(child);
      });
    }

    const ordinarySaveRow = [...card.querySelectorAll('.alarm-audio-save-row')]
      .find((row) => !row.classList.contains('alarm-audio-scheduled-save-row'));
    if (ordinarySaveRow) advancedCard.appendChild(ordinarySaveRow);

    const testPanel = card.querySelector('.alarm-audio-test-panel');
    if (testPanel) advancedCard.appendChild(testPanel);
    const readings = card.querySelector('.alarm-audio-readings');
    if (readings) advancedCard.appendChild(readings);

    if (card.parentElement !== alarmPanel) {
      const saveCard = byId('alarm-workspace-save-card');
      if (saveCard) saveCard.insertAdjacentElement('afterend', card);
      else alarmPanel.appendChild(card);
    }
    return true;
  }

  function reconcile() {
    installStyles();
    const introReady = updateAlarmIntro();
    const saveReady = ensureAlarmSaveCard();
    const workspace = ensureAdvancedWorkspace();
    const schedulerReady = moveSchedulerDiagnostics(workspace);
    const audioReady = reshapeAlarmAudio(workspace);

    if (introReady && saveReady && schedulerReady && audioReady && reconcileTimer) {
      window.clearInterval(reconcileTimer);
      reconcileTimer = null;
    }
  }

  reconcile();
  reconcileTimer = window.setInterval(reconcile, 150);
  window.setTimeout(reconcile, 0);

  window.addEventListener('pagehide', () => {
    if (reconcileTimer) window.clearInterval(reconcileTimer);
  });
})();
