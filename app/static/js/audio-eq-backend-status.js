(() => {
  if (window.__aClockworkPlexEqBackendStatusLoaded) return;
  window.__aClockworkPlexEqBackendStatusLoaded = true;

  const style = document.createElement('style');
  style.textContent = `
    html[data-acp-eq-backend="offline"] #acp-eq-health,
    html[data-acp-eq-backend="offline"] #acp-eq-settings-health {
      font-size: 0 !important;
    }

    html[data-acp-eq-backend="offline"] #acp-eq-health::after,
    html[data-acp-eq-backend="offline"] #acp-eq-settings-health::after {
      content: "Backend offline";
      font-size: 0.72rem;
    }

    html[data-acp-eq-backend="unavailable"] #acp-eq-health,
    html[data-acp-eq-backend="unavailable"] #acp-eq-settings-health {
      font-size: 0 !important;
    }

    html[data-acp-eq-backend="unavailable"] #acp-eq-health::after,
    html[data-acp-eq-backend="unavailable"] #acp-eq-settings-health::after {
      content: "Backend unavailable";
      font-size: 0.72rem;
    }
  `;
  document.head.appendChild(style);

  fetch('/api/audio/eq', { cache: 'no-store' })
    .then((response) => response.json())
    .then((payload) => {
      const state = String(payload?.eq?.backend_state || '').trim().toLowerCase();
      if (['offline', 'unavailable', 'active'].includes(state)) {
        document.documentElement.dataset.acpEqBackend = state;
      }
    })
    .catch(() => {
      document.documentElement.dataset.acpEqBackend = 'unavailable';
    });
})();
