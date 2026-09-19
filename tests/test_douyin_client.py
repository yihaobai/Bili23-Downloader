import sys
import unittest
from pathlib import Path
import runpy


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from util.douyin.client import DouyinClient

url_patterns = runpy.run_path(
    str(Path(__file__).parents[1] / "src" / "util" / "common" / "data" / "url_pattern.py")
)["url_patterns"]


class DouyinClientTests(unittest.TestCase):
    def test_url_pattern_routes_douyin_before_bilibili_patterns(self):
        parser_type = next(
            parser_type
            for parser_type, pattern in url_patterns
            if pattern.search("https://www.douyin.com/video/123456789012")
        )

        self.assertEqual(parser_type, "douyin")

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

    def test_prefers_play_addr_over_download_addr(self):
        detail = {
            "desc": "浏览器播放地址",
            "aweme_id": "123456789012",
            "video": {
                "play_addr": {
                    "url_list": ["https://example.com/play/video-without-watermark.mp4"]
                },
                "download_addr": {
                    "url_list": ["https://example.com/playwm/video-with-watermark.mp4"]
                },
            },
        }

        media = DouyinClient.normalize_captured_detail(
            "123456789012",
            [{"data": {"aweme_detail": detail}}],
            page_url="https://www.douyin.com/video/123456789012",
        )

        self.assertEqual(media.media_url, "https://example.com/play/video-without-watermark.mp4")
        self.assertEqual(media.media_headers["Referer"], "https://www.douyin.com/video/123456789012")

    def test_normalizes_nested_browser_response_body(self):
        body = {
            "payload": {
                "data": {
                    "aweme_detail": {
                        "aweme_id": "123456789012",
                        "desc": "嵌套响应",
                        "video": {
                            "play_addr": {
                                "url_list": ["https://example.com/play/nested.mp4"]
                            }
                        },
                    }
                }
            }
        }

        media = DouyinClient.normalize_captured_detail(
            "123456789012",
            [{"body": __import__("json").dumps(body)}],
        )

        self.assertEqual(media.title, "嵌套响应")
        self.assertEqual(media.media_url, "https://example.com/play/nested.mp4")

    def test_normalize_requires_a_media_url(self):
        with self.assertRaisesRegex(RuntimeError, "可下载的视频地址"):
            DouyinClient.normalize_detail("123456789012", {"video": {}})


if __name__ == "__main__":
    unittest.main()
