(() => {
  const slider = document.getElementById('airplay-volume-slider');
  const label = document.getElementById('airplay-volume-label');

  if (!slider) {
    return;
  }

  let heldPercent = null;
  let heldLabel = null;
  let heldUntil = 0;
  let activePointer = false;

  function clamp(number, min, max) {
    return Math.min(max, Math.max(min, number));
  }

  function dbFromUiPercent(percent) {
    const cleanPercent = clamp(Number(percent), 0, 100);
    if (cleanPercent <= 0) {
      return 'Muted';
    }
    const db = (cleanPercent / 100) * 30 - 30;
    return `${db.toFixed(1)} dB`;
  }

  function rememberVolume(percent, durationMs = 14000) {
    heldPercent = clamp(Number(percent), 0, 100);
    heldLabel = dbFromUiPercent(heldPercent);
    heldUntil = Math.max(heldUntil, Date.now() + durationMs);
    applyHeldVolume();
  }

  function applyHeldVolume() {
    if (heldPercent === null || Date.now() > heldUntil) {
      heldPercent = null;
      heldLabel = null;
      return;
    }

    const rounded = String(Math.round(heldPercent));
    if (slider.value !== rounded) {
      slider.value = rounded;
    }

    document.body.style.setProperty('--airplay-volume-percent', `${heldPercent}%`);

    if (label && heldLabel) {
      label.textContent = heldLabel;
    }
  }

  slider.addEventListener('pointerdown', () => {
    activePointer = true;
    rememberVolume(slider.value, 18000);
  }, { capture: true });

  slider.addEventListener('input', () => {
    rememberVolume(slider.value, 18000);
  }, { capture: true });

  slider.addEventListener('change', () => {
    rememberVolume(slider.value, 18000);
  }, { capture: true });

  slider.addEventListener('pointerup', () => {
    activePointer = false;
    rememberVolume(slider.value, 18000);
  }, { capture: true });

  slider.addEventListener('pointercancel', () => {
    activePointer = false;
    rememberVolume(slider.value, 12000);
  }, { capture: true });

  window.setInterval(() => {
    if (activePointer || heldPercent !== null) {
      applyHeldVolume();
    }
  }, 120);
})();