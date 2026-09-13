(() => {
  if (String(document.body?.dataset?.activePage || '').toLowerCase() !== 'settings') return;
  if (window.__aClockworkPlexNewsFeedDiscoveryLoaded) return;
  window.__aClockworkPlexNewsFeedDiscoveryLoaded = true;

  const feedSubpage = document.querySelector('[data-settings-subpage="news:feeds"]');
  const editorList = feedSubpage?.querySelector('[data-news-feed-editor-list]');
  const globalMessage = feedSubpage?.querySelector('[data-news-feed-editor-message]');
  if (!feedSubpage || !editorList || !globalMessage) return;

  const BBC_PAGE_HOSTS = new Set(['bbc.co.uk', 'www.bbc.co.uk', 'bbc.com', 'www.bbc.com']);
  const SAFE_PATH_SEGMENT = /^[A-Za-z0-9_-]+$/;
  const DEFAULT_GUIDANCE = 'Paste a BBC News section page URL or a feeds.bbci.co.uk RSS address, then press Check feed. A successful check is required before the custom feed can be used.';
  const PAGE_HELP = 'Add a custom BBC News section by pasting its normal BBC News page URL, or paste a feeds.bbci.co.uk RSS address directly. Built-in BBC sections keep their standard names and URLs; use Feed order to enable and arrange them.';
  const ROW_HELP = 'Add and manage custom BBC News sections by page or RSS URL';
  const FIELD_CAPTION = 'BBC News page or RSS URL';
  const FIELD_HELP = 'Paste a BBC News section page, for example https://www.bbc.co.uk/news/england/sussex, or a feeds.bbci.co.uk RSS address, then press Check feed.';
  const localStatusByUrl = new Map();
  let activeCheck = null;
  let resettingGlobalMessage = false;

  function clean(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
  }

  function setTextIfChanged(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function isCustomCard(card) {
    const source = clean(card?.querySelector('.settings-card-heading .muted.small')?.textContent);
    return source.startsWith('Custom BBC News feed');
  }

  function urlField(card) {
    if (!isCustomCard(card)) return null;
    return card.querySelector('.setting-field.wide');
  }

  function urlInput(card) {
    return urlField(card)?.querySelector('input') || null;
  }

  function refreshPageGuidance() {
    const feedHelp = feedSubpage.querySelector('.settings-card .settings-card-heading .muted.small');
    setTextIfChanged(feedHelp, PAGE_HELP);
    const row = document.querySelector('[data-settings-overview="news"] [data-settings-subpage-target="news:feeds"]');
    setTextIfChanged(row?.querySelector('small'), ROW_HELP);
  }

  function bbcNewsPageToFeedUrl(value) {
    const text = clean(value);
    if (!text) return '';
    let parsed;
    try {
      parsed = new URL(text);
    } catch (_error) {
      return '';
    }
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) return '';
    if (parsed.port && parsed.port !== '443') return '';
    const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
    if (!BBC_PAGE_HOSTS.has(host)) return '';

    const path = parsed.pathname.replace(/\/+$/, '') || '/news';
    const segments = path.split('/').filter(Boolean);
    if (!segments.length || segments[0].toLowerCase() !== 'news') return '';
    if (segments.some((segment) => !SAFE_PATH_SEGMENT.test(segment))) return '';

    const feedPath = segments.length === 1 ? '/news/rss.xml' : `/${segments.join('/')}/rss.xml`;
    return `https://feeds.bbci.co.uk${feedPath}`;
  }

  function statusTextNode(status) {
    const paragraph = document.createElement('p');
    paragraph.className = 'small news-feed-check-status';
    paragraph.dataset.newsFeedCheckStatus = '';
    paragraph.setAttribute('aria-live', 'polite');
    paragraph.dataset.newsFeedCheckText = status.text;
    paragraph.dataset.newsFeedCheckError = status.error ? 'true' : 'false';
    if (status.error) {
      const strong = document.createElement('strong');
      strong.textContent = 'Feed check failed: ';
      paragraph.append(strong, document.createTextNode(status.text.replace(/^Feed check failed:\s*/i, '')));
    } else {
      paragraph.textContent = status.text;
    }
    return paragraph;
  }

  function decorateCard(card) {
    if (!isCustomCard(card)) return;
    const field = urlField(card);
    const input = urlInput(card);
    if (!field || !input) return;

    setTextIfChanged(field.querySelector(':scope > span'), FIELD_CAPTION);
    setTextIfChanged(field.querySelector(':scope > small'), FIELD_HELP);

    const status = localStatusByUrl.get(clean(input.value));
    const existing = card.querySelector('[data-news-feed-check-status]');
    if (!status) {
      existing?.remove();
      return;
    }
    if (
      existing
      && existing.dataset.newsFeedCheckText === status.text
      && existing.dataset.newsFeedCheckError === (status.error ? 'true' : 'false')
    ) {
      return;
    }

    existing?.remove();
    const actions = card.querySelector('.settings-action-row');
    const local = statusTextNode(status);
    if (actions) actions.insertAdjacentElement('afterend', local);
    else card.appendChild(local);
  }

  function decorateAllCards() {
    editorList.querySelectorAll('[data-news-feed-editor-id]').forEach(decorateCard);
  }

  function statusLooksLikeValidation(text) {
    return text.startsWith('Checking ')
      || text.startsWith('Feed checked successfully')
      || text.startsWith('Feed check failed:')
      || text === 'Enter the BBC RSS URL before checking this feed.'
      || text.startsWith('That BBC RSS URL is already present');
  }

  function localiseValidationMessage() {
    if (resettingGlobalMessage) return;
    const text = clean(globalMessage.textContent);

    if (!statusLooksLikeValidation(text)) {
      if (
        text.includes('before Save Changes')
        || text.startsWith('Enter a BBC News RSS URL, press Check feed')
        || text.startsWith('Custom feeds must pass a live BBC RSS check')
      ) {
        resettingGlobalMessage = true;
        setTextIfChanged(globalMessage, DEFAULT_GUIDANCE);
        resettingGlobalMessage = false;
      }
      return;
    }
    if (!activeCheck) return;

    let localText = text;
    if (activeCheck.fromPage && text.startsWith('Feed checked successfully')) {
      localText = `BBC News page found. ${text}`;
    } else if (text.startsWith('Feed check failed: Feed must be an HTTPS BBC News RSS URL')) {
      localText = 'Feed check failed: enter an HTTPS BBC News section page on bbc.co.uk/bbc.com, or a BBC News RSS URL on feeds.bbci.co.uk.';
    } else if (text === 'Enter the BBC RSS URL before checking this feed.') {
      localText = 'Feed check failed: enter a BBC News section page or RSS URL before pressing Check feed.';
    }

    localStatusByUrl.set(activeCheck.url, {
      text: localText,
      error: localText.startsWith('Feed check failed:') || localText.startsWith('That BBC RSS URL'),
    });
    decorateAllCards();

    resettingGlobalMessage = true;
    setTextIfChanged(globalMessage, DEFAULT_GUIDANCE);
    resettingGlobalMessage = false;
  }

  feedSubpage.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || clean(button.textContent) !== 'Check feed') return;
    const card = button.closest('[data-news-feed-editor-id]');
    const input = urlInput(card);
    if (!card || !input) return;

    const original = clean(input.value);
    const derivedFeed = bbcNewsPageToFeedUrl(original);
    if (derivedFeed) {
      input.value = derivedFeed;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    const checkedValue = clean(input.value);
    activeCheck = {
      url: checkedValue,
      fromPage: Boolean(derivedFeed),
    };
    localStatusByUrl.delete(checkedValue);
    if (checkedValue) {
      localStatusByUrl.set(checkedValue, {
        text: derivedFeed ? 'Found the BBC News page; checking its RSS feed…' : 'Checking BBC RSS feed…',
        error: false,
      });
      decorateAllCards();
    }
  }, { capture: true });

  feedSubpage.addEventListener('input', (event) => {
    const input = event.target;
    const card = input?.closest?.('[data-news-feed-editor-id]');
    if (!card || input !== urlInput(card)) return;
    if (activeCheck && clean(input.value) !== activeCheck.url) {
      localStatusByUrl.delete(activeCheck.url);
      activeCheck = null;
    }
    card.querySelector('[data-news-feed-check-status]')?.remove();
  }, { capture: true });

  const messageObserver = new MutationObserver(localiseValidationMessage);
  messageObserver.observe(globalMessage, { childList: true, characterData: true, subtree: true });

  // settings-news.js replaces/appends whole editor cards as direct children of
  // editorList. Observe only that boundary. Watching the entire subtree would
  // see our own caption/help/status decorations and can create a self-sustaining
  // MutationObserver loop that starves the Settings page event loop.
  const editorObserver = new MutationObserver(() => {
    refreshPageGuidance();
    decorateAllCards();
  });
  editorObserver.observe(editorList, { childList: true });

  refreshPageGuidance();
  decorateAllCards();
  localiseValidationMessage();
  window.setTimeout(() => {
    refreshPageGuidance();
    decorateAllCards();
    localiseValidationMessage();
  }, 0);
})();
