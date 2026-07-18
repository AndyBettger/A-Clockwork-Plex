(() => {
  const page = document.querySelector('.airplay-page');
  const title = document.getElementById('airplay-title');
  const detail = document.getElementById('airplay-detail');
  if (!page || !title || !detail) {
    return;
  }

  const configuredName = String(page.dataset.configuredReceiverName || '').trim();
  const receiverName = String(page.dataset.receiverName || configuredName)
    .replace(/\s+Plexamp$/i, '')
    .trim() || configuredName || 'A Clockwork Plex';

  let normalising = false;

  function normaliseReadyCopy() {
    if (normalising) {
      return;
    }
    normalising = true;

    if (configuredName && title.textContent.trim() === configuredName) {
      title.textContent = receiverName;
    }

    const detailText = detail.textContent;
    if (configuredName && detailText.includes(configuredName)) {
      detail.textContent = detailText.split(configuredName).join(receiverName);
    }

    normalising = false;
  }

  const observer = new MutationObserver(normaliseReadyCopy);
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  observer.observe(detail, { childList: true, characterData: true, subtree: true });
  normaliseReadyCopy();
})();