(() => {
  const readings = document.querySelectorAll('.weather-detail-page .wind-readings strong');
  if (!readings.length) {
    return;
  }

  readings.forEach((element) => {
    const rawValue = String(element.textContent || '').trim();
    const match = rawValue.match(/^([+-]?\d+(?:\.\d+)?)(.*)$/);
    if (!match) {
      return;
    }

    const numeric = Number(match[1]);
    if (!Number.isFinite(numeric)) {
      return;
    }

    const paddedValue = numeric.toFixed(1).padStart(4, '0');
    element.textContent = `${paddedValue}${match[2]}`;
    element.setAttribute('aria-label', rawValue);
  });
})();
