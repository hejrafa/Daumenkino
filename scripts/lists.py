"""Import Rafael's yearly Top 20 lists from Letterboxd into data/top20.json.

Run locally, not in Actions: Letterboxd tends to block automated requests from CI.
Past years never change, so this only needs a re-run when the current list does:

    python3 scripts/lists.py            # every year since 2015
    python3 scripts/lists.py 2026       # only the listed years
"""
import concurrent.futures
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
import sys
import urllib.error
from sync import request, safe_url

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/top20.json'
USER = 'hejrafa'
FIRST_YEAR = 2015

def list_url(year):
    return f'https://letterboxd.com/{USER}/list/top-20-movies-{year}/'

def parse_list(html):
    """Entries in list order: slug, title, release year and Rafael's rating.

    Only the list's own entries carry data-list-index; the page also shows other lists' posters.
    Older lists are not marked as ranked on Letterboxd, but their order is the ranking.
    """
    films = []
    for item in re.finditer(r'<li class="posteritem[^"]*"(.*?)</li>', html, re.S):
        block = item[1]
        index = re.search(r'data-list-index="(\d+)"', block)
        slug = re.search(r'data-item-slug="([a-z0-9-]+)"', block)
        name = re.search(r'data-item-name="([^"]+)"', block)
        if not index or not slug or not name: continue
        title = unescape(name[1])
        year = re.search(r'\s\((\d{4})\)$', title)
        if year: title = title[:year.start()]
        rating = re.search(r'data-owner-rating="(\d+)"', block)
        films.append({'rank': int(index[1]) + 1, 'slug': slug[1], 'title': title,
                      'year': year[1] if year else '',
                      'rating': int(rating[1]) / 2 if rating and rating[1] != '0' else None})
    return sorted(films, key=lambda x: x['rank'])

def parse_film(html):
    """TMDB id, poster and (when the film has one) a landscape backdrop from a film page."""
    tmdb = re.search(r'data-tmdb-id="(\d+)"', html)
    poster = ''
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        block = re.sub(r'/\*.*?\*/', '', block, flags=re.S).strip()
        try: poster = safe_url(json.loads(block).get('image', ''))
        except (ValueError, AttributeError): continue
        if poster: break
    image = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    # Only the 16:9 crop is a real backdrop; otherwise Letterboxd falls back to a poster or logo.
    backdrop = safe_url(unescape(image[1])) if image and '-1200-1200-675-675-crop' in image[1] else ''
    return {'tmdbId': tmdb[1] if tmdb else '', 'poster': poster, 'backdrop': backdrop}

def import_lists(years=None):
    old = json.loads(DATA.read_text()) if DATA.exists() else {'lists': []}
    saved = {x['year']: x for x in old['lists']}
    # Film details never change, so any film already fetched (in any year) is reused.
    known = {f['slug']: f for x in old['lists'] for f in x['films'] if f.get('tmdbId')}
    wanted = years or range(FIRST_YEAR, datetime.now().year + 1)
    lists = dict(saved)
    for year in wanted:
        try:
            films = parse_list(request(list_url(year)).decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                print(f'{year}: no list'); continue
            raise
        if not films: raise ValueError(f'{year}: list page had no films; Letterboxd markup may have changed.')
        lists[year] = {'year': year, 'url': list_url(year), 'films': films}
        print(f'{year}: {len(films)} films')
    missing = {f['slug'] for x in lists.values() for f in x['films'] if f['slug'] not in known}
    def fetch(slug):
        try: return slug, parse_film(request(f'https://letterboxd.com/film/{slug}/').decode())
        except Exception as exc:
            print(f'Film page unavailable for {slug}: {type(exc).__name__}')
            return slug, {'tmdbId': '', 'poster': '', 'backdrop': ''}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        details = dict(pool.map(fetch, sorted(missing)))
    for x in lists.values():
        for film in x['films']:
            source = known.get(film['slug']) or details.get(film['slug'], {})
            for key in ('tmdbId', 'poster', 'backdrop'): film[key] = source.get(key, '')
            # Added by the scheduled sync, which has the TMDB token (see sync.enrich_top20).
            if 'tmdbPoster' in source: film['tmdbPoster'] = source['tmdbPoster']
    payload = {'updated': datetime.now(timezone.utc).isoformat(),
               'lists': sorted(lists.values(), key=lambda x: x['year'], reverse=True)}
    temp = DATA.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(DATA)
    print(f'Saved {len(payload["lists"])} lists ({len(missing)} new film pages fetched)')
    return payload

if __name__ == '__main__': import_lists([int(y) for y in sys.argv[1:]] or None)
