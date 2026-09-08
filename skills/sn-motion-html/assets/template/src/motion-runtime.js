(function expose(global) {
  global.mountMotionHTML = function mountMotionHTML(container, config) {
    const chapters = config.chapters || [];
    const connectorUrls = config.connectors || [];
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
    const smooth = (value) => {
      const x = clamp(value);
      return x * x * (3 - 2 * x);
    };
    const node = (tag, className) => {
      const element = document.createElement(tag);
      element.className = className || '';
      return element;
    };
    const escapeHtml = (value) => String(value).replace(
      /[&<>\"]/g,
      (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[character]),
    );

    container.className = 'mh-root';
    container.replaceChildren();
    document.documentElement.dataset.ui = config.ui || 'folio';

    const stage = node('div', 'mh-stage');
    const copyLayer = node('div', 'mh-copy-layer');
    const header = node('header', 'mh-header');
    const brand = node('a', 'mh-brand');
    brand.href = '#top';
    brand.innerHTML = `
      ${config.kicker ? `<span>${escapeHtml(config.kicker)}</span>` : ''}
      <strong>${escapeHtml(config.title || '')}</strong>
      ${config.subtitle ? `<i>${escapeHtml(config.subtitle)}</i>` : ''}`;
    const chapterStatus = node('p', 'mh-header__status');
    const sourceLink = node('a', 'mh-header__source');
    sourceLink.href = '#sources';
    sourceLink.textContent = 'Sources';
    header.append(brand, chapterStatus, sourceLink);

    const progress = node('div', 'mh-progress');
    const progressFill = node('i');
    progress.appendChild(progressFill);
    const navigation = node('nav', 'mh-route');
    navigation.setAttribute('aria-label', 'Story chapters');
    const hint = node('div', 'mh-hint');
    hint.innerHTML = '<span>Move through the story</span><i aria-hidden="true"></i>';
    const track = node('div', 'mh-track');
    container.append(stage, copyLayer, header, progress, navigation, hint, track);

    const segments = [];
    const sceneSegments = [];
    chapters.forEach((chapter, chapterIndex) => {
      const scene = {
        kind: 'scene',
        chapterIndex,
        still: chapter.still,
        clip: chapter.clip,
        units: chapter.span || 4.6,
        linger: chapter.linger || 0,
      };
      segments.push(scene);
      sceneSegments.push(scene);
      if (chapterIndex < chapters.length - 1 && connectorUrls[chapterIndex]) {
        segments.push({
          kind: 'connector',
          chapterIndex,
          still: chapter.still,
          clip: connectorUrls[chapterIndex],
          units: config.connectorSpan || 1.2,
          linger: 0,
        });
      }
    });

    segments.forEach((segment, index) => {
      const shot = node('div', 'mh-shot');
      shot.dataset.kind = segment.kind;
      const chapter = chapters[segment.chapterIndex] || {};
      const fallback = node('div', 'mh-shot__fallback');
      fallback.innerHTML = `<span>${String(index + 1).padStart(2, '0')}</span><strong>${escapeHtml(chapter.label || chapter.title || '')}</strong>`;
      const poster = node('img', 'mh-shot__poster');
      poster.alt = segment.kind === 'scene' ? (chapter.label || chapter.title || '') : '';
      poster.decoding = 'async';
      poster.loading = index < 2 ? 'eager' : 'lazy';
      if (segment.still) poster.src = segment.still;
      poster.addEventListener('error', () => shot.classList.add('is-missing'));
      shot.append(fallback, poster);
      stage.appendChild(shot);
      Object.assign(segment, {
        shot,
        poster,
        video: null,
        loading: false,
        failed: false,
        ready: false,
        visible: false,
        current: 0,
        target: 0,
      });
    });

    const copies = [];
    const navButtons = [];
    chapters.forEach((chapter, index) => {
      const article = node('article', 'mh-copy');
      article.dataset.position = chapter.copyPosition || (index % 2 ? 'right' : 'left');
      if (chapter.accent) article.style.setProperty('--mh-scene-accent', chapter.accent);
      const paragraphs = (chapter.paragraphs || []).map((text) => `<p>${escapeHtml(text)}</p>`).join('');
      const tags = (chapter.tags || []).map((text) => `<li>${escapeHtml(text)}</li>`).join('');
      article.innerHTML = `
        <p class="mh-copy__index">${String(index + 1).padStart(2, '0')} <span>/</span> ${String(chapters.length).padStart(2, '0')}</p>
        ${chapter.eyebrow ? `<p class="mh-copy__eyebrow">${escapeHtml(chapter.eyebrow)}</p>` : ''}
        <h2>${escapeHtml(chapter.title || '')}</h2>
        ${chapter.subtitle ? `<p class="mh-copy__subtitle">${escapeHtml(chapter.subtitle)}</p>` : ''}
        <div class="mh-copy__body">${paragraphs}</div>
        ${tags ? `<ul class="mh-copy__tags">${tags}</ul>` : ''}`;
      copyLayer.appendChild(article);
      copies.push(article);

      const button = node('button', 'mh-route__item');
      button.type = 'button';
      button.innerHTML = `<span>${String(index + 1).padStart(2, '0')}</span><i>${escapeHtml(chapter.label || chapter.title || '')}</i>`;
      button.setAttribute('aria-label', `Go to ${chapter.label || chapter.title || `chapter ${index + 1}`}`);
      button.addEventListener('click', () => {
        const target = sceneSegments[index]?.start || 0;
        scrollTo({ top: target, behavior: reduced ? 'auto' : 'smooth' });
      });
      navigation.appendChild(button);
      navButtons.push(button);
    });

    let viewportHeight = innerHeight;
    let viewportWidth = innerWidth;
    let totalUnits = 0;
    let readQueued = false;
    let activeChapter = -1;

    function layout() {
      viewportHeight = innerHeight;
      viewportWidth = innerWidth;
      let offset = 0;
      segments.forEach((segment) => {
        segment.start = offset * viewportHeight;
        offset += segment.units;
        segment.end = offset * viewportHeight;
      });
      totalUnits = offset;
      track.style.height = `${(totalUnits + 1) * viewportHeight}px`;
      read();
    }

    function loadClip(segment) {
      if (reduced || segment.loading || segment.failed || !segment.clip) return;
      segment.loading = true;
      fetch(segment.clip)
        .then((response) => response.ok ? response.blob() : Promise.reject(new Error(String(response.status))))
        .then((blob) => {
          const video = node('video', 'mh-shot__video');
          video.muted = true;
          video.playsInline = true;
          video.preload = 'auto';
          video.src = URL.createObjectURL(blob);
          video.addEventListener('loadedmetadata', () => {
            segment.ready = true;
            scheduleRead();
          });
          video.addEventListener('seeked', () => shotReady(segment), { once: true });
          segment.shot.appendChild(video);
          segment.video = video;
        })
        .catch(() => {
          segment.failed = true;
          segment.loading = false;
          segment.shot.classList.add('is-missing');
        });
    }

    function shotReady(segment) {
      segment.shot.classList.add('has-video');
    }

    function remapWithLinger(progress, amount) {
      if (!amount) return progress;
      const hold = clamp(amount, 0, 0.6) * 0.38;
      const left = 0.5 - hold;
      const right = 0.5 + hold;
      if (progress < left) return progress * (0.5 / left);
      if (progress > right) return 0.5 + (progress - right) * (0.5 / (1 - right));
      return 0.5;
    }

    function read() {
      const y = scrollY;
      const fadeDistance = Math.max(1, viewportHeight * 0.14);
      let currentSegment = segments[0];

      segments.forEach((segment) => {
        const local = clamp((y - segment.start) / Math.max(1, segment.end - segment.start));
        const distance = y < segment.start ? segment.start - y : y > segment.end ? y - segment.end : 0;
        const opacity = distance === 0 ? 1 : smooth(1 - distance / fadeDistance);
        segment.shot.style.opacity = opacity;
        segment.visible = opacity > 0.01;
        segment.target = remapWithLinger(local, segment.linger);
        if (y >= segment.start) currentSegment = segment;
        if (distance < viewportHeight * 2.2) loadClip(segment);
        if (!segment.ready) segment.poster.style.transform = `scale(${(1.02 + local * 0.06).toFixed(3)})`;
      });

      chapters.forEach((chapter, index) => {
        const scene = sceneSegments[index];
        const local = clamp((y - scene.start) / Math.max(1, scene.end - scene.start));
        const inside = y >= scene.start && y <= scene.end;
        const enter = index === 0 ? 1 : smooth(local / 0.09);
        const leave = index === chapters.length - 1 ? 1 : smooth((1 - local) / 0.09);
        const opacity = inside ? Math.min(enter, leave) : (index === chapters.length - 1 && y > scene.end ? 1 : 0);
        copies[index].style.opacity = opacity;
        copies[index].style.pointerEvents = opacity > 0.7 ? 'auto' : 'none';
      });

      const localChapter = currentSegment.kind === 'scene'
        ? currentSegment.chapterIndex
        : currentSegment.chapterIndex + (currentSegment.target >= 0.5 ? 1 : 0);
      if (localChapter !== activeChapter) {
        activeChapter = localChapter;
        const chapter = chapters[activeChapter] || {};
        chapterStatus.textContent = `${String(activeChapter + 1).padStart(2, '0')} — ${chapter.label || chapter.title || ''}`;
        navButtons.forEach((button, index) => {
          button.classList.toggle('is-active', index === activeChapter);
          if (index === activeChapter) button.setAttribute('aria-current', 'step');
          else button.removeAttribute('aria-current');
        });
      }

      const maximum = Math.max(1, totalUnits * viewportHeight);
      progressFill.style.transform = `scaleX(${clamp(y / maximum)})`;
      hint.classList.toggle('is-hidden', y > viewportHeight * 0.2);
      readQueued = false;
    }

    function scheduleRead() {
      if (readQueued) return;
      readQueued = true;
      requestAnimationFrame(read);
    }

    function animate() {
      segments.forEach((segment) => {
        if (!segment.visible || !segment.ready || !segment.video || segment.video.seeking) return;
        segment.current += (segment.target - segment.current) * 0.2;
        const targetTime = clamp(segment.current, 0, 0.999) * (segment.video.duration || 1);
        if (Math.abs(segment.video.currentTime - targetTime) > 0.01) segment.video.currentTime = targetTime;
      });
      requestAnimationFrame(animate);
    }

    function primeVideos() {
      segments.forEach((segment) => {
        if (!segment.video) return;
        const promise = segment.video.play();
        if (promise?.then) promise.then(() => segment.video.pause()).catch(() => {});
      });
    }

    function onResize() {
      if (innerWidth === viewportWidth && Math.abs(innerHeight - viewportHeight) < 80) return;
      layout();
    }

    addEventListener('scroll', scheduleRead, { passive: true });
    addEventListener('resize', onResize);
    addEventListener('touchstart', primeVideos, { once: true, passive: true });
    addEventListener('pointerdown', primeVideos, { once: true, passive: true });
    layout();
    requestAnimationFrame(animate);

    return function destroy() {
      removeEventListener('scroll', scheduleRead);
      removeEventListener('resize', onResize);
      segments.forEach((segment) => {
        if (segment.video?.src.startsWith('blob:')) URL.revokeObjectURL(segment.video.src);
      });
    };
  };
})(window);
