"""Static language rendering and discoverable, factual search metadata."""
from html import escape
from html.parser import HTMLParser
import json
import os
import re
from urllib.parse import urlsplit

DEFAULT_URL = 'https://hejrafa.github.io/Daumenkino/'


def site_url():
    url = os.environ.get('SITE_URL', DEFAULT_URL).rstrip('/') + '/'
    # Pages can report HTTP while its new-domain certificate is provisioning.
    # Publish the eventual secure canonical address, never an HTTP duplicate.
    if url.startswith('http://'): url = 'https://' + url[len('http://'):]
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('SITE_URL must be an absolute HTTPS URL without query or fragment')
    return url


class EnglishPage(HTMLParser):
    """Translate only explicit text/attribute annotations; preserve escaped user content."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.replace_text = False
    def handle_decl(self, decl): self.output.append(f'<!{decl}>')
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        translated = attrs.get('data-en')
        if tag == 'html' or 'data-language-text' in attrs: attrs['lang'] = 'en'
        for field in ('aria-label', 'content', 'alt'):
            if 'data-en-' + field in attrs: attrs[field] = attrs['data-en-' + field]
        if 'data-language' in attrs:
            if attrs['data-language'] == 'en': attrs['aria-current'] = 'page'
            else: attrs.pop('aria-current', None)
        if tag in ('link', 'script', 'img'):
            for key in ('href', 'src'):
                if attrs.get(key, '').startswith('./'): attrs[key] = '../' + attrs[key][2:]
        if 'data-language' in attrs:
            # data-page keeps the toggle on the same page (e.g. the legal page) in the other language.
            attrs['href'] = ('../' if attrs['data-language'] == 'de' else './') + attrs.get('data-page', '')
        attributes = ''.join(' ' + k + (f'="{escape(v, quote=True)}"' if v is not None else '') for k, v in attrs.items())
        self.output.append(f'<{tag}{attributes}>')
        self.replace_text = translated is not None
        if translated is not None: self.output.append(escape(translated))
    def handle_endtag(self, tag):
        self.output.append(f'</{tag}>'); self.replace_text = False
    def handle_data(self, data):
        if not self.replace_text: self.output.append(data)
    def handle_entityref(self, name):
        if not self.replace_text: self.output.append(f'&{name};')
    def handle_charref(self, name):
        if not self.replace_text: self.output.append(f'&#{name};')
    def handle_comment(self, data): self.output.append(f'<!--{data}-->')


def english_page(html):
    parser = EnglishPage(); parser.feed(html)
    return ''.join(parser.output)


GERMAN = set('der die das und ist nicht ich ein eine mit auf aber auch sich es zu den dem von wie noch nur war hat sehr'.split())
ENGLISH = set('the and is not it a an with on but also of to was has very this that for my just'.split())

def review_language(text):
    """Reviews are usually English; a clear majority of German function words marks German."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    return 'de' if sum(w in GERMAN for w in words) > sum(w in ENGLISH for w in words) else 'en'


def metadata(base, language, reviews, excerpt):
    url = base + ('en/' if language == 'en' else '')
    authors = [{ '@type': 'Person', '@id': base + '#' + handle, 'name': name,
                 'sameAs': ['https://letterboxd.com/' + handle + '/']} for handle, name in
               [('hejrafa', 'Rafael Polutta'), ('annso', 'Ann-Sophie')]]
    graph = [
        {'@type': 'WebSite', '@id': base + '#website', 'url': base, 'name': 'Daumenkino',
         'inLanguage': ['de', 'en'], 'sameAs': ['https://www.instagram.com/daumenkino.fm/']},
        *authors,
        {'@type': 'PodcastSeries', '@id': base + '#podcast-series', 'name': 'Daumenkino',
         'url': 'https://podcasts.apple.com/de/podcast/daumenkino/id1476457786',
         'sameAs': ['https://open.spotify.com/show/0Wz3TC6p48i7DgnRLxKlNR'],
         'datePublished': '2019-07-24',
         'inLanguage': 'de', 'author': [{'@id': a['@id']} for a in authors],
         'description': 'Ein Filmpodcast von Ann-Sophie und Rafael.',
         'image': base + 'assets/podcast-cover.jpg', 'webFeed': 'https://anchor.fm/s/cbef5f8/podcast/rss'},
        {'@type': 'CollectionPage', '@id': url + '#page', 'url': url, 'name': 'Daumenkino',
         'inLanguage': language, 'isPartOf': {'@id': base + '#website'},
         'about': {'@id': base + '#podcast-series'},
         'mainEntity': {'@type': 'ItemList', 'itemListElement': []}},
    ]
    item_list = graph[-1]['mainEntity']['itemListElement']
    for item in reviews:
        if item['spoiler']: continue  # Never leak a spoiler through structured data.
        fragment = 'review-' + ''.join(c for c in item['id'] if c.isalnum() or c == '-')
        review = {'@type': 'Review', '@id': url + '#' + fragment, 'url': url + '#' + fragment,
                  'author': {'@id': base + '#' + item['author']},
                  'reviewBody': excerpt(item['review']), 'inLanguage': review_language(item['review']),
                  'isBasedOn': item['url'],
                  'itemReviewed': {'@type': 'Movie', 'name': item['title']}}
        if item['tmdbId']:
            review['itemReviewed']['sameAs'] = 'https://www.themoviedb.org/movie/' + item['tmdbId']
        if item['poster']: review['itemReviewed']['image'] = item['poster']
        if item['published']: review['datePublished'] = item['published']
        if item['rating'] is not None:
            review['reviewRating'] = {'@type': 'Rating', 'ratingValue': item['rating'], 'bestRating': 5, 'worstRating': 0.5}
        item_list.append({'@type': 'ListItem', 'position': len(item_list)+1, 'item': review})
    payload = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('<', '\\u003c')
    return f'''<link rel="canonical" href="{escape(url)}">
  <link rel="alternate" hreflang="de" href="{escape(base)}">
  <link rel="alternate" hreflang="en" href="{escape(base)}en/">
  <link rel="alternate" hreflang="x-default" href="{escape(base)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <meta property="og:url" content="{escape(url)}">
  <meta property="og:site_name" content="Daumenkino">
  <meta property="og:locale" content="{'en_GB' if language == 'en' else 'de_DE'}">
  <meta property="og:locale:alternate" content="{'de_DE' if language == 'en' else 'en_GB'}">
  <meta property="og:image" content="{escape(base)}assets/og-{language}.png">
  <meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{'Daumenkino* — Big films. Short takes.' if language == 'en' else 'Daumenkino* — Große Filme. Kurze Meinung.'}">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{payload}</script>'''


def discovery_files(out, base):
    (out / 'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: ' + base + 'sitemap.xml\n')
    # Only real, canonical pages; feed sync time is not a reliable content modification date.
    (out / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + ''.join('<url><loc>' + escape(base + path) + '</loc></url>' for path in ('', 'en/'))
        + '</urlset>\n')
