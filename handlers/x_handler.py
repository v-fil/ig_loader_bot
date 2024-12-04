import re

from aiogram import types

from .base import AbstractRunner
from .strategies import SSSPlaywrightStrategy, TwitterLoadStrategy


class XRunner(AbstractRunner):
    strategies = [SSSPlaywrightStrategy(), TwitterLoadStrategy()]

    def extract_id(self, text: str) -> str:
        _id = re.search(r"https://x.com/\S*/status/(\S*)/", text).group(1)
        return f"X:{_id}"


async def x_handler(message: types.Message) -> None:
    runner = XRunner()
    await runner.run(message)
