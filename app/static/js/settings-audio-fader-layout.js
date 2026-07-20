(() => {
  if (window.__aClockworkPlexAudioFaderLayoutLoaded) {
    return;
  }
  window.__aClockworkPlexAudioFaderLayoutLoaded = true;

  function install() {
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
