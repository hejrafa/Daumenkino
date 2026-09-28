import json
import unittest
from unittest.mock import patch
from test_pipeline import FEED
from sync import parse_feed, enrich, backdrop_frames
from build import card


class FlipbookTests(unittest.TestCase):
    def test_only_distinct_text_free_landscape_frames(self):
        def image(path, **extra):
            return dict(file_path=path, width=1280, aspect_ratio=1.78, iso_639_1=None, **extra)
        images = [image('/cover.jpg'), image('/a.jpg'), image('/a.jpg'),
                  {**image('/text.jpg'), 'iso_639_1': 'en'},
                  {**image('/poster.jpg'), 'aspect_ratio': .67},
                  {**image('/small.jpg'), 'width': 300}, image('/bad".jpg')]
        images += [image(f'/{n}.jpg') for n in range(8)]
        frames = backdrop_frames(images, 'https://image.tmdb.org/t/p/w1280/cover.jpg')
        self.assertEqual(len(frames), 4)
        self.assertTrue(frames[0].endswith('/a.jpg'))
        self.assertTrue(frames[-1].endswith('/2.jpg'))

    def test_existing_cover_is_upgraded_and_empty_gallery_is_cached(self):
        item = {**parse_feed(FEED, 'hejrafa')[0], 'backdrop': 'https://image.tmdb.org/t/p/w1280/cover.jpg', 'imageSource': 'TMDB'}
        with patch('sync.request', return_value=json.dumps({'backdrops': []}).encode()) as request:
            enrich(item, 'test-token')
            self.assertIn('/images?', request.call_args.args[0])
            self.assertEqual(item['backdrops'], [])
            enrich(item, 'test-token')
            self.assertEqual(request.call_count, 1)

    def test_failed_gallery_keeps_cover_and_can_retry(self):
        item = {**parse_feed(FEED, 'hejrafa')[0], 'backdrop': 'https://image.tmdb.org/t/p/w1280/cover.jpg', 'imageSource': 'TMDB'}
        with patch('sync.request', side_effect=TimeoutError):
            enrich(item, 'test-token')
        self.assertTrue(item['backdrop'].endswith('/cover.jpg'))
        self.assertNotIn('backdrops', item)

    def test_render_accepts_only_tmdb_image_urls(self):
        item = parse_feed(FEED, 'hejrafa')[0]
        item['backdrops'] = ['javascript:alert(1)', 'https://evil.test/image.jpg', 'https://image.tmdb.org/t/p/w1280/a.jpg']
        output = card(item, 0)
        self.assertNotIn('javascript:', output)
        self.assertNotIn('evil.test', output)
        self.assertIn('data-flipbook="[&quot;https://image.tmdb.org/t/p/w1280/a.jpg&quot;]"', output)


if __name__ == '__main__': unittest.main()
