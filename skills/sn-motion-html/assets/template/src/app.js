(async function boot() {
  const root = document.getElementById('experience');
  const bootScreen = document.getElementById('boot');
  const dialog = document.getElementById('sources');
  try {
    const response = await fetch('content/story.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`story.json returned ${response.status}`);
    const story = await response.json();
    document.title = story.meta.title;
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = story.meta.description || story.meta.subtitle || story.meta.title;
    document.documentElement.dataset.style = story.meta.style || 'cinematic';
    document.documentElement.dataset.ui = story.meta.ui || 'folio';
    if (story.meta.accent) {
      document.documentElement.style.setProperty('--mh-accent', story.meta.accent);
    }
    window.mountMotionHTML(root, {
      title: story.meta.title,
      kicker: story.meta.kicker,
      subtitle: story.meta.subtitle,
      ui: story.meta.ui || 'folio',
      accent: story.meta.accent,
      chapters: story.chapters,
      connectors: story.connectors,
      connectorSpan: story.meta.connectorSpan || 1.2,
    });

    document.getElementById('adaptation-note').textContent = story.meta.note || '';
    const sourceList = document.getElementById('source-list');
    for (const source of story.sources || []) {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = source.url;
      link.textContent = source.label;
      link.target = '_blank';
      link.rel = 'noreferrer';
      li.appendChild(link);
      sourceList.appendChild(li);
    }

    document.addEventListener('click', (event) => {
      if (event.target.closest('a[href="#sources"]')) {
        event.preventDefault();
        dialog.showModal();
      }
    });
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  } catch (error) {
    console.error(error);
    bootScreen.textContent = 'Could not load story data. Open this project through HTTP.';
    return;
  }
  bootScreen.classList.add('is-hidden');
  setTimeout(() => bootScreen.remove(), 400);
})();
