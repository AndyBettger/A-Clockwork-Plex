(() => {
  const page = document.querySelector('.airplay-page');
  const title = document.getElementById('airplay-title');
  const detail = document.getElementById('airplay-detail');
  if (!page || !title || !detail) {
    return;
  }

  const configuredName = String(page.dataset.configuredReceiverName || '').trim();
  const renderedName = String(page.dataset.receiverName || '').trim();
  const receiverName = configuredName || renderedName || 'A Clockwork Plex';

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

    replaceOnlyWhenChanged(title, receiverName);

    const detailText = detail.textContent;
    if (renderedName && renderedName !== receiverName && detailText.includes(renderedName)) {
      replaceOnlyWhenChanged(detail, detailText.split(renderedName).join(receiverName));
    } else if (configuredName && detailText.includes(configuredName) === false) {
      const fallbackNames = [renderedName, 'A Clockwork Plex'].filter(Boolean);
      let nextDetail = detailText;
      for (const fallbackName of fallbackNames) {
        if (nextDetail.includes(fallbackName)) {
          nextDetail = nextDetail.split(fallbackName).join(configuredName);
          break;
        }
      }
      replaceOnlyWhenChanged(detail, nextDetail);
    }

    normalising = false;
  }

  const observer = new MutationObserver(normaliseReadyCopy);
  observer.observe(title, { childList: true, characterData: true, subtree: true });
  observer.observe(detail, { childList: true, characterData: true, subtree: true });
  normaliseReadyCopy();
})();
