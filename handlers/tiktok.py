import re

from aiogram import types

from .base import AbstractRunner
from .strategies import SnaptikSessionStrategy


class TiktokRunner(AbstractRunner):
    def extract_id(self, text: str) -> str:
        _id = re.search(r"https://vm.tiktok.com/(\S*)/", text).group(1)
        return f"TIKTOK:{_id}"

    strategies = [SnaptikSessionStrategy()]


async def tiktok(message: types.Message) -> None:
    runner = TiktokRunner()
    await runner.run(message)
