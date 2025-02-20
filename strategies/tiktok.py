import json
import logging
import re
from os import getenv

from aiohttp import ClientSession

from strategies.base import AbstractStrategy
from strategies.utils import Answer, Link

DEBUG = getenv("DEBUG", False)

logger = logging.getLogger()


class SnaptikSessionStrategy(AbstractStrategy):
    async def run(self, text: str) -> Answer | None:
        async with ClientSession() as session:
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118."
                }
            )
            result = await (await session.get("https://snaptik.pro/")).text()
            token = re.search(
                '<input type="hidden" name="token" value="(.*?)">', result
            ).group(1)
            data = {"url": text, "token": token, "submit": "1"}
            response = await session.post("https://snaptik.pro/action", data=data)
            result = json.loads(await response.text())

            if result.get("error"):
                return

            try:
                video_url = re.search(
                    '<div class="btn-container mb-1"><a href="(.*?)" target="_blank" rel="noreferrer">',
                    result["html"],
                ).group(1)
                return Answer([Link(video_url)])
            except IndexError as e:
                logger.error(e)
                return


def extract_id(text: str) -> str:
    _id = re.search(r"https://vm.tiktok.com/(\S*)/", text).group(1)
    return f"TIKTOK:{_id}"


async def preprocess_url(url: str) -> str:
    if 'vm.tiktok' in url:
        async with ClientSession() as session:
            result = await session.get(url, allow_redirects=False)
            return result.headers['Location']
    return url
