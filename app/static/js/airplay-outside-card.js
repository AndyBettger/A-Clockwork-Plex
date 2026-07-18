(() => {
  const source = document.getElementById('airplay-outside-now');
  const temperature = document.getElementById('airplay-outside-temperature');
  const humidity = document.getElementById('airplay-outside-humidity');

  if (!source || !temperature || !humidity) {
    return;
  }

  let lastRawValue = null;

  function sourceValue() {
    return String(source.dataset.segmentSource || source.textContent || '').trim();
  }

  function syncOutsideReadings() {
    const rawValue = sourceValue();
    if (!rawValue || rawValue === lastRawValue) {
      return;
    }
    lastRawValue = rawValue;

    const parts = rawValue
      .split('·')
      .map((part) => part.trim())
      .filter(Boolean);

    const temperatureValue = parts[0] || 'Waiting';
    const humidityValue = parts[1] || '—';

    temperature.textContent = temperatureValue;
    humidity.textContent = humidityValue;
    temperature.setAttribute('aria-label', `Outdoor temperature ${temperatureValue}`);
    humidity.setAttribute('aria-label', `Outdoor humidity ${humidityValue}`);

    window.AClockworkSegmentReadouts?.refresh?.();
  }

  const observer = new MutationObserver(syncOutsideReadings);
  observer.observe(source, {
    childList: true,
    characterData: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-segment-source'],
  });

  syncOutsideReadings();
  window.setInterval(syncOutsideReadings, 1000);
})();
