import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, types

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
    await registry.run(provider=Provider.youtube, message=message)


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
