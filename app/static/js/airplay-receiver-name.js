(() => {
  const page = document.querySelector('.airplay-page');
  const title = document.getElementById('airplay-title');
  const detail = document.getElementById('airplay-detail');
  if (!page || !title || !detail) {
    return;
  }

  const configuredName = String(page.dataset.configuredReceiverName || '').trim();
  const renderedName = String(page.dataset.receiverName || '').trim();
  if (!configuredName) {
    return;
  }

  // This is a one-time compatibility repair for the server-rendered ready copy.
  // airplay-live.js remains the sole ongoing owner of title and detail text.
  const currentTitle = title.textContent.trim();
  if (!renderedName || currentTitle === renderedName || currentTitle === configuredName) {
    title.textContent = configuredName;
  }

  if (renderedName && renderedName !== configuredName && detail.textContent.includes(renderedName)) {
    detail.textContent = detail.textContent.split(renderedName).join(configuredName);
  }
})();
