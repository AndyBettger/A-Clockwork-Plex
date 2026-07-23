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

  function replaceOnlyWhenChanged(element, nextText) {
    if (!element || element.textContent === nextText) {
      return false;
    }
    element.textContent = nextText;
    return true;
  }

  function normaliseReadyCopy() {
    if (normalising) {
      return;
    }
    normalising = true;

    const currentTitle = title.textContent.trim();
    if (configuredName && currentTitle === configuredName && receiverName !== currentTitle) {
      replaceOnlyWhenChanged(title, receiverName);
    }

    const detailText = detail.textContent;
    if (configuredName && detailText.includes(configuredName)) {
      const nextDetail = detailText.split(configuredName).join(receiverName);
      replaceOnlyWhenChanged(detail, nextDetail);
    }

    normalising = false;
  }

  const observer = new MutationObserver(normaliseReadyCopy);
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  observer.observe(detail, { childList: true, characterData: true, subtree: true });
  normaliseReadyCopy();
})();
