import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lists import parse_list, parse_film
from build import card, top20_film, top20_ranks, top20_teaser, top20_year
from seo import list_metadata
from test_pipeline import FEED
from sync import parse_feed
import sync

def entry(index, slug, name, rating='10', classes='posteritem numbered-list-item'):
    return (f'<li class="{classes}" data-owner-rating="{rating}"> <div class="react-component" data-item-name="{name}" '
            f'data-item-slug="{slug}" data-list-index="{index}"> </div> </li>')

# A list page also shows other lists' posters; those have no data-list-index.
LIST = (entry(1, 'second', 'Second &amp; Co (2019)', '7') + entry(0, 'first', 'First (2020)')
        + '<li class="posteritem"> <div data-item-name="Other (2021)" data-item-slug="other"> </div> </li>')
FILM = '''<body data-tmdb-type="movie" data-tmdb-id="42"><meta property="og:image" content="https://a.ltrbxd.com/x-1200-1200-675-675-crop-000000.jpg?v=1">
<script type="application/ld+json">/* <![CDATA[ */{"image":"https://a.ltrbxd.com/poster.jpg","@type":"Movie"}/* ]]> */</script>'''

def film(rank, **extra):
    return {'rank': rank, 'slug': f'film-{rank}', 'title': f'Film {rank}', 'year': '2026', 'rating': 4.5,
            'tmdbId': str(rank), 'poster': 'https://a.ltrbxd.com/p.jpg', 'backdrop': 'https://a.ltrbxd.com/b.jpg', **extra}

class Top20Tests(unittest.TestCase):
    def test_list_entries_in_rank_order_without_other_lists(self):
        films = parse_list(LIST)
        self.assertEqual([x['slug'] for x in films], ['first', 'second'])
        self.assertEqual(films[1], {'rank': 2, 'slug': 'second', 'title': 'Second & Co', 'year': '2019', 'rating': 3.5})
    def test_film_page_details(self):
        self.assertEqual(parse_film(FILM), {'tmdbId': '42', 'poster': 'https://a.ltrbxd.com/poster.jpg',
                                            'backdrop': 'https://a.ltrbxd.com/x-1200-1200-675-675-crop-000000.jpg?v=1'})
        # A poster-shaped og:image is not a backdrop.
        self.assertEqual(parse_film(FILM.replace('-1200-1200-675-675-crop', '-0-600-0-900-crop'))['backdrop'], '')
    def test_most_recent_list_wins_for_badges(self):
        lists = [{'year': 2026, 'films': [film(3, tmdbId='123')]}, {'year': 2025, 'films': [film(1, tmdbId='123')]}]
        self.assertEqual(top20_ranks(lists)['123'], (2026, 3))
        item = parse_feed(FEED, 'hejrafa')[0]
        output = card(item, 0, (2026, 3))
        self.assertIn('href="./top-20.html#top-2026"', output)
        self.assertIn('aria-label="Platz 3 in Rafaels Top 20 von 2026"', output)
        self.assertNotIn('rank-badge', card(item, 0))
    def test_first_place_is_wide_and_links_review(self):
        first = top20_film(film(1), 'review-x')
        self.assertIn('top20-first', first)
        self.assertIn('class="film-still" src="https://a.ltrbxd.com/b.jpg"', first)
        self.assertIn('href="./#review-x"', first)
        self.assertNotIn('top20-first', top20_film(film(1), wide=False))
        self.assertIn('top20-runner', top20_film(film(5)))
        self.assertNotIn('top20-runner', top20_film(film(6)))
        self.assertNotIn('./#', top20_film(film(6)))
    def test_titles_are_escaped_and_missing_posters_show_title(self):
        output = top20_film(film(7, title='<script>x</script>', poster=''))
        self.assertNotIn('<script>', output)
        self.assertNotIn('<img', output)
        self.assertIn('class="poster-fallback"', output)
    def test_year_and_teaser(self):
        x = {'year': 2026, 'url': 'https://letterboxd.com/hejrafa/list/top-20-movies-2026/', 'films': [film(i) for i in range(1, 21)]}
        year = top20_year(x, {'3': 'review-3'}, 2026)
        self.assertEqual(year.count('class="top20-film'), 20)
        self.assertIn('läuft noch', year)
        self.assertNotIn('läuft noch', top20_year(x, {}, 2027))
        teaser = top20_teaser(x, 2015, 2026)
        self.assertEqual(teaser.count('class="top20-film'), 5)
        self.assertIn('Alle Jahre seit 2015', teaser)
        self.assertIn('Das Beste aus 2026.', top20_teaser(x, 2015, 2027))
    def test_share_image_gets_only_tmdb_posters(self):
        output = top20_film(film(2, tmdbPoster='https://image.tmdb.org/t/p/w500/abc.jpg'))
        self.assertIn('data-rank="2" data-poster="https://image.tmdb.org/t/p/w500/abc.jpg"', output)
        self.assertIn('<img src="https://image.tmdb.org/t/p/w500/abc.jpg"', output)
        self.assertNotIn('data-poster', top20_film(film(2, tmdbPoster='https://evil.example/x.jpg')))
        x = {'year': 2026, 'url': 'https://letterboxd.com/hejrafa/list/top-20-movies-2026/', 'films': [film(1)]}
        self.assertIn('class="share-list top20-pill" type="button" hidden', top20_year(x, {}, 2026))
        self.assertIn('data-year="2026"', top20_year(x, {}, 2026))
    def test_sync_looks_up_each_tmdb_poster_once(self):
        with tempfile.TemporaryDirectory() as path:
            data = Path(path) / 'top20.json'
            data.write_text(json.dumps({'lists': [{'year': 2026, 'films': [
                film(1), film(2, tmdbPoster=''), film(3)]}]}))
            responses = {'1': {'poster_path': '/abc.jpg'}, '3': {'poster_path': None}}
            with patch.object(sync, 'TOP20', data), patch.object(sync, 'request', lambda url, token: json.dumps(responses[url.rsplit('/', 1)[1]])):
                sync.enrich_top20('token')
            films = json.loads(data.read_text())['lists'][0]['films']
            self.assertEqual([f['tmdbPoster'] for f in films], ['https://image.tmdb.org/t/p/w500/abc.jpg', '', ''])
            before = data.read_text()
            with patch.object(sync, 'TOP20', data), patch.object(sync, 'request', side_effect=AssertionError('no lookups')):
                sync.enrich_top20('token')
            self.assertEqual(data.read_text(), before)
    def test_structured_lists(self):
        lists = [{'year': 2026, 'url': 'https://letterboxd.com/hejrafa/list/top-20-movies-2026/', 'films': [film(1), film(2)]}]
        output = list_metadata('https://daumenkino.fm/', 'en', lists)
        self.assertIn('rel="canonical" href="https://daumenkino.fm/en/top-20.html"', output)
        self.assertIn('hreflang="de" href="https://daumenkino.fm/top-20.html"', output)
        data = json.loads(re.search(r'<script[^>]*>(.*?)</script>', output).group(1))
        year = data['@graph'][0]['hasPart'][0]
        self.assertEqual([x['position'] for x in year['itemListElement']], [1, 2])
        self.assertEqual(year['itemListElement'][0]['item']['sameAs'], 'https://www.themoviedb.org/movie/1')

if __name__ == '__main__': unittest.main()
