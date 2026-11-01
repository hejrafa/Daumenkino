"""Post new reviews to Instagram as 4:5 feed posts, drawn by share.js in a headless browser.

Before the site deploys, `prepare` picks the new reviews and `draw` saves their images into dist/,
so they go live with the site. `publish` then hands Meta their URLs, since Meta fetches images itself.
"""
import base64
from datetime import datetime, timedelta, timezone
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from build import anchor, excerpt, stars
from seo import site_url

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/letterboxd.json'
LEDGER = ROOT / 'data/instagram.json'
DIST = ROOT / 'dist'
API = 'https://graph.instagram.com'
VERSION = 'v26.0'
PER_RUN = 3  # If the ledger is ever lost, reviews trickle out instead of flooding the account.
CAPTION = 2000  # Instagram allows 2,200 characters; the margin covers how it counts emoji.
REFRESH_EVERY = timedelta(days=7)

def eligible(entries):
    # The reviews the site quotes. Spoilers are left out: the caption carries the whole review.
    return [x for x in entries if x['review'] and not x['spoiler']]

def load_ledger():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else None

def save_ledger(ledger):
    temp = LEDGER.with_suffix('.tmp')
    temp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n')
    temp.replace(LEDGER)

def hashtag(title):
    tag = re.sub(r'[\W_]+', '', title.lower())
    return '#' + tag if re.search(r'[^\W\d_]', tag) else ''  # Instagram ignores tags without letters.

def heading(item):
    return f"{item['name']} über {item['title']}" + (f" ({item['year']})" if item['year'] else '')

def caption(item):
    head = heading(item) + (' · ' + stars(item['rating']) if item['rating'] else '')
    tags = ' '.join(filter(None, ('#daumenkino', hashtag(item['title']))))
    tail = f"\n\nGanze Kritik auf Letterboxd: {item['url']}\nAlle Kritiken: daumenkino.fm\n\n{tags}"
    room = CAPTION - len(head) - len(tail) - 2
    review = item['review'] if len(item['review']) <= room else item['review'][:room - 1].rsplit(' ', 1)[0] + '…'
    return f'{head}\n\n{review}{tail}'

def alt_text(item):
    rating = f", {item['rating']:g} von 5 Sternen".replace('.', ',') if item['rating'] else ''
    return f"{heading(item)}{rating}: „{excerpt(item['review'])}“"

def post(item, site):
    image = f'instagram/{anchor(item)}.jpg'
    return {'id': item['id'], 'card': anchor(item), 'image': image, 'imageUrl': site + image,
            'caption': caption(item), 'altText': alt_text(item)}

def prepare(manifest):
    entries = eligible(json.loads(DATA.read_text())['entries'])
    ledger = load_ledger()
    if ledger is None:
        # The first run only remembers the reviews already there, so the back catalogue isn't posted.
        save_ledger({'posts': {x['id']: None for x in entries}})
        print(f'Instagram: remembered {len(entries)} earlier reviews; new ones get posted from now on')
        posts = []
    else:
        new = sorted((x for x in entries if x['id'] not in ledger['posts']), key=lambda x: (x['date'], x['published']))
        posts = [post(x, site_url()) for x in new[:PER_RUN]]  # Oldest first, so the grid follows the reviews.
        print(f'Instagram: {len(new)} new reviews' + (f', posting {len(posts)} this run' if len(new) > len(posts) else ''))
    manifest.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + '\n')
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output: output.write(f'count={len(posts)}\n')

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def draw(posts):
    from playwright.sync_api import sync_playwright  # Only needed when there is something to draw.
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=DIST))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (DIST / 'instagram').mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            # The installed Chrome: GitHub's runners have it, so nothing needs downloading.
            browser = p.chromium.launch(channel='chrome')
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function('() => typeof window.daumenkinoPost === "function"')
            for x in posts:
                image = page.evaluate('id => window.daumenkinoPost(id)', x['card'])
                (DIST / x['image']).write_bytes(base64.b64decode(image.split(',', 1)[1]))
                print(f"Drew dist/{x['image']}")
            browser.close()
    finally:
        server.shutdown()

