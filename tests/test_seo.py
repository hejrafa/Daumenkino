import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from seo import english_page, metadata, discovery_files, site_url, review_language
from build import card, excerpt
from test_pipeline import FEED
from sync import parse_feed

class SearchTests(unittest.TestCase):
    def test_english_is_static_and_uses_working_relative_assets(self):
        source = '<html lang="de"><title data-en="Films &amp; podcast">Filme</title><link href="./styles.css"><a href="./en/" data-language="en">EN</a><p>&lt;script&gt;Review&lt;/script&gt;</p></html>'
        en = english_page(source)
        self.assertIn('lang="en"', en)
        self.assertIn('>Films &amp; podcast</title>', en)
        self.assertIn('href="../styles.css"', en)
        self.assertIn('href="./" data-language="en" aria-current="page"', en)
        self.assertIn('&lt;script&gt;Review&lt;/script&gt;', en)
    def test_review_language_and_share_preview(self):
        self.assertEqual(review_language('Das letzte Drittel zieht gut an, aber das erste ist zu lang.'), 'de')
        self.assertEqual(review_language('Quite handy to have your own Benoit Blanc in your prison.'), 'en')
        output = metadata('https://daumenkino.fm/', 'de', [], excerpt)
        self.assertIn('property="og:image" content="https://daumenkino.fm/assets/og-de.png"', output)
        self.assertIn('name="twitter:card" content="summary_large_image"', output)
    def test_language_toggle_stays_on_the_same_page(self):
        en = english_page('<a href="./impressum.html" data-language="de" data-page="impressum.html" aria-current="page">DE</a>')
        self.assertIn('href="../impressum.html"', en)
        self.assertNotIn('aria-current', en)
    def test_english_images_use_working_paths_and_alt_text(self):
        en = english_page('<img src="./assets/cover.jpg" alt="Cover von uns" data-en-alt="Our cover">')
        self.assertIn('src="../assets/cover.jpg" alt="Our cover"', en)
    def test_structured_reviews_match_visible_excerpts_and_hide_spoilers(self):
        item = parse_feed(FEED, 'hejrafa')[0]
        hidden = {**item, 'spoiler': True, 'review': 'Secret ending'}
        output = metadata('https://daumenkino.fm/', 'en', [item, hidden], excerpt)
        data = json.loads(re.search(r'<script[^>]*>(.*?)</script>', output).group(1))
        reviews = data['@graph'][-1]['mainEntity']['itemListElement']
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]['item']['reviewBody'], excerpt(item['review']))
        self.assertEqual(reviews[0]['item']['reviewRating']['ratingValue'], 3.5)
        self.assertNotIn('Secret ending', output)
        self.assertIn('href="https://daumenkino.fm/en/"', output)
    def test_json_ld_escapes_script_terminators(self):
        item = {**parse_feed(FEED, 'hejrafa')[0], 'review': '</script><script>alert(1)</script>'}
        output = metadata('https://daumenkino.fm/', 'de', [item], excerpt)
        self.assertEqual(output.count('</script>'), 1)
    def test_static_cards_have_accessible_names_and_are_not_hidden(self):
        output = card(parse_feed(FEED, 'hejrafa')[0], 20)
        self.assertIn('aria-labelledby="review-letterboxd-review-1-title"', output)
        self.assertIn('role="img" aria-label="3.5 von 5 Sternen"', output)
        self.assertNotIn(' hidden', output.split('>')[0])
        self.assertIn('datetime="2026-09-27"', output)
    def test_discovery_uses_configured_origin_and_only_real_pages(self):
        with patch.dict('os.environ', {'SITE_URL': 'https://daumenkino.fm'}):
            self.assertEqual(site_url(), 'https://daumenkino.fm/')
        with patch.dict('os.environ', {'SITE_URL': 'http://daumenkino.fm'}):
            self.assertEqual(site_url(), 'https://daumenkino.fm/')
        with tempfile.TemporaryDirectory() as path:
            discovery_files(Path(path), 'https://daumenkino.fm/')
            xml = (Path(path) / 'sitemap.xml').read_text()
            self.assertEqual(xml.count('<url>'), 2)
            self.assertNotIn('github.io', xml)
            self.assertIn('https://daumenkino.fm/sitemap.xml', (Path(path) / 'robots.txt').read_text())
