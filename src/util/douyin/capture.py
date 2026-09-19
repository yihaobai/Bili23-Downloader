"""Helpers for normalizing data captured from a real Douyin browser page."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


class DouyinCapture:
    """Find video detail objects without depending on a fixed response schema."""

    @classmethod
    def find_detail(cls, responses: list[Any], aweme_id: str) -> dict:
        for response in responses:
            payload = cls.decode(response)

            for node in cls.iter_dicts(payload):
                detail = node.get("aweme_detail")

                if cls.is_detail(detail, aweme_id):
                    return detail

                if cls.is_detail(node, aweme_id):
                    return node

        raise RuntimeError("浏览器响应中未找到抖音视频详情")

    @staticmethod
    def decode(value: Any) -> Any:
        if isinstance(value, dict) and "body" in value:
            value = value["body"]

        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="replace")

        if isinstance(value, str):
            try:
                return json.loads(value)

            except json.JSONDecodeError:
                return None

        return value

    @classmethod
    def iter_dicts(cls, value: Any) -> Iterator[dict]:
        if isinstance(value, dict):
            yield value

            for child in value.values():
                yield from cls.iter_dicts(child)

        elif isinstance(value, list):
            for child in value:
                yield from cls.iter_dicts(child)

    @staticmethod
    def is_detail(value: Any, aweme_id: str) -> bool:
        if not isinstance(value, dict) or not isinstance(value.get("video"), dict):
            return False

        value_id = str(value.get("aweme_id") or value.get("item_id") or "")

        return value_id == str(aweme_id) or bool(value.get("desc"))

