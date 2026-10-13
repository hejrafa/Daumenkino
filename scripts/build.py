"""Dependency-free static build for GitHub Pages (also works at a custom domain)."""
from datetime import datetime
import hashlib
from html import escape as esc
import json
import os
from pathlib import Path
import re
import shutil
from seo import english_page, metadata, list_metadata, discovery_files, site_url, review_language

ROOT = Path(__file__).resolve().parents[1]

def stars(rating):
    if rating is None: return ''
    return '★' * int(rating) + ('½' if rating % 1 else '')

def excerpt(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    short = ' '.join(sentences[:2])
    if len(short) > 180: short = short[:177].rsplit(' ', 1)[0] + '…'
    return short

def anchor(item):
    return 'review-' + ''.join(c for c in item['id'] if c.isalnum() or c == '-')

def rank_badge(rank):
    year, position = rank
    return (f'<a class="rank-badge" href="./top-20.html#top-{year}" aria-label="Platz {position} in Rafaels Top 20 von {year}" '
            f'data-en-aria-label="No. {position} in Rafael’s Top 20 of {year}">#{position} · Top 20 {year}</a>')

def card(item, index, rank=None):
    quote = 'Diese Kritik enthält Spoiler.' if item['spoiler'] else excerpt(item['review'])
    image = item.get('backdrop') or item['poster']
    frames = [url for url in item.get('backdrops', [])
              if re.fullmatch(r'https://image\.tmdb\.org/t/p/w1280/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', url)][:4]
    flipbook = f' data-flipbook="{esc(json.dumps(frames))}"' if frames else ''
    date = datetime.fromisoformat(item['date']).strftime('%d.%m.%Y') if item['date'] else ''
    quote_attrs = ' data-en="This review contains spoilers." data-language-text lang="de"' if item['spoiler'] else f' lang="{review_language(item["review"])}"'
    rating_label = f"{item['rating']} von 5 Sternen" if item['rating'] is not None else 'Keine Bewertung'
    rating_en = f"{item['rating']} out of 5 stars" if item['rating'] is not None else 'Not rated'
    review_id = anchor(item)
    return f'''<article class="review-card {'feature' if index == 0 else ''}" data-author="{esc(item['author'])}"{flipbook} id="{review_id}" aria-labelledby="{review_id}-title">
      <img class="film-still" src="{esc(image)}" alt="" {'fetchpriority="high"' if index == 0 else 'loading="lazy"'} width="1280" height="720">
      <div class="card-shade"></div>
      <div class="card-top"><span>{esc(item['name'])}</span><span class="rating" role="img" aria-label="{rating_label}" data-en-aria-label="{rating_en}">{stars(item['rating'])}</span></div>
      <blockquote class="quote {'long-quote' if len(quote)>110 else ''}"><span class="quote-mark">“</span><span{quote_attrs}>{esc(quote)}</span><span class="quote-mark">”</span></blockquote>
      <div class="card-bottom"><div>{rank_badge(rank) if rank else ''}<span class="film-year">{esc(item['year'])} <span>· <time datetime="{esc(item['date'])}" data-date="{esc(item['date'])}">{date}</time></span></span><h3 id="{review_id}-title" tabindex="-1">{esc(item['title'])}</h3></div><div class="card-actions"><button class="share-card" type="button" hidden aria-label="{esc(item['title'])}: als Bild teilen" data-en-aria-label="{esc(item['title'])}: share as image"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 15V3M7 8l5-5 5 5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button><a class="review-link" href="{esc(item['url'])}" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(item['title'])}: Review von {esc(item['name'])} auf Letterboxd" data-en-aria-label="{esc(item['title'])}: review by {esc(item['name'])} on Letterboxd"><span>Letterboxd</span> <span class="link-arrow" aria-hidden="true">↗</span></a></div></div>
    </article>'''

def favorites(films, username, name):
    posters = ''
    for x in films[:4]:
        # The title shows through if a poster is missing or fails to load.
        image = f'<img src="{esc(x["poster"])}" alt="" loading="lazy" width="300" height="450">' if x['poster'] else ''
        posters += f'''<a class="watched-film" href="https://letterboxd.com/tmdb/{esc(x['tmdbId'])}/" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{esc(x['title'])} ({esc(x['year'])}), Lieblingsfilm von {esc(name)}" data-en-aria-label="{esc(x['title'])} ({esc(x['year'])}), a favorite of {esc(name)}"><div class="poster-wrap"><span class="poster-fallback" aria-hidden="true">{esc(x['title'])}</span>{image}</div></a>'''
    return f'''<section class="watchlist"><div class="watchlist-heading"><h3>{name}</h3><a href="https://letterboxd.com/{username}/" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer"><span class="text-link">@{username}</span> <span class="arrow" aria-hidden="true">↗</span></a></div><div class="posters">{posters}</div></section>'''

def top20_ranks(lists):
    """tmdbId → (year, rank), preferring the most recent list a film appears on."""
    ranks = {}
    for x in lists:
        for film in x['films']:
            if film['tmdbId']: ranks.setdefault(film['tmdbId'], (x['year'], film['rank']))
    return ranks

def top20_film(film, review='', wide=True):
    """One ranked film: #1 as a wide still card, the rest as posters with their rank."""
    title, year = esc(film['title']), esc(film['year'])
    link = f'https://letterboxd.com/film/{esc(film["slug"])}/'
    letterboxd = f'target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="{title} ({year}) auf Letterboxd" data-en-aria-label="{title} ({year}) on Letterboxd"'
    rank = f'<span class="top20-rank"><span class="sr-only" data-en="No. ">Platz </span>{film["rank"]}</span>'
    rating = ''
    if film['rating'] is not None:
        rating = f' · <span class="rating" role="img" aria-label="{film["rating"]} von 5 Sternen" data-en-aria-label="{film["rating"]} out of 5 stars">{stars(film["rating"])}</span>'
    details = f'<span class="film-year">{year}{rating}</span>'
    # TMDB posters (added by the sync) can be drawn into the list's share image; Letterboxd's cannot.
    tmdb = film.get('tmdbPoster', '')
    tmdb = tmdb if re.fullmatch(r'https://image\.tmdb\.org/t/p/w500/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', tmdb) else ''
    data = f' data-rank="{film["rank"]}"' + (f' data-poster="{tmdb}"' if tmdb else '')
    if film['rank'] == 1 and wide:
        image = film.get('backdrop') or tmdb or film['poster']
        still = f'<img class="film-still" src="{esc(image)}" alt="" loading="lazy" width="1200" height="675">' if image else ''
        review_link = ''
        if review:
            review_link = f'<a class="review-link" href="./#{esc(review)}" aria-label="{title}: Kritik von Rafael lesen" data-en-aria-label="{title}: read Rafael’s review"><span data-en="Review">Kritik</span> <span class="link-arrow" aria-hidden="true">→</span></a>'
        return (f'<li class="top20-film top20-first feature"{data}>{still}<div class="card-shade"></div>{rank}'
                f'<div class="card-bottom"><div>{details}<h3>{title}</h3></div><div class="card-actions">{review_link}'
                f'<a class="review-link" href="{link}" {letterboxd}><span>Letterboxd</span> <span class="link-arrow" aria-hidden="true">↗</span></a></div></div></li>')
    # The title shows through if a poster is missing or fails to load.
    poster = tmdb or film['poster']
    image = f'<img src="{esc(poster)}" alt="" loading="lazy" width="300" height="450">' if poster else ''
    review_link = ''
    if review:
        review_link = f' · <a class="text-link" href="./#{esc(review)}" aria-label="{title}: Kritik von Rafael" data-en-aria-label="{title}: Rafael’s review"><span data-en="Review">Kritik</span></a>'
    return (f'<li class="top20-film{" top20-runner" if film["rank"] <= 5 else ""}"{data}><a class="watched-film" href="{link}" {letterboxd}>'
            f'<div class="poster-wrap"><span class="poster-fallback" aria-hidden="true">{title}</span>{image}</div></a>'
            f'<div class="top20-meta">{rank}<div><h3>{title}</h3><p>{details}{review_link}</p></div></div></li>')

def top20_teaser(latest, first_year, current_year):
    year = latest['year']
    heading = ('Das Jahr bisher.', 'The year so far.') if year == current_year else (f'Das Beste aus {year}.', f'The best of {year}.')
    # The teaser shows the top five as equal posters; the page gives #1 its wide still.
    films = ''.join(top20_film(film, wide=False) for film in latest['films'][:5])
    return (f'<section class="top20-teaser" id="top-20" aria-labelledby="top20-teaser-title"><div class="footer-heading">'
            f'<h2 id="top20-teaser-title"><span class="eyebrow" data-en="Rafael’s Top 20 · {year}">Rafaels Top 20 · {year}</span> '
            f'<span data-en="{heading[1]}">{heading[0]}</span></h2>'
            f'<a class="top20-all" href="./top-20.html#top-{year}"><span class="text-link" data-en="All years since {first_year}">Alle Jahre seit {first_year}</span> <span class="arrow" aria-hidden="true">→</span></a></div>'
            f'<ol class="top20-list">{films}</ol></section>')

def watched_line(year, counts, current_year):
    """How many films Rafael logged that year, and how many of them came out that year."""
    if not counts: return ''
    total, new = int(counts['total']), int(counts['fromYear'])
    so_far = ('Bisher ', 'So far ') if year == current_year else ('', '')
    return (f'<p class="top20-watched"><span data-en="{so_far[1]}{total} films watched,">{so_far[0]}{total} Filme gesehen,</span> '
            f'<span data-en="{new} of them new releases.">{new} davon Neuerscheinungen.</span></p>')

def top20_year(x, reviewed, current_year, counts=None):
    year = x['year']
    films = ''.join(top20_film(film, reviewed.get(film['tmdbId'], '')) for film in x['films'])
    share = (f'<button class="top20-story top20-pill" type="button" hidden aria-label="Top 20 {year} als Bild teilen" data-en-aria-label="Share Top 20 {year} as an image">'
             '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 15V3M7 8l5-5 5 5M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
             '<span data-en="Share as image">Als Bild teilen</span></button>')
    return (f'<section class="top20-year" id="top-{year}" data-year="{year}" aria-labelledby="top-{year}-title"><div class="top20-year-heading">'
            f'<div><h2 id="top-{year}-title">{year}</h2>{watched_line(year, counts, current_year)}</div><div class="top20-year-actions">{share}<a class="top20-pill" href="{esc(x["url"])}" target="_blank" aria-describedby="new-tab-note" rel="noopener noreferrer" aria-label="Top 20 {year} auf Letterboxd" data-en-aria-label="Top 20 {year} on Letterboxd">'
            f'<span><span class="pill-extra" data-en="List on ">Liste auf </span>Letterboxd</span><span class="arrow" aria-hidden="true">↗</span></a></div></div>'
            f'<ol class="top20-list">{films}</ol></section>')

ASSETS = ('styles.css', 'app.js', 'flipbook.js', 'share.js', 'top20.js')

def versioned(html):
    # A content hash per file makes browsers fetch new CSS/JS as soon as a deploy changes them.
    for name in ASSETS:
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:8]
        html = html.replace(f'"./{name}"', f'"./{name}?v={digest}"')
    return html

