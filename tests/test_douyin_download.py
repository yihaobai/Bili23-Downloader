import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from util.common.enum import DownloadType
from util.download.downloader.merger import Merger
from util.download.downloader.parse_worker import ParseWorker
from util.download.task.info import TaskInfo


class DouyinDownloadTests(unittest.TestCase):
    def make_task(self):
        task = TaskInfo()
        task.Basic.task_id = "test-douyin"
        task.Episode.platform = "douyin"
        task.Episode.media_url = "https://v26-web.douyinvod.com/video.mp4"
        task.Episode.media_headers = {"Referer": "https://www.douyin.com/"}
        task.Download.type = DownloadType.VIDEO
        return task

    def test_parse_creates_one_unsegmented_download(self):
        task = self.make_task()
        with patch(
            "util.download.downloader.parse_worker.resolve_download_url",
            return_value={"url": task.Episode.media_url, "file_size": 2048},
        ):
            info = ParseWorker(task).parse_douyin_download_info()

        self.assertEqual(task.Download.video_parts_count, 0)
        self.assertFalse(task.Download.merge_video_audio)
        self.assertEqual(info["download_list"]["video"]["file_name"], "video_test-douyin.mp4")

    def test_old_task_renames_single_mp4_without_concat(self):
        task = self.make_task()
        task.Download.video_parts_count = 1  # Persisted by an older version.
        task.File.video_file_ext = "mp4"
        task.File.name = "下载结果"

        with tempfile.TemporaryDirectory() as folder:
            task.File.download_path = folder
            source = Path(folder, "video_test-douyin.mp4")
            source.write_bytes(b"\x00\x00\x00\x18ftypisom")

            merger = Merger(task)
            with patch("util.download.downloader.merger.task_manager.update"), patch.object(
                merger, "mark_as_completed"
            ) as completed, patch.object(merger, "merge_video_parts") as concat:
                merger.start()

            self.assertFalse(source.exists())
            self.assertTrue(Path(folder, "下载结果.mp4").exists())
            self.assertEqual(task.File.relative_files, ["下载结果.mp4"])
            completed.assert_called_once()
            concat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
