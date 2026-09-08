(() => {
  'use strict';

  function installNativePortabilityBridge(doc) {
    if (!doc?.documentElement) return;
    if (typeof chrome === 'undefined' || typeof chrome.runtime?.getURL !== 'function') return;
    if (doc.getElementById('acp-plexamp-native-portability-bridge')) return;

    const script = doc.createElement('script');
    script.id = 'acp-plexamp-native-portability-bridge';
    script.src = chrome.runtime.getURL('native-portability.js');
    script.async = false;
    const cleanup = () => script.remove();
    script.addEventListener('load', cleanup, { once: true });
    script.addEventListener('error', cleanup, { once: true });
    (doc.head || doc.documentElement).append(script);
  }

  if (typeof document !== 'undefined') installNativePortabilityBridge(document);
})();
