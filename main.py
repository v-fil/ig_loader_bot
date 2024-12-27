import asyncio
import logging
import sys
from os import getenv
import re

from aiogram import Bot, Dispatcher, types

from strategies import registry, Provider, get_provider_by_url

TOKEN = getenv("BOT_TOKEN")
DEBUG = getenv("DEBUG", False)


dp = Dispatcher()


@dp.message()
async def handler(message: types.Message) -> None:
    regex = (r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)"
             r"(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|"
             r"[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")
    urls = re.findall(regex, message.text)
    if not re.findall(regex, message.text):
        return

    coroutines = []
    for _url in urls:
        url = _url[0]
        provider_name = get_provider_by_url(url)
        if provider_name:
            coroutines.append(
                registry.run(
                    provider=getattr(Provider, provider_name),
                    message=message,
                    url=url,
                )
            )
    if coroutines:
        await asyncio.gather(*coroutines)


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info(f'Launching with DEBUG mode: {"on" if DEBUG else "off"}')
    asyncio.run(main())