def request(method, path, token, **params):
    query = urllib.parse.urlencode({**params, 'access_token': token})
    url = API + path + ('?' + query if method == 'GET' else '')
    body = query.encode() if method == 'POST' else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, method=method), timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Only Meta's message: the request URL would include the token.
        message = json.loads(exc.read() or b'{}').get('error', {}).get('message', '')
        raise RuntimeError(f'Instagram API {exc.code}: {message}') from None

def refresh(token, ledger):
    """Long-lived tokens expire after 60 days unless renewed, so renew weekly and save the new one."""
    last = ledger.get('tokenRefreshed')
    if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < REFRESH_EVERY: return token
    try:
        new = request('GET', '/refresh_access_token', token, grant_type='ig_refresh_token')['access_token']
    except RuntimeError as exc:
        # Tokens can only be renewed once they are a day old; the next run tries again.
        print(f'::warning::Instagram token not renewed: {exc}')
        return token
    if new != token:
        saved = bool(os.getenv('GH_TOKEN')) and subprocess.run(
            ['gh', 'secret', 'set', 'INSTAGRAM_TOKEN', '--repo', os.environ['GITHUB_REPOSITORY']], input=new.encode()).returncode == 0
        if not saved:
            # Not recorded as renewed, so the next run tries again.
            print('::warning::Instagram issued a new token that could not be saved. Check the SECRETS_TOKEN secret, '
                  'or replace INSTAGRAM_TOKEN by hand before the old one expires.')
            return new
    ledger['tokenRefreshed'] = datetime.now(timezone.utc).isoformat()
    return new

def wait_until_live(url, attempts=20):
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=20): return
        except (urllib.error.URLError, TimeoutError): time.sleep(6)
    raise RuntimeError(f'{url} is not online')

def publish_one(x, user, token):
    container = request('POST', f'/{VERSION}/{user}/media', token,
                        image_url=x['imageUrl'], caption=x['caption'], alt_text=x['altText'])['id']
    for _ in range(20):
        status = request('GET', f'/{VERSION}/{container}', token, fields='status_code')['status_code']
        if status == 'FINISHED': break
        if status in ('ERROR', 'EXPIRED'): raise RuntimeError(f"Instagram could not process {x['image']}: {status}")
        time.sleep(3)
    else:
        raise RuntimeError(f"Instagram is still processing {x['image']}")
    return request('POST', f'/{VERSION}/{user}/media_publish', token, creation_id=container)['id']

def publish(manifest):
    ledger = load_ledger() or {'posts': {}}
    token = refresh(os.environ['INSTAGRAM_TOKEN'], ledger)
    save_ledger(ledger)
    # A newer run may already have posted some of these.
    posts = [x for x in json.loads(manifest.read_text()) if x['id'] not in ledger['posts']]
    if not posts: return
    me = request('GET', f'/{VERSION}/me', token, fields='user_id,username')
    for x in posts:
        wait_until_live(x['imageUrl'])  # Meta fetches the image from the deployed site.
        ledger['posts'][x['id']] = publish_one(x, me.get('user_id') or me['id'], token)
        save_ledger(ledger)  # Saved after every post, so a later failure can't post it twice.
        print(f"Posted {x['image']} to @{me.get('username', '')}")

def preview(count=3):
    """Draw the latest reviews into dist/instagram/ to check the layout. Run build.py first."""
    entries = sorted(eligible(json.loads(DATA.read_text())['entries']), key=lambda x: (x['date'], x['published']))
    posts = [post(x, 'http://localhost/') for x in entries[-count:]]
    draw(posts)
    for x in posts: print(f"\n{x['image']}\n{x['caption']}\nAlt: {x['altText']}")

if __name__ == '__main__':
    command, *args = sys.argv[1:] or ['preview']
    if command in ('prepare', 'draw', 'publish') and len(args) == 1:
        manifest = Path(args[0])
        if command == 'prepare': prepare(manifest)
        elif command == 'draw': draw(json.loads(manifest.read_text()))
        else: publish(manifest)
    elif command == 'preview': preview()
    else: raise SystemExit('Usage: instagram.py prepare|draw|publish MANIFEST, or instagram.py preview')
