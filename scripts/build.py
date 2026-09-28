"""Dependency-free static build for GitHub Pages (also works at a custom domain)."""
from datetime import datetime
from html import escape as esc
import json
from pathlib import Path
import re
import shutil
from seo import english_page, metadata, discovery_files, site_url

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
    quote_attrs = ' data-en="“This review contains spoilers.”" data-language-text lang="de"' if item['spoiler'] else ' lang="en"'
    rating_label = f"{item['rating']} von 5 Sternen" if item['rating'] is not None else 'Keine Bewertung'
    rating_en = f"{item['rating']} out of 5 stars" if item['rating'] is not None else 'Not rated'
    review_id = 'review-' + ''.join(c for c in item['id'] if c.isalnum() or c == '-')
    return f'''<article class="review-card {'feature' if index == 0 else ''}" data-author="{esc(item['author'])}" id="{review_id}" aria-labelledby="{review_id}-title">
      <img class="film-still" src="{esc(image)}" alt="" {'fetchpriority="high"' if index == 0 else 'loading="lazy"'} width="1280" height="720">
      <div class="card-shade"></div>
      <div class="card-top"><span><span data-en="{'IN FOCUS' if index == 0 else 'SHORT TAKE'}">{'IM FOKUS' if index == 0 else 'KURZKRITIK'}</span> <span class="small-divider">/</span> {esc(item['name'])}</span><span class="rating" role="img" aria-label="{rating_label}" data-en-aria-label="{rating_en}">{stars(item['rating'])}</span></div>
      <blockquote class="quote {'long-quote' if len(quote)>110 else ''}" {quote_attrs}>“{esc(quote)}”</blockquote>
      <div class="card-bottom"><div><span class="film-year">{esc(item['year'])} <span>· <time datetime="{esc(item['date'])}" data-date="{esc(item['date'])}">{date}</time></span></span><h3 id="{review_id}-title" tabindex="-1">{esc(item['title'])}</h3></div><a class="review-link" href="{esc(item['url'])}" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(item['title'])}: Review von {esc(item['name'])} auf Letterboxd" data-en-aria-label="{esc(item['title'])}: review by {esc(item['name'])} on Letterboxd"><span>Letterboxd</span> <span class="link-arrow" aria-hidden="true">↗</span></a></div>
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
    posters = ''.join(f'''<a class="watched-film" data-en-aria-label="{esc(x['title'])}, {esc(x['name'])}, {str(x['rating']) + ' out of 5 stars' if x['rating'] is not None else 'not rated'}" href="{esc(x['url'])}" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(x['title'])}, {esc(x['name'])}, {str(x['rating']) + ' von 5 Sternen' if x['rating'] is not None else 'keine Bewertung'}"><div class="poster-wrap"><img src="{esc(x['poster'])}" alt="{esc(x['title'])}" loading="lazy" width="300" height="450"></div><span class="poster-rating" aria-hidden="true">{stars(x['rating']) or '—'}</span></a>''' for x in recent)
    return f'''<section class="watchlist"><div class="watchlist-heading"><h3>{name}</h3><a href="https://letterboxd.com/{username}/" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer">@{username} ↗</a></div><div class="posters">{posters}</div></section>'''

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
    html = html.replace('{{UPDATED_ISO}}', datetime.fromisoformat(oldest_sync).date().isoformat())
    html = html.replace('{{UPDATED}}', datetime.fromisoformat(oldest_sync).strftime('%d.%m.%Y'))
    out = ROOT / 'dist'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    base = site_url()
    en = english_page(html)
    (out / 'index.html').write_text(html.replace('<!-- SEARCH_METADATA -->', metadata(base, 'de', reviews, excerpt)))
    (out / 'en').mkdir()
    (out / 'en/index.html').write_text(en.replace('<!-- SEARCH_METADATA -->', metadata(base, 'en', reviews, excerpt)))
    discovery_files(out, base)
    for filename in ('styles.css', 'app.js'): shutil.copy(ROOT / filename, out / filename)
    shutil.copytree(ROOT / 'assets', out / 'assets')
    (out / '.nojekyll').touch()
    print(f'Built {len(reviews)} reviews and two watchlists into dist/')

if __name__ == '__main__': build()
