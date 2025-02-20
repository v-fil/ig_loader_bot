import logging
from os import path, getcwd
import re
from urllib.error import HTTPError

from pytubefix import YouTube

from strategies.base import AbstractStrategy
from strategies.utils import Answer, Link


class PytubeYtStrategy(AbstractStrategy):
    async def run(self, url: str) -> Answer | None:
        try:
            short_url = re.findall(r"(https://[w.]*youtube.com/shorts/\S*)", url)
            if not short_url:
                return
            yt = YouTube(
                short_url[0],
                use_oauth=True,
                allow_oauth_cache=True,
                token_file=path.join(getcwd(), 'tmp', 'tokens.json'),
            )
            _url = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
                .url
            )
            if _url:
                return Answer([Link(_url)])
        except (HTTPError, TypeError) as e:
            logging.error(e)
            return None


def extract_id(text: str) -> str:
    _id = re.search(r"youtube.com/shorts/(\S*)/?", text).group(1)
    return f"YTShorts:{_id}"
