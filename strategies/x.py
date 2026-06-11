import logging
import re

from aiohttp import ClientSession

from strategies.base import AbstractStrategy
from strategies.types import FileType, ResultType
from strategies.utils import Answer, Link

logger = logging.getLogger()

TWEET_URL_RE = re.compile(r"https?://(?:x|twitter)\.com/([^/\s]+)/status/(\d+)")


class FxTwitterStrategy(AbstractStrategy):
    api_base = "https://api.fxtwitter.com"

    async def run(self, url: str) -> Answer | None:
        match = TWEET_URL_RE.search(url)
        if not match:
            return None
        screen_name, status_id = match.group(1), match.group(2)

        async with ClientSession() as session:
            async with session.get(f"{self.api_base}/{screen_name}/status/{status_id}") as resp:
                if resp.status != 200:
                    logger.error(f"fxtwitter returned status {resp.status} for {status_id}")
                    return None
                try:
                    data = await resp.json(content_type=None)
                except Exception as e:
                    logger.error(f"fxtwitter returned non-JSON: {e}")
                    return None

        media = (data.get("tweet") or {}).get("media") or {}
        items = media.get("all") or []
        if not items:
            return None

        links: list[Link] = []
        for idx, item in enumerate(items):
            media_url = item.get("url")
            if not media_url:
                continue
            kind = item.get("type")
            if kind in ("video", "gif"):
                links.append(Link(media_url, FileType.video, f"x_{status_id}_{idx}.mp4"))
            elif kind == "photo":
                links.append(Link(media_url, FileType.img, f"x_{status_id}_{idx}.jpg"))

        if not links:
            return None
        if len(links) == 1 and links[0].filetype == FileType.video:
            return Answer([Link(links[0].url)])
        return Answer(links, result_type=ResultType.items_list)


def extract_id(text: str) -> str:
    match = TWEET_URL_RE.search(text)
    if not match:
        raise ValueError(f"Could not extract X/Twitter ID from: {text}")
    return f"X:{match.group(2)}"
