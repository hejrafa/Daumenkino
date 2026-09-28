import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync import parse_feed, Description, safe_url
from build import card, excerpt, watched

FEED = '''<rss xmlns:letterboxd="https://letterboxd.com" xmlns:tmdb="https://themoviedb.org"><channel><item><guid>letterboxd-review-1</guid><link>https://letterboxd.com/hejrafa/film/test/</link><pubDate>Mon, 28 Sep 2026 11:01:55 +1300</pubDate><letterboxd:filmTitle>A &amp; B</letterboxd:filmTitle><letterboxd:filmYear>2026</letterboxd:filmYear><letterboxd:watchedDate>2026-09-27</letterboxd:watchedDate><letterboxd:memberRating>3.5</letterboxd:memberRating><tmdb:movieId>123</tmdb:movieId><description><![CDATA[<p><img src="https://example.com/poster.jpg"></p><p>It's &amp; it works.</p><p>Second sentence!</p>]]></description></item><item><title>Not a movie list</title></item></channel></rss>'''

class PipelineTest(unittest.TestCase):
    def test_rss_namespaces_entities_and_non_film_activity(self):
        items = parse_feed(FEED, 'hejrafa')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['review'], "It's & it works. Second sentence!")
        self.assertEqual(items[0]['rating'], 3.5)
        self.assertEqual(items[0]['tmdbId'], '123')
        self.assertEqual(items[0]['poster'], 'https://example.com/poster.jpg')
    def test_watched_only_entry_is_not_a_review(self):
        xml = FEED.replace("It's &amp; it works.</p><p>Second sentence!", 'Watched on Monday September 7, 2026.')
        self.assertEqual(parse_feed(xml, 'annso')[0]['review'], '')
    def test_untrusted_review_html_is_never_rendered(self):
        item = parse_feed(FEED, 'hejrafa')[0]
        item['review'] = '<script>alert(1)</script>'
        item['title'] = '<img onerror=alert(1)>'
        output = card(item, 0)
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)
        self.assertEqual(safe_url('javascript:alert(1)'), '')
    def test_spoilers_are_not_exposed_on_card(self):
        item = parse_feed(FEED.replace("It's &amp; it works.", 'This review may contain spoilers. The ending.'), 'hejrafa')[0]
        self.assertTrue(item['spoiler'])
        self.assertNotIn('The ending', card(item, 0))
    def test_review_excerpt_is_short(self):
        self.assertEqual(excerpt('First. Second! Third?'), 'First. Second!')
        self.assertLessEqual(len(excerpt('A very long thought ' * 50)), 180)
    def test_latest_watches_include_unreviewed_and_skip_duplicates(self):
        item = parse_feed(FEED, 'hejrafa')[0]
        items = [{**item, 'tmdbId': str(i), 'title': f'Film {i}', 'review': ''} for i in range(6)]
        output = watched([items[0], *items], 'hejrafa', 'Rafael')
        self.assertEqual(output.count('class="watched-film"'), 4)
        self.assertNotIn('Film 4', output)
    def test_empty_or_invalid_feed_cannot_replace_snapshot(self):
        with self.assertRaises(ValueError): parse_feed('<rss><channel/></rss>', 'annso')
    def test_description_ignores_script_content(self):
        d = Description(); d.feed('<script>bad</script><p>Good <b>film</b>.</p>')
        self.assertEqual(d.text, 'Good film.')

if __name__ == '__main__': unittest.main()
