(() => {
  const version = document.getElementById('about-version');
  const release = document.getElementById('about-release');
  const tag = document.getElementById('about-tag');
  const message = document.getElementById('about-message');
  const repositoryLink = document.getElementById('about-repository-link');
  const companionLink = document.getElementById('about-companion-link');

  if (!version || !release || !tag || !message) {
    return;
  }

  const messages = [
    'System status: Mostly harmless.',
    'The answer remains 42. The alarm clock remains under careful supervision.',
    'Towel status: regrettably unverified.',
    'Don’t panic. Unless Classic Klaxon preview is active.',
    'Plexamp connected. Vogon poetry filter unavailable.',
    'Current improbability level: inconveniently measurable.',
  ];

  const messageIndex = Math.floor(Math.random() * messages.length);
  message.textContent = messages[messageIndex] || messages[0];

  fetch('/static/app-version.json', { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Version metadata returned ${response.status}`);
      }
      return response.json();
    })
    .then((metadata) => {
      version.textContent = metadata.version ? `v${metadata.version}` : 'Development build';
      release.textContent = metadata.release_name || 'Development build';
      tag.textContent = metadata.tag || 'Unreleased';

      if (repositoryLink && metadata.repository) {
        repositoryLink.href = metadata.repository;
        repositoryLink.querySelector('span').textContent = metadata.repository.replace(/^https?:\/\//, '');
      }
      if (companionLink && metadata.companion_repository) {
        companionLink.href = metadata.companion_repository;
        companionLink.querySelector('span').textContent = metadata.companion_repository.replace(/^https?:\/\//, '');
      }
    })
    .catch(() => {
      version.textContent = 'Development build';
      release.textContent = 'Metadata temporarily hiding behind the sofa';
      tag.textContent = 'Unknown';
    });

  const schedulerStatusScript = document.createElement('script');
  schedulerStatusScript.src = '/static/js/settings-alarm-scheduler.js';
  schedulerStatusScript.async = false;
  document.head.appendChild(schedulerStatusScript);
})();
