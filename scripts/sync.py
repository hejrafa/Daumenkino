"""Fetch public Letterboxd RSS; optionally enrich using the authenticated TMDB API."""
import concurrent.futures
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/letterboxd.json'
NS = {'lb': 'https://letterboxd.com', 'tmdb': 'https://themoviedb.org'}
AUTHORS = {'hejrafa': 'Rafael', 'annso': 'Ann-Sophie'}

class Description(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.poster, self.skip = [], '', 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'): self.skip += 1
        if tag == 'img' and not self.poster: self.poster = safe_url(attrs.get('src', ''))
        if tag in ('p', 'br', 'blockquote'): self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.skip = max(0, self.skip - 1)
        if tag in ('p', 'blockquote'): self.parts.append(' ')
    def handle_data(self, text):
        if not self.skip: self.parts.append(text)
    @property
    def text(self): return re.sub(r'\s+', ' ', ''.join(self.parts)).strip()

def safe_url(url):
    return url if url.startswith('https://') else ''

def request(url, token=None):
    headers = {'User-Agent': 'Daumenkino/1.0 (+https://github.com/hejrafa/Daumenkino)'}
    if token: headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
        return response.read()

def parse_feed(xml, username):
    items = []
    for item in ET.fromstring(xml).findall('./channel/item'):
        title = item.findtext('lb:filmTitle', '', NS)
        if not title: continue  # Lists and other activity are not diary entries.
        description = Description()
        raw = item.findtext('description', '')
        description.feed(raw)
        guid = item.findtext('guid', '')
        text = description.text
        if re.fullmatch(r'(?:Rewatched|Watched) on .+\.', text): text = ''
        rating = item.findtext('lb:memberRating', '', NS)
        try: rating = min(5, max(0, float(rating))) if rating else None
        except ValueError: rating = None
        pub = item.findtext('pubDate', '')
        try: published = parsedate_to_datetime(pub).isoformat()
        except (ValueError, TypeError): published = ''
        spoiler = bool(re.search(r'contains? spoilers?|class=["\'][^"\']*spoiler', raw, re.I))
        items.append({'id': guid or item.findtext('link'), 'author': username,
            'name': AUTHORS[username], 'title': title, 'year': item.findtext('lb:filmYear', '', NS),
            'url': safe_url(item.findtext('link', '')), 'date': item.findtext('lb:watchedDate', '', NS),
            'published': published, 'rating': rating, 'review': text,
            'spoiler': spoiler, 'poster': description.poster,
            'tmdbId': item.findtext('tmdb:movieId', '', NS), 'backdrop': ''})
    if not items: raise ValueError(f'No film entries in {username} feed')
    return items

def enrich(item, token):
    if item.get('backdrop') and (not token or item.get('imageSource') == 'TMDB'): return item
    try:
        if token and item['tmdbId']:
            movie = json.loads(request('https://api.themoviedb.org/3/movie/' + item['tmdbId'], token))
            if movie.get('backdrop_path'):
                item['backdrop'] = 'https://image.tmdb.org/t/p/w1280' + movie['backdrop_path']
                item['imageSource'] = 'TMDB'
                return item
        # A public film-page fallback makes the draft useful before a TMDB token is supplied.
        match = re.search(r'/film/([^/]+)/', item['url'])
        if match:
            page = request('https://letterboxd.com/film/' + match[1] + '/').decode()
            backdrop = re.search(r'data-backdrop="([^"]+)"', page)
            if backdrop:
                item['backdrop'] = safe_url(backdrop[1])
                item['imageSource'] = 'Letterboxd'
    except Exception as exc:
        print(f"Image unavailable for {item['title']}: {type(exc).__name__}; keeping poster.")
    return item

def sync():
    old = json.loads(DATA.read_text()) if DATA.exists() else {'entries': [], 'feeds': {}}
    records = {x['id']: x for x in old['entries']}
    feeds = old.get('feeds', {})
    failures = []
    for username in AUTHORS:
        try:
            entries = parse_feed(request(f'https://letterboxd.com/{username}/rss/'), username)
            for item in entries:
                previous = records.get(item['id'], {})
                item['backdrop'] = previous.get('backdrop', '')
                item['imageSource'] = previous.get('imageSource', '')
                records[item['id']] = item
            feeds[username] = {'updated': datetime.now(timezone.utc).isoformat()}
            print(f'{username}: {len(entries)} entries')
        except Exception as exc:
            failures.append(username)
            print(f'Feed unavailable for {username}: {type(exc).__name__}; preserving saved entries.')
    entries = sorted(records.values(), key=lambda x: (x['date'], x['published']), reverse=True)
    if any(not any(x['author'] == u for x in entries) for u in AUTHORS):
        raise RuntimeError('Initial sync requires data for both accounts.')
    # Enrich a bounded set per author, retaining an archive as the RSS window rolls on.
    selected = []
    for username in AUTHORS:
        selected.extend([x for x in entries if x['author'] == username and x['review']][:16])
    token = os.getenv('TMDB_READ_TOKEN')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda item: enrich(item, token), selected))
    payload = {'updated': datetime.now(timezone.utc).isoformat(), 'feeds': feeds, 'entries': entries}
    DATA.parent.mkdir(exist_ok=True)
    temp = DATA.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temp.replace(DATA)
    if failures: print('WARNING: stale feeds: ' + ', '.join(failures))
    return payload

if __name__ == '__main__': sync()
