import json
import logging
import re
from os import getenv

from aiohttp import ClientSession

from strategies.base import AbstractStrategy
from strategies.utils import Answer, Link, USER_AGENT

DEBUG = getenv("DEBUG", "").lower() in ("1", "true", "yes")

logger = logging.getLogger()


class SnaptikSessionStrategy(AbstractStrategy):
    async def run(self, text: str) -> Answer | None:
        async with ClientSession() as session:
            session.headers.update({"User-Agent": USER_AGENT})
            async with session.get("https://snaptik.pro/") as resp:
                page = await resp.text()
            token_match = re.search(
                '<input type="hidden" name="token" value="(.*?)">', page
            )
            if not token_match:
                logger.error("snaptik: token not found on page")
                return None
            data = {"url": text, "token": token_match.group(1), "submit": "1"}
            async with session.post("https://snaptik.pro/action", data=data) as resp:
                try:
                    result = json.loads(await resp.text())
                except ValueError:
                    logger.error("snaptik: non-JSON response")
                    return None

            if result.get("error"):
                return None

            link_match = re.search(
                '<div class="btn-container mb-1"><a href="(.*?)" target="_blank" rel="noreferrer">',
                result.get("html") or "",
            )
            if not link_match:
                logger.error("snaptik: download link not found in response")
                return None
            return Answer([Link(link_match.group(1))])


def extract_id(text: str) -> str:
    match = re.search(r"https://\S+?\.tiktok\.com/.*/video/(\d+)", text)
    if not match:
        match = re.search(r"https://\S+?\.tiktok\.com/(\S+?)/", text)
    if not match:
        raise ValueError(f"Could not extract TikTok ID from: {text}")
    return f"TIKTOK:{match.group(1)}"


async def preprocess_url(url: str) -> str:
    if re.match(r"https://v[a-z]\.tiktok\.com/", url):
        async with ClientSession() as session:
            async with session.get(url, allow_redirects=False) as result:
                location = result.headers.get('Location')
            if location:
                return location
            logger.warning(f"No redirect Location header for TikTok URL: {url}")
    return url
