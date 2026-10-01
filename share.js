// Turns a review card into a 1080×1920 story image: shared on phones, downloaded on desktops.
(() => {
  const W = 1080, H = 1920, SIDE = 90;
  const ink = '#171916', paper = '#f5f3c5', yellow = '#f5f1a2';
  const display = 'Barlow, Impact, "Arial Narrow", sans-serif', body = 'DM, Arial, sans-serif';

  function loadImage(src) {
    return new Promise(resolve => {
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.onload = () => resolve(image);
      image.onerror = () => resolve(null); // No still: the card is drawn on plain ink.
      image.src = src;
    });
  }

  function spacing(ctx, value) { if ('letterSpacing' in ctx) ctx.letterSpacing = value; }

  function wrap(ctx, text, maxWidth) {
    const lines = [];
    let line = '';
    for (const word of text.split(/\s+/)) {
      const next = line ? line + ' ' + word : word;
      if (line && ctx.measureText(next).width > maxWidth) { lines.push(line); line = word; }
      else line = next;
    }
    if (line) lines.push(line);
    return lines;
  }

  function star(ctx, x, y, size) {
    // The Daumenkino asterisk, same geometry and stroke as the footer wordmark SVG.
    const s = size / 32;
    ctx.save();
    ctx.translate(x, y); ctx.scale(s, s);
    ctx.strokeStyle = paper; ctx.lineWidth = 4.5;
    ctx.beginPath();
    ctx.moveTo(16, 2); ctx.lineTo(16, 30); ctx.moveTo(2, 16); ctx.lineTo(30, 16);
    ctx.moveTo(6, 6); ctx.lineTo(26, 26); ctx.moveTo(6, 26); ctx.lineTo(26, 6);
    ctx.stroke();
    ctx.restore();
  }

  async function render(card) {
    await Promise.all([document.fonts.load(`700 100px ${display}`), document.fonts.load(`400 30px ${body}`)]);
    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = ink; ctx.fillRect(0, 0, W, H);

    // A separate URL keeps this CORS request from reusing the page's non-CORS cached copy.
    const cover = card.querySelector('.film-still');
    const still = /^https:\/\/image\.tmdb\.org\//.test(cover.src) ? await loadImage(cover.src + '?share') : null;
    if (still) {
      const scale = Math.max(W / still.naturalWidth, H / still.naturalHeight);
      const w = still.naturalWidth * scale, h = still.naturalHeight * scale;
      ctx.drawImage(still, (W - w) / 2, (H - h) / 2, w, h);
    }
    const shade = ctx.createLinearGradient(0, 0, 0, H);
    shade.addColorStop(0, 'rgba(9,15,12,.72)');
    shade.addColorStop(.4, 'rgba(8,12,9,.6)');
    shade.addColorStop(1, 'rgba(6,10,8,.92)');
    ctx.fillStyle = shade; ctx.fillRect(0, 0, W, H);

    // Same layout as the card on the site: reviewer and rating on top, quote centred,
    // film at the bottom, with the wordmark where the card's buttons sit.
    const TOP = 190, BOTTOM = 1750;
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = paper;
    ctx.font = `400 34px ${body}`; spacing(ctx, '3px');
    ctx.textAlign = 'left';
    ctx.fillText(card.querySelector('.card-top > span').textContent.trim().toUpperCase(), SIDE, TOP);
    const rating = card.querySelector('.rating').textContent.trim();
    if (rating) { ctx.font = `44px ${body}`; spacing(ctx, '4px'); ctx.textAlign = 'right'; ctx.fillText(rating, W - SIDE, TOP + 4); }

    // Footer: wordmark bottom right, sharing the title's last baseline.
    ctx.textAlign = 'left';
    ctx.font = `700 60px ${display}`; spacing(ctx, '-1.5px');
    const markWidth = ctx.measureText('DAUMENKINO').width, starSize = 24;
    const markX = W - SIDE - starSize - 6 - markWidth;
    ctx.fillText('DAUMENKINO', markX, BOTTOM);
    star(ctx, markX + markWidth + 6, BOTTOM - 46, starSize);

    ctx.font = `700 90px ${display}`; spacing(ctx, '0px');
    const title = wrap(ctx, card.querySelector('h3').textContent.trim().toUpperCase(), markX - SIDE - 40).slice(0, 3);
    const titleTop = BOTTOM - (title.length - 1) * 90;
    title.forEach((line, i) => ctx.fillText(line, SIDE, titleTop + i * 90));
    const year = card.querySelector('.film-year');
    const date = year.querySelector('span')?.textContent.replace(/\s+/g, ' ').trim() || '';
    const yearText = year.textContent.replace(/\s+/g, ' ').trim().replace(date, '').trim();
    ctx.font = `400 34px ${body}`; spacing(ctx, '3px');
    const dateY = titleTop - 96;
    ctx.fillText(yearText, SIDE, dateY);
    if (date) {
      const x = SIDE + ctx.measureText(yearText + ' ').width;
      ctx.globalAlpha = .7; spacing(ctx, '1.2px'); ctx.fillText(date, x, dateY); ctx.globalAlpha = 1;
    }

    // Quote: largest size that fits between header and footer, with hanging quotation marks.
    const quote = card.querySelector('.quote > span:not(.quote-mark)').textContent.trim().toUpperCase();
    const space = { top: TOP + 90, bottom: dateY - 34 - 90 };
    let size = 140, lines;
    for (;;) {
      ctx.font = `700 ${size}px ${display}`; spacing(ctx, `${-size * .025}px`);
      lines = wrap(ctx, quote, W - SIDE * 2 - 40);
      const fits = lines.length * size <= space.bottom - space.top && lines.every(l => ctx.measureText(l).width <= W - SIDE * 2 - 40);
      if (fits || size <= 48) break;
      size -= 4;
    }
    const lineHeight = size;
    const top = (space.top + space.bottom) / 2 - (lines.length * lineHeight) / 2 + lineHeight * .78;
    ctx.fillStyle = yellow; ctx.textAlign = 'center';
    lines.forEach((line, i) => ctx.fillText(line, W / 2, top + i * lineHeight));
    ctx.textAlign = 'right';
    ctx.fillText('“', W / 2 - ctx.measureText(lines[0]).width / 2, top);
    ctx.textAlign = 'left';
    const last = lines[lines.length - 1];
    ctx.fillText('”', W / 2 + ctx.measureText(last).width / 2, top + (lines.length - 1) * lineHeight);

    return new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  }

  async function share(button) {
    const card = button.closest('.review-card');
    button.disabled = true; button.setAttribute('aria-busy', 'true');
    try {
      const blob = await render(card);
      const slug = card.querySelector('h3').textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const file = new File([blob], `daumenkino-${slug}.png`, { type: 'image/png' });
      // Phones get the share sheet (Instagram, Photos); desktops get a download.
      if (matchMedia('(pointer: coarse)').matches && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file] });
      } else {
        const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: file.name });
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      }
    } catch (error) {
      if (error?.name !== 'AbortError') console.warn('Share image failed', error);
    } finally {
      button.disabled = false; button.removeAttribute('aria-busy');
    }
  }

  document.querySelectorAll('.share-card').forEach(button => {
    button.hidden = false; // Only offered once the script can actually make the image.
    button.addEventListener('click', () => share(button));
  });
})();
