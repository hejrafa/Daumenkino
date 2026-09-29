"""Dependency-free static build for GitHub Pages (also works at a custom domain)."""
from datetime import datetime
import hashlib
from html import escape as esc
import json
import os
from pathlib import Path
import re
import shutil
from seo import english_page, metadata, discovery_files, site_url, review_language

ROOT = Path(__file__).resolve().parents[1]

def stars(rating):
    if rating is None: return ''
    return '★' * int(rating) + ('½' if rating % 1 else '')

def excerpt(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    short = ' '.join(sentences[:2])
    if len(short) > 180: short = short[:177].rsplit(' ', 1)[0] + '…'
    return short

def card(item, index):
    quote = 'Diese Kritik enthält Spoiler.' if item['spoiler'] else excerpt(item['review'])
    image = item.get('backdrop') or item['poster']
    frames = [url for url in item.get('backdrops', [])
              if re.fullmatch(r'https://image\.tmdb\.org/t/p/w1280/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', url)][:4]
    flipbook = f' data-flipbook="{esc(json.dumps(frames))}"' if frames else ''
    date = datetime.fromisoformat(item['date']).strftime('%d.%m.%Y') if item['date'] else ''
    quote_attrs = ' data-en="This review contains spoilers." data-language-text lang="de"' if item['spoiler'] else f' lang="{review_language(item["review"])}"'
    rating_label = f"{item['rating']} von 5 Sternen" if item['rating'] is not None else 'Keine Bewertung'
    rating_en = f"{item['rating']} out of 5 stars" if item['rating'] is not None else 'Not rated'
    review_id = 'review-' + ''.join(c for c in item['id'] if c.isalnum() or c == '-')
    return f'''<article class="review-card {'feature' if index == 0 else ''}" data-author="{esc(item['author'])}"{flipbook} id="{review_id}" aria-labelledby="{review_id}-title">
      <img class="film-still" src="{esc(image)}" alt="" {'fetchpriority="high"' if index == 0 else 'loading="lazy"'} width="1280" height="720">
      <div class="card-shade"></div>
      <div class="card-top"><span>{esc(item['name'])}</span><span class="rating" role="img" aria-label="{rating_label}" data-en-aria-label="{rating_en}">{stars(item['rating'])}</span></div>
      <blockquote class="quote {'long-quote' if len(quote)>110 else ''}"><span class="quote-mark">“</span><span{quote_attrs}>{esc(quote)}</span><span class="quote-mark">”</span></blockquote>
      <div class="card-bottom"><div><span class="film-year">{esc(item['year'])} <span>· <time datetime="{esc(item['date'])}" data-date="{esc(item['date'])}">{date}</time></span></span><h3 id="{review_id}-title" tabindex="-1">{esc(item['title'])}</h3></div><div class="card-actions"><button class="share-card" type="button" hidden aria-label="{esc(item['title'])}: als Bild teilen" data-en-aria-label="{esc(item['title'])}: share as image"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 15V3M7 8l5-5 5 5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button><a class="review-link" href="{esc(item['url'])}" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(item['title'])}: Review von {esc(item['name'])} auf Letterboxd" data-en-aria-label="{esc(item['title'])}: review by {esc(item['name'])} on Letterboxd"><span>Letterboxd</span> <span class="link-arrow" aria-hidden="true">↗</span></a></div></div>
    </article>'''

def favorites(films, username, name):
    posters = ''
    for x in films[:4]:
        # The title shows through if a poster is missing or fails to load.
        image = f'<img src="{esc(x["poster"])}" alt="" loading="lazy" width="300" height="450">' if x['poster'] else ''
        posters += f'''<a class="watched-film" href="https://letterboxd.com/tmdb/{esc(x['tmdbId'])}/" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(x['title'])} ({esc(x['year'])}), Lieblingsfilm von {esc(name)}" data-en-aria-label="{esc(x['title'])} ({esc(x['year'])}), a favorite of {esc(name)}"><div class="poster-wrap"><span class="poster-fallback" aria-hidden="true">{esc(x['title'])}</span>{image}</div></a>'''
    return f'''<section class="watchlist"><div class="watchlist-heading"><h3>{name}</h3><a href="https://letterboxd.com/{username}/" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer"><span class="text-link">@{username}</span> <span class="arrow" aria-hidden="true">↗</span></a></div><div class="posters">{posters}</div></section>'''

ASSETS = ('styles.css', 'app.js', 'flipbook.js', 'share.js')

def versioned(html):
    # A content hash per file makes browsers fetch new CSS/JS as soon as a deploy changes them.
    for name in ASSETS:
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:8]
        html = html.replace(f'"./{name}"', f'"./{name}?v={digest}"')
    return html

def build():
    data = json.loads((ROOT / 'data/letterboxd.json').read_text())
    picks = json.loads((ROOT / 'data/favorites.json').read_text())
    entries = sorted(data['entries'], key=lambda x: (x['date'], x['published']), reverse=True)
    # The editorial overview alternates voices; each person's own feed stays chronological.
    voices = [[x for x in entries if x['author'] == u and x['review']] for u in ('hejrafa', 'annso')]
    reviews = []
    for i in range(max(map(len, voices), default=0)):
        for voice in voices:
            if i < len(voice): reviews.append(voice[i])
    html = versioned((ROOT / 'index.html').read_text())
    html = html.replace('<!-- REVIEWS -->', '\n'.join(card(x, i) for i, x in enumerate(reviews)))
    html = html.replace('<!-- FAVORITES -->', ''.join(
        favorites(picks.get(u, []), u, name) for u, name in (('hejrafa', 'Rafael'), ('annso', 'Ann-Sophie'))))
    html = html.replace('{{REVIEW_COUNT}}', str(len(reviews))).replace('{{YEAR}}', str(datetime.now().year))
    out = ROOT / 'dist'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    base = site_url()
    en = english_page(html)
    (out / 'index.html').write_text(html.replace('<!-- SEARCH_METADATA -->', metadata(base, 'de', reviews, excerpt)))
    (out / 'en').mkdir()
    (out / 'en/index.html').write_text(en.replace('<!-- SEARCH_METADATA -->', metadata(base, 'en', reviews, excerpt)))
    discovery_files(out, base)
    legal = versioned((ROOT / 'legal.html').read_text()).replace('{{YEAR}}', str(datetime.now().year))
    # Never publish the legal page with placeholder details.
    if 'TODO' in legal and not os.environ.get('ALLOW_DRAFT_LEGAL'):
        raise SystemExit('legal.html still contains TODO placeholders; fill in the Impressum details.')
    (out / 'impressum.html').write_text(legal)
    (out / 'en/impressum.html').write_text(english_page(legal))
    for filename in ASSETS: shutil.copy(ROOT / filename, out / filename)
    shutil.copytree(ROOT / 'assets', out / 'assets')
    (out / '.nojekyll').touch()
    print(f'Built {len(reviews)} reviews and favorite films into dist/')

if __name__ == '__main__': build()
