import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from util.douyin.client import DouyinClient


class DouyinClientTests(unittest.TestCase):
    def test_recognizes_long_and_short_douyin_hosts(self):
        self.assertTrue(DouyinClient.is_url("https://www.douyin.com/video/123456789012"))
        self.assertTrue(DouyinClient.is_url("https://v.douyin.com/abc123/"))
        self.assertTrue(DouyinClient.is_url("https://www.iesdouyin.com/share/video/123456789012"))
        self.assertFalse(DouyinClient.is_url("https://www.bilibili.com/video/BV1xx"))

    def test_extracts_aweme_id_from_path_and_query(self):
        self.assertEqual(
            DouyinClient.extract_aweme_id("https://www.douyin.com/video/123456789012?modal_id=1"),
            "123456789012",
        )
        self.assertEqual(
            DouyinClient.extract_aweme_id("https://www.douyin.com/?modal_id=123456789012"),
            "123456789012",
        )
        self.assertIsNone(DouyinClient.extract_aweme_id("https://v.douyin.com/abc123/"))

    def test_normalizes_public_no_watermark_media_url(self):
        detail = {
            "desc": "测试视频",
            "create_time": 1700000000,
            "author": {"nickname": "作者", "uid": "42"},
            "video": {
                "duration": 12345,
                "width": 1080,
                "height": 1920,
                "cover": {"url_list": ["https://example.com/cover.jpg"]},
                "download_addr": {
                    "url_list": [
                        "https://example.com/playwm/video.mp4?watermark=1&foo=bar"
                    ]
                },
            },
        }

        media = DouyinClient.normalize_detail("123456789012", detail)

        self.assertEqual(media.title, "测试视频")
        self.assertEqual(media.author_id, 42)
        self.assertEqual(media.duration, 12)
        self.assertEqual(media.media_url, "https://example.com/play/video.mp4?foo=bar")

    def test_normalize_requires_a_media_url(self):
        with self.assertRaisesRegex(RuntimeError, "可下载的视频地址"):
            DouyinClient.normalize_detail("123456789012", {"video": {}})


if __name__ == "__main__":
    unittest.main()
