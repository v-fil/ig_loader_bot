import asyncio
import logging
import re
import sys
from os import getenv

from aiogram import Bot, Dispatcher, types
from pytube import YouTube

from filters import IGLinkFilter, TikTokFilter, XFilter, YTShortsFilter
from strategies import registry, Provider

TOKEN = getenv("BOT_TOKEN")
DEBUG = getenv("DEBUG", False)


dp = Dispatcher()


@dp.message(IGLinkFilter())
async def ig_reel_handler(message: types.Message) -> None:
    await registry.run(provider=Provider.instagram, message=message)


@dp.message(YTShortsFilter())
async def yt_shorts_handler(message: types.Message) -> None:
    if not message.text:
        return
    try:
        short_url = re.findall(r"(https://[w.]*youtube.com/shorts/\S*)", message.text)
        if not short_url:
            return
        yt = YouTube(short_url[0])
        _url = (
            yt.streams.filter(progressive=True, file_extension="mp4")
            .order_by("resolution")
            .desc()
            .first()
            .url
        )
        if _url:
            await message.answer_video(
                _url, reply_to_message_id=message.message_id, supports_streaming=True
            )
    except TypeError:
        pass


@dp.message(TikTokFilter())
async def tiktok_handler(message: types.Message) -> None:
    await registry.run(provider=Provider.tiktok, message=message)


@dp.message(XFilter())
async def twitter_handler(message: types.Message) -> None:
    await registry.run(provider=Provider.twitter, message=message)


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info(f'Launching with DEBUG mode: {"on" if DEBUG else "off"}')
    asyncio.run(main())
