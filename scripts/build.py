"""Dependency-free static build for GitHub Pages (also works at a custom domain)."""
from datetime import datetime
from html import escape as esc
import json
from pathlib import Path
import re
import shutil

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
    quote = 'Diese Review enthält Spoiler.' if item['spoiler'] else excerpt(item['review'])
    image = item.get('backdrop') or item['poster']
    date = datetime.fromisoformat(item['date']).strftime('%d.%m.%Y') if item['date'] else ''
    return f'''<article class="review-card {'feature' if index == 0 else ''}" data-author="{esc(item['author'])}" {'hidden' if index > 4 else ''}>
      <img class="film-still" src="{esc(image)}" alt="" {'fetchpriority="high"' if index == 0 else 'loading="lazy"'} width="1280" height="720">
      <div class="card-shade"></div>
      <div class="card-top"><span>{'IM FOKUS' if index == 0 else 'KURZKRITIK'} <span class="small-divider">/</span> {esc(item['name'])}</span><span class="rating" aria-label="{item['rating'] or 0} von 5 Sternen">{stars(item['rating'])}</span></div>
      <blockquote class="quote {'long-quote' if len(quote)>110 else ''}" lang="en">“{esc(quote)}”</blockquote>
      <div class="card-bottom"><div><span class="film-year">{esc(item['year'])} <span>· {date}</span></span><h3>{esc(item['title'])}</h3></div><a class="review-link" href="{esc(item['url'])}" target="_blank" rel="noopener noreferrer" aria-label="{esc(item['title'])}: Review von {esc(item['name'])} auf Letterboxd"><span>Letterboxd</span> ↗</a></div>
    </article>'''

def watched(entries, username, name):
    seen, recent = set(), []
    for item in entries:
        if item['author'] != username or not item['date']: continue
        # Four most recently watched films, without duplicate rewatches in the strip.
        key = item['tmdbId'] or item['title']
        if key in seen: continue
        seen.add(key); recent.append(item)
        if len(recent) == 4: break
    posters = ''.join(f'''<a class="watched-film" href="{esc(x['url'])}" target="_blank" rel="noopener noreferrer" aria-label="{esc(x['title'])}, {esc(x['name'])}, {x['rating'] if x['rating'] is not None else 'keine Bewertung'} von 5 Sternen"><div class="poster-wrap"><img src="{esc(x['poster'])}" alt="{esc(x['title'])}" loading="lazy" width="300" height="450"></div><span class="poster-rating" aria-hidden="true">{stars(x['rating']) or '—'}</span></a>''' for x in recent)
    return f'''<section class="watchlist"><div class="watchlist-heading"><h3>{name}</h3><a href="https://letterboxd.com/{username}/" target="_blank" rel="noopener noreferrer">@{username} ↗</a></div><div class="posters">{posters}</div></section>'''

def build():
    data = json.loads((ROOT / 'data/letterboxd.json').read_text())
    entries = sorted(data['entries'], key=lambda x: (x['date'], x['published']), reverse=True)
    # The editorial overview alternates voices; each person's own feed stays chronological.
    voices = [[x for x in entries if x['author'] == u and x['review']] for u in ('hejrafa', 'annso')]
    reviews = []
    for i in range(max(map(len, voices), default=0)):
        for voice in voices:
            if i < len(voice): reviews.append(voice[i])
    html = (ROOT / 'index.html').read_text()
    html = html.replace('<!-- REVIEWS -->', '\n'.join(card(x, i) for i, x in enumerate(reviews)))
    html = html.replace('<!-- WATCHED -->', watched(entries, 'hejrafa', 'Rafael') + watched(entries, 'annso', 'Ann-Sophie'))
    html = html.replace('{{REVIEW_COUNT}}', str(len(reviews))).replace('{{YEAR}}', str(datetime.now().year))
    oldest_sync = min((x['updated'] for x in data['feeds'].values()), default=data['updated'])
    html = html.replace('{{UPDATED}}', datetime.fromisoformat(oldest_sync).strftime('%d.%m.%Y'))
    out = ROOT / 'dist'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    (out / 'index.html').write_text(html)
    for filename in ('styles.css', 'app.js'): shutil.copy(ROOT / filename, out / filename)
    shutil.copytree(ROOT / 'assets', out / 'assets')
    (out / '.nojekyll').touch()
    print(f'Built {len(reviews)} reviews and two watchlists into dist/')

if __name__ == '__main__': build()
