import re

from aiogram.filters import Filter
from aiogram.types import Message


class IGLinkFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(
                re.fullmatch(r"https://[w.]*instagram.com/reel[s]?/\S*", message.text)
            )
        return False


class YTShortsFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.fullmatch(r"https://[w.]*youtube.com/shorts/\S*", message.text))
        return False


class TikTokFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.fullmatch(r"https://vm.tiktok.com/\S*/", message.text))
        return False


class XFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.fullmatch(r"https://x.com/\S*", message.text))
        return False
