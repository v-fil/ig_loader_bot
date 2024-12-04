import json
import logging
import re
from os import getenv

from aiohttp import ClientSession

from handlers.base import AbstractStrategy, StrategyType

DEBUG = getenv("DEBUG", False)

logger = logging.getLogger()


class SnaptikSessionStrategy(AbstractStrategy):
    strategy_type = StrategyType.video_url

    async def run(self, text: str) -> str | None:
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
                return video_url
            except IndexError as e:
                logger.error(e)
                return
