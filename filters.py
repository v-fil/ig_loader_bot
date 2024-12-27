import re

from aiogram.filters import Filter
from aiogram.types import Message

url_regex = (r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)"
             r"(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|"
             r"[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")


class UrlFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.text and re.findall(url_regex, message.text))
