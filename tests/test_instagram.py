from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import instagram
from instagram import alt_text, caption, eligible, hashtag, prepare, publish, refresh

def review(n, **extra):
    return {'id': f'letterboxd-review-{n}', 'author': 'hejrafa', 'name': 'Rafael', 'title': f'Film {n}', 'year': '2026',
            'url': f'https://letterboxd.com/hejrafa/film/film-{n}/', 'date': f'2026-10-{n:02d}', 'published': '',
            'rating': 4.5, 'review': f'Review {n}. Second sentence.', 'spoiler': False, **extra}

class InstagramTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.data, self.ledger, self.manifest = self.dir / 'letterboxd.json', self.dir / 'instagram.json', self.dir / 'posts.json'
        for name, path in (('DATA', self.data), ('LEDGER', self.ledger)):
            patcher = patch.object(instagram, name, path); patcher.start(); self.addCleanup(patcher.stop)
        env = patch.dict(os.environ, {'SITE_URL': 'https://daumenkino.fm', 'GITHUB_OUTPUT': '', 'GH_TOKEN': ''})
        env.start(); self.addCleanup(env.stop)

    def write(self, entries):
        self.data.write_text(json.dumps({'entries': entries}))

    def test_only_quoted_reviews_are_posted(self):
        entries = [review(1), review(2, review=''), review(3, spoiler=True)]
        self.assertEqual([x['id'] for x in eligible(entries)], ['letterboxd-review-1'])

    def test_first_run_remembers_existing_reviews_without_posting(self):
        self.write([review(1), review(2)])
        prepare(self.manifest)
        self.assertEqual(json.loads(self.manifest.read_text()), [])
        self.assertEqual(json.loads(self.ledger.read_text()), {'posts': {'letterboxd-review-1': None, 'letterboxd-review-2': None}})

    def test_new_reviews_are_posted_oldest_first_a_few_per_run(self):
        self.write([review(1)]); prepare(self.manifest)
        self.write([review(n) for n in (6, 2, 5, 1, 4, 3)]); prepare(self.manifest)
        posts = json.loads(self.manifest.read_text())
        self.assertEqual([x['id'] for x in posts], [f'letterboxd-review-{n}' for n in (2, 3, 4)])
        self.assertEqual(posts[0]['imageUrl'], 'https://daumenkino.fm/instagram/review-letterboxd-review-2.jpg')
        self.assertEqual(posts[0]['card'], 'review-letterboxd-review-2')

    def test_caption_has_review_link_and_tags(self):
        text = caption(review(1, title='Spider-Man: Brand New Day'))
        self.assertTrue(text.startswith('Rafael über Spider-Man: Brand New Day (2026) · ★★★★½\n\nReview 1. Second sentence.'))
        self.assertIn('https://letterboxd.com/hejrafa/film/film-1/', text)
        self.assertTrue(text.endswith('#daumenkino #spidermanbrandnewday'))
        self.assertNotIn('·', caption(review(1, rating=None)))
        self.assertEqual(hashtag('1917'), '')

    def test_long_reviews_are_shortened_to_fit(self):
        text = caption(review(1, review='Word ' * 1000))
        self.assertLessEqual(len(text), instagram.CAPTION)
        self.assertIn('Word…', text)

    def test_alt_text_reads_the_image(self):
        self.assertEqual(alt_text(review(1)), 'Rafael über Film 1 (2026), 4,5 von 5 Sternen: „Review 1. Second sentence.“')

    def test_publish_records_each_post_and_skips_posted_ones(self):
        recent = datetime.now(timezone.utc).isoformat()
        self.ledger.write_text(json.dumps({'tokenRefreshed': recent, 'posts': {'letterboxd-review-1': '17'}}))
        self.manifest.write_text(json.dumps([instagram.post(review(n), 'https://daumenkino.fm/') for n in (1, 2)]))
        calls = []
        def api(method, path, token, **params):
            calls.append((method, path, params))
            if path.endswith('/me'): return {'user_id': '99', 'username': 'daumenkino.fm'}
            if path.endswith('/99/media'): return {'id': 'c2'}
            if path.endswith('/c2'): return {'status_code': 'FINISHED'}
            if path.endswith('/media_publish'): return {'id': 'm2'}
        with patch.object(instagram, 'request', api), patch.object(instagram, 'wait_until_live'), \
             patch.dict(os.environ, {'INSTAGRAM_TOKEN': 't'}):
            publish(self.manifest)
        self.assertEqual(json.loads(self.ledger.read_text())['posts'], {'letterboxd-review-1': '17', 'letterboxd-review-2': 'm2'})
        media = next(params for method, path, params in calls if path.endswith('/99/media'))
        self.assertEqual(media['image_url'], 'https://daumenkino.fm/instagram/review-letterboxd-review-2.jpg')
        self.assertIn('Rafael über Film 2', media['caption'])
        self.assertFalse(any(path == '/refresh_access_token' for _, path, _ in calls))

    def test_token_is_renewed_weekly(self):
        week_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        ledger = {'tokenRefreshed': week_ago, 'posts': {}}
        with patch.object(instagram, 'request', return_value={'access_token': 't'}) as api:
            self.assertEqual(refresh('t', ledger), 't')
        api.assert_called_once()
        self.assertGreater(ledger['tokenRefreshed'], week_ago)
        with patch.object(instagram, 'request') as api:
            refresh('t', ledger)
        api.assert_not_called()

    def test_failed_or_unsaved_renewal_is_retried_next_run(self):
        ledger = {'posts': {}}
        with patch.object(instagram, 'request', side_effect=RuntimeError('too young')):
            self.assertEqual(refresh('t', ledger), 't')
        with patch.object(instagram, 'request', return_value={'access_token': 'new'}):
            self.assertEqual(refresh('t', ledger), 'new')  # No SECRETS_TOKEN to save it with.
        self.assertNotIn('tokenRefreshed', ledger)

if __name__ == '__main__': unittest.main()
