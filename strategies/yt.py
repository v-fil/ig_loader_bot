import re
import logging

from urllib.error import HTTPError

from pytubefix import YouTube

from strategies.base import AbstractStrategy


class PytubeYtStrategy(AbstractStrategy):
    async def run(self, url: str) -> str | None:
        try:
            short_url = re.findall(r"(https://[w.]*youtube.com/shorts/\S*)", url)
            if not short_url:
                return
            yt = YouTube(short_url[0], use_oauth=False, allow_oauth_cache=True)
            _url = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
                .url
            )
            if _url:
                return _url
        except (HTTPError, TypeError) as e:
            logging.error(e)
            return None


def extract_id(text: str) -> str:
    _id = re.search(r"youtube.com/shorts/(\S*)/?", text).group(1)
    return f"YTShorts:{_id}"
