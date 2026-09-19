import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from PySide6.QtCore import QCoreApplication

from util.common.signal_bus import signal_bus
from util.douyin.client import DouyinClient, DouyinMedia
from util.parse.episode.tree import Attribute, EpisodeData
from util.parse.parser.douyin import DouyinParser


class DouyinParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_parse_emits_selectable_episode_tree(self):
        media = DouyinMedia(
            aweme_id="7309762524075920649",
            title="测试视频",
            author="作者",
            author_id=42,
            cover_url="https://example.com/cover.jpg",
            media_url="https://v26-web.douyinvod.com/video.mp4",
            duration=112,
            publish_time=1700000000,
            width=576,
            height=1024,
            media_headers={"Referer": "https://www.douyin.com/"},
        )
        updates = []

        def capture(title, category, root, current):
            updates.append((title, category, root, current))

        signal_bus.parse.update_parse_list.connect(capture)
        try:
            with patch.object(DouyinClient, "fetch", return_value=media):
                with EpisodeData.parsing():
                    parser = DouyinParser()
                    parser.parse("https://v.douyin.com/SsTL1BXBURQ/")

            self.assertEqual(len(updates), 1)
            title, category, wrapper, current = updates[0]
            self.assertEqual(title, "测试视频")
            self.assertEqual(category, parser.get_category_name())

            group = wrapper.child(0)
            item = group.child(0)
            self.assertTrue(group.has_attribute(Attribute.TREE_NODE_BIT))
            self.assertTrue(item.has_attribute(Attribute.VIDEO_BIT | Attribute.NORMAL_BIT))
            self.assertEqual(current, ("episode_id", item.episode_id))
            self.assertEqual(item.to_dict()["douyin_aweme_id"], media.aweme_id)
            self.assertEqual(item.to_dict()["media_url"], media.media_url)
        finally:
            signal_bus.parse.update_parse_list.disconnect(capture)


if __name__ == "__main__":
    unittest.main()