def build():
    data = json.loads((ROOT / 'data/letterboxd.json').read_text())
    picks = json.loads((ROOT / 'data/favorites.json').read_text())
    top20 = ROOT / 'data/top20.json'
    lists = sorted(json.loads(top20.read_text())['lists'], key=lambda x: x['year'], reverse=True) if top20.exists() else []
    year = datetime.now().year
    entries = sorted(data['entries'], key=lambda x: (x['date'], x['published']), reverse=True)
    # The editorial overview alternates voices; each person's own feed stays chronological.
    voices = [[x for x in entries if x['author'] == u and x['review']] for u in ('hejrafa', 'annso')]
    reviews = []
    for i in range(max(map(len, voices), default=0)):
        for voice in voices:
            if i < len(voice): reviews.append(voice[i])
    html = versioned((ROOT / 'index.html').read_text())
    ranks = top20_ranks(lists)
    # The lists are Rafael's, so only his own reviews carry a rank badge.
    html = html.replace('<!-- REVIEWS -->', '\n'.join(
        card(x, i, ranks.get(x['tmdbId']) if x['author'] == 'hejrafa' else None) for i, x in enumerate(reviews)))
    html = html.replace('<!-- TOP20 -->', top20_teaser(lists[0], lists[-1]['year'], year) if lists else '')
    html = html.replace('<!-- FAVORITES -->', ''.join(
        favorites(picks.get(u, []), u, name) for u, name in (('hejrafa', 'Rafael'), ('annso', 'Ann-Sophie'))))
    html = html.replace('{{REVIEW_COUNT}}', str(len(reviews))).replace('{{YEAR}}', str(year))
    out = ROOT / 'dist'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    base = site_url()
    en = english_page(html)
    (out / 'index.html').write_text(html.replace('<!-- SEARCH_METADATA -->', metadata(base, 'de', reviews, excerpt)))
    (out / 'en').mkdir()
    (out / 'en/index.html').write_text(en.replace('<!-- SEARCH_METADATA -->', metadata(base, 'en', reviews, excerpt)))
    pages = ['', 'en/']
    if lists:
        reviewed = {}
        for x in reviews:
            if x['author'] == 'hejrafa' and x['tmdbId']: reviewed.setdefault(x['tmdbId'], anchor(x))
        page = versioned((ROOT / 'top20.html').read_text())
        page = page.replace('<!-- TOP20_NAV -->', ''.join(f'<a href="#top-{x["year"]}">{x["year"]}</a>' for x in lists))
        # Watch counts come from Rafael's Letterboxd year in review, which blocks scripts; edited by hand.
        watched = json.loads((ROOT / 'data/watched.json').read_text()) if (ROOT / 'data/watched.json').exists() else {}
        page = page.replace('<!-- TOP20_LISTS -->', ''.join(top20_year(x, reviewed, year, watched.get(str(x['year']))) for x in lists))
        page = (page.replace('{{LIST_COUNT}}', str(len(lists))).replace('{{FILM_COUNT}}', str(sum(len(x['films']) for x in lists)))
                .replace('{{FIRST_YEAR}}', str(lists[-1]['year'])).replace('{{YEAR}}', str(year)))
        (out / 'top-20.html').write_text(page.replace('<!-- SEARCH_METADATA -->', list_metadata(base, 'de', lists)))
        (out / 'en/top-20.html').write_text(english_page(page).replace('<!-- SEARCH_METADATA -->', list_metadata(base, 'en', lists)))
        pages += ['top-20.html', 'en/top-20.html']
    discovery_files(out, base, pages)
    legal = versioned((ROOT / 'legal.html').read_text()).replace('{{YEAR}}', str(year))
    # Never publish the legal page with placeholder details.
    if 'TODO' in legal and not os.environ.get('ALLOW_DRAFT_LEGAL'):
        raise SystemExit('legal.html still contains TODO placeholders; fill in the Impressum details.')
    (out / 'impressum.html').write_text(legal)
    (out / 'en/impressum.html').write_text(english_page(legal))
    for filename in ASSETS: shutil.copy(ROOT / filename, out / filename)
    shutil.copytree(ROOT / 'assets', out / 'assets')
    (out / '.nojekyll').touch()
    print(f'Built {len(reviews)} reviews, favorite films and {len(lists)} Top 20 lists into dist/')

if __name__ == '__main__': build()
