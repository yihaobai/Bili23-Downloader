from ...common.enum import ParserType
from ...douyin.client import DouyinClient

from ..episode.tree import Attribute, EpisodeData, TreeItem
from .base import ParserBase


class DouyinParser(ParserBase):
    """Parse one publicly accessible Douyin video into the normal episode tree."""

    def parse(self, url: str, pn: int = 1, get_info_data: bool = False):
        self.url = url
        media = DouyinClient.fetch(url)

        episode_id = EpisodeData.add_episode()
        EpisodeData.get_episode_data(episode_id).update(
            {
                "platform": "douyin",
                "douyin_aweme_id": media.aweme_id,
                "media_url": media.media_url,
                "media_headers": media.media_headers or DouyinClient.media_headers(),
                "media_width": media.width,
                "media_height": media.height,
            }
        )

        item = TreeItem(
            {
                "episode_id": episode_id,
                "cover": media.cover_url,
                "duration": media.duration,
                "number": 1,
                "pubtime": media.publish_time,
                "title": media.title,
                "url": self.url,
                "uploader": media.author,
                "uploader_uid": media.author_id,
            }
        )
        item.set_attribute(Attribute.VIDEO_BIT | Attribute.NORMAL_BIT)

        root = TreeItem({"number": "抖音", "title": media.title})
        root.set_attribute(Attribute.TREE_NODE_BIT)
        root.add_child(item)

        self.info_data = {
            "platform": "douyin",
            "title": media.title,
            "duration": media.duration,
            "cover": media.cover_url,
            "uploader": media.author,
        }

        if get_info_data:
            return self.info_data

        self.update_episode_list(root, ("cid", 0))

    def get_parser_type(self):
        # Reuse the existing user-upload category and naming rules.
        return ParserType.VIDEO
