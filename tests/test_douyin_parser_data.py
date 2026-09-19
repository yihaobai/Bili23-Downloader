import unittest


class DouyinParserDataTests(unittest.TestCase):
    """Keep the provider payload contract explicit without starting Qt."""

    def test_task_provider_fields_are_optional_and_default_to_bilibili(self):
        # The dataclass is intentionally tested through its source contract here;
        # the full TaskInfo import requires the desktop Qt dependencies.
        from pathlib import Path

        source = Path(__file__).parents[1] / "src" / "util" / "download" / "task" / "info.py"
        text = source.read_text(encoding="utf-8")

        self.assertIn('platform: str = "bilibili"', text)
        self.assertIn('douyin_aweme_id: str = ""', text)
        self.assertIn('media_headers: dict = field(default_factory = dict)', text)


if __name__ == "__main__":
    unittest.main()
