import re
from enum import EnumType

from aiogram.filters import Filter
from aiogram.types import Message


class FilterUrlRegex(EnumType):
    instagram = r"https://[w.]*instagram\.com/[reel|share]*/\S*"
    tiktok = r"https://vm.tiktok.com/\S*/"
    twitter = r"https://x.com/\S*"
    youtube = r"https://[w.]*youtube.com/shorts/\S*"


class IGLinkFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.findall(FilterUrlRegex.instagram, message.text))
        return False


class YTShortsFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.findall(FilterUrlRegex.youtube, message.text))
        return False


class TikTokFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.findall(FilterUrlRegex.tiktok, message.text))
        return False


class XFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            return bool(re.findall(FilterUrlRegex.twitter, message.text))
        return False
