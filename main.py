import asyncio
import logging
import re
import sys
from os import getcwd, getenv
from os.path import join

import newrelic.agent
from aiogram import Bot, Dispatcher
from aiogram.types import Message

from filters import PingFilter, UrlFilter, url_regex
from strategies import Provider, get_provider_by_url, registry

TOKEN = getenv("BOT_TOKEN")
DEBUG = getenv("DEBUG", False)


dp = Dispatcher()


@dp.message(UrlFilter())
@newrelic.agent.background_task()
async def handler(message: Message) -> None:
    urls = re.findall(url_regex, message.text)

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


@dp.message(PingFilter())
async def ping(message: Message) -> None:
    await message.answer("pong")


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info(f'Launching with DEBUG mode: {"on" if DEBUG else "off"}')

    newrelic.agent.initialize(join(getcwd(), 'newrelic.ini'), environment='staging' if DEBUG else 'production')

    asyncio.run(main())
