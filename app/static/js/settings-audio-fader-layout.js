(() => {
  if (window.__aClockworkPlexAudioFaderLayoutLoaded) {
    return;
  }
  window.__aClockworkPlexAudioFaderLayoutLoaded = true;

  function installStyles() {
    if (document.querySelector('link[data-audio-console-mk2-styles]')) {
      return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/settings-audio-console-mk2.css';
    link.dataset.audioConsoleMk2Styles = 'true';
    document.head.appendChild(link);
  }

  function install() {
    installStyles();
    const card = document.getElementById('audio-mixer-card');
    if (!card) {
      window.setTimeout(install, 100);
      return;
    }

    card.classList.add('is-console-mk2');
    card.querySelectorAll('.audio-mixer-pcm').forEach((element) => element.remove());

    card.querySelectorAll('.audio-mixer-control-row').forEach((row) => {
      if (!row.querySelector('.audio-fader-scale-label.is-top')) {
        const top = document.createElement('span');
        top.className = 'audio-fader-scale-label is-top';
        top.textContent = '11';
        top.setAttribute('aria-hidden', 'true');
        row.appendChild(top);
      }
      if (!row.querySelector('.audio-fader-scale-label.is-bottom')) {
        const bottom = document.createElement('span');
        bottom.className = 'audio-fader-scale-label is-bottom';
        bottom.textContent = '0';
        bottom.setAttribute('aria-hidden', 'true');
        row.appendChild(bottom);
      }
    });
  }

  install();
})();
