import re

from aiogram import types

from .base import AbstractRunner
from .strategies import DDInstaStrategy, SnapinstaPlaywrightStrategy


class IGRunner(AbstractRunner):
    def extract_id(self, text: str) -> str:
        _id = re.search(r"https://[w.]*instagram.com/reel[s]?/(\S*)/", text).group(1)
        return f"IG:{_id}"

    strategies = [SnapinstaPlaywrightStrategy(), DDInstaStrategy()]


async def ig_reel_handler(message: types.Message) -> None:
    runner = IGRunner()
    await runner.run(message)
