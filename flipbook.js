// A short, hard-cut flipbook: extra stills load only when a mouse enters a card.
(() => {
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const hover = matchMedia('(any-hover: hover)');
  const controllers = new Map();
  const frameDuration = 650;

  document.querySelectorAll('[data-flipbook]').forEach(card => {
    const urls = JSON.parse(card.dataset.flipbook);
    let frames = [];
    let loading;
    let timer;
    let generation = 0;
    let inside = false;

    function stop() {
      generation += 1;
      clearTimeout(timer);
      frames.forEach(frame => { frame.hidden = true; });
    }

    function preload() {
      // Failed or slow images never replace the original still with a blank frame.
      return loading ||= Promise.all(urls.map(url => new Promise(resolve => {
        const frame = new Image();
        frame.alt = '';
        frame.setAttribute('aria-hidden', 'true');
        frame.className = 'film-still flipbook-frame';
        frame.hidden = true;
        frame.decoding = 'async';
        const timeout = setTimeout(() => finish(null), 10000);
        let settled = false;
        function finish(result) {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          frame.onload = frame.onerror = null;
          resolve(result);
        }
        frame.onload = () => frame.decode().then(() => finish(frame), () => finish(null));
        frame.onerror = () => finish(null);
        frame.src = url;
      }))).then(loaded => {
        frames = loaded.filter(Boolean);
        frames.forEach(frame => card.append(frame));
        return frames;
      });
    }

    async function start(event) {
      if (event.pointerType !== 'mouse' || motion.matches || !hover.matches
          || document.hidden || card.hidden || navigator.connection?.saveData) return;
      inside = true;
      stop();
      const current = generation;
      const loaded = await preload();
      if (current !== generation || !inside || !loaded.length) return;
      let index = 0;
      function flip() {
        if (current !== generation || !inside || motion.matches || document.hidden || card.hidden) {
          stop();
          return;
        }
        frames.forEach(frame => { frame.hidden = true; });
        // One pass lasts under three seconds; leaving always restores the cover.
        if (index === frames.length) return;
        frames[index++].hidden = false;
        timer = setTimeout(flip, frameDuration);
      }
      timer = setTimeout(flip, frameDuration);
    }

    card.addEventListener('pointerenter', start);
    card.addEventListener('pointerleave', () => { inside = false; stop(); });
    card.addEventListener('pointercancel', () => { inside = false; stop(); });
    controllers.set(card, stop);
  });

  const stopAll = () => controllers.forEach(stop => stop());
  motion.addEventListener('change', stopAll);
  hover.addEventListener('change', stopAll);
  document.addEventListener('visibilitychange', stopAll);
  window.addEventListener('blur', stopAll);
  // Stop when filtering hides a card, or scrolling takes it off screen.
  const visibility = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (!entry.isIntersecting) controllers.get(entry.target)(); });
  });
  controllers.forEach((stop, card) => {
    visibility.observe(card);
    new MutationObserver(() => { if (card.hidden) stop(); })
      .observe(card, { attributes: true, attributeFilter: ['hidden'] });
  });
})();
