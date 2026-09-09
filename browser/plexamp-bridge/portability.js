(() => {
  'use strict';

  function installPageBridge(doc, id, filename) {
    if (!doc?.documentElement) return;
    if (typeof chrome === 'undefined' || typeof chrome.runtime?.getURL !== 'function') return;
    if (doc.getElementById(id)) return;

    const script = doc.createElement('script');
    script.id = id;
    script.src = chrome.runtime.getURL(filename);
    script.async = false;
    const cleanup = () => script.remove();
    script.addEventListener('load', cleanup, { once: true });
    script.addEventListener('error', cleanup, { once: true });
    (doc.head || doc.documentElement).append(script);
  }

  function installPortabilityBridges(doc) {
    installPageBridge(doc, 'acp-plexamp-native-portability-bridge', 'native-portability.js');
    installPageBridge(doc, 'acp-plexamp-home-portability-v2-bridge', 'home-portability-v2.js');
  }

  if (typeof document !== 'undefined') installPortabilityBridges(document);
})();
