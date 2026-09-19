from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re


_AWEME_ID_RE = re.compile(
    r"(?:/(?:video|note|share/video|share/note)/)(\d{8,})(?:[/?#]|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DouyinMedia:
    aweme_id: str
    title: str
    author: str
    author_id: int
    cover_url: str
    media_url: str
    duration: int
    publish_time: int
    width: int
    height: int


class DouyinClient:
    """Client for public Douyin video detail responses.

    Requests are imported lazily so URL and response normalization tests do not
    need to initialize the desktop application's Qt/network stack.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
    REFERER = "https://www.douyin.com/"

    @classmethod
    def is_url(cls, value: str) -> bool:
        if not value:
            return False

        candidate = value.strip()
        if "://" not in candidate:
            candidate = f"https://{candidate}"

        host = (urlsplit(candidate).hostname or "").lower().rstrip(".")
        return host == "douyin.com" or host.endswith(".douyin.com") or host == "iesdouyin.com" or host.endswith(".iesdouyin.com")

    @classmethod
    def extract_aweme_id(cls, url: str) -> str | None:
        """Extract an aweme id from a long URL or resolved share URL."""
        if not url:
            return None

        match = _AWEME_ID_RE.search(url)
        if match:
            return match.group(1)

        query = dict(parse_qsl(urlsplit(url).query))
        for key in ("modal_id", "item_id", "aweme_id"):
            value = query.get(key, "")
            if value.isdigit() and len(value) >= 8:
                return value

        return None

    @classmethod
    def resolve_url(cls, url: str) -> str:
        """Resolve a short share URL using the normal HTTP client."""
        if not cls.is_url(url):
            raise ValueError("不是有效的抖音链接")

        if cls.extract_aweme_id(url):
            return url.strip()

        from ..network.request import ResponseType, SyncNetWorkRequest

        request = SyncNetWorkRequest(
            url.strip(),
            response_type=ResponseType.REDIRECT_URL,
            extra_headers={"Referer": cls.REFERER, "User-Agent": cls.USER_AGENT},
        )
        return request.run()

    @classmethod
    def fetch(cls, url: str) -> DouyinMedia:
        resolved_url = cls.resolve_url(url)
        aweme_id = cls.extract_aweme_id(resolved_url)

        if not aweme_id:
            raise ValueError("无法从抖音链接中识别视频 ID")

        from ..network.request import SyncNetWorkRequest

        endpoint = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
        request = SyncNetWorkRequest(
            endpoint,
            params={"aweme_id": aweme_id},
            extra_headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": cls.REFERER,
                "User-Agent": cls.USER_AGENT,
            },
        )
        response = request.run()
        detail = cls._get_detail(response)

        return cls.normalize_detail(aweme_id, detail)

    @classmethod
    def normalize_detail(cls, aweme_id: str, detail: dict) -> DouyinMedia:
        video = detail.get("video") or {}
        media_url = cls._get_no_watermark_url(video)
        if not media_url:
            raise RuntimeError("抖音接口未返回可下载的视频地址")

        author = detail.get("author") or {}
        title = (detail.get("desc") or "抖音视频").strip() or "抖音视频"
        create_time = int(detail.get("create_time") or 0)

        return DouyinMedia(
            aweme_id=aweme_id,
            title=title,
            author=author.get("nickname") or "",
            author_id=int(author.get("uid") or 0),
            cover_url=cls._first_url((video.get("cover") or {}).get("url_list")),
            media_url=media_url,
            duration=max(int(video.get("duration") or 0) // 1000, 0),
            publish_time=create_time,
            width=int(video.get("width") or 0),
            height=int(video.get("height") or 0),
        )

    @staticmethod
    def _get_detail(response: dict) -> dict:
        # The web endpoint has returned both shapes over time.
        detail = response.get("aweme_detail")
        if isinstance(detail, dict):
            return detail

        data = response.get("data")
        if isinstance(data, dict):
            detail = data.get("aweme_detail") or data.get("aweme_detail_info")
            if isinstance(detail, dict):
                return detail

        if response.get("status_code") not in (None, 0):
            raise RuntimeError(response.get("status_msg") or "抖音接口返回错误")

        raise RuntimeError("抖音接口未返回视频详情，可能需要在浏览器中登录或链接已失效")

    @classmethod
    def _get_no_watermark_url(cls, video: dict) -> str:
        # Prefer the public download address. Older responses only expose a
        # playwm URL, whose public no-watermark form uses /play/.
        candidates = []
        for key in ("download_addr", "play_addr", "play_addr_h264"):
            candidates.extend((video.get(key) or {}).get("url_list") or [])

        for candidate in candidates:
            normalized = cls._remove_watermark(candidate)
            if normalized:
                return normalized

        return ""

    @staticmethod
    def _first_url(urls) -> str:
        if isinstance(urls, list):
            return next((item for item in urls if item), "")
        return ""

    @staticmethod
    def _remove_watermark(url: str) -> str:
        if not isinstance(url, str) or not url:
            return ""

        parts = urlsplit(url)
        path = parts.path.replace("/playwm/", "/play/").replace("playwm", "play")
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in {"watermark", "water_mark"}
        ]
        return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), parts.fragment))
